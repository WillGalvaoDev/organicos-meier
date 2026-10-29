"""E09-08: telas financeiras do administrador (acceptance A-1 a A-13 e A-15; o A-14 é a varredura
de políticas, também exercitada aqui rota a rota)."""

import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.urls import resolve, reverse

from apps.contas.permissoes import Politica, politica_da_view, rotas_sem_politica
from apps.financeiro.alertas import abrir_alerta
from apps.financeiro.apuracao import registrar_apuracao_no_livro
from apps.financeiro.livro import EXTERIOR, saldo
from apps.financeiro.models import (
    AlertaFinanceiro,
    DesignacaoDaReserva,
    Despesa,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeMovimento,
)
from apps.financeiro.reserva import avaliar_reserva, designar_reserva, situacao_da_reserva
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import SISTEMA
from tests.apoio.admin_fluxos import administrador_com_passkey, entrar_com_passkey_direta
from tests.apoio.financeiro import (
    Apuracao,
    despesas,
    frete_de,
    montar_ap,
    mover,
    obrigacao_de_teste,
    pagar_pedido,
    receita_de,
    reserva,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
BASE = "/administracao/financeiro/"
T = TipoDeMovimento
NOMES_DAS_ROTAS = [
    "financeiro_resumo",
    "financeiro_movimentos",
    "financeiro_reserva",
    "financeiro_aporte",
    "financeiro_designar",
    "financeiro_desfazer_designacao",
    "financeiro_cobrir_obrigacao",
    "financeiro_cobrir_despesa",
    "financeiro_retirada",
    "financeiro_conciliacoes",
]
DE_LEITURA = ["financeiro_resumo", "financeiro_movimentos", "financeiro_reserva"]


@dataclass
class Tela:
    ap: Apuracao
    cliente: Client
    relogio: RelogioControlado
    sim: Any
    o1: ObrigacaoComComprador
    deficit: Despesa
    conta: Any
    credencial: bytes

    def entrar(self) -> None:
        """Um login novo por passkey no instante corrente: a passkey fica recente."""
        self.cliente.post("/sair/")
        entrar_com_passkey_direta(self.cliente, self.credencial, self.conta)


@pytest.fixture
def tela(
    client: Client, webauthn: Any, relogio: RelogioControlado, simulador_pagamentos: Any
) -> Tela:
    """O estado do A-1 da E09-06 (rodada apurada, tarifa coberta, déficit de 10,00 pendente), a
    reserva com 1000,00 e a obrigação O1 de 25,00 sem cobertura; o administrador entra por
    passkey no fim."""
    relogio.congelar(T0)
    conta, credencial = administrador_com_passkey(client)
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    simulador_pagamentos.definir_liberacao("pix", horas=24)
    ap = montar_ap()
    pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, H)
    mover(T.APORTE, EXTERIOR, reserva(), "1000.00", autor=ap.admin, justificativa="Aporte inicial")
    from django.db import transaction

    with transaction.atomic():
        registrar_apuracao_no_livro(ap.ciclo, [ap.x], autor=SISTEMA)
    o1 = obrigacao_de_teste("25.00")
    deficit = Despesa.objects.get(tipo="deficit_frete", ciclo=ap.ciclo)
    t = Tela(ap, client, relogio, simulador_pagamentos, o1, deficit, conta, credencial)
    t.entrar()
    return t


def _linha(html: str, texto: str) -> str:
    for linha in re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL):
        if texto in linha:
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(linha))).strip()
    raise AssertionError(f"sem linha com {texto!r}")


def _pagina(tela: Tela, nome: str, **kwargs: Any) -> str:
    resposta = tela.cliente.get(reverse(nome, kwargs=kwargs or None))
    assert resposta.status_code == 200, (nome, resposta.status_code)
    return str(resposta.content.decode())


def _estado() -> tuple[int, int, int]:
    return (
        MovimentoFinanceiro.objects.count(),
        DesignacaoDaReserva.objects.count(),
        AlertaFinanceiro.objects.count(),
    )


def test_o_resumo_mostra_cada_destinacao_e_as_pendencias(tela: Tela) -> None:  # A-1
    html = _pagina(tela, "financeiro_resumo")
    fornecedor = _linha(html, "Fornecedor A")
    assert "R$ 100,00" in fornecedor
    assert "R$ 0,00" in fornecedor  # o liberado: o pagamento só é liberado 24h depois
    frete = _linha(html, "30,00")
    for valor in ("R$ 30,00", "R$ 20,00", "R$ 10,00"):
        assert valor in frete
    assert "Saldo R$ 1.000,00" in html
    assert "Comprometido R$ 0,00" in html
    assert "Livre R$ 1.000,00" in html
    pendencias = html.split("Pendências", 1)[1]
    assert "R$ 10,00" in pendencias  # o déficit de frete
    assert "R$ 25,00" in pendencias  # a obrigação O1
    for secao in ("Alertas abertos", "Por destinação", "Reserva", "Conciliação"):
        assert secao in html


