"""E08-02: abertura do pagamento e pedidos congelados (acceptance A-1 a A-11 e A-13 a A-17)."""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import Client

from apps.catalogo.models import Unidade
from apps.catalogo.servicos import editar_produto
from apps.contas.moderacao import suspender
from apps.interesses.consultas import carrinho_do_comprador
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.progresso import progresso_da_rodada
from apps.interesses.servicos import adicionar_interesse
from apps.notificacoes.models import Envio, Notificacao
from apps.notificacoes.processamento import processar_envios
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from apps.pedidos.abertura import abrir_pagamento
from apps.pedidos.models import (
    AberturaDoPagamento,
    ItemDoPedido,
    ParcelaNoPedido,
    Pedido,
    SituacaoDoPedido,
)
from apps.rodadas.condicoes import InteressesBloqueados
from apps.rodadas.fechamento import TransicaoRecusada
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.ciclos import dar_prazo_de_teste
from tests.apoio.interesses import sem_minimo
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    abertura_unica,
    abrir,
    administrador,
    montar_arranjo,
    pedido_de,
)
from tests.conftest import RelogioControlado
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
ACAO = "rodada.abrir_pagamento"
MODELOS_DO_PEDIDO = (AberturaDoPagamento, Pedido, ItemDoPedido, ParcelaNoPedido)


@pytest.fixture
def arranjo(relogio: RelogioControlado) -> Arranjo:
    relogio.congelar(T0)
    return montar_arranjo()


def _etapa(rodada: Rodada) -> str:
    return str(Rodada.objects.get(pk=rodada.pk).etapa)


def _gravado() -> dict[str, int]:
    return {m.__name__: m.objects.count() for m in (*MODELOS_DO_PEDIDO, SituacaoDoPedido)}


def _avisos(evento: str, conta: Any = None) -> list[Notificacao]:
    consulta = Notificacao.objects.filter(evento=evento).order_by("pk")
    return list(consulta.filter(conta=conta) if conta is not None else consulta)


@pytest.mark.acceptance
def test_abertura_congela_um_pedido_por_comprador(arranjo: Arranjo) -> None:  # A-1, cenário 11
    resultado = abrir(arranjo)
    assert resultado.etapa_final == Etapa.PAGAMENTO
    assert _etapa(arranjo.rodada) == Etapa.PAGAMENTO
    abertura = abertura_unica()
    assert resultado.abertura == abertura
    assert (abertura.ciclo, abertura.rodada, abertura.autor) == (
        arranjo.ciclo,
        arranjo.rodada,
        arranjo.admin,
    )
    assert abertura.t0 == T0
    assert (abertura.frete, abertura.total_produtos) == (D("22.00"), D("170.00"))
    a, b = pedido_de(arranjo.a), pedido_de(arranjo.b)
    assert (a.produtos, a.servico, a.frete, a.total) == (
        D("80.00"),
        D("4.00"),
        D("10.35"),
        D("94.35"),
    )
    assert (b.produtos, b.servico, b.frete, b.total) == (
        D("90.00"),
        D("4.50"),
        D("11.65"),
        D("106.15"),
    )
    assert a.frete + b.frete == D("22.00")
    assert a.abertura == b.abertura == abertura
    situacoes = SituacaoDoPedido.objects.order_by("pedido_id")
    assert [s.situacao for s in situacoes] == ["aguardando_pagamento", "aguardando_pagamento"]
    assert [s.pedido_id for s in situacoes] == sorted([a.pk, b.pk])
    assert all(
        (s.quitado_por, s.quitado_em, s.cancelado_em, s.motivo_do_cancelamento)
        == (None, None, None, "")
        for s in situacoes
    )


def test_caixas_numeradas_por_produto(arranjo: Arranjo) -> None:  # A-2, §6.3
    abrir(arranjo)
    linhas = list(
        ParcelaNoPedido.objects.filter(item__produto=arranjo.p2)
        .order_by("caixa", "parcela__sequencia")
        .values_list("caixa", "item__pedido__comprador_id", "quantidade")
    )
    a, b = arranjo.a.pk, arranjo.b.pk
    assert linhas == [(1, a, D("4")), (1, b, D("2")), (2, b, D("4")), (2, b, D("2"))]
    for caixa in (1, 2):
        assert sum(q for c, _, q in linhas if c == caixa) == D("6")
    assert set(
        ParcelaNoPedido.objects.filter(item__produto=arranjo.p1).values_list("caixa", flat=True)
    ) == {None}
    # a soma por item é a quantidade do item
    for item in ItemDoPedido.objects.all():
        assert sum(p.quantidade for p in item.parcelas.all()) == item.quantidade


