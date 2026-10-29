"""E09-01: livro-razão, destinações, movimentos e proibições (acceptance A-1 a A-13, A-17, A-18)."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any, cast

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.transaction import TransactionManagementError
from django.test import TestCase as DjangoTestCase

from apps.financeiro.livro import (
    EXTERIOR,
    MovimentoConflitante,
    MovimentoInvalido,
    MovimentoProibido,
    OrdemDeTravasViolada,
    SaldoInsuficiente,
    Transferencia,
    _travar_conta,
    conta,
    extrato,
    lancar,
    saldo,
    saldo_total_esperado,
)
from apps.financeiro.models import (
    Componente,
    ContaFinanceira,
    Destinacao,
    MovimentoFinanceiro,
    TipoDeMovimento,
    TransferenciaFinanceira,
)
from apps.nucleo.auditoria import SISTEMA, EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from tests.apoio.financeiro import (
    Mundo,
    chave_nova,
    custodia,
    despesas,
    frete_de,
    montar_mundo,
    mover,
    obrigacao_com,
    obrigacao_de,
    receita_de,
    reserva,
    semear,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
T = TipoDeMovimento


@pytest.fixture
def m() -> Mundo:
    return montar_mundo()


def _estado() -> tuple[int, int, list[tuple[int, Decimal]]]:
    """Movimentos, transferências e saldos não nulos: o que 'nenhuma escrita' compara (uma conta
    criada vazia pelo chamador não é escrita de dinheiro)."""
    contas = ContaFinanceira.objects.order_by("pk")
    return (
        MovimentoFinanceiro.objects.count(),
        TransferenciaFinanceira.objects.count(),
        [(c.pk, saldo(c)) for c in contas if saldo(c) != 0],
    )


def test_entrada_de_pagamento_em_tres_componentes(m: Mundo) -> None:  # A-1
    produtos = custodia(m.ra, m.ca, m.x, Componente.PRODUTOS)
    servico = custodia(m.ra, m.ca, m.x, Componente.SERVICO)
    frete = custodia(m.ra, m.ca, m.x, Componente.FRETE)
    movimento = lancar(
        tipo=T.ENTRADA_DE_PAGAMENTO,
        transferencias=[
            Transferencia(EXTERIOR, produtos, D("100.00")),
            Transferencia(EXTERIOR, servico, D("5.00")),
            Transferencia(EXTERIOR, frete, D("20.00")),
        ],
        autor=SISTEMA,
        justificativa="P-1: entrada",
        origem=m.ra,
        chave="entrada:1",
    )
    assert movimento.pk is not None
    assert movimento.transferencias.count() == 3
    assert [saldo(produtos), saldo(servico), saldo(frete)] == [D("100.00"), D("5.00"), D("20.00")]
    assert saldo_total_esperado() == D("125.00")
    movimento.refresh_from_db()
    assert movimento.tipo == T.ENTRADA_DE_PAGAMENTO
    assert (movimento.autor_tipo, movimento.autor_id) == ("sistema", None)
    assert movimento.momento is not None
    assert movimento.justificativa == "P-1: entrada"
    assert (movimento.origem_tipo, movimento.origem_id) == ("rodadas.rodada", str(m.ra.pk))
    assert movimento.chave == "entrada:1"


def test_a_conta_nasce_uma_vez_so(m: Mundo) -> None:
    primeira = custodia(m.ra, m.ca, m.x)
    segunda = custodia(m.ra, m.ca, m.x)
    assert primeira.pk is not None
    assert primeira.pk == segunda.pk
    assert conta(Destinacao.RESERVA).pk == reserva().pk
    assert ContaFinanceira.objects.count() == 2


@pytest.mark.acceptance
def test_movimentos_e_transferencias_so_aceitam_insercao(m: Mundo) -> None:  # A-2
    mover(T.ENTRADA_DE_PAGAMENTO, EXTERIOR, custodia(m.ra, m.ca, m.x), "100.00")
    modelos: list[Any] = [MovimentoFinanceiro, TransferenciaFinanceira, ContaFinanceira]
    antes = {modelo.__name__: list(modelo.objects.order_by("pk").values()) for modelo in modelos}
    for modelo in modelos:
        objeto = modelo.objects.order_by("pk").first()
        assert objeto is not None
        with pytest.raises(RegistroImutavel):
            objeto.save()
        with pytest.raises(RegistroImutavel):
            objeto.delete()
        with pytest.raises(RegistroImutavel):
            modelo.objects.all().update(pk=objeto.pk)
        with pytest.raises(RegistroImutavel):
            modelo.objects.all().delete()
        tabela = modelo._meta.db_table
        for sql in (
            f'UPDATE "{tabela}" SET id = id + 1000 WHERE id = %s',  # noqa: S608
            f'DELETE FROM "{tabela}" WHERE id = %s',  # noqa: S608
        ):
            with (
                pytest.raises(DatabaseError),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(sql, [objeto.pk])
    assert {
        modelo.__name__: list(modelo.objects.order_by("pk").values()) for modelo in modelos
    } == antes


def test_tarifa_nao_sai_do_dinheiro_do_fornecedor(m: Mundo) -> None:  # A-3
    produtos = custodia(m.ra, m.ca, m.x)
    semear(m, produtos, "100.00")
    mover(T.TARIFA, despesas(), EXTERIOR, "1.00")
    antes = _estado()
    assert saldo(despesas()) == D("-1.00")
    with pytest.raises(MovimentoProibido) as erro:
        mover(T.COBERTURA_DE_DESPESA, produtos, despesas(), "1.00")
    assert "fluxo_nao_permitido" in str(erro.value)
    assert _estado() == antes


def test_dinheiro_do_fornecedor_nao_vai_para_outra_rodada(m: Mundo) -> None:  # A-4
    devida = obrigacao_de(m.fa, m.ra)
    semear(m, devida, "100.00")
    de_outra_rodada = obrigacao_com(m.rb, m.cb, m.x, numero=2)
    antes = _estado()
    with pytest.raises(MovimentoProibido):
        mover(T.FINANCIAMENTO_DE_OBRIGACAO, devida, de_outra_rodada, "10.00")
    assert _estado() == antes


@pytest.mark.parametrize(
    "tipo",
    [T.FINANCIAMENTO_DE_OBRIGACAO, T.COBERTURA_DE_DESPESA, T.APURACAO, T.REPASSE],
)
@pytest.mark.parametrize(
    "destino", ["frete_de_outra_rodada", "reserva", "receita", "outro_fornecedor"]
)
def test_obrigacao_do_fornecedor_so_vai_para_onde_a_p2_permite(
    m: Mundo, destino: str, tipo: str
) -> None:  # A-5
    devida = obrigacao_de(m.fa, m.ra)
    semear(m, devida, "100.00")
    alvo = {
        "frete_de_outra_rodada": frete_de(m.rb),
        "reserva": reserva(),
        "receita": receita_de(m.ra),
        "outro_fornecedor": obrigacao_de(m.fb, m.rb),
    }[destino]
    antes = _estado()
    with pytest.raises(MovimentoProibido):
        mover(tipo, devida, alvo, "1.00")
    assert _estado() == antes


def test_custodia_nao_vai_para_outro_comprador_nem_troca_de_componente(m: Mundo) -> None:  # A-6
    produtos = custodia(m.ra, m.ca, m.x)
    semear(m, produtos, "100.00")
    antes = _estado()
    with pytest.raises(MovimentoProibido):
        mover(T.FINANCIAMENTO_DE_OBRIGACAO, produtos, obrigacao_com(m.ra, m.ca, m.y), "10.00")
    with pytest.raises(MovimentoProibido):
        mover(T.APURACAO, produtos, receita_de(m.ra), "10.00")
    assert _estado() == antes


def test_ressalva_da_p2_a_devolucao_devida_antes_do_repasse(m: Mundo) -> None:  # A-7
    devida = obrigacao_de(m.fa, m.ra)
    semear(m, devida, "100.00")
    obrigacao = obrigacao_com(m.ra, m.ca, m.x)
    mover(T.FINANCIAMENTO_DE_OBRIGACAO, devida, obrigacao, "25.00")
    assert (saldo(devida), saldo(obrigacao)) == (D("75.00"), D("25.00"))


def _fluxo(m: Mundo, numero: int) -> tuple[str, Any, Any, str]:
    """O arranjo mínimo de cada fluxo da lista: (tipo, origem, destino, valor)."""
    obrigacao = obrigacao_com(m.ra, m.ca, m.x)
    if numero == 1:
        return T.ENTRADA_DE_PAGAMENTO, EXTERIOR, custodia(m.ra, m.ca, m.x), "10.00"
    if numero == 2:
        return T.ENTRADA_PARA_DEVOLUCAO, EXTERIOR, obrigacao, "10.00"
    if numero == 3:
        return T.APORTE, EXTERIOR, reserva(), "10.00"
    if numero == 4:
        return T.TARIFA, despesas(), EXTERIOR, "10.00"
    if numero in (5, 6, 7):
        componente, destino = {
            5: (Componente.PRODUTOS, obrigacao_de(m.fa, m.ra)),
            6: (Componente.SERVICO, receita_de(m.ra)),
            7: (Componente.FRETE, frete_de(m.ra)),
        }[numero]
        origem = custodia(m.ra, m.ca, m.x, componente)
        semear(m, origem, "10.00")
        return T.APURACAO, origem, destino, "10.00"
    if numero == 8:
        origem = custodia(m.ra, m.ca, m.x, Componente.SERVICO)
        semear(m, origem, "10.00")
        return T.FINANCIAMENTO_DE_OBRIGACAO, origem, obrigacao, "10.00"
    if numero == 9:
        origem = obrigacao_de(m.fa, m.ra)
        semear(m, origem, "10.00")
        return T.FINANCIAMENTO_DE_OBRIGACAO, origem, obrigacao, "10.00"
    if numero == 10:
        origem = frete_de(m.ra)
        semear(m, origem, "10.00")
        return T.FINANCIAMENTO_DE_OBRIGACAO, origem, obrigacao, "10.00"
    if numero == 11:
        origem = reserva()
        semear(m, origem, "10.00")
        return T.COBERTURA_DE_DESPESA, origem, despesas(), "10.00"
    if numero == 12:
        origem = obrigacao_de(m.fa, m.ra)
        semear(m, origem, "10.00")
        return T.REPASSE, origem, EXTERIOR, "10.00"
    if numero == 13:
        origem = receita_de(m.ra)
        semear(m, origem, "10.00")
        return T.RETIRADA_DE_RECEITA, origem, EXTERIOR, "10.00"
    if numero == 14:
        origem = frete_de(m.ra)
        semear(m, origem, "10.00")
        return T.PAGAMENTO_DO_FRETE, origem, EXTERIOR, "10.00"
    assert numero == 15
    semear(m, obrigacao, "10.00")
    return T.DEVOLUCAO, obrigacao, EXTERIOR, "10.00"


@pytest.mark.acceptance
@pytest.mark.parametrize("numero", range(1, 16))
def test_todos_os_fluxos_da_lista_sao_aceitos(m: Mundo, numero: int) -> None:  # A-8
    tipo, origem, destino, valor = _fluxo(m, numero)
    antes = [(c, saldo(c)) for c in (origem, destino) if isinstance(c, ContaFinanceira)]
    movimento = mover(tipo, origem, destino, valor)
    for conta_, anterior in antes:
        sinal = -1 if conta_ is origem else 1
        assert saldo(conta_) == anterior + sinal * D(valor)
    assert movimento.transferencias.count() == 1


@pytest.mark.parametrize(
    ("origem", "destino"),
    [("receita", "despesas"), ("receita", "frete"), ("receita", "obrigacao"), ("reserva", "frete")],
)
def test_receita_e_reserva_cobrem_despesa_frete_e_obrigacao(
    m: Mundo, origem: str, destino: str
) -> None:  # F11
    de = {"receita": receita_de(m.ra), "reserva": reserva()}[origem]
    para = {
        "despesas": despesas(),
        "frete": frete_de(m.rb),
        "obrigacao": obrigacao_com(m.rb, m.cb, m.y),
    }[destino]
    semear(m, de, "10.00")
    tipo = T.COBERTURA_DE_DESPESA if destino != "obrigacao" else T.FINANCIAMENTO_DE_OBRIGACAO
    mover(tipo, de, para, "4.00")
    assert saldo(de) == D("6.00")
    assert saldo(para) == D("4.00")


def test_saldo_insuficiente_nao_grava_nada(m: Mundo) -> None:  # A-9
    receita = receita_de(m.ra)
    semear(m, receita, "10.00")
    semear(m, reserva(), "100.00")
    antes = _estado()
    with pytest.raises(SaldoInsuficiente):
        mover(T.RETIRADA_DE_RECEITA, receita, EXTERIOR, "10.01")
    assert _estado() == antes
    with pytest.raises(SaldoInsuficiente):
        lancar(
            tipo=T.COBERTURA_DE_DESPESA,
            transferencias=[
                Transferencia(reserva(), despesas(), D("5.00")),
                Transferencia(receita, despesas(), D("10.01")),
            ],
            autor=SISTEMA,
            justificativa="teste",
            origem=m.ra,
            chave=chave_nova(),
        )
    assert _estado() == antes


def test_despesas_a_cobrir_e_o_unico_saldo_que_fica_negativo(m: Mundo) -> None:  # A-10
    assert saldo(despesas()) == D("0.00")
    mover(T.TARIFA, despesas(), EXTERIOR, "1.50")
    assert saldo(despesas()) == D("-1.50")
    assert saldo_total_esperado() == D("-1.50")


def _movimento_com(
    m: Mundo,
    valor: object = D("1.00"),
    *,
    de: Any = EXTERIOR,
    autor: Any = SISTEMA,
    justificativa: str = "teste",
    transferencias: list[Transferencia] | None = None,
) -> Any:
    destino = custodia(m.ra, m.ca, m.x)
    return lancar(
        tipo=T.ENTRADA_DE_PAGAMENTO,
        transferencias=(
            transferencias
            if transferencias is not None
            else [Transferencia(de, destino, cast(Decimal, valor))]
        ),
        autor=autor,
        justificativa=justificativa,
        origem=m.ra,
        chave=chave_nova(),
    )


@pytest.mark.parametrize(
    "valor", [D("0"), D("-1.00"), D("1.001"), 1.5], ids=["zero", "negativo", "tres_casas", "float"]
)
def test_valor_invalido_e_recusado(m: Mundo, valor: object) -> None:  # A-11
    antes = _estado()
    with pytest.raises(MovimentoInvalido) as erro:
        _movimento_com(m, valor)
    assert erro.value.codigo == "valor"
    assert _estado() == antes


def test_transferencias_invalidas_sao_recusadas(m: Mundo) -> None:  # A-11
    produtos = custodia(m.ra, m.ca, m.x)
    outra = receita_de(m.ra)
    antes = _estado()
    casos = {
        "de_igual_a_para": [Transferencia(produtos, produtos, D("1.00"))],
        "lista_vazia": [],
        "dois_exteriores": [Transferencia(EXTERIOR, EXTERIOR, D("1.00"))],
        "dois_sentidos": [
            Transferencia(produtos, outra, D("1.00")),
            Transferencia(outra, produtos, D("1.00")),
        ],
    }
    for nome, transferencias in casos.items():
        with pytest.raises(MovimentoInvalido) as erro:
            _movimento_com(m, transferencias=transferencias)
        assert erro.value.codigo == "transferencias", nome
    assert _estado() == antes


@pytest.mark.parametrize("justificativa", ["", "   "])
def test_administrador_exige_justificativa(m: Mundo, justificativa: str) -> None:  # A-11
    antes = _estado()
    with pytest.raises(MovimentoInvalido) as erro:
        _movimento_com(m, autor=m.admin, justificativa=justificativa)
    assert erro.value.codigo == "justificativa"
    assert _estado() == antes
    assert EntradaAuditoria.objects.filter(acao="financeiro.movimento").count() == 0


def test_repetir_a_chave_devolve_o_mesmo_movimento(m: Mundo) -> None:  # A-12
    produtos = custodia(m.ra, m.ca, m.x)

    def lancar_com(valor: str) -> MovimentoFinanceiro:
        return lancar(
            tipo=T.ENTRADA_DE_PAGAMENTO,
            transferencias=[Transferencia(EXTERIOR, produtos, D(valor))],
            autor=SISTEMA,
            justificativa="teste",
            origem=m.ra,
            chave="k",
        )

    primeiro = lancar_com("100.00")
    antes = _estado()
    segundo = lancar_com("100.00")
    assert segundo.pk == primeiro.pk
    assert _estado() == antes
    with pytest.raises(MovimentoConflitante):
        lancar_com("101.00")
    assert _estado() == antes


def test_repetir_a_retirada_nao_exige_saldo_de_novo(m: Mundo) -> None:  # A-12, idempotência
    receita = receita_de(m.ra)
    semear(m, receita, "10.00")
    primeiro = mover(T.RETIRADA_DE_RECEITA, receita, EXTERIOR, "10.00", chave="retirada:1")
    segundo = mover(T.RETIRADA_DE_RECEITA, receita, EXTERIOR, "10.00", chave="retirada:1")
    assert segundo.pk == primeiro.pk
    assert saldo(receita) == D("0.00")


def test_movimento_do_administrador_guarda_autor_e_auditoria(m: Mundo) -> None:  # A-13
    semear(m, reserva(), "100.00")
    movimento = mover(
        T.COBERTURA_DE_DESPESA,
        reserva(),
        despesas(),
        "30.00",
        autor=m.admin,
        justificativa="Cobertura da tarifa de outubro",
    )
    movimento.refresh_from_db()
    assert (movimento.autor_tipo, movimento.autor_id) == ("usuario", str(m.admin.pk))
    assert movimento.justificativa == "Cobertura da tarifa de outubro"
    (entrada,) = EntradaAuditoria.objects.filter(acao="financeiro.movimento")
    assert entrada.autor_id == str(m.admin.pk)
    assert entrada.alteracoes["tipo"] == T.COBERTURA_DE_DESPESA
    assert D(str(entrada.alteracoes["valor"])) == D("30.00")
    assert sorted(entrada.alteracoes["contas"]) == ["despesas_a_cobrir:unica", "reserva:unica"]
    assert m.admin.email_normalizado not in str(entrada.alteracoes)
    assert m.admin.nome not in str(entrada.alteracoes)
    assert (entrada.objeto_tipo, entrada.objeto_id) == (
        "financeiro.movimentofinanceiro",
        str(movimento.pk),
    )


def test_movimento_do_sistema_nao_grava_auditoria(m: Mundo) -> None:
    semear(m, reserva(), "10.00")
    assert EntradaAuditoria.objects.filter(acao="financeiro.movimento").count() == 0


@pytest.mark.django_db(transaction=True)
def test_lancar_fora_de_transacao_e_recusado() -> None:  # A-17
    mundo = montar_mundo()
    produtos = custodia(mundo.ra, mundo.ca, mundo.x)
    assert not connection.in_atomic_block
    with pytest.raises(TransactionManagementError):
        lancar(
            tipo=T.ENTRADA_DE_PAGAMENTO,
            transferencias=[Transferencia(EXTERIOR, produtos, D("1.00"))],
            autor=SISTEMA,
            justificativa="teste",
            origem=mundo.ra,
            chave="fora",
        )
    assert MovimentoFinanceiro.objects.count() == 0


def test_saldo_total_esperado_ate_um_instante(m: Mundo, relogio: RelogioControlado) -> None:  # A-18
    dez = T0
    relogio.congelar(dez)
    mover(T.ENTRADA_DE_PAGAMENTO, EXTERIOR, custodia(m.ra, m.ca, m.x), "125.00")
    relogio.congelar(dez + timedelta(hours=2))
    mover(T.APORTE, EXTERIOR, reserva(), "1000.00")
    assert saldo_total_esperado(ate=dez + timedelta(hours=1)) == D("125.00")
    assert saldo_total_esperado() == D("1125.00")


def test_extrato_lista_as_transferencias_da_conta_com_o_saldo_acumulado(m: Mundo) -> None:
    caixa = reserva()
    a = mover(T.APORTE, EXTERIOR, caixa, "100.00", chave="aporte:a")
    b = mover(T.COBERTURA_DE_DESPESA, caixa, despesas(), "30.00", chave="cobertura:b")
    c = mover(T.APORTE, EXTERIOR, caixa, "5.00", chave="aporte:c")
    mover(T.TARIFA, despesas(), EXTERIOR, "1.00", chave="tarifa:d")  # outra conta
    linhas = extrato(caixa)
    assert [(linha.movimento.pk, linha.valor, linha.saldo) for linha in linhas] == [
        (a.pk, D("100.00"), D("100.00")),
        (b.pk, D("-30.00"), D("70.00")),
        (c.pk, D("5.00"), D("75.00")),
    ]


# --- Correção E09-R02: a guarda da ordem das travas (A-19 e A-20) -------------------------------


@dataclass
class TresContas:
    c1: ContaFinanceira
    c2: ContaFinanceira
    c3: ContaFinanceira


def _tres_contas() -> TresContas:
    """Três contas criadas nesta ordem (`pk` crescente), com saldo: reserva, receita e despesas."""
    mundo = montar_mundo()
    with transaction.atomic():
        c1, c2, c3 = reserva(), receita_de(mundo.ra), despesas()
    for destino in (c1, c2):  # cada saldo na sua transação, como em produção
        with transaction.atomic():
            semear(mundo, destino, "100.00")
    assert c1.pk < c2.pk < c3.pk
    return TresContas(c1, c2, c3)


def _estado_das_tres(t: TresContas) -> tuple[int, list[Decimal]]:
    return MovimentoFinanceiro.objects.count(), [saldo(c) for c in (t.c1, t.c2, t.c3)]


def _cobertura(origem: ContaFinanceira, destino: ContaFinanceira, chave: str) -> Any:
    return lancar(
        tipo=T.COBERTURA_DE_DESPESA,
        transferencias=[Transferencia(origem, destino, D("1.00"))],
        autor=SISTEMA,
        justificativa="teste",
        origem=origem,
        chave=chave,
    )


@pytest.mark.django_db(transaction=True)
def test_travar_fora_de_ordem_e_recusado_antes_de_travar() -> None:  # A-19, E09-R02
    t = _tres_contas()
    antes = _estado_das_tres(t)
    with transaction.atomic():
        _travar_conta(t.c3.pk)
        with pytest.raises(OrdemDeTravasViolada):
            _travar_conta(t.c1.pk)
    with transaction.atomic():
        _travar_conta(t.c2.pk)
        with pytest.raises(OrdemDeTravasViolada):
            _cobertura(t.c1, t.c3, "guarda-1")  # o `lancar` precisaria travar c1 depois de c2
    assert _estado_das_tres(t) == antes


@pytest.mark.django_db(transaction=True)
def test_travar_de_novo_e_o_registro_recomeca_em_cada_transacao() -> None:  # A-20, E09-R02
    t = _tres_contas()
    with transaction.atomic():
        for conta_ in (t.c1, t.c3, t.c1):
            _travar_conta(conta_.pk)  # travar de novo uma conta já travada é permitido
    with transaction.atomic():
        lancar(
            tipo=T.COBERTURA_DE_DESPESA,
            transferencias=[
                Transferencia(t.c2, t.c3, D("1.00")),
                Transferencia(t.c1, t.c3, D("1.00")),
            ],
            autor=SISTEMA,
            justificativa="teste",
            origem=t.c1,
            chave="guarda-2",
        )  # as transferências em qualquer ordem: o `lancar` ordena
    with transaction.atomic():
        lancar(
            tipo=T.COBERTURA_DE_DESPESA,
            transferencias=[
                Transferencia(t.c1, t.c3, D("1.00")),
                Transferencia(t.c2, t.c3, D("1.00")),
            ],
            autor=SISTEMA,
            justificativa="teste",
            origem=t.c1,
            chave="guarda-3",
        )
    with transaction.atomic():
        _travar_conta(t.c3.pk)
    with transaction.atomic():  # depois de um commit, o registro começa vazio
        _travar_conta(t.c1.pk)
    with pytest.raises(RuntimeError):  # noqa: PT012
        with transaction.atomic():
            _travar_conta(t.c3.pk)
            raise RuntimeError("desfaz a transação")
    with transaction.atomic():  # depois de um rollback, também
        _travar_conta(t.c1.pk)


# --- Correção E09-R10: o registro da guarda segue as travas retidas (A-22 a A-27) --------------


def _menor_e_maior() -> tuple[ContaFinanceira, ContaFinanceira]:
    """Duas contas do livro com `menor.pk < maior.pk`, conferido aqui."""
    menor = conta(Destinacao.RESERVA)
    maior = conta(Destinacao.DESPESAS_A_COBRIR)
    assert menor.pk < maior.pk
    return menor, maior


def _outra_conexao_trava(conta_: ContaFinanceira) -> bool:
    """Uma outra conexão consegue travar a conta em 500 ms? (a trava não está retida)"""
    import threading

    resultado: list[bool] = []

    def tenta() -> None:
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '500ms'")
                ContaFinanceira.objects.select_for_update().get(pk=conta_.pk)
            resultado.append(True)
        except DatabaseError:
            resultado.append(False)
        finally:
            connection.close()

    fio = threading.Thread(target=tenta)
    fio.start()
    fio.join(20)
    return resultado == [True]


@pytest.mark.django_db(transaction=True)
def test_o_mesmo_objeto_atomic_reutilizado_recomeca_o_registro() -> None:  # A-22, E09-R10
    menor, maior = _menor_e_maior()
    escopo = transaction.atomic()
    with escopo:
        _travar_conta(maior.pk)
    with escopo:
        _travar_conta(menor.pk)  # a segunda execução não herda a trava da primeira
    with pytest.raises(RuntimeError):  # noqa: PT012
        with escopo:
            _travar_conta(maior.pk)
            raise RuntimeError("desfaz a transação")
    with escopo:
        _travar_conta(menor.pk)


@pytest.mark.django_db(transaction=True)
def test_o_objeto_atomic_reutilizado_continua_guardando_a_ordem() -> None:  # A-23, E09-R10
    menor, maior = _menor_e_maior()
    escopo = transaction.atomic()
    with escopo:
        _travar_conta(menor.pk)
        _travar_conta(maior.pk)
    with escopo:
        _travar_conta(maior.pk)
        with pytest.raises(OrdemDeTravasViolada):
            _travar_conta(menor.pk)


@pytest.mark.django_db(transaction=True)
def test_funcao_decorada_com_atomic_recomeca_o_registro_a_cada_chamada() -> None:  # A-24, E09-R10
    menor, maior = _menor_e_maior()

    @transaction.atomic
    def travar(*contas: ContaFinanceira) -> None:
        for c in contas:
            _travar_conta(c.pk)

    travar(maior)
    travar(menor)  # (i) duas chamadas aceitas
    travar(menor, maior)
    with pytest.raises(OrdemDeTravasViolada):  # (ii) a segunda chamada recusa
        travar(maior, menor)


@pytest.mark.django_db(transaction=True)
def test_trava_desfeita_por_savepoint_nao_conta_mas_a_ordem_segue_guardada() -> None:  # A-25
    menor, maior = _menor_e_maior()
    with transaction.atomic():
        with pytest.raises(RuntimeError):  # noqa: PT012
            with transaction.atomic():
                _travar_conta(menor.pk)
                raise RuntimeError("desfaz o savepoint")
        assert _outra_conexao_trava(menor)  # a trava não está retida
        _travar_conta(maior.pk)
        with pytest.raises(OrdemDeTravasViolada):
            _travar_conta(menor.pk)


@pytest.mark.django_db(transaction=True)
def test_trava_liberada_pelo_savepoint_desfeito_pode_ser_pedida_depois() -> None:  # A-26
    menor, maior = _menor_e_maior()
    with transaction.atomic():
        with pytest.raises(RuntimeError):  # noqa: PT012
            with transaction.atomic():
                _travar_conta(maior.pk)
                raise RuntimeError("desfaz o savepoint")
        _travar_conta(menor.pk)
        _travar_conta(maior.pk)
    with transaction.atomic():  # aninhado: o de dentro trava e o de fora é desfeito
        with pytest.raises(RuntimeError):  # noqa: PT012
            with transaction.atomic():
                with transaction.atomic():
                    _travar_conta(maior.pk)
                raise RuntimeError("desfaz o savepoint de fora")
        _travar_conta(menor.pk)
        _travar_conta(maior.pk)


@pytest.mark.django_db(transaction=True)
def test_savepoint_liberado_mantem_a_trava_no_registro() -> None:  # A-27 (i)
    menor, maior = _menor_e_maior()
    with transaction.atomic():
        with transaction.atomic():
            _travar_conta(maior.pk)
        with pytest.raises(OrdemDeTravasViolada):
            _travar_conta(menor.pk)


@pytest.mark.django_db(transaction=True)
def test_savepoint_desfeito_nao_libera_a_trava_anterior() -> None:  # A-27 (ii)
    menor, maior = _menor_e_maior()
    with transaction.atomic():
        _travar_conta(maior.pk)
        with pytest.raises(RuntimeError):  # noqa: PT012
            with transaction.atomic():
                _travar_conta(maior.pk)
                raise RuntimeError("desfaz o savepoint")
        with pytest.raises(OrdemDeTravasViolada):
            _travar_conta(menor.pk)


class TestGuardaNoTestCase(DjangoTestCase):  # A-27 (iii)
    def test_o_mesmo_escopo_usado_duas_vezes_no_testcase(self) -> None:
        menor, maior = _menor_e_maior()
        escopo = transaction.atomic()
        with escopo:
            _travar_conta(maior.pk)
        with escopo:
            _travar_conta(menor.pk)  # A-22: a segunda execução começa vazia
        with escopo:
            _travar_conta(menor.pk)
            _travar_conta(maior.pk)
        with escopo:  # A-23: o registro vale dentro da execução
            _travar_conta(maior.pk)
            with pytest.raises(OrdemDeTravasViolada):
                _travar_conta(menor.pk)

    # --- Correção E09-R10 residual: `savepoint=False` sob o `TestCase` (A-28 a A-30) ------------

    def test_atomic_sem_savepoint_reutilizado_nao_herda_o_registro(self) -> None:  # A-28
        menor, maior = _menor_e_maior()
        escopo = transaction.atomic(savepoint=False)
        with escopo:
            _travar_conta(maior.pk)
        with escopo:
            _travar_conta(menor.pk)

    def test_atomic_sem_savepoint_fica_fora_da_guarda(self) -> None:  # A-29
        menor, maior = _menor_e_maior()
        with transaction.atomic(savepoint=False):  # (i) maior e depois menor, no mesmo bloco
            _travar_conta(maior.pk)
            _travar_conta(menor.pk)
        with transaction.atomic(savepoint=False):  # (ii) dois blocos seguidos
            _travar_conta(maior.pk)
        with transaction.atomic(savepoint=False):
            _travar_conta(menor.pk)

    def test_atomic_padrao_dentro_de_sem_savepoint_e_o_escopo_da_guarda(self) -> None:  # A-30
        menor, maior = _menor_e_maior()
        with transaction.atomic(savepoint=False):
            with transaction.atomic():
                _travar_conta(maior.pk)
                with pytest.raises(OrdemDeTravasViolada):
                    _travar_conta(menor.pk)


@pytest.mark.django_db(transaction=True)
def test_atomic_sem_savepoint_em_transacao_real_segue_a_execucao() -> None:  # A-31 (i)
    menor, maior = _menor_e_maior()
    escopo = transaction.atomic(savepoint=False)
    with escopo:
        _travar_conta(maior.pk)
    with escopo:
        _travar_conta(menor.pk)
    with escopo:
        _travar_conta(maior.pk)
        with pytest.raises(OrdemDeTravasViolada):
            _travar_conta(menor.pk)


@pytest.mark.django_db(transaction=True)
def test_atomic_sem_savepoint_dentro_de_savepoint_desfeito_libera_a_trava() -> None:  # A-31 (ii)
    menor, maior = _menor_e_maior()
    with transaction.atomic():
        with pytest.raises(RuntimeError):  # noqa: PT012
            with transaction.atomic():
                with transaction.atomic(savepoint=False):
                    _travar_conta(maior.pk)
                raise RuntimeError("desfaz o savepoint de fora")
        _travar_conta(menor.pk)
        _travar_conta(maior.pk)
