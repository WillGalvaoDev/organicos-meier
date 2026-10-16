"""E03-06: alteração do incremento (acceptance A-1 a A-9)."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import IncrementoInvalido
from apps.catalogo.servicos import IncrementoIncompativel, alterar_incremento
from apps.contas.models import Conta, Papel
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.models import Etapa
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, ParcelaFactory, ProdutoFactory, RodadaFactory

pytestmark = pytest.mark.django_db

D = Decimal
S = SituacaoParcela
MSG_QUANTIDADE = "O novo incremento não é compatível com quantidades já registradas deste produto."
MSG_MULTIPLO = "O múltiplo do produto não é divisível pelo novo incremento."
MENSAGEM = "As condições da rodada só podem ser alteradas na fase de interesse."
ETAPAS_CONGELADAS = [
    Etapa.FECHAMENTO,
    Etapa.FECHAMENTO_ENCERRADO,
    Etapa.PAGAMENTO,
    Etapa.AGUARDANDO_FORNECEDOR,
]


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _admin() -> Conta:
    return Conta.objects.filter(papel=Papel.ADMINISTRADOR).first() or ContaFactory.create(
        administrador=True
    )


def _url(produto: Produto) -> str:
    return f"/administracao/produtos/{produto.pk}/incremento/"


def _cenario_105(etapa: Etapa | None = Etapa.INTERESSE) -> tuple[Produto, list[ParcelaDeInteresse]]:
    """Incremento 0,5, múltiplo 3, reservadas 1,0 e 1,5 e uma pendente de 2,0."""
    produto = ProdutoFactory.create(incremento=D("0.500"), multiplo=D("3.000"))
    if etapa is not None:
        RodadaFactory.create(fornecedor=produto.fornecedor, etapa=etapa)
    parcelas = [
        ParcelaFactory.create(
            produto=produto, quantidade_original=D("1.0"), quantidade_reservada=D("1.0")
        ),
        ParcelaFactory.create(
            produto=produto, quantidade_original=D("1.5"), quantidade_reservada=D("1.5")
        ),
        ParcelaFactory.create(
            produto=produto,
            quantidade_original=D("2.0"),
            quantidade_reservada=D("0"),
            quantidade_pendente=D("2.0"),
            situacao=S.PENDENTE,
        ),
    ]
    return produto, parcelas


def _estado_das_parcelas() -> list[tuple[Any, ...]]:
    return list(
        ParcelaDeInteresse.objects.order_by("pk").values_list(
            "pk", "quantidade_original", "quantidade_reservada", "quantidade_pendente", "situacao"
        )
    )


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_incremento_compativel_e_aceito(admin_client: Client) -> None:  # A-1, cenário 105, T-48
    produto, _ = _cenario_105()
    antes = _estado_das_parcelas()
    resposta = admin_client.post(_url(produto), {"incremento": "0,25"})
    assert resposta.status_code == 302
    assert resposta["Location"] == f"/administracao/fornecedores/{produto.fornecedor_id}/"
    produto.refresh_from_db()
    assert produto.incremento == D("0.250")
    assert str(produto.incremento) == "0.250"
    assert _estado_das_parcelas() == antes
    entrada = EntradaAuditoria.objects.get(acao="produto.alterar_incremento")
    assert entrada.alteracoes == {"produto": produto.pk, "anterior": "0.500", "novo": "0.250"}


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_incremento_incompativel_com_reservada_e_recusado(
    admin_client: Client,
) -> None:  # A-2, cenário 106, T-48
    produto, _ = _cenario_105()
    antes = _estado_das_parcelas()
    with pytest.raises(IncrementoIncompativel, match=MSG_QUANTIDADE) as erro:
        alterar_incremento(_admin(), produto, "1")
    assert erro.value.codigo == "quantidade"
    resposta = admin_client.post(_url(produto), {"incremento": "1"})
    assert resposta.status_code == 200
    assert MSG_QUANTIDADE in resposta.content.decode()
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert _estado_das_parcelas() == antes
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_incremento_para_2_no_cenario_106_e_recusado(admin_client: Client) -> None:  # cenário 106
    produto, _ = _cenario_105()
    with pytest.raises(IncrementoIncompativel) as erro:
        alterar_incremento(_admin(), produto, "2")
    # a ordem dos passos (quantidades antes do múltiplo) faz a recusa sair como "quantidade"
    assert erro.value.codigo == "quantidade"
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_incremento_incompativel_com_o_multiplo_e_recusado(admin_client: Client) -> None:  # A-3
    produto, parcelas = _cenario_105()
    # só a pendente de 2,0 fica em uso: 2,0 é múltiplo de 2, mas o múltiplo 3 não é
    for parcela in parcelas[:2]:
        parcela.situacao = S.REMOVIDA
        parcela.quantidade_reservada = D("0")
        parcela.save(update_fields=["situacao", "quantidade_reservada"])
    with pytest.raises(IncrementoIncompativel, match=MSG_MULTIPLO) as erro:
        alterar_incremento(_admin(), produto, "2")
    assert erro.value.codigo == "multiplo"
    resposta = admin_client.post(_url(produto), {"incremento": "2"})
    assert resposta.status_code == 200
    assert MSG_MULTIPLO in resposta.content.decode()
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert EntradaAuditoria.objects.count() == 0


def test_pendente_da_fila_tambem_conta(admin_client: Client) -> None:  # A-4, Q-6
    produto = ProdutoFactory.create(incremento=D("0.250"), multiplo=None)
    RodadaFactory.create(fornecedor=produto.fornecedor)
    ParcelaFactory.create(
        produto=produto,
        quantidade_original=D("0.75"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("0.75"),
        situacao=S.PENDENTE,
    )
    with pytest.raises(IncrementoIncompativel) as erro:
        alterar_incremento(_admin(), produto, "0.5")
    assert erro.value.codigo == "quantidade"
    produto.refresh_from_db()
    assert produto.incremento == D("0.250")


@pytest.mark.parametrize("valor", ["0", "-1", "0,0001", "abc"])
def test_incremento_invalido_pela_tela(admin_client: Client, valor: str) -> None:  # A-5, R-8
    produto, _ = _cenario_105()
    resposta = admin_client.post(_url(produto), {"incremento": valor})
    assert resposta.status_code == 200
    assert "incremento" in resposta.context["form"].errors
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.parametrize("valor", ["0", "-1", "0.0001", "abc", 0.25, 1])
def test_incremento_invalido_pelo_servico(valor: Any) -> None:  # A-5
    produto, _ = _cenario_105()
    with pytest.raises(IncrementoInvalido):
        alterar_incremento(_admin(), produto, valor)
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("etapa", [*ETAPAS_CONGELADAS, None, Etapa.DISPONIVEL_PARA_RETIRADA])
def test_incremento_congelado(
    admin_client: Client, etapa: Etapa | None
) -> None:  # A-6, cenário 107
    produto, _ = _cenario_105(etapa)
    resposta = admin_client.post(_url(produto), {"incremento": "0,25"})
    assert resposta.status_code == 409
    assert MENSAGEM in resposta.content.decode()
    with pytest.raises(CondicoesCongeladas):
        alterar_incremento(_admin(), produto, "0.25")
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert EntradaAuditoria.objects.count() == 0


def test_get_fora_de_interesse_mostra_so_a_mensagem(admin_client: Client) -> None:
    produto, _ = _cenario_105(Etapa.PAGAMENTO)
    resposta = admin_client.get(_url(produto))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert MENSAGEM in html
    assert 'name="incremento"' not in html


def test_get_em_interesse_mostra_o_incremento_atual_e_o_formulario(admin_client: Client) -> None:
    produto, _ = _cenario_105()
    html = admin_client.get(_url(produto)).content.decode()
    assert 'name="incremento"' in html
    assert "0,5" in html
    assert "0,500" not in html


@pytest.mark.acceptance
def test_preco_continua_editavel_no_fechamento(admin_client: Client) -> None:  # A-7, cenário 107
    produto, _ = _cenario_105(Etapa.FECHAMENTO)
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/",
        {"nome": produto.nome, "descricao": "", "preco": "12,50", "disponivel": "on"},
    )
    assert resposta.status_code == 302
    produto.refresh_from_db()
    assert produto.preco == D("12.50")


def test_parcela_removida_nao_impede_a_mudanca(admin_client: Client) -> None:  # A-8
    produto = ProdutoFactory.create(incremento=D("0.500"), multiplo=D("3.000"))
    RodadaFactory.create(fornecedor=produto.fornecedor)
    ParcelaFactory.create(
        produto=produto,
        quantidade_original=D("1.5"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("0"),
        situacao=S.REMOVIDA,
    )
    resposta = admin_client.post(_url(produto), {"incremento": "1"})
    assert resposta.status_code == 302
    produto.refresh_from_db()
    assert produto.incremento == D("1.000")


def test_mesmo_valor_nao_grava_nem_audita(admin_client: Client) -> None:  # A-9
    produto, _ = _cenario_105()
    resposta = admin_client.post(_url(produto), {"incremento": "0,5"})
    assert resposta.status_code == 302
    assert EntradaAuditoria.objects.count() == 0
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")


def test_so_o_administrador_altera_o_incremento_pelo_servico() -> None:
    produto, _ = _cenario_105()
    comprador = ContaFactory.create()
    with pytest.raises(PermissionDenied):
        alterar_incremento(comprador, produto, "0.25")
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert EntradaAuditoria.objects.count() == 0


def test_leitura_das_parcelas_e_travada_em_ordem_de_sequencia() -> None:
    produto, _ = _cenario_105()
    with CaptureQueriesContext(connection) as consultas:
        alterar_incremento(_admin(), produto, "0.25")
    sqls = [c["sql"] for c in consultas if 'FROM "interesses_parcela"' in c["sql"]]
    assert sqls
    assert all("FOR UPDATE" in s and 'ORDER BY "interesses_parcela"."sequencia"' in s for s in sqls)


def test_incremento_ids_inexistentes_dao_404(admin_client: Client) -> None:
    assert admin_client.get("/administracao/produtos/999999/incremento/").status_code == 404
    assert admin_client.post("/administracao/produtos/999999/incremento/", {}).status_code == 404


def test_formulario_do_produto_aponta_para_a_tela_do_incremento(admin_client: Client) -> None:
    produto, _ = _cenario_105()
    html = admin_client.get(f"/administracao/produtos/{produto.pk}/").content.decode()
    assert _url(produto) in html