def test_itens_guardam_a_copia_do_produto(arranjo: Arranjo) -> None:  # A-3, Infra 4.12
    abrir(arranjo)
    for produto, comprador, quantidade in (
        (arranjo.p1, arranjo.a, D("6")),
        (arranjo.p1, arranjo.b, D("5")),
        (arranjo.p2, arranjo.a, D("4")),
        (arranjo.p2, arranjo.b, D("8")),
    ):
        item = ItemDoPedido.objects.get(pedido=pedido_de(comprador), produto=produto)
        assert (item.nome, item.unidade, item.incremento, item.multiplo) == (
            produto.nome,
            produto.unidade,
            produto.incremento,
            produto.multiplo,
        )
        assert (item.preco_unitario, item.quantidade) == (produto.preco, quantidade)
        assert item.subtotal == produto.preco * quantidade
    item = ItemDoPedido.objects.get(pedido=pedido_de(arranjo.a), produto=arranjo.p2)
    assert (item.quantidade, item.subtotal) == (D("4"), D("20.00"))


@pytest.mark.acceptance
def test_parcela_atendida_em_parte_pela_fila_fica_pendente(
    relogio: RelogioControlado,
) -> None:  # A-4, herdado da E05
    relogio.congelar(T0)
    arranjo = montar_arranjo(pendente_a_p1=3)
    parcela = ParcelaDeInteresse.objects.get(comprador=arranjo.a, produto=arranjo.p1)
    sequencia = parcela.sequencia
    abrir(arranjo)
    item = ItemDoPedido.objects.get(pedido=pedido_de(arranjo.a), produto=arranjo.p1)
    assert item.quantidade == D("6")
    parcela.refresh_from_db()
    assert (
        parcela.situacao,
        parcela.sequencia,
        parcela.quantidade_reservada,
        parcela.quantidade_pendente,
    ) == (SituacaoParcela.PENDENTE, sequencia, D("0"), D("3"))
    assert item.parcelas.get().parcela_id == parcela.pk
    assert item.parcelas.get().quantidade == D("6")
    cliente = Client()
    cliente.force_login(arranjo.a)
    resposta = cliente.post(
        "/interesses/pendentes/remover/", {"produto": arranjo.p1.pk, "quantidade": "2"}
    )
    assert resposta.status_code == 302
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.quantidade_pendente) == (SituacaoParcela.PENDENTE, D("1"))
    item.refresh_from_db()
    assert item.quantidade == D("6")
    (grupo,) = carrinho_do_comprador(arranjo.a)
    (linha_p1,) = [x for x in grupo.linhas if x.produto.pk == arranjo.p1.pk]
    assert (linha_p1.pendente, linha_p1.reservado) == (D("1"), D("0"))


def test_parcela_sem_pendente_vira_em_pedido_com_a_reserva(arranjo: Arranjo) -> None:  # A-5
    abrir(arranjo)
    parcelas = list(ParcelaDeInteresse.objects.order_by("sequencia"))
    assert len(parcelas) == 5
    for parcela in parcelas:
        assert parcela.situacao == SituacaoParcela.EM_PEDIDO
        assert parcela.quantidade_reservada == parcela.quantidade_original
        assert parcela.quantidade_pendente == 0


def _estado(arranjo: Arranjo) -> tuple[str, dict[str, int]]:
    return _etapa(arranjo.rodada), _gravado()


