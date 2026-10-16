"""Conta, papéis e e-mails banidos (E02-01)."""

from typing import Any, ClassVar

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.functions import Lower, Trim

from apps.contas.emails import EmailInvalido, normalizar_email
from apps.fornecedores.models import Fornecedor
from apps.nucleo.so_insercao import RegistroSoInsercao
from apps.nucleo.tempo import agora


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
