"""Contexto das páginas do comprador para interesse (E05-05): carrinho e catálogo do fornecedor.

Só monta dados para o template: nenhuma regra mora aqui. O comprador vê o percentual do mínimo e
a própria participação; o mínimo, o valor elegível e o que falta em reais nunca saem daqui.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.catalogo.consultas import produtos_da_rodada
from apps.catalogo.quantidades import formatar_quantidade
from apps.contas.models import Conta
from apps.interesses.consultas import carrinho_do_comprador
from apps.interesses.progresso import progresso_da_rodada
from apps.rodadas.models import Etapa, Rodada

ETAPAS_QUE_ACEITAM = (Etapa.INTERESSE, Etapa.FECHAMENTO)


@dataclass(frozen=True)
class Retorno:
    """O resultado de um envio recusado, para a página de origem: status, aviso do topo e, no
    formulário do produto enviado, o texto digitado e a mensagem do serviço."""

    status: int
    topo: str | None = None
    produto_id: int | None = None
    acao: str = "quantidade"
    texto: str = ""
    mensagem: str | None = None
    sem_formulario: bool = False


def texto_decimal(valor: Decimal) -> str:
    """Quantidade para o campo do formulário: ponto decimal e sem zeros à direita."""
    return formatar_quantidade(valor).replace(",", ".")


def _formulario(
    retorno: Retorno | None, produto_id: int, acao: str, padrao: Decimal, permitido: bool
) -> dict[str, Any]:
    devolvido = retorno is not None and retorno.produto_id == produto_id and retorno.acao == acao
    if retorno is not None and acao == "quantidade" and retorno.sem_formulario:
        permitido = permitido and retorno.produto_id != produto_id
    return {
        "mostrar": permitido,
        "valor": retorno.texto if devolvido and retorno else texto_decimal(padrao),
        "mensagem": retorno.mensagem if devolvido and retorno else None,
    }


def contexto_do_carrinho(conta: Conta, retorno: Retorno | None = None) -> dict[str, Any]:
    ativa = conta.pode_adicionar_interesse
    grupos = []
    for grupo in carrinho_do_comprador(conta):
        linhas = [
            {
                "linha": linha,
                "quantidade": _formulario(
                    retorno,
                    linha.produto.pk,
                    "quantidade",
                    linha.reservado,
                    ativa and grupo.editavel and linha.no_estoque,
                ),
                "pendentes": _formulario(
                    retorno,
                    linha.produto.pk,
                    "pendentes",
                    linha.pendente,
                    ativa and linha.pendente > 0,
                ),
            }
            for linha in grupo.linhas
        ]
        grupos.append({"grupo": grupo, "linhas": linhas})
    return {"grupos": grupos, "retorno": retorno}


def contexto_do_catalogo(
    conta: Conta, rodada: Rodada, retorno: Retorno | None = None
) -> dict[str, Any]:
    progresso = progresso_da_rodada(rodada, conta)
    por_produto = {p.produto.pk: p for p in progresso.produtos}
    editavel = conta.pode_adicionar_interesse and rodada.etapa in ETAPAS_QUE_ACEITAM
    linhas = []
    for item in produtos_da_rodada(rodada):
        dele = por_produto[item.produto.pk]
        participacao = dele.do_comprador
        if participacao is None:
            raise ValueError("o progresso precisa ser pedido com o comprador")
        linhas.append(
            {
                "item": item,
                "interesse": participacao,
                "caixas": dele if item.produto.multiplo is not None else None,
                "quantidade": _formulario(
                    retorno, item.produto.pk, "quantidade", participacao.reservado, editavel
                ),
            }
        )
    return {
        "rodada": rodada,
        "linhas": linhas,
        "itens": [linha["item"] for linha in linhas],
        "percentual": progresso.percentual,
        "atingido": progresso.atingido,
        "retorno": retorno,
    }
