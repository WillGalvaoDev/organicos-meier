"""As consultas do portal do fornecedor (E13-07).

Cada consulta devolve dicionários só com as chaves de uma lista fechada, e as páginas usam apenas
o que elas devolvem: nenhum objeto de modelo chega ao template (infraestrutura 4.13). O filtro
pelo fornecedor vinculado fica nas views (`Rodada.objects.filter(fornecedor=...)`); aqui as
consultas partem do fornecedor ou da rodada já filtrada. O fornecedor não vê pagamentos,
compradores, taxa de serviço, reserva, tentativas de envio, frete nem repasses.
"""

import csv
import io
from decimal import Decimal
from typing import Any

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import formatar_quantidade
from apps.fornecedores.models import Fornecedor
from apps.interesses.progresso import progresso_da_rodada
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos.models import PedidoFormal
from apps.pedidos.pedido_formal import previsao_vigente
from apps.rodadas.models import Etapa, Rodada

CABECALHO_DO_CSV = (
    "produto",
    "unidade",
    "quantidade",
    "multiplo",
    "caixas",
    "preco_unitario",
    "valor_total",
)
ETAPAS_COM_PROGRESSO = (Etapa.INTERESSE, Etapa.FECHAMENTO, Etapa.FECHAMENTO_ENCERRADO)
ETAPAS_COM_PEDIDO_FORMAL = (
    Etapa.AGUARDANDO_FORNECEDOR,
    Etapa.DISPONIVEL_PARA_RETIRADA,
    Etapa.CANCELADA,
)
FRASE_DO_PAGAMENTO = "As quantidades finais serão informadas no pedido formal, depois da apuração."


def _data_hora(instante: Any) -> str:
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}"


def dados_do_painel(fornecedor: Fornecedor) -> dict[str, Any]:
    """O painel: o nome, os produtos e as rodadas do fornecedor vinculado."""
    produtos = Produto.objects.filter(fornecedor=fornecedor).order_by("nome", "pk")
    rodadas = Rodada.objects.filter(fornecedor=fornecedor).order_by("-pk")
    return {
        "fornecedor": {"nome": fornecedor.nome},
        "produtos": [
            {
                "nome": p.nome,
                "unidade": p.unidade,
                "preco_unitario": p.preco,
                "multiplo": p.multiplo,
            }
            for p in produtos
        ],
        "rodadas": [
            {
                "numero": r.pk,
                "etapa": r.get_etapa_display(),
                "aberta_em": f"{no_fuso_da_operacao(r.aberta_em):%d/%m/%Y}",
            }
            for r in rodadas
        ],
    }


def _progresso(rodada: Rodada) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    progresso = progresso_da_rodada(rodada)
    produtos = [
        {
            "nome": p.produto.nome,
            "unidade": p.produto.unidade,
            "preco_unitario": p.produto.preco,
            "total_em_interesse": p.total_reservado,
            "caixas_completas": p.caixas_completas,
            "faltam_para_proxima_caixa": p.faltam_para_proxima_caixa,
            "excedente": p.excedente,
            "valor_total": p.valor_bruto,
        }
        for p in progresso.produtos
    ]
    return {"progresso_percentual": progresso.percentual}, produtos


def dados_da_rodada(rodada: Rodada) -> dict[str, Any]:
    """O andamento da rodada, conforme a etapa: o progresso agregado, a frase do pagamento ou o
    pedido formal com a previsão. A rodada já vem filtrada pelo fornecedor vinculado."""
    bloco: dict[str, Any] = {"etapa": rodada.get_etapa_display()}
    produtos: list[dict[str, Any]] = []
    if rodada.etapa in ETAPAS_COM_PROGRESSO:
        extra, produtos = _progresso(rodada)
        bloco |= extra
    pedido_formal: dict[str, Any] | None = None
    linhas: list[dict[str, Any]] = []
    previsao: Any = None
    pedido = PedidoFormal.objects.filter(rodada=rodada).first()
    if pedido is not None and rodada.etapa in ETAPAS_COM_PEDIDO_FORMAL:
        pedido_formal = {
            "numero": pedido.pk,
            "emitido_em": _data_hora(pedido.emitido_em),
            "total_produtos": pedido.total_produtos,
        }
        linhas = _linhas(pedido)
        if rodada.etapa == Etapa.AGUARDANDO_FORNECEDOR:
            vigente = previsao_vigente(pedido.ciclo)
            previsao = vigente.data if vigente is not None else pedido.previsao_inicial
    return {
        "rodada": bloco,
        "produtos": produtos,
        "pedido_formal": pedido_formal,
        "linhas": linhas,
        "previsao_de_entrega": previsao,
        "frase_do_pagamento": FRASE_DO_PAGAMENTO if rodada.etapa == Etapa.PAGAMENTO else "",
    }


def _linhas(pedido: PedidoFormal) -> list[dict[str, Any]]:
    return [
        {
            "nome": linha.nome,
            "unidade": linha.unidade,
            "quantidade": linha.quantidade,
            "multiplo": linha.multiplo,
            "caixas": linha.caixas,
            "preco_unitario": linha.preco_unitario,
            "valor_total": linha.valor_total,
        }
        for linha in pedido.linhas.order_by("nome", "produto_id")
    ]


def _dinheiro(valor: Decimal) -> str:
    return f"{valor:.2f}".replace(".", ",")


def csv_do_pedido_formal(pedido: PedidoFormal) -> str:
    """A exportação: uma linha por linha do pedido formal, separador `;` e vírgula decimal."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(CABECALHO_DO_CSV)
    for linha in _linhas(pedido):
        escritor.writerow(
            [
                linha["nome"],
                linha["unidade"],
                formatar_quantidade(linha["quantidade"]),
                "" if linha["multiplo"] is None else formatar_quantidade(linha["multiplo"]),
                "" if linha["caixas"] is None else linha["caixas"],
                _dinheiro(linha["preco_unitario"]),
                _dinheiro(linha["valor_total"]),
            ]
        )
    return saida.getvalue()
