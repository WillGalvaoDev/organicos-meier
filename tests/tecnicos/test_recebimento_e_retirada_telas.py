"""E14-06: as telas do administrador, recebimento, ocorrências, liberação, retiradas e descartes
(acceptance A-1 a A-23 e A-25)."""

import re
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import H
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.entrega import (
    arranjo_ae,
    item_de,
    liberar,
    ocorrer,
    receber_tudo,
    registrar_endereco,
    retirar,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
L = T0 + 72 * H
RECARREGUE = "Recarregue a página e tente de novo."
PREENCHA = "Preencha todos os campos."


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _ae(
    client: Client,
    relogio: RelogioControlado,
    sim: Any,
    *,
    estado: str = "ae",
    **opcoes: Any,
) -> tuple[Any, Any, Any, bytes]:
    """O AE com o administrador logado. `estado`: `ae`, `recebido` ou `liberada`. O endereço de
    retirada fica registrado, e o relógio fica em `T0 + 48h` (`L` na liberada)."""
    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    a, x, y, pf = arranjo_ae(relogio, sim, **opcoes)
    registrar_endereco(a.admin)
    if estado in ("recebido", "liberada"):
        receber_tudo(a, pf)
    if estado == "liberada":
        liberar(relogio, a)
    entrar_de_novo(client, credencial, a.admin)
    return a, x, y, credencial


def _rota(a: Any, sufixo: str) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/{sufixo}/"


def _acionamento(client: Client, url: str, acao: str) -> str:
    """O `acionamento` do formulário da página cuja ação termina em `acao`."""
    html = client.get(url).content.decode()
    achado = re.search(
        rf'<form[^>]*action="[^"]*{re.escape(acao)}"[^>]*>.*?name="acionamento" value="([^"]+)"',
        html,
        re.DOTALL,
    )
    assert achado, f"sem formulário para {acao}"
    return achado.group(1)


def _estado_dos_registros() -> Any:
    from apps.financeiro.models import Reembolso
    from apps.pedidos.models import (
        DescarteDeItem,
        OcorrenciaDeEntrega,
        RecebimentoDoFornecedor,
        RetiradaDeItem,
    )

    return tuple(
        modelo.objects.count()
        for modelo in (
            RecebimentoDoFornecedor,
            OcorrenciaDeEntrega,
            RetiradaDeItem,
            DescarteDeItem,
            Reembolso,
        )
    )


# --- recebimento ---------------------------------------------------------------------------


def test_a_pagina_de_recebimento(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, _x, _y, _c = _ae(client, relogio, sim)
    resposta = client.get(_rota(a, "recebimento"))
    assert resposta.status_code == 200
    texto = _texto(resposta)
    assert re.search(r"P1 unidade 11 0 0 0 0 11", texto)
    assert re.search(r"P2 unidade 12 0 0 0 0 12", texto)
    assert re.search(r'name="acionamento" value="[0-9a-f-]{36}"', resposta.content.decode())
    assert "Liberar retirada" not in texto
    assert "Ainda falta resolver: P1 (11 unidade); P2 (12 unidade)." in texto


def test_cada_carregamento_traz_um_acionamento_novo(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, _x, _y, _c = _ae(client, relogio, sim)
    url = _rota(a, "recebimento")
    assert _acionamento(client, url, "recebimento/registrar/") != _acionamento(
        client, url, "recebimento/registrar/"
    )


def test_registrar_o_recebimento(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-3 e A-4
    a, _x, _y, _c = _ae(client, relogio, sim)
    url = _rota(a, "recebimento")
    campos = {
        "produto": a.p1.pk,
        "quantidade": "7",
        "acionamento": _acionamento(client, url, "recebimento/registrar/"),
    }
    resposta = client.post(_rota(a, "recebimento/registrar"), campos, follow=True)
    assert resposta.redirect_chain[-1][0] == url
    assert "Recebimento registrado: 7 unidade de P1." in _texto(resposta)
    repetida = client.post(_rota(a, "recebimento/registrar"), campos, follow=True)
    assert "Este registro já tinha sido feito." in _texto(repetida)
    assert _estado_dos_registros()[0] == 1


def test_recebimento_que_passa_do_pedido_formal(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, _x, _y, _c = _ae(client, relogio, sim)
    campos = {"produto": a.p1.pk, "quantidade": "12", "acionamento": str(uuid.uuid4())}
    resposta = client.post(_rota(a, "recebimento/registrar"), campos)
    assert resposta.status_code == 409
    assert "A quantidade passa do que falta receber deste produto (11 unidade)." in _texto(resposta)
    assert _estado_dos_registros()[0] == 0


@pytest.mark.parametrize(
    ("campos", "mensagem"),
    [
        ({"produto": "P1", "quantidade": "1"}, RECARREGUE),
        ({"produto": "P1", "quantidade": "1", "acionamento": "abc"}, RECARREGUE),
        ({"produto": "P1", "acionamento": "UUID"}, PREENCHA),
        ({"produto": "P1", "quantidade": "x", "acionamento": "UUID"}, PREENCHA),
    ],
)
def test_campos_ausentes_ou_malformados(
    client: Client, relogio: RelogioControlado, sim: Any, campos: dict[str, str], mensagem: str
) -> None:  # A-6
    a, _x, _y, _c = _ae(client, relogio, sim)
    enviados = {
        chave: (str(a.p1.pk) if valor == "P1" else str(uuid.uuid4()) if valor == "UUID" else valor)
        for chave, valor in campos.items()
    }
    resposta = client.post(_rota(a, "recebimento/registrar"), enviados)
    assert resposta.status_code == 400
    assert mensagem in _texto(resposta)
    assert _estado_dos_registros()[0] == 0


def test_quantidade_por_peso_com_virgula(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    a, _x, _y, _c = _ae(
        client,
        relogio,
        sim,
        unidade_de_p1="kg",
        incremento_de_p1="0.500",
        parcelas_de_p1=(("a", 2), ("b", 1)),
    )
    campos = {"produto": a.p1.pk, "quantidade": "2,5", "acionamento": str(uuid.uuid4())}
    assert client.post(_rota(a, "recebimento/registrar"), campos).status_code == 302
    from apps.pedidos.models import RecebimentoDoFornecedor

    assert RecebimentoDoFornecedor.objects.get().quantidade == D("2.5")


def test_a_liberacao_pela_tela(client: Client, relogio: RelogioControlado, sim: Any) -> None:  # A-8
    a, _x, _y, _c = _ae(client, relogio, sim, estado="recebido")
    url = _rota(a, "recebimento")
    assert "Liberar retirada" in _texto(client.get(url))
    relogio.congelar(L)
    campos = {"acionamento": _acionamento(client, url, "retirada/liberar/")}
    resposta = client.post(_rota(a, "retirada/liberar"), campos, follow=True)
    assert resposta.redirect_chain[-1][0] == _rota(a, "retiradas")
    assert "Retirada liberada. Os compradores foram avisados." in _texto(resposta)
    from apps.rodadas.models import Rodada

    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "disponivel_para_retirada"


def test_a_liberacao_sem_endereco(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    from apps.pedidos.models import EnderecoDeRetirada

    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    a, _x, _y, pf = arranjo_ae(relogio, sim)
    receber_tudo(a, pf)
    entrar_de_novo(client, credencial, a.admin)
    assert not EnderecoDeRetirada.objects.exists()
    resposta = client.get(_rota(a, "recebimento"))
    texto = _texto(resposta)
    assert "Liberar retirada" not in texto
    assert "/administracao/retirada/endereco/" in resposta.content.decode()
    recusada = client.post(_rota(a, "retirada/liberar"), {"acionamento": str(uuid.uuid4())})
    assert recusada.status_code == 409
    assert "Registre o endereço de retirada antes de liberar." in _texto(recusada)


def test_rodada_liberada_so_para_leitura(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    a, _x, _y, _c = _ae(client, relogio, sim, estado="liberada")
    resposta = client.post(
        _rota(a, "retirada/liberar"), {"acionamento": str(uuid.uuid4())}, follow=True
    )
    assert resposta.redirect_chain[-1][0] == _rota(a, "retiradas")
    assert "A retirada desta rodada já foi liberada." in _texto(resposta)
    texto = _texto(client.get(_rota(a, "recebimento")))
    assert "Retirada liberada em 05/11/2026 10:00, prazo até 12/11/2026 10:00" in texto
    assert "Registrar recebimento" not in texto


# --- ocorrências ---------------------------------------------------------------------------


def test_a_pagina_de_ocorrencias(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-11
    a, x, y, _c = _ae(client, relogio, sim)
    resposta = client.get(_rota(a, "ocorrencias"))
    assert resposta.status_code == 200
    texto = _texto(resposta)
    for pedido, comprador in ((x, a.a), (y, a.b)):
        assert f"Pedido {pedido.pk}" in texto
        assert comprador.nome in texto
    html = resposta.content.decode()
    for tipo in ("Faltante", "Incorreto", "Não entregue"):
        assert tipo in html
    assert re.search(r"P1 unidade 6 0 0 0 6", texto)
    assert re.search(r"P2 unidade 4 0 0 0 4", texto)
    assert re.search(r"P1 unidade 5 0 0 0 5", texto)
    assert re.search(r"P2 unidade 8 0 0 0 8", texto)


def test_registrar_a_ocorrencia(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    a, x, _y, _c = _ae(client, relogio, sim)
    url = _rota(a, "ocorrencias")
    campos = {
        "item": item_de(x, a.p1).pk,
        "tipo": "faltante",
        "quantidade": "2",
        "acionamento": _acionamento(client, url, "ocorrencias/registrar/"),
    }
    resposta = client.post(_rota(a, "ocorrencias/registrar"), campos, follow=True)
    assert resposta.redirect_chain[-1][0] == url
    texto = _texto(resposta)
    assert (
        "Ocorrência registrada. Reembolso de R$ 23,59 "
        "(produtos R$ 20,00, serviço R$ 1,00, frete R$ 2,59)." in texto
    )
    assert "antes da liberação" in texto
    from apps.financeiro.models import ObrigacaoComComprador

    obrigacao = ObrigacaoComComprador.objects.get(pedido=x)
    assert f"/administracao/financeiro/devolucoes/{obrigacao.pk}/" in resposta.content.decode()
    assert "Ver devolução" in texto


def test_ocorrencia_acima_do_saldo(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    a, x, _y, _c = _ae(client, relogio, sim)
    item = item_de(x, a.p1)
    ocorrer(a.admin, item, D("2"), "faltante")
    campos = {
        "item": item.pk,
        "tipo": "nao_entregue",
        "quantidade": "5",
        "acionamento": str(uuid.uuid4()),
    }
    antes = _estado_dos_registros()
    resposta = client.post(_rota(a, "ocorrencias/registrar"), campos)
    assert resposta.status_code == 409
    assert "A quantidade passa do saldo deste item (4 unidade)." in _texto(resposta)
    assert _estado_dos_registros() == antes


def test_ocorrencia_depois_do_repasse(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-14
    from apps.pedidos.repasse import registrar_repasse

    a, x, _y, _c = _ae(client, relogio, sim, liberacao_horas=0)
    registrar_repasse(
        a.admin, a.rodada, valor=D("170.00"), identificacao="pix-001", justificativa="Repasse"
    )
    campos = {
        "item": item_de(x, a.p1).pk,
        "tipo": "faltante",
        "quantidade": "2",
        "acionamento": str(uuid.uuid4()),
    }
    resposta = client.post(_rota(a, "ocorrencias/registrar"), campos, follow=True)
    assert (
        "Parte do reembolso ainda não tem cobertura: R$ 20,00. "
        "Cubra antes de autorizar a devolução." in _texto(resposta)
    )


def test_item_de_outra_rodada_da_404(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-15
    a, _x, _y, _c = _ae(client, relogio, sim)
    b, x2, _y2, _pf = arranjo_ae(relogio, sim)
    entrar_de_novo(client, _c, a.admin)
    campos = {
        "item": item_de(x2, b.p1).pk,
        "tipo": "faltante",
        "quantidade": "1",
        "acionamento": str(uuid.uuid4()),
    }
    antes = _estado_dos_registros()
    assert client.post(_rota(a, "ocorrencias/registrar"), campos).status_code == 404
    assert _estado_dos_registros() == antes


def test_ocorrencias_da_rodada_cancelada(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, x, _y, _c = _ae(client, relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    resposta = client.get(_rota(a, "ocorrencias"))
    assert resposta.status_code == 200
    assert 'name="tipo"' not in resposta.content.decode()
    campos = {
        "item": item_de(x, a.p1).pk,
        "tipo": "faltante",
        "quantidade": "1",
        "acionamento": str(uuid.uuid4()),
    }
    recusada = client.post(_rota(a, "ocorrencias/registrar"), campos)
    assert recusada.status_code == 409
    assert (
        "Ocorrências só são registradas depois da aprovação do resultado e antes do cancelamento."
        in _texto(recusada)
    )


# --- retiradas e descartes ------------------------------------------------------------------


def test_a_retirada_pela_tela(client: Client, relogio: RelogioControlado, sim: Any) -> None:  # A-17
    a, x, _y, cred = _ae(client, relogio, sim, estado="liberada")
    relogio.congelar(L + timedelta(days=1))
    entrar_de_novo(client, cred, a.admin)
    url = _rota(a, "retiradas")
    texto = _texto(client.get(url))
    assert "Retirada liberada em 05/11/2026 10:00. Prazo até 12/11/2026 10:00." in texto
    assert "Rua das Hortas, 100" in texto
    assert "O descarte fica disponível a partir de 12/11/2026 10:00." in texto
    campos = {
        "item": item_de(x, a.p1).pk,
        "quantidade": "4",
        "acionamento": _acionamento(client, url, "retiradas/registrar/"),
    }
    resposta = client.post(_rota(a, "retiradas/registrar"), campos, follow=True)
    assert "Retirada registrada: 4 unidade de P1." in _texto(resposta)
    from apps.pedidos.ocorrencias import saldo_do_item

    assert saldo_do_item(item_de(x, a.p1)) == D("2")


def test_cenario_23_pelas_telas(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-18
    a, x, _y, cred = _ae(client, relogio, sim, estado="liberada")
    retirar(a.admin, item_de(x, a.p1), D("4"))
    relogio.congelar(L + timedelta(days=8))
    entrar_de_novo(client, cred, a.admin)
    url = _rota(a, "retiradas")
    texto = _texto(client.get(url))
    assert "Prazo encerrado — pendentes de decisão" in texto
    campos = {
        "item": item_de(x, a.p1).pk,
        "quantidade": "2",
        "acionamento": _acionamento(client, url, "descartes/registrar/"),
    }
    resposta = client.post(_rota(a, "descartes/registrar"), campos, follow=True)
    texto = _texto(resposta)
    assert "Descarte registrado: 2 unidade de P1." in texto
    assert "Retirada" in texto
    assert "Descarte" in texto


def test_descarte_antes_do_prazo_pela_tela(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-19
    a, x, _y, cred = _ae(client, relogio, sim, estado="liberada")
    relogio.congelar(L + timedelta(days=1))
    entrar_de_novo(client, cred, a.admin)
    campos = {"item": item_de(x, a.p1).pk, "quantidade": "6", "acionamento": str(uuid.uuid4())}
    resposta = client.post(_rota(a, "descartes/registrar"), campos)
    assert resposta.status_code == 409
    assert "a partir de 12/11/2026 10:00 (horário de Brasília)" in _texto(resposta)
    assert _estado_dos_registros()[3] == 0


def test_a_pagina_de_retiradas_so_da_rodada_liberada(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-20
    a, _x, _y, _c = _ae(client, relogio, sim)
    assert client.get(_rota(a, "retiradas")).status_code == 404


def test_o_bloco_da_pagina_da_rodada(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-21
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, _x, _y, cred = _ae(client, relogio, sim)
    pagina = f"/administracao/rodadas/{a.rodada.pk}/estoque/"
    texto = _texto(client.get(pagina))
    assert "Aguardando o fornecedor: 2 produto(s) a resolver." in texto
    html = client.get(pagina).content.decode()
    assert _rota(a, "recebimento") in html
    assert _rota(a, "ocorrencias") in html
    assert _rota(a, "retiradas") not in html
    receber_tudo(a, a.rodada.pedidos_formais.get())
    liberar(relogio, a)
    entrar_de_novo(client, cred, a.admin)
    html = client.get(pagina).content.decode()
    assert "Retirada liberada; prazo até 12/11/2026 10:00." in _texto(client.get(pagina))
    assert _rota(a, "retiradas") in html
    b, _x2, _y2, _pf = arranjo_ae(relogio, sim)
    cancelar_rodada(b.admin, b.rodada, com_reembolso=False)
    entrar_de_novo(client, cred, b.admin)
    texto = _texto(client.get(f"/administracao/rodadas/{b.rodada.pk}/estoque/"))
    assert "Rodada cancelada." in texto


ROTAS_GET = ("recebimento", "ocorrencias", "retiradas")
ROTAS_POST = (
    "recebimento/registrar",
    "retirada/liberar",
    "ocorrencias/registrar",
    "retiradas/registrar",
    "descartes/registrar",
)


@pytest.mark.parametrize("estado", ["ae", "liberada"])
def test_so_o_administrador_acessa(
    client: Client, relogio: RelogioControlado, sim: Any, estado: str
) -> None:  # A-22
    a, x, _y, _c = _ae(client, relogio, sim, estado=estado)
    conta_f = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    campos = {
        "item": item_de(x, a.p1).pk,
        "produto": a.p1.pk,
        "tipo": "faltante",
        "quantidade": "1",
        "acionamento": str(uuid.uuid4()),
    }
    antes = _estado_dos_registros()
    for conta in (a.a, conta_f):
        cliente = Client()
        cliente.force_login(conta)
        for rota in ROTAS_GET:
            assert cliente.get(_rota(a, rota)).status_code == 403
        for rota in ROTAS_POST:
            assert cliente.post(_rota(a, rota), campos).status_code == 403
    anonimo = Client()
    for rota in ROTAS_GET:
        assert anonimo.get(_rota(a, rota)).status_code == 302
    for rota in ROTAS_POST:
        assert anonimo.post(_rota(a, rota), campos).status_code == 302
    assert _estado_dos_registros() == antes


def test_get_nas_rotas_de_escrita_da_405(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-23
    a, _x, _y, _c = _ae(client, relogio, sim, estado="liberada")
    for rota in ROTAS_POST:
        assert client.get(_rota(a, rota)).status_code == 405


def test_campos_extras_sao_ignorados(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-25
    a, _x, _y, _c = _ae(client, relogio, sim)
    campos = {
        "produto": a.p1.pk,
        "quantidade": "3",
        "acionamento": str(uuid.uuid4()),
        "linha": 1,
        "pedido_formal": 2,
    }
    assert client.post(_rota(a, "recebimento/registrar"), campos).status_code == 302
    assert _estado_dos_registros()[0] == 1
