"""Progresso elegível da rodada e caixas dos produtos (E05-04).

Só a quantidade reservada conta (parcelas `ativa`): pendentes nunca entram. Em produto com
múltiplo `m`, só `piso(total / m) * m` é elegível, e as unidades entram nas caixas pela ordem de
`sequencia` das parcelas (a mesma prioridade da remoção de excedentes, §6.3). O valor elegível
soma, por comprador e por produto, o subtotal arredondado uma vez: é o `T` da cobrança com o
preço vigente. A consulta não grava nada e faz um número fixo de leituras.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import calcular_subtotal
from apps.contas.models import Conta
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.rodadas.models import EstoqueDaRodada, Rodada

_ZERO = Decimal("0.000")


@dataclass(frozen=True)
class ParticipacaoDoComprador:
    reservado: Decimal
    pendente: Decimal
    em_caixas: Decimal
    excedente: Decimal
    subtotal: Decimal


@dataclass(frozen=True)
class ProgressoDoProduto:
    produto: Produto
    total_reservado: Decimal
    quantidade_elegivel: Decimal
    caixas_completas: int | None
    faltam_para_proxima_caixa: Decimal | None
    excedente: Decimal
    valor_bruto: Decimal
    valor_elegivel: Decimal
    do_comprador: ParticipacaoDoComprador | None


@dataclass(frozen=True)
class ProgressoDaRodada:
    rodada: Rodada
    minimo: Decimal
    valor_elegivel: Decimal
    atingido: bool
    falta: Decimal
    percentual: int
    produtos: list[ProgressoDoProduto]


@dataclass
class _Linha:
    comprador_id: int
    situacao: str
    reservada: Decimal
    pendente: Decimal


def _produto(produto: Produto, linhas: list[_Linha], comprador: Conta | None) -> ProgressoDoProduto:
    ativas = [x for x in linhas if x.situacao == SituacaoParcela.ATIVA and x.reservada > 0]
    total = sum((x.reservada for x in ativas), _ZERO).quantize(_ZERO)
    multiplo = produto.multiplo
    caixas: int | None
    faltam: Decimal | None
    if multiplo is None:
        elegivel, caixas, faltam = total, None, None
    else:
        elegivel = ((total // multiplo) * multiplo).quantize(_ZERO)
        caixas = int(total // multiplo)
        faltam = (multiplo - (total % multiplo)).quantize(_ZERO)
    restante = elegivel
    em_caixas: dict[int, Decimal] = defaultdict(lambda: _ZERO)
    for linha in ativas:  # já em ordem de sequência
        parte = min(linha.reservada, restante)
        em_caixas[linha.comprador_id] += parte
        restante -= parte
    valor_elegivel = sum(
        (calcular_subtotal(produto.preco, q) for q in em_caixas.values() if q > 0), Decimal("0.00")
    )
    participacao = None
    if comprador is not None:
        reservado = sum((x.reservada for x in ativas if x.comprador_id == comprador.pk), _ZERO)
        pendente = sum((x.pendente for x in linhas if x.comprador_id == comprador.pk), _ZERO)
        dele = em_caixas.get(comprador.pk, _ZERO)
        participacao = ParticipacaoDoComprador(
            reservado=reservado.quantize(_ZERO),
            pendente=pendente.quantize(_ZERO),
            em_caixas=dele.quantize(_ZERO),
            excedente=(reservado - dele).quantize(_ZERO),
            subtotal=calcular_subtotal(produto.preco, reservado),
        )
    return ProgressoDoProduto(
        produto=produto,
        total_reservado=total,
        quantidade_elegivel=elegivel,
        caixas_completas=caixas,
        faltam_para_proxima_caixa=faltam,
        excedente=(total - elegivel).quantize(_ZERO),
        valor_bruto=calcular_subtotal(produto.preco, total),
        valor_elegivel=valor_elegivel,
        do_comprador=participacao,
    )


def progresso_da_rodada(rodada: Rodada, comprador: Conta | None = None) -> ProgressoDaRodada:
    minimo = rodada.fornecedor.minimo
    estoques = list(
        EstoqueDaRodada.objects.filter(rodada_id=rodada.pk)
        .select_related("produto")
        .order_by("produto__nome", "produto_id")
    )
    por_produto: dict[int, list[_Linha]] = defaultdict(list)
    parcelas = (
        ParcelaDeInteresse.objects.filter(
            produto_id__in=[e.produto_id for e in estoques],
            situacao__in=(SituacaoParcela.ATIVA, SituacaoParcela.PENDENTE),
        )
        .order_by("produto_id", "sequencia")
        .values_list(
            "produto_id", "comprador_id", "situacao", "quantidade_reservada", "quantidade_pendente"
        )
    )
    for produto_id, comprador_id, situacao, reservada, pendente in parcelas:
        por_produto[produto_id].append(_Linha(comprador_id, situacao, reservada, pendente))
    produtos = [_produto(e.produto, por_produto[e.produto_id], comprador) for e in estoques]
    valor = sum((p.valor_elegivel for p in produtos), Decimal("0.00"))
    atingido = valor >= minimo
    if minimo == 0:
        percentual = 100
    else:
        percentual = int((valor * 100 / minimo).to_integral_value(rounding=ROUND_FLOOR))
        percentual = 100 if atingido else min(percentual, 99)
    return ProgressoDaRodada(
        rodada=rodada,
        minimo=minimo,
        valor_elegivel=valor,
        atingido=atingido,
        falta=max(minimo - valor, Decimal("0.00")),
        percentual=percentual,
        produtos=produtos,
    )
