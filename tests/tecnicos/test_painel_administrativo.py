"""E15-05: o painel do administrador em `administracao/` (acceptance A-1 a A-25)."""

import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.test import Client
from django.urls import reverse

from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import H
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.entrega import (
    arranjo_ae,
    descartar,
    item_de,
    liberar,
    ocorrer,
    receber,
    receber_tudo,
    registrar_endereco,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
L = T0 + 72 * H
URL = "/administracao/"
TITULOS = [
    "Alertas abertos",
    "Ações necessárias",
    "Rodadas",
    "Prazos encerrados",
    "Tarefas periódicas",
]


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


class Painel:
    """O administrador autenticado por passkey, que lê o painel em qualquer instante."""

    def __init__(self, client: Client, relogio: RelogioControlado) -> None:
        self.client = client
        self.relogio = relogio
        relogio.congelar(T0)
        self.admin, self.credencial = administrador_com_passkey(client)

    def pagina(self, instante: Any = None) -> Any:
        if instante is not None:
            self.relogio.congelar(instante)
        entrar_de_novo(self.client, self.credencial, self.admin)
        return self.client.get(URL)


@pytest.fixture
def painel(client: Client, relogio: RelogioControlado) -> Painel:
    return Painel(client, relogio)


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _secoes(resposta: Any) -> dict[str, str]:
    """O texto de cada seção `<h2>`, pelo título."""
    html = resposta.content.decode()
    achados = re.split(r"<h2[^>]*>(.*?)</h2>", html, flags=re.DOTALL)
    return {
        " ".join(achados[i].split()): " ".join(re.sub(r"<[^>]+>", " ", achados[i + 1]).split())
        for i in range(1, len(achados) - 1, 2)
    }


def _html_da_secao(resposta: Any, titulo: str) -> str:
    html: str = resposta.content.decode()
    inicio = html.index(f">{titulo}</h2>")
    proximo = html.find("<h2", inicio + 1)
    return html[inicio : proximo if proximo != -1 else len(html)]


def _ap_i(minimo: str = "200.00") -> Any:
    """O AP-I: G em interesse, produto Q de R$ 10,00 por unidade com múltiplo 12 e 18 reservadas."""
    from apps.fornecedores.models import Fornecedor
    from tests.apoio.interesses import cenario, reservada

    rodada, produto, _estoque = cenario(limite="30", nome="Q", preco=D("10.00"), multiplo=D("12"))
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(nome="G", minimo=D(minimo))
    reservada(ContaFactory.create(nome="Comprador Secreto"), produto, 18)
    return rodada


def _ae(relogio: RelogioControlado, sim: Any, **opcoes: Any) -> tuple[Any, Any, Any, Any]:
    a, x, y, pf = arranjo_ae(relogio, sim, **opcoes)
    registrar_endereco(a.admin)
    return a, x, y, pf


def _saidas(a: Any) -> None:
    """O repasse total e o frete, como pela tela da E13-06 (pelos serviços)."""
    from apps.pedidos.repasse import registrar_pagamento_do_frete, registrar_repasse

    registrar_repasse(
        a.admin, a.rodada, valor=D("170.00"), identificacao="rep-1", justificativa="Repasse"
    )
    registrar_pagamento_do_frete(
        a.admin, a.rodada, valor=D("22.00"), identificacao="fre-1", justificativa="Frete"
    )


# --- seções e alertas ---------------------------------------------------------------------------


def test_as_secoes_e_as_mensagens_vazias(painel: Painel) -> None:  # A-1
    resposta = painel.pagina()
    assert resposta.status_code == 200
    secoes = _secoes(resposta)
    nomes = [n for n in secoes if n in TITULOS]
    assert nomes == TITULOS
    assert "Nenhum alerta aberto." in secoes["Alertas abertos"]
    assert "Nenhuma ação pendente." in secoes["Ações necessárias"]
    assert "Nenhuma rodada em andamento." in secoes["Rodadas"]
    assert "Nenhum prazo encerrado aguardando." in secoes["Prazos encerrados"]


def test_os_alertas_abertos_e_a_ciencia(painel: Painel) -> None:  # A-2
    from apps.financeiro.alertas import abrir_alerta

    with transaction.atomic():
        atrasada = abrir_alerta(
            "tarefa_atrasada",
            "processar_envios_pendentes",
            {
                "tarefa": "processar_envios_pendentes",
                "descricao": "Envio de notificações",
                "referencia": T0.isoformat(),
                "atrasada_desde": T0.isoformat(),
                "intervalo_minutos": 1,
            },
        )
        falhou = abrir_alerta(
            "chamada_ao_provedor_falhou",
            "chamada:1",
            {
                "chamada": 1,
                "operacao": "cancelar_cobranca",
                "alvo": "cob-1",
                "erro": "recusada",
                "concluida_em": T0.isoformat(),
            },
        )
    painel.relogio.avancar(timedelta(minutes=1))
    with transaction.atomic():
        invariante = abrir_alerta("invariante_violado", "geral", {"diferenca": "10.00"})
    resposta = painel.pagina()
    html = _html_da_secao(resposta, "Alertas abertos")
    posicoes = [html.index(t) for t in ("Alerta crítico: saldo", "Tarefa atrasada", "Chamada ao")]
    assert posicoes == sorted(posicoes)
    texto = _secoes(resposta)["Alertas abertos"]
    assert "Crítico" in texto
    assert texto.count("Aviso") >= 2
    assert "Ver" in texto
    assert "aberto em 03/11/2026" in texto
    assert f'action="/administracao/alertas/{falhou.pk}/ciencia/"' in html
    assert f'action="/administracao/alertas/{atrasada.pk}/ciencia/"' not in html
    assert f'action="/administracao/alertas/{invariante.pk}/ciencia/"' not in html
    assert "csrfmiddlewaretoken" in html
    assert "Dar ciência" in texto


# --- rodadas ------------------------------------------------------------------------------------


def test_a_rodada_em_interesse(painel: Painel) -> None:  # A-3
    rodada = _ap_i()
    resposta = painel.pagina()
    texto = _secoes(resposta)["Rodadas"]
    assert "G" in texto
    assert "Interesse" in texto
    assert "R$ 120,00 de R$ 200,00 (60%)" in texto
    assert "Q: 6 unidade aguardando, faltam 6 para a próxima caixa" in texto
    assert "Abrir" in texto
    assert reverse("rodadas_estoque", args=[rodada.pk]) in _html_da_secao(resposta, "Rodadas")
    assert "Nenhuma ação pendente." in _secoes(resposta)["Ações necessárias"]


def test_minimo_atingido_e_acao(painel: Painel) -> None:  # A-4
    rodada = _ap_i("100.00")
    resposta = painel.pagina()
    secao = _secoes(resposta)["Ações necessárias"]
    assert "G" in secao
    assert "Mínimo atingido: o fechamento pode ser iniciado." in secao
    assert reverse("rodadas_estoque", args=[rodada.pk]) in _html_da_secao(
        resposta, "Ações necessárias"
    )


def test_fechamento_e_prazo_vencido(painel: Painel) -> None:  # A-5
    from apps.rodadas.fechamento import prazo_do_fechamento
    from tests.apoio.ciclos import simular_inicio_do_fechamento

    rodada = _ap_i("100.00")
    simular_inicio_do_fechamento(rodada)
    prazo = prazo_do_fechamento(rodada)
    assert prazo is not None
    antes = painel.pagina(prazo - timedelta(minutes=1))
    assert "Fecha em 04/11/2026 10:00" in _secoes(antes)["Rodadas"]
    assert "Q: 6 unidade aguardando" in _secoes(antes)["Rodadas"]
    assert "Nenhum prazo encerrado aguardando." in _secoes(antes)["Prazos encerrados"]
    depois = painel.pagina(prazo + timedelta(minutes=1))
    assert (
        "G: fechamento vencido em 04/11/2026 10:00, aguardando o encerramento automático."
        in _secoes(depois)["Prazos encerrados"]
    )


def test_fechamento_encerrado(painel: Painel) -> None:  # A-6
    from apps.rodadas.fechamento import encerrar_fechamentos_vencidos, prazo_do_fechamento
    from tests.apoio.ciclos import simular_inicio_do_fechamento

    rodada = _ap_i("100.00")
    simular_inicio_do_fechamento(rodada)
    prazo = prazo_do_fechamento(rodada)
    assert prazo is not None
    painel.relogio.congelar(prazo + timedelta(minutes=1))
    assert encerrar_fechamentos_vencidos() == 1
    resposta = painel.pagina()
    secoes = _secoes(resposta)
    assert "Fechamento com prazo encerrado" in secoes["Rodadas"]
    assert "Encerrado em 04/11/2026 10:00" in secoes["Rodadas"]
    assert "Q:" not in secoes["Rodadas"]
    assert "Fechamento encerrado: aguarda a abertura do pagamento." in secoes["Ações necessárias"]
    assert "G: fechamento encerrado em 04/11/2026 10:00." in secoes["Prazos encerrados"]


def test_pagamento_e_a_margem(painel: Painel) -> None:  # A-7
    from tests.apoio.apuracao import arranjo_ap

    a, _x, _y = arranjo_ap(painel.relogio)
    cedo = painel.pagina(T0 + H)
    rodadas = _secoes(cedo)["Rodadas"]
    assert "Pagamento até 04/11/2026 10:00; margem até 05/11/2026 10:00" in rodadas
    assert "Apta para a apuração final" not in _secoes(cedo)["Ações necessárias"]
    tarde = painel.pagina(T0 + 48 * H)
    assert (
        "Apta para a apuração final desde 05/11/2026 10:00." in _secoes(tarde)["Ações necessárias"]
    )
    assert "margem encerrada em 05/11/2026 10:00" in _secoes(tarde)["Prazos encerrados"]
    assert a.fornecedor.nome in _secoes(tarde)["Prazos encerrados"]


def test_apuracao_feita_aguarda_aprovacao(painel: Painel, sim: Any) -> None:  # A-8
    from apps.pedidos.apuracao import iniciar_apuracao
    from tests.apoio.apuracao import arranjo_ap, pagar

    a, x, y = arranjo_ap(painel.relogio)
    pagar(painel.relogio, sim, x)
    pagar(painel.relogio, sim, y)
    painel.relogio.congelar(T0 + 48 * H)
    iniciar_apuracao(a.admin, a.rodada)
    resposta = painel.pagina()
    acoes = _secoes(resposta)["Ações necessárias"]
    assert "Apuração feita: aguarda a aprovação do resultado." in acoes
    assert "Apta para a apuração" not in acoes
    assert "margem encerrada" not in _secoes(resposta)["Prazos encerrados"]


# --- aguardando fornecedor ----------------------------------------------------------------------


def test_pedido_formal_nao_enviado(painel: Painel, sim: Any, settings: Any) -> None:  # A-9
    from tests.apoio.pedido_formal import af_falhas

    a, _x, _y, _pf = af_falhas(painel.relogio, sim, settings)
    resposta = painel.pagina()
    acoes = _secoes(resposta)["Ações necessárias"]
    assert "O pedido formal não foi enviado depois das três tentativas: reenvie." in acoes
    assert reverse("rodadas_pedido_formal", args=[a.rodada.pk]) in _html_da_secao(
        resposta, "Ações necessárias"
    )


def test_recebimento_a_resolver(painel: Painel, sim: Any) -> None:  # A-10
    a, _x, _y, _pf = _ae(painel.relogio, sim)
    receber(a.admin, a.rodada, a.p1, D("11"))
    acoes = _secoes(painel.pagina())["Ações necessárias"]
    assert "Recebimento: 1 produto(s) a resolver." in acoes


def test_recebimento_resolvido_e_endereco(painel: Painel, sim: Any) -> None:  # A-11
    a, _x, _y, pf = arranjo_ae(painel.relogio, sim)
    receber_tudo(a, pf)
    sem = _secoes(painel.pagina())["Ações necessárias"]
    assert (
        "Recebimento resolvido: a retirada pode ser liberada. "
        "Registre antes o endereço de retirada." in sem
    )
    registrar_endereco(a.admin)
    com = _secoes(painel.pagina())["Ações necessárias"]
    assert "Recebimento resolvido: a retirada pode ser liberada." in com
    assert "Registre antes" not in com


def test_repasse_e_frete_liberados(painel: Painel, sim: Any) -> None:  # A-12
    a, _x, _y, _pf = _ae(painel.relogio, sim, liberacao_horas=0)
    acoes = _secoes(painel.pagina())["Ações necessárias"]
    assert "Repasse ao fornecedor liberado: R$ 170,00." in acoes
    assert "Pagamento do frete liberado: R$ 22,00." in acoes
    _saidas(a)
    depois = _secoes(painel.pagina())["Ações necessárias"]
    assert "Repasse ao fornecedor liberado" not in depois
    assert "Pagamento do frete liberado" not in depois


# --- retirada -----------------------------------------------------------------------------------


def _liberada(painel: Painel, sim: Any) -> tuple[Any, Any, Any]:
    a, x, y, pf = _ae(painel.relogio, sim, liberacao_horas=0)
    receber_tudo(a, pf)
    liberar(painel.relogio, a)
    return a, x, y


def test_prazo_de_retirada_encerrado(painel: Painel, sim: Any) -> None:  # A-13
    a, _x, _y = _liberada(painel, sim)
    _saidas(a)
    resposta = painel.pagina(L + timedelta(days=8))
    secoes = _secoes(resposta)
    assert "Disponível para retirada" in secoes["Rodadas"]
    assert "Retirada até 12/11/2026 10:00" in secoes["Rodadas"]
    assert (
        "Prazo de retirada encerrado: 4 item(ns) pendente(s) de decisão."
        in secoes["Ações necessárias"]
    )
    assert (
        "retirada encerrada em 12/11/2026 10:00, com itens pendentes."
        in secoes["Prazos encerrados"]
    )
    assert reverse("rodadas_retiradas", args=[a.rodada.pk]) in _html_da_secao(
        resposta, "Prazos encerrados"
    )


def test_sem_saldo_a_rodada_sai_do_painel(painel: Painel, sim: Any) -> None:  # A-14
    from apps.pedidos.models import ItemDoPedido
    from apps.pedidos.ocorrencias import saldo_do_item

    a, _x, _y = _liberada(painel, sim)
    _saidas(a)
    painel.relogio.congelar(L + timedelta(days=8))
    for item in ItemDoPedido.objects.filter(pedido__abertura__rodada=a.rodada):
        descartar(a.admin, item, saldo_do_item(item))
    resposta = painel.pagina()
    secoes = _secoes(resposta)
    assert "Nenhuma rodada em andamento." in secoes["Rodadas"]
    assert "Nenhuma ação pendente." in secoes["Ações necessárias"]
    assert "Nenhum prazo encerrado aguardando." in secoes["Prazos encerrados"]


def test_rodada_cancelada_fora_do_painel(painel: Painel, sim: Any) -> None:  # A-15
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, _x, _y, _pf = _ae(painel.relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    secoes = _secoes(painel.pagina())
    assert "Nenhuma rodada em andamento." in secoes["Rodadas"]
    assert "Nenhum prazo encerrado aguardando." in secoes["Prazos encerrados"]
    assert a.fornecedor.nome not in secoes["Ações necessárias"]


# --- globais ------------------------------------------------------------------------------------


def test_devolucoes_a_autorizar(painel: Painel, sim: Any) -> None:  # A-16
    from apps.financeiro.devolucoes import autorizar_devolucao

    a, x, _y, _pf = _ae(painel.relogio, sim)
    resultado = ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    resposta = painel.pagina()
    acoes = _secoes(resposta)["Ações necessárias"]
    assert "Devoluções a autorizar: 1 (R$ 23,59)." in acoes
    assert reverse("financeiro_devolucoes") in _html_da_secao(resposta, "Ações necessárias")
    autorizar_devolucao(resultado.reembolso.obrigacao, autor=a.admin)
    assert "Devoluções a autorizar" not in _secoes(painel.pagina())["Ações necessárias"]


def test_itens_sem_cobertura(painel: Painel, sim: Any) -> None:  # A-17
    a, _x, y, pf = _ae(painel.relogio, sim, liberacao_horas=0)
    from apps.pedidos.repasse import registrar_repasse

    registrar_repasse(
        a.admin, a.rodada, valor=D("170.00"), identificacao="rep-1", justificativa="Repasse"
    )
    receber_tudo(a, pf)
    liberar(painel.relogio, a)
    painel.relogio.congelar(L + timedelta(days=1))
    ocorrer(a.admin, item_de(y, a.p2), D("2"), "incorreto")
    resposta = painel.pagina()
    acoes = _secoes(resposta)["Ações necessárias"]
    assert "Itens sem cobertura: 1 (R$ 10,00)." in acoes
    assert reverse("financeiro_reserva") in _html_da_secao(resposta, "Ações necessárias")


def test_a_ordem_das_acoes(painel: Painel, sim: Any) -> None:  # A-18
    from apps.fornecedores.models import Fornecedor

    a, x, _y, _pf = _ae(painel.relogio, sim)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(nome="Zeta")
    g = _ap_i("100.00")
    Fornecedor.objects.filter(pk=g.fornecedor_id).update(nome="Alfa")
    painel.relogio.congelar(T0 + H)
    acoes = _secoes(painel.pagina())["Ações necessárias"]
    ordem = [acoes.index(t) for t in ("Alfa", "Zeta", "Devoluções a autorizar")]
    assert ordem == sorted(ordem)
    assert g.pk > a.rodada.pk  # a ordem alfabética difere da ordem dos pk


# --- tarefas ------------------------------------------------------------------------------------


def test_as_tarefas_e_a_conciliacao(painel: Painel) -> None:  # A-19
    from datetime import date

    from apps.financeiro.models import ConciliacaoDiaria
    from apps.operacao.models import ExecucaoDaTarefa
    from tests.apoio.operacao import INSTANTE, concluir_todas

    painel.relogio.congelar(INSTANTE)
    concluir_todas(INSTANTE, exceto=("processar_envios_pendentes", "verificar_operacao"))
    ExecucaoDaTarefa.objects.create(
        nome="processar_envios_pendentes",
        monitorada_desde=INSTANTE - 3 * H,
        ultima_conclusao_em=INSTANTE - 3 * H,
        ultima_falha_em=INSTANTE - H,
        ultimo_erro="RuntimeError",
        falhas_seguidas=2,
    )
    ConciliacaoDiaria.objects.create(data=date(2026, 11, 19), resultado="ok")
    resposta = painel.pagina()
    secao = _secoes(resposta)["Tarefas periódicas"]
    assert "Envio de notificações" in secao
    assert "Atrasada desde 20/11/2026 06:05" in secao
    assert "Última falha em 20/11/2026 09:00: RuntimeError" in secao
    assert "Sem registro de execução" in secao
    assert "Verificação operacional" in secao
    assert "Última conciliação: 19/11/2026 (Sem divergência)" in secao
    assert (
        _html_da_secao(resposta, "Tarefas periódicas").count("<li")
        + _html_da_secao(resposta, "Tarefas periódicas").count("<tr")
        >= 11
    )


def test_sem_conciliacao(painel: Painel) -> None:  # A-20
    assert "Nenhuma conciliação registrada." in _secoes(painel.pagina())["Tarefas periódicas"]


def test_a_navegacao_continua(painel: Painel) -> None:  # A-21
    from tests.fabricas import EnvioFactory

    EnvioFactory.create(situacao="falhou", concluido_em=T0)
    resposta = painel.pagina()
    texto = _texto(resposta)
    assert f"Olá, {painel.admin.nome}." in texto
    for rotulo in (
        "Envios",
        "Financeiro",
        "Fornecedores",
        "Usuários",
        "Convites",
        "Comunicados",
        "Endereço de retirada",
    ):
        assert rotulo in texto
    assert "Envios com falha: 1" in texto
    assert "Sair" in texto
    html = resposta.content.decode()
    for nome in (
        "fornecedores_lista",
        "usuarios_administracao",
        "convites_administracao",
        "comunicados_administracao",
        "retirada_endereco",
    ):
        assert f'href="{reverse(nome)}"' in html


def test_so_o_administrador_acessa(painel: Painel, sim: Any) -> None:  # A-22
    a, _x, _y, _pf = _ae(painel.relogio, sim)
    for conta in (a.a, ContaFactory.create(fornecedor=True)):
        cliente = Client()
        cliente.force_login(conta)
        assert cliente.get(URL).status_code == 403
    anonimo = Client().get(URL)
    assert anonimo.status_code == 302
    assert "/entrar/" in anonimo["Location"]


def test_nada_de_comprador_no_painel(painel: Painel, sim: Any) -> None:  # A-23
    a, x, _y, _pf = _ae(painel.relogio, sim, liberacao_horas=0)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    _ap_i()
    html = painel.pagina().content.decode()
    for conta in (a.a, a.b):
        assert conta.nome not in html
        assert conta.email_normalizado not in html
    assert "Comprador Secreto" not in html


def _tabelas() -> tuple[int, ...]:
    from apps.financeiro.models import (
        AlertaFinanceiro,
        MovimentoFinanceiro,
        ObrigacaoComComprador,
        Reembolso,
    )
    from apps.nucleo.auditoria import EntradaAuditoria
    from apps.pedidos.models import Pedido
    from apps.rodadas.models import Rodada

    return tuple(
        m.objects.count()
        for m in (
            AlertaFinanceiro,
            MovimentoFinanceiro,
            ObrigacaoComComprador,
            Reembolso,
            EntradaAuditoria,
            Pedido,
            Rodada,
        )
    )


def test_o_painel_nao_escreve(painel: Painel, sim: Any) -> None:  # A-24
    a, _x, _y = _liberada(painel, sim)
    _ap_i("100.00")
    antes = _tabelas()
    for instante in (L, L + timedelta(days=8)):
        assert painel.pagina(instante).status_code == 200
    assert _tabelas() == antes
    assert a.rodada.pk


def test_cinco_rodadas_em_etapas_diferentes(painel: Painel, sim: Any) -> None:  # A-25
    from apps.rodadas.models import Etapa
    from tests.apoio.ciclos import dar_prazo_de_teste
    from tests.fabricas import FornecedorFactory, RodadaFactory

    a, _x, _y = _liberada(painel, sim)
    from apps.fornecedores.models import Fornecedor

    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(nome="F5")
    nomes = {
        Etapa.INTERESSE: "F1",
        Etapa.FECHAMENTO: "F2",
        Etapa.PAGAMENTO: "F3",
        Etapa.AGUARDANDO_FORNECEDOR: "F4",
    }
    for etapa, nome in nomes.items():
        rodada = RodadaFactory.create(fornecedor=FornecedorFactory.create(nome=nome), etapa=etapa)
        if etapa == Etapa.FECHAMENTO:
            dar_prazo_de_teste(rodada, L + 10 * H)
    resposta = painel.pagina(L + H)
    assert resposta.status_code == 200
    rodadas = _secoes(resposta)["Rodadas"]
    posicoes = [rodadas.index(n) for n in ("F1", "F2", "F3", "F4", "F5")]
    assert posicoes == sorted(posicoes)
