"""Livro-razão: o serviço `lancar` e as consultas (E09-01).

Um movimento é um conjunto de transferências `(de, para, valor)` que acontece inteiro ou não
acontece. O saldo de uma conta é o que entrou nela menos o que saiu. A P-2 fica garantida por uma
lista fechada de fluxos permitidos: o que não está na lista é recusado, mesmo que o chamador erre.

Ordem das travas: as da E08 (o pagamento no provedor, a situação do pedido e a tentativa) vêm
antes; as contas do livro-razão são travadas por último.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import connection
from django.db.models import Sum
from django.db.transaction import TransactionManagementError

from apps.contas.models import Conta
from apps.financeiro.models import (
    Componente,
    ContaFinanceira,
    Destinacao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeMovimento,
    TransferenciaFinanceira,
)
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora
from apps.nucleo.valores import ValorInvalido, dinheiro
from apps.rodadas.models import Rodada

ZERO = Decimal("0.00")


class MovimentoProibido(Exception):
    """O fluxo não está na lista do que é permitido (P-2)."""


class SaldoInsuficiente(Exception):
    """O movimento deixaria uma conta com saldo negativo."""


class MovimentoInvalido(Exception):
    """O movimento está mal formado; `codigo` diz o quê."""

    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


class OrdemDeTravasViolada(Exception):
    """Uma conta foi pedida fora da ordem crescente de `pk` na mesma transação (E09-R02)."""


class MovimentoConflitante(Exception):
    """A chave já existe com outro conteúdo."""


class _Exterior:
    def __repr__(self) -> str:
        return "EXTERIOR"


EXTERIOR = _Exterior()
Ponta = ContaFinanceira | _Exterior


@dataclass(frozen=True)
class Transferencia:
    de: Ponta
    para: Ponta
    valor: Decimal


@dataclass(frozen=True)
class LinhaDoExtrato:
    movimento: MovimentoFinanceiro
    valor: Decimal  # com sinal: positivo entrou na conta, negativo saiu
    saldo: Decimal  # o saldo da conta logo depois desta linha


# --- contas ----------------------------------------------------------------------------------


def _pk(valor: Any) -> int:
    return int(valor.pk if hasattr(valor, "pk") else valor)


# destinação → chaves obrigatórias (as opcionais da obrigação são só dados da conta)
_CHAVES: dict[str, tuple[str, ...]] = {
    Destinacao.CUSTODIA: ("rodada", "ciclo", "comprador", "componente"),
    Destinacao.OBRIGACAO_FORNECEDOR: ("fornecedor", "rodada"),
    Destinacao.FRETE: ("rodada",),
    Destinacao.RECEITA_SERVICO: ("rodada",),
    Destinacao.OBRIGACAO_COMPRADOR: ("obrigacao",),
    Destinacao.RESERVA: (),
    Destinacao.DESPESAS_A_COBRIR: (),
}
_OPCIONAIS_DA_OBRIGACAO = ("rodada", "ciclo", "comprador")


def conta(destinacao: str, **chave: Any) -> ContaFinanceira:
    """Cria a conta no primeiro uso e a devolve nos seguintes."""
    if destinacao not in _CHAVES:
        raise ValueError(f"destinação desconhecida: {destinacao!r}")
    obrigatorias = _CHAVES[destinacao]
    aceitas = set(obrigatorias)
    if destinacao == Destinacao.OBRIGACAO_COMPRADOR:
        aceitas |= set(_OPCIONAIS_DA_OBRIGACAO)
    if not set(obrigatorias) <= set(chave) or not set(chave) <= aceitas:
        raise ValueError(f"chave da conta {destinacao}: esperado {sorted(obrigatorias)}")
    campos: dict[str, Any] = {}
    for nome, valor in chave.items():
        if nome == "componente":
            campos["componente"] = Componente(valor).value
        elif nome == "obrigacao":
            campos["obrigacao"] = _pk(valor)
        elif valor is not None:
            campos[f"{nome}_id"] = _pk(valor)
    if destinacao == Destinacao.CUSTODIA:
        texto = (
            f"r{campos['rodada_id']}:c{campos['ciclo_id']}:b{campos['comprador_id']}:"
            f"{campos['componente']}"
        )
    elif destinacao == Destinacao.OBRIGACAO_FORNECEDOR:
        texto = f"f{campos['fornecedor_id']}:r{campos['rodada_id']}"
    elif destinacao in (Destinacao.FRETE, Destinacao.RECEITA_SERVICO):
        texto = f"r{campos['rodada_id']}"
    elif destinacao == Destinacao.OBRIGACAO_COMPRADOR:
        texto = f"o{campos['obrigacao']}"
    else:
        texto = "unica"
    encontrada, _ = ContaFinanceira.objects.get_or_create(
        destinacao=destinacao, chave=texto, defaults=campos
    )
    return encontrada


# --- a lista fechada de fluxos permitidos -----------------------------------------------------

T = TipoDeMovimento
D = Destinacao

_DO_EXTERIOR = {
    (T.ENTRADA_DE_PAGAMENTO, D.CUSTODIA),
    (T.ENTRADA_PARA_DEVOLUCAO, D.OBRIGACAO_COMPRADOR),
    (T.APORTE, D.RESERVA),
}
_PARA_O_EXTERIOR = {
    (T.TARIFA, D.DESPESAS_A_COBRIR),
    (T.REPASSE, D.OBRIGACAO_FORNECEDOR),
    (T.RETIRADA_DE_RECEITA, D.RECEITA_SERVICO),
    (T.PAGAMENTO_DO_FRETE, D.FRETE),
    (T.DEVOLUCAO, D.OBRIGACAO_COMPRADOR),
}
_COBERTURAS = (T.COBERTURA_DE_DESPESA, T.FINANCIAMENTO_DE_OBRIGACAO)


def _apuracao_permitida(de: ContaFinanceira, para: ContaFinanceira) -> bool:
    """F5, F6 e F7: a custódia vai para o destino do componente, na mesma rodada."""
    if para.rodada_id != de.rodada_id:
        return False
    if de.rodada_id is None:
        return False
    if de.componente == Componente.PRODUTOS:
        fornecedor_da_rodada = Rodada.objects.values_list("fornecedor_id", flat=True).get(
            pk=de.rodada_id
        )
        return (
            para.destinacao == D.OBRIGACAO_FORNECEDOR and para.fornecedor_id == fornecedor_da_rodada
        )
    if de.componente == Componente.SERVICO:
        return para.destinacao == D.RECEITA_SERVICO
    return para.destinacao == D.FRETE


def _financiamento_permitido(de: ContaFinanceira, para: ContaFinanceira) -> bool:
    """F8, F9 e F10: a obrigação com comprador é financiada pelo que é da mesma rodada."""
    if para.destinacao != D.OBRIGACAO_COMPRADOR:
        return False
    if de.destinacao == D.CUSTODIA:
        return (
            para.rodada_id == de.rodada_id
            and para.ciclo_id == de.ciclo_id
            and para.comprador_id == de.comprador_id
        )
    return para.rodada_id == de.rodada_id


def _permitido(tipo: str, de: Ponta, para: Ponta) -> bool:
    if isinstance(de, _Exterior):
        return isinstance(para, ContaFinanceira) and (tipo, para.destinacao) in _DO_EXTERIOR
    if isinstance(para, _Exterior):
        return (tipo, de.destinacao) in _PARA_O_EXTERIOR
    if tipo == T.APURACAO:
        return de.destinacao == D.CUSTODIA and _apuracao_permitida(de, para)
    livres = de.destinacao in (D.RECEITA_SERVICO, D.RESERVA) and tipo in _COBERTURAS
    if livres:
        return para.destinacao in (D.DESPESAS_A_COBRIR, D.FRETE, D.OBRIGACAO_COMPRADOR)
    if tipo == T.FINANCIAMENTO_DE_OBRIGACAO and de.destinacao in (
        D.CUSTODIA,
        D.OBRIGACAO_FORNECEDOR,
        D.FRETE,
    ):
        return _financiamento_permitido(de, para)
    return False


# --- validação -------------------------------------------------------------------------------


def _validar(transferencias: list[Transferencia]) -> list[Transferencia]:
    if not transferencias:
        raise MovimentoInvalido("transferencias")
    validas: list[Transferencia] = []
    for item in transferencias:
        if not isinstance(item.valor, Decimal):
            raise MovimentoInvalido("valor")
        try:
            valor = dinheiro(item.valor)
        except ValorInvalido:
            raise MovimentoInvalido("valor") from None
        if valor <= 0:
            raise MovimentoInvalido("valor")
        if item.de is item.para or (
            isinstance(item.de, ContaFinanceira)
            and isinstance(item.para, ContaFinanceira)
            and item.de.pk == item.para.pk
        ):
            raise MovimentoInvalido("transferencias")
        validas.append(Transferencia(item.de, item.para, valor))
    pares = {(_id(t.de), _id(t.para)) for t in validas}
    if any((para, de) in pares for de, para in pares):
        raise MovimentoInvalido("transferencias")
    return validas


def _id(ponta: Ponta) -> int | None:
    return None if isinstance(ponta, _Exterior) else ponta.pk


def _contas_de(transferencias: list[Transferencia]) -> list[ContaFinanceira]:
    vistas: dict[int, ContaFinanceira] = {}
    for item in transferencias:
        for ponta in (item.de, item.para):
            if isinstance(ponta, ContaFinanceira):
                vistas.setdefault(ponta.pk, ponta)
    return [vistas[pk] for pk in sorted(vistas)]  # ordem global de trava: pk crescente


def _conteudo(transferencias: list[Transferencia]) -> list[tuple[int | None, int | None, Decimal]]:
    return sorted(
        ((_id(t.de), _id(t.para), t.valor) for t in transferencias),
        key=lambda c: (c[0] or 0, c[1] or 0, c[2]),
    )


def _existente(
    chave: str, tipo: str, origem_tipo: str, origem_id: str, transferencias: list[Transferencia]
) -> MovimentoFinanceiro | None:
    movimento: MovimentoFinanceiro | None = MovimentoFinanceiro.objects.filter(chave=chave).first()
    if movimento is None:
        return None
    gravadas = sorted(
        ((t.de_id, t.para_id, t.valor) for t in movimento.transferencias.all()),
        key=lambda c: (c[0] or 0, c[1] or 0, c[2]),
    )
    if (
        movimento.tipo != tipo
        or (movimento.origem_tipo, movimento.origem_id) != (origem_tipo, origem_id)
        or gravadas != _conteudo(transferencias)
    ):
        raise MovimentoConflitante(f"a chave {chave!r} já existe com outro conteúdo")
    return movimento


# --- o lançamento ----------------------------------------------------------------------------


def lancar(
    *,
    tipo: str,
    transferencias: list[Transferencia],
    autor: Any,
    justificativa: str,
    origem: Any,
    chave: str,
) -> MovimentoFinanceiro:
    """Grava o movimento inteiro ou não grava nada. Exige transação aberta."""
    if not connection.in_atomic_block:
        raise TransactionManagementError("lancar exige uma transação aberta.")
    validas = _validar(transferencias)
    if autor is SISTEMA:
        autor_tipo, autor_id = MovimentoFinanceiro.AutorTipo.SISTEMA, None
    elif isinstance(autor, Conta) and autor.pk is not None:
        autor_tipo, autor_id = MovimentoFinanceiro.AutorTipo.USUARIO, str(autor.pk)
    else:
        raise ValueError("autor inválido: informe uma conta salva ou SISTEMA")
    if not justificativa or not justificativa.strip():
        raise MovimentoInvalido("justificativa")
    for numero, item in enumerate(validas, start=1):
        if not _permitido(tipo, item.de, item.para):
            raise MovimentoProibido(
                f"fluxo_nao_permitido: transferência {numero} de {_nome(item.de)} "
                f"para {_nome(item.para)} no tipo {tipo}"
            )
    origem_tipo, origem_id = origem._meta.label_lower, str(origem.pk)
    contas = _contas_de(validas)
    for c in contas:
        _travar_conta(c.pk)
    existente = _existente(chave, tipo, origem_tipo, origem_id, validas)
    if existente is not None:
        return existente
    variacao: dict[int, Decimal] = {}
    for item in validas:
        if isinstance(item.de, ContaFinanceira):
            variacao[item.de.pk] = variacao.get(item.de.pk, ZERO) - item.valor
        if isinstance(item.para, ContaFinanceira):
            variacao[item.para.pk] = variacao.get(item.para.pk, ZERO) + item.valor
    for c in contas:
        if saldo(c) + variacao[c.pk] < 0 and c.destinacao != D.DESPESAS_A_COBRIR:
            raise SaldoInsuficiente(f"{c.destinacao}:{c.chave}")
    movimento = MovimentoFinanceiro.objects.create(
        tipo=tipo,
        autor_tipo=autor_tipo,
        autor_id=autor_id,
        momento=agora(),
        justificativa=justificativa,
        origem_tipo=origem_tipo,
        origem_id=origem_id,
        chave=chave,
    )
    for item in validas:
        TransferenciaFinanceira.objects.create(
            movimento=movimento,
            de=item.de if isinstance(item.de, ContaFinanceira) else None,
            para=item.para if isinstance(item.para, ContaFinanceira) else None,
            valor=item.valor,
        )
    if autor_tipo == MovimentoFinanceiro.AutorTipo.USUARIO:
        registrar_auditoria(
            autor,
            "financeiro.movimento",
            movimento,
            {
                "tipo": tipo,
                "valor": sum((t.valor for t in validas), ZERO),
                "contas": [str(c) for c in contas],
            },
            motivo=justificativa,
        )
    return movimento


def _nome(ponta: Ponta) -> str:
    return "exterior" if isinstance(ponta, _Exterior) else str(ponta.destinacao)


# --- consultas -------------------------------------------------------------------------------


def saldo(conta: ContaFinanceira) -> Decimal:
    entrou = TransferenciaFinanceira.objects.filter(para=conta).aggregate(s=Sum("valor"))["s"]
    saiu = TransferenciaFinanceira.objects.filter(de=conta).aggregate(s=Sum("valor"))["s"]
    return (entrou or ZERO) - (saiu or ZERO)


def extrato(conta: ContaFinanceira) -> list[LinhaDoExtrato]:
    """As transferências da conta, em ordem de movimento, com o saldo depois de cada uma."""
    linhas: list[LinhaDoExtrato] = []
    acumulado = ZERO
    transferencias = (
        (
            TransferenciaFinanceira.objects.filter(de=conta)
            | TransferenciaFinanceira.objects.filter(para=conta)
        )
        .select_related("movimento")
        .order_by("movimento__pk", "pk")
    )
    for t in transferencias:
        valor = t.valor if t.para_id == conta.pk else -t.valor
        acumulado += valor
        linhas.append(LinhaDoExtrato(t.movimento, valor, acumulado))
    return linhas


def saldo_total_esperado(ate: datetime | None = None) -> Decimal:
    """A soma dos saldos de todas as contas: o que entrou do exterior menos o que saiu para ele,
    só com os movimentos de momento até `ate`, quando informado."""
    filtro = {} if ate is None else {"movimento__momento__lte": ate}
    entrou = TransferenciaFinanceira.objects.filter(de__isnull=True, **filtro).aggregate(
        s=Sum("valor")
    )["s"]
    saiu = TransferenciaFinanceira.objects.filter(para__isnull=True, **filtro).aggregate(
        s=Sum("valor")
    )["s"]
    return (entrou or ZERO) - (saiu or ZERO)


def conta_da_obrigacao(obrigacao: ObrigacaoComComprador) -> ContaFinanceira:
    """A conta `obrigacao_comprador(o)`, criada se ainda não existir."""
    return conta(
        D.OBRIGACAO_COMPRADOR,
        obrigacao=obrigacao.pk,
        rodada=obrigacao.rodada_id,
        ciclo=obrigacao.ciclo_id,
        comprador=obrigacao.comprador_id,
    )


def _escopo_da_transacao() -> object | None:
    """O bloco `atomic` mais externo que não é o do caso de teste: a transação das travas. No
    `TestCase` o único bloco é o do próprio teste, que nunca termina; sem transação própria, não
    há ordem a guardar."""
    for bloco in connection.atomic_blocks:
        if not getattr(bloco, "_from_testcase", False):
            return bloco
    return None


def _travadas_da_transacao() -> set[int] | None:
    """As contas que a transação mais externa já travou; começa vazio em cada transação nova,
    depois de um commit ou de um rollback."""
    escopo = _escopo_da_transacao()
    if escopo is None:
        return None
    atual = getattr(connection, "_travas_do_financeiro", None)
    if atual is None or atual[0] is not escopo:
        atual = (escopo, set())
        connection._travas_do_financeiro = atual  # type: ignore[attr-defined]
    travadas: set[int] = atual[1]
    return travadas


def _travar_conta(pk: int) -> ContaFinanceira:
    """O único caminho de trava das contas do livro-razão. A guarda da ordem (E09-R02): pedir uma
    conta de `pk` menor que a maior já travada na transação é um erro de programação, e levanta
    `OrdemDeTravasViolada` antes de travar; travar de novo uma conta já travada é permitido."""
    travadas = _travadas_da_transacao()
    if travadas is not None and pk not in travadas and travadas and pk < max(travadas):
        raise OrdemDeTravasViolada(
            f"a conta {pk} foi pedida depois da {max(travadas)}: trave o conjunto de uma vez, "
            "em ordem crescente de pk"
        )
    travada: ContaFinanceira = ContaFinanceira.objects.select_for_update().get(pk=pk)
    if travadas is not None:
        travadas.add(pk)
    return travada


def travar_contas(*contas: ContaFinanceira) -> None:
    """Trava o conjunto de contas de uma vez, em ordem crescente de `pk` (regra única de travas
    do financeiro, E09-R01, R02 e R09)."""
    for pk in sorted({c.pk for c in contas}):
        _travar_conta(pk)


__all__ = [
    "EXTERIOR",
    "LinhaDoExtrato",
    "MovimentoConflitante",
    "MovimentoInvalido",
    "MovimentoProibido",
    "SaldoInsuficiente",
    "Transferencia",
    "conta",
    "conta_da_obrigacao",
    "extrato",
    "lancar",
    "saldo",
    "saldo_total_esperado",
    "travar_contas",
]