@pytest.mark.acceptance
def test_comprador_suspenso_antes_da_abertura_refaz_as_caixas(
    arranjo: Arranjo,
) -> None:  # A-6, herdado da E06
    suspender(arranjo.admin, arranjo.b)
    resultado = abrir(arranjo)
    assert resultado.etapa_final == Etapa.INTERESSE
    assert resultado.abertura is None
    assert _etapa(arranjo.rodada) == Etapa.INTERESSE
    assert all(v == 0 for v in _gravado().values())
    (removido,) = _avisos("excedentes_removidos", arranjo.a)
    assert removido.corpo == (
        "Na abertura do pagamento da rodada de F, 4 unidade de P2 não completaram caixa e "
        "foram removidas do seu interesse. Continuam no seu interesse: 0 unidade."
    )
    assert removido.titulo == "Excedentes removidos: P2"
    assert removido.chave == (
        f"excedentes_removidos:abertura:{arranjo.ciclo.pk}:{arranjo.p2.pk}:{arranjo.a.pk}"
    )
    (retorno,) = _avisos("retorno_para_interesse", arranjo.a)
    assert "voltou para a fase de interesse porque o mínimo do fornecedor não foi atingido" in (
        retorno.corpo
    )
    assert "na abertura do pagamento" in retorno.corpo
    assert "Nada foi cobrado neste ciclo, então não há estornos." in retorno.corpo
    assert _avisos("retorno_para_interesse", arranjo.b) == []
    (entrada,) = EntradaAuditoria.objects.filter(acao=ACAO)
    assert entrada.alteracoes["resultado"] == "retorno_para_interesse"
    assert entrada.autor_id == str(arranjo.admin.pk)
    parcela = ParcelaDeInteresse.objects.get(comprador=arranjo.a, produto=arranjo.p2)
    assert (parcela.situacao, parcela.quantidade_reservada) == (SituacaoParcela.REMOVIDA, D("0"))


def test_preco_reduzido_antes_da_abertura_derruba_o_minimo(arranjo: Arranjo) -> None:  # A-7
    editar_produto(arranjo.admin, arranjo.p1, preco="1.00")
    resultado = abrir(arranjo)
    assert (resultado.etapa_final, resultado.abertura) == (Etapa.INTERESSE, None)
    assert _etapa(arranjo.rodada) == Etapa.INTERESSE
    assert all(v == 0 for v in _gravado().values())
    (entrada,) = EntradaAuditoria.objects.filter(acao=ACAO)
    assert entrada.alteracoes["resultado"] == "retorno_para_interesse"
    assert entrada.alteracoes["valor_elegivel"] == "71.00"


def test_preco_aumentado_antes_da_abertura_entra_no_pedido(arranjo: Arranjo) -> None:  # A-8
    editar_produto(arranjo.admin, arranjo.p1, preco="12.00")
    abrir(arranjo)
    assert abertura_unica().total_produtos == D("192.00")
    precos = set(
        ItemDoPedido.objects.filter(produto=arranjo.p1).values_list("preco_unitario", flat=True)
    )
    assert precos == {D("12.00")}


@pytest.mark.parametrize("etapa", [Etapa.INTERESSE, Etapa.FECHAMENTO, Etapa.PAGAMENTO])
def test_so_o_fechamento_encerrado_abre_o_pagamento(arranjo: Arranjo, etapa: str) -> None:  # A-9
    Rodada.objects.filter(pk=arranjo.rodada.pk).update(etapa=etapa)
    antes = _gravado()
    with pytest.raises(TransicaoRecusada) as erro:
        abrir(arranjo)
    assert erro.value.codigo == "fora_de_fechamento_encerrado_para_pagamento"
    assert str(erro.value) == "Só uma rodada com o fechamento encerrado pode abrir o pagamento."
    assert _gravado() == antes
    assert _etapa(arranjo.rodada) == etapa
    assert not EntradaAuditoria.objects.filter(acao=ACAO).exists()


def test_autor_e_frete_invalidos_nao_gravam_nada(arranjo: Arranjo) -> None:  # A-10
    for autor in (arranjo.a, None):
        with pytest.raises(PermissionDenied):
            abrir_pagamento(autor, arranjo.rodada, D("22.00"))
    for frete in (D("-1"), D("22.001"), 22.0, "22.00", None, D("NaN")):
        with pytest.raises(ValueError):  # noqa: PT011
            abrir_pagamento(arranjo.admin, arranjo.rodada, frete)  # type: ignore[arg-type]
    assert all(v == 0 for v in _gravado().values())
    assert _etapa(arranjo.rodada) == Etapa.FECHAMENTO_ENCERRADO
    assert not EntradaAuditoria.objects.filter(acao=ACAO).exists()


def test_frete_acima_da_capacidade_e_recusado(arranjo: Arranjo) -> None:  # A-10
    with pytest.raises(ValueError):  # noqa: PT011
        abrir_pagamento(arranjo.admin, arranjo.rodada, D("10000000000.00"))
    assert _etapa(arranjo.rodada) == Etapa.FECHAMENTO_ENCERRADO


