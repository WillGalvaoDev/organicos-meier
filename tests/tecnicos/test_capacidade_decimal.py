"""E03-R01: entrada acima da capacidade das colunas decimais vira erro de campo, nunca HTTP 500.

Cobre E03-01 (A-18 a A-20), E03-03 (A-24 a A-28), E03-05 (A-20 e A-21) e E03-06 (A-15); o
critério A-19 da E03-02 fica em `test_rodadas_minimo.py`. O fim do arquivo traz, literalmente, o
script de probes do revisor (`docs/specs/E03-08/review.md`).
"""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import (
    IncrementoInvalido,
    MultiploInvalido,
    QuantidadeInvalida,
    validar_incremento,
    validar_multiplo,
    validar_quantidade,
)
from apps.catalogo.servicos import (
    alterar_incremento,
    alterar_multiplo,
    criar_produto,
    editar_produto,
)
from apps.catalogo.sinais import preco_alterado
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import criar_fornecedor
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.valores import (
    MAIOR_DINHEIRO,
    MAIOR_QUANTIDADE,
    CampoDinheiro,
    CampoQuantidade,
    ValorInvalido,
    cabe_em_dinheiro,
    cabe_em_quantidade,
)
from apps.rodadas.estoque import alterar_estoque, incluir_produto_na_rodada
from apps.rodadas.models import EstoqueDaRodada
from apps.rodadas.sinais import estoque_alterado
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ProdutoFactory,
    RodadaFactory,
)

D = Decimal
MSG_DINHEIRO = "O valor máximo aceito é R$ 9.999.999.999,99."
MSG_QUANTIDADE = "O valor máximo aceito é 999999999,999."
ACIMA_DINHEIRO = D("10000000000.00")
ACIMA_QUANTIDADE = D("1000000000.000")


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _admin() -> Conta:
    return Conta.objects.filter(papel=Papel.ADMINISTRADOR).first() or ContaFactory.create(
        administrador=True
    )


# --- E03-01, A-18: primitivas -----------------------------------------------------------------


@pytest.mark.tecnico
def test_constantes_derivam_das_colunas() -> None:  # A-18
    dinheiro, quantidade = CampoDinheiro(), CampoQuantidade()
    esperado_dinheiro = D(10) ** (dinheiro.max_digits - dinheiro.decimal_places) - D(10) ** -(
        dinheiro.decimal_places
    )
    esperado_quantidade = D(10) ** (quantidade.max_digits - quantidade.decimal_places) - D(10) ** -(
        quantidade.decimal_places
    )
    assert MAIOR_DINHEIRO == esperado_dinheiro == D("9999999999.99")
    assert MAIOR_QUANTIDADE == esperado_quantidade == D("999999999.999")


@pytest.mark.tecnico
def test_cabe_nos_limites_e_nao_cabe_acima() -> None:  # A-18
    assert cabe_em_dinheiro(D("9999999999.99")) is True
    assert cabe_em_dinheiro(ACIMA_DINHEIRO) is False
    assert cabe_em_dinheiro(D("0.01")) is True
    assert cabe_em_quantidade(D("999999999.999")) is True
    assert cabe_em_quantidade(ACIMA_QUANTIDADE) is False
    assert cabe_em_quantidade(D("0.001")) is True


@pytest.mark.tecnico
@pytest.mark.parametrize("funcao", [cabe_em_dinheiro, cabe_em_quantidade])
@pytest.mark.parametrize("invalido", [1.5, 1, True, "1.00", None, D("NaN"), D("Infinity")])
def test_cabe_recusa_tipos_e_valores_nao_finitos(funcao: Any, invalido: Any) -> None:  # A-18
    with pytest.raises(ValorInvalido):
        funcao(invalido)


@pytest.mark.tecnico
def test_cabe_nao_altera_o_valor_recebido() -> None:  # A-18
    valor = D("12345678901.234567")
    copia = D("12345678901.234567")
    assert cabe_em_quantidade(valor) is False
    assert valor == copia
    assert valor.as_tuple() == copia.as_tuple()


# --- E03-01, A-19 e A-20: cadastro de fornecedor ----------------------------------------------


@pytest.mark.django_db
@pytest.mark.tecnico
def test_criar_fornecedor_no_limite_e_acima() -> None:  # A-19
    admin = _admin()
    fornecedor = criar_fornecedor(
        admin,
        nome="No limite",
        email_pedido="a@x.com",
        minimo=D("9999999999.99"),
        prazo_entrega_dias=7,
    )
    assert fornecedor.minimo == D("9999999999.99")
    auditorias = EntradaAuditoria.objects.count()
    with pytest.raises(ValidationError) as erro:
        criar_fornecedor(
            admin, nome="Acima", email_pedido="b@x.com", minimo=ACIMA_DINHEIRO, prazo_entrega_dias=7
        )
    assert erro.value.message_dict == {"minimo": [MSG_DINHEIRO]}
    assert Fornecedor.objects.count() == 1
    assert EntradaAuditoria.objects.count() == auditorias


