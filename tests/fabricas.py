"""Fábricas de teste (factory-boy)."""

import hashlib
from datetime import timedelta

from allauth.account.models import EmailAddress
from factory.declarations import LazyAttribute, LazyFunction, Sequence, Trait
from factory.django import DjangoModelFactory
from factory.helpers import post_generation

from apps.contas.models import Conta, Convite, Papel, Situacao
from apps.fornecedores.models import Fornecedor
from apps.nucleo.tempo import agora


class FornecedorFactory(DjangoModelFactory[Fornecedor]):
    class Meta:
        model = Fornecedor

    nome = Sequence(lambda n: f"Fornecedor {n}")


class ContaFactory(DjangoModelFactory[Conta]):
    """Comprador por padrão. Traits: `fornecedor`, `administrador` e `suspensa`."""

    class Meta:
        model = Conta
        skip_postgeneration_save = True

    email_normalizado = Sequence(lambda n: f"conta{n}@exemplo.com")
    nome = Sequence(lambda n: f"Conta {n}")
    papel = Papel.COMPRADOR
    situacao = Situacao.ATIVA

    @post_generation  # type: ignore[untyped-decorator]
    def endereco_verificado(self, create: bool, extracted: object, **kwargs: object) -> None:
        """Conta criada já tem e-mail verificado e primário (exigido pelo allauth no login)."""
        if create:
            EmailAddress.objects.create(
                user=self, email=self.email_normalizado, verified=True, primary=True
            )

    class Params:
        # O trait se chama `fornecedor`; por isso ele preenche `fornecedor_id` (e não
        # `fornecedor`), senão o factory-boy acusaria definição cíclica.
        fornecedor = Trait(
            papel=Papel.FORNECEDOR,
            fornecedor_id=LazyFunction(lambda: FornecedorFactory.create().pk),
        )
        administrador = Trait(papel=Papel.ADMINISTRADOR)
        suspensa = Trait(situacao=Situacao.SUSPENSA)


def _administrador_existente() -> Conta:
    """Há um único administrador: as fábricas reaproveitam o que já existe."""
    return Conta.objects.filter(papel=Papel.ADMINISTRADOR).first() or ContaFactory.create(
        administrador=True
    )


class ConviteFactory(DjangoModelFactory[Convite]):
    """Convite de comprador pendente, emitido agora. Traits: `fornecedor` e `consumido`."""

    class Meta:
        model = Convite
        skip_postgeneration_save = True

    email_normalizado = Sequence(lambda n: f"convidado{n}@exemplo.com")
    papel = Papel.COMPRADOR
    token_hash = Sequence(lambda n: hashlib.sha256(f"token-{n}".encode()).hexdigest())
    emitido_por = LazyFunction(_administrador_existente)
    emitido_em = LazyFunction(agora)
    expira_em = LazyAttribute(lambda o: o.emitido_em + timedelta(hours=24))

    class Params:
        fornecedor = Trait(
            papel=Papel.FORNECEDOR,
            fornecedor_id=LazyFunction(lambda: FornecedorFactory.create().pk),
        )
        consumido = Trait(
            consumido_em=LazyAttribute(lambda o: o.emitido_em + timedelta(hours=1)),
            conta_criada=LazyAttribute(
                lambda o: ContaFactory.create(email_normalizado=o.email_normalizado)
            ),
        )
