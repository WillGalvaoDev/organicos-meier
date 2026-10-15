"""Trilha de auditoria comum (E01-04).

O autor e o objeto afetado são gravados como texto, sem chave estrangeira: remover a conta
ou o objeto não apaga a entrada, e nenhum dado pessoal é copiado.
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from apps.nucleo.so_insercao import RegistroSoInsercao
from apps.nucleo.tempo import agora

TERMOS_DE_SEGREDO = ("senha", "password", "token", "secret", "chave_api")


class _Sistema:
    def __repr__(self) -> str:
        return "SISTEMA"


SISTEMA = _Sistema()


class EntradaAuditoria(RegistroSoInsercao):
    class AutorTipo(models.TextChoices):
        USUARIO = "usuario"
        SISTEMA = "sistema"

    autor_tipo = models.CharField(max_length=10, choices=AutorTipo.choices)
    # NULL é exigido pela constraint: autor "sistema" não tem identificador.
    autor_id = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    acao = models.CharField(max_length=100)
    momento = models.DateTimeField()
    motivo = models.TextField(blank=True, default="")
    alteracoes = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    objeto_tipo = models.CharField(max_length=100)
    objeto_id = models.CharField(max_length=64)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(autor_tipo__in=["usuario", "sistema"]),
                name="auditoria_autor_tipo_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(autor_tipo="usuario", autor_id__isnull=False, autor_id__regex=r"\S")
                    | models.Q(autor_tipo="sistema", autor_id__isnull=True)
                ),
                name="auditoria_autor_id_conforme_tipo",
            ),
        )

    def __str__(self) -> str:
        return f"{self.momento:%Y-%m-%d %H:%M:%S} {self.acao}"


def _validar_sem_segredos(valor: Any, caminho: str = "alteracoes") -> None:
    if isinstance(valor, dict):
        for chave, interno in valor.items():
            if any(termo in str(chave).lower() for termo in TERMOS_DE_SEGREDO):
                raise ValueError(f"chave com termo reservado a segredo em {caminho}: {chave!r}")
            _validar_sem_segredos(interno, f"{caminho}.{chave}")
    elif isinstance(valor, list | tuple):
        for indice, interno in enumerate(valor):
            _validar_sem_segredos(interno, f"{caminho}[{indice}]")


def registrar_auditoria(
    autor: Any,
    acao: str,
    objeto: models.Model,
    alteracoes: dict[str, Any],
    motivo: str | None = None,
) -> EntradaAuditoria:
    """Grava uma entrada na transação corrente. `autor` é um usuário salvo ou `SISTEMA`."""
    if autor is SISTEMA:
        autor_tipo, autor_id = EntradaAuditoria.AutorTipo.SISTEMA, None
    elif isinstance(autor, get_user_model()) and autor.pk is not None:
        autor_tipo, autor_id = EntradaAuditoria.AutorTipo.USUARIO, str(autor.pk)
    else:
        raise ValueError("autor inválido: informe um usuário salvo ou SISTEMA")
    if not isinstance(acao, str) or not acao.strip():
        raise ValueError("ação vazia")
    if objeto.pk is None:
        raise ValueError("objeto afetado ainda não foi salvo")
    _validar_sem_segredos(alteracoes)
    return EntradaAuditoria.objects.create(
        autor_tipo=autor_tipo,
        autor_id=autor_id,
        acao=acao,
        momento=agora(),
        motivo=motivo or "",
        alteracoes=alteracoes,
        objeto_tipo=objeto._meta.label_lower,
        objeto_id=str(objeto.pk),
    )
