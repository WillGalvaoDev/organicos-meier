"""E16-06: a página `regras/` completa para o comprador (acceptance A-1 a A-8)."""

import re
from decimal import Decimal
from typing import Any

import pytest
from django.conf import settings
from django.test import Client

from tests.apoio.pedidos import T0, montar_arranjo
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

ENDERECO = "Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ"
TITULOS = [
    "Participação",
    "Interesse e reservas",
    "Fechamento",
    "Pagamento",
    "Apuração e falta de pagamento",
    "Devoluções",
    "Cancelamento da rodada",
    "Retirada",
]

# Os parágrafos da regra 2, na ordem, com {fechamento}, {taxa}, {prazo} e {margem} no lugar dos
# valores que vêm das constantes do servidor.
PARAGRAFOS: dict[str, list[str]] = {
    "Participação": [
        "O acesso é feito por convite, de uso único e válido por 24 horas. Cada e-mail "
        "corresponde a uma única conta.",
        "Contas de comprador e de fornecedor são separadas. Uma conta de fornecedor não faz "
        "compras.",
    ],
    "Interesse e reservas": [
        "Os itens do carrinho representam interesse, não compra paga. Ao adicionar uma "
        "quantidade, ela reserva o estoque disponível da rodada; uma quantidade acima do "
        "estoque é recusada.",
        "Cada acréscimo entra na fila na ordem em que foi feito. Ao reduzir, as quantidades "
        "mais recentes saem primeiro.",
        "Cada fornecedor tem um mínimo de compra calculado só sobre os produtos, sem frete nem "
        "taxa. Em produtos vendidos por caixa, só contam as caixas completas.",
        "Quando uma caixa é invalidada por falta de pagamento de outro comprador e a rodada "
        "continua, as suas unidades pagas nela são reembolsadas e voltam para uma fila de "
        "pendentes do mesmo fornecedor, com a prioridade original. Quantidade pendente não é "
        "reserva: ela é atendida em uma próxima rodada, se houver estoque. Você pode remover "
        "quantidades pendentes a qualquer momento.",
    ],
    "Fechamento": [
        "Quando o mínimo é atingido, o administrador pode iniciar o fechamento, que dura "
        "{fechamento} horas. Durante o fechamento ainda é possível alterar o carrinho.",
        "Ao fim do fechamento, as unidades que não completam uma caixa são removidas, pela "
        "ordem de adição, e você é avisado. Se o mínimo deixar de ser atingido, a rodada volta "
        "para a fase de interesse.",
    ],
    "Pagamento": [
        "Quando o administrador abre o pagamento, o seu pedido é congelado: produtos e "
        "quantidades não mudam mais, nem por você nem pelo administrador.",
        "O valor a pagar é a soma dos produtos, da taxa de serviço de {taxa}% sobre os "
        "produtos e da sua parte do frete, proporcional ao valor dos seus produtos.",
        "Você tem {prazo} horas para pagar, a partir da abertura, sem prorrogação. O pagamento "
        "é feito somente pela plataforma de pagamentos integrada; nunca por Pix direto, "
        "transferência ou outro meio.",
        "Um pagamento iniciado no prazo e aprovado até {margem} horas depois do fim dele é "
        "aceito. Aprovado depois disso, ele é devolvido.",
    ],
    "Apuração e falta de pagamento": [
        "A apuração dos pagamentos é feita pelo administrador depois do fim desse período, e "
        "nunca antes.",
        "Quem não pagou perde os itens daquele fornecedor no carrinho, inclusive as reservas. "
        "Se os produtos pagos não alcançarem o mínimo, a rodada volta para a fase de interesse "
        "e todos os valores recebidos são devolvidos.",
    ],
    "Devoluções": [
        "Há devolução quando o mínimo não é alcançado, quando uma caixa é invalidada, em "
        "ocorrências de entrega, no cancelamento da rodada com reembolso, em pagamento "
        "aprovado fora do prazo e em pagamento em duplicidade.",
        "As devoluções são feitas pela plataforma de pagamentos. Quando isso não for possível, "
        "o administrador devolve diretamente e registra a devolução.",
        "Depois de pagar, não há cancelamento voluntário do pedido.",
    ],
    "Cancelamento da rodada": [
        "Só o administrador pode cancelar uma rodada, sempre por inteiro. Ao cancelar, ele "
        "indica se há reembolso; com reembolso, todos os que pagaram recebem de volta o valor "
        "pago.",
    ],
}
VALORES_PADRAO = {"fechamento": 24, "taxa": 5, "prazo": 24, "margem": 24}


