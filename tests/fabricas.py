"""Fábricas de teste (factory-boy)."""

import hashlib
from datetime import timedelta
from decimal import Decimal

from allauth.account.models import EmailAddress
from factory.declarations import (
    LazyAttribute,
    LazyFunction,
    SelfAttribute,
    Sequence,
    SubFactory,
    Trait,
)
from factory.django import DjangoModelFactory
from factory.helpers import post_generation

from apps.catalogo.models import Produto, Unidade
from apps.contas.models import Conta, Convite, Papel, Situacao
from apps.fornecedores.models import Fornecedor
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.nucleo.tempo import agora
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada


class FornecedorFactory(DjangoModelFactory[Fornecedor]):
    class Meta:
        model = Fornecedor

    nome = Sequence(lambda n: f"Fornecedor {n}")
    email_pedido = Sequence(lambda n: f"pedidos{n}@fornecedor.example")
    minimo = Decimal("100.00")
    prazo_entrega_dias = 7


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


class RodadaFactory(DjangoModelFactory[Rodada]):
    """Rodada em `interesse` por padrão; `etapa=` cria já em outra etapa (sem transições ainda)."""

    class Meta:
        model = Rodada

    fornecedor = SubFactory(FornecedorFactory)
    etapa = Etapa.INTERESSE
    aberta_por = LazyFunction(_administrador_existente)


class ProdutoFactory(DjangoModelFactory[Produto]):
    """Produto em kg, incremento 1, preço R$ 10,00, sem múltiplo."""

    class Meta:
        model = Produto

    fornecedor = SubFactory(FornecedorFactory)
    nome = Sequence(lambda n: f"Produto {n}")
    descricao = ""
    unidade = Unidade.KG
    incremento = Decimal("1.000")
    preco = Decimal("10.00")
    multiplo = None
    disponivel = True


class ParcelaFactory(DjangoModelFactory[ParcelaDeInteresse]):
    """Parcela ativa de 1 unidade, toda reservada; informe situação e quantidades para variar."""

    class Meta:
        model = ParcelaDeInteresse

    comprador = SubFactory(ContaFactory)
    produto = SubFactory(ProdutoFactory)
    quantidade_original = Decimal("1.000")
    quantidade_reservada = Decimal("1.000")
    quantidade_pendente = Decimal("0.000")
    situacao = SituacaoParcela.ATIVA


class EstoqueDaRodadaFactory(DjangoModelFactory[EstoqueDaRodada]):
    """Produto na rodada com limite 10; o produto vem do mesmo fornecedor da rodada."""

    class Meta:
        model = EstoqueDaRodada

    rodada = SubFactory(RodadaFactory)
    produto = SubFactory(ProdutoFactory, fornecedor=SelfAttribute("..rodada.fornecedor"))
    limite = Decimal("10.000")
