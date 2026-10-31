"""E11-07: telas da apuração para o administrador (acceptance A-1 a A-12 e A-17)."""

import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.financeiro.models import ObrigacaoComComprador
from apps.pedidos.models import ApuracaoFinal
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H
SUCESSO_VIAVEL = "Apuração feita. Confira o resultado e aprove o avanço."
SUCESSO_RETORNO = (
    "Apuração feita. A rodada voltou para interesse; autorize as devoluções na lista de devoluções."
)
SUCESSO_APROVACAO = "Resultado aprovado. A rodada aguarda o fornecedor."


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _tela(
    client: Client, relogio: RelogioControlado, **arranjo: Any
) -> tuple[Any, Any, Any, bytes]:
    relogio.congelar(T0)
    conta, credencial = administrador_com_passkey(client)
    a, x, y = arranjo_ap(relogio, **arranjo)
    assert a.admin.pk == conta.pk
    return a, x, y, credencial


def _texto(resposta: Any) -> str:
    html = resposta.content.decode()
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _pagina(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/estoque/"


def _iniciar(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/apuracao/iniciar/"


def _aprovar(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/apuracao/aprovar/"


def _no_prazo(client: Client, relogio: RelogioControlado, a: Any, credencial: bytes) -> None:
    relogio.congelar(PRAZO)
    entrar_de_novo(client, credencial, a.admin)


def test_antes_de_48_horas_a_pagina_so_informa_o_horario(
    client: Client, relogio: RelogioControlado
) -> None:  # A-1
    a, _x, _y, credencial = _tela(client, relogio)
    relogio.congelar(T0 + 47 * H)
    entrar_de_novo(client, credencial, a.admin)
    texto = _texto(client.get(_pagina(a)))
    assert "Apuração final" in texto
    assert "A apuração pode começar a partir de 04/11/2026 às 10:00 (horário de Brasília)" in texto
    assert "Iniciar apuração" not in texto


def test_a_partir_de_48_horas_a_pagina_oferece_o_botao(
    client: Client, relogio: RelogioControlado
) -> None:  # A-2
    a, _x, _y, credencial = _tela(client, relogio)
    _no_prazo(client, relogio, a, credencial)
    texto = _texto(client.get(_pagina(a)))
    assert "Iniciar apuração" in texto
    assert "Ela não pode ser desfeita" in texto


def _apurar(client: Client, a: Any, **opcoes: Any) -> Any:
    return client.post(_iniciar(a), follow=True, **opcoes)


def test_apuracao_viavel_mostra_o_resultado_e_o_botao_de_aprovar(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    a, x, _y, credencial = _tela(client, relogio)
    pagar(relogio, sim, x)
    _no_prazo(client, relogio, a, credencial)
    resposta = _apurar(client, a)
    assert resposta.redirect_chain[-1][0] == _pagina(a)
    texto = _texto(resposta)
    assert SUCESSO_VIAVEL in texto
    assert "Comprador A" in texto
    assert "Cancelado (falta de pagamento)" in texto
    assert "P2 · caixa 1" in texto
    assert "P2 · caixa 2" in texto
    assert "Valor válido R$ 60,00" in texto
    assert "Mínimo do ciclo R$ 50,00" in texto
    assert "Mínimo atendido" in texto
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x)
    assert "caixa invalidada" in texto
    assert "R$ 23,59" in texto
    assert "Pendente de autorização" in texto
    assert f'href="/administracao/financeiro/devolucoes/{obrigacao.pk}/"' in (
        resposta.content.decode()
    )
    assert "Aprovar resultado e avançar" in texto
    assert "déficit do administrador" in texto


def test_aprovar_mostra_o_frete_e_esconde_o_botao(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    a, x, _y, credencial = _tela(client, relogio)
    pagar(relogio, sim, x)
    _no_prazo(client, relogio, a, credencial)
    _apurar(client, a)
    relogio.congelar(T0 + 49 * H)
    entrar_de_novo(client, credencial, a.admin)
    resposta = client.post(_aprovar(a), follow=True)
    texto = _texto(resposta)
    assert SUCESSO_APROVACAO in texto
    assert "Frete efetivo R$ 22,00" in texto
    assert "arrecadado R$ 7,76" in texto
    assert "déficit R$ 14,24" in texto
    assert "Resultado aprovado em" in texto
    assert "por Adm" in texto
    assert "Aprovar resultado e avançar" not in texto


def test_minimo_nao_atendido_devolve_a_rodada_e_mostra_o_estorno_integral(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, x, _y, credencial = _tela(client, relogio, minimo="100.00")
    pagar(relogio, sim, x)
    _no_prazo(client, relogio, a, credencial)
    resposta = _apurar(client, a)
    texto = _texto(resposta)
    assert SUCESSO_RETORNO in texto
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "interesse"
    assert "Mínimo não atendido: a rodada voltou para interesse" in texto
    assert "mínimo não atingido" in texto
    assert "R$ 94,35" in texto
    assert "Aprovar resultado e avançar" not in texto


def test_apurar_antes_de_48_horas_e_recusado_com_409(
    client: Client, relogio: RelogioControlado
) -> None:  # A-6
    a, _x, _y, credencial = _tela(client, relogio)
    relogio.congelar(T0 + 47 * H)
    entrar_de_novo(client, credencial, a.admin)
    resposta = client.post(_iniciar(a))
    assert resposta.status_code == 409
    assert (
        "A apuração só pode começar a partir de 04/11/2026 às 10:00 (horário de Brasília)."
        in _texto(resposta)
    )
    assert ApuracaoFinal.objects.count() == 0


def test_apurar_de_novo_e_recusado_com_409(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    a, x, _y, credencial = _tela(client, relogio)
    pagar(relogio, sim, x)
    _no_prazo(client, relogio, a, credencial)
    _apurar(client, a)
    resposta = client.post(_iniciar(a))
    assert resposta.status_code == 409
    assert "A apuração deste ciclo já foi feita." in _texto(resposta)


def test_provedor_fora_do_ar_responde_503_sem_apurar(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    a, _x, _y, credencial = _tela(client, relogio)
    _no_prazo(client, relogio, a, credencial)
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    resposta = client.post(_iniciar(a))
    assert resposta.status_code == 503
    assert "Não foi possível consultar o provedor; nada foi apurado. Tente de novo." in _texto(
        resposta
    )
    assert ApuracaoFinal.objects.count() == 0


def test_sem_nova_autenticacao_recente_redireciona_sem_chamar_o_servico(
    client: Client, relogio: RelogioControlado
) -> None:  # A-9
    a, _x, _y, _credencial = _tela(client, relogio)
    from tests.apoio.admin_fluxos import entrar_com_passkey_direta

    entrar_com_passkey_direta(client, _credencial, a.admin)
    relogio.congelar(PRAZO + timedelta(hours=2))
    for rota in (_iniciar(a), _aprovar(a)):
        resposta = client.post(rota)
        assert resposta.status_code == 302
        assert "reauthenticate" in resposta["Location"]
    assert ApuracaoFinal.objects.count() == 0


def test_comprador_e_fornecedor_nao_acessam(client: Client, relogio: RelogioControlado) -> None:
    # A-10
    a, _x, _y, _ = _tela(client, relogio)
    relogio.congelar(PRAZO)
    for conta in (a.a, ContaFactory.create(fornecedor=True)):
        cliente = Client()
        cliente.force_login(conta)
        assert cliente.post(_iniciar(a)).status_code in (302, 403)
        assert cliente.post(_aprovar(a)).status_code in (302, 403)
        assert cliente.get(_pagina(a)).status_code in (302, 403)
    assert ApuracaoFinal.objects.count() == 0


def test_get_nas_rotas_de_acao_responde_405(client: Client, relogio: RelogioControlado) -> None:
    # A-11
    a, _x, _y, credencial = _tela(client, relogio)
    _no_prazo(client, relogio, a, credencial)
    assert client.get(_iniciar(a)).status_code == 405
    assert client.get(_aprovar(a)).status_code == 405


def test_painel_dos_pedidos_mostra_a_falta_de_pagamento(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    a, x, _y, credencial = _tela(client, relogio)
    pagar(relogio, sim, x)
    _no_prazo(client, relogio, a, credencial)
    client.post(_iniciar(a))
    html = client.get(_pagina(a)).content.decode()
    pedidos = re.search(r"<h3>Pedidos</h3>(.*?)<h3>", html, re.DOTALL)
    assert pedidos is not None
    assert "Cancelado (falta de pagamento)" in " ".join(
        re.sub(r"<[^>]+>", " ", pedidos.group(1)).split()
    )


def test_novo_pagamento_esconde_a_apuracao_do_ciclo_antigo(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-17
    from apps.interesses.servicos import adicionar_interesse
    from apps.pedidos.abertura import abrir_pagamento
    from apps.rodadas.fechamento import encerrar_fechamento, iniciar_fechamento

    a, x, _y, credencial = _tela(client, relogio, minimo="100.00")
    pagar(relogio, sim, x)
    _no_prazo(client, relogio, a, credencial)
    client.post(_iniciar(a))
    assert "Mínimo não atendido" in _texto(client.get(_pagina(a)))
    adicionar_interesse(ContaFactory.create(nome="Comprador C"), a.p1, D("5"))
    iniciar_fechamento(a.admin, a.rodada)
    relogio.congelar(PRAZO + 25 * H)
    encerrar_fechamento(a.rodada)
    a.rodada.refresh_from_db()
    abrir_pagamento(a.admin, a.rodada, D("10.00"))
    entrar_de_novo(client, credencial, a.admin)
    texto = _texto(client.get(_pagina(a)))
    assert "Mínimo não atendido" not in texto
    assert "Pagamento aberto em" in texto
