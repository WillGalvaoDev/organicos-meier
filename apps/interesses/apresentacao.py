"""Contexto das páginas do comprador para interesse (E05-05): carrinho e catálogo do fornecedor.

Só monta dados para o template: nenhuma regra mora aqui. O comprador vê o percentual do mínimo e
a própria participação; o mínimo, o valor elegível e o que falta em reais nunca saem daqui.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.catalogo.consultas import produtos_da_rodada
from apps.catalogo.quantidades import formatar_quantidade
from apps.contas.models import Conta
from apps.interesses.consultas import carrinho_do_comprador
from apps.interesses.progresso import progresso_da_rodada
from apps.nucleo.tempo import agora, no_fuso_da_operacao, prazo_encerrado
from apps.rodadas.condicoes import aceita_interesses
from apps.rodadas.fechamento import prazo_do_fechamento
from apps.rodadas.models import Etapa, Rodada


@dataclass(frozen=True)
class Retorno:
    """O resultado de um envio recusado, para a página de origem: status, aviso do topo e, no
    formulário do produto enviado, o texto digitado e a mensagem do serviço."""

    status: int
    topo: str | None = None
    produto_id: int | None = None
    acao: str = "quantidade"
    texto: str | None = ""  # None: mostra o valor atual do banco
    mensagem: str | None = None
    sem_formulario: bool = False
    produto_nome: str | None = None  # prefixo da mensagem quando ela vai para o topo


def texto_decimal(valor: Decimal) -> str:
    """Quantidade para o campo do formulário: ponto decimal e sem zeros à direita."""
    return formatar_quantidade(valor).replace(",", ".")


def _formulario(
    retorno: Retorno | None,
    produto_id: int,
    acao: str,
    padrao: Decimal,
    permitido: bool,
    estado: tuple[Decimal, Decimal],
) -> dict[str, Any]:
    """Estado de um formulário. `estado` é (reservado, pendente) lido para montar a página: vai
    nos campos ocultos, para o servidor reconhecer o envio feito sobre um estado que mudou."""
    devolvido = retorno is not None and retorno.produto_id == produto_id and retorno.acao == acao
    if retorno is not None and acao == "quantidade" and retorno.sem_formulario:
        permitido = permitido and retorno.produto_id != produto_id
    return {
        "mostrar": permitido,
        "valor": (
            retorno.texto
            if devolvido and retorno and retorno.texto is not None
            else texto_decimal(padrao)
        ),
        "reservado_atual": texto_decimal(estado[0]),
        "pendente_atual": texto_decimal(estado[1]),
        "mensagem": retorno.mensagem if devolvido and retorno else None,
    }


def _mensagem_sem_destino(retorno: Retorno | None, formularios: list[dict[str, Any]]) -> str | None:
    """A mensagem da recusa, com o nome do produto, quando nenhum formulário de destino foi
    desenhado para recebê-la (E05-R05). Se algum recebe, devolve `None`: ela aparece uma vez só."""
    if retorno is None or not retorno.mensagem:
        return None
    if any(f["mostrar"] and f["mensagem"] for f in formularios):
        return None
    prefixo = f"{retorno.produto_nome}: " if retorno.produto_nome else ""
    return prefixo + retorno.mensagem


def prazo_da_rodada(rodada: Rodada | None) -> datetime | None:
    """O prazo do fechamento, só para a rodada em fechamento ou com o fechamento encerrado."""
    if rodada is None or rodada.etapa not in (Etapa.FECHAMENTO, Etapa.FECHAMENTO_ENCERRADO):
        return None
    return prazo_do_fechamento(rodada)


def linha_do_prazo(rodada: Rodada | None, prazo: datetime | None) -> str | None:
    """A linha do prazo do fechamento que o comprador vê; nada sem prazo gravado (E06-07)."""
    if rodada is None or prazo is None:
        return None
    local = no_fuso_da_operacao(prazo)
    if rodada.etapa == Etapa.FECHAMENTO and not prazo_encerrado(agora(), prazo):
        return f"Prazo do fechamento: {local:%d/%m/%Y} às {local:%H:%M} (horário de Brasília)"
    return f"Prazo do fechamento encerrado em {local:%d/%m/%Y} às {local:%H:%M}."


def contexto_do_carrinho(conta: Conta, retorno: Retorno | None = None) -> dict[str, Any]:
    ativa = conta.pode_adicionar_interesse
    grupos: list[dict[str, Any]] = []
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
                    (linha.reservado, linha.pendente),
                ),
                "pendentes": _formulario(
                    retorno,
                    linha.produto.pk,
                    "pendentes",
                    linha.pendente,
                    ativa and linha.pendente > 0,
                    (linha.reservado, linha.pendente),
                ),
            }
            for linha in grupo.linhas
        ]
        grupos.append(
            {
                "grupo": grupo,
                "linhas": linhas,
                "prazo": linha_do_prazo(grupo.rodada, prazo_da_rodada(grupo.rodada)),
            }
        )
    desenhados = [
        f for g in grupos for item in g["linhas"] for f in (item["quantidade"], item["pendentes"])
    ]
    return {
        "grupos": grupos,
        "retorno": retorno,
        "retorno_sem_destino": _mensagem_sem_destino(retorno, desenhados),
    }


def contexto_do_catalogo(
    conta: Conta, rodada: Rodada, retorno: Retorno | None = None
) -> dict[str, Any]:
    progresso = progresso_da_rodada(rodada, conta)
    por_produto = {p.produto.pk: p for p in progresso.produtos}
    editavel = conta.pode_adicionar_interesse and aceita_interesses(rodada, agora())
    linhas: list[dict[str, Any]] = []
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
                    retorno,
                    item.produto.pk,
                    "quantidade",
                    participacao.reservado,
                    editavel,
                    (participacao.reservado, participacao.pendente),
                ),
            }
        )
    return {
        "rodada": rodada,
        "linhas": linhas,
        "itens": [linha["item"] for linha in linhas],
        "percentual": progresso.percentual,
        "atingido": progresso.atingido,
        "prazo": linha_do_prazo(rodada, prazo_da_rodada(rodada)),
        "retorno": retorno,
        "retorno_sem_destino": _mensagem_sem_destino(
            retorno, [linha["quantidade"] for linha in linhas]
        ),
    }
