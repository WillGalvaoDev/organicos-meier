"""Fábricas de teste (factory-boy)."""

from allauth.account.models import EmailAddress
from factory.declarations import LazyFunction, Sequence, Trait
from factory.django import DjangoModelFactory
from factory.helpers import post_generation

from apps.contas.models import Conta, Papel, Situacao
from apps.fornecedores.models import Fornecedor


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
