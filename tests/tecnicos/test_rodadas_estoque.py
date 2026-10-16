"""E03-05: estoque por rodada (acceptance A-1 a A-14 e A-19)."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.transaction import TransactionManagementError
from django.test import Client

from apps.catalogo.models import Produto
from apps.contas.models import Conta
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.estoque import (
    EstoqueAbaixoDoReservado,
    alterar_estoque,
    estoque_livre,
    incluir_produto_na_rodada,
    travar_estoque,
)
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada
from apps.rodadas.sinais import estoque_alterado
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal
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


@pytest.fixture
def admin() -> Conta:
    return ContaFactory.create(administrador=True)


@pytest.fixture
def receptor() -> Iterator[list[tuple[Any, Any, Any, bool]]]:
    chamadas: list[tuple[Any, Any, Any, bool]] = []

    def ouvir(sender: Any, estoque: EstoqueDaRodada, anterior: Any, novo: Any, **kw: Any) -> None:
        chamadas.append((estoque, anterior, novo, connection.in_atomic_block))

    estoque_alterado.connect(ouvir, weak=False)
    yield chamadas
    estoque_alterado.disconnect(ouvir)


def _com_reserva(estoque: EstoqueDaRodada, reservado: str) -> None:
    ParcelaFactory.create(
        produto=estoque.produto,
        quantidade_original=D(reservado),
        quantidade_reservada=D(reservado),
    )


def _estoque(rodada: Rodada | None = None, limite: str | None = "10") -> EstoqueDaRodada:
    kwargs: dict[str, Any] = {"limite": None if limite is None else D(limite)}
    if rodada is not None:
        kwargs["rodada"] = rodada
    return EstoqueDaRodadaFactory.create(**kwargs)


def test_inclusao_com_e_sem_limite_pela_tela(admin_client: Client) -> None:  # A-1
    rodada = RodadaFactory.create()
    com, sem = (ProdutoFactory.create(fornecedor=rodada.fornecedor) for _ in range(2))
    url = f"/administracao/rodadas/{rodada.pk}/estoque/incluir/"
    for produto, limite in ((com, "10"), (sem, "")):
        resposta = admin_client.post(url, {"produto": str(produto.pk), "limite": limite})
        assert resposta.status_code == 302
        assert resposta["Location"] == f"/administracao/rodadas/{rodada.pk}/estoque/"
    assert EstoqueDaRodada.objects.get(produto=com).limite == D("10.000")
    assert EstoqueDaRodada.objects.get(produto=sem).limite is None
    entradas = {
        e.alteracoes["produto"]: e.alteracoes
        for e in EntradaAuditoria.objects.filter(acao="estoque.incluir")
    }
    assert entradas[com.pk] == {"rodada": rodada.pk, "produto": com.pk, "limite": "10.000"}
    assert entradas[sem.pk] == {"rodada": rodada.pk, "produto": sem.pk, "limite": None}
    html = admin_client.get(f"/administracao/rodadas/{rodada.pk}/estoque/").content.decode()
    assert "sem limite" in html


def test_nova_rodada_comeca_sem_produtos(admin_client: Client) -> None:  # A-2
    antiga = RodadaFactory.create(etapa=Etapa.DISPONIVEL_PARA_RETIRADA)
    estoque_antigo = _estoque(antiga, "7")
    nova = RodadaFactory.create(fornecedor=antiga.fornecedor)
    assert EstoqueDaRodada.objects.filter(rodada=nova).count() == 0
    html = admin_client.get(f"/administracao/rodadas/{nova.pk}/estoque/").content.decode()
    assert "fora da rodada" in html
    estoque_antigo.refresh_from_db()
    assert estoque_antigo.limite == D("7.000")
    assert estoque_antigo.rodada_id == antiga.pk


def test_produto_de_outro_fornecedor_e_recusado(admin: Conta) -> None:  # A-3
    rodada = RodadaFactory.create()
    estranho = ProdutoFactory.create(fornecedor=FornecedorFactory.create())
    with pytest.raises(ValidationError):
        incluir_produto_na_rodada(admin, rodada, estranho, "5")
    assert EstoqueDaRodada.objects.count() == 0
    assert EntradaAuditoria.objects.count() == 0


def test_banco_recusa_produto_de_outro_fornecedor() -> None:  # A-3
    rodada = RodadaFactory.create()
    estranho = ProdutoFactory.create(fornecedor=FornecedorFactory.create())
    sql = (
        "INSERT INTO rodadas_estoque (rodada_id, produto_id, limite, incluido_em) "
        "VALUES (%s, %s, 5, now())"
    )
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [rodada.pk, estranho.pk])
    assert EstoqueDaRodada.objects.count() == 0


def test_banco_aceita_produto_do_mesmo_fornecedor() -> None:
    rodada = RodadaFactory.create()
    produto = ProdutoFactory.create(fornecedor=rodada.fornecedor)
    sql = (
        "INSERT INTO rodadas_estoque (rodada_id, produto_id, limite, incluido_em) "
        "VALUES (%s, %s, 5, now())"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [rodada.pk, produto.pk])
    assert EstoqueDaRodada.objects.count() == 1


def test_produto_ja_incluido_e_recusado(admin: Conta) -> None:  # A-4
    estoque = _estoque()
    with pytest.raises(ValidationError, match=r"Este produto já está na rodada\."):
        incluir_produto_na_rodada(admin, estoque.rodada, estoque.produto, "5")
    assert EstoqueDaRodada.objects.count() == 1
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")


@pytest.mark.parametrize("limite", ["-1", "abc", 5.0, "1.0001"])
def test_limite_invalido_na_inclusao(admin: Conta, limite: Any) -> None:
    rodada = RodadaFactory.create()
    produto = ProdutoFactory.create(fornecedor=rodada.fornecedor)
    with pytest.raises(ValidationError):
        incluir_produto_na_rodada(admin, rodada, produto, limite)
    assert EstoqueDaRodada.objects.count() == 0


def test_limite_zero_e_aceito(admin: Conta) -> None:
    rodada = RodadaFactory.create()
    produto = ProdutoFactory.create(fornecedor=rodada.fornecedor)
    assert incluir_produto_na_rodada(admin, rodada, produto, "0").limite == D("0.000")


def test_produto_indisponivel_pode_ser_incluido(admin: Conta) -> None:
    rodada = RodadaFactory.create()
    produto = ProdutoFactory.create(fornecedor=rodada.fornecedor, disponivel=False)
    estoque = incluir_produto_na_rodada(admin, rodada, produto, "")
    assert estoque.pk is not None
    assert EstoqueDaRodada.objects.get(produto=produto).limite is None


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_reducao_ate_o_reservado_e_aceita(admin: Conta) -> None:  # A-5, cenário 71
    estoque = _estoque(limite="10")
    _com_reserva(estoque, "6")
    alterar_estoque(admin, estoque, "8")
    alterar_estoque(admin, estoque, D("6"))
    estoque.refresh_from_db()
    assert estoque.limite == D("6.000")
    entradas = list(EntradaAuditoria.objects.filter(acao="estoque.alterar").order_by("id"))
    assert [(e.alteracoes["anterior"], e.alteracoes["novo"]) for e in entradas] == [
        ("10.000", "8.000"),
        ("8.000", "6.000"),
    ]
    assert entradas[0].alteracoes["rodada"] == estoque.rodada_id
    assert entradas[0].alteracoes["produto"] == estoque.produto_id
    assert entradas[0].alteracoes["estoque"] == estoque.pk


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_reducao_abaixo_do_reservado_e_recusada(
    admin: Conta, receptor: list[Any]
) -> None:  # A-6, cenário 71, T-23
    estoque = _estoque(limite="10")
    _com_reserva(estoque, "6")
    with pytest.raises(EstoqueAbaixoDoReservado, match="6"):
        alterar_estoque(admin, estoque, "5")
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert EntradaAuditoria.objects.count() == 0
    assert receptor == []


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_sem_limite_nao_pode_ir_abaixo_do_reservado(admin: Conta) -> None:  # A-7, cenário 71
    estoque = _estoque(limite=None)
    _com_reserva(estoque, "6")
    with pytest.raises(EstoqueAbaixoDoReservado):
        alterar_estoque(admin, estoque, "4")
    estoque.refresh_from_db()
    assert estoque.limite is None


def test_remover_o_limite_envia_o_sinal(admin: Conta, receptor: list[Any]) -> None:  # A-8
    estoque = _estoque(limite="10")
    alterar_estoque(admin, estoque, None)
    estoque.refresh_from_db()
    assert estoque.limite is None
    assert len(receptor) == 1
    _, anterior, novo, dentro = receptor[0]
    assert (anterior, novo, dentro) == (D("10.000"), None, True)
    assert EntradaAuditoria.objects.get(acao="estoque.alterar").alteracoes["novo"] is None


def test_alterar_estoque_pela_tela(admin_client: Client) -> None:
    estoque = _estoque(limite="10")
    url = f"/administracao/estoque/{estoque.pk}/alterar/"
    resposta = admin_client.post(url, {"limite": "8,5"})
    assert resposta.status_code == 302
    assert resposta["Location"] == f"/administracao/rodadas/{estoque.rodada_id}/estoque/"
    estoque.refresh_from_db()
    assert estoque.limite == D("8.500")
    assert admin_client.post(url, {"limite": ""}).status_code == 302
    estoque.refresh_from_db()
    assert estoque.limite is None


def test_reducao_abaixo_do_reservado_pela_tela_mostra_a_mensagem(admin_client: Client) -> None:
    estoque = _estoque(limite="10")
    _com_reserva(estoque, "6")
    resposta = admin_client.post(f"/administracao/estoque/{estoque.pk}/alterar/", {"limite": "5"})
    assert resposta.status_code == 200
    assert "O estoque não pode ficar abaixo da quantidade já reservada (6)." in (
        resposta.content.decode()
    )
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")


def test_valor_invalido_pela_tela_nao_grava(admin_client: Client) -> None:
    estoque = _estoque(limite="10")
    for valor in ("abc", "-1", "1,0001"):
        resposta = admin_client.post(
            f"/administracao/estoque/{estoque.pk}/alterar/", {"limite": valor}
        )
        assert resposta.status_code == 200, valor
        assert 'role="alert"' in resposta.content.decode(), valor
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert EntradaAuditoria.objects.count() == 0


def test_mesmo_limite_nao_grava_nem_audita_nem_avisa(admin: Conta, receptor: list[Any]) -> None:
    estoque = _estoque(limite="10")
    alterar_estoque(admin, estoque, "10")
    assert EntradaAuditoria.objects.count() == 0
    assert receptor == []


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("etapa", ETAPAS_CONGELADAS)
def test_estoque_congelado_pela_rota(admin_client: Client, etapa: Etapa) -> None:  # A-9, T-23
    rodada = RodadaFactory.create(etapa=etapa)
    estoque = _estoque(rodada, "10")
    outro = ProdutoFactory.create(fornecedor=rodada.fornecedor)
    incluir = admin_client.post(
        f"/administracao/rodadas/{rodada.pk}/estoque/incluir/",
        {"produto": str(outro.pk), "limite": "3"},
    )
    alterar = admin_client.post(f"/administracao/estoque/{estoque.pk}/alterar/", {"limite": "8"})
    for resposta in (incluir, alterar):
        assert resposta.status_code == 409
        assert MENSAGEM in resposta.content.decode()
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert EstoqueDaRodada.objects.count() == 1
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("etapa", ETAPAS_CONGELADAS)
def test_estoque_congelado_pelo_servico(admin: Conta, etapa: Etapa) -> None:  # A-9, T-23
    rodada = RodadaFactory.create(etapa=etapa)
    estoque = _estoque(rodada, "10")
    outro = ProdutoFactory.create(fornecedor=rodada.fornecedor)
    with pytest.raises(CondicoesCongeladas) as erro:
        incluir_produto_na_rodada(admin, rodada, outro, "3")
    assert erro.value.codigo == "fora_de_interesse"
    with pytest.raises(CondicoesCongeladas):
        alterar_estoque(admin, estoque, "8")
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert EstoqueDaRodada.objects.count() == 1
    assert EntradaAuditoria.objects.count() == 0


def test_estoque_de_rodada_antiga_nunca_muda(admin: Conta) -> None:  # A-10
    antiga = RodadaFactory.create(etapa=Etapa.DISPONIVEL_PARA_RETIRADA)
    estoque = _estoque(antiga, "10")
    RodadaFactory.create(fornecedor=antiga.fornecedor, etapa=Etapa.INTERESSE)
    outro = ProdutoFactory.create(fornecedor=antiga.fornecedor)
    with pytest.raises(CondicoesCongeladas):
        alterar_estoque(admin, estoque, "8")
    with pytest.raises(CondicoesCongeladas):
        incluir_produto_na_rodada(admin, antiga, outro, "3")
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert EstoqueDaRodada.objects.count() == 1
    assert EntradaAuditoria.objects.count() == 0


def test_sem_rodada_ativa_o_estoque_e_recusado(admin: Conta) -> None:
    antiga = RodadaFactory.create(etapa=Etapa.CANCELADA)
    estoque = _estoque(antiga, "10")
    with pytest.raises(CondicoesCongeladas) as erro:
        alterar_estoque(admin, estoque, "8")
    assert erro.value.codigo == "sem_rodada_ativa"


def test_sinal_na_inclusao_e_na_alteracao(admin: Conta, receptor: list[Any]) -> None:  # A-11
    rodada = RodadaFactory.create()
    produto = ProdutoFactory.create(fornecedor=rodada.fornecedor)
    estoque = incluir_produto_na_rodada(admin, rodada, produto, "10")
    alterar_estoque(admin, estoque, "8")
    assert len(receptor) == 2
    (e1, anterior1, novo1, dentro1), (e2, anterior2, novo2, dentro2) = receptor
    assert e1.pk == e2.pk == estoque.pk
    assert (anterior1, novo1, dentro1) == (D("0"), D("10.000"), True)
    assert (anterior2, novo2, dentro2) == (D("10.000"), D("8.000"), True)


def test_receptor_que_falha_desfaz_a_alteracao(admin: Conta) -> None:  # A-12
    estoque = _estoque(limite="10")

    def falha(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("falha do receptor")

    estoque_alterado.connect(falha, weak=False)
    try:
        with pytest.raises(RuntimeError):
            alterar_estoque(admin, estoque, "8")
    finally:
        estoque_alterado.disconnect(falha)
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert EntradaAuditoria.objects.count() == 0


def test_receptor_que_falha_desfaz_a_inclusao(admin: Conta) -> None:
    rodada = RodadaFactory.create()
    produto = ProdutoFactory.create(fornecedor=rodada.fornecedor)

    def falha(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("falha do receptor")

    estoque_alterado.connect(falha, weak=False)
    try:
        with pytest.raises(RuntimeError):
            incluir_produto_na_rodada(admin, rodada, produto, "10")
    finally:
        estoque_alterado.disconnect(falha)
    assert EstoqueDaRodada.objects.count() == 0
    assert EntradaAuditoria.objects.count() == 0


def test_estoque_livre() -> None:  # A-13
    com_limite = _estoque(limite="10")
    _com_reserva(com_limite, "6")
    sem_limite = _estoque(limite=None)
    assert estoque_livre(com_limite) == D("4.000")
    assert str(estoque_livre(com_limite)) == "4.000"
    assert estoque_livre(sem_limite) is None


def test_estoque_livre_tem_piso_zero() -> None:
    estoque = _estoque(limite="5")
    _com_reserva(estoque, "6")
    assert estoque_livre(estoque) == D("0.000")


@pytest.mark.parametrize(
    ("sql", "usa_outro_produto"),
    [
        ("UPDATE rodadas_estoque SET limite = -1 WHERE id = %s", False),
        ("UPDATE rodadas_estoque SET produto_id = %s WHERE id = %s", True),
        ("DELETE FROM rodadas_estoque WHERE id = %s", False),
    ],
)
def test_banco_recusa_limite_negativo_troca_de_produto_e_exclusao(
    sql: str, usa_outro_produto: bool
) -> None:  # A-14
    estoque = _estoque(limite="10")
    outro = ProdutoFactory.create(fornecedor=estoque.rodada.fornecedor)
    parametros = [outro.pk, estoque.pk] if usa_outro_produto else [estoque.pk]
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, parametros)
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert estoque.produto_id != outro.pk


def test_banco_recusa_troca_de_rodada() -> None:
    estoque = _estoque(limite="10")
    outra = RodadaFactory.create(fornecedor=estoque.rodada.fornecedor, etapa=Etapa.CANCELADA)
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE rodadas_estoque SET rodada_id = %s WHERE id = %s", [outra.pk, estoque.pk]
        )
    estoque.refresh_from_db()
    assert estoque.rodada_id != outra.pk


def test_banco_recusa_produto_repetido_na_rodada() -> None:
    estoque = _estoque()
    with pytest.raises(IntegrityError), transaction.atomic():
        EstoqueDaRodada.objects.create(
            rodada=estoque.rodada, produto=estoque.produto, limite=D("1")
        )
    assert EstoqueDaRodada.objects.count() == 1


def test_save_comum_do_orm_passa_pelas_triggers() -> None:
    estoque = _estoque(limite="10")
    estoque.limite = D("9")
    estoque.save()
    estoque.refresh_from_db()
    assert estoque.limite == D("9.000")


def test_tela_somente_leitura_fora_de_interesse(admin_client: Client) -> None:  # A-19
    rodada = RodadaFactory.create(etapa=Etapa.FECHAMENTO)
    estoque = _estoque(rodada, "10")
    _com_reserva(estoque, "6")
    resposta = admin_client.get(f"/administracao/rodadas/{rodada.pk}/estoque/")
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'name="limite"' not in html
    assert "/estoque/incluir/" not in html
    assert "/alterar/" not in html
    assert estoque.produto.nome in html
    assert MENSAGEM in html


def test_tela_em_interesse_mostra_limite_reservado_e_livre(admin_client: Client) -> None:
    rodada = RodadaFactory.create()
    estoque = _estoque(rodada, "10")
    _com_reserva(estoque, "6")
    fora = ProdutoFactory.create(fornecedor=rodada.fornecedor, nome="Produto de fora")
    html = admin_client.get(f"/administracao/rodadas/{rodada.pk}/estoque/").content.decode()
    assert estoque.produto.nome in html
    assert fora.nome in html
    assert 'name="limite"' in html
    assert f"/administracao/estoque/{estoque.pk}/alterar/" in html
    assert f"/administracao/rodadas/{rodada.pk}/estoque/incluir/" in html
    for esperado in ("10", "6", "4"):
        assert esperado in html


def test_tela_nao_mostra_produtos_de_outro_fornecedor(admin_client: Client) -> None:
    rodada = RodadaFactory.create()
    estranho = ProdutoFactory.create(nome="Produto Estranho")
    html = admin_client.get(f"/administracao/rodadas/{rodada.pk}/estoque/").content.decode()
    assert rodada.fornecedor.nome in html
    assert estranho.nome not in html


def test_inclusao_pela_tela_de_produto_de_outro_fornecedor_nao_grava(admin_client: Client) -> None:
    rodada = RodadaFactory.create()
    estranho = ProdutoFactory.create()
    resposta = admin_client.post(
        f"/administracao/rodadas/{rodada.pk}/estoque/incluir/",
        {"produto": str(estranho.pk), "limite": "5"},
    )
    assert resposta.status_code == 200
    assert 'role="alert"' in resposta.content.decode()
    assert EstoqueDaRodada.objects.count() == 0


def test_ids_inexistentes_dao_404(admin_client: Client) -> None:
    assert admin_client.get("/administracao/rodadas/999999/estoque/").status_code == 404
    assert (
        admin_client.post("/administracao/rodadas/999999/estoque/incluir/", {}).status_code == 404
    )
    assert admin_client.post("/administracao/estoque/999999/alterar/", {}).status_code == 404
    rodada = RodadaFactory.create()
    resposta = admin_client.post(
        f"/administracao/rodadas/{rodada.pk}/estoque/incluir/", {"produto": "999999", "limite": ""}
    )
    assert resposta.status_code == 200
    assert EstoqueDaRodada.objects.count() == 0


def test_detalhe_do_fornecedor_tem_link_para_o_estoque(admin_client: Client) -> None:
    rodada = RodadaFactory.create()
    html = admin_client.get(f"/administracao/fornecedores/{rodada.fornecedor_id}/").content.decode()
    assert f"/administracao/rodadas/{rodada.pk}/estoque/" in html


def test_so_o_administrador_usa_os_servicos() -> None:
    comprador = ContaFactory.create()
    estoque = _estoque()
    outro = ProdutoFactory.create(fornecedor=estoque.rodada.fornecedor)
    with pytest.raises(PermissionDenied):
        incluir_produto_na_rodada(comprador, estoque.rodada, outro, "5")
    with pytest.raises(PermissionDenied):
        alterar_estoque(comprador, estoque, "5")
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert EntradaAuditoria.objects.count() == 0


def test_travar_estoque_exige_transacao_e_trava_a_linha() -> None:
    from django.test.utils import CaptureQueriesContext

    estoque = _estoque()
    with transaction.atomic(), CaptureQueriesContext(connection) as consultas:
        travado = travar_estoque(estoque.rodada, estoque.produto)
    assert travado.pk == estoque.pk
    sqls = [c["sql"] for c in consultas]
    assert any("FOR UPDATE" in s and "rodadas_estoque" in s for s in sqls)
    assert any("FOR UPDATE" in s and "catalogo_produto" in s for s in sqls)
    assert isinstance(travado.produto_id, int)
    assert Produto.objects.filter(pk=travado.produto_id).exists()


@pytest.mark.django_db(transaction=True)
def test_travar_estoque_fora_de_transacao_falha() -> None:
    estoque = _estoque()
    with pytest.raises(TransactionManagementError):
        travar_estoque(estoque.rodada, estoque.produto)
