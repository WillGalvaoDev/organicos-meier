"""E13-06: a tela das saídas da rodada (acceptance A-18 a A-22)."""

import re
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client

from apps.financeiro.livro import conta, saldo
from apps.financeiro.models import Destinacao, MovimentoFinanceiro
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.pedido_formal import arranjo_af
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

H = timedelta(hours=1)
MENSAGEM_DO_VALOR = (
    "Informe um valor em reais maior que zero, com até duas casas decimais (por exemplo, 1000,00)."
)


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
    return f"/administracao/rodadas/{a.rodada.pk}/saidas/"


def _rota(a: Any, saida: str) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/saidas/{saida}/"


def _af_logado(client: Client, relogio: RelogioControlado, sim: Any) -> tuple[Any, bytes]:
    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    a, _x, _y, _pedido = arranjo_af(relogio, sim, liberacao_horas=72, pago_y_em=T0 + 20 * H)
    relogio.congelar(T0 + 80 * H)
    entrar_de_novo(client, credencial, a.admin)
    return a, credencial


def _campos(
    valor: str, identificacao: str = "pix-001", justificativa: str = "Pix"
) -> dict[str, str]:
    return {"valor": valor, "identificacao": identificacao, "justificativa": justificativa}


def _obrigacao(a: Any) -> Any:
    return conta(Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk)


def test_a_pagina_mostra_a_obrigacao_e_o_frete(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-18
    a, _credencial = _af_logado(client, relogio, sim)
    resposta = client.get(_pagina(a))
    assert resposta.status_code == 200
    texto = _texto(resposta)
    assert "Repasse ao fornecedor" in texto
    assert "Saldo: R$ 170,00" in texto
    assert "Liberado no provedor: R$ 80,00" in texto
    assert "A liberar: R$ 90,00" in texto
    assert "Frete efetivo: R$ 22,00" in texto
    assert "Arrecadado: R$ 22,00" in texto
    assert "Déficit: R$ 0,00" in texto
    assert "Saldo do frete: R$ 22,00" in texto
    assert "Liberado do frete: R$ 10,35" in texto
    assert "Registrar repasse" in texto
    assert "Registrar pagamento do frete" in texto


def test_o_repasse_pela_tela(client: Client, relogio: RelogioControlado, sim: Any) -> None:  # A-19
    a, _credencial = _af_logado(client, relogio, sim)
    resposta = client.post(_rota(a, "repasse"), _campos("80,00"), follow=True)
    assert resposta.redirect_chain[-1][0] == _pagina(a)
    texto = _texto(resposta)
    assert "Repasse de R$ 80,00 registrado." in texto
    assert "pix-001" in texto
    assert a.admin.nome in texto
    assert saldo(_obrigacao(a)) == 90


@pytest.mark.parametrize(
    ("campos", "status", "mensagem"),
    [
        (_campos("80,01"), 409, "Só R$ 80,00 estão liberados no provedor (R$ 90,00 a liberar)."),
        (_campos("10,00", justificativa=""), 400, "Informe a justificativa."),
        (_campos("10,00", identificacao=""), 400, "Informe a identificação da saída no provedor."),
        (_campos("abc"), 400, MENSAGEM_DO_VALOR),
    ],
)
def test_recusas_do_repasse(
    client: Client,
    relogio: RelogioControlado,
    sim: Any,
    campos: dict[str, str],
    status: int,
    mensagem: str,
) -> None:  # A-20
    a, _credencial = _af_logado(client, relogio, sim)
    antes = MovimentoFinanceiro.objects.count()
    resposta = client.post(_rota(a, "repasse"), campos)
    assert resposta.status_code == status
    assert mensagem in _texto(resposta)
    assert MovimentoFinanceiro.objects.count() == antes


def test_identificacao_repetida_e_provedor_indisponivel(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-20
    a, _credencial = _af_logado(client, relogio, sim)
    client.post(_rota(a, "repasse"), _campos("10,00"))
    repetida = client.post(_rota(a, "repasse"), _campos("5,00"))
    assert repetida.status_code == 409
    assert "Esta identificação de saída já foi registrada." in _texto(repetida)
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    fora = client.post(_rota(a, "repasse"), _campos("5,00", identificacao="pix-002"))
    assert fora.status_code == 503
    assert (
        "Não foi possível consultar o provedor; o repasse não foi registrado. Tente de novo."
        in _texto(fora)
    )


def test_acesso_metodo_e_nova_autenticacao(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-21
    a, _credencial = _af_logado(client, relogio, sim)
    antes = MovimentoFinanceiro.objects.count()
    assert client.get(_rota(a, "repasse")).status_code == 405
    assert client.get(_rota(a, "frete")).status_code == 405
    relogio.congelar(T0 + 80 * H + timedelta(days=1))  # a passkey deixa de ser recente
    resposta = client.post(_rota(a, "frete"), _campos("5,00", "frete-001", "Frete"))
    assert resposta.status_code == 302
    assert "reauthenticate" in resposta["Location"]
    fornecedor = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    for conta_ in (a.a, fornecedor):
        client.force_login(conta_)
        assert client.post(_rota(a, "repasse"), _campos("5,00")).status_code == 403
        assert client.post(_rota(a, "frete"), _campos("5,00")).status_code == 403
    assert MovimentoFinanceiro.objects.count() == antes


def test_os_links_para_as_saidas(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-22
    a, _credencial = _af_logado(client, relogio, sim)
    for pagina in (
        f"/administracao/rodadas/{a.rodada.pk}/pedido-formal/",
        f"/administracao/rodadas/{a.rodada.pk}/estoque/",
    ):
        resposta = client.get(pagina)
        assert "Saídas da rodada" in _texto(resposta)
        assert f'href="{_pagina(a)}"' in resposta.content.decode()


def test_sem_apuracao_no_livro_a_pagina_da_404(client: Client, relogio: RelogioControlado) -> None:
    from tests.apoio.apuracao import arranjo_ap

    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    a, _x, _y = arranjo_ap(relogio)
    entrar_de_novo(client, credencial, a.admin)
    assert client.get(_pagina(a)).status_code == 404
