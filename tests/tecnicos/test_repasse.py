"""E13-06: o repasse ao fornecedor e o pagamento do frete (acceptance A-1 a A-17)."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.financeiro.liquidez import LiquidezInsuficiente, SaidaRepetida, liquidez
from apps.financeiro.livro import conta, saldo
from apps.financeiro.models import ContaFinanceira, Destinacao, MovimentoFinanceiro
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from tests.apoio.pedido_formal import arranjo_af
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _af(relogio: RelogioControlado, sim: Any, **opcoes: Any) -> tuple[Any, Any, Any, Any]:
    """AF com a liberação do Pix em 72h; X pago em `T0 + 2h` e Y em `T0 + 20h`. O relógio fica
    em `T0 + 80h`: X liberado, Y a liberar."""
    af = arranjo_af(relogio, sim, liberacao_horas=72, pago_y_em=T0 + 20 * H, **opcoes)
    relogio.congelar(T0 + 80 * H)
    return af


def _obrigacao(a: Any) -> ContaFinanceira:
    return conta(Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk)


def _frete(a: Any) -> ContaFinanceira:
    return conta(Destinacao.FRETE, rodada=a.rodada.pk)


def _repasse(a: Any, valor: str, identificacao: str = "pix-001", **opcoes: Any) -> Any:
    from apps.pedidos.repasse import registrar_repasse

    return registrar_repasse(
        opcoes.pop("autor", a.admin),
        a.rodada,
        valor=D(valor),
        identificacao=identificacao,
        justificativa=opcoes.pop("justificativa", "Pix ao fornecedor"),
    )


def _frete_pago(a: Any, valor: str, identificacao: str = "frete-001") -> Any:
    from apps.pedidos.repasse import registrar_pagamento_do_frete

    return registrar_pagamento_do_frete(
        a.admin, a.rodada, valor=D(valor), identificacao=identificacao, justificativa="Frete"
    )


def _saldos(excecao: ContaFinanceira | None = None) -> dict[int, Decimal]:
    return {
        c.pk: saldo(c)
        for c in ContaFinanceira.objects.order_by("pk")
        if excecao is None or c.pk != excecao.pk
    }


def _foto() -> Any:
    return (MovimentoFinanceiro.objects.count(), EntradaAuditoria.objects.count())


def test_o_repasse_so_baixa_a_obrigacao_com_o_fornecedor(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, _x, _y, _pedido = _af(relogio, sim)
    obrigacao = _obrigacao(a)
    assert (saldo(obrigacao), liquidez(obrigacao).liberado) == (D("170.00"), D("80.00"))
    outros = _saldos(obrigacao)
    movimento = _repasse(a, "80.00")
    assert movimento.tipo == "repasse"
    assert saldo(obrigacao) == D("90.00")
    assert _saldos(obrigacao) == outros
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.repasse")
    dados = auditoria.alteracoes
    assert auditoria.autor_id == str(a.admin.pk)
    assert (dados["rodada"], dados["fornecedor"]) == (a.rodada.pk, a.fornecedor.pk)
    assert (dados["valor"], dados["identificacao"]) == ("80.00", "pix-001")
    assert (dados["liberado"], dados["a_liberar"]) == ("80.00", "90.00")


def test_o_repasse_nao_passa_do_liberado(relogio: RelogioControlado, sim: Any) -> None:  # A-2
    a, _x, _y, _pedido = _af(relogio, sim)
    antes = _foto()
    with pytest.raises(LiquidezInsuficiente) as erro:
        _repasse(a, "80.01")
    assert "R$ 80,00" in str(erro.value)
    assert "R$ 90,00" in str(erro.value)
    assert _foto() == antes


def test_tudo_liberado_pode_ser_repassado(relogio: RelogioControlado, sim: Any) -> None:  # A-3
    a, _x, _y, _pedido = _af(relogio, sim)
    relogio.congelar(T0 + 92 * H)
    _repasse(a, "170.00")
    assert saldo(_obrigacao(a)) == D("0.00")


def test_o_liberado_de_outro_fornecedor_nao_paga_este(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from tests.apoio.financeiro import pedido_pago_e_apurado

    a, _x, _y, _pedido = _af(relogio, sim)
    g = pedido_pago_e_apurado(
        sim,
        relogio,
        nome="G",
        t0=T0 - 120 * H,
        produtos="500.00",
        servico="5.00",
        aprovado_em=T0 - 110 * H,
    )
    relogio.congelar(T0 + 80 * H)
    obrigacao_g = conta(
        Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=g.fornecedor.pk, rodada=g.rodada.pk
    )
    assert liquidez(obrigacao_g).liberado == D("500.00")
    antes_de_g = (saldo(obrigacao_g), liquidez(obrigacao_g))
    with pytest.raises(LiquidezInsuficiente):
        _repasse(a, "80.01")
    assert (saldo(obrigacao_g), liquidez(obrigacao_g)) == antes_de_g


def test_consulta_que_falha_bloqueia_o_repasse(relogio: RelogioControlado, sim: Any) -> None:  # A-5
    a, _x, _y, _pedido = _af(relogio, sim)
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    antes = _foto()
    with pytest.raises(ConsultaAoProvedorFalhou):
        _repasse(a, "10.00")
    assert _foto() == antes


def test_a_consulta_vem_antes_do_movimento(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-6
    from apps.pedidos import repasse as modulo

    a, x, y, _pedido = _af(relogio, sim)
    eventos: list[str] = []
    consultar = modulo.consultar_antes_de_decidir
    registrar = modulo.registrar_saida

    def espiar_consulta(referencia: str) -> Any:
        eventos.append(f"consulta:{referencia}")
        return consultar(referencia)

    def espiar_saida(*args: Any, **kwargs: Any) -> Any:
        eventos.append("saida")
        return registrar(*args, **kwargs)

    monkeypatch.setattr(modulo, "consultar_antes_de_decidir", espiar_consulta)
    monkeypatch.setattr(modulo, "registrar_saida", espiar_saida)
    _repasse(a, "10.00")
    assert eventos == [
        f"consulta:{x.referencia_externa}",
        f"consulta:{y.referencia_externa}",
        "saida",
    ]


def test_sem_apuracao_no_livro_nao_ha_o_que_repassar(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-7
    from apps.pedidos import repasse as modulo
    from tests.apoio.apuracao import arranjo_ap

    a, _x, _y = arranjo_ap(relogio)
    consultas: list[str] = []
    monkeypatch.setattr(modulo, "consultar_antes_de_decidir", consultas.append)
    with pytest.raises(modulo.RepasseRecusado) as repasse:
        _repasse(a, "10.00")
    assert repasse.value.codigo == "sem_obrigacao"
    assert str(repasse.value) == "A rodada não tem valores devidos ao fornecedor."
    with pytest.raises(modulo.RepasseRecusado) as frete:
        _frete_pago(a, "1.00")
    assert frete.value.codigo == "sem_obrigacao"
    assert str(frete.value) == "A rodada não tem frete apurado."
    assert not consultas
    assert not MovimentoFinanceiro.objects.filter(tipo__in=["repasse", "pagamento_do_frete"])


def test_a_mesma_identificacao_nao_entra_duas_vezes(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    a, _x, _y, _pedido = _af(relogio, sim)
    _repasse(a, "10.00")
    antes = _foto()
    with pytest.raises(SaidaRepetida):
        _repasse(a, "1.00")
    assert _foto() == antes


def test_so_o_administrador_repassa_fora_de_transacao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    from tests.fabricas import ContaFactory

    a, _x, _y, _pedido = _af(relogio, sim)
    fornecedor = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    antes = _foto()
    for autor in (a.a, fornecedor, None):
        with pytest.raises(PermissionDenied):
            _repasse(a, "10.00", autor=autor)
    with pytest.raises(RuntimeError), transaction.atomic():
        _repasse(a, "10.00")
    assert _foto() == antes


def test_rodada_cancelada_sem_reembolso_ainda_registra_o_repasse(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, _x, _y, _pedido = _af(relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    _repasse(a, "80.00")
    assert saldo(_obrigacao(a)) == D("90.00")


def test_rodada_cancelada_com_reembolso_consumiu_a_obrigacao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-11
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, _x, _y, _pedido = _af(relogio, sim)
    relogio.congelar(T0 + 92 * H)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=True)
    with pytest.raises(LiquidezInsuficiente):
        _repasse(a, "0.01")


def test_o_frete_so_sai_ate_o_liberado(relogio: RelogioControlado, sim: Any) -> None:  # A-12
    a, _x, _y, _pedido = _af(relogio, sim)
    antes = _foto()
    with pytest.raises(LiquidezInsuficiente) as erro:
        _frete_pago(a, "22.00")
    assert "R$ 10,35" in str(erro.value)
    assert "R$ 11,65" in str(erro.value)
    assert _foto() == antes


def test_pagamento_do_frete_do_liberado(relogio: RelogioControlado, sim: Any) -> None:  # A-13
    a, _x, _y, _pedido = _af(relogio, sim)
    frete = _frete(a)
    outros = _saldos(frete)
    movimento = _frete_pago(a, "10.35")
    assert movimento.tipo == "pagamento_do_frete"
    assert saldo(frete) == D("11.65")
    assert _saldos(frete) == outros
    assert EntradaAuditoria.objects.filter(acao="rodada.pagamento_do_frete").count() == 1


def _cobrir_o_deficit_com_a_reserva(a: Any) -> None:
    from apps.financeiro.apuracao import cobrir_despesa
    from apps.financeiro.models import Despesa
    from apps.financeiro.reserva import registrar_aporte

    registrar_aporte(a.admin, D("1000.00"), "aporte-1", "Reserva")
    deficit = Despesa.objects.get(tipo="deficit_frete", rodada=a.rodada)
    cobrir_despesa(a.admin, deficit, fonte="reserva", valor=deficit.valor, justificativa="r")


def test_a_cobertura_da_reserva_conta_como_liberada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-14
    a, _x, _y, _pedido = _af(relogio, sim, pagar_y=False)
    frete = _frete(a)
    assert liquidez(frete).liberado == D("7.76")
    _cobrir_o_deficit_com_a_reserva(a)
    assert liquidez(frete).liberado == D("22.00")
    _frete_pago(a, "22.00")
    assert saldo(frete) == D("0.00")


def test_a_cobertura_da_receita_de_outra_rodada_conta_como_liberada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-15
    from apps.financeiro.apuracao import cobrir_despesa
    from apps.financeiro.models import Despesa
    from tests.apoio.financeiro import pedido_pago_e_apurado

    a, _x, _y, _pedido = _af(relogio, sim, pagar_y=False)
    g = pedido_pago_e_apurado(
        sim,
        relogio,
        nome="G",
        t0=T0 - 120 * H,
        produtos="500.00",
        servico="20.00",
        aprovado_em=T0 - 110 * H,
    )
    relogio.congelar(T0 + 80 * H)
    deficit = Despesa.objects.get(tipo="deficit_frete", rodada=a.rodada)
    cobrir_despesa(
        a.admin, deficit, fonte=("receita", g.rodada), valor=deficit.valor, justificativa="r"
    )
    assert liquidez(_frete(a)).liberado == D("22.00")


def test_a_devolucao_do_frete_reduz_o_liberado(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    from apps.financeiro.obrigacoes import registrar_obrigacao_com_comprador

    a, x, _y, _pedido = _af(relogio, sim)
    registrar_obrigacao_com_comprador(
        origem=x,
        rodada=a.rodada,
        ciclo=a.ciclo,
        comprador=a.a,
        pedido=x,
        motivo="devolucao_de_teste",
        produtos=D("0.00"),
        servico=D("0.00"),
        frete=D("2.00"),
    )
    assert liquidez(_frete(a)).liberado == D("8.35")


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_dois_repasses_que_juntos_passam_do_liberado(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-17
    from tests.apoio.concorrencia import executar_em_paralelo

    a, _x, _y, _pedido = _af(relogio, simulador_pagamentos)

    def repassar(identificacao: str) -> Any:
        def operacao(barreira: Any) -> Any:
            barreira.wait(timeout=10)
            return _repasse(a, "50.00", identificacao)

        return operacao

    resultados = executar_em_paralelo(repassar("pix-a"), repassar("pix-b"), tempo_limite=60)
    erros = [r.excecao for r in resultados if r.excecao is not None]
    assert len(erros) == 1
    assert isinstance(erros[0], LiquidezInsuficiente)
    assert saldo(_obrigacao(a)) == D("120.00")
    assert liquidez(_obrigacao(a)).liberado == D("30.00")
