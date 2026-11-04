"""E13-04: telas do administrador, o pedido consolidado, as tentativas e o botão Reenviar pedido
(acceptance A-1 a A-17)."""

import re
import uuid
from typing import Any

import pytest
from django.core import mail
from django.test import Client

from apps.notificacoes.models import Notificacao
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.pedido_formal import (
    EMAIL_DO_PEDIDO,
    FALHA,
    PRAZO,
    M,
    af_falhas,
    af_meio,
    af_sucesso,
    arranjo_af,
    processar,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

SUCESSO = "Reenvio registrado: aceito pelo serviço de e-mail."
EM_ANDAMENTO = (
    "O envio automático ainda está em andamento; o reenvio fica disponível quando ele terminar."
)
RODADA_CANCELADA = "A rodada foi cancelada; o pedido formal não é reenviado."
RECARREGUE = "Recarregue a página e tente de novo."


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    html = resposta.content.decode()
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _pagina(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/pedido-formal/"


def _rota(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/pedido-formal/reenviar/"


def _admin(client: Client, relogio: RelogioControlado) -> bytes:
    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    return credencial


def _entrar(client: Client, credencial: bytes, a: Any) -> None:
    entrar_de_novo(client, credencial, a.admin)


def _token(resposta: Any) -> str:
    achado = re.search(r'name="token" value="([^"]+)"', resposta.content.decode())
    assert achado, "a página não traz o campo token"
    return achado.group(1)


def _tentativas() -> list[Any]:
    from apps.pedidos.models import TentativaDeEnvioDoPedidoFormal

    return list(TentativaDeEnvioDoPedidoFormal.objects.order_by("numero"))


def test_o_pedido_consolidado_e_as_tentativas(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    credencial = _admin(client, relogio)
    a, _x, _y, pedido = af_sucesso(relogio, sim)
    _entrar(client, credencial, a)
    resposta = client.get(_pagina(a))
    assert resposta.status_code == 200
    texto = _texto(resposta)
    assert f"Pedido formal nº {pedido.pk}" in texto
    assert "Emitido em 04/11/2026 10:00 (horário de Brasília)" in texto
    assert "P1 11 unidade — R$ 10,00 R$ 110,00" in texto
    assert "P2 12 unidade 2 R$ 5,00 R$ 60,00" in texto
    assert "Total dos produtos: R$ 170,00" in texto
    assert pedido.assunto in texto
    assert "Total dos produtos: R$ 170,00" in pedido.corpo
    assert "Envio automático concluído: aceito pelo serviço de e-mail." in texto
    assert "A aceitação pelo serviço de e-mail não comprova a entrega ao fornecedor." in texto
    assert "Automática 1/3" in texto
    assert "Aceito pelo serviço de e-mail" in texto
    assert EMAIL_DO_PEDIDO in texto
    assert 'name="token"' in resposta.content.decode()
    assert "Reenviar pedido" in texto
    assert "Cada acionamento faz uma única tentativa com o mesmo pedido formal." in texto


def test_depois_das_tres_falhas_o_formulario_aparece(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-2
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_falhas(relogio, sim, settings)
    _entrar(client, credencial, a)
    resposta = client.get(_pagina(a))
    texto = _texto(resposta)
    assert "Envio automático concluído sem sucesso depois de 3 tentativas." in texto
    assert texto.count("ConnectionError") == 3
    assert texto.count("Falha") >= 3
    assert 'name="token"' in resposta.content.decode()


def test_durante_o_ciclo_a_pagina_explica_e_nao_oferece_o_botao(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-3
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_meio(relogio, sim, settings)
    _entrar(client, credencial, a)
    resposta = client.get(_pagina(a))
    texto = _texto(resposta)
    assert (
        "Envio automático em andamento: tentativa 2 de 3 prevista para 04/11/2026 10:05." in texto
    )
    assert 'name="token"' not in resposta.content.decode()
    assert EM_ANDAMENTO in texto


def test_rodada_cancelada_interrompe_e_esconde_o_botao(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = arranjo_af(relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    processar(relogio, PRAZO + M)
    _entrar(client, credencial, a)
    resposta = client.get(_pagina(a))
    texto = _texto(resposta)
    assert "Envio interrompido: a rodada foi cancelada." in texto
    assert 'name="token"' not in resposta.content.decode()
    assert RODADA_CANCELADA in texto


def test_cada_carregamento_traz_um_token_novo(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_sucesso(relogio, sim)
    _entrar(client, credencial, a)
    primeiro, segundo = _token(client.get(_pagina(a))), _token(client.get(_pagina(a)))
    assert uuid.UUID(primeiro) != uuid.UUID(segundo)


def test_reenviar_depois_do_sucesso(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_sucesso(relogio, sim)
    _entrar(client, credencial, a)
    token = _token(client.get(_pagina(a)))
    resposta = client.post(_rota(a), {"token": token}, follow=True)
    assert resposta.redirect_chain[-1][0] == _pagina(a)
    texto = _texto(resposta)
    assert SUCESSO in texto
    assert "Manual" in texto
    assert a.admin.nome in texto
    assert [t.tipo for t in _tentativas()] == ["automatica", "manual"]


def test_duplo_clique_gera_um_envio_e_novo_acionamento_outro(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-7
    credencial = _admin(client, relogio)
    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    _entrar(client, credencial, a)
    mail.outbox.clear()
    token = _token(client.get(_pagina(a)))
    primeiro = client.post(_rota(a), {"token": token}, follow=True)
    segundo = client.post(_rota(a), {"token": token}, follow=True)
    assert SUCESSO in _texto(primeiro)
    assert "Este reenvio já tinha sido registrado." in _texto(segundo)
    assert len([m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]) == 1
    novo = _token(client.get(_pagina(a)))
    assert novo != token
    client.post(_rota(a), {"token": novo}, follow=True)
    enviados = [m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]
    assert len(enviados) == 2
    assert all((m.subject, m.body) == (pedido.assunto, pedido.corpo) for m in enviados)


def test_reenvio_que_falha_continua_com_o_botao(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-8
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_falhas(relogio, sim, settings)
    _entrar(client, credencial, a)
    token = _token(client.get(_pagina(a)))
    settings.EMAIL_BACKEND = FALHA
    resposta = client.post(_rota(a), {"token": token}, follow=True)
    assert "Reenvio registrado: o serviço de e-mail recusou (ConnectionError)." in _texto(resposta)
    assert 'name="token"' in resposta.content.decode()


def test_reenvio_durante_o_ciclo_e_recusado_com_409(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-9
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_meio(relogio, sim, settings)
    _entrar(client, credencial, a)
    resposta = client.post(_rota(a), {"token": str(uuid.uuid4())})
    assert resposta.status_code == 409
    assert EM_ANDAMENTO in _texto(resposta)
    assert [t.tipo for t in _tentativas()] == ["automatica"]


def test_provedor_indisponivel_responde_503(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-10
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_falhas(relogio, sim, settings)
    _entrar(client, credencial, a)
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    resposta = client.post(_rota(a), {"token": str(uuid.uuid4())})
    assert resposta.status_code == 503
    assert (
        "Não foi possível consultar o provedor; o pedido não foi reenviado. Tente de novo."
        in _texto(resposta)
    )
    assert [t.tipo for t in _tentativas()] == ["automatica"] * 3


@pytest.mark.parametrize("campos", [{}, {"token": "abc"}])
def test_token_ausente_ou_invalido_responde_400(
    client: Client,
    relogio: RelogioControlado,
    sim: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
    campos: dict[str, str],
) -> None:  # A-11
    from apps.pedidos import reenvio_do_pedido_formal as modulo

    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_falhas(relogio, sim, settings)
    _entrar(client, credencial, a)
    consultas: list[str] = []
    monkeypatch.setattr(modulo, "consultar_antes_de_decidir", consultas.append)
    resposta = client.post(_rota(a), campos)
    assert resposta.status_code == 400
    assert RECARREGUE in _texto(resposta)
    assert not consultas
    assert [t.tipo for t in _tentativas()] == ["automatica"] * 3


def test_campos_extras_sao_ignorados(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-12
    credencial = _admin(client, relogio)
    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    _entrar(client, credencial, a)
    mail.outbox.clear()
    token = _token(client.get(_pagina(a)))
    resposta = client.post(
        _rota(a), {"token": token, "assunto": "x", "corpo": "y", "quantidade": "1"}, follow=True
    )
    assert SUCESSO in _texto(resposta)
    (enviado,) = [m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]
    assert (enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)


def test_so_o_administrador_acessa(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-13
    _admin(client, relogio)
    a, _x, _y, _pedido = af_falhas(relogio, sim, settings)
    fornecedor = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    for conta in (a.a, fornecedor):
        client.force_login(conta)
        assert client.get(_pagina(a)).status_code == 403
        assert client.post(_rota(a), {"token": str(uuid.uuid4())}).status_code == 403
    assert [t.tipo for t in _tentativas()] == ["automatica"] * 3


def test_a_rota_so_aceita_post(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-14
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_falhas(relogio, sim, settings)
    _entrar(client, credencial, a)
    assert client.get(_rota(a)).status_code == 405


def test_sem_pedido_formal_a_pagina_e_a_rota_dao_404(
    client: Client, relogio: RelogioControlado
) -> None:  # A-15
    from tests.apoio.apuracao import arranjo_ap

    credencial = _admin(client, relogio)
    a, _x, _y = arranjo_ap(relogio)
    _entrar(client, credencial, a)
    assert client.get(_pagina(a)).status_code == 404
    assert client.post(_rota(a), {"token": str(uuid.uuid4())}).status_code == 404


def test_a_pagina_da_rodada_traz_o_bloco_do_pedido_formal(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    credencial = _admin(client, relogio)
    a, _x, _y, pedido = af_sucesso(relogio, sim)
    _entrar(client, credencial, a)
    resposta = client.get(f"/administracao/rodadas/{a.rodada.pk}/estoque/")
    texto = _texto(resposta)
    assert "Pedido formal" in texto
    assert f"nº {pedido.pk}" in texto
    assert "R$ 170,00" in texto
    assert "Envio automático concluído: aceito pelo serviço de e-mail." in texto
    assert f'href="{_pagina(a)}"' in resposta.content.decode()


def test_o_link_do_aviso_leva_ao_botao(
    client: Client, relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-17
    credencial = _admin(client, relogio)
    a, _x, _y, _pedido = af_falhas(relogio, sim, settings)
    _entrar(client, credencial, a)
    aviso = Notificacao.objects.get(evento="falha_no_pedido_formal", conta=a.admin)
    assert aviso.link is not None
    resposta = client.get(aviso.link)
    assert resposta.status_code == 200
    assert 'name="token"' in resposta.content.decode()