def test_os_movimentos_mostram_o_registro_e_o_filtro_restringe(tela: Tela) -> None:  # A-2
    html = _pagina(tela, "financeiro_movimentos")
    apuracao = _linha(html, "Apuração")
    assert "Sistema" in apuracao
    assert "Apuração final aprovada" in apuracao
    assert "02/11/2026 11:00" in _linha(html, "Entrada de pagamento")  # 14:00 UTC, em Brasília
    resposta = tela.cliente.get(
        reverse("financeiro_movimentos"),
        {"destinacao": "receita_servico", "rodada": str(tela.ap.rodada.pk)},
    )
    filtrado = resposta.content.decode()
    assert "Apuração" in filtrado
    assert "Cobertura de despesa" in filtrado
    assert "Entrada de pagamento" not in filtrado
    assert "Aporte" not in filtrado


def test_aporte_com_passkey_recente_entra_na_reserva_e_no_historico(tela: Tela) -> None:  # A-3
    resposta = tela.cliente.post(
        reverse("financeiro_aporte"),
        {"valor": "1000,00", "identificacao": "sim-mov-1", "justificativa": "Aporte inicial"},
        follow=True,
    )
    assert resposta.status_code == 200
    assert "Aporte de R$ 1.000,00 registrado." in resposta.content.decode()
    assert situacao_da_reserva().saldo == D("2000.00")
    historico = _pagina(tela, "financeiro_reserva")
    linha = _linha(historico, "sim-mov-1")
    assert "R$ 1.000,00" in linha
    assert "Aporte inicial" in linha


def test_sem_passkey_recente_as_acoes_vao_para_a_nova_autenticacao(tela: Tela) -> None:  # A-4
    tela.relogio.avancar(timedelta(seconds=301))
    antes = _estado()
    acoes = [
        ("financeiro_aporte", {}, {"valor": "1,00", "identificacao": "x", "justificativa": "x"}),
        ("financeiro_designar", {"pk": tela.o1.pk}, {"valor": "1,00", "justificativa": "x"}),
        ("financeiro_cobrir_obrigacao", {"pk": tela.o1.pk}, {"valor": "1,00"}),
        ("financeiro_cobrir_despesa", {"pk": tela.deficit.pk}, {"valor": "1,00"}),
        ("financeiro_retirada", {}, {"valor": "1,00"}),
        ("financeiro_desfazer_designacao", {"pk": 1}, {"justificativa": "x"}),
    ]
    for nome, kwargs, dados in acoes:
        caminho = reverse(nome, kwargs=kwargs or None)
        resposta = tela.cliente.post(caminho, dados)
        assert resposta.status_code == 302, nome
        assert resposta["Location"].startswith(reverse("mfa_reauthenticate_webauthn")), nome
        assert "next=" in resposta["Location"], nome
    assert _estado() == antes


def _caminhos(tela: Tela) -> list[tuple[str, str]]:
    return [
        (nome, reverse(nome, kwargs={"pk": 1} if nome in _COM_ID else None))
        for nome in NOMES_DAS_ROTAS
    ]


_COM_ID = {
    "financeiro_designar",
    "financeiro_desfazer_designacao",
    "financeiro_cobrir_obrigacao",
    "financeiro_cobrir_despesa",
}


def test_comprador_fornecedor_e_anonimo_nao_veem_nada(tela: Tela) -> None:  # A-5
    antes = _estado()
    comprador = ContaFactory.create()
    fornecedor = ContaFactory.create(fornecedor=True)
    for conta in (comprador, fornecedor, None):
        cliente = Client()
        if conta is not None:
            cliente.force_login(conta)
        for nome, caminho in _caminhos(tela):
            for metodo in ("get", "post"):
                resposta = getattr(cliente, metodo)(caminho)
                if conta is None:
                    assert resposta.status_code == 302, (nome, metodo)
                else:
                    assert resposta.status_code in (403, 405), (nome, metodo)
                assert b"Fornecedor A" not in resposta.content, (nome, metodo)
    assert _estado() == antes


