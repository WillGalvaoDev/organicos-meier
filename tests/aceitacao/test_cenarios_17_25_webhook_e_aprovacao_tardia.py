"""Cenários 17 e 25 (E16-07, regra 5: caracterização contra o simulador).

A matriz de rastreabilidade não tinha teste que enviasse o webhook repetido (cenário 17) nem um com
aprovação em `T0 + 30h` e notificação depois de `T0 + 48h` (cenário 25). Os comportamentos já
existem; estes testes os caracterizam, e por isso passam na primeira execução.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.financeiro.devolucoes import autorizar_devolucao, confirmar_devolucao_excepcional
from apps.financeiro.livro import conta_da_obrigacao
from apps.financeiro.models import ObrigacaoComComprador, ParcelaDeDevolucao
from apps.financeiro.obrigacoes import _liquidado
from apps.fornecedores.models import Fornecedor
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import AvisoRecebido, PagamentoNoProvedor
from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao
from apps.pedidos.models import (
    DestinoDoPagamento,
    LinhaDoPedidoFormal,
    Pedido,
    PedidoFormal,
    SituacaoDoPedido,
    TentativaDeEnvioDoPedidoFormal,
)
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.apuracao import arranjo_ap, pagar
from tests.apoio.pedido_formal import EMAIL_DO_PEDIDO, PRAZO, M, arranjo_af, processar
from tests.apoio.pedidos import T0, Arranjo, pedido_aberto, tentativa_criada
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

H = timedelta(hours=1)
D = Decimal
REPETICOES = 5


@dataclass
class Cenario:
    arranjo: Arranjo
    x: Pedido
    sim: Any
    p: str


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> Cenario:
    arranjo, x = pedido_aberto(relogio)
    tentativa = tentativa_criada(x)
    assert tentativa.id_externo is not None
    return Cenario(arranjo, x, simulador_pagamentos, tentativa.id_externo)


def _aprovar_e_receber(c: Cenario, relogio: RelogioControlado, quando: Any, chega: Any) -> None:
    """O provedor aprova em `quando`; o webhook chega em `chega`, repetido `REPETICOES` vezes."""
    relogio.congelar(chega)
    c.sim.aprovar(c.p, em=quando)
    c.sim.entregar_avisos(vezes=REPETICOES)
    processar_chamadas()


def test_cenario_17_webhook_repetido_nao_duplica_pagamento_pedido_e_mensagem(
    cenario: Cenario, relogio: RelogioControlado
) -> None:
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 2 * H, T0 + 2 * H + timedelta(minutes=1))
    assert AvisoRecebido.objects.count() == 1
    assert PagamentoNoProvedor.objects.filter(id_externo=c.p).count() == 1
    assert DestinoDoPagamento.objects.filter(pagamento__id_externo=c.p).count() == 1
    assert SituacaoDoPedido.objects.get(pedido=c.x).situacao == "pago"
    assert EntradaAuditoria.objects.filter(acao="pedido.quitar").count() == 1
    avisos = Notificacao.objects.filter(conta=c.arranjo.a, evento="pagamento_confirmado")
    assert avisos.count() == 1


def test_cenario_17_webhook_repetido_nao_duplica_estorno(
    cenario: Cenario, relogio: RelogioControlado
) -> None:
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 49 * H, T0 + 50 * H)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=c.x)
    autorizar_devolucao(obrigacao, autor=c.arranjo.admin)
    processar_chamadas()
    c.sim.reemitir_aviso(c.p)
    c.sim.entregar_avisos(vezes=REPETICOES)
    processar_chamadas()
    assert ObrigacaoComComprador.objects.filter(pedido=c.x).count() == 1
    assert ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).count() == 1
    assert EstornoSimulado.objects.filter(situacao="concluido").count() == 1


def test_cenario_25_aprovado_em_30h_e_avisado_depois_de_48h_quita_o_pedido(
    cenario: Cenario, relogio: RelogioControlado
) -> None:
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 30 * H, T0 + 50 * H)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=c.p)
    assert (destino.destino, destino.motivo, destino.pedido) == ("quita", "", c.x)
    situacao = SituacaoDoPedido.objects.get(pedido=c.x)
    assert (situacao.situacao, situacao.quitado_em) == ("pago", T0 + 30 * H)
    assert PagamentoNoProvedor.objects.get(id_externo=c.p).primeiro_aviso_em == T0 + 50 * H
    assert not ObrigacaoComComprador.objects.filter(pedido=c.x).exists()


def test_cenario_17_webhook_repetido_nao_cria_outro_pedido_nem_muda_a_situacao(
    cenario: Cenario, relogio: RelogioControlado
) -> None:
    c = cenario
    relogio.congelar(T0 + 2 * H + timedelta(minutes=1))
    c.sim.aprovar(c.p, em=T0 + 2 * H)
    c.sim.entregar_avisos()
    processar_chamadas()
    pedidos = list(Pedido.objects.order_by("pk").values())
    situacoes = list(SituacaoDoPedido.objects.order_by("pk").values())
    c.sim.reemitir_aviso(c.p)
    c.sim.entregar_avisos(vezes=REPETICOES)
    processar_chamadas()
    assert list(Pedido.objects.order_by("pk").values()) == pedidos
    assert list(SituacaoDoPedido.objects.order_by("pk").values()) == situacoes


def _emails_do_pedido() -> int:
    return len([m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]])


def test_cenario_17_webhook_repetido_depois_do_envio_nao_duplica_o_pedido_formal(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    a, x, _y, pedido = arranjo_af(relogio, simulador_pagamentos)
    assert processar(relogio, PRAZO) == 1
    linhas = list(LinhaDoPedidoFormal.objects.filter(pedido_formal=pedido).order_by("pk").values())
    tentativas = TentativaDeEnvioDoPedidoFormal.objects.count()
    enviados = _emails_do_pedido()
    quitado_por = SituacaoDoPedido.objects.get(pedido=x).quitado_por
    assert quitado_por is not None
    simulador_pagamentos.reemitir_aviso(quitado_por.id_externo)
    simulador_pagamentos.entregar_avisos(vezes=REPETICOES)
    processar_chamadas()
    processar(relogio, PRAZO + 10 * M)
    assert PedidoFormal.objects.filter(rodada=a.rodada).count() == 1
    assert (
        list(LinhaDoPedidoFormal.objects.filter(pedido_formal=pedido).order_by("pk").values())
        == linhas
    )
    assert TentativaDeEnvioDoPedidoFormal.objects.count() == tentativas == 1
    assert _emails_do_pedido() == enviados == 1


def test_cenario_17_webhook_repetido_antes_da_aprovacao_gera_um_so_pedido_formal(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    a, x, y = arranjo_ap(relogio)
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(email_pedido=EMAIL_DO_PEDIDO)
    for pedido in (x, y):
        id_externo = pagar(relogio, simulador_pagamentos, pedido)
        simulador_pagamentos.reemitir_aviso(id_externo)
        simulador_pagamentos.entregar_avisos(vezes=2)
        processar_chamadas()
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    aprovar_resultado(a.admin, a.rodada)
    pedido_formal = PedidoFormal.objects.get(rodada=a.rodada)
    quantidades = {
        linha.nome: linha.quantidade
        for linha in LinhaDoPedidoFormal.objects.filter(pedido_formal=pedido_formal)
    }
    assert quantidades == {"P1": D("11.000"), "P2": D("12.000")}
    assert processar(relogio, PRAZO) == 1
    assert TentativaDeEnvioDoPedidoFormal.objects.count() == 1
    assert _emails_do_pedido() == 1


def test_cenario_26_pagamento_tardio_devolvido_pela_devolucao_excepcional(
    cenario: Cenario, relogio: RelogioControlado, settings: Any, tmp_path: Path
) -> None:  # E16-07 regra 2-G: o pagamento tardio, não o parcial do arranjo de devolução
    settings.MEDIA_ROOT = tmp_path
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 49 * H, T0 + 50 * H)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=c.x)
    assert obrigacao.integral == c.x.total
    c.sim.recusar_estornos(c.p, "prazo_vencido")
    parcela = autorizar_devolucao(obrigacao, autor=c.arranjo.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    confirmacao = confirmar_devolucao_excepcional(
        parcela,
        autor=c.arranjo.admin,
        meio="transferencia",
        identificacao="TED-26",
        justificativa="Devolvido por transferência",
        comprovante=SimpleUploadedFile("c.pdf", b"%PDF-1.4 comprovante"),
    )
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida_fora_da_plataforma"
    assert (confirmacao.pedido_id, confirmacao.comprador_id) == (c.x.pk, c.arranjo.a.pk)
    assert _liquidado(conta_da_obrigacao(obrigacao)) == obrigacao.devido
