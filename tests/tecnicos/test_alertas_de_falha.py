"""E15-04: as falhas de comunicação e do provedor, a contagem de avisos recusados e a ciência do
administrador (acceptance A-1 a A-28)."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import Client

from tests.apoio.operacao import (
    INSTANTE,
    MIN,
    Ao,
    alertas,
    arranjo_ao,
    concluir_todas,
    notificacoes,
    verificar,
)
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

HORA = timedelta(hours=1)
URL_DOS_AVISOS = "/pagamentos/avisos/"


@pytest.fixture
def ao(relogio: RelogioControlado) -> Ao:
    return arranjo_ao(relogio)


def _verificar(relogio: RelogioControlado, instante: datetime) -> tuple[int, int]:
    concluir_todas(instante)
    return verificar(relogio, instante)


def _abertos(tipo: str) -> list[Any]:
    return alertas(tipo, abertos=True)


# --- apoio de dados -----------------------------------------------------------------------------


def _envio_falho(concluido_em: datetime) -> Any:
    from tests.fabricas import EnvioFactory

    return EnvioFactory.create(situacao="falhou", concluido_em=concluido_em)


def _chamada(alvo: str, **campos: Any) -> Any:
    from apps.pagamentos.models import ChamadaAoProvedor

    padrao: dict[str, Any] = {
        "operacao": "cancelar_cobranca",
        "alvo": alvo,
        "chave_idempotencia": f"k-{alvo}-{campos.get('operacao', 'x')}",
        "provedor": "simulador",
        "ambiente": "teste",
        "situacao": "falhou",
        "concluida_em": INSTANTE,
        "ultimo_erro": "recusada",
    }
    return ChamadaAoProvedor.objects.create(**{**padrao, **campos})


def _pagamento(id_externo: str, **campos: Any) -> Any:
    from apps.pagamentos.models import PagamentoNoProvedor

    padrao: dict[str, Any] = {
        "provedor": "simulador",
        "ambiente": "teste",
        "id_externo": id_externo,
        "referencia_externa": f"ref-{id_externo}",
        "valor": Decimal("45.90"),
        "situacao": "aprovado",
        "criado_no_provedor_em": INSTANTE - 3 * HORA,
        "expira_em": INSTANTE + 24 * HORA,
        "aprovado_no_provedor_em": INSTANTE - 2 * HORA,
    }
    return PagamentoNoProvedor.objects.create(**{**padrao, **campos})


def _consulta(pagamento: Any, divergencia: str, quando: datetime) -> Any:
    from apps.pagamentos.models import ConsultaDoPagamento

    return ConsultaDoPagamento.objects.create(
        pagamento=pagamento,
        origem="tarefa",
        situacao="aprovado",
        referencia_externa=pagamento.referencia_externa,
        valor=pagamento.valor,
        consultado_em=quando,
        aplicada=True,
        divergencia=divergencia,
    )


def _chamada_falhou_aberta(relogio: RelogioControlado) -> Any:
    _chamada("cob-1")
    _verificar(relogio, INSTANTE)
    (alerta,) = _abertos("chamada_ao_provedor_falhou")
    return alerta


# --- falha de mensagem --------------------------------------------------------------------------


def test_falha_de_mensagem(relogio: RelogioControlado, ao: Ao) -> None:  # A-1
    _envio_falho(INSTANTE - 2 * HORA)
    _envio_falho(INSTANTE - HORA)
    _verificar(relogio, INSTANTE)
    (alerta,) = _abertos("falha_de_mensagem")
    assert alerta.chave == "geral"
    assert alerta.gravidade == "aviso"
    notificacao = next(
        n for n in notificacoes(ao.adm1) if n.titulo == "Falha no envio de mensagens"
    )
    assert notificacao.corpo == (
        "2 mensagem(ns) não foram entregues nas últimas 24 horas. "
        "A mais recente falhou em 20/11/2026 08:00."
    )
    assert notificacao.link == "/administracao/envios/?situacao=falhou"


def test_a_falha_de_mensagem_sai_depois_de_24_horas(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-2
    _envio_falho(INSTANTE - 2 * HORA)
    _envio_falho(INSTANTE - HORA)
    _verificar(relogio, INSTANTE)
    _verificar(relogio, INSTANTE + 23 * HORA)
    assert len(_abertos("falha_de_mensagem")) == 1
    _verificar(relogio, INSTANTE + 23 * HORA + timedelta(seconds=1))
    assert _abertos("falha_de_mensagem") == []


def test_falha_antiga_nao_acusa(relogio: RelogioControlado, ao: Ao) -> None:  # A-3
    _envio_falho(INSTANTE - 24 * HORA - timedelta(seconds=1))
    _verificar(relogio, INSTANTE)
    assert alertas("falha_de_mensagem") == []


# --- chamada ao provedor ------------------------------------------------------------------------


def test_chamada_que_falhou_de_vez(relogio: RelogioControlado, ao: Ao) -> None:  # A-4
    chamada = _chamada("cob-1")
    _verificar(relogio, INSTANTE)
    (alerta,) = _abertos("chamada_ao_provedor_falhou")
    assert alerta.chave == f"chamada:{chamada.pk}"
    notificacao = next(n for n in notificacoes(ao.adm1) if n.titulo == "Chamada ao provedor falhou")
    assert notificacao.corpo == (
        "A operação cancelar_cobranca para cob-1 falhou no provedor (recusada) em 20/11/2026 09:00."
    )
    from apps.operacao.tipos import natureza_do_alerta

    assert natureza_do_alerta(alerta) == "fato"


def test_so_as_operacoes_do_provedor_que_nao_tem_alerta_proprio(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-5
    _chamada("cob-1", operacao="estornar")
    _chamada("cob-2", operacao="criar_cobranca")
    _verificar(relogio, INSTANTE)
    assert alertas("chamada_ao_provedor_falhou") == []
    _chamada("cob-3", operacao="consultar_pagamento")
    _verificar(relogio, INSTANTE)
    assert len(_abertos("chamada_ao_provedor_falhou")) == 1


def test_a_ciencia_resolve_e_a_verificacao_nao_reabre(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-6
    from apps.operacao.ciencia import dar_ciencia

    from apps.nucleo.auditoria import EntradaAuditoria

    alerta = _chamada_falhou_aberta(relogio)
    dar_ciencia(ao.adm1, alerta)
    alerta.refresh_from_db()
    assert alerta.resolvido_em == INSTANTE
    assert alerta.motivo_da_resolucao == "ciência do administrador"
    (entrada,) = EntradaAuditoria.objects.filter(acao="alerta.ciencia")
    assert entrada.autor_id == str(ao.adm1.pk)
    assert entrada.alteracoes == {"tipo": "chamada_ao_provedor_falhou", "chave": alerta.chave}
    assert _verificar(relogio, INSTANTE + 5 * MIN) == (0, 0)
    assert len(alertas("chamada_ao_provedor_falhou")) == 1


# --- divergência de consulta --------------------------------------------------------------------


def test_consulta_com_divergencia(relogio: RelogioControlado, ao: Ao) -> None:  # A-7
    _consulta(_pagamento("pg1"), "valor", INSTANTE)
    _verificar(relogio, INSTANTE)
    (alerta,) = _abertos("consulta_com_divergencia")
    assert alerta.chave == "pg1:valor"
    notificacao = next(
        n for n in notificacoes(ao.adm1) if n.titulo == "Divergência na consulta ao provedor"
    )
    assert "pg1" in notificacao.corpo
    assert "Valor" in notificacao.corpo


def test_reconsulta_igual_nao_abre_outro(relogio: RelogioControlado, ao: Ao) -> None:  # A-8
    pagamento = _pagamento("pg1")
    _consulta(pagamento, "valor", INSTANTE)
    _verificar(relogio, INSTANTE)
    _consulta(pagamento, "valor", INSTANTE + 10 * MIN)
    assert _verificar(relogio, INSTANTE + 11 * MIN) == (0, 0)
    assert len(alertas("consulta_com_divergencia")) == 1


def test_divergencia_nova_depois_da_ciencia_abre_outro(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-9
    from apps.operacao.ciencia import dar_ciencia

    pagamento = _pagamento("pg1")
    _consulta(pagamento, "valor", INSTANTE)
    _verificar(relogio, INSTANTE)
    _consulta(pagamento, "valor", INSTANTE + 10 * MIN)
    _verificar(relogio, INSTANTE + 11 * MIN)
    relogio.congelar(INSTANTE + 20 * MIN)
    dar_ciencia(ao.adm1, _abertos("consulta_com_divergencia")[0])
    _consulta(pagamento, "valor", INSTANTE + 30 * MIN)
    assert _verificar(relogio, INSTANTE + 31 * MIN) == (1, 0)
    todos = alertas("consulta_com_divergencia")
    assert len(todos) == 2
    assert todos[0].resolvido_em == INSTANTE + 20 * MIN


def test_divergencia_com_ciencia_e_sem_consulta_nova(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-10
    from apps.operacao.ciencia import dar_ciencia

    _consulta(_pagamento("pg1"), "valor", INSTANTE)
    _verificar(relogio, INSTANTE)
    dar_ciencia(ao.adm1, _abertos("consulta_com_divergencia")[0])
    assert _verificar(relogio, INSTANTE + HORA) == (0, 0)
    assert len(alertas("consulta_com_divergencia")) == 1


# --- pagamento sem pedido e sem horário ---------------------------------------------------------


def test_pagamento_sem_pedido(relogio: RelogioControlado, ao: Ao) -> None:  # A-11
    from apps.pedidos.models import DestinoDoPagamento

    pagamento = _pagamento("pg2")
    DestinoDoPagamento.objects.create(
        pagamento=pagamento,
        destino="sem_pedido",
        motivo="referencia_desconhecida",
        decidido_em=INSTANTE,
    )
    _verificar(relogio, INSTANTE)
    (alerta,) = _abertos("pagamento_sem_pedido")
    assert alerta.chave == "pagamento:pg2"
    notificacao = next(n for n in notificacoes(ao.adm1) if n.titulo == "Pagamento sem pedido")
    assert "pg2" in notificacao.corpo
    assert "R$ 45,90" in notificacao.corpo
    assert "Referência desconhecida" in notificacao.corpo


def test_pagamento_aprovado_sem_horario(relogio: RelogioControlado, ao: Ao) -> None:  # A-12
    from apps.operacao.tipos import natureza_do_alerta

    _pagamento("pg3", aprovado_no_provedor_em=None)
    _verificar(relogio, INSTANTE)
    (alerta,) = _abertos("pagamento_sem_horario_de_aprovacao")
    assert alerta.chave == "pagamento:pg3"
    assert natureza_do_alerta(alerta) == "condicao"


def test_o_horario_chega_e_o_alerta_se_resolve(relogio: RelogioControlado, ao: Ao) -> None:  # A-13
    from apps.pagamentos.models import PagamentoNoProvedor
    from apps.pedidos.models import DestinoDoPagamento

    pagamento = _pagamento("pg3", aprovado_no_provedor_em=None)
    _verificar(relogio, INSTANTE)
    PagamentoNoProvedor.objects.filter(pk=pagamento.pk).update(
        aprovado_no_provedor_em=INSTANTE - HORA
    )
    DestinoDoPagamento.objects.create(
        pagamento=pagamento, destino="sem_pedido", motivo="referencia_desconhecida"
    )
    _verificar(relogio, INSTANTE + MIN)
    assert _abertos("pagamento_sem_horario_de_aprovacao") == []


# --- avisos recusados em sequência --------------------------------------------------------------


def _recusar(vezes: int) -> list[int]:
    cliente = Client()
    return [
        cliente.post(URL_DOS_AVISOS, data=b'{"x": 1}', content_type="application/json").status_code
        for _ in range(vezes)
    ]


def _sequencia() -> Any:
    from apps.pagamentos.models import SequenciaDeAvisosRecusados

    return SequenciaDeAvisosRecusados.objects.get()


def _aviso_valido(sim: Any, relogio: RelogioControlado) -> int:
    from apps.pagamentos.provedor import NovaCobranca, obter_provedor
    from apps.simulador_pagamentos.controle import corpo_e_cabecalhos
    from apps.simulador_pagamentos.models import AvisoSimulado

    nova = NovaCobranca("kv", "ref-v", Decimal("45.90"), "Pedido", INSTANTE + 24 * HORA)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    sim.aprovar(id_externo, em=INSTANTE)
    corpo, cabecalhos = corpo_e_cabecalhos(AvisoSimulado.objects.get(id_externo=id_externo))
    return (
        Client()
        .post(URL_DOS_AVISOS, data=corpo, content_type="application/json", headers=cabecalhos)
        .status_code
    )


def test_cinco_recusas_abrem_o_alerta(relogio: RelogioControlado, ao: Ao) -> None:  # A-14
    from apps.pagamentos.models import AvisoRecebido

    assert _recusar(5) == [401] * 5
    assert _sequencia().recusas_seguidas == 5
    assert AvisoRecebido.objects.count() == 0
    _verificar(relogio, INSTANTE)
    (alerta,) = _abertos("avisos_recusados_em_sequencia")
    assert alerta.chave == "geral"
    notificacao = next(
        n for n in notificacoes(ao.adm1) if n.titulo == "Avisos do provedor recusados"
    )
    assert notificacao.corpo.startswith(
        "5 avisos seguidos do provedor de pagamentos foram recusados"
    )
    assert "desde 20/11/2026 09:00" in notificacao.corpo


def test_quatro_recusas_nao_alertam(relogio: RelogioControlado, ao: Ao) -> None:  # A-15
    _recusar(4)
    _verificar(relogio, INSTANTE)
    assert alertas("avisos_recusados_em_sequencia") == []


def test_um_aviso_aceito_zera_a_contagem(
    relogio: RelogioControlado, ao: Ao, simulador_pagamentos: Any
) -> None:  # A-16
    _recusar(5)
    _verificar(relogio, INSTANTE)
    assert _aviso_valido(simulador_pagamentos, relogio) == 200
    sequencia = _sequencia()
    assert sequencia.recusas_seguidas == 0
    assert sequencia.primeira_em is None
    assert sequencia.ultima_em is None
    assert _verificar(relogio, INSTANTE + MIN) == (0, 1)


def test_corpo_grande_nao_conta(relogio: RelogioControlado, ao: Ao) -> None:  # A-17
    from apps.pagamentos.avisos import TAMANHO_MAXIMO_DO_AVISO

    _recusar(3)
    grande = b"x" * (TAMANHO_MAXIMO_DO_AVISO + 1)
    resposta = Client().post(URL_DOS_AVISOS, data=grande, content_type="application/json")
    assert resposta.status_code == 400
    assert _sequencia().recusas_seguidas == 3


def test_falha_ao_gravar_a_contagem_nao_muda_a_resposta(
    ao: Ao, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # A-18
    from apps.pagamentos import avisos

    def quebra() -> None:
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr(avisos, "registrar_recusa", quebra)
    with caplog.at_level(logging.ERROR):
        assert _recusar(1) == [401]
    assert "RuntimeError" in " ".join(r.getMessage() for r in caplog.records)


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_dez_recusas_em_cinco_conexoes() -> None:  # A-19
    def recusar_duas() -> list[int]:
        try:
            return _recusar(2)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=5) as pool:
        resultados = [f.result() for f in [pool.submit(recusar_duas) for _ in range(5)]]
    assert [c for r in resultados for c in r] == [401] * 10
    assert _sequencia().recusas_seguidas == 10


def test_a_contagem_guarda_so_tres_campos(ao: Ao) -> None:  # A-20
    from apps.pagamentos.models import SequenciaDeAvisosRecusados

    _recusar(5)
    campos = {c.name for c in SequenciaDeAvisosRecusados._meta.get_fields()}
    assert campos == {"id", "recusas_seguidas", "primeira_em", "ultima_em"}


# --- ciência ------------------------------------------------------------------------------------


def test_so_alerta_de_fato_recebe_ciencia(relogio: RelogioControlado, ao: Ao) -> None:  # A-21
    from apps.operacao.ciencia import CienciaRecusada, dar_ciencia
    from django.db import transaction

    from apps.financeiro.alertas import abrir_alerta
    from apps.nucleo.auditoria import EntradaAuditoria

    _verificar(relogio, INSTANTE + 6 * MIN)  # as tarefas estão em dia; abre uma condição à mão
    with transaction.atomic():
        condicao = abrir_alerta(
            "tarefa_atrasada",
            "x",
            {
                "tarefa": "processar_envios_pendentes",
                "descricao": "Envio de notificações",
                "referencia": INSTANTE.isoformat(),
                "atrasada_desde": INSTANTE.isoformat(),
                "intervalo_minutos": 1,
            },
        )
        financeiro = abrir_alerta("invariante_violado", "geral", {"diferenca": "10.00"})
    for alerta in (condicao, financeiro):
        with pytest.raises(CienciaRecusada) as erro:
            dar_ciencia(ao.adm1, alerta)
        assert erro.value.codigo == "nao_e_fato"
        assert str(erro.value) == "Este alerta se encerra sozinho quando a situação é resolvida."
        alerta.refresh_from_db()
        assert alerta.resolvido_em is None
    assert not EntradaAuditoria.objects.filter(acao="alerta.ciencia").exists()


def test_ciencia_de_alerta_resolvido(relogio: RelogioControlado, ao: Ao) -> None:  # A-22
    from apps.operacao.ciencia import CienciaRecusada, dar_ciencia

    alerta = _chamada_falhou_aberta(relogio)
    dar_ciencia(ao.adm1, alerta)
    with pytest.raises(CienciaRecusada) as erro:
        dar_ciencia(ao.adm1, alerta)
    assert erro.value.codigo == "ja_resolvido"
    assert str(erro.value) == "Este alerta já foi encerrado."


def test_so_o_administrador_da_ciencia(relogio: RelogioControlado, ao: Ao) -> None:  # A-23
    from apps.operacao.ciencia import dar_ciencia

    alerta = _chamada_falhou_aberta(relogio)
    for autor in (ao.c, ao.f, None):
        with pytest.raises(PermissionDenied):
            dar_ciencia(autor, alerta)
    alerta.refresh_from_db()
    assert alerta.resolvido_em is None


@pytest.fixture
def navegador(client: Client, relogio: RelogioControlado, webauthn: Any) -> tuple[Client, Ao]:
    """O administrador autenticado por passkey (o arranjo AO reaproveita a conta dele)."""
    from tests.apoio.admin_fluxos import administrador_com_passkey, entrar_com_passkey_direta

    relogio.congelar(INSTANTE)
    conta, credencial = administrador_com_passkey(client)
    entrar_com_passkey_direta(client, credencial, conta)
    return client, arranjo_ao(relogio)


def test_a_rota_da_ciencia(
    navegador: tuple[Client, Ao], relogio: RelogioControlado
) -> None:  # A-24
    client, _ao = navegador
    alerta = _chamada_falhou_aberta(relogio)
    resposta = client.post(f"/administracao/alertas/{alerta.pk}/ciencia/", follow=True)
    assert resposta.redirect_chain == [("/administracao/", 302)]
    assert "Ciência registrada." in resposta.content.decode()
    alerta.refresh_from_db()
    assert alerta.resolvido_em is not None


def test_a_rota_recusa_o_que_nao_e_fato(
    navegador: tuple[Client, Ao], relogio: RelogioControlado
) -> None:  # A-25
    from django.db import transaction

    from apps.financeiro.alertas import abrir_alerta
    from apps.nucleo.auditoria import EntradaAuditoria

    client, _ao = navegador
    with transaction.atomic():
        financeiro = abrir_alerta("invariante_violado", "geral", {"diferenca": "10.00"})
    resposta = client.post(f"/administracao/alertas/{financeiro.pk}/ciencia/", follow=True)
    assert resposta.redirect_chain == [("/administracao/", 302)]
    assert "Este alerta se encerra sozinho quando a situação é resolvida." in (
        resposta.content.decode()
    )
    financeiro.refresh_from_db()
    assert financeiro.resolvido_em is None
    assert not EntradaAuditoria.objects.filter(acao="alerta.ciencia").exists()


def test_a_rota_recusa_o_que_nao_deve(
    navegador: tuple[Client, Ao], relogio: RelogioControlado
) -> None:  # A-26
    from tests.apoio.admin_fluxos import entrar_com_passkey_direta  # noqa: F401

    client, ao = navegador
    alerta = _chamada_falhou_aberta(relogio)
    url = f"/administracao/alertas/{alerta.pk}/ciencia/"
    assert client.get(url).status_code == 405
    assert client.post("/administracao/alertas/999999/ciencia/").status_code == 404
    for conta in (ao.c, ao.f):
        outro = Client()
        outro.force_login(conta)
        assert outro.post(url).status_code == 403
    anonimo = Client().post(url)
    assert anonimo.status_code == 302
    assert "/entrar/" in anonimo["Location"]
    alerta.refresh_from_db()
    assert alerta.resolvido_em is None


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_duas_ciencias_ao_mesmo_tempo(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-27
    from apps.operacao.ciencia import CienciaRecusada, dar_ciencia

    from apps.nucleo.auditoria import EntradaAuditoria
    from apps.operacao import ciencia
    from tests.apoio.corrida import Corrida

    ao = arranjo_ao(relogio)
    alerta = _chamada_falhou_aberta(relogio)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, ciencia, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: dar_ciencia(ao.adm1, alerta),
        lambda: dar_ciencia(ao.adm1, alerta),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, CienciaRecusada), repr(rb.excecao)
    assert rb.excecao.codigo == "ja_resolvido"
    assert corrida.b_esperou
    assert EntradaAuditoria.objects.filter(acao="alerta.ciencia").count() == 1


def test_nenhum_dado_de_comprador_nos_alertas(relogio: RelogioControlado, ao: Ao) -> None:  # A-28
    from tests.fabricas import ContaFactory

    ContaFactory.create(nome="Maria Compradora", email_normalizado="maria@exemplo.com")
    _chamada("cob-1")
    _envio_falho(INSTANTE - HORA)
    _consulta(_pagamento("pg1"), "valor", INSTANTE)
    _pagamento("pg3", aprovado_no_provedor_em=None)
    _recusar(5)
    _verificar(relogio, INSTANTE)
    assert len(alertas()) >= 5
    texto = " ".join(f"{a.dados} {a.chave}" for a in alertas())
    texto += " ".join(n.corpo + n.titulo for n in notificacoes(ao.adm1))
    assert "Maria" not in texto
    assert "maria@exemplo.com" not in texto
