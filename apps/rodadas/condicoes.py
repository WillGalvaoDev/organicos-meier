"""Primitiva da fase de interesse (E03-02).

Toda alteração de condição comercial da rodada (hoje, o mínimo do fornecedor) e toda mudança
de etapa passam pela mesma ordem de travas: primeiro a linha do fornecedor, depois a da rodada
ativa. Assim, uma alteração que espera por uma mudança de etapa enxerga a etapa já confirmada.
"""

from django.db import connection
from django.db.transaction import TransactionManagementError

from apps.fornecedores.models import Fornecedor
from apps.rodadas.models import ETAPAS_ATIVAS, Etapa, Rodada

MENSAGEM = "As condições da rodada só podem ser alteradas na fase de interesse."


class CondicoesCongeladas(Exception):
    """Alteração recusada. `codigo`: `sem_rodada_ativa` ou `fora_de_interesse`."""

    def __init__(self, codigo: str) -> None:
        super().__init__(MENSAGEM)
        self.codigo = codigo


def travar_condicoes(fornecedor: Fornecedor) -> Rodada:
    """Trava o fornecedor e a rodada ativa e devolve a rodada, que precisa estar em `interesse`.

    Exige transação aberta: a trava vale até o fim dela, e fora de uma transação seria solta
    na hora, sem proteger a alteração que vem depois.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("travar_condicoes exige uma transação aberta.")
    Fornecedor.objects.select_for_update().get(pk=fornecedor.pk)
    rodada = (
        Rodada.objects.select_for_update()
        .filter(fornecedor_id=fornecedor.pk, etapa__in=ETAPAS_ATIVAS)
        .first()
    )
    if rodada is None:
        raise CondicoesCongeladas("sem_rodada_ativa")
    if rodada.etapa != Etapa.INTERESSE:
        raise CondicoesCongeladas("fora_de_interesse")
    return rodada


def condicoes_editaveis(fornecedor: Fornecedor) -> bool:
    """Leitura sem trava: o fornecedor tem rodada em `interesse`?

    Só serve para escolher a resposta de uma rota quando nada será gravado. Quem grava trava e
    verifica de novo (`travar_condicoes`).
    """
    return Rodada.objects.filter(fornecedor_id=fornecedor.pk, etapa=Etapa.INTERESSE).exists()
