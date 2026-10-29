"""E09-04: entradas dos pagamentos e tarifas no livro-razão (A-1, A-2, A-5 a A-10 e A-13)."""

from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from apps.contas.models import Conta
from apps.financeiro.entradas import (
    registrar_entrada,
    registrar_tarifa,
    registrar_tarifas_pendentes_agora,
)
from apps.financeiro.livro import saldo
from apps.financeiro.models import (
    AlertaFinanceiro,
    Componente,
    ContaFinanceira,
    Despesa,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeMovimento,
)
from apps.pagamentos.models import PagamentoNoProvedor
from apps.pagamentos.provedor import NovaCobranca, obter_provedor
from apps.pagamentos.sincronizacao import sincronizar_pagamento
from apps.pedidos.models import DestinoDoPagamento, ItemDoPedido, Pedido
from apps.pedidos.sinais import destino_do_pagamento_decidido
from apps.pedidos.tarefas import reconsultar_pagamentos_da_margem_agora
from tests.apoio.financeiro import (
    custodia,
    despesas,
    obrigacao_com,
    pedido_composto,
)
from tests.apoio.pedidos import T0, cancelar_direto, sincronizar, tentativa_criada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
T = TipoDeMovimento


def _um(itens: Any) -> Any:
    achados = list(itens)
    assert len(achados) == 1, f"esperava 1 registro, há {len(achados)}"
    return achados[0]


@dataclass
class Ambiente:
    b: Conta
    x: Pedido
    sim: Any
    relogio: RelogioControlado


@pytest.fixture
def amb(relogio: RelogioControlado, simulador_pagamentos: Any) -> Ambiente:
    """O pedido X de B (produtos 100, serviço 5, frete 20), tarifa de 1% e liberação em 24h."""
    relogio.congelar(T0 + H)
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    simulador_pagamentos.definir_liberacao("pix", horas=24)
    b = ContaFactory.create(nome="Comprador B")
    return Ambiente(b, pedido_composto(b), simulador_pagamentos, relogio)


def _pagar(a: Ambiente, em: timedelta = H) -> str:
    """Cria a cobrança de X, aprova em `T0 + em` e sincroniza."""
    id_externo = tentativa_criada(a.x).id_externo
    assert id_externo is not None
    a.relogio.congelar(T0 + em)
    a.sim.aprovar(id_externo)
    sincronizar(id_externo)
    return id_externo


def _custodias(a: Ambiente) -> list[Decimal]:
    rodada, ciclo = a.x.abertura.rodada, a.x.abertura.ciclo
    return [
        saldo(custodia(rodada, ciclo, a.b, componente))
        for componente in (Componente.PRODUTOS, Componente.SERVICO, Componente.FRETE)
    ]


def _destino(id_externo: str) -> DestinoDoPagamento:
    return DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)


def _movimentos(tipo: str) -> list[MovimentoFinanceiro]:
    return list(MovimentoFinanceiro.objects.filter(tipo=tipo).order_by("pk"))


def test_pagamento_que_quita_entra_na_custodia_por_componente(amb: Ambiente) -> None:  # A-1
    id_externo = _pagar(amb)
    destino = _destino(id_externo)
    assert (destino.destino, destino.motivo) == ("quita", "")
    entrada = _um(_movimentos(T.ENTRADA_DE_PAGAMENTO))
    assert entrada.chave == f"entrada:{destino.pk}"
    assert (entrada.autor_tipo, entrada.autor_id) == ("sistema", None)
    assert entrada.transferencias.count() == 3
    assert _custodias(amb) == [D("100.00"), D("5.00"), D("20.00")]
    tocadas = ContaFinanceira.objects.exclude(destinacao="custodia").exclude(
        destinacao="despesas_a_cobrir"
    )
    assert [c for c in tocadas if saldo(c) != 0] == []


