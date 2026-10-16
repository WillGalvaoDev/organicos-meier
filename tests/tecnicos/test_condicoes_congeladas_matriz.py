"""E03-07: matriz consolidada do congelamento (acceptance A-9 e A-10; T-23, cenário 72).

Cada condição (mínimo, múltiplo, incremento, inclusão e alteração de estoque) é tentada em cada
situação em que não pode mudar, pela rota (com e sem `HX-Request`) e pelo serviço. O preço, que
fica fora do congelamento, é aceito nas quatro etapas ativas.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.catalogo.models import Produto
from apps.catalogo.servicos import alterar_incremento, alterar_multiplo, editar_produto
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.estoque import alterar_estoque, incluir_produto_na_rodada
from apps.rodadas.models import EstoqueDaRodada, Etapa
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import (
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = [pytest.mark.django_db, pytest.mark.tecnico]

D = Decimal
HTMX: Any = {"HTTP_HX_REQUEST": "true"}
MENSAGEM = "As condições da rodada só podem ser alteradas na fase de interesse."

SITUACOES = [
    Etapa.FECHAMENTO,
    Etapa.FECHAMENTO_ENCERRADO,
    Etapa.PAGAMENTO,
    Etapa.AGUARDANDO_FORNECEDOR,
    Etapa.DISPONIVEL_PARA_RETIRADA,
    Etapa.CANCELADA,
]
ETAPAS_ATIVAS_CONGELADAS = SITUACOES[:4]


@dataclass
class Contexto:
    fornecedor: Fornecedor
    rodada: Any
    produto: Produto
    fora: Produto
    estoque: EstoqueDaRodada


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _contexto(etapa: Etapa) -> Contexto:
    fornecedor = FornecedorFactory.create(minimo=D("150.00"))
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=etapa)
    produto = ProdutoFactory.create(
        fornecedor=fornecedor, incremento=D("0.500"), multiplo=D("3.000")
    )
    fora = ProdutoFactory.create(fornecedor=fornecedor)
    estoque = EstoqueDaRodadaFactory.create(rodada=rodada, produto=produto, limite=D("10"))
    return Contexto(fornecedor, rodada, produto, fora, estoque)


def _admin() -> Conta:
    return Conta.objects.get(papel=Papel.ADMINISTRADOR)


# condição -> (rota e dados, chamada ao serviço)
Rota = Callable[[Contexto], tuple[str, dict[str, str]]]
Servico = Callable[[Conta, Contexto], Any]

CONDICOES: dict[str, tuple[Rota, Servico]] = {
    "minimo": (
        lambda c: (f"/administracao/fornecedores/{c.fornecedor.pk}/minimo/", {"minimo": "200,00"}),
        lambda a, c: alterar_minimo(a, c.fornecedor, "200,00"),
    ),
    "multiplo": (
        lambda c: (f"/administracao/produtos/{c.produto.pk}/multiplo/", {"multiplo": "6"}),
        lambda a, c: alterar_multiplo(a, c.produto, "6"),
    ),
    "incremento": (
        lambda c: (f"/administracao/produtos/{c.produto.pk}/incremento/", {"incremento": "0,25"}),
        lambda a, c: alterar_incremento(a, c.produto, "0.25"),
    ),
    "incluir_estoque": (
        lambda c: (
            f"/administracao/rodadas/{c.rodada.pk}/estoque/incluir/",
            {"produto": str(c.fora.pk), "limite": "5"},
        ),
        lambda a, c: incluir_produto_na_rodada(a, c.rodada, c.fora, "5"),
    ),
    "alterar_estoque": (
        lambda c: (f"/administracao/estoque/{c.estoque.pk}/alterar/", {"limite": "8"}),
        lambda a, c: alterar_estoque(a, c.estoque, "8"),
    ),
}


def _estado(c: Contexto) -> tuple[Any, ...]:
    c.fornecedor.refresh_from_db()
    c.produto.refresh_from_db()
    c.estoque.refresh_from_db()
    return (
        c.fornecedor.minimo,
        c.produto.multiplo,
        c.produto.incremento,
        c.estoque.limite,
        EstoqueDaRodada.objects.count(),
    )


@pytest.mark.acceptance
@pytest.mark.parametrize("situacao", SITUACOES)
@pytest.mark.parametrize("condicao", list(CONDICOES))
def test_nenhuma_condicao_muda_fora_de_interesse(
    admin_client: Client, condicao: str, situacao: Etapa
) -> None:  # A-9, T-23, cenário 72
    contexto = _contexto(situacao)
    rota, servico = CONDICOES[condicao]
    antes = _estado(contexto)
    url, dados = rota(contexto)
    extras: list[dict[str, Any]] = [{}, HTMX]
    for extra in extras:
        resposta = admin_client.post(url, dados, **extra)
        assert resposta.status_code == 409, (condicao, situacao, extra)
        assert MENSAGEM in resposta.content.decode()
    with pytest.raises(CondicoesCongeladas):
        servico(_admin(), contexto)
    assert _estado(contexto) == antes
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.acceptance
@pytest.mark.parametrize("etapa", ETAPAS_ATIVAS_CONGELADAS)
def test_preco_muda_nas_quatro_etapas_ativas(
    admin_client: Client, etapa: Etapa
) -> None:  # A-10, T-23, cenário 72, §5.1
    contexto = _contexto(etapa)
    resposta = admin_client.post(
        f"/administracao/produtos/{contexto.produto.pk}/",
        {
            "nome": contexto.produto.nome,
            "descricao": "",
            "preco": "12,50",
            "disponivel": "on",
        },
    )
    assert resposta.status_code == 302
    contexto.produto.refresh_from_db()
    assert contexto.produto.preco == D("12.50")
    editar_produto(_admin(), contexto.produto, preco="13.00")
    contexto.produto.refresh_from_db()
    assert contexto.produto.preco == D("13.00")


def test_a_matriz_cobre_as_cinco_condicoes_e_as_seis_situacoes() -> None:
    assert set(CONDICOES) == {
        "minimo",
        "multiplo",
        "incremento",
        "incluir_estoque",
        "alterar_estoque",
    }
    assert len(SITUACOES) == 6