def _sql_recusado(sql: str, parametros: list[Any]) -> None:
    with (
        pytest.raises(DatabaseError),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(sql, parametros)


def _composicao_minima(arranjo: Arranjo) -> None:
    """Uma abertura, um pedido, um item e uma parcela, gravados direto (sem o serviço)."""
    abertura = AberturaDoPagamento.objects.create(
        ciclo=arranjo.ciclo,
        rodada=arranjo.rodada,
        t0=T0,
        frete=D("1.00"),
        total_produtos=D("10.00"),
        autor=arranjo.admin,
    )
    pedido = Pedido.objects.create(
        abertura=abertura,
        comprador=arranjo.a,
        produtos=D("10.00"),
        servico=D("0.50"),
        frete=D("1.00"),
        total=D("11.50"),
    )
    SituacaoDoPedido.objects.create(pedido=pedido, situacao="aguardando_pagamento")
    item = ItemDoPedido.objects.create(
        pedido=pedido,
        produto=arranjo.p1,
        nome="P1",
        unidade=Unidade.UNIDADE,
        incremento=D("1"),
        preco_unitario=D("10.00"),
        quantidade=D("1"),
        subtotal=D("10.00"),
    )
    parcela = ParcelaDeInteresse.objects.filter(comprador=arranjo.a, produto=arranjo.p1).first()
    assert parcela is not None
    ParcelaNoPedido.objects.create(item=item, parcela=parcela, caixa=None, quantidade=D("1"))


@pytest.mark.acceptance
def test_composicao_do_pedido_nao_muda_nem_some(
    arranjo: Arranjo, caplog: pytest.LogCaptureFixture
) -> None:  # A-11, T-17
    _composicao_minima(arranjo)
    instantaneo = {m.__name__: list(m.objects.order_by("pk").values()) for m in MODELOS_DO_PEDIDO}
    for modelo in MODELOS_DO_PEDIDO:
        objeto = modelo.objects.order_by("pk").first()
        assert objeto is not None
        mensagem = f"Tentativa de alterar pedido congelado: {modelo.__name__} {objeto.pk}"
        with caplog.at_level(logging.WARNING):
            caplog.clear()
            with pytest.raises(RegistroImutavel):
                objeto.save()
            assert mensagem in caplog.text
            caplog.clear()
            with pytest.raises(RegistroImutavel):
                objeto.delete()
            assert mensagem in caplog.text
        with pytest.raises(RegistroImutavel):
            modelo.objects.all().update(pk=objeto.pk)
        with pytest.raises(RegistroImutavel):
            modelo.objects.all().delete()
        tabela = modelo._meta.db_table
        _sql_recusado(f'UPDATE "{tabela}" SET id = id + 1000 WHERE id = %s', [objeto.pk])  # noqa: S608
        _sql_recusado(f'DELETE FROM "{tabela}" WHERE id = %s', [objeto.pk])  # noqa: S608
    assert {
        m.__name__: list(m.objects.order_by("pk").values()) for m in MODELOS_DO_PEDIDO
    } == instantaneo


def test_o_banco_recusa_pedido_incoerente(arranjo: Arranjo) -> None:
    _composicao_minima(arranjo)
    pedido = pedido_de(arranjo.a)
    abertura = pedido.abertura
    recusas = [
        lambda: Pedido.objects.create(
            abertura=abertura,
            comprador=ContaFactory.create(),
            produtos=D("10.00"),
            servico=D("0.50"),
            frete=D("1.00"),
            total=D("99.00"),
        ),
        lambda: Pedido.objects.create(
            abertura=abertura,
            comprador=arranjo.a,
            produtos=D("10.00"),
            servico=D("0.50"),
            frete=D("1.00"),
            total=D("11.50"),
        ),  # segundo pedido do mesmo comprador na abertura
        lambda: ItemDoPedido.objects.create(
            pedido=pedido,
            produto=arranjo.p1,
            nome="x",
            unidade=Unidade.UNIDADE,
            incremento=D("1"),
            preco_unitario=D("1.00"),
            quantidade=D("0"),
            subtotal=D("0.00"),
        ),
        lambda: ItemDoPedido.objects.create(
            pedido=pedido,
            produto=arranjo.p1,
            nome="x",
            unidade=Unidade.UNIDADE,
            incremento=D("1"),
            preco_unitario=D("1.00"),
            quantidade=D("1"),
            subtotal=D("1.00"),
        ),  # produto repetido no pedido
    ]
    for recusa in recusas:
        with pytest.raises(DatabaseError), transaction.atomic():
            recusa()
    novo = Pedido.objects.create(
        abertura=abertura,
        comprador=ContaFactory.create(),
        produtos=D("10.00"),
        servico=D("0.50"),
        frete=D("1.00"),
        total=D("11.50"),
    )
    incoerentes: list[dict[str, Any]] = [
        {"situacao": "pago"},  # pago sem pagamento nem horário
        {"situacao": "cancelado"},  # cancelado sem horário nem motivo
        {"situacao": "aguardando_pagamento", "cancelado_em": T0},
        {"situacao": "cancelado", "cancelado_em": T0, "motivo_do_cancelamento": "outro"},
    ]
    for campos in incoerentes:
        with pytest.raises(DatabaseError), transaction.atomic():
            SituacaoDoPedido.objects.create(pedido=novo, **campos)
    SituacaoDoPedido.objects.create(
        pedido=novo,
        situacao="cancelado",
        cancelado_em=T0,
        motivo_do_cancelamento="suspensao",
    )


def test_a_abertura_e_unica_por_ciclo(arranjo: Arranjo) -> None:
    _composicao_minima(arranjo)
    with pytest.raises(DatabaseError), transaction.atomic():
        AberturaDoPagamento.objects.create(
            ciclo=arranjo.ciclo,
            rodada=arranjo.rodada,
            t0=T0,
            frete=D("1.00"),
            total_produtos=D("1.00"),
            autor=arranjo.admin,
        )


@pytest.mark.acceptance
def test_composicao_fica_congelada_apos_a_abertura(arranjo: Arranjo) -> None:
    # A-13, cenário 11 (serviço; a recusa das rotas está no arquivo de telas)
    abrir(arranjo)
    c = ContaFactory.create()
    with pytest.raises(InteressesBloqueados):
        adicionar_interesse(c, arranjo.p1, "1")
    antes = list(ItemDoPedido.objects.order_by("pk").values())
    totais = list(Pedido.objects.order_by("pk").values("produtos", "servico", "frete", "total"))
    editar_produto(arranjo.admin, arranjo.p1, preco="20.00")
    editar_produto(arranjo.admin, arranjo.p2, preco="1.00")
    assert list(ItemDoPedido.objects.order_by("pk").values()) == antes
    assert list(Pedido.objects.order_by("pk").values("produtos", "servico", "frete", "total")) == (
        totais
    )
    assert antes
    assert _avisos("preco_alterado", arranjo.a) == []
    assert _avisos("preco_alterado", arranjo.b) == []


@pytest.mark.acceptance
def test_produto_por_peso_guarda_o_subtotal_arredondado(
    relogio: RelogioControlado,
) -> None:  # A-14, cenário 65
    relogio.congelar(T0)
    fornecedor = FornecedorFactory.create(nome="F")
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.FECHAMENTO_ENCERRADO)
    dar_prazo_de_teste(rodada)
    produto = ProdutoFactory.create(
        fornecedor=fornecedor,
        nome="Banana",
        unidade=Unidade.KG,
        incremento=D("0.05"),
        preco=D("12.99"),
    )
    EstoqueDaRodadaFactory.create(rodada=rodada, produto=produto, limite=None)
    comprador = ContaFactory.create()
    ParcelaFactory.create(
        comprador=comprador,
        produto=produto,
        quantidade_original=D("0.350"),
        quantidade_reservada=D("0.350"),
    )
    sem_minimo(rodada)
    abrir_pagamento(administrador(), rodada, D("0.00"))
    assert ItemDoPedido.objects.count() == 1
    item = ItemDoPedido.objects.get()
    assert (item.quantidade, item.subtotal) == (D("0.350"), D("4.55"))
    editar_produto(administrador(), produto, preco="20.00")
    item.refresh_from_db()
    assert (item.preco_unitario, item.subtotal) == (D("12.99"), D("4.55"))


