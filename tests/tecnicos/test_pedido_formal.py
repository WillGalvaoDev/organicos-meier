"""E13-01: o pedido formal, registro único e congelado do ciclo aprovado (acceptance A-1 a A-17)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.core import mail
from django.db import IntegrityError, connection, transaction

from apps.financeiro.livro import conta
from apps.financeiro.models import (
    ApuracaoNoLivro,
    Destinacao,
    MovimentoFinanceiro,
    TransferenciaFinanceira,
)
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.pedidos import T0, pedido_de
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H
CORPO_SEM_FRETE = (
    "Pedido formal nº {pk}\n"
    "Fornecedor: F\n"
    "Rodada {rodada}, ciclo 1\n"
    "Emitido em 04/11/2026 10:00 (horário de Brasília)\n"
    "\n"
    "Produtos:\n"
    "- P1: 11 unidade × R$ 10,00 = R$ 110,00\n"
    "- P2: 12 unidade em 2 caixa(s) de 6 unidade × R$ 5,00 = R$ 60,00\n"
    "Total dos produtos: R$ 170,00\n"
    "\n"
    "Condições de entrega:\n"
    "Previsão de entrega: 11/11/2026 (prazo padrão de 7 dias)"
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _apurar(
    relogio: RelogioControlado, sim: Any, *, pagar_y: bool = True, **arranjo: Any
) -> tuple[Any, Any, Any]:
    """O arranjo AF antes da aprovação: AP-viável, X (e Y) pagos e a apuração iniciada em
    `T0 + 48h`. O relógio fica em `T0 + 48h`."""
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, y = arranjo_ap(relogio, **arranjo)
    pagar(relogio, sim, x)
    if pagar_y:
        pagar(relogio, sim, y)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    return a, x, y


def _aprovar(a: Any) -> Any:
    from apps.pedidos.apuracao import aprovar_resultado

    return aprovar_resultado(a.admin, a.rodada)


def _af(relogio: RelogioControlado, sim: Any, **arranjo: Any) -> tuple[Any, Any, Any, Any]:
    a, x, y = _apurar(relogio, sim, **arranjo)
    return a, x, y, _aprovar(a)


def _pedido_formal() -> Any:
    from apps.pedidos.models import PedidoFormal

    return PedidoFormal.objects.get()


def _linhas(pedido: Any) -> dict[str, Any]:
    return {linha.nome: linha for linha in pedido.linhas.all()}


def test_a_aprovacao_gera_o_pedido_formal_com_as_linhas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, _x, _y, aprovacao = _af(relogio, sim)
    pedido = _pedido_formal()
    assert pedido.aprovacao_id == aprovacao.pk
    assert pedido.ciclo_id == a.ciclo.pk
    assert pedido.rodada_id == a.rodada.pk
    assert pedido.fornecedor_id == a.fornecedor.pk
    assert pedido.emitido_em == PRAZO
    assert pedido.prazo_entrega_dias == 7
    assert pedido.total_produtos == D("170.00")
    linhas = _linhas(pedido)
    assert set(linhas) == {"P1", "P2"}
    p1, p2 = linhas["P1"], linhas["P2"]
    assert (p1.produto_id, p1.unidade, p1.preco_unitario) == (a.p1.pk, "unidade", D("10.00"))
    assert (p1.quantidade, p1.multiplo, p1.caixas, p1.valor_total) == (
        D("11.000"),
        None,
        None,
        D("110.00"),
    )
    assert (p2.produto_id, p2.unidade, p2.preco_unitario) == (a.p2.pk, "unidade", D("5.00"))
    assert (p2.quantidade, p2.multiplo, p2.caixas, p2.valor_total) == (
        D("12.000"),
        D("6.000"),
        2,
        D("60.00"),
    )


def test_so_entra_o_que_foi_pago_e_esta_em_caixa_valida(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    _a, _x, _y, _aprovacao = _af(relogio, sim, pagar_y=False)
    pedido = _pedido_formal()
    linhas = _linhas(pedido)
    assert set(linhas) == {"P1"}
    assert (linhas["P1"].quantidade, linhas["P1"].valor_total) == (D("6.000"), D("60.00"))
    assert pedido.total_produtos == D("60.00")


@pytest.mark.parametrize("pagar_y", [True, False])
def test_o_total_e_o_que_a_apuracao_transferiu_ao_fornecedor(
    relogio: RelogioControlado, sim: Any, pagar_y: bool
) -> None:  # A-3
    a, _x, _y, _aprovacao = _af(relogio, sim, pagar_y=pagar_y)
    no_livro = ApuracaoNoLivro.objects.get(ciclo=a.ciclo)
    destino = conta(Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk)
    transferido = sum(
        (
            t.valor
            for t in TransferenciaFinanceira.objects.filter(
                movimento=no_livro.movimento, para=destino
            )
        ),
        D("0.00"),
    )
    assert _pedido_formal().total_produtos == transferido


def test_a_previsao_inicial_conta_o_prazo_do_fornecedor(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.pedidos.pedido_formal import previsao_vigente

    from apps.pedidos.models import PrevisaoDeEntrega

    a, _x, _y, _aprovacao = _af(relogio, sim)
    (previsao,) = PrevisaoDeEntrega.objects.all()
    assert previsao.origem == "padrao"
    assert previsao.autor_id is None
    assert previsao.data == date(2026, 11, 11)
    assert (previsao.rodada_id, previsao.ciclo_id) == (a.rodada.pk, a.ciclo.pk)
    assert _pedido_formal().previsao_inicial == date(2026, 11, 11)
    assert previsao_vigente(a.ciclo) == previsao


def test_a_previsao_conta_o_dia_de_brasilia(relogio: RelogioControlado, sim: Any) -> None:  # A-5
    from apps.pedidos.apuracao import aprovar_resultado

    a, _x, _y = _apurar(relogio, sim)
    relogio.congelar(datetime(2026, 11, 5, 2, 30, tzinfo=UTC))  # 23:30 de 04/11 em Brasília
    aprovar_resultado(a.admin, a.rodada)
    assert _pedido_formal().previsao_inicial == date(2026, 11, 11)


def test_o_conteudo_do_e_mail_sem_informacoes_de_frete(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    a, _x, _y, _aprovacao = _af(relogio, sim)
    pedido = _pedido_formal()
    assert pedido.assunto == f"Pedido formal nº {pedido.pk} — Orgânicos Méier — F"
    assert pedido.corpo == CORPO_SEM_FRETE.format(pk=pedido.pk, rodada=a.rodada.pk)


def test_o_conteudo_do_e_mail_com_informacoes_de_frete(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    from apps.fornecedores.models import Fornecedor

    a, x, y = arranjo_ap(relogio)
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(
        informacoes_frete="Entrega no galpão às terças"
    )
    from apps.pedidos.apuracao import iniciar_apuracao

    pagar(relogio, sim, x)
    pagar(relogio, sim, y)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    _aprovar(a)
    pedido = _pedido_formal()
    assert pedido.corpo.endswith(
        "Previsão de entrega: 11/11/2026 (prazo padrão de 7 dias)\n"
        "Informações de frete: Entrega no galpão às terças"
    )


def test_o_pedido_formal_nao_identifica_comprador_nem_cobranca(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    a, _x, _y, _aprovacao = _af(relogio, sim)
    pedido = _pedido_formal()
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pedido_formal.gerar")
    textos = [pedido.assunto, pedido.corpo, repr(auditoria.alteracoes)]
    for linha in pedido.linhas.all():
        textos.append(repr(sorted(vars(linha).items(), key=lambda par: par[0])))
    proibidos = [
        a.a.nome,
        a.a.email,
        a.b.nome,
        a.b.email,
        "Comprador",
        "serviço",
        "8,50",
        "8.50",
        "22,00",
        "22.00",
    ]
    for texto in textos:
        for proibido in proibidos:
            assert proibido not in texto, (proibido, texto)
    campos = {campo.name for campo in type(pedido)._meta.get_fields()}
    campos |= {campo.name for campo in type(pedido.linhas.first())._meta.get_fields()}
    assert not {"comprador", "pedido", "conta"} & campos
    assert not {"comprador", "pedido", "compradores", "pedidos"} & set(auditoria.alteracoes)


def test_produto_fracionario_em_caixas_de_meio_quilo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    from apps.catalogo.models import Unidade
    from apps.pedidos.apuracao import iniciar_apuracao
    from tests.apoio.pedidos import abrir, montar_arranjo
    from tests.fabricas import EstoqueDaRodadaFactory, ParcelaFactory, ProdutoFactory

    relogio.congelar(T0)
    a = montar_arranjo(minimo="50.00", parcelas_de_p2=())
    p4 = ProdutoFactory.create(
        fornecedor=a.fornecedor,
        nome="P4",
        unidade=Unidade.KG,
        preco=D("7.99"),
        incremento=D("0.250"),
        multiplo=D("0.500"),
    )
    EstoqueDaRodadaFactory.create(rodada=a.rodada, produto=p4, limite=None)
    for dono, quantidade in ((a.a, "0.750"), (a.b, "0.250")):
        ParcelaFactory.create(
            comprador=dono,
            produto=p4,
            quantidade_original=D(quantidade),
            quantidade_reservada=D(quantidade),
        )
    abrir(a, "22.00")
    relogio.congelar(T0 + H)
    pagar(relogio, sim, pedido_de(a.a))
    pagar(relogio, sim, pedido_de(a.b))
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    _aprovar(a)
    pedido = _pedido_formal()
    linha = _linhas(pedido)["P4"]
    assert (linha.quantidade, linha.caixas, linha.multiplo) == (D("1.000"), 2, D("0.500"))
    from apps.pedidos.models import ItemDoPedido

    esperado = sum((i.subtotal for i in ItemDoPedido.objects.filter(produto=p4)), D("0.00"))
    assert linha.valor_total == esperado
    assert "- P4: 1 kg em 2 caixa(s) de 0,5 kg × R$ 7,99 = " in pedido.corpo
    assert "1 kg em 2 caixa(s) de 0,5 kg" in pedido.corpo


def test_so_a_caixa_invalidada_sai_do_pedido_formal(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    a, x, y = arranjo_ap(relogio, parcelas_de_p2=(("a", 4), ("c", 2), ("a", 2), ("b", 4)))
    assert a.c is not None
    from apps.pedidos.apuracao import iniciar_apuracao

    z = pedido_de(a.c)
    pagar(relogio, sim, x)
    pagar(relogio, sim, z)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    _aprovar(a)
    pedido = _pedido_formal()
    linhas = _linhas(pedido)
    assert (linhas["P2"].quantidade, linhas["P2"].caixas, linhas["P2"].valor_total) == (
        D("6.000"),
        1,
        D("30.00"),
    )
    assert linhas["P1"].quantidade == D("6.000")  # as unidades de B ficam de fora
    assert y.pk != x.pk


def test_gerar_de_novo_devolve_o_existente_sem_escrever(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-11
    from apps.pedidos.pedido_formal import gerar_pedido_formal

    from apps.pedidos.models import (
        EnvioDoPedidoFormal,
        LinhaDoPedidoFormal,
        PedidoFormal,
        PrevisaoDeEntrega,
    )

    _a, _x, _y, aprovacao = _af(relogio, sim)
    existente = _pedido_formal()
    foto = (
        PedidoFormal.objects.count(),
        LinhaDoPedidoFormal.objects.count(),
        PrevisaoDeEntrega.objects.count(),
        EnvioDoPedidoFormal.objects.count(),
        EntradaAuditoria.objects.count(),
    )
    with transaction.atomic():
        assert gerar_pedido_formal(aprovacao).pk == existente.pk
    assert foto == (
        PedidoFormal.objects.count(),
        LinhaDoPedidoFormal.objects.count(),
        PrevisaoDeEntrega.objects.count(),
        EnvioDoPedidoFormal.objects.count(),
        EntradaAuditoria.objects.count(),
    )


def test_sem_aprovacao_valida_nao_ha_pedido_formal(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    from apps.pedidos.pedido_formal import gerar_pedido_formal

    from apps.pedidos.models import ApuracaoFinal, PedidoFormal

    a, _x, _y = _apurar(relogio, sim)  # apurada e não aprovada
    assert not PedidoFormal.objects.exists()
    with pytest.raises(ValueError), transaction.atomic():
        gerar_pedido_formal(None)  # type: ignore[arg-type]
    assert not PedidoFormal.objects.exists()
    assert ApuracaoFinal.objects.filter(ciclo=a.ciclo).exists()


def test_retorno_para_interesse_nunca_gera_pedido_formal(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    from apps.pedidos.pedido_formal import gerar_pedido_formal

    from apps.pedidos.apuracao import iniciar_apuracao
    from apps.pedidos.models import AprovacaoDoResultado, ApuracaoFinal, PedidoFormal

    a, x, _y = arranjo_ap(relogio, minimo="100.00", limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    apuracao = ApuracaoFinal.objects.get(ciclo=a.ciclo)
    assert apuracao.resultado == "retorno_para_interesse"
    assert not PedidoFormal.objects.exists()
    # uma aprovação gravada à força não vale: a função recusa um resultado que não é válido
    aprovacao = AprovacaoDoResultado.objects.create(
        apuracao=apuracao, autor=a.admin, aprovada_em=PRAZO
    )
    with pytest.raises(ValueError), transaction.atomic():
        gerar_pedido_formal(aprovacao)
    assert not PedidoFormal.objects.exists()


def test_o_envio_nasce_em_andamento_sem_enviar_nada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    from apps.pedidos.models import EnvioDoPedidoFormal

    mail.outbox.clear()
    _af(relogio, sim)
    envio = EnvioDoPedidoFormal.objects.get()
    assert envio.pedido_formal_id == _pedido_formal().pk
    assert envio.situacao == "em_andamento"
    assert envio.automaticas == 0
    assert envio.proxima_tentativa_em == PRAZO
    assert envio.concluido_em is None
    assert envio.motivo_da_interrupcao == ""
    assert not [m for m in mail.outbox if "Pedido formal" in m.subject]


def test_o_pedido_formal_so_aceita_insercao(relogio: RelogioControlado, sim: Any) -> None:  # A-14
    from apps.pedidos.models import LinhaDoPedidoFormal, PedidoFormal, PrevisaoDeEntrega

    _af(relogio, sim)
    pedido = _pedido_formal()
    linha = pedido.linhas.first()
    previsao = PrevisaoDeEntrega.objects.get()
    for registro in (pedido, linha, previsao):
        with pytest.raises(RegistroImutavel):
            registro.save()
        with pytest.raises(RegistroImutavel):
            registro.delete()
    for modelo in (PedidoFormal, LinhaDoPedidoFormal, PrevisaoDeEntrega):
        with pytest.raises(RegistroImutavel):
            modelo.objects.all().update(pk=1)
        with pytest.raises(RegistroImutavel):
            modelo.objects.all().delete()
    tabelas = {
        "pedidos_pedidoformal": "assunto = 'x'",
        "pedidos_linhadopedidoformal": "nome = 'x'",
        "pedidos_previsaodeentrega": "origem = 'padrao'",
    }
    for tabela, atribuicao in tabelas.items():
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"UPDATE {tabela} SET {atribuicao}")
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {tabela}")


def test_uma_linha_incoerente_desfaz_a_aprovacao(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-15
    from apps.pedidos import pedido_formal as modulo
    from apps.pedidos.models import AprovacaoDoResultado, PedidoFormal

    a, _x, _y = _apurar(relogio, sim)
    original = modulo._valor_da_linha

    def valor_errado(*args: Any, **kwargs: Any) -> Decimal:
        return original(*args, **kwargs) + D("0.01")

    monkeypatch.setattr(modulo, "_valor_da_linha", valor_errado)
    with pytest.raises(modulo.PedidoFormalIncoerente):
        _aprovar(a)
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "pagamento"
    assert not AprovacaoDoResultado.objects.exists()
    assert not ApuracaoNoLivro.objects.exists()
    assert not PedidoFormal.objects.exists()
    assert not MovimentoFinanceiro.objects.filter(chave=f"apuracao:{a.ciclo.pk}").exists()


def test_a_auditoria_do_pedido_formal(relogio: RelogioControlado, sim: Any) -> None:  # A-16
    a, _x, _y, _aprovacao = _af(relogio, sim)
    pedido = _pedido_formal()
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pedido_formal.gerar")
    assert (auditoria.autor_tipo, auditoria.autor_id) == ("sistema", None)
    dados = auditoria.alteracoes
    assert dados["pedido_formal"] == pedido.pk
    assert dados["ciclo"] == a.ciclo.pk
    assert dados["total_produtos"] == "170.00"
    assert dados["previsao_inicial"] == "2026-11-11"
    assert dados["linhas"] == [
        {"produto": a.p1.pk, "quantidade": "11.000", "caixas": None, "valor": "110.00"},
        {"produto": a.p2.pk, "quantidade": "12.000", "caixas": 2, "valor": "60.00"},
    ]


def test_as_quantidades_pendentes_nao_entram(relogio: RelogioControlado, sim: Any) -> None:  # A-17
    from apps.interesses.models import ParcelaDeInteresse

    a, _x, _y, _aprovacao = _af(relogio, sim, pendente_a_p1=2)
    assert _linhas(_pedido_formal())["P1"].quantidade == D("11.000")
    parcela = ParcelaDeInteresse.objects.get(comprador=a.a, produto=a.p1)
    assert parcela.quantidade_pendente == D("2.000")
