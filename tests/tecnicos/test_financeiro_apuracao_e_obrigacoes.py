"""E09-06: apuração no livro, déficit de frete, obrigações com compradores e liquidação
(acceptance A-1 a A-16)."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied

from apps.financeiro.apuracao import (
    FreteDoCiclo,
    cobrir_despesa,
    frete_do_ciclo,
    registrar_apuracao_no_livro,
)
from apps.financeiro.entradas import registrar_tarifa
from apps.financeiro.liquidez import registrar_saida
from apps.financeiro.livro import (
    EXTERIOR,
    MovimentoConflitante,
    SaldoInsuficiente,
    saldo,
)
from apps.financeiro.models import (
    AlertaFinanceiro,
    ApuracaoNoLivro,
    Despesa,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeMovimento,
)
from apps.financeiro.obrigacoes import (
    LiquidacaoRecusada,
    cobrir_obrigacao_com_receita,
    liquidar_obrigacao,
    registrar_obrigacao_com_comprador,
)
from apps.financeiro.reserva import (
    CoberturaExcedente,
    designar_reserva,
    itens_sem_cobertura,
    situacao_da_reserva,
)
from apps.nucleo.auditoria import SISTEMA, EntradaAuditoria
from apps.pagamentos.models import PagamentoNoProvedor
from apps.pedidos.models import Pedido
from tests.apoio.financeiro import (
    Apuracao,
    custodia,
    frete_de,
    montar_ap,
    mover,
    obrigacao_de,
    pagar_pedido,
    receita_de,
    reserva,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
T = TipoDeMovimento


@dataclass
class Cenario:
    ap: Apuracao
    sim: Any
    relogio: RelogioControlado


@pytest.fixture
def cen(relogio: RelogioControlado, simulador_pagamentos: Any) -> Cenario:
    """O arranjo Ap: X quitado pela entrada da E09-04 (tarifa de 1,25), Y sem pagamento e a
    reserva com 1000,00 de aporte."""
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    ap = montar_ap()
    pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, H)
    mover(T.APORTE, EXTERIOR, reserva(), "1000.00", autor=ap.admin, justificativa="Aporte inicial")
    return Cenario(ap, simulador_pagamentos, relogio)


def _apurar(c: Cenario) -> ApuracaoNoLivro:
    return registrar_apuracao_no_livro(c.ap.ciclo, [c.ap.x], autor=SISTEMA)


def _custodias(c: Cenario, comprador: Any) -> list[Decimal]:
    return [
        saldo(custodia(c.ap.rodada, c.ap.ciclo, comprador, componente))
        for componente in ("produtos", "servico", "frete")
    ]


def _obrigacao(c: Cenario, **componentes: str) -> Any:
    valores = {"produtos": "25.00", "servico": "1.25", "frete": "5.00", **componentes}
    return registrar_obrigacao_com_comprador(
        origem=c.ap.x,
        rodada=c.ap.rodada,
        ciclo=c.ap.ciclo,
        comprador=c.ap.b,
        pedido=c.ap.x,
        motivo="devolucao_de_teste",
        produtos=D(valores["produtos"]),
        servico=D(valores["servico"]),
        frete=D(valores["frete"]),
    )


def _destinacoes(movimento: MovimentoFinanceiro) -> list[tuple[str | None, str | None, Decimal]]:
    return [
        (t.de.destinacao if t.de else None, t.para.destinacao if t.para else None, t.valor)
        for t in movimento.transferencias.order_by("pk")
    ]


def _deficit(c: Cenario) -> Despesa:
    return Despesa.objects.get(tipo="deficit_frete", ciclo=c.ap.ciclo)


def test_a_apuracao_leva_a_custodia_para_fornecedor_receita_e_frete(cen: Cenario) -> None:
    ap = cen.ap  # A-1
    apuracao = _apurar(cen)
    assert saldo(obrigacao_de(ap.fornecedor, ap.rodada)) == D("100.00")
    assert saldo(receita_de(ap.rodada)) == D("3.75")  # 5,00 menos a tarifa de 1,25
    assert saldo(frete_de(ap.rodada)) == D("20.00")
    assert _custodias(cen, ap.b) == [D("0.00"), D("0.00"), D("0.00")]
    assert (apuracao.frete_efetivo, apuracao.frete_arrecadado) == (D("30.00"), D("20.00"))
    assert apuracao.ciclo_id == ap.ciclo.pk
    (movimento,) = MovimentoFinanceiro.objects.filter(tipo=T.APURACAO)
    assert movimento.chave == f"apuracao:{ap.ciclo.pk}"
    assert movimento.justificativa == "Apuração final aprovada (infraestrutura 3.2)"


def test_a_tarifa_da_rodada_e_coberta_pela_receita_sem_tocar_o_fornecedor(cen: Cenario) -> None:
    ap = cen.ap  # A-2, cenário 30, P-1
    antes = Pedido.objects.filter(pk=ap.x.pk).values().get()
    _apurar(cen)
    (cobertura,) = MovimentoFinanceiro.objects.filter(tipo=T.COBERTURA_DE_DESPESA)
    assert (cobertura.autor_tipo, cobertura.autor_id) == ("sistema", None)
    assert "P-1" in cobertura.justificativa
    assert _destinacoes(cobertura) == [("receita_servico", "despesas_a_cobrir", D("1.25"))]
    assert not [i for i in itens_sem_cobertura() if i.tipo == "despesa" and i.valor == D("1.25")]
    assert saldo(obrigacao_de(ap.fornecedor, ap.rodada)) == D("100.00")
    assert Pedido.objects.filter(pk=ap.x.pk).values().get() == antes


def test_o_frete_do_ciclo_mostra_o_deficit_pendente(cen: Cenario) -> None:  # A-3, cenário 31
    _apurar(cen)
    assert frete_do_ciclo(cen.ap.ciclo) == FreteDoCiclo(
        efetivo=D("30.00"),
        arrecadado=D("20.00"),
        devolvido=D("0.00"),
        deficit=D("10.00"),
        deficit_coberto=D("0.00"),
    )
    deficit = _deficit(cen)
    assert (deficit.valor, deficit.rodada_id) == (D("10.00"), cen.ap.rodada.pk)


def test_o_deficit_e_coberto_pela_receita_e_pela_reserva(cen: Cenario) -> None:  # A-4, cenário 31
    ap = cen.ap
    _apurar(cen)
    deficit = _deficit(cen)
    cobrir_despesa(
        ap.admin, deficit, fonte=("receita", ap.rodada), valor=D("3.75"), justificativa="a"
    )
    cobrir_despesa(ap.admin, deficit, fonte="reserva", valor=D("6.25"), justificativa="b")
    assert saldo(frete_de(ap.rodada)) == D("30.00")
    assert saldo(receita_de(ap.rodada)) == D("0.00")
    assert saldo(reserva()) == D("993.75")
    assert frete_do_ciclo(ap.ciclo).deficit_coberto == D("10.00")
    assert EntradaAuditoria.objects.filter(acao="financeiro.movimento").count() >= 2
    assert not [i for i in itens_sem_cobertura() if i.tipo == "despesa"]


def test_tarifa_que_nao_cabe_na_receita_da_rodada_fica_pendente(cen: Cenario) -> None:  # A-5
    ap = cen.ap
    _apurar(cen)
    mover(T.RETIRADA_DE_RECEITA, receita_de(ap.rodada), EXTERIOR, "3.75")
    cen.sim.definir_tarifa("pix", percentual=D("0.00"), fixa=D("0.80"))
    id_externo = pagar_pedido(ap, ap.y, cen.sim, cen.relogio, 2 * H)
    pagamento = PagamentoNoProvedor.objects.get(id_externo=id_externo)
    assert pagamento.tarifa == D("0.80")
    registrar_tarifa(pagamento)
    tarifa = Despesa.objects.get(tipo="tarifa", pagamento=pagamento)
    assert tarifa.rodada_id == ap.rodada.pk
    assert ("despesa", tarifa.pk, D("0.80")) in [
        (i.tipo, i.objeto_id, i.valor) for i in itens_sem_cobertura()
    ]
    assert saldo(receita_de(ap.rodada)) == D("0.00")


def test_obrigacao_antes_da_apuracao_e_financiada_pela_custodia(cen: Cenario) -> None:  # A-6
    resultado = _obrigacao(cen)
    assert resultado.sem_cobertura == D("0.00")
    obrigacao = resultado.obrigacao
    assert (obrigacao.produtos, obrigacao.servico, obrigacao.frete) == (
        D("25.00"),
        D("1.25"),
        D("5.00"),
    )
    assert obrigacao.depois_da_apuracao is False
    assert _custodias(cen, cen.ap.b) == [D("75.00"), D("3.75"), D("15.00")]
    (movimento,) = MovimentoFinanceiro.objects.filter(tipo=T.FINANCIAMENTO_DE_OBRIGACAO)
    assert movimento.transferencias.count() == 3
    assert (movimento.autor_tipo, "P-2" in movimento.justificativa) == ("sistema", True)


def test_obrigacao_depois_da_apuracao_usa_as_fontes_da_rodada(cen: Cenario) -> None:  # A-7
    ap = cen.ap
    _apurar(cen)
    resultado = _obrigacao(cen)
    assert resultado.sem_cobertura == D("0.00")
    assert resultado.obrigacao.depois_da_apuracao is True
    assert saldo(obrigacao_de(ap.fornecedor, ap.rodada)) == D("75.00")
    assert saldo(receita_de(ap.rodada)) == D("2.50")
    assert saldo(frete_de(ap.rodada)) == D("15.00")
    novo = Despesa.objects.filter(tipo="deficit_frete", valor=D("5.00"))
    assert novo.count() == 1
    assert frete_do_ciclo(ap.ciclo).devolvido == D("5.00")


def _apos_o_repasse(c: Cenario) -> Any:
    _apurar(c)
    mover(T.REPASSE, obrigacao_de(c.ap.fornecedor, c.ap.rodada), EXTERIOR, "100.00")
    return _obrigacao(c, servico="0.00", frete="0.00")


def test_sem_saldo_depois_do_repasse_a_obrigacao_fica_sem_cobertura(cen: Cenario) -> None:  # A-8
    resultado = _apos_o_repasse(cen)
    assert resultado.sem_cobertura == D("25.00")
    assert resultado.obrigacao.devido == D("25.00")
    assert saldo(obrigacao_de(cen.ap.fornecedor, cen.ap.rodada)) == D("0.00")
    assert (
        AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None).count() == 0
    )


def test_receita_de_outra_rodada_e_reserva_cobrem_o_que_faltou(cen: Cenario) -> None:  # A-9
    from tests.apoio.financeiro import montar_mundo, semear

    mundo = montar_mundo()
    r2 = mundo.rb
    semear(mundo, receita_de(r2), "10.00")
    obrigacao = _apos_o_repasse(cen).obrigacao
    cobrir_obrigacao_com_receita(cen.ap.admin, obrigacao, r2, D("10.00"), "receita de outra rodada")
    designar_reserva(cen.ap.admin, obrigacao, D("15.00"), "reserva")
    assert [i for i in itens_sem_cobertura() if i.tipo == "obrigacao"] == []
    assert saldo(receita_de(r2)) == D("0.00")
    assert situacao_da_reserva().comprometido == D("15.00")


def test_liquidar_consome_o_financiado_e_a_designacao_uma_vez_so(cen: Cenario) -> None:  # A-10
    obrigacao = _apos_o_repasse(cen).obrigacao
    from tests.apoio.financeiro import montar_mundo, semear

    mundo = montar_mundo()
    semear(mundo, receita_de(mundo.rb), "10.00")
    cobrir_obrigacao_com_receita(cen.ap.admin, obrigacao, mundo.rb, D("10.00"), "receita")
    designar_reserva(cen.ap.admin, obrigacao, D("15.00"), "reserva")
    primeira = liquidar_obrigacao(obrigacao, D("25.00"), referencia="dev-1")
    assert primeira.chave == "devolucao:dev-1"
    consumo = MovimentoFinanceiro.objects.filter(
        tipo=T.FINANCIAMENTO_DE_OBRIGACAO, origem_tipo="financeiro.designacaodareserva"
    )
    assert consumo.count() == 1
    assert situacao_da_reserva().comprometido == D("0.00")
    assert primeira.tipo == T.DEVOLUCAO
    assert sum(t.valor for t in primeira.transferencias.all()) == D("25.00")
    movimentos = MovimentoFinanceiro.objects.count()
    assert liquidar_obrigacao(obrigacao, D("25.00"), referencia="dev-1").pk == primeira.pk
    assert MovimentoFinanceiro.objects.count() == movimentos
    with pytest.raises(LiquidacaoRecusada):
        liquidar_obrigacao(obrigacao, D("0.01"), referencia="dev-2")
    assert MovimentoFinanceiro.objects.count() == movimentos
    with pytest.raises(MovimentoConflitante):
        liquidar_obrigacao(obrigacao, D("24.00"), referencia="dev-1")


def _duplicidade(c: Cenario) -> Any:
    """Uma obrigação de 125,00 vinda de destino `duplicidade`, com o alerta aberto: um segundo
    pagamento do pedido X, que já está pago."""
    from apps.pagamentos.provedor import NovaCobranca, obter_provedor
    from apps.pedidos.models import DestinoDoPagamento
    from tests.apoio.pedidos import sincronizar

    c.relogio.congelar(T0 + 2 * H)
    nova = NovaCobranca(
        chave_idempotencia="k-duplicidade",
        referencia_externa=c.ap.x.referencia_externa,
        valor=D("125.00"),
        descricao="Segundo pagamento",
        expira_em=T0 + 24 * H,
    )
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    c.sim.aprovar(id_externo)
    sincronizar(id_externo)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)
    assert destino.motivo == "duplicidade"
    return ObrigacaoComComprador.objects.get(origem_id=str(destino.pk)), id_externo


def test_liquidar_a_duplicidade_resolve_o_alerta(cen: Cenario) -> None:  # A-11
    obrigacao, id_externo = _duplicidade(cen)
    assert AlertaFinanceiro.objects.filter(tipo="duplicidade", resolvido_em=None).count() == 1
    liquidar_obrigacao(obrigacao, D("100.00"), referencia="parcial")
    assert AlertaFinanceiro.objects.filter(tipo="duplicidade", resolvido_em=None).count() == 1
    liquidar_obrigacao(obrigacao, D("25.00"), referencia="resto")
    alerta = AlertaFinanceiro.objects.get(tipo="duplicidade", chave=id_externo)
    assert alerta.resolvido_em is not None


def test_apuracao_repetida_devolve_a_existente(cen: Cenario) -> None:  # A-12
    primeira = _apurar(cen)
    movimentos = MovimentoFinanceiro.objects.count()
    assert _apurar(cen).pk == primeira.pk
    assert MovimentoFinanceiro.objects.count() == movimentos
    with pytest.raises(MovimentoConflitante):
        registrar_apuracao_no_livro(cen.ap.ciclo, [], autor=SISTEMA)


def test_pre_condicoes_da_apuracao(cen: Cenario) -> None:  # A-13
    from tests.apoio.financeiro import montar_ap as outro_arranjo

    outro = outro_arranjo()
    antes = (MovimentoFinanceiro.objects.count(), ApuracaoNoLivro.objects.count())
    for lista in ([cen.ap.y], [outro.x], [cen.ap.x, cen.ap.x]):
        with pytest.raises(ValueError):  # noqa: PT011
            registrar_apuracao_no_livro(cen.ap.ciclo, lista, autor=SISTEMA)
    assert (MovimentoFinanceiro.objects.count(), ApuracaoNoLivro.objects.count()) == antes


def test_antes_da_apuracao_o_frete_nao_tem_efetivo(cen: Cenario) -> None:  # A-14
    assert frete_do_ciclo(cen.ap.ciclo) == FreteDoCiclo(None, None, None, None, None)


def test_obrigacao_invalida_e_recusada(cen: Cenario) -> None:  # A-15
    ap = cen.ap
    _obrigacao(cen)
    antes = (ObrigacaoComComprador.objects.count(), MovimentoFinanceiro.objects.count())
    base: dict[str, Any] = {
        "origem": ap.y,
        "rodada": ap.rodada,
        "ciclo": ap.ciclo,
        "comprador": ap.b,
        "pedido": ap.x,
        "motivo": "teste",
        "produtos": D("10.00"),
        "servico": D("0.00"),
        "frete": D("0.00"),
    }
    invalidas: list[dict[str, Any]] = [
        {"produtos": D("-1.00"), "servico": D("5.00")},
        {"produtos": D("0.00")},
        {"comprador": ap.d},  # o pedido é de B, e não de D
        {"origem": ap.x},  # a origem já foi usada
    ]
    for mudanca in invalidas:
        with pytest.raises(ValueError):  # noqa: PT011
            registrar_obrigacao_com_comprador(**{**base, **mudanca})
    assert (ObrigacaoComComprador.objects.count(), MovimentoFinanceiro.objects.count()) == antes


def test_cobertura_acima_do_devido_e_recusada(cen: Cenario) -> None:  # A-16
    ap = cen.ap
    _apurar(cen)
    deficit = _deficit(cen)
    antes = (MovimentoFinanceiro.objects.count(), saldo(reserva()))
    with pytest.raises(CoberturaExcedente):
        cobrir_despesa(ap.admin, deficit, fonte="reserva", valor=D("10.01"), justificativa="x")
    obrigacao = _apos_o_repasse(cen).obrigacao
    movimentos = MovimentoFinanceiro.objects.count()
    with pytest.raises(CoberturaExcedente):
        cobrir_obrigacao_com_receita(ap.admin, obrigacao, ap.rodada, D("25.01"), "x")
    assert MovimentoFinanceiro.objects.count() == movimentos
    assert antes[1] == saldo(reserva())


def test_receita_sem_saldo_nao_cobre(cen: Cenario) -> None:
    obrigacao = _apos_o_repasse(cen).obrigacao
    with pytest.raises(SaldoInsuficiente):
        cobrir_obrigacao_com_receita(cen.ap.admin, obrigacao, cen.ap.rodada, D("25.00"), "x")


def test_so_o_administrador_cobre(cen: Cenario) -> None:
    obrigacao = _apos_o_repasse(cen).obrigacao
    deficit = _deficit(cen)
    for autor in (cen.ap.b, None):
        with pytest.raises(PermissionDenied):
            cobrir_obrigacao_com_receita(autor, obrigacao, cen.ap.rodada, D("1.00"), "x")  # type: ignore[arg-type]
        with pytest.raises(PermissionDenied):
            cobrir_despesa(autor, deficit, fonte="reserva", valor=D("1.00"), justificativa="x")  # type: ignore[arg-type]


# --- Correção E09-R04: o frete coberto inclui a cobertura das obrigações (A-25 e A-26) ----------


def _arranjo_f(c: Cenario) -> None:
    """O A-4 (déficit de 10,00 coberto) e o frete de 30,00 pago: `frete(r)` em 0,00."""
    ap = c.ap
    _apurar(c)
    deficit = _deficit(c)
    cobrir_despesa(
        ap.admin, deficit, fonte=("receita", ap.rodada), valor=D("3.75"), justificativa="a"
    )
    cobrir_despesa(ap.admin, deficit, fonte="reserva", valor=D("6.25"), justificativa="b")
    registrar_saida(
        ap.admin,
        tipo="pagamento_do_frete",
        conta=frete_de(ap.rodada),
        valor=D("30.00"),
        identificacao="frete-1",
        justificativa="Pagamento do frete",
    )
    assert saldo(frete_de(ap.rodada)) == D("0.00")


def _coberto(c: Cenario) -> Decimal | None:
    return frete_do_ciclo(c.ap.ciclo).deficit_coberto


def test_cobertura_da_obrigacao_so_de_frete_entra_no_deficit_coberto(cen: Cenario) -> None:
    ap = cen.ap  # A-25, E09-R04
    _arranjo_f(cen)
    resultado = _obrigacao(cen, produtos="0.00", servico="0.00", frete="5.00")
    assert resultado.sem_cobertura == D("5.00")
    assert Despesa.objects.filter(tipo="deficit_frete").count() == 1  # sem despesa nova
    leituras = []
    for passo in range(3):
        if passo == 1:
            designar_reserva(ap.admin, resultado.obrigacao, D("5.00"), "reserva")
        if passo == 2:
            liquidar_obrigacao(resultado.obrigacao, D("5.00"), referencia="dev-frete")
        relatorio = frete_do_ciclo(ap.ciclo)
        assert (relatorio.devolvido, relatorio.deficit) == (D("5.00"), D("15.00"))
        leituras.append(relatorio.deficit_coberto)
    assert leituras == [D("10.00"), D("15.00"), D("15.00")]


def test_o_que_falta_da_obrigacao_mista_e_atribuido_primeiro_ao_frete(cen: Cenario) -> None:
    ap = cen.ap  # A-26, E09-R04
    _arranjo_f(cen)
    obrigacao = ObrigacaoComComprador.objects.create(
        rodada=ap.rodada,
        ciclo=ap.ciclo,
        pedido=ap.x,
        comprador=ap.b,
        origem_tipo="teste",
        origem_id="mista",
        motivo="devolucao_de_teste",
        produtos=D("10.00"),
        frete=D("5.00"),
        depois_da_apuracao=True,
    )
    leituras = [_coberto(cen)]
    for valor in ("5.00", "8.00", "2.00"):
        designar_reserva(ap.admin, obrigacao, D(valor), "reserva")
        relatorio = frete_do_ciclo(ap.ciclo)
        assert (relatorio.devolvido, relatorio.deficit) == (D("5.00"), D("15.00"))
        leituras.append(relatorio.deficit_coberto)
    assert leituras == [D("10.00"), D("10.00"), D("13.00"), D("15.00")]