def _reserva_de_20(tela: Tela) -> None:
    mover(T.COBERTURA_DE_DESPESA, reserva(), despesas(), "980.00")
    assert situacao_da_reserva().livre == D("20.00")


def test_designar_acima_do_livre_responde_409_com_a_mensagem(tela: Tela) -> None:  # A-6, T-10
    _reserva_de_20(tela)
    antes = _estado()
    resposta = tela.cliente.post(
        reverse("financeiro_designar", kwargs={"pk": tela.o1.pk}),
        {"valor": "25,00", "justificativa": "devolução"},
    )
    assert resposta.status_code == 409
    assert "O valor passa do saldo livre da reserva (R$ 20,00)." in resposta.content.decode()
    assert DesignacaoDaReserva.objects.count() == 0
    assert _estado()[1] == antes[1]


def test_cobrir_o_deficit_com_a_reserva(tela: Tela) -> None:  # A-7, cenário 31
    resposta = tela.cliente.post(
        reverse("financeiro_cobrir_despesa", kwargs={"pk": tela.deficit.pk}),
        {"fonte": "reserva", "valor": "10,00", "justificativa": "Cobertura do déficit de frete"},
        follow=True,
    )
    assert resposta.status_code == 200
    assert "Cobertura de R$ 10,00 registrada." in resposta.content.decode()
    assert saldo(frete_de(tela.ap.rodada)) == D("30.00")
    assert saldo(reserva()) == D("990.00")


def test_cobrir_o_deficit_com_a_receita_de_uma_rodada(tela: Tela) -> None:
    resposta = tela.cliente.post(
        reverse("financeiro_cobrir_despesa", kwargs={"pk": tela.deficit.pk}),
        {
            "fonte": f"receita:{tela.ap.rodada.pk}",
            "valor": "3,75",
            "justificativa": "Receita da rodada",
        },
    )
    assert resposta.status_code == 302
    assert saldo(receita_de(tela.ap.rodada)) == D("0.00")
    assert saldo(frete_de(tela.ap.rodada)) == D("23.75")


def test_retirada_acima_do_liberado_responde_409_com_a_mensagem(tela: Tela) -> None:  # A-8
    antes = _estado()
    resposta = tela.cliente.post(
        reverse("financeiro_retirada"),
        {
            "rodada": tela.ap.rodada.pk,
            "valor": "1,00",
            "identificacao": "ret-1",
            "justificativa": "Retirada de receita",
        },
    )
    assert resposta.status_code == 409
    assert (
        "Só R$ 0,00 da receita desta rodada estão liberados no provedor."
        in resposta.content.decode()
    )
    assert _estado() == antes


def test_retirada_dentro_do_liberado_e_registrada(tela: Tela) -> None:
    tela.relogio.congelar(T0 + 26 * H)
    tela.entrar()
    resposta = tela.cliente.post(
        reverse("financeiro_retirada"),
        {
            "rodada": tela.ap.rodada.pk,
            "valor": "1,00",
            "identificacao": "ret-1",
            "justificativa": "Retirada de receita",
        },
        follow=True,
    )
    assert "Retirada de R$ 1,00 registrada." in resposta.content.decode()
    assert saldo(receita_de(tela.ap.rodada)) == D("2.75")
    formulario = _pagina(tela, "financeiro_retirada")
    assert "R$ 2,75" in formulario  # o liberado, ao lado da rodada


def test_o_aviso_de_reserva_insuficiente_aparece_nas_duas_telas(tela: Tela) -> None:  # A-9
    _reserva_de_20(tela)
    from django.db import transaction

    with transaction.atomic():
        avaliar_reserva()
    aviso = (
        "Reserva insuficiente: obrigações sem cobertura de R$ 35,00 para um saldo livre de "
        "R$ 20,00."
    )
    assert aviso in _pagina(tela, "financeiro_resumo")
    assert aviso in _pagina(tela, "financeiro_reserva")


@pytest.mark.parametrize("valor", ["1.000", "10,001", "-5", "abc", ""])
def test_aporte_com_valor_invalido_responde_400(tela: Tela, valor: str) -> None:  # A-10
    antes = _estado()
    resposta = tela.cliente.post(
        reverse("financeiro_aporte"),
        {"valor": valor, "identificacao": "sim-mov-2", "justificativa": "Aporte"},
    )
    assert resposta.status_code == 400
    assert "Informe um valor em reais maior que zero" in resposta.content.decode()
    assert _estado() == antes


