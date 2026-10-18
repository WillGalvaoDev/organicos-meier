"""Receptores que atendem a fila de pendentes (E05-02).

Rodam dentro da transação do remetente: uma falha desfaz a abertura ou a alteração de estoque.
"""

from typing import Any

from apps.contas.models import Papel
from apps.interesses.fila import _alocar_produto, alocar_pendentes
from apps.interesses.servicos import remover_interesses_do_comprador
from apps.rodadas.models import Rodada


def atender_fila_na_abertura(sender: Any, rodada: Rodada, **kwargs: Any) -> None:
    alocar_pendentes(rodada.fornecedor)


def atender_fila_no_aumento_de_estoque(
    sender: Any, estoque: Any, anterior: Any, novo: Any, **kwargs: Any
) -> None:
    """Só quando o estoque aumentou (ou deixou de ter limite). A inclusão conta como aumento."""
    if novo is None or novo > anterior:
        _alocar_produto(estoque.rodada, estoque.produto)


def remover_interesses_na_suspensao(sender: Any, conta: Any, **kwargs: Any) -> None:
    remover_interesses_do_comprador(conta, motivo="suspensao")


def remover_interesses_na_remocao(sender: Any, conta: Any, **kwargs: Any) -> None:
    """Conta de fornecedor não tem parcelas: nada a fazer."""
    if conta.papel == Papel.COMPRADOR:
        remover_interesses_do_comprador(conta, motivo="remocao_da_conta")
