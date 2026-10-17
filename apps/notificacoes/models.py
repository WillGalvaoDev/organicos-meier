"""Notificação no site (E04-01).

O conteúdo é congelado na criação: depois de gravada, só `lida_em` muda, uma única vez, de nulo
para um instante. A aplicação recusa o resto (`RegistroImutavel`) e as triggers do banco também,
inclusive por SQL direto (`gatilhos.py`).
"""

from typing import Any

from django.db import models

from apps.contas.models import Conta
from apps.notificacoes.eventos import Canal, Evento
from apps.nucleo.so_insercao import RegistroImutavel
from apps.nucleo.tempo import agora

_SO_LIDA_EM = {"lida_em"}


class NotificacaoQuerySet(models.QuerySet["Notificacao"]):
    def update(self, **kwargs: Any) -> int:
        if set(kwargs) != _SO_LIDA_EM:
            raise RegistroImutavel("notificação: update() em lote só aceita lida_em")
        return super().update(**kwargs)

    def delete(self) -> tuple[int, dict[str, int]]:
        raise RegistroImutavel("notificação não pode ser apagada: delete() em lote recusado")

    def bulk_update(self, *args: Any, **kwargs: Any) -> int:
        raise RegistroImutavel("notificação: bulk_update() recusado")


class Notificacao(models.Model):
    conta = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="+")
    evento = models.CharField(max_length=40, choices=Evento.choices)
    titulo = models.CharField(max_length=150)
    corpo = models.CharField(max_length=2000)
    link = models.CharField(max_length=500, null=True, blank=True)  # noqa: DJ001
    chave = models.CharField(max_length=200, unique=True)
    criada_em = models.DateTimeField(default=agora)
    lida_em = models.DateTimeField(null=True, blank=True)

    objects = NotificacaoQuerySet.as_manager()

    class Meta:
        db_table = "notificacoes_notificacao"
        indexes = (
            models.Index(fields=["conta", "lida_em", "criada_em"], name="notificacao_central"),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(evento__in=Evento.values), name="notificacao_evento_valido"
            ),
            models.CheckConstraint(
                condition=~models.Q(titulo="") & ~models.Q(corpo=""),
                name="notificacao_titulo_e_corpo_preenchidos",
            ),
            models.CheckConstraint(
                condition=models.Q(link__isnull=True)
                | (models.Q(link__startswith="/") & ~models.Q(link__startswith="//")),
                name="notificacao_link_relativo",
            ),
        )

    def __str__(self) -> str:
        return f"Notificação {self.pk}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding and set(kwargs.get("update_fields") or ()) != _SO_LIDA_EM:
            raise RegistroImutavel("Notificacao só aceita alterar lida_em: save() recusado")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise RegistroImutavel("Notificacao não pode ser apagada: delete() recusado")


class SituacaoEnvio(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    ENVIADO = "enviado", "Aceito pelo serviço de e-mail"
    FALHOU = "falhou", "Falhou"
    CANCELADO = "cancelado", "Cancelado"


CANAIS_EXTERNOS = [(c.value, c.label) for c in Canal if c is not Canal.SITE]


class Envio(models.Model):
    """Fila de saída (outbox): um envio por canal externo de cada notificação (E04-02).

    O conteúdo (canal, tipo, destinatário, assunto, corpo, chave) é congelado na criação. Só os
    campos de estado mudam, e só enquanto o envio está pendente (triggers em `gatilhos.py`).
    Nesta fatia `notificacao` e `conta` são obrigatórias; a E04-05 relaxa para os e-mails de
    acesso.
    """

    canal = models.CharField(max_length=10, choices=CANAIS_EXTERNOS)
    tipo = models.CharField(max_length=40)
    notificacao = models.ForeignKey(
        Notificacao, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    conta = models.ForeignKey(
        Conta, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    destino = models.CharField(max_length=254, blank=True)
    assunto = models.CharField(max_length=150)
    corpo = models.TextField(blank=True)
    chave = models.CharField(max_length=220, unique=True)
    situacao = models.CharField(
        max_length=10, choices=SituacaoEnvio.choices, default=SituacaoEnvio.PENDENTE
    )
    tentativas = models.PositiveSmallIntegerField(default=0)
    proxima_tentativa_em = models.DateTimeField(default=agora)
    criado_em = models.DateTimeField(default=agora)
    concluido_em = models.DateTimeField(null=True, blank=True)
    motivo_cancelamento = models.CharField(max_length=40, blank=True)

    class Meta:
        db_table = "notificacoes_envio"
        indexes = (
            models.Index(
                fields=["proxima_tentativa_em"],
                condition=models.Q(situacao="pendente"),
                name="envio_pendente_por_prazo",
            ),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(situacao__in=SituacaoEnvio.values),
                name="envio_situacao_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(tentativas__gte=0, tentativas__lte=3),
                name="envio_tentativas_de_0_a_3",
            ),
            models.CheckConstraint(
                condition=models.Q(situacao="pendente", concluido_em__isnull=True)
                | (~models.Q(situacao="pendente") & models.Q(concluido_em__isnull=False)),
                name="envio_concluido_se_e_so_se_nao_pendente",
            ),
            models.CheckConstraint(
                condition=models.Q(notificacao__isnull=False, conta__isnull=False),
                name="envio_com_notificacao_e_conta",
            ),
        )

    def __str__(self) -> str:
        return f"Envio {self.pk}"
