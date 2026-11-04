"""E13-08: pedido formal, repasse e fornecedor de ponta a ponta com o simulador (A-1 a A-8)."""

import copy
import re
import uuid
from datetime import timedelta
from decimal import Decimal
from threading import Event
from typing import Any

import pytest
from django.core import mail
from django.db import transaction
from django.test import Client

from apps.financeiro.livro import conta, saldo
from apps.financeiro.models import (
    AlertaFinanceiro,
    ContaFinanceira,
    Destinacao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
)
from apps.fornecedores.models import Fornecedor
from apps.notificacoes.models import Notificacao
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.provedor import NovaCobranca, obter_provedor
from apps.pedidos.models import (
    DestinoDoPagamento,
    LinhaDoPedidoFormal,
    PedidoFormal,
    TentativaDeEnvioDoPedidoFormal,
)
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.pedido_formal import EMAIL_DO_PEDIDO, FALHA, LOCMEM, PRAZO, M, processar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)
COM_FALHAS = "tests.apoio.email_falho.BackendComFalhas"


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _processar_tudo() -> None:
    while processar_chamadas():
        pass


def _invariante_ok() -> None:
    from apps.financeiro.invariante import verificar_invariante_agora

    verificar_invariante_agora()
    assert not AlertaFinanceiro.objects.filter(
        tipo="invariante_violado", resolvido_em__isnull=True
    ).exists()


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _af_pela_tela(
    client: Client,
    relogio: RelogioControlado,
    sim: Any,
    *,
    liberacao_horas: int | None = None,
    com_segunda_cobranca: bool = False,
) -> tuple[Any, Any, Any, Any, bytes, str | None]:
    """O AF com a apuração e a aprovação feitas pela tela da E11-07. O relógio fica em `T0 + 48h`.
    Devolve o arranjo, X, Y, o pedido formal, a credencial do administrador e, se pedida, a
    segunda cobrança pendente de X."""
    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    if liberacao_horas is not None:
        sim.definir_liberacao("pix", horas=liberacao_horas)
    a, x, y = arranjo_ap(relogio)
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(email_pedido=EMAIL_DO_PEDIDO)
    pagar(relogio, sim, x)
    extra = None
    if com_segunda_cobranca:
        extra = (
            obter_provedor()
            .criar_cobranca(
                NovaCobranca("extra-e13", x.referencia_externa, x.total, "Pedido", T0 + 24 * H)
            )
            .pagamento.id_externo
        )
    pagar(relogio, sim, y, quando=T0 + 20 * H)
    relogio.congelar(PRAZO)
    entrar_de_novo(client, credencial, a.admin)
    base = f"/administracao/rodadas/{a.rodada.pk}/apuracao"
    assert client.post(f"{base}/iniciar/").status_code == 302
    assert client.post(f"{base}/aprovar/").status_code == 302
    return a, x, y, PedidoFormal.objects.get(rodada=a.rodada), credencial, extra