def _texto(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _secoes(html: str) -> dict[str, str]:
    achados = re.split(r"<h2[^>]*>(.*?)</h2>", html, flags=re.DOTALL)
    return {
        " ".join(achados[i].split()): _texto(achados[i + 1]) for i in range(1, len(achados) - 1, 2)
    }


@pytest.fixture
def mundo(relogio: RelogioControlado) -> Any:
    from apps.pedidos.endereco_de_retirada import definir_endereco_de_retirada
    from apps.rodadas.models import Rodada

    relogio.congelar(T0)
    a = montar_arranjo(minimo="50.00")
    Rodada.objects.filter(pk=a.rodada.pk).update(etapa="pagamento")
    definir_endereco_de_retirada(a.admin, ENDERECO)
    return a


def _regras(conta: Any) -> Any:
    cliente = Client()
    cliente.force_login(conta)
    return cliente.get("/regras/")


def test_titulo_e_secoes(mundo: Any) -> None:  # A-1
    resposta = _regras(mundo.a)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert re.search(r"<h1[^>]*>\s*Regras de funcionamento\s*</h1>", html)
    assert "<title>Regras de funcionamento · Orgânicos Méier</title>" in html
    assert [t for t in _secoes(html) if t in TITULOS] == TITULOS


def test_cada_paragrafo_com_o_texto_exato(mundo: Any) -> None:  # A-2
    secoes = _secoes(_regras(mundo.a).content.decode())
    for titulo, paragrafos in PARAGRAFOS.items():
        for paragrafo in paragrafos:
            esperado = paragrafo.format(**VALORES_PADRAO)
            assert esperado in secoes[titulo], (titulo, esperado)


def test_a_secao_de_retirada_nao_mudou(mundo: Any) -> None:  # A-3
    retirada = _secoes(_regras(mundo.a).content.decode())["Retirada"]
    assert f"Endereço: {ENDERECO}" in retirada
    assert "o prazo para retirar é de sete dias" in retirada
    assert "Não há substituição de produtos." in retirada


def test_a_pagina_acompanha_as_constantes(mundo: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # A-4
    from apps.pedidos import calculo, prazos
    from apps.rodadas import fechamento

    monkeypatch.setattr(calculo, "TAXA_DE_SERVICO", Decimal("0.07"))
    monkeypatch.setattr(prazos, "HORAS_DO_PRAZO_DE_PAGAMENTO", 36)
    monkeypatch.setattr(prazos, "HORAS_DA_MARGEM", 60)
    monkeypatch.setattr(fechamento, "HORAS_DO_FECHAMENTO", 36)
    secoes = _secoes(_regras(mundo.a).content.decode())
    assert "taxa de serviço de 7%" in secoes["Pagamento"]
    assert "Você tem 36 horas para pagar" in secoes["Pagamento"]
    assert "aprovado até 24 horas depois do fim dele" in secoes["Pagamento"]  # 60 - 36
    assert "que dura 36 horas" in secoes["Fechamento"]


def test_o_prazo_de_retirada_acompanha_a_constante(
    mundo: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-5
    from datetime import timedelta

    from apps.pedidos import liberacao_da_retirada

    monkeypatch.setattr(liberacao_da_retirada, "PRAZO_DE_RETIRADA", timedelta(days=10))
    retirada = _secoes(_regras(mundo.a).content.decode())["Retirada"]
    assert "o prazo para retirar é de 10 dias" in retirada
    assert "sete dias" not in retirada


def test_sem_dados_de_rodada_pedido_ou_pessoa(mundo: Any) -> None:  # A-6
    html = _regras(mundo.a).content.decode()
    texto = _texto(html)
    for nome in ("Comprador A", "Comprador B", mundo.fornecedor.nome, "P1", "P2"):
        if len(nome) > 2:
            assert nome not in texto, nome
    assert "P1" not in texto
    assert "P2" not in texto


def test_o_acesso_continua_o_da_e14_03(mundo: Any) -> None:  # A-7
    fornecedor = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=mundo.fornecedor.pk
    )
    assert _regras(fornecedor).status_code == 403
    anonimo = Client().get("/regras/")
    assert anonimo.status_code == 302
    assert anonimo["Location"].startswith(settings.LOGIN_URL)


def test_o_link_na_pagina_inicial(mundo: Any) -> None:  # A-8
    cliente = Client()
    cliente.force_login(mundo.a)
    html = cliente.get("/inicio/").content.decode()
    assert re.search(r'<a href="/regras/">Regras de funcionamento</a>', html)
