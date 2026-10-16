"""Conta, papéis e e-mails banidos (E02-01)."""

import hashlib
from datetime import timedelta
from typing import Any, ClassVar

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.functions import Lower, Trim

from apps.contas.emails import EmailInvalido, normalizar_email
from apps.fornecedores.models import Fornecedor
from apps.nucleo.so_insercao import RegistroSoInsercao
from apps.nucleo.tempo import agora, prazo_encerrado


class EmailEmUso(Exception):
    """Já existe uma conta com este e-mail. A mensagem não repete o endereço."""


class Papel(models.TextChoices):
    COMPRADOR = "comprador"
    FORNECEDOR = "fornecedor"
    ADMINISTRADOR = "administrador"


class Situacao(models.TextChoices):
    ATIVA = "ativa"
    SUSPENSA = "suspensa"
    REMOVIDA = "removida"


def _ja_normalizado() -> models.Q:
    """Condição do CHECK: e-mail igual à sua forma normalizada e não vazio."""
    return models.Q(email_normalizado=Lower(Trim("email_normalizado"))) & ~models.Q(
        email_normalizado=""
    )


class ContaManager(BaseUserManager["Conta"]):
    pass


class Conta(AbstractBaseUser):
    email_normalizado = models.CharField(max_length=254)
    nome = models.CharField(max_length=150)
    papel = models.CharField(max_length=15, choices=Papel.choices)
    situacao = models.CharField(max_length=10, choices=Situacao.choices, default=Situacao.ATIVA)
    fornecedor = models.ForeignKey(Fornecedor, null=True, blank=True, on_delete=models.PROTECT)
    criada_em = models.DateTimeField(default=agora)

    objects = ContaManager()

    USERNAME_FIELD = "email_normalizado"
    EMAIL_FIELD = "email_normalizado"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["nome"]

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["email_normalizado"], name="conta_email_unico"),
            models.CheckConstraint(condition=_ja_normalizado(), name="conta_email_ja_normalizado"),
            models.CheckConstraint(
                condition=models.Q(papel__in=["comprador", "fornecedor", "administrador"]),
                name="conta_papel_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(situacao__in=["ativa", "suspensa", "removida"]),
                name="conta_situacao_valida",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(papel="fornecedor", fornecedor__isnull=False)
                    | (~models.Q(papel="fornecedor") & models.Q(fornecedor__isnull=True))
                ),
                name="conta_fornecedor_vinculado",
            ),
            models.UniqueConstraint(
                fields=["papel"],
                condition=models.Q(papel="administrador"),
                name="conta_administrador_unico",
            ),
            models.CheckConstraint(
                condition=~models.Q(papel="administrador") | models.Q(situacao="ativa"),
                name="conta_administrador_ativo",
            ),
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self._state.adding and not self.password:
            self.set_unusable_password()  # a senha nasce no convite ou na recuperação

    def __str__(self) -> str:
        return self.nome

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        """Suspensa continua ativa para autenticar (§2); só a removida fica bloqueada."""
        return self.situacao != Situacao.REMOVIDA

    def clean(self) -> None:
        super().clean()
        self.nome = (self.nome or "").strip()
        if not self.nome:
            raise ValidationError({"nome": "Informe o nome."})
        try:
            self.email_normalizado = normalizar_email(self.email_normalizado)
        except EmailInvalido as erro:
            raise ValidationError({"email_normalizado": str(erro)}) from None

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email_normalizado = normalizar_email(self.email_normalizado)
        self.nome = (self.nome or "").strip()
        outras = Conta.objects.filter(email_normalizado=self.email_normalizado)
        if self.pk is not None:
            outras = outras.exclude(pk=self.pk)
        if outras.exists():
            raise EmailEmUso("já existe uma conta com este e-mail")
        try:
            with transaction.atomic():  # ponto de salvamento: não contamina a transação externa
                super().save(*args, **kwargs)
        except IntegrityError as erro:
            if "conta_email_unico" in str(erro):  # corrida: venceu a restrição do banco
                raise EmailEmUso("já existe uma conta com este e-mail") from erro
            raise


