"""Primitiva da fase de interesse (E03-02).

Toda alteração de condição comercial da rodada (hoje, o mínimo do fornecedor) e toda mudança
de etapa passam pela mesma ordem de travas: primeiro a linha do fornecedor, depois a da rodada
ativa. Assim, uma alteração que espera por uma mudança de etapa enxerga a etapa já confirmada.
"""

from datetime import datetime

from django.db import connection
from django.db.transaction import TransactionManagementError

from apps.fornecedores.models import Fornecedor
from apps.nucleo.tempo import agora, prazo_encerrado
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


MENSAGEM_INTERESSES = "Os interesses deste fornecedor não podem ser alterados nesta etapa."


class InteressesBloqueados(Exception):
    """Operação de interesse recusada.

    `codigo`: `sem_rodada_ativa`, `etapa_bloqueada` ou `prazo_encerrado` (E06-03).
    """

    def __init__(self, codigo: str) -> None:
        super().__init__(MENSAGEM_INTERESSES)
        self.codigo = codigo


def aceita_interesses(rodada: Rodada, instante: datetime) -> bool:
    """A rodada aceita interesses neste instante? A única regra, usada por todos (E06-03).

    Em `interesse`, sempre. Em `fechamento`, até o prazo (limite exclusivo): a partir do instante
    do prazo nada é aceito, mesmo que a tarefa de encerramento ainda não tenha gravado a etapa
    (§15). Nas outras etapas, nunca. `fechamento` sem prazo gravado viola a invariante da E06-01
    e é erro, para nunca aceitar interesse sem prazo.
    """
    if rodada.etapa == Etapa.INTERESSE:
        return True
    if rodada.etapa != Etapa.FECHAMENTO:
        return False
    from apps.rodadas.fechamento import prazo_do_fechamento

    prazo = prazo_do_fechamento(rodada)
    if prazo is None:
        raise RuntimeError("rodada em fechamento sem prazo gravado")
    return not prazo_encerrado(instante, prazo)


def travar_rodada_para_interesses(fornecedor: Fornecedor) -> Rodada:
    """Trava o fornecedor e a rodada ativa e devolve a rodada, que aceita interesses.

    Aceitam `interesse` e `fechamento` (§7). Nas demais etapas, ou sem rodada ativa, levanta
    `InteressesBloqueados`. Exige transação aberta, como `travar_condicoes`.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError(
            "travar_rodada_para_interesses exige uma transação aberta."
        )
    Fornecedor.objects.select_for_update().get(pk=fornecedor.pk)
    rodada = (
        Rodada.objects.select_for_update()
        .filter(fornecedor_id=fornecedor.pk, etapa__in=ETAPAS_ATIVAS)
        .first()
    )
    if rodada is None:
        raise InteressesBloqueados("sem_rodada_ativa")
    if rodada.etapa not in (Etapa.INTERESSE, Etapa.FECHAMENTO):
        raise InteressesBloqueados("etapa_bloqueada")
    if not aceita_interesses(rodada, agora()):  # o instante é lido depois das travas
        raise InteressesBloqueados("prazo_encerrado")
    return rodada


def interesses_editaveis(fornecedor: Fornecedor) -> bool:
    """Leitura sem trava: a rodada ativa aceita interesses? Só para a tela escolher a resposta."""
    rodada = Rodada.objects.filter(
        fornecedor_id=fornecedor.pk, etapa__in=(Etapa.INTERESSE, Etapa.FECHAMENTO)
    ).first()
    return rodada is not None and aceita_interesses(rodada, agora())
