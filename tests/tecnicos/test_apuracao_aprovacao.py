"""E11-06: aprovação do resultado e avanço para aguardando fornecedor (acceptance A-1 a A-13)."""

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.financeiro.apuracao import frete_do_ciclo
from apps.financeiro.livro import conta, saldo
from apps.financeiro.models import (
    AlertaFinanceiro,
    ApuracaoNoLivro,
    Componente,
    Despesa,
    Destinacao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    PedidoApurado,
    TipoDeDespesa,
)
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pedidos.models import DestinoDoPagamento, Pedido, SituacaoDoPedido, TentativaDePagamento
from tests.apoio.apuracao import H, arranjo_ap, cobranca, pagar
from tests.apoio.pedidos import T0, pedido_de
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H
ALERTA = "aprovado_no_prazo_depois_da_apuracao"


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


@pytest.fixture
def consultas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from apps.pagamentos import consulta
    from apps.pedidos import apuracao

    registradas: list[str] = []
    original = consulta.consultar_antes_de_decidir

    def espiar(referencia: str) -> Any:
        registradas.append(referencia)
        return original(referencia)

    monkeypatch.setattr(apuracao, "consultar_antes_de_decidir", espiar)
    return registradas


def _iniciar(a: Any) -> Any:
    from apps.pedidos.apuracao import iniciar_apuracao

    return iniciar_apuracao(a.admin, a.rodada)


def _aprovar(a: Any) -> Any:
    from apps.pedidos.apuracao import aprovar_resultado

    return aprovar_resultado(a.admin, a.rodada)


def _v(relogio: RelogioControlado, sim: Any, **arranjo: Any) -> tuple[Any, Pedido, Pedido, Any]:
    """O arranjo V: AP-viável, X pago, Y sem pagamento, apurado em `T0 + 48h`; relógio `T0 + 49h`."""
    a, x, y = arranjo_ap(relogio, **arranjo)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    relogio.congelar(T0 + 49 * H)
    return a, x, y, apuracao


def _custodia(a: Any, comprador: Any) -> list[Decimal]:
    return [
        saldo(
            conta(
                Destinacao.CUSTODIA,
                rodada=a.rodada.pk,
                ciclo=a.ciclo.pk,
                comprador=comprador.pk,
                componente=componente,
            )
        )
        for componente in (Componente.PRODUTOS, Componente.SERVICO, Componente.FRETE)
    ]


def _foto() -> tuple[Any, ...]:
    from apps.pedidos.models import AprovacaoDoResultado

    return (
        AprovacaoDoResultado.objects.count(),
        ApuracaoNoLivro.objects.count(),
        Despesa.objects.count(),
        MovimentoFinanceiro.objects.count(),
        EntradaAuditoria.objects.count(),
    )


def test_aprovar_leva_a_apuracao_ao_livro_e_avanca_a_rodada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    from apps.pedidos.models import AprovacaoDoResultado

    a, x, _y, apuracao = _v(relogio, sim)
    aprovacao = _aprovar(a)
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "aguardando_fornecedor"
    assert aprovacao.apuracao_id == apuracao.pk
    assert AprovacaoDoResultado.objects.count() == 1
    no_livro = ApuracaoNoLivro.objects.get(ciclo=a.ciclo)
    assert list(
        PedidoApurado.objects.filter(apuracao=no_livro).values_list("pedido_id", flat=True)
    ) == [x.pk]
    assert no_livro.movimento is not None
    assert no_livro.movimento.chave == f"apuracao:{a.ciclo.pk}"
    assert (no_livro.frete_efetivo, no_livro.frete_arrecadado) == (D("22.00"), D("7.76"))
    destinos = {
        componente: saldo(
            conta(destinacao, rodada=a.rodada.pk)
            if destinacao != Destinacao.OBRIGACAO_FORNECEDOR
            else conta(destinacao, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk)
        )
        for componente, destinacao in (
            ("produtos", Destinacao.OBRIGACAO_FORNECEDOR),
            ("servico", Destinacao.RECEITA_SERVICO),
            ("frete", Destinacao.FRETE),
        )
    }
    assert destinos == {"produtos": D("60.00"), "servico": D("3.00"), "frete": D("7.76")}
    (deficit,) = Despesa.objects.filter(tipo=TipoDeDespesa.DEFICIT_DE_FRETE)
    assert deficit.valor == D("14.24")


