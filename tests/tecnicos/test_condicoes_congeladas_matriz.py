"""E03-07: matriz consolidada do congelamento (acceptance A-9 e A-10; T-23, cenário 72).

Cada condição (mínimo, múltiplo, incremento, inclusão e alteração de estoque) é tentada em cada
situação em que não pode mudar, pela rota (com e sem `HX-Request`) e pelo serviço. O preço, que
fica fora do congelamento, é aceito nas quatro etapas ativas.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client

from apps.catalogo.models import Produto
from apps.catalogo.servicos import alterar_incremento, alterar_multiplo, editar_produto
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import CondicoesCongeladas, condicoes_editaveis
from apps.rodadas.estoque import alterar_estoque, incluir_produto_na_rodada
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada
from apps.rodadas.sinais import estoque_alterado
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import (
    ContaFactory,
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
    assert set(VALORES_DA_ROTA) == set(CONDICOES)
    assert set(VALORES_DO_SERVICO) == set(CONDICOES)
    for condicao in CONDICOES:
        assert set(VALORES_DA_ROTA[condicao]) == set(CLASSES_DE_VALOR), condicao
        assert VALORES_DO_SERVICO[condicao], condicao


# --- E03-R03: a fase prevalece sobre o valor (A-12, A-13) --------------------------------------

CLASSES_DE_VALOR = ("valido", "mal_formado", "sinal", "capacidade", "vazio")

# condição -> (campo do formulário, classe de valor -> textos enviados)
VALORES_DA_ROTA: dict[str, dict[str, list[str]]] = {
    "minimo": {
        "valido": ["200,00"],
        "mal_formado": ["abc"],
        "sinal": ["-1", "0"],
        "capacidade": ["10000000000,00"],
        "vazio": [""],
    },
    "multiplo": {
        "valido": ["6"],
        "mal_formado": ["abc"],
        "sinal": ["-1"],
        "capacidade": ["1000000000,000"],
        "vazio": [""],
    },
    "incremento": {
        "valido": ["0,25"],
        "mal_formado": ["abc"],
        "sinal": ["-1", "0"],
        "capacidade": ["1000000000,000"],
        "vazio": [""],
    },
    "incluir_estoque": {
        "valido": ["5"],
        "mal_formado": ["abc"],
        "sinal": ["-1"],
        "capacidade": ["1000000000,000"],
        "vazio": [""],
    },
    "alterar_estoque": {
        "valido": ["8"],
        "mal_formado": ["abc"],
        "sinal": ["-1"],
        "capacidade": ["1000000000,000"],
        "vazio": [""],
    },
}
CAMPO_DO_VALOR = {
    "minimo": "minimo",
    "multiplo": "multiplo",
    "incremento": "incremento",
    "incluir_estoque": "limite",
    "alterar_estoque": "limite",
}
# o serviço recebe valores mal formados, de sinal e de capacidade (e vazio)
VALORES_DO_SERVICO: dict[str, list[Any]] = {
    "minimo": ["abc", D("0"), "-1", D("10000000000.00"), ""],
    "multiplo": ["abc", "-1", D("1000000000.000")],
    "incremento": ["abc", "0", "-1", D("1000000000.000")],
    "incluir_estoque": ["abc", "-1", D("1000000000.000")],
    "alterar_estoque": ["abc", "-1", D("1000000000.000")],
}
URLS_DA_CONDICAO: dict[str, Callable[[Contexto], tuple[str, dict[str, str]]]] = {
    "minimo": lambda c: (f"/administracao/fornecedores/{c.fornecedor.pk}/minimo/", {}),
    "multiplo": lambda c: (f"/administracao/produtos/{c.produto.pk}/multiplo/", {}),
    "incremento": lambda c: (f"/administracao/produtos/{c.produto.pk}/incremento/", {}),
    "incluir_estoque": lambda c: (
        f"/administracao/rodadas/{c.rodada.pk}/estoque/incluir/",
        {"produto": str(c.fora.pk)},
    ),
    "alterar_estoque": lambda c: (f"/administracao/estoque/{c.estoque.pk}/alterar/", {}),
}
SERVICOS_COM_VALOR: dict[str, Callable[[Conta, Contexto, Any], Any]] = {
    "minimo": lambda a, c, v: alterar_minimo(a, c.fornecedor, v),
    "multiplo": lambda a, c, v: alterar_multiplo(a, c.produto, v),
    "incremento": lambda a, c, v: alterar_incremento(a, c.produto, v),
    "incluir_estoque": lambda a, c, v: incluir_produto_na_rodada(a, c.rodada, c.fora, v),
    "alterar_estoque": lambda a, c, v: alterar_estoque(a, c.estoque, v),
}


@pytest.fixture
def sinais_do_estoque() -> Iterator[list[Any]]:
    recebidos: list[Any] = []

    def ouvir(sender: Any, **kwargs: Any) -> None:
        recebidos.append(kwargs)

    estoque_alterado.connect(ouvir, weak=False)
    yield recebidos
    estoque_alterado.disconnect(ouvir)


@pytest.mark.acceptance
@pytest.mark.parametrize("situacao", SITUACOES)
@pytest.mark.parametrize("condicao", list(CONDICOES))
def test_a_fase_prevalece_sobre_o_valor_pela_rota(
    admin_client: Client, sinais_do_estoque: list[Any], condicao: str, situacao: Etapa
) -> None:  # A-12, E03-R03, T-23, cenário 72
    contexto = _contexto(situacao)
    antes = _estado(contexto)
    url, fixos = URLS_DA_CONDICAO[condicao](contexto)
    campo = CAMPO_DO_VALOR[condicao]
    for classe, textos in VALORES_DA_ROTA[condicao].items():
        for texto in textos:
            extras: list[dict[str, Any]] = [{}, HTMX]
            for extra in extras:
                resposta = admin_client.post(url, {**fixos, campo: texto}, **extra)
                where = (condicao, situacao, classe, texto, extra)
                assert resposta.status_code == 409, where
                corpo = resposta.content.decode()
                assert MENSAGEM in corpo, where
                assert f'name="{campo}"' not in corpo, where
    assert _estado(contexto) == antes
    assert EntradaAuditoria.objects.count() == 0
    assert sinais_do_estoque == []


@pytest.mark.acceptance
@pytest.mark.parametrize("situacao", SITUACOES)
@pytest.mark.parametrize("condicao", list(CONDICOES))
def test_a_fase_prevalece_sobre_o_valor_pelo_servico(
    sinais_do_estoque: list[Any], condicao: str, situacao: Etapa
) -> None:  # A-13, E03-R03
    admin = ContaFactory.create(administrador=True)
    contexto = _contexto(situacao)
    antes = _estado(contexto)
    for valor in VALORES_DO_SERVICO[condicao]:
        with pytest.raises(CondicoesCongeladas):
            SERVICOS_COM_VALOR[condicao](admin, contexto, valor)
    assert _estado(contexto) == antes
    assert EntradaAuditoria.objects.count() == 0
    assert sinais_do_estoque == []


def test_condicoes_editaveis_so_com_rodada_em_interesse() -> None:  # E03-R03
    fornecedor = FornecedorFactory.create()
    assert condicoes_editaveis(fornecedor) is False
    RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.CANCELADA)
    assert condicoes_editaveis(fornecedor) is False
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.INTERESSE)
    assert condicoes_editaveis(fornecedor) is True
    for etapa in ETAPAS_ATIVAS_CONGELADAS:
        Rodada.objects.filter(pk=rodada.pk).update(etapa=etapa)
        assert condicoes_editaveis(fornecedor) is False, etapa


def test_em_interesse_o_erro_de_valor_continua_200(admin_client: Client) -> None:
    contexto = _contexto(Etapa.INTERESSE)
    url, _ = URLS_DA_CONDICAO["minimo"](contexto)
    resposta = admin_client.post(url, {"minimo": "10000000000,00"})
    assert resposta.status_code == 200
    assert 'value="10000000000,00"' in resposta.content.decode()


@pytest.fixture
def admin(client: Client, webauthn: Any) -> Client:
    # fixture do probe literal do revisor (docs/specs/E03-08/review.md, revalidação de 2e7bbcc)
    cache.clear()
    administrador_logado(client)
    return client


@pytest.mark.parametrize(
    "etapa", ["fechamento", "fechamento_encerrado", "pagamento", "aguardando_fornecedor"]
)
def test_minimo_excedente_fora_de_interesse_responde_409(
    admin: Client, etapa: str
) -> None:  # probe do revisor
    f = FornecedorFactory.create(minimo=Decimal("150"))
    RodadaFactory.create(fornecedor=f, etapa=etapa)
    resposta = admin.post(
        f"/administracao/fornecedores/{f.pk}/minimo/", {"minimo": "10000000000.00"}
    )
    f.refresh_from_db()
    assert f.minimo == Decimal("150")
    assert resposta.status_code == 409