@pytest.mark.django_db
@pytest.mark.tecnico
@pytest.mark.parametrize("digitado", ["10000000000,00", "10000000000.00", "9" * 30])
def test_cadastro_pela_rota_com_minimo_acima_da_capacidade(
    admin_client: Client, digitado: str
) -> None:  # A-20
    resposta = admin_client.post(
        "/administracao/fornecedores/novo/",
        {
            "nome": "Acima",
            "email_pedido": "a@x.com",
            "minimo": digitado,
            "prazo_entrega_dias": "7",
        },
    )
    assert resposta.status_code == 200
    erros = resposta.context["form"].errors
    assert "minimo" in erros
    if len(digitado) < 30:
        assert MSG_DINHEIRO in erros["minimo"]
    assert digitado in resposta.content.decode()
    assert Fornecedor.objects.count() == 0


# --- E03-02, A-19 está em test_rodadas_minimo.py -----------------------------------------------

# --- E03-03, A-24 a A-28: produto --------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.tecnico
def test_criar_produto_com_preco_no_limite_e_acima(admin_client: Client) -> None:  # A-24
    admin = _admin()
    fornecedor = FornecedorFactory.create()
    produto = criar_produto(
        admin,
        fornecedor,
        nome="Caro",
        unidade="kg",
        incremento="1",
        preco=D("9999999999.99"),
    )
    assert produto.preco == D("9999999999.99")
    auditorias = EntradaAuditoria.objects.count()
    with pytest.raises(ValidationError) as erro:
        criar_produto(
            admin, fornecedor, nome="Mais", unidade="kg", incremento="1", preco=ACIMA_DINHEIRO
        )
    assert erro.value.message_dict == {"preco": [MSG_DINHEIRO]}
    resposta = admin_client.post(
        f"/administracao/fornecedores/{fornecedor.pk}/produtos/novo/",
        {"nome": "Mais", "unidade": "kg", "incremento": "1", "preco": "10000000000,00"},
    )
    assert resposta.status_code == 200
    assert MSG_DINHEIRO in resposta.context["form"].errors["preco"]
    assert Produto.objects.count() == 1
    assert EntradaAuditoria.objects.count() == auditorias


@pytest.mark.django_db
@pytest.mark.tecnico
def test_editar_produto_com_preco_acima_nao_grava_nada(admin_client: Client) -> None:  # A-25
    produto = ProdutoFactory.create(nome="Antigo", preco=D("7.99"))
    chamadas: list[Any] = []

    def receptor(sender: Any, **kwargs: Any) -> None:
        chamadas.append(kwargs)

    preco_alterado.connect(receptor, weak=False)
    try:
        with pytest.raises(ValidationError) as erro:
            editar_produto(_admin(), produto, nome="Novo", preco=ACIMA_DINHEIRO)
        assert erro.value.message_dict == {"preco": [MSG_DINHEIRO]}
        resposta = admin_client.post(
            f"/administracao/produtos/{produto.pk}/",
            {"nome": "Novo", "descricao": "", "preco": "10000000000,00", "disponivel": "on"},
        )
    finally:
        preco_alterado.disconnect(receptor)
    assert resposta.status_code == 200
    assert MSG_DINHEIRO in resposta.context["form"].errors["preco"]
    produto.refresh_from_db()
    assert (produto.nome, produto.preco) == ("Antigo", D("7.99"))
    assert EntradaAuditoria.objects.count() == 0
    assert chamadas == []


@pytest.mark.tecnico
def test_validar_incremento_e_multiplo_no_limite_e_acima() -> None:  # A-26
    assert validar_incremento("999999999.999") == D("999999999.999")
    assert validar_multiplo("999999999", D("1")) == D("999999999.000")
    with pytest.raises(IncrementoInvalido, match=r"999999999,999\."):
        validar_incremento("1000000000.000")
    with pytest.raises(MultiploInvalido, match=r"999999999,999\."):
        validar_multiplo("1000000000.000", D("1"))
    with pytest.raises(IncrementoInvalido) as erro:
        validar_incremento(ACIMA_QUANTIDADE)
    assert str(erro.value) == MSG_QUANTIDADE


