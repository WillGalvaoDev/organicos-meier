"""Devolução pela plataforma (E10-04): parcela, autorização, estados, tentativa e liquidação."""

from apps.contas.models import Conta
from apps.financeiro.models import ObrigacaoComComprador, ParcelaDeDevolucao
from apps.nucleo.auditoria import _Sistema
from apps.pagamentos.models import PagamentoNoProvedor


class DevolucaoRecusada(Exception):
    """A ação não pode ser feita agora; a mensagem diz o motivo."""


def pagamento_da_obrigacao(obrigacao: ObrigacaoComComprador) -> PagamentoNoProvedor:
    raise NotImplementedError


def situacao_da_devolucao(obrigacao: ObrigacaoComComprador) -> str:
    raise NotImplementedError


def autorizar_devolucao(
    obrigacao: ObrigacaoComComprador, *, autor: Conta | _Sistema
) -> ParcelaDeDevolucao:
    raise NotImplementedError


def tentar_devolucao_de_novo(
    parcela: ParcelaDeDevolucao, *, autor: Conta | _Sistema
) -> ParcelaDeDevolucao:
    raise NotImplementedError


def transicionar(
    parcela: ParcelaDeDevolucao,
    nova: str,
    *,
    autor: Conta | _Sistema,
    dados: dict[str, object] | None = None,
) -> ParcelaDeDevolucao:
    raise NotImplementedError
