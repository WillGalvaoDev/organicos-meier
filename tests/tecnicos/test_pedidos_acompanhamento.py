"""E08-05: situação dos pedidos para o administrador (acceptance A-16 e A-17)."""

import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import PagamentoNoProvedor
from apps.pedidos.acompanhamento import devolucoes_devidas, situacao_dos_pedidos
from apps.pedidos.models import DestinoDoPagamento, Pedido
from apps.pedidos.pagamento import pedir_pagamento
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    cancelar_direto,
    marcar_pago,
    pedido_aberto,
    pedido_de,
    pedido_na_abertura,
    tentativa_criada,
)
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)


@pytest.fixture
def painel(
    client: Client, webauthn: Any, relogio: RelogioControlado, simulador_pagamentos: Any
) -> tuple[Arranjo, dict[str, Pedido], Client]:
    """X pago no prazo, Y pago na margem, Z com tentativa aberta, W sem tentativa, V cancelado
    por suspensão e U com a chamada de criação sem resposta; uma devolução por duplicidade em Y."""
    relogio.congelar(T0)
    administrador_logado(client)
    arranjo, x = pedido_aberto(relogio)
    abertura = x.abertura
    y = pedido_de(arranjo.b)
    compradores = {
        letra: ContaFactory.create(nome=f"Comprador {letra}") for letra in ("C", "D", "E", "G")
    }
    z = pedido_na_abertura(abertura, compradores["C"])
    w = pedido_na_abertura(abertura, compradores["D"])
    v = pedido_na_abertura(abertura, compradores["E"])
    u = pedido_na_abertura(abertura, compradores["G"])
    marcar_pago(x, T0 + 2 * H)
    marcar_pago(y, T0 + 30 * H)
    tentativa_criada(z)
    cancelar_direto(v, "suspensao")
    pedir_pagamento(compradores["G"], u)
    simulador_pagamentos.indisponivel()
    processar_chamadas()
    duplicado = PagamentoNoProvedor.objects.create(
        provedor="simulador",
        ambiente="testes",
        id_externo="dup-1",
        referencia_externa=y.referencia_externa,
        valor=y.total,
        situacao="aprovado",
        criado_no_provedor_em=T0 + H,
        expira_em=T0 + 24 * H,
        aprovado_no_provedor_em=T0 + 3 * H,
    )
    DestinoDoPagamento.objects.create(
        pagamento_id=duplicado.pk, pedido=y, destino="devolucao", motivo="duplicidade"
    )
    relogio.congelar(T0 + 31 * H)
    pedidos = {"X": x, "Y": y, "Z": z, "W": w, "V": v, "U": u}
    return arranjo, pedidos, client


def _linhas(html: str) -> dict[str, str]:
    """O texto de cada linha da tabela de pedidos, pelo nome do comprador."""
    resultado: dict[str, str] = {}
    for linha in re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL):
        texto = " ".join(re.sub(r"<[^>]+>", " ", linha).split())
        nome = re.search(r"Comprador [A-Z]", texto)
        if nome:
            resultado[nome.group(0)] = texto
    return resultado


@pytest.mark.acceptance
def test_a_pagina_mostra_a_linha_do_tempo_os_pedidos_e_as_devolucoes(
    painel: tuple[Arranjo, dict[str, Pedido], Client],
) -> None:  # A-16, Infra 4.3, Spec §13
    arranjo, pedidos, cliente = painel
    resposta = cliente.get(f"/administracao/rodadas/{arranjo.rodada.pk}/estoque/")
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Prazo de pagamento até 03/11/2026 às 10:00. Margem até 04/11/2026 às 10:00." in html
    assert "A apuração só pode começar depois disso, com a sua autorização." in html
    linhas = _linhas(html)
    esperado = {
        "Comprador A": "Pago no prazo",
        "Comprador B": "Pago na margem",
        "Comprador C": "Pagamento pendente",
        "Comprador D": "Não pago",
        "Comprador E": "Cancelado (suspensão)",
        "Comprador G": "Sem resposta do provedor",
    }
    for nome, situacao in esperado.items():
        assert situacao in linhas[nome], (nome, linhas[nome])
    assert "pagamento em duplicidade" in html
    assert "dup-1" in html
    assert "R$ 106,15" in html
    assert "Nenhuma devolução devida." not in html
    # nenhum formulário de alteração dos pedidos ou dos prazos
    for pedido in pedidos.values():
        assert f"/pedidos/{pedido.pk}/pagar/" not in html


def test_o_servico_devolve_as_linhas_e_as_devolucoes(
    painel: tuple[Arranjo, dict[str, Pedido], Client],
) -> None:
    _, pedidos, _ = painel
    abertura = pedidos["X"].abertura
    situacoes = {linha.comprador: linha.situacao for linha in situacao_dos_pedidos(abertura)}
    assert situacoes["Comprador A"] == "Pago no prazo"
    assert situacoes["Comprador B"] == "Pago na margem"
    (devolucao,) = devolucoes_devidas(abertura)
    assert (devolucao.id_externo, devolucao.valor, devolucao.motivo) == (
        "dup-1",
        pedidos["Y"].total,
        "pagamento em duplicidade",
    )


def test_sem_devolucoes_a_lista_diz_que_nao_ha(
    client: Client, webauthn: Any, relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    relogio.congelar(T0)
    administrador_logado(client)
    arranjo, _ = pedido_aberto(relogio)
    html = client.get(f"/administracao/rodadas/{arranjo.rodada.pk}/estoque/").content.decode()
    assert "Nenhuma devolução devida." in html


def test_comprador_e_fornecedor_nao_veem_a_pagina(
    painel: tuple[Arranjo, dict[str, Pedido], Client],
) -> None:  # A-17, Spec §2
    arranjo, _, _ = painel
    fornecedor = ContaFactory.create(fornecedor=True)
    for conta in (arranjo.a, fornecedor, None):
        cliente = Client()
        if conta is not None:
            cliente.force_login(conta)
        resposta = cliente.get(f"/administracao/rodadas/{arranjo.rodada.pk}/estoque/")
        assert resposta.status_code in (302, 403)
        assert "Comprador B" not in resposta.content.decode()
        assert "dup-1" not in resposta.content.decode()
