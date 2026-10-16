"""Fábricas de teste (factory-boy)."""

from factory.declarations import LazyFunction, Sequence, Trait
from factory.django import DjangoModelFactory

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

    email_normalizado = Sequence(lambda n: f"conta{n}@exemplo.com")
    nome = Sequence(lambda n: f"Conta {n}")
    papel = Papel.COMPRADOR
    situacao = Situacao.ATIVA

    class Params:
        # O trait se chama `fornecedor`; por isso ele preenche `fornecedor_id` (e não
        # `fornecedor`), senão o factory-boy acusaria definição cíclica.
        fornecedor = Trait(
            papel=Papel.FORNECEDOR,
            fornecedor_id=LazyFunction(lambda: FornecedorFactory.create().pk),
        )
        administrador = Trait(papel=Papel.ADMINISTRADOR)
        suspensa = Trait(situacao=Situacao.SUSPENSA)
