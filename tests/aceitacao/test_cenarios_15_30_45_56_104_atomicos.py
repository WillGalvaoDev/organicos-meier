"""Cenários 15, 30, 45, 56 e 104 / T-47 (E16-07, regras 2-E e 5: caracterização contra o simulador).

Cada teste executa a ação de uma afirmação atômica que nenhum teste existente provava por inteiro e
confere o resultado dela. O comportamento já existia, então os testes passaram na primeira execução.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.catalogo.quantidades import calcular_subtotal
from apps.financeiro.apuracao import registrar_apuracao_no_livro
from apps.financeiro.devolucoes import autorizar_devolucao
from apps.financeiro.livro import EXTERIOR
from apps.financeiro.models import (
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
    TipoDeMovimento,
)
from apps.financeiro.reserva import pendente_da_despesa
from apps.interesses.models import ParcelaDeInteresse
from apps.interesses.servicos import adicionar_interesse
from apps.nucleo.auditoria import SISTEMA
from apps.pagamentos.chamadas import processar_chamadas
from apps.pedidos.apuracao import iniciar_apuracao
from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
from apps.pedidos.models import Pedido
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import arranjo_ap, pagar
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.financeiro import montar_ap, mover, pagar_pedido, reserva
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory
from tests.tecnicos.test_apuracao_retorno import INSUFICIENTE, PRAZO
from tests.tecnicos.test_fila_ponta_a_ponta import abrir_r2, montar_fp

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _rodada_devolvida_com_x_pago(relogio: RelogioControlado, sim: Any) -> tuple[Any, Any]:
    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    return a, x


def test_cenario_15_o_estorno_do_pago_na_rodada_devolvida_e_autorizavel(
    relogio: RelogioControlado, sim: Any
) -> None:
    a, x = _rodada_devolvida_com_x_pago(relogio, sim)
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "interesse"
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x)
    assert not ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).exists()
    autorizar_devolucao(obrigacao, autor=a.admin)
    processar_chamadas()
    assert ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "concluida"
    assert EstornoSimulado.objects.filter(situacao="concluido").count() == 1


def test_cenario_56_o_estorno_pendente_nao_impede_novas_adicoes(
    relogio: RelogioControlado, sim: Any
) -> None:
    a, x = _rodada_devolvida_com_x_pago(relogio, sim)
    novo = ContaFactory.create(nome="Comprador C")
    adicionar_interesse(novo, a.p1, D("5"))
    assert ParcelaDeInteresse.objects.filter(comprador=novo, produto=a.p1).exists()
    assert ObrigacaoComComprador.objects.filter(pedido=x).count() == 1
    assert not ParcelaDeDevolucao.objects.exists()


def test_cenario_30_a_tarifa_e_coberta_pela_receita_de_servico(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    ap = montar_ap()
    pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, timedelta(hours=1))
    mover(TipoDeMovimento.APORTE, EXTERIOR, reserva(), "1000.00", autor=ap.admin, justificativa="A")
    from apps.financeiro.models import Despesa

    tarifa = Despesa.objects.get(tipo="tarifa", rodada=ap.rodada)
    assert pendente_da_despesa(tarifa) == D("1.25")
    registrar_apuracao_no_livro(ap.ciclo, [ap.x], autor=SISTEMA)
    assert pendente_da_despesa(tarifa) == D("0.00")
    cobertura = MovimentoFinanceiro.objects.get(
        tipo=TipoDeMovimento.COBERTURA_DE_DESPESA, origem_id=tarifa.pk
    )
    assert "Tarifa coberta pela receita de serviço" in cobertura.justificativa


def test_cenario_45_os_registros_anteriores_continuam_consultaveis_depois_do_cancelamento(
    client: Client, relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    admin, credencial = administrador_com_passkey(client)
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    cancelar_rodada(admin, a.rodada, com_reembolso=False)
    entrar_de_novo(client, credencial, admin)
    resposta = client.get("/administracao/historico/")
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    assert "pedido.quitar" in texto
    assert "rodada.cancelar" in texto


def test_cenario_104_a_cobranca_do_pedido_ignora_as_pendentes(
    relogio: RelogioControlado, sim: Any
) -> None:
    from apps.pedidos.abertura import abrir_pagamento
    from apps.rodadas.fechamento import encerrar_fechamento, iniciar_fechamento

    fp = montar_fp(relogio, sim)
    r2 = abrir_r2(fp, 10, com_q=True)
    adicionar_interesse(fp.a, fp.q, D("10"))
    iniciar_fechamento(fp.admin, r2)
    relogio.congelar(T0 + timedelta(hours=80))
    encerrar_fechamento(r2)
    r2.refresh_from_db()
    abrir_pagamento(fp.admin, r2, D("10.00"))
    pedido = Pedido.objects.get(comprador=fp.c, abertura__rodada=r2)
    assert pedido.produtos == calcular_subtotal(fp.p.preco, D("4.000"))