def test_aviso_de_pagamento_aberto_por_comprador(arranjo: Arranjo) -> None:  # A-15, Spec §12
    abrir(arranjo)
    esperado = {
        arranjo.a: ("80,00", "4,00", "10,35", "94,35"),
        arranjo.b: ("90,00", "4,50", "11,65", "106,15"),
    }
    for comprador, (produtos, servico, frete, total) in esperado.items():
        (aviso,) = _avisos("pagamento_aberto", comprador)
        pedido = pedido_de(comprador)
        assert aviso.titulo == "Pagamento aberto: F"
        assert aviso.corpo == (
            f"Seu pedido da rodada de F foi congelado. Produtos: R$ {produtos}. "
            f"Serviço: R$ {servico}. Frete: R$ {frete}. Total: R$ {total}. "
            "Pague até 03/11/2026 às 10:00 (horário de Brasília). "
            "Esse prazo de 24 horas não é prorrogado."
        )
        assert aviso.link == f"/pedidos/{pedido.pk}/"
        assert aviso.chave == f"pagamento_aberto:{pedido.pk}:{comprador.pk}"
    assert Notificacao.objects.filter(evento="pagamento_aberto").count() == 2


@pytest.mark.acceptance
def test_falha_do_whatsapp_nao_desfaz_a_abertura(
    arranjo: Arranjo, relogio: RelogioControlado, simulador_whatsapp: Any
) -> None:  # A-16, cenário 24 (abertura real)
    simulador_whatsapp.falhar_sempre()
    ContaFactory._meta.model.objects.filter(pk=arranjo.a.pk).update(
        telefone="+5521999990000", whatsapp_consentido_em=T0
    )
    abrir(arranjo)
    for espera in (timedelta(0), timedelta(minutes=1), timedelta(minutes=10)):
        relogio.avancar(espera)
        processar_envios()
    assert Pedido.objects.count() == 2
    whatsapp = Envio.objects.get(canal="whatsapp", conta=arranjo.a)
    assert (whatsapp.situacao, whatsapp.tentativas) == ("falhou", 3)
    assert {e.situacao for e in Envio.objects.filter(canal="email", tipo="pagamento_aberto")} == {
        "enviado"
    }
    assert Pedido.objects.count() == 2
    assert _etapa(arranjo.rodada) == Etapa.PAGAMENTO
    cliente = Client()
    cliente.force_login(arranjo.a)
    pagina = cliente.get("/notificacoes/").content.decode()
    assert "Pagamento aberto: F" in pagina


