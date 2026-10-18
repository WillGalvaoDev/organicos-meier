"""Moderação de contas pelo administrador (E02-08).

Suspensão é reversível e não encerra sessões (o suspenso continua entrando). Remoção é definitiva:
bane o e-mail, apaga as sessões e mantém a conta e todo o histórico. Todas as ações travam a conta
(`select_for_update(no_key=True)`), revalidam a situação depois da trava e rodam numa única
transação com a auditoria e os sinais, para que efeitos de etapas futuras sejam atômicos com a
moderação.
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.dispatch import Signal

from apps.contas.models import Conta, EmailBanido, Papel, Situacao
from apps.contas.sessoes import encerrar_sessoes
from apps.nucleo.auditoria import registrar_auditoria

# Enviados dentro da transação da moderação, com o argumento `conta`.
conta_suspensa = Signal()
conta_removida = Signal()


class ModeracaoInvalida(Exception):
    """Alvo ou situação que a moderação não permite. Nada é alterado nem auditado."""


def _exigir_administrador(autor: Conta) -> None:
    if getattr(autor, "papel", None) != Papel.ADMINISTRADOR:
        raise PermissionDenied


def _travar(conta: Conta, papeis: tuple[str, ...], situacoes: tuple[str, ...]) -> tuple[Conta, str]:
    """Trava a conta e revalida papel e situação. Devolve a conta e a situação anterior."""
    try:
        # FOR NO KEY UPDATE: não bloqueia o FOR KEY SHARE das chaves estrangeiras para a conta
        # (notificações, auditoria), que a edição de preço pede no COMMIT (E05-R03).
        travada = Conta.objects.select_for_update(no_key=True).get(pk=conta.pk)
    except Conta.DoesNotExist:
        raise ModeracaoInvalida("conta inexistente") from None
    if travada.papel not in papeis or travada.situacao not in situacoes:
        raise ModeracaoInvalida("ação não permitida para esta conta")
    return travada, str(travada.situacao)


def _mudar_situacao(autor: Conta, conta: Conta, nova: Situacao, acao: str, anterior: str) -> None:
    conta.situacao = nova
    conta.save(update_fields=["situacao"])
    registrar_auditoria(
        autor,
        acao,
        conta,
        {"conta": conta.pk, "situacao_anterior": anterior, "situacao_nova": str(nova)},
    )


def suspender(autor: Conta, conta: Conta) -> None:
    """Comprador ativo passa a suspenso. Não encerra sessões; envia `conta_suspensa`."""
    _exigir_administrador(autor)
    with transaction.atomic():
        travada, anterior = _travar(conta, (Papel.COMPRADOR,), (Situacao.ATIVA,))
        _mudar_situacao(autor, travada, Situacao.SUSPENSA, "conta.suspender", anterior)
        conta_suspensa.send(sender=Conta, conta=travada)
    conta.situacao = Situacao.SUSPENSA


def reativar(autor: Conta, conta: Conta) -> None:
    """Comprador suspenso volta a ativo. Não restaura nada além da situação."""
    _exigir_administrador(autor)
    with transaction.atomic():
        travada, anterior = _travar(conta, (Papel.COMPRADOR,), (Situacao.SUSPENSA,))
        _mudar_situacao(autor, travada, Situacao.ATIVA, "conta.reativar", anterior)
    conta.situacao = Situacao.ATIVA


def remover(autor: Conta, conta: Conta) -> None:
    """Remove a conta (definitivo): bane o e-mail e apaga as sessões, sem apagar nada mais."""
    _exigir_administrador(autor)
    with transaction.atomic():
        travada, anterior = _travar(
            conta,
            (Papel.COMPRADOR, Papel.FORNECEDOR),
            (Situacao.ATIVA, Situacao.SUSPENSA),
        )
        _mudar_situacao(autor, travada, Situacao.REMOVIDA, "conta.remover", anterior)
        if not EmailBanido.objects.filter(email_normalizado=travada.email_normalizado).exists():
            EmailBanido.objects.create(
                email_normalizado=travada.email_normalizado, banido_por=autor
            )
        encerrar_sessoes(travada)
        conta_removida.send(sender=Conta, conta=travada)
    conta.situacao = Situacao.REMOVIDA
