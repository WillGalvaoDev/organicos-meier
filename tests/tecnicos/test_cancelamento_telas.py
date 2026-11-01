"""E12-06: telas do cancelamento para o administrador (acceptance A-1 a A-13 e A-18)."""

import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.test import Client

from apps.financeiro.models import ObrigacaoComComprador
from apps.rodadas.models import Rodada
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.cancelamento import Ci
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H
INDICACAO = "Informe se existe reembolso devido."
SO_A_INDICACAO = (
    "O cancelamento vale para a rodada inteira e só recebe a indicação de reembolso e a "
    "mensagem opcional."
)


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _pagina(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/estoque/"


def _rota(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/cancelar/"


def _tela(
    client: Client, relogio: RelogioControlado, **arranjo: Any
) -> tuple[Any, Any, Any, bytes]:
    relogio.congelar(T0)
    conta, credencial = administrador_com_passkey(client)
    a, x, y = arranjo_ap(relogio, **arranjo)
    assert a.admin.pk == conta.pk
    return a, x, y, credencial


def _etapa(a: Any) -> str:
    return str(Rodada.objects.get(pk=a.rodada.pk).etapa)


def test_a_pagina_oferece_o_bloco_de_cancelamento(
    client: Client, relogio: RelogioControlado
) -> None:  # A-1
    a, _x, _y, _ = _tela(client, relogio)
    html = client.get(_pagina(a)).content.decode()
    texto = _texto(client.get(_pagina(a)))
    assert "Cancelar rodada" in texto
    assert (
        "O cancelamento vale para todos os compradores da rodada e não pode ser desfeito." in texto
    )
    assert "Com reembolso integral para quem pagou" in texto
    assert "Sem reembolso (não inicia novas devoluções)" in texto
    assert "Mensagem aos compradores (opcional)" in texto
    radios = re.findall(r'<input[^>]*name="reembolso"[^>]*>', html)
    assert len(radios) == 2
    assert all("checked" not in r for r in radios)
    assert 'name="motivo"' not in html
    assert 'name="compradores"' not in html


def test_cancelar_com_reembolso_pela_tela(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, x, _y, _ = _tela(client, relogio)
    pagar(relogio, sim, x)
    resposta = client.post(_rota(a), {"reembolso": "sim", "mensagem": "Fornecedor sem colheita"})
    assert resposta.status_code == 302
    assert resposta["Location"] == _pagina(a)
    texto = _texto(client.get(_pagina(a)))
    assert "Rodada cancelada." in texto
    assert "As devoluções integrais foram geradas e autorizadas." in texto
    assert a.admin.nome in texto
    assert "com reembolso" in texto
    assert "Fornecedor sem colheita" in texto
    assert "94,35" in texto
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo="cancelamento_da_rodada")
    assert f"/financeiro/devolucoes/{obrigacao.pk}/" in client.get(_pagina(a)).content.decode()


def test_cancelar_sem_reembolso_pela_tela(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    a, x, _y, _ = _tela(client, relogio)
    pagar(relogio, sim, x)
    resposta = client.post(_rota(a), {"reembolso": "nao"}, follow=True)
    texto = _texto(resposta)
    assert "Rodada cancelada." in texto
    assert "As devoluções integrais foram geradas" not in texto
    assert "sem reembolso" in texto
    assert not ObrigacaoComComprador.objects.filter(motivo="cancelamento_da_rodada").exists()


@pytest.mark.parametrize("extra", [{"compradores": "1"}, {"motivo": "x"}])
def test_a_rota_recusa_campos_fora_da_indicacao(
    client: Client,
    relogio: RelogioControlado,
    extra: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-4
    from apps.rodadas import views

    a, _x, _y, _ = _tela(client, relogio)
    chamadas: list[Any] = []
    monkeypatch.setattr(views, "cancelar_rodada", lambda *args, **kwargs: chamadas.append(1))
    resposta = client.post(_rota(a), {"reembolso": "sim", **extra})
    assert resposta.status_code == 400
    assert SO_A_INDICACAO in _texto(resposta)
    assert chamadas == []
    assert _etapa(a) == "pagamento"


def test_aceita_so_a_indicacao(client: Client, relogio: RelogioControlado) -> None:  # A-5
    relogio.congelar(T0)
    administrador_com_passkey(client)
    ci = Ci()
    resposta = client.post(f"/administracao/rodadas/{ci.rodada.pk}/cancelar/", {"reembolso": "nao"})
    assert resposta.status_code == 302
    assert Rodada.objects.get(pk=ci.rodada.pk).etapa == "cancelada"


@pytest.mark.parametrize("dados", [{}, {"reembolso": "talvez"}])
def test_a_indicacao_e_obrigatoria(
    client: Client, relogio: RelogioControlado, dados: dict[str, str]
) -> None:  # A-6
    a, _x, _y, _ = _tela(client, relogio)
    resposta = client.post(_rota(a), dados)
    assert resposta.status_code == 400
    assert INDICACAO in _texto(resposta)
    assert _etapa(a) == "pagamento"


def test_comprador_e_fornecedor_nao_cancelam(client: Client, relogio: RelogioControlado) -> None:
    # A-7
    a, _x, _y, _ = _tela(client, relogio)
    for conta in (a.a, ContaFactory.create(fornecedor=True)):
        cliente = Client()
        cliente.force_login(conta)
        assert cliente.post(_rota(a), {"reembolso": "nao"}).status_code in (302, 403)
        assert cliente.get(_pagina(a)).status_code in (302, 403)
    assert _etapa(a) == "pagamento"


def test_sem_nova_autenticacao_recente_redireciona(
    client: Client, relogio: RelogioControlado
) -> None:  # A-8
    from tests.apoio.admin_fluxos import entrar_com_passkey_direta

    a, _x, _y, credencial = _tela(client, relogio)
    entrar_com_passkey_direta(client, credencial, a.admin)
    relogio.congelar(T0 + timedelta(hours=3))
    resposta = client.post(_rota(a), {"reembolso": "nao"})
    assert resposta.status_code == 302
    assert "reauthenticate" in resposta["Location"]
    assert _etapa(a) == "pagamento"


def test_get_na_rota_responde_405(client: Client, relogio: RelogioControlado) -> None:  # A-9
    a, _x, _y, _ = _tela(client, relogio)
    assert client.get(_rota(a)).status_code == 405


def test_cancelar_de_novo_responde_409(client: Client, relogio: RelogioControlado) -> None:
    # A-10
    a, _x, _y, _ = _tela(client, relogio)
    client.post(_rota(a), {"reembolso": "nao"})
    resposta = client.post(_rota(a), {"reembolso": "nao"})
    assert resposta.status_code == 409
    assert "Esta rodada já foi cancelada." in _texto(resposta)


def test_falha_da_consulta_responde_503(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-11
    a, x, _y, _ = _tela(client, relogio)
    pagar(relogio, sim, x)
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    resposta = client.post(_rota(a), {"reembolso": "sim"})
    assert resposta.status_code == 503
    assert "Não foi possível consultar o provedor; nada foi cancelado. Tente de novo." in _texto(
        resposta
    )
    assert _etapa(a) == "pagamento"


def test_pagina_da_rodada_cancelada_so_le(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    a, x, _y, _ = _tela(client, relogio)
    pagar(relogio, sim, x)
    client.post(_rota(a), {"reembolso": "sim"})
    html = client.get(_pagina(a)).content.decode()
    texto = _texto(client.get(_pagina(a)))
    for acao in (
        "Iniciar fechamento",
        "Abrir pagamento",
        "Iniciar apuração",
        "Aprovar resultado",
        "Cancelar rodada",
    ):
        assert acao not in texto
    assert "Salvar" not in texto
    assert 'name="limite"' not in html
    assert "Pedidos" in texto


def test_devolucao_do_cancelamento_nao_oferece_autorizar(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    from apps.financeiro.livro import saldo
    from apps.financeiro.reserva import sem_cobertura_da_obrigacao
    from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao
    from tests.apoio.financeiro import chave_nova, despesas, mover, receita_de

    a, x, _y, _ = _tela(client, relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    aprovar_resultado(a.admin, a.rodada)
    with transaction.atomic():
        mover(
            "cobertura_de_despesa",
            receita_de(a.rodada),
            despesas(),
            saldo(receita_de(a.rodada)),
            chave=chave_nova(),
        )
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    cancelar_rodada(a.admin, a.rodada, com_reembolso=True)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo="cancelamento_da_rodada")
    assert sem_cobertura_da_obrigacao(obrigacao) > 0
    lista = _texto(client.get("/financeiro/devolucoes/"))
    detalhe = _texto(client.get(f"/financeiro/devolucoes/{obrigacao.pk}/"))
    for texto in (lista, detalhe):
        assert "Autorizada pelo cancelamento da rodada" in texto
        assert "aguardando cobertura" in texto
    assert "Autorizar devolução" not in detalhe


def test_painel_mostra_o_pedido_cancelado_pela_rodada(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-18
    a, x, _y, _ = _tela(client, relogio)
    pagar(relogio, sim, x)
    client.post(_rota(a), {"reembolso": "sim"})
    html = client.get(_pagina(a)).content.decode()
    pedidos = re.search(r"<h3>Pedidos</h3>(.*?)<h3>|<h3>Pedidos</h3>(.*)", html, re.DOTALL)
    assert pedidos is not None
    trecho = pedidos.group(1) or pedidos.group(2)
    assert "Cancelado (rodada cancelada)" in " ".join(re.sub(r"<[^>]+>", " ", trecho).split())