@pytest.mark.django_db
@pytest.mark.tecnico
def test_incremento_e_multiplo_acima_pela_rota_e_pelo_servico(admin_client: Client) -> None:  # A-27
    fornecedor = FornecedorFactory.create()
    resposta = admin_client.post(
        f"/administracao/fornecedores/{fornecedor.pk}/produtos/novo/",
        {"nome": "X", "unidade": "kg", "incremento": "1000000000,000", "preco": "1,00"},
    )
    assert resposta.status_code == 200
    assert MSG_QUANTIDADE in resposta.context["form"].errors["incremento"]
    assert Produto.objects.count() == 0
    produto = ProdutoFactory.create(fornecedor=fornecedor, incremento=D("1"), multiplo=D("12"))
    RodadaFactory.create(fornecedor=fornecedor)
    with pytest.raises(MultiploInvalido, match=r"999999999,999\."):
        alterar_multiplo(_admin(), produto, "1000000000")
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/multiplo/", {"multiplo": "1000000000"}
    )
    assert resposta.status_code == 200
    assert MSG_QUANTIDADE in resposta.context["form"].errors["multiplo"]
    produto.refresh_from_db()
    assert produto.multiplo == D("12.000")
    assert EntradaAuditoria.objects.filter(acao="produto.alterar_multiplo").count() == 0


@pytest.mark.django_db
@pytest.mark.tecnico
def test_validar_quantidade_no_limite_e_acima() -> None:  # A-28
    produto = ProdutoFactory.build(incremento=D("1"))
    assert validar_quantidade(produto, "999999999") == D("999999999.000")
    with pytest.raises(QuantidadeInvalida) as erro:
        validar_quantidade(produto, "1000000000")
    assert str(erro.value) == MSG_QUANTIDADE


# --- E03-05, A-20 e A-21: estoque --------------------------------------------------------------


@pytest.fixture
def receptor_de_estoque() -> Iterator[list[Any]]:
    chamadas: list[Any] = []

    def ouvir(sender: Any, **kwargs: Any) -> None:
        chamadas.append(kwargs)

    estoque_alterado.connect(ouvir, weak=False)
    yield chamadas
    estoque_alterado.disconnect(ouvir)


@pytest.mark.django_db
@pytest.mark.tecnico
def test_inclusao_de_estoque_no_limite_e_acima(
    admin_client: Client, receptor_de_estoque: list[Any]
) -> None:  # A-20
    rodada = RodadaFactory.create()
    primeiro = ProdutoFactory.create(fornecedor=rodada.fornecedor)
    segundo = ProdutoFactory.create(fornecedor=rodada.fornecedor)
    admin = _admin()
    estoque = incluir_produto_na_rodada(admin, rodada, primeiro, "999999999.999")
    assert estoque.limite == D("999999999.999")
    assert len(receptor_de_estoque) == 1
    auditorias = EntradaAuditoria.objects.count()
    with pytest.raises(ValidationError, match=r"999999999,999\."):
        incluir_produto_na_rodada(admin, rodada, segundo, ACIMA_QUANTIDADE)
    resposta = admin_client.post(
        f"/administracao/rodadas/{rodada.pk}/estoque/incluir/",
        {"produto": str(segundo.pk), "limite": "1000000000,000"},
    )
    assert resposta.status_code == 200
    assert MSG_QUANTIDADE in resposta.content.decode()
    assert not EstoqueDaRodada.objects.filter(produto=segundo).exists()
    assert EntradaAuditoria.objects.count() == auditorias
    assert len(receptor_de_estoque) == 1


@pytest.mark.django_db
@pytest.mark.tecnico
def test_alteracao_de_estoque_no_limite_e_acima(
    admin_client: Client, receptor_de_estoque: list[Any]
) -> None:  # A-21
    estoque = EstoqueDaRodadaFactory.create(limite=D("10"))
    admin = _admin()
    alterar_estoque(admin, estoque, "999999999.999")
    estoque.refresh_from_db()
    assert estoque.limite == D("999999999.999")
    assert len(receptor_de_estoque) == 1
    auditorias = EntradaAuditoria.objects.count()
    with pytest.raises(ValidationError, match=r"999999999,999\."):
        alterar_estoque(admin, estoque, ACIMA_QUANTIDADE)
    resposta = admin_client.post(
        f"/administracao/estoque/{estoque.pk}/alterar/", {"limite": "1000000000,000"}
    )
    assert resposta.status_code == 200
    assert MSG_QUANTIDADE in resposta.content.decode()
    estoque.refresh_from_db()
    assert estoque.limite == D("999999999.999")
    assert EntradaAuditoria.objects.count() == auditorias
    assert len(receptor_de_estoque) == 1