def test_a_tarifa_vira_despesa_sem_mexer_em_valores(amb: Ambiente) -> None:  # A-2
    itens_antes = list(ItemDoPedido.objects.filter(pedido=amb.x).values())
    pedido_antes = Pedido.objects.filter(pk=amb.x.pk).values().get()
    id_externo = _pagar(amb)
    pagamento = PagamentoNoProvedor.objects.get(id_externo=id_externo)
    despesa = _um(Despesa.objects.all())
    assert (despesa.tipo, despesa.valor, despesa.rodada_id) == (
        "tarifa",
        D("1.25"),
        amb.x.abertura.rodada_id,
    )
    assert despesa.pagamento_id == pagamento.pk
    tarifa = _um(_movimentos(T.TARIFA))
    assert tarifa.chave == f"tarifa:{pagamento.pk}"
    assert saldo(despesas()) == D("-1.25")
    assert _custodias(amb) == [D("100.00"), D("5.00"), D("20.00")]
    assert Pedido.objects.filter(pk=amb.x.pk).values().get() == pedido_antes
    assert list(ItemDoPedido.objects.filter(pedido=amb.x).values()) == itens_antes


def _sem_pedido(a: Ambiente, valor: str = "40.00") -> str:
    """Uma cobrança com referência que nenhum pedido tem, aprovada e sincronizada."""
    nova = NovaCobranca(
        chave_idempotencia="k-sem-pedido",
        referencia_externa="ref-desconhecida",
        valor=D(valor),
        descricao="Sem pedido",
        expira_em=T0 + 24 * H,
    )
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    a.sim.aprovar(id_externo)
    sincronizar(id_externo)
    return id_externo


def test_pagamento_sem_pedido_vira_obrigacao_sem_alerta(amb: Ambiente) -> None:  # A-5
    id_externo = _sem_pedido(amb)
    destino = _destino(id_externo)
    assert destino.destino == "sem_pedido"
    obrigacao = _um(ObrigacaoComComprador.objects.all())
    assert (obrigacao.rodada, obrigacao.ciclo, obrigacao.pedido, obrigacao.comprador) == (
        None,
        None,
        None,
        None,
    )
    assert obrigacao.integral == D("40.00")
    assert obrigacao.motivo == "referencia_desconhecida"
    entrada = _um(_movimentos(T.ENTRADA_PARA_DEVOLUCAO))
    assert entrada.chave == f"entrada:{destino.pk}"
    assert saldo(ContaFinanceira.objects.get(destinacao="obrigacao_comprador")) == D("40.00")
    assert AlertaFinanceiro.objects.count() == 0
    despesa = _um(Despesa.objects.all())
    assert (despesa.rodada, despesa.valor) == (None, D("0.40"))


def _cobranca_direta(
    a: Ambiente, referencia: str, valor: str, chave: str, expira_em: Any = None
) -> str:
    nova = NovaCobranca(
        chave_idempotencia=chave,
        referencia_externa=referencia,
        valor=D(valor),
        descricao="Pedido de teste",
        expira_em=expira_em or T0 + 72 * H,
    )
    return obter_provedor().criar_cobranca(nova).pagamento.id_externo


@pytest.mark.parametrize(
    "motivo", ["iniciado_fora_do_prazo", "pedido_cancelado", "valor_divergente"]
)
def test_outros_motivos_de_devolucao_viram_obrigacao_sem_alerta(
    amb: Ambiente, motivo: str
) -> None:  # A-6
    referencia = amb.x.referencia_externa
    if motivo == "iniciado_fora_do_prazo":
        amb.relogio.congelar(T0 + 25 * H)  # criada depois das 24h
        id_externo = _cobranca_direta(amb, referencia, "125.00", "k-fora")
        valor = D("125.00")
    elif motivo == "pedido_cancelado":
        criada = tentativa_criada(amb.x).id_externo
        assert criada is not None
        id_externo = criada
        cancelar_direto(amb.x, "suspensao", T0 + 2 * H)
        amb.relogio.congelar(T0 + 3 * H)
        valor = D("125.00")
    else:
        id_externo = _cobranca_direta(amb, referencia, "100.00", "k-valor")
        valor = D("100.00")
    amb.sim.aprovar(id_externo)
    sincronizar(id_externo)
    assert _destino(id_externo).motivo == motivo
    obrigacao = _um(ObrigacaoComComprador.objects.all())
    assert (obrigacao.motivo, obrigacao.integral) == (motivo, valor)
    assert obrigacao.pedido_id == amb.x.pk
    conta_ = obrigacao_com(amb.x.abertura.rodada, amb.x.abertura.ciclo, amb.b, obrigacao.pk)
    assert saldo(conta_) == valor
    assert len(_movimentos(T.ENTRADA_PARA_DEVOLUCAO)) == 1
    assert _movimentos(T.ENTRADA_DE_PAGAMENTO) == []
    assert AlertaFinanceiro.objects.count() == 0