class EmailBanido(RegistroSoInsercao):
    """Banimento definitivo: o endereço normalizado nunca mais cadastra nem entra."""

    email_normalizado = models.CharField(max_length=254)
    banido_em = models.DateTimeField(default=agora)
    banido_por = models.ForeignKey(Conta, on_delete=models.PROTECT)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["email_normalizado"], name="emailbanido_email_unico"),
            models.CheckConstraint(condition=_ja_normalizado(), name="emailbanido_ja_normalizado"),
        )

    def __str__(self) -> str:
        return self.email_normalizado

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding:
            self.email_normalizado = normalizar_email(self.email_normalizado)
        super().save(*args, **kwargs)


class Convite(models.Model):
    """Convite individual, de uso único, com validade fixa de 24 horas (E02-04).

    O token em texto nunca é gravado: só o hash SHA-256 em hexadecimal.
    """

    email_normalizado = models.CharField(max_length=254)
    papel = models.CharField(max_length=15, choices=Papel.choices)
    fornecedor = models.ForeignKey(Fornecedor, null=True, blank=True, on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64)
    emitido_por = models.ForeignKey(
        Conta, on_delete=models.PROTECT, related_name="convites_emitidos"
    )
    emitido_em = models.DateTimeField(default=agora)
    expira_em = models.DateTimeField()
    consumido_em = models.DateTimeField(null=True, blank=True)
    conta_criada = models.ForeignKey(
        Conta, null=True, blank=True, on_delete=models.PROTECT, related_name="convite_de_origem"
    )

    # Preenchido por `emitir_convite` quando o envio já ocorreu (True/False); `None` se ainda
    # pendente (transação externa aberta). Não é coluna.
    email_enviado: bool | None = None

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["token_hash"], name="convite_token_unico"),
            models.CheckConstraint(
                condition=_ja_normalizado(), name="convite_email_ja_normalizado"
            ),
            models.CheckConstraint(
                condition=models.Q(papel__in=["comprador", "fornecedor"]),
                name="convite_papel_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(papel="fornecedor", fornecedor__isnull=False)
                    | (~models.Q(papel="fornecedor") & models.Q(fornecedor__isnull=True))
                ),
                name="convite_fornecedor_vinculado",
            ),
            models.CheckConstraint(
                condition=models.Q(expira_em=models.F("emitido_em") + timedelta(hours=24)),
                name="convite_validade_24h",
            ),
        )

    def __str__(self) -> str:
        return f"convite {self.pk}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding:
            self.email_normalizado = normalizar_email(self.email_normalizado)
        super().save(*args, **kwargs)

    @classmethod
    def hash_do_token(cls, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @property
    def situacao(self) -> str:
        """Derivada, sem coluna. No instante exato de `expira_em` o prazo já está encerrado."""
        if self.consumido_em is not None:
            return "consumido"
        if prazo_encerrado(agora(), self.expira_em):
            return "expirado"
        return "pendente"


class LinkDeAcesso(models.Model):
    """Link de acesso por e-mail (E02-06): uso único, 15 minutos. Só o hash do token é gravado."""

    conta = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="links_de_acesso")
    token_hash = models.CharField(max_length=64)
    criado_em = models.DateTimeField(default=agora)
    expira_em = models.DateTimeField()
    usado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["token_hash"], name="link_token_unico"),
            models.CheckConstraint(
                condition=models.Q(expira_em=models.F("criado_em") + timedelta(minutes=15)),
                name="link_validade_15min",
            ),
        )
        indexes = (models.Index(fields=["conta", "criado_em"], name="link_conta_criado_idx"),)

    def __str__(self) -> str:
        return f"link {self.pk}"

    @classmethod
    def hash_do_token(cls, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