def test_aporte_sem_identificacao_ou_sem_justificativa_responde_400(tela: Tela) -> None:  # A-10
    antes = _estado()
    for dados, mensagem in (
        ({"valor": "1,00", "identificacao": "", "justificativa": "x"}, "Informe a identificação"),
        ({"valor": "1,00", "identificacao": "x", "justificativa": " "}, "Informe a justificativa"),
    ):
        resposta = tela.cliente.post(reverse("financeiro_aporte"), dados)
        assert resposta.status_code == 400
        assert mensagem in resposta.content.decode()
    assert _estado() == antes


def test_id_inexistente_responde_404(tela: Tela) -> None:  # A-11
    for nome, dados in (
        ("financeiro_designar", {"valor": "1,00", "justificativa": "x"}),
        ("financeiro_cobrir_obrigacao", {"rodada": tela.ap.rodada.pk, "valor": "1,00"}),
        ("financeiro_cobrir_despesa", {"fonte": "reserva", "valor": "1,00"}),
        ("financeiro_desfazer_designacao", {"justificativa": "x"}),
    ):
        resposta = tela.cliente.post(reverse(nome, kwargs={"pk": 999999}), dados)
        assert resposta.status_code == 404, nome


def test_desfazer_a_designacao_uma_vez_so(tela: Tela) -> None:  # A-12
    from django.db import transaction

    with transaction.atomic():
        designacao = designar_reserva(tela.ap.admin, tela.o1, D("25.00"), "devolução")
    assert situacao_da_reserva().comprometido == D("25.00")
    caminho = reverse("financeiro_desfazer_designacao", kwargs={"pk": designacao.pk})
    primeira = tela.cliente.post(caminho, {"justificativa": "outra fonte"})
    assert primeira.status_code == 302
    assert situacao_da_reserva().comprometido == D("0.00")
    segunda = tela.cliente.post(caminho, {"justificativa": "de novo"})
    assert segunda.status_code == 409
    assert "Esta designação já foi desfeita ou consumida." in segunda.content.decode()


def test_cobrir_a_obrigacao_com_a_receita(tela: Tela) -> None:
    resposta = tela.cliente.post(
        reverse("financeiro_cobrir_obrigacao", kwargs={"pk": tela.o1.pk}),
        {"rodada": tela.ap.rodada.pk, "valor": "3,75", "justificativa": "Receita da rodada"},
    )
    assert resposta.status_code == 302
    assert saldo(receita_de(tela.ap.rodada)) == D("0.00")


def test_o_aviso_do_alerta_aponta_para_o_resumo(tela: Tela) -> None:  # A-13
    from django.db import transaction

    with transaction.atomic():
        abrir_alerta("reserva_insuficiente", "geral", {"sem_cobertura": "35.00", "livre": "20.00"})
    notificacao = Notificacao.objects.get(conta=tela.ap.admin, evento="alerta_financeiro")
    assert notificacao.link == reverse("financeiro_resumo")


@pytest.mark.parametrize("nome", NOMES_DAS_ROTAS)
def test_cada_rota_financeira_declara_a_politica_de_administrador(nome: str) -> None:  # A-14
    assert rotas_sem_politica() == []
    kwargs = {"pk": 1} if nome in _COM_ID else None
    achada = resolve(reverse(nome, kwargs=kwargs))
    assert achada.url_name == nome
    assert politica_da_view(achada.func) == Politica.ADMINISTRADOR
    assert reverse(nome, kwargs=kwargs).startswith(BASE)


def test_o_mesmo_deposito_nao_entra_duas_vezes(tela: Tela) -> None:  # A-15
    dados = {"valor": "5,00", "identificacao": "sim-mov-5", "justificativa": "Aporte"}
    primeira = tela.cliente.post(reverse("financeiro_aporte"), dados)
    assert primeira.status_code == 302
    segunda = tela.cliente.post(reverse("financeiro_aporte"), dados)
    assert segunda.status_code == 409
    assert "Este depósito já foi registrado como aporte." in segunda.content.decode()
    assert MovimentoFinanceiro.objects.filter(tipo=T.APORTE, chave="aporte:sim-mov-5").count() == 1


def test_as_telas_de_leitura_e_de_formulario_respondem(tela: Tela) -> None:
    for nome in (
        *DE_LEITURA,
        "financeiro_aporte",
        "financeiro_retirada",
        "financeiro_conciliacoes",
    ):
        _pagina(tela, nome)


def test_o_menu_do_administrador_ganha_o_link_financeiro(tela: Tela) -> None:
    html = _pagina(tela, "painel_administracao")
    assert f'href="{reverse("financeiro_resumo")}"' in html
    assert "Financeiro" in html