def test_auditoria_da_abertura(arranjo: Arranjo) -> None:  # A-17
    abrir(arranjo)
    (entrada,) = EntradaAuditoria.objects.filter(acao=ACAO)
    assert entrada.autor_tipo == "usuario"
    assert entrada.autor_id == str(arranjo.admin.pk)
    alteracoes = entrada.alteracoes
    assert alteracoes["t0"] == "2026-11-02T13:00:00+00:00"
    assert alteracoes["frete"] == "22.00"
    assert alteracoes["total_produtos"] == "170.00"
    assert alteracoes["pedidos"] == 2
    assert alteracoes["resultado"] == "pagamento"
    assert alteracoes["rodada"] == arranjo.rodada.pk
    assert alteracoes["ciclo"] == arranjo.ciclo.pk
    assert alteracoes["removidas"] == []


def test_o_total_da_abertura_e_o_valor_elegivel_do_progresso(arranjo: Arranjo) -> None:
    antes = progresso_da_rodada(
        Rodada.objects.select_related("fornecedor").get(pk=arranjo.rodada.pk)
    )
    abrir(arranjo)
    assert abertura_unica().total_produtos == antes.valor_elegivel


def test_excedente_na_abertura_sai_e_o_pedido_so_leva_caixas_completas(
    relogio: RelogioControlado,
) -> None:
    relogio.congelar(T0)
    arranjo = montar_arranjo()
    ParcelaFactory.create(
        comprador=arranjo.a,
        produto=arranjo.p2,
        quantidade_original=D("3"),
        quantidade_reservada=D("3"),
    )  # P2 passa a 15: duas caixas e 3 de excedente
    abrir(arranjo)
    item = ItemDoPedido.objects.get(pedido=pedido_de(arranjo.a), produto=arranjo.p2)
    assert item.quantidade == D("4")
    (removido,) = _avisos("excedentes_removidos", arranjo.a)
    assert "3 unidade de P2 não completaram caixa" in removido.corpo
    assert "Continuam no seu interesse: 4 unidade." in removido.corpo
    assert sum(p.quantidade for p in ParcelaNoPedido.objects.filter(item__produto=arranjo.p2)) == 12