def test_repetir_nao_cria_nada_de_novo(amb: Ambiente) -> None:  # A-7
    id_externo = _pagar(amb)
    destino = _destino(id_externo)
    pagamento = PagamentoNoProvedor.objects.get(id_externo=id_externo)
    antes = (
        MovimentoFinanceiro.objects.count(),
        ObrigacaoComComprador.objects.count(),
        Despesa.objects.count(),
    )
    with transaction.atomic():
        registrar_entrada(destino)
        registrar_tarifa(pagamento)
    amb.relogio.congelar(T0 + 25 * H)
    assert reconsultar_pagamentos_da_margem_agora() >= 1
    assert (
        MovimentoFinanceiro.objects.count(),
        ObrigacaoComComprador.objects.count(),
        Despesa.objects.count(),
    ) == antes


def test_tarifa_informada_depois_e_registrada_pela_tarefa(amb: Ambiente) -> None:  # A-8
    id_externo = tentativa_criada(amb.x).id_externo
    assert id_externo is not None
    amb.sim.aprovar(id_externo)
    completa = obter_provedor().consultar_pagamento(id_externo)
    with transaction.atomic():
        sincronizar_pagamento(replace(completa, tarifa=None, liberado_em=None), origem="tarefa")
    assert Despesa.objects.count() == 0
    assert _movimentos(T.TARIFA) == []
    assert registrar_tarifas_pendentes_agora() == 0  # ainda sem tarifa
    sincronizar(id_externo)
    assert Despesa.objects.count() == 0  # a sincronização não registra; a tarefa registra
    assert registrar_tarifas_pendentes_agora() == 1
    despesa = _um(Despesa.objects.all())
    assert despesa.valor == D("1.25")
    assert len(_movimentos(T.TARIFA)) == 1
    assert registrar_tarifas_pendentes_agora() == 0


