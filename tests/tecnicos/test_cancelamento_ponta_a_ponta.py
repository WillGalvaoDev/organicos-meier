"""E12-07: o cancelamento da rodada de ponta a ponta com o simulador (acceptance A-1 a A-8)."""

import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.test import Client

from apps.financeiro.models import (
    AlertaFinanceiro,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
    Reembolso,
)
from apps.notificacoes.models import Notificacao
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.provedor import obter_provedor
from apps.pedidos.models import DestinoDoPagamento, SituacaoDoPedido
from apps.rodadas.models import Rodada
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import H, arranjo_ap, cobranca, pagar
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H
MOTIVO = "cancelamento_da_rodada"
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _rota(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/cancelar/"


def _processar_tudo() -> None:
    while processar_chamadas():
        pass


def _invariante_ok() -> None:
    from apps.financeiro.invariante import verificar_invariante_agora

    verificar_invariante_agora()
    assert not AlertaFinanceiro.objects.filter(
        tipo="invariante_violado", resolvido_em__isnull=True
    ).exists()


def _no_simulador(id_externo: str) -> str:
    return str(obter_provedor().consultar_pagamento(id_externo).situacao)


def _estornado_de(id_externo: str) -> Decimal:
    """A soma dos estornos concluídos no simulador para a cobrança."""
    estornos = EstornoSimulado.objects.filter(situacao="concluido").select_related("cobranca")
    return sum((e.valor for e in estornos if e.cobranca.id_externo == id_externo), D("0.00"))


def _tela(
    client: Client, relogio: RelogioControlado, **arranjo: Any
) -> tuple[Any, Any, Any, bytes]:
    relogio.congelar(T0)
    conta, credencial = administrador_com_passkey(client)
    a, x, y = arranjo_ap(relogio, **arranjo)
    assert a.admin.pk == conta.pk
    return a, x, y, credencial


def _cancelar_pela_tela(
    client: Client, a: Any, credencial: bytes, reembolso: str, **extra: str
) -> Any:
    entrar_de_novo(client, credencial, a.admin)
    return client.post(_rota(a), {"reembolso": reembolso, **extra})


def _autorizar_pela_tela(client: Client, a: Any, credencial: bytes, obrigacao: Any) -> Any:
    entrar_de_novo(client, credencial, a.admin)
    return client.post(f"/administracao/financeiro/devolucoes/{obrigacao.pk}/autorizar/")


def _x_pago_y_pendente(
    client: Client, relogio: RelogioControlado, sim: Any
) -> tuple[Any, Any, Any, str, str, bytes]:
    a, x, y, credencial = _tela(client, relogio)
    id_x = pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(T0 + 30 * H)
    return a, x, y, id_x, id_y, credencial


def test_cancelamento_com_reembolso_durante_a_margem(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    from apps.financeiro.livro import conta_da_obrigacao
    from apps.financeiro.obrigacoes import _liquidado

    a, x, _y, id_x, id_y, credencial = _x_pago_y_pendente(client, relogio, sim)
    resposta = _cancelar_pela_tela(client, a, credencial, "sim")
    assert resposta.status_code == 302
    _processar_tudo()
    assert _no_simulador(id_y) == "cancelado"
    assert _estornado_de(id_x) == D("94.35")
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    assert ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "concluida"
    assert obrigacao.devido - _liquidado(conta_da_obrigacao(obrigacao)) == D("0.00")
    assert Notificacao.objects.filter(conta=a.a, evento="estorno").exists()
    _invariante_ok()


def test_pagamento_aprovado_junto_do_cancelamento_gera_devolucao_e_alerta(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, _x, y, _id_x, id_y, credencial = _x_pago_y_pendente(client, relogio, sim)
    _cancelar_pela_tela(client, a, credencial, "sim")
    sim.aprovar(id_y, em=T0 + 30 * H)
    sim.entregar_avisos()
    _processar_tudo()
    situacao = SituacaoDoPedido.objects.get(pedido=y)
    assert (situacao.situacao, situacao.motivo_do_cancelamento) == ("cancelado", MOTIVO)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_y)
    assert (destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")
    obrigacao = ObrigacaoComComprador.objects.get(pedido=y, origem_id=str(destino.pk))
    assert obrigacao.integral == D("106.15")
    assert AlertaFinanceiro.objects.filter(
        tipo="pagamento_depois_do_cancelamento", gravidade="critico", chave=id_y
    ).exists()
    assert _autorizar_pela_tela(client, a, credencial, obrigacao).status_code == 302
    _processar_tudo()
    assert _estornado_de(id_y) == D("106.15")
    _invariante_ok()


def test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, y, credencial = _tela(client, relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    sim.aprovar(id_y, em=PRAZO + timedelta(milliseconds=1))
    sim.entregar_avisos()
    _processar_tudo()
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_y)
    existente = ObrigacaoComComprador.objects.get(pedido=y, origem_id=str(destino.pk))
    antes = list(ObrigacaoComComprador.objects.order_by("pk").values())
    _cancelar_pela_tela(client, a, credencial, "nao")
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"
    assert list(ObrigacaoComComprador.objects.order_by("pk").values()) == antes
    assert not ParcelaDeDevolucao.objects.filter(obrigacao=existente).exists()
    # o dinheiro aprovado depois da margem só fica liberado para estorno dias depois (saldo do
    # provedor), então a autorização vem depois disso
    relogio.congelar(PRAZO + timedelta(days=3))
    _autorizar_pela_tela(client, a, credencial, existente)
    _processar_tudo()
    assert _estornado_de(id_y) == existente.integral
    _invariante_ok()


def test_cancelamento_depois_da_aprovacao_do_resultado(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.financeiro.conciliacao import conciliar_dias_pendentes_agora
    from apps.financeiro.livro import saldo
    from apps.financeiro.models import ConciliacaoDiaria
    from apps.financeiro.reserva import (
        designar_reserva,
        registrar_aporte,
        sem_cobertura_da_obrigacao,
    )
    from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao
    from apps.pedidos.cancelamento_da_rodada import autorizar_devolucoes_do_cancelamento_agora
    from apps.pedidos.models import AprovacaoDoResultado
    from tests.apoio.financeiro import chave_nova, despesas, mover, receita_de

    a, x, _y, credencial = _tela(client, relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    aprovar_resultado(a.admin, a.rodada)
    id_deposito = sim.depositar(D("1000.00"))
    with transaction.atomic():
        registrar_aporte(a.admin, D("1000.00"), id_deposito, "Aporte")
    with transaction.atomic():
        mover(
            "cobertura_de_despesa",
            receita_de(a.rodada),
            despesas(),
            saldo(receita_de(a.rodada)),
            chave=chave_nova(),
        )
    aprovacoes = list(AprovacaoDoResultado.objects.values())
    _cancelar_pela_tela(client, a, credencial, "sim")
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    falta = sem_cobertura_da_obrigacao(obrigacao)
    assert falta > 0
    with transaction.atomic():
        designar_reserva(a.admin, obrigacao, falta, "Cobrir a devolução do cancelamento")
    autorizar_devolucoes_do_cancelamento_agora()
    _processar_tudo()
    assert ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "concluida"
    relogio.congelar(PRAZO + timedelta(days=2))
    conciliar_dias_pendentes_agora()
    assert not ConciliacaoDiaria.objects.filter(resultado="divergente").exists()
    assert list(AprovacaoDoResultado.objects.values()) == aprovacoes
    _invariante_ok()


def test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    from apps.financeiro.devolucoes import autorizar_devolucao
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from tests.apoio.devolucoes import K, itens_do_pedido, parcial
    from tests.apoio.financeiro import pedido_composto
    from tests.apoio.pedidos import administrador, sincronizar, tentativa_criada

    relogio.congelar(T0 + H)
    pedido = pedido_composto(ContaFactory.create(), "7.99", "0.40", "1.60")
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    sim.aprovar(id_externo)
    sincronizar(id_externo)
    (item,) = itens_do_pedido(pedido, K[3])
    registrado = parcial(item, "0.25")
    autorizar_devolucao(registrado.obrigacao, autor=administrador())
    _processar_tudo()
    assert _estornado_de(id_externo) == D(
        "2.50"
    )  # 2,00 de produtos, 0,10 de serviço, 0,40 de frete
    relogio.congelar(T0 + 2 * H)
    cancelar_rodada(administrador(), pedido.abertura.rodada, com_reembolso=True)
    _processar_tudo()
    do_cancelamento = Reembolso.objects.get(pedido=pedido, motivo=MOTIVO)
    assert do_cancelamento.produtos == D("5.99")
    assert _estornado_de(id_externo) == pedido.total == D("9.99")
    _invariante_ok()


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_dois_cancelamentos_em_paralelo_geram_um_estorno_por_pagamento(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-6
    from apps.pedidos import cancelamento_da_rodada as modulo
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado, cancelar_rodada
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    id_x = pagar(relogio, simulador_pagamentos, x)
    id_y = pagar(relogio, simulador_pagamentos, y)

    def cancelar() -> Any:
        return cancelar_rodada(a.admin, a.rodada, com_reembolso=True)

    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "_reembolsar_os_pedidos_pagos")
    ra, rb = corrida.rodar(cancelar, cancelar, a_atomica=False, b_atomica=False)
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, CancelamentoRecusado), rb.excecao
    assert rb.excecao.codigo == "ja_cancelada"
    _processar_tudo()
    assert EstornoSimulado.objects.filter(situacao="concluido").count() == 2
    assert _estornado_de(id_x) == D("94.35")
    assert _estornado_de(id_y) == D("106.15")
    _invariante_ok()  # A-10


def test_a_rota_pelo_cliente_http(client: Client, relogio: RelogioControlado) -> None:  # A-7
    a, _x, _y, credencial = _tela(client, relogio)
    assert _cancelar_pela_tela(client, a, credencial, "sim", compradores="1").status_code == 400
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "pagamento"
    for conta in (a.a, ContaFactory.create(fornecedor=True)):
        cliente = Client()
        cliente.force_login(conta)
        assert cliente.post(_rota(a), {"reembolso": "nao"}).status_code in (302, 403)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "pagamento"
    assert _cancelar_pela_tela(client, a, credencial, "nao").status_code == 302
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"
    _invariante_ok()  # A-10


def test_nova_rodada_depois_do_cancelamento(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    from apps.rodadas.estoque import incluir_produto_na_rodada
    from apps.rodadas.servicos import abrir_rodada

    a, _x, _y, _id_x, _id_y, credencial = _x_pago_y_pendente(client, relogio, sim)
    _cancelar_pela_tela(client, a, credencial, "sim")
    _processar_tudo()

    def foto() -> tuple[Any, ...]:
        return (
            Rodada.objects.get(pk=a.rodada.pk).etapa,
            [
                (s.pedido_id, s.situacao, s.motivo_do_cancelamento)
                for s in SituacaoDoPedido.objects.order_by("pk")
            ],
            list(
                Reembolso.objects.order_by("pk").values_list(
                    "chave", "produtos", "servico", "frete"
                )
            ),
            list(ParcelaDeDevolucao.objects.order_by("pk").values_list("obrigacao_id", "situacao")),
        )

    antes = foto()
    nova = abrir_rodada(a.admin, a.rodada.fornecedor)
    incluir_produto_na_rodada(a.admin, nova, a.p1, "20")
    assert nova.etapa == "interesse"
    assert foto() == antes
    _invariante_ok()  # A-10


def _retorno_cancelado_pela_tela(
    client: Client, relogio: RelogioControlado, sim: Any, reembolso: str
) -> tuple[Any, Any]:
    """AP-R pela tela: X pago, a apuração em 48h com o retorno ao interesse e o administrador
    cancelando; depois o processamento das chamadas."""
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, _y, credencial = _tela(client, relogio, minimo="100.00", limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    assert _cancelar_pela_tela(client, a, credencial, reembolso).status_code == 302
    _processar_tudo()
    return a, x


@pytest.mark.parametrize("reembolso", ["sim", "nao"])
def test_cancelamento_depois_de_um_retorno_ao_interesse(
    client: Client, relogio: RelogioControlado, sim: Any, reembolso: str
) -> None:  # A-9
    a, x = _retorno_cancelado_pela_tela(client, relogio, sim, reembolso)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"
    aviso = Notificacao.objects.get(conta=a.a, evento="rodada_cancelada")
    assert aviso.link == f"/pedidos/{x.pk}/"
    entrar = Client()
    entrar.force_login(a.a)
    pagina = " ".join(
        re.sub(r"<[^>]+>", " ", entrar.get(f"/pedidos/{x.pk}/").content.decode()).split()
    )
    assert "seus interesses continuam reservados na rodada" not in pagina
    assert "A rodada foi cancelada pelo administrador." in pagina
    if reembolso == "sim":
        assert "As devoluções já devidas do seu pedido continuam em andamento." in aviso.corpo
        assert "As devoluções já devidas deste pedido continuam em andamento." in pagina
    else:
        assert "O cancelamento não inicia novas devoluções." in aviso.corpo
        assert "O cancelamento não inicia novas devoluções." in pagina
    assert not Reembolso.objects.filter(pedido=x, motivo=MOTIVO).exists()
    assert ParcelaDeDevolucao.objects.filter(obrigacao__pedido=x).count() <= 1
    assert ObrigacaoComComprador.objects.filter(pedido=x).count() == 1
    _invariante_ok()
