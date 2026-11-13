"""O pedido formal ao fornecedor (E13-01).

Gerado uma vez por ciclo aprovado, na transação da aprovação do resultado (receptor de
`resultado_aprovado`). O conteúdo do e-mail é montado aqui e gravado: todo envio, automático ou
manual, usa o mesmo registro. Nada é enviado nesta etapa. O pedido formal não tem dado de
comprador (§2, §10): parte dos itens congelados, agrupados por produto.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection, transaction

from apps.catalogo.quantidades import formatar_quantidade
from apps.catalogo.templatetags.catalogo import reais
from apps.financeiro.livro import conta
from apps.financeiro.models import ApuracaoNoLivro, Destinacao, TransferenciaFinanceira
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos.apuracao import _calcular_o_resultado
from apps.pedidos.models import (
    AprovacaoDoResultado,
    EnvioDoPedidoFormal,
    ItemDoPedido,
    LinhaDoPedidoFormal,
    OrigemDaPrevisao,
    ParcelaNoPedido,
    PedidoFormal,
    PrevisaoDeEntrega,
    ResultadoDaApuracao,
    SituacaoDePagamento,
    SituacaoDoEnvio,
    SituacaoDoPedido,
)
from apps.rodadas.models import Ciclo

ZERO = Decimal("0.000")
ZERO_DINHEIRO = Decimal("0.00")
MAIOR_ASSUNTO = 200
VEZES = "×"  # noqa: RUF001


class PedidoFormalIncoerente(Exception):
    """Um invariante do pedido formal não fechou (E13-01, regra 7). Desfaz a aprovação."""


@dataclass(frozen=True)
class _Linha:
    produto_id: int
    nome: str
    unidade: str
    preco_unitario: Decimal
    multiplo: Decimal | None
    quantidade: Decimal
    caixas: int | None
    valor_total: Decimal


def previsao_vigente(ciclo: Ciclo) -> PrevisaoDeEntrega | None:
    """A previsão de entrega vigente do ciclo: a de maior `pk` (E13-01)."""
    return PrevisaoDeEntrega.objects.filter(ciclo=ciclo).order_by("-pk").first()


def _valor_da_linha(itens: list[ItemDoPedido], descontos: dict[int, Decimal]) -> Decimal:
    """O valor dos produtos de uma linha: `subtotal - desconto` dos itens do produto, com o
    desconto da E11-03 (o mesmo valor do estorno proporcional da E11-04)."""
    return sum((i.subtotal - descontos.get(i.pk, ZERO_DINHEIRO) for i in itens), ZERO_DINHEIRO)


def _linhas(apuracao_no_livro: ApuracaoNoLivro, aprovacao: AprovacaoDoResultado) -> list[_Linha]:
    apuracao = aprovacao.apuracao
    abertura = apuracao.abertura
    validos = list(apuracao_no_livro.pedidos_validos.values_list("pedido_id", flat=True))
    nao_pagos = set(
        SituacaoDoPedido.objects.filter(pedido__abertura=abertura)
        .exclude(situacao=SituacaoDePagamento.PAGO)
        .values_list("pedido_id", flat=True)
    )
    calculo = _calcular_o_resultado(abertura, nao_pagos)
    invalidas = set(apuracao.caixas.values_list("produto_id", "numero"))
    itens = list(ItemDoPedido.objects.filter(pedido_id__in=validos).order_by("produto_id", "pk"))
    por_produto: dict[int, list[ItemDoPedido]] = {}
    for item in itens:
        por_produto.setdefault(item.produto_id, []).append(item)
    parcelas = ParcelaNoPedido.objects.filter(item__in=itens).select_related("item")
    caixas_validas: dict[int, set[int]] = {}
    for parcela in parcelas:
        chave = (parcela.item.produto_id, parcela.caixa)
        if parcela.caixa is not None and chave not in invalidas:
            caixas_validas.setdefault(parcela.item.produto_id, set()).add(parcela.caixa)
    linhas: list[_Linha] = []
    for produto_id, do_produto in por_produto.items():
        quantidade = sum(
            (i.quantidade - calculo.unidades_invalidadas.get(i.pk, ZERO) for i in do_produto), ZERO
        )
        if quantidade <= 0:
            continue
        primeiro = do_produto[0]
        if len({i.preco_unitario for i in do_produto}) != 1:
            raise PedidoFormalIncoerente(f"preços diferentes no produto {produto_id}")
        com_multiplo = primeiro.multiplo is not None
        linhas.append(
            _Linha(
                produto_id=produto_id,
                nome=primeiro.nome,
                unidade=primeiro.unidade,
                preco_unitario=primeiro.preco_unitario,
                multiplo=primeiro.multiplo,
                quantidade=quantidade,
                caixas=len(caixas_validas.get(produto_id, set())) if com_multiplo else None,
                valor_total=_valor_da_linha(do_produto, calculo.descontos),
            )
        )
    return sorted(linhas, key=lambda linha: (linha.nome, linha.produto_id))


def _conferir(
    linhas: list[_Linha], total: Decimal, apuracao_no_livro: ApuracaoNoLivro, fornecedor_id: int
) -> None:
    """A rede contra regressão (regra 7): nunca deve falhar."""
    for linha in linhas:
        if linha.multiplo is not None and linha.quantidade != (linha.caixas or 0) * linha.multiplo:
            raise PedidoFormalIncoerente(f"caixas incoerentes no produto {linha.produto_id}")
    destino = conta(
        Destinacao.OBRIGACAO_FORNECEDOR,
        fornecedor=fornecedor_id,
        rodada=apuracao_no_livro.ciclo.rodada_id,
    )
    transferido = sum(
        (
            t.valor
            for t in TransferenciaFinanceira.objects.filter(
                movimento=apuracao_no_livro.movimento, para=destino
            )
        ),
        ZERO_DINHEIRO,
    )
    if apuracao_no_livro.movimento is None or total != transferido:
        raise PedidoFormalIncoerente(
            f"o total {total} difere do transferido ao fornecedor ({transferido})"
        )


def _texto_da_linha(linha: _Linha) -> str:
    quantidade = f"{formatar_quantidade(linha.quantidade)} {linha.unidade}"
    preco = reais(linha.preco_unitario)
    if linha.multiplo is None:
        detalhe = quantidade
    else:
        detalhe = (
            f"{quantidade} em {linha.caixas} caixa(s) de "
            f"{formatar_quantidade(linha.multiplo)} {linha.unidade}"
        )
    return f"- {linha.nome}: {detalhe} {VEZES} {preco} = {reais(linha.valor_total)}"


def _corpo(
    pk: int,
    fornecedor_nome: str,
    informacoes_frete: str,
    ciclo: Ciclo,
    emitido_em: object,
    linhas: list[_Linha],
    total: Decimal,
    previsao: date,
    prazo: int,
) -> str:
    emitido = no_fuso_da_operacao(emitido_em)  # type: ignore[arg-type]
    partes = [
        f"Pedido formal nº {pk}",
        f"Fornecedor: {fornecedor_nome}",
        f"Rodada {ciclo.rodada_id}, ciclo {ciclo.numero}",
        f"Emitido em {emitido:%d/%m/%Y %H:%M} (horário de Brasília)",
        "",
        "Produtos:",
        *[_texto_da_linha(linha) for linha in linhas],
        f"Total dos produtos: {reais(total)}",
        "",
        "Condições de entrega:",
        f"Previsão de entrega: {previsao:%d/%m/%Y} (prazo padrão de {prazo} dias)",
    ]
    if informacoes_frete.strip():
        partes.append(f"Informações de frete: {informacoes_frete.strip()}")
    return "\n".join(partes)


def _proximo_pk() -> int:
    """Reserva o `pk` antes da inserção: o corpo do e-mail cita o número, e o registro não pode
    ser alterado depois de gravado."""
    tabela = PedidoFormal._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [tabela])
        return int(cursor.fetchone()[0])


def gerar_pedido_formal(aprovacao: AprovacaoDoResultado) -> PedidoFormal:
    """Gera o pedido formal da aprovação, uma única vez. Exige transação aberta
    (`TransactionManagementError`) e uma aprovação de resultado válido (`ValueError`). Repetir
    devolve o existente, sem escrita."""
    if aprovacao is None:
        raise ValueError("o pedido formal exige uma aprovação do resultado")
    if not connection.in_atomic_block:
        raise transaction.TransactionManagementError("gerar_pedido_formal exige transação aberta")
    existente: PedidoFormal | None = PedidoFormal.objects.filter(aprovacao=aprovacao).first()
    if existente is not None:
        return existente
    apuracao = aprovacao.apuracao
    if apuracao.resultado != ResultadoDaApuracao.VALIDA:
        raise ValueError("o pedido formal exige um resultado válido aprovado")
    ciclo = apuracao.ciclo
    rodada = ciclo.rodada
    fornecedor = rodada.fornecedor
    no_livro = ApuracaoNoLivro.objects.get(ciclo=ciclo)
    linhas = _linhas(no_livro, aprovacao)
    total = sum((linha.valor_total for linha in linhas), ZERO_DINHEIRO)
    _conferir(linhas, total, no_livro, fornecedor.pk)
    emitido_em = aprovacao.aprovada_em
    prazo = fornecedor.prazo_entrega_dias
    previsao = no_fuso_da_operacao(emitido_em).date() + timedelta(days=prazo)
    pk = _proximo_pk()
    assunto = f"Pedido formal nº {pk} — Orgânicos Méier — {fornecedor.nome}"[:MAIOR_ASSUNTO]
    corpo = _corpo(
        pk, fornecedor.nome, fornecedor.informacoes_frete, ciclo, emitido_em, linhas, total,
        previsao, prazo,
    )  # fmt: skip
    pedido = PedidoFormal.objects.create(
        pk=pk,
        aprovacao=aprovacao,
        ciclo=ciclo,
        rodada=rodada,
        fornecedor=fornecedor,
        emitido_em=emitido_em,
        prazo_entrega_dias=prazo,
        previsao_inicial=previsao,
        total_produtos=total,
        assunto=assunto,
        corpo=corpo,
    )
    LinhaDoPedidoFormal.objects.bulk_create(
        [
            LinhaDoPedidoFormal(
                pedido_formal=pedido,
                produto_id=linha.produto_id,
                nome=linha.nome,
                unidade=linha.unidade,
                preco_unitario=linha.preco_unitario,
                multiplo=linha.multiplo,
                quantidade=linha.quantidade,
                caixas=linha.caixas,
                valor_total=linha.valor_total,
            )
            for linha in linhas
        ]
    )
    PrevisaoDeEntrega.objects.create(
        rodada=rodada, ciclo=ciclo, data=previsao, origem=OrigemDaPrevisao.PADRAO
    )
    EnvioDoPedidoFormal.objects.create(
        pedido_formal=pedido,
        situacao=SituacaoDoEnvio.EM_ANDAMENTO,
        automaticas=0,
        proxima_tentativa_em=emitido_em,
    )
    registrar_auditoria(
        SISTEMA,
        "pedido_formal.gerar",
        pedido,
        {
            "pedido_formal": pedido.pk,
            "ciclo": ciclo.pk,
            "linhas": [
                {
                    "produto": linha.produto_id,
                    "quantidade": str(linha.quantidade),
                    "caixas": linha.caixas,
                    "valor": str(linha.valor_total),
                }
                for linha in linhas
            ],
            "total_produtos": str(total),
            "previsao_inicial": previsao.isoformat(),
        },
    )
    return pedido