# --- E03-06, A-15: incremento ------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.tecnico
def test_alterar_incremento_no_limite_e_acima(admin_client: Client) -> None:  # A-15
    produto = ProdutoFactory.create(incremento=D("1"), multiplo=None)
    RodadaFactory.create(fornecedor=produto.fornecedor)
    admin = _admin()
    alterar_incremento(admin, produto, "999999999.999")
    produto.refresh_from_db()
    assert produto.incremento == D("999999999.999")
    auditorias = EntradaAuditoria.objects.count()
    with pytest.raises(IncrementoInvalido) as erro:
        alterar_incremento(admin, produto, "1000000000.000")
    assert str(erro.value) == MSG_QUANTIDADE
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/incremento/", {"incremento": "1000000000,000"}
    )
    assert resposta.status_code == 200
    assert MSG_QUANTIDADE in resposta.context["form"].errors["incremento"]
    produto.refresh_from_db()
    assert produto.incremento == D("999999999.999")
    assert EntradaAuditoria.objects.count() == auditorias


# --- script de probes do revisor (literal, docs/specs/E03-08/review.md) -------------------------
from decimal import Decimal as D  # noqa: E402

import pytest  # noqa: E402
from django.core.cache import cache  # noqa: E402

from tests.apoio.admin_fluxos import administrador_logado  # noqa: E402, F811
from tests.apoio.webauthn_falso import instalar  # noqa: E402
from tests.fabricas import (  # noqa: E402, F811
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ProdutoFactory,
    RodadaFactory,
)


@pytest.mark.tecnico
@pytest.mark.django_db
@pytest.mark.parametrize("excede", [False, True])
@pytest.mark.parametrize(
    "caso",
    [
        "fornecedor",
        "minimo",
        "preco",
        "cadastro_incremento",
        "incremento",
        "multiplo",
        "incluir_estoque",
        "alterar_estoque",
    ],
)
def test_entrada_acima_da_capacidade_vira_erro_de_campo(client, monkeypatch, caso, excede):  # type: ignore[no-untyped-def]
    cache.clear()
    instalar(monkeypatch)
    administrador_logado(client)
    f = FornecedorFactory.create()
    p = ProdutoFactory.create(fornecedor=f, incremento=D("1"), multiplo=None)
    r = RodadaFactory.create(fornecedor=f)
    e = EstoqueDaRodadaFactory.create(rodada=r, produto=p, limite=D("10"))
    q = ProdutoFactory.create(fornecedor=f)
    casos = {
        "fornecedor": (
            "/administracao/fornecedores/novo/",
            {
                "nome": "Teste",
                "email_pedido": "teste@example.com",
                "prazo_entrega_dias": "7",
                "minimo": "10000000000.00",
            },
        ),
        "minimo": (f"/administracao/fornecedores/{f.pk}/minimo/", {"minimo": "10000000000.00"}),
        "preco": (
            f"/administracao/produtos/{p.pk}/",
            {"nome": p.nome, "preco": "10000000000.00", "disponivel": "on"},
        ),
        "cadastro_incremento": (
            f"/administracao/fornecedores/{f.pk}/produtos/novo/",
            {
                "nome": "Teste",
                "unidade": "kg",
                "preco": "1.00",
                "incremento": "1000000000.000",
                "disponivel": "on",
            },
        ),
        "incremento": (
            f"/administracao/produtos/{p.pk}/incremento/",
            {"incremento": "1000000000.000"},
        ),
        "multiplo": (
            f"/administracao/produtos/{p.pk}/multiplo/",
            {"multiplo": "1000000000.000"},
        ),
        "incluir_estoque": (
            f"/administracao/rodadas/{r.pk}/estoque/incluir/",
            {"produto": str(q.pk), "limite": "1000000000.000"},
        ),
        "alterar_estoque": (
            f"/administracao/estoque/{e.pk}/alterar/",
            {"limite": "1000000000.000"},
        ),
    }
    url, dados = casos[caso]
    if not excede:
        dados = {
            k: v.replace("10000000000.00", "9999999999.99").replace(
                "1000000000.000", "999999999.999"
            )
            for k, v in dados.items()
        }
        if caso == "multiplo":
            dados["multiplo"] = "999999999.000"
    client.raise_request_exception = False
    resposta = client.post(url, dados)
    assert resposta.status_code == (200 if excede else 302), (
        caso,
        resposta.status_code,
        resposta.exc_info[1] if resposta.exc_info else None,
    )