def _pagina(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/pedido-formal/"


def _token(client: Client, a: Any) -> str:
    achado = re.search(r'name="token" value="([^"]+)"', client.get(_pagina(a)).content.decode())
    assert achado
    return achado.group(1)


def _reenviar(client: Client, a: Any, token: str | None = None, **opcoes: Any) -> Any:
    return client.post(
        f"/administracao/rodadas/{a.rodada.pk}/pedido-formal/reenviar/",
        {"token": token or _token(client, a)},
        **opcoes,
    )


def _snapshot(pedido: Any) -> Any:
    return (
        list(PedidoFormal.objects.filter(pk=pedido.pk).values()),
        list(LinhaDoPedidoFormal.objects.filter(pedido_formal=pedido).order_by("pk").values()),
    )


def _emails_iguais_ao_snapshot(pedido: Any) -> list[Any]:
    enviados = [m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]
    for enviado in enviados:
        assert (enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)
    assert PedidoFormal.objects.filter(ciclo=pedido.ciclo).count() == 1
    return enviados


def _o_fornecedor_ve_so_o_permitido(a: Any, x: Any) -> None:
    """E13-07 A-12 e A-13, no estado corrente: o portal e as recusas."""
    fornecedor = Client()
    fornecedor.force_login(ContaFactory.create(papel="fornecedor", fornecedor_id=a.fornecedor.pk))
    respostas = [
        fornecedor.get("/fornecedor/"),
        fornecedor.get(f"/fornecedor/rodadas/{a.rodada.pk}/"),
    ]
    csv = fornecedor.get(f"/fornecedor/rodadas/{a.rodada.pk}/pedido-formal.csv")
    assert [r.status_code for r in respostas] == [200, 200]
    assert csv.status_code in (200, 404)
    for resposta in (*respostas, csv):
        corpo = resposta.content.decode()
        for proibido in (a.a.nome, a.b.nome, "R$ 8,50", "R$ 22,00", f"/pedidos/{x.pk}/", "Repasse"):
            assert proibido not in corpo, proibido
    proibidas = [
        fornecedor.get(f"/pedidos/{x.pk}/"),
        fornecedor.post(f"/pedidos/{x.pk}/pagar/"),
        fornecedor.get("/administracao/financeiro/"),
        fornecedor.get("/administracao/financeiro/reserva/"),
        fornecedor.get(f"/administracao/rodadas/{a.rodada.pk}/saidas/"),
        fornecedor.get("/carrinho/"),
        fornecedor.get("/catalogo/"),
    ]
    assert [r.status_code for r in proibidas] == [403] * 7


def test_do_resultado_aprovado_ao_pedido_aceito(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-1
    from tests.apoio.email_falho import BackendComFalhas

    a, x, _y, pedido, _credencial, _extra = _af_pela_tela(client, relogio, sim)
    settings.EMAIL_BACKEND = COM_FALHAS
    BackendComFalhas.configurar(falhas=1)
    mail.outbox.clear()
    assert processar(relogio, PRAZO) == 1
    assert processar(relogio, PRAZO + 5 * M) == 1
    tentativas = TentativaDeEnvioDoPedidoFormal.objects.order_by("numero")
    assert [(t.ordem_automatica, t.resultado) for t in tentativas] == [(1, "falha"), (2, "sucesso")]
    assert len(_emails_iguais_ao_snapshot(pedido)) == 1
    assert not Notificacao.objects.filter(evento="falha_no_pedido_formal").exists()
    fornecedor = Client()
    fornecedor.force_login(ContaFactory.create(papel="fornecedor", fornecedor_id=a.fornecedor.pk))
    texto = _texto(fornecedor.get(f"/fornecedor/rodadas/{a.rodada.pk}/"))
    assert "Total dos produtos: R$ 170,00" in texto
    assert "Previsão de entrega: 11/11/2026" in texto
    _o_fornecedor_ve_so_o_permitido(a, x)  # A-8
    _invariante_ok()


def test_tres_falhas_e_reenvio_pela_tela(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-2
    a, _x, _y, pedido, credencial, _extra = _af_pela_tela(client, relogio, sim)
    antes = _snapshot(pedido)
    settings.EMAIL_BACKEND = FALHA
    processar(relogio, PRAZO)
    entrar_de_novo(client, credencial, a.admin)
    durante = _reenviar(client, a, str(uuid.uuid4()))  # a página não traz o botão
    assert durante.status_code == 409
    processar(relogio, PRAZO + 5 * M)
    processar(relogio, PRAZO + 35 * M)
    entrar_de_novo(client, credencial, a.admin)
    aviso = Notificacao.objects.get(evento="falha_no_pedido_formal", conta=a.admin)
    assert aviso.link is not None
    pagina = client.get(aviso.link)
    assert pagina.status_code == 200
    primeira = _reenviar(client, a, follow=True)
    assert "Reenvio registrado: o serviço de e-mail recusou (ConnectionError)." in _texto(primeira)
    settings.EMAIL_BACKEND = LOCMEM
    segunda = _reenviar(client, a, follow=True)
    assert "Reenvio registrado: aceito pelo serviço de e-mail." in _texto(segunda)
    tipos = [t.tipo for t in TentativaDeEnvioDoPedidoFormal.objects.order_by("numero")]
    assert tipos == ["automatica"] * 3 + ["manual"] * 2
    from apps.pedidos.models import EnvioDoPedidoFormal

    envio = EnvioDoPedidoFormal.objects.get()
    assert envio.situacao == "concluido_com_falhas"
    assert processar(relogio, PRAZO + 24 * 60 * M) == 0
    assert _snapshot(pedido) == antes
    assert len(_emails_iguais_ao_snapshot(pedido)) == 1
    _invariante_ok()


def _cookies_do_administrador(client: Client) -> Any:
    return copy.deepcopy(client.cookies)


def _cliente(cookies: Any) -> Client:
    cliente = Client()
    cliente.cookies = copy.deepcopy(cookies)
    return cliente


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_mesmo_token_em_dois_post_envia_uma_vez(
    client: Client,
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-3 (cenários 70 e 95)
    from apps.pedidos import reenvio_do_pedido_formal as modulo
    from tests.apoio.concorrencia import executar_em_paralelo
    from tests.apoio.trava import esperar_outra_conexao_na_trava

    a, _x, _y, pedido, credencial, _extra = _af_pela_tela(client, relogio, simulador_pagamentos)
    processar(relogio, PRAZO)
    entrar_de_novo(client, credencial, a.admin)
    token = _token(client, a)
    cookies = _cookies_do_administrador(client)
    mail.outbox.clear()
    pausado = Event()
    enviar = modulo.enviar_email

    def pausar(*args: Any) -> None:
        pausado.set()
        esperar_outra_conexao_na_trava()
        enviar(*args)

    monkeypatch.setattr(modulo, "enviar_email", pausar)

    def primeira(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return _reenviar(_cliente(cookies), a, token)

    def segunda(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        return _reenviar(_cliente(cookies), a, token)

    resultados = executar_em_paralelo(primeira, segunda, tempo_limite=60)
    assert [r.excecao for r in resultados] == [None, None], [repr(r.excecao) for r in resultados]
    assert [r.valor.status_code for r in resultados] == [302, 302]
    assert len(_emails_iguais_ao_snapshot(pedido)) == 1
    assert TentativaDeEnvioDoPedidoFormal.objects.filter(tipo="manual").count() == 1
    _invariante_ok()


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_tokens_distintos_em_dois_post_se_executam_em_sequencia(
    client: Client,
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-3 (cenário 119)
    from apps.pedidos import reenvio_do_pedido_formal as modulo
    from tests.apoio.concorrencia import executar_em_paralelo
    from tests.apoio.trava import esperar_outra_conexao_na_trava

    a, _x, _y, pedido, credencial, _extra = _af_pela_tela(client, relogio, simulador_pagamentos)
    processar(relogio, PRAZO)
    entrar_de_novo(client, credencial, a.admin)
    tokens = [_token(client, a), _token(client, a)]
    cookies = _cookies_do_administrador(client)
    mail.outbox.clear()
    pausado = Event()
    chamadas: list[int] = []
    enviar = modulo.enviar_email

    def pausar(*args: Any) -> None:
        chamadas.append(1)
        if len(chamadas) == 1:
            pausado.set()
            esperar_outra_conexao_na_trava()
        enviar(*args)

    monkeypatch.setattr(modulo, "enviar_email", pausar)

    def primeira(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return _reenviar(_cliente(cookies), a, tokens[0])

    def segunda(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        return _reenviar(_cliente(cookies), a, tokens[1])

    resultados = executar_em_paralelo(primeira, segunda, tempo_limite=60)
    assert [r.excecao for r in resultados] == [None, None], [repr(r.excecao) for r in resultados]
    primeira_t, segunda_t = TentativaDeEnvioDoPedidoFormal.objects.filter(tipo="manual").order_by(
        "numero"
    )
    assert segunda_t.iniciada_em >= primeira_t.concluida_em
    assert len(_emails_iguais_ao_snapshot(pedido)) == 2
    _invariante_ok()


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_post_durante_a_tentativa_automatica_e_recusado_sem_esperar(
    client: Client,
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-3 (cenário 118)
    from apps.pedidos import envio_do_pedido_formal as envio
    from tests.apoio.concorrencia import executar_em_paralelo

    settings.EMAIL_BACKEND = FALHA
    a, _x, _y, pedido, credencial, _extra = _af_pela_tela(client, relogio, simulador_pagamentos)
    processar(relogio, PRAZO)
    processar(relogio, PRAZO + 5 * M)
    relogio.congelar(PRAZO + 35 * M)
    entrar_de_novo(client, credencial, a.admin)
    cookies = _cookies_do_administrador(client)
    pausado, liberar = Event(), Event()
    enviar = envio.enviar_email

    def pausar(*args: Any) -> None:
        pausado.set()
        assert liberar.wait(20)
        enviar(*args)

    monkeypatch.setattr(envio, "enviar_email", pausar)

    def automatica(barreira: Any) -> int:
        barreira.wait(timeout=10)
        return envio.processar_pedidos_formais()

    def post(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        try:
            return _reenviar(_cliente(cookies), a, "00000000-0000-4000-8000-000000000001")
        finally:
            liberar.set()

    resultados = executar_em_paralelo(automatica, post, tempo_limite=60)
    assert resultados[0].excecao is None, repr(resultados[0].excecao)
    assert resultados[1].excecao is None, repr(resultados[1].excecao)
    assert resultados[1].valor.status_code == 409
    assert [t.tipo for t in TentativaDeEnvioDoPedidoFormal.objects.order_by("numero")] == [
        "automatica"
    ] * 3
    assert PedidoFormal.objects.filter(pk=pedido.pk).count() == 1
    _invariante_ok()


def test_ajuste_da_previsao_pela_tela_e_reenvio_com_o_conteudo_original(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    a, x, y, pedido, credencial, _extra = _af_pela_tela(client, relogio, sim)
    processar(relogio, PRAZO)
    entrar_de_novo(client, credencial, a.admin)
    resposta = client.post(
        f"/administracao/rodadas/{a.rodada.pk}/previsao/", {"data": "2026-11-14"}, follow=True
    )
    assert "Previsão de entrega alterada para 14/11/2026." in _texto(resposta)
    avisos = Notificacao.objects.filter(evento="previsao_de_entrega_alterada")
    assert {n.conta_id for n in avisos} == {a.a.pk, a.b.pk}
    fornecedor = Client()
    fornecedor.force_login(ContaFactory.create(papel="fornecedor", fornecedor_id=a.fornecedor.pk))
    assert "Previsão de entrega: 14/11/2026" in _texto(
        fornecedor.get(f"/fornecedor/rodadas/{a.rodada.pk}/")
    )
    comprador = Client()
    comprador.force_login(a.a)
    assert "Previsão de entrega: 14/11/2026." in _texto(comprador.get(f"/pedidos/{x.pk}/"))
    assert y.pk
    mail.outbox.clear()
    assert _reenviar(client, a).status_code == 302
    (reenviado,) = _emails_iguais_ao_snapshot(pedido)
    assert "Previsão de entrega: 11/11/2026" in reenviado.body
    _invariante_ok()


def _repasse_pela_tela(client: Client, a: Any, valor: str, identificacao: str) -> Any:
    return client.post(
        f"/administracao/rodadas/{a.rodada.pk}/saidas/repasse/",
        {"valor": valor, "identificacao": identificacao, "justificativa": "Pix ao fornecedor"},
    )


def _repassar_tudo(
    client: Client, relogio: RelogioControlado, sim: Any, a: Any, credencial: bytes
) -> None:
    """O cenário 5: recusado antes da liberação, depois 80,00 e 90,00, cada saída também no
    simulador."""
    obrigacao = conta(
        Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk
    )
    relogio.congelar(T0 + 50 * H)
    entrar_de_novo(client, credencial, a.admin)
    recusado = _repasse_pela_tela(client, a, "10,00", "pix-cedo")
    assert recusado.status_code == 409
    assert "Só R$ 0,00 estão liberados no provedor" in _texto(recusado)
    outros = {c.pk: saldo(c) for c in ContaFinanceira.objects.exclude(pk=obrigacao.pk)}
    for horas, valor in ((80, "80,00"), (92, "90,00")):
        relogio.congelar(T0 + horas * H)
        entrar_de_novo(client, credencial, a.admin)
        id_saida = sim.registrar_saida(
            D(valor.replace(",", ".")), descricao="repasse", em=T0 + horas * H
        )
        assert _repasse_pela_tela(client, a, valor, id_saida).status_code == 302
    assert saldo(obrigacao) == D("0.00")
    assert {c.pk: saldo(c) for c in ContaFinanceira.objects.exclude(pk=obrigacao.pk)} == outros


def test_repasse_limitado_ao_liberado_e_conciliado(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    from apps.financeiro.conciliacao import conciliar_dias_pendentes_agora
    from apps.financeiro.models import ConciliacaoDiaria

    a, x, _y, _pedido, credencial, _extra = _af_pela_tela(client, relogio, sim, liberacao_horas=72)
    _repassar_tudo(client, relogio, sim, a, credencial)
    relogio.congelar(T0 + 92 * H + timedelta(days=2))
    conciliar_dias_pendentes_agora()
    assert not ConciliacaoDiaria.objects.filter(resultado="divergente").exists()
    assert MovimentoFinanceiro.objects.filter(tipo="repasse").count() == 2
    _o_fornecedor_ve_so_o_permitido(a, x)  # A-8
    _invariante_ok()


def _cancelar_depois_do_repasse(
    client: Client, relogio: RelogioControlado, sim: Any, **opcoes: Any
) -> tuple[Any, Any, Any, Any, bytes, str | None, Any]:
    """O cenário 6 até o cancelamento: AF com liberação em 72h, pedido formal aceito, repasse
    total e o cancelamento com reembolso pela tela. Devolve também a foto do repasse."""
    a, x, y, pedido, credencial, extra = _af_pela_tela(
        client, relogio, sim, liberacao_horas=72, **opcoes
    )
    processar(relogio, PRAZO)
    _repassar_tudo(client, relogio, sim, a, credencial)
    repasses = list(MovimentoFinanceiro.objects.filter(tipo="repasse").order_by("pk").values())
    relogio.congelar(T0 + 93 * H)
    entrar_de_novo(client, credencial, a.admin)
    resposta = client.post(f"/administracao/rodadas/{a.rodada.pk}/cancelar/", {"reembolso": "sim"})
    assert resposta.status_code == 302
    return a, x, y, pedido, credencial, extra, repasses


def _cobrir_a_falta_com_a_reserva(a: Any, sim: Any) -> list[Any]:
    from apps.financeiro.reserva import (
        designar_reserva,
        registrar_aporte,
        sem_cobertura_da_obrigacao,
    )

    id_deposito = sim.depositar(D("1000.00"))
    with transaction.atomic():
        registrar_aporte(a.admin, D("1000.00"), id_deposito, "Aporte")
    obrigacoes = list(
        ObrigacaoComComprador.objects.filter(motivo="cancelamento_da_rodada").order_by("pk")
    )
    for obrigacao in obrigacoes:
        falta = sem_cobertura_da_obrigacao(obrigacao)
        assert falta > 0  # a parte de produtos já foi repassada ao fornecedor
        with transaction.atomic():
            designar_reserva(a.admin, obrigacao, falta, "Cobrir a devolução do cancelamento")
        assert sem_cobertura_da_obrigacao(obrigacao) == 0
    return obrigacoes


def test_cancelamento_depois_do_repasse(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    from apps.pedidos.cancelamento_da_rodada import autorizar_devolucoes_do_cancelamento_agora

    a, x, y, pedido, credencial, _extra, repasses = _cancelar_depois_do_repasse(
        client, relogio, sim
    )
    tentativas = list(TentativaDeEnvioDoPedidoFormal.objects.order_by("pk").values())
    obrigacoes = _cobrir_a_falta_com_a_reserva(a, sim)
    assert {o.pedido_id for o in obrigacoes} == {x.pk, y.pk}
    autorizar_devolucoes_do_cancelamento_agora()
    _processar_tudo()
    for obrigacao in obrigacoes:
        assert ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "concluida"
    assert (
        list(MovimentoFinanceiro.objects.filter(tipo="repasse").order_by("pk").values()) == repasses
    )
    assert list(TentativaDeEnvioDoPedidoFormal.objects.order_by("pk").values()) == tentativas
    assert PedidoFormal.objects.get(pk=pedido.pk).corpo == pedido.corpo
    entrar_de_novo(client, credencial, a.admin)
    assert _reenviar(client, a, str(uuid.uuid4())).status_code == 409  # rodada_cancelada
    _o_fornecedor_ve_so_o_permitido(a, x)  # A-8
    _invariante_ok()


def test_pagamento_depois_do_cancelamento_com_repasse_feito(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    a, x, _y, _pedido, _credencial, extra, repasses = _cancelar_depois_do_repasse(
        client, relogio, sim, com_segunda_cobranca=True
    )
    assert extra is not None
    obrigacao_f = conta(
        Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk
    )
    antes = saldo(obrigacao_f)
    sim.aprovar(extra, em=T0 + 47 * H)
    sim.entregar_avisos()
    _processar_tudo()
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=extra)
    assert destino.destino == "devolucao"
    integral = ObrigacaoComComprador.objects.get(pedido=x, origem_id=str(destino.pk))
    assert integral.integral == x.total
    assert AlertaFinanceiro.objects.filter(
        tipo="pagamento_depois_do_cancelamento", gravidade="critico"
    ).exists()
    assert saldo(obrigacao_f) == antes
    assert (
        list(MovimentoFinanceiro.objects.filter(tipo="repasse").order_by("pk").values()) == repasses
    )
    _invariante_ok()