def test_tarifa_zero_nao_gera_despesa(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-9
    relogio.congelar(T0 + H)
    b = ContaFactory.create()
    amb = Ambiente(b, pedido_composto(b), simulador_pagamentos, relogio)
    _pagar(amb)
    assert Despesa.objects.count() == 0
    assert _movimentos(T.TARIFA) == []
    assert len(_movimentos(T.ENTRADA_DE_PAGAMENTO)) == 1


class _Estoura:
    """Receptor de teste que levanta uma exceção, só uma vez, depois do receptor financeiro."""

    def __init__(self) -> None:
        self.estourou = False

    def __call__(self, sender: Any, destino: Any, **kwargs: Any) -> None:
        if not self.estourou:
            self.estourou = True
            raise RuntimeError("falha local de teste")


def test_excecao_depois_do_receptor_financeiro_desfaz_tudo(amb: Ambiente) -> None:  # A-10
    primeira = tentativa_criada(amb.x).id_externo
    assert primeira is not None
    amb.sim.expirar(primeira)
    sincronizar(primeira)
    amb.relogio.congelar(T0 + 2 * H)
    segunda = tentativa_criada(amb.x).id_externo
    assert segunda is not None
    amb.sim.aprovar(primeira, em=T0 + 90 * timedelta(minutes=1))
    amb.sim.aprovar(segunda, em=T0 + 2 * H)
    sincronizar(primeira)  # quita
    antes = (
        DestinoDoPagamento.objects.count(),
        MovimentoFinanceiro.objects.count(),
        Despesa.objects.count(),
    )
    estoura = _Estoura()
    destino_do_pagamento_decidido.connect(estoura, weak=False, dispatch_uid="teste-estoura")
    try:
        with pytest.raises(RuntimeError):
            sincronizar(segunda)
    finally:
        destino_do_pagamento_decidido.disconnect(dispatch_uid="teste-estoura")
    assert (
        DestinoDoPagamento.objects.count(),
        MovimentoFinanceiro.objects.count(),
        Despesa.objects.count(),
    ) == antes
    assert ObrigacaoComComprador.objects.count() == 0
    assert AlertaFinanceiro.objects.count() == 0
    sincronizar(segunda)
    assert _destino(segunda).motivo == "duplicidade"
    assert ObrigacaoComComprador.objects.count() == 1
    assert AlertaFinanceiro.objects.filter(tipo="duplicidade", resolvido_em=None).count() == 1
    assert len(_movimentos(T.ENTRADA_PARA_DEVOLUCAO)) == 1
    assert len(_movimentos(T.TARIFA)) == 2
    assert Despesa.objects.count() == 2


def test_componentes_zerados_nao_geram_transferencia(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-13
    relogio.congelar(T0 + H)
    b = ContaFactory.create()
    for produtos, servico, frete in (("100.00", "5.00", "0.00"), ("0.01", "0.00", "0.00")):
        pedido = pedido_composto(b, produtos, servico, frete)
        id_externo = tentativa_criada(pedido).id_externo
        assert id_externo is not None
        simulador_pagamentos.aprovar(id_externo)
        sincronizar(id_externo)
        pagamento = PagamentoNoProvedor.objects.get(id_externo=id_externo)
        entrada = MovimentoFinanceiro.objects.get(chave=f"entrada:{_destino(id_externo).pk}")
        valores = [t.valor for t in entrada.transferencias.all()]
        assert sum(valores, D("0.00")) == pagamento.valor
        assert all(v > 0 for v in valores)
        esperado = 2 if frete == "0.00" and servico != "0.00" else 1
        assert len(valores) == esperado


def test_o_banco_recusa_obrigacao_e_despesa_incoerentes(amb: Ambiente) -> None:
    id_externo = _pagar(amb)
    pagamento = PagamentoNoProvedor.objects.get(id_externo=id_externo)
    rodada, ciclo = amb.x.abertura.rodada, amb.x.abertura.ciclo
    base: dict[str, Any] = {"origem_tipo": "teste", "motivo": "duplicidade"}
    completa = {"rodada": rodada, "ciclo": ciclo, "pedido": amb.x, "comprador": amb.b}
    recusados: list[dict[str, Any]] = [
        {**base, "origem_id": "1", **completa, "produtos": D("-1.00"), "integral": D("5.00")},
        {**base, "origem_id": "2", **completa},  # devido zero
        {**base, "origem_id": "3", "rodada": rodada, "integral": D("5.00")},  # nulos misturados
        {**base, "origem_id": "4", **completa, "integral": D("5.00"), "origem_tipo": ""},
    ]
    for campos in recusados:
        with pytest.raises(IntegrityError), transaction.atomic():
            ObrigacaoComComprador.objects.create(**campos)
    assert ObrigacaoComComprador.objects.count() == 0
    ObrigacaoComComprador.objects.create(
        **base, origem_id="9", integral=D("5.00")
    )  # sem pedido: tudo nulo é coerente
    despesas_recusadas: list[dict[str, Any]] = [
        {"tipo": "tarifa", "valor": D("0.00"), "pagamento": pagamento},
        {"tipo": "tarifa", "valor": D("1.00")},  # tarifa sem pagamento
        {"tipo": "deficit_frete", "valor": D("1.00")},  # déficit sem rodada e ciclo
        {"tipo": "tarifa", "valor": D("1.25"), "pagamento": pagamento},  # a tarifa já existe
    ]
    for campos in despesas_recusadas:
        with pytest.raises(IntegrityError), transaction.atomic():
            Despesa.objects.create(**campos)
    assert Despesa.objects.count() == 1