def test_o_pedido_e_o_pagamento_nao_mudam_e_a_custodia_zera(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, x, _y, _ = _v(relogio, sim)
    antes = (
        list(Pedido.objects.order_by("pk").values()),
        SituacaoDoPedido.objects.get(pedido=x).quitado_por_id,
        TentativaDePagamento.objects.count(),
    )
    _aprovar(a)
    assert (
        list(Pedido.objects.order_by("pk").values()),
        SituacaoDoPedido.objects.get(pedido=x).quitado_por_id,
        TentativaDePagamento.objects.count(),
    ) == antes
    assert _custodia(a, a.a) == [D("0.00"), D("0.00"), D("0.00")]


def test_frete_do_ciclo_depois_da_aprovacao(relogio: RelogioControlado, sim: Any) -> None:  # A-3
    a, _x, _y, _ = _v(relogio, sim)
    _aprovar(a)
    frete = frete_do_ciclo(a.ciclo)
    assert (frete.efetivo, frete.arrecadado, frete.devolvido, frete.deficit) == (
        D("22.00"),
        D("7.76"),
        D("0.00"),
        D("14.24"),
    )


def test_a_nova_consulta_registra_o_pagamento_descoberto_e_o_avanco_segue(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(PRAZO)
    _iniciar(a)
    sim.aprovar(id_y, em=PRAZO - timedelta(minutes=1))
    relogio.congelar(T0 + 49 * H)
    _aprovar(a)
    destino = DestinoDoPagamento.objects.get(pedido=y)
    assert (destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")
    assert ObrigacaoComComprador.objects.get(pedido=y).integral == y.total
    assert AlertaFinanceiro.objects.filter(tipo=ALERTA, resolvido_em=None).count() == 1
    assert SituacaoDoPedido.objects.get(pedido=y).situacao == "cancelado"
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "aguardando_fornecedor"
    assert list(PedidoApurado.objects.values_list("pedido_id", flat=True)) == [x.pk]


def test_provedor_indisponivel_bloqueia_a_aprovacao(relogio: RelogioControlado, sim: Any) -> None:
    # A-5
    a, _x, _y, _ = _v(relogio, sim)
    antes = _foto()
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    with pytest.raises(ConsultaAoProvedorFalhou):
        _aprovar(a)
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "pagamento"
    assert _foto() == antes


def test_so_o_administrador_aprova(relogio: RelogioControlado, sim: Any) -> None:  # A-6
    from apps.pedidos.apuracao import aprovar_resultado
    from tests.fabricas import ContaFactory

    a, _x, _y, _ = _v(relogio, sim)
    antes = _foto()
    for autor in (a.a, ContaFactory.create(fornecedor=True), None):
        with pytest.raises(PermissionDenied):
            aprovar_resultado(autor, a.rodada)
    assert _foto() == antes


def test_recusas_sem_consulta_nem_escrita(
    relogio: RelogioControlado, sim: Any, consultas: list[str]
) -> None:  # A-7
    from apps.pedidos.apuracao import ApuracaoRecusada

    # (i) sem apuração, depois de T0 + 48h
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    antes = _foto()
    with pytest.raises(ApuracaoRecusada) as recusa:
        _aprovar(a)
    assert recusa.value.codigo == "sem_apuracao"
    assert str(recusa.value) == "A apuração deste ciclo ainda não foi feita."
    assert (consultas, _foto()) == ([], antes)
    # (iii) o avanço já aconteceu
    _iniciar(a)
    relogio.congelar(T0 + 49 * H)
    _aprovar(a)
    consultas.clear()
    antes = _foto()
    with pytest.raises(ApuracaoRecusada) as recusa:
        _aprovar(a)
    assert recusa.value.codigo == "fora_de_pagamento"
    assert (consultas, _foto()) == ([], antes)


def test_retorno_para_interesse_nao_se_aprova(
    relogio: RelogioControlado, sim: Any, consultas: list[str]
) -> None:  # A-7 (ii)
    from apps.pedidos.apuracao import ApuracaoRecusada

    a, x, _y = arranjo_ap(relogio, minimo="100.00")
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    _iniciar(a)
    consultas.clear()
    antes = _foto()
    with pytest.raises(ApuracaoRecusada) as recusa:
        _aprovar(a)
    assert recusa.value.codigo == "fora_de_pagamento"
    assert (consultas, _foto()) == ([], antes)


def test_resultado_de_retorno_com_a_rodada_em_pagamento_nao_e_valido(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    from apps.pedidos.apuracao import ApuracaoRecusada

    a, x, _y = arranjo_ap(relogio, minimo="100.00")
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    _iniciar(a)
    a.rodada.etapa = "pagamento"  # estado que nenhum fluxo produz: isola a conferência
    a.rodada.save(update_fields=["etapa"])
    with pytest.raises(ApuracaoRecusada) as recusa:
        _aprovar(a)
    assert recusa.value.codigo == "resultado_nao_valido"
    assert str(recusa.value) == "Só um resultado válido pode ser aprovado."


@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_dentro_de_transacao_de_quem_chama_e_recusada(
    relogio: RelogioControlado, simulador_pagamentos: Any, consultas: list[str]
) -> None:  # A-9
    a, _x, _y, _ = _v(relogio, simulador_pagamentos)
    antes = _foto()
    consultas.clear()
    with pytest.raises(RuntimeError, match="durable"):
        with transaction.atomic():
            _aprovar(a)
    assert (consultas, _foto()) == ([], antes)


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_duas_aprovacoes_em_paralelo_aprovam_uma(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-10
    from apps.pedidos import apuracao
    from apps.pedidos.apuracao import ApuracaoRecusada
    from apps.pedidos.models import AprovacaoDoResultado
    from tests.apoio.corrida import Corrida

    a, _x, _y, _ = _v(relogio, simulador_pagamentos)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, apuracao, "_registrar_a_apuracao_no_livro")
    ra, rb = corrida.rodar(
        lambda: apuracao.aprovar_resultado(a.admin, a.rodada),
        lambda: apuracao.aprovar_resultado(a.admin, a.rodada),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, ApuracaoRecusada), rb.excecao
    assert rb.excecao.codigo in ("fora_de_pagamento", "ja_aprovado")
    assert AprovacaoDoResultado.objects.count() == 1
    assert ApuracaoNoLivro.objects.count() == 1


@pytest.fixture
def receptor() -> Iterator[list[dict[str, Any]]]:
    from apps.pedidos.sinais import resultado_aprovado

    chamadas: list[dict[str, Any]] = []

    def receber(sender: Any, **kwargs: Any) -> None:
        chamadas.append(kwargs)

    resultado_aprovado.connect(receber, weak=False)
    yield chamadas
    resultado_aprovado.disconnect(receber)


def test_o_sinal_de_aprovacao_leva_a_rodada_o_ciclo_e_a_apuracao(
    relogio: RelogioControlado, sim: Any, receptor: list[dict[str, Any]]
) -> None:  # A-11
    a, _x, _y, apuracao = _v(relogio, sim)
    _aprovar(a)
    (chamada,) = receptor
    assert chamada["rodada"].pk == a.rodada.pk
    assert chamada["ciclo"].pk == a.ciclo.pk
    assert chamada["apuracao"].pk == apuracao.pk


def test_excecao_no_receptor_desfaz_o_avanco(relogio: RelogioControlado, sim: Any) -> None:
    # A-11
    from apps.pedidos.sinais import resultado_aprovado

    a, _x, _y, _ = _v(relogio, sim)
    antes = _foto()

    def quebrar(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("receptor com defeito")

    resultado_aprovado.connect(quebrar, weak=False)
    try:
        with pytest.raises(RuntimeError, match="receptor com defeito"):
            _aprovar(a)
    finally:
        resultado_aprovado.disconnect(quebrar)
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "pagamento"
    assert _foto() == antes


def test_pedido_com_todas_as_unidades_invalidadas_nao_e_valido(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    a, x, _y = arranjo_ap(
        relogio,
        parcelas_de_p1=(("a", 6), ("b", 5)),
        parcelas_de_p2=(("c", 4), ("b", 2), ("a", 6)),
    )
    assert a.c is not None
    z = pedido_de(a.c)
    pagar(relogio, sim, x)
    pagar(relogio, sim, z)
    relogio.congelar(PRAZO)
    assert _iniciar(a).resultado == "valida"
    relogio.congelar(T0 + 49 * H)
    _aprovar(a)
    assert list(PedidoApurado.objects.values_list("pedido_id", flat=True)) == [x.pk]
    assert _custodia(a, a.c) == [D("0.00"), D("0.00"), D("0.00")]


def test_auditoria_da_aprovacao(relogio: RelogioControlado, sim: Any) -> None:  # A-13
    a, x, _y, apuracao = _v(relogio, sim)
    _aprovar(a)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.aprovar_resultado")
    assert auditoria.autor_id == str(a.admin.pk)
    dados = auditoria.alteracoes
    assert dados["apuracao"] == apuracao.pk
    assert dados["pedidos_validos"] == [x.pk]
    assert (dados["frete_efetivo"], dados["frete_arrecadado"], dados["deficit"]) == (
        "22.00",
        "7.76",
        "14.24",
    )
