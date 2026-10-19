"""E06-07: telas do administrador para o fechamento (acceptance A-1 a A-9, A-12 e A-14)."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone
from django.utils.html import escape

from apps.contas.models import Conta
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.fechamento import (
    encerrar_fechamento,
    iniciar_fechamento,
    prazo_do_fechamento,
)
from apps.rodadas.forms import FormularioProrrogacao
from apps.rodadas.models import Ciclo, Etapa, PrazoDoFechamento, Rodada
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.interesses import cenario, reservada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
T0 = datetime(2026, 11, 2, 13, 30, tzinfo=UTC)
T = datetime(2026, 11, 3, 13, 30, tzinfo=UTC)


@pytest.fixture
def admin_client(client: Client, webauthn: Any, relogio: RelogioControlado) -> Client:
    relogio.congelar(T0)  # a sessão nasce no instante dos testes, que avançam o relógio
    administrador_logado(client)
    return client


def pagina_do_estoque(rodada: Rodada) -> str:
    return f"/administracao/rodadas/{rodada.pk}/estoque/"


def iniciar_url(rodada: Rodada) -> str:
    return f"/administracao/rodadas/{rodada.pk}/fechamento/iniciar/"


def prorrogar_url(rodada: Rodada) -> str:
    return f"/administracao/rodadas/{rodada.pk}/fechamento/prorrogar/"


def montar(reservado: int, relogio: RelogioControlado) -> Rodada:
    relogio.congelar(T0)
    rodada, produto, _ = cenario(None, nome="Ovos", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, reservado)
    return rodada


def administrador() -> Conta:
    return Conta.objects.get(papel="administrador")


def html_de(cliente: Client, url: str) -> str:
    resposta = cliente.get(url)
    assert resposta.status_code == 200
    return str(resposta.content.decode())


def test_com_o_minimo_atingido_oferece_iniciar(
    admin_client: Client, relogio: RelogioControlado
) -> None:  # A-1
    rodada = montar(10, relogio)
    html = html_de(admin_client, pagina_do_estoque(rodada))
    assert f'action="{iniciar_url(rodada)}"' in html
    assert "Iniciar fechamento" in html
    assert "O prazo será de 24 horas a partir do início." in html


def test_sem_o_minimo_nao_oferece_iniciar(
    admin_client: Client, relogio: RelogioControlado
) -> None:  # A-2
    rodada = montar(9, relogio)
    html = html_de(admin_client, pagina_do_estoque(rodada))
    assert "O fechamento pode ser iniciado quando o mínimo elegível for atingido." in html
    assert "Iniciar fechamento" not in html
    assert iniciar_url(rodada) not in html


def test_iniciar_pela_tela(admin_client: Client, relogio: RelogioControlado) -> None:  # A-3
    rodada = montar(10, relogio)
    resposta = admin_client.post(iniciar_url(rodada))
    assert (resposta.status_code, resposta.get("Location")) == (302, pagina_do_estoque(rodada))
    html = html_de(admin_client, pagina_do_estoque(rodada))
    assert "Fechamento iniciado. Prazo: 03/11/2026 às 10:30 (horário de Brasília)." in html
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO


def test_iniciar_recusado_volta_409_com_a_mensagem(
    admin_client: Client, relogio: RelogioControlado
) -> None:  # A-4
    rodada = montar(9, relogio)
    resposta = admin_client.post(iniciar_url(rodada))
    assert resposta.status_code == 409
    assert "O fechamento só pode começar com o mínimo elegível atingido." in (
        resposta.content.decode()
    )
    assert Ciclo.objects.count() == 0
    outra = montar(10, relogio)
    iniciar_fechamento(administrador(), outra)
    resposta = admin_client.post(iniciar_url(outra))
    assert resposta.status_code == 409
    assert "O fechamento só pode começar com a rodada em interesse." in resposta.content.decode()
    assert Ciclo.objects.filter(rodada=outra).count() == 1


def test_fechamento_em_andamento_mostra_prazo_formulario_e_historico(
    admin_client: Client, relogio: RelogioControlado
) -> None:  # A-5
    rodada = montar(10, relogio)
    iniciar_fechamento(administrador(), rodada)
    html = html_de(admin_client, pagina_do_estoque(rodada))
    assert "Prazo do fechamento: 03/11/2026 10:30 (horário de Brasília)" in html
    assert f'action="{prorrogar_url(rodada)}"' in html
    assert "Prorrogar fechamento" in html
    assert re.search(r'name="termino"\s+value="2026-11-03T10:30"', html)
    assert "Início" in html


def test_prorrogar_pela_tela(admin_client: Client, relogio: RelogioControlado) -> None:  # A-6
    rodada = montar(10, relogio)
    iniciar_fechamento(administrador(), rodada)
    resposta = admin_client.post(prorrogar_url(rodada), {"termino": "2026-11-04T01:30"})
    assert (resposta.status_code, resposta.get("Location")) == (302, pagina_do_estoque(rodada))
    html = html_de(admin_client, pagina_do_estoque(rodada))
    assert "Prazo do fechamento prorrogado para 04/11/2026 às 01:30 (horário de Brasília)." in html
    assert prazo_do_fechamento(rodada) == datetime(2026, 11, 4, 4, 30, tzinfo=UTC)
    assert "Início" in html
    assert "Prorrogação" in html
    assert PrazoDoFechamento.objects.count() == 2


@pytest.mark.parametrize("texto", ["", "abc", '"><b>x</b>'])
def test_termino_invalido_volta_200_sem_gravar(
    texto: str, admin_client: Client, relogio: RelogioControlado
) -> None:  # A-7
    rodada = montar(10, relogio)
    iniciar_fechamento(administrador(), rodada)
    resposta = admin_client.post(prorrogar_url(rodada), {"termino": texto})
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Informe a data e a hora do novo prazo." in html
    assert "<b>x</b>" not in html
    if texto.startswith('"'):
        assert "&quot;&gt;&lt;b&gt;x&lt;/b&gt;" in html
    assert PrazoDoFechamento.objects.count() == 1


def test_termino_anterior_ao_prazo_volta_409(
    admin_client: Client, relogio: RelogioControlado
) -> None:  # A-7
    rodada = montar(10, relogio)
    iniciar_fechamento(administrador(), rodada)
    resposta = admin_client.post(prorrogar_url(rodada), {"termino": "2026-11-03T09:00"})
    assert resposta.status_code == 409
    assert "O novo prazo precisa ser posterior ao prazo atual, 03/11/2026 às 10:30." in (
        resposta.content.decode()
    )
    assert PrazoDoFechamento.objects.count() == 1


def test_prazo_vencido_sem_a_tarefa_nao_oferece_prorrogar(
    admin_client: Client, relogio: RelogioControlado
) -> None:  # A-8
    rodada = montar(10, relogio)
    iniciar_fechamento(administrador(), rodada)
    relogio.congelar(datetime(2026, 11, 3, 13, 31, tzinfo=UTC))
    html = html_de(admin_client, pagina_do_estoque(rodada))
    assert (
        "Prazo do fechamento encerrado em 03/11/2026 10:30. "
        "O encerramento será processado automaticamente."
    ) in html
    assert prorrogar_url(rodada) not in html
    resposta = admin_client.post(prorrogar_url(rodada), {"termino": "2026-11-05T10:00"})
    assert resposta.status_code == 409
    assert "O prazo deste fechamento já terminou e não pode mais ser prorrogado." in (
        resposta.content.decode()
    )


def test_fechamento_encerrado_mostra_o_estado_e_o_detalhe_do_fornecedor(
    admin_client: Client, relogio: RelogioControlado
) -> None:  # A-9
    rodada = montar(12, relogio)
    iniciar_fechamento(administrador(), rodada)
    relogio.congelar(T)
    encerrar_fechamento(rodada)
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO_ENCERRADO
    html = html_de(admin_client, pagina_do_estoque(rodada))
    assert "Fechamento encerrado em 03/11/2026 10:30. Aguardando a autorização do pagamento." in (
        html
    )
    detalhe = html_de(admin_client, f"/administracao/fornecedores/{rodada.fornecedor_id}/")
    assert "Prazo do fechamento: 03/11/2026 10:30" in detalhe
    assert "Prazo encerrado." in detalhe


@pytest.mark.parametrize("quem", ["comprador", "fornecedor", "anonimo"])
def test_so_o_administrador_usa_as_rotas(quem: str, relogio: RelogioControlado) -> None:  # A-12
    rodada = montar(10, relogio)
    cliente = Client()
    if quem == "comprador":
        cliente.force_login(ContaFactory.create())
    elif quem == "fornecedor":
        cliente.force_login(ContaFactory.create(fornecedor=True))
    for url in (iniciar_url(rodada), prorrogar_url(rodada)):
        resposta = cliente.post(url, {"termino": "2026-11-05T10:00"})
        if quem == "anonimo":
            assert resposta.status_code == 302
            assert str(resposta.get("Location")).startswith("/entrar/")
        else:
            assert resposta.status_code == 403
    assert Ciclo.objects.count() == 0


def test_get_nas_rotas_responde_405(admin_client: Client, relogio: RelogioControlado) -> None:
    rodada = montar(10, relogio)  # A-12
    assert admin_client.get(iniciar_url(rodada)).status_code == 405
    assert admin_client.get(prorrogar_url(rodada)).status_code == 405


def test_rodada_inexistente_da_404(admin_client: Client) -> None:  # A-14
    assert admin_client.post("/administracao/rodadas/999999/fechamento/iniciar/").status_code == 404
    resposta = admin_client.post(
        "/administracao/rodadas/999999/fechamento/prorrogar/", {"termino": "2026-11-05T10:00"}
    )
    assert resposta.status_code == 404


TEXTOS_FORA_DO_FORMATO = [
    "2026-11-04",
    "2026-11-04T01:30:59",
    "2026-11-04T01:30:00+00:00",
    "2026-11-04T01:30-03:00",
    "2026-11-04 01:30",
    "2026-11-04t01:30",
    "2026-11-04T1:30",
    "2026-11-31T10:00",
    "2026-11-04T24:00",
    "٢٠٢٦-11-04T01:30",
]


@pytest.mark.parametrize("texto", TEXTOS_FORA_DO_FORMATO)
def test_formato_do_prazo_restrito_ao_contrato(
    texto: str, admin_client: Client, relogio: RelogioControlado
) -> None:  # A-15, E06-R02
    rodada = montar(10, relogio)
    iniciar_fechamento(administrador(), rodada)
    form = FormularioProrrogacao({"termino": texto})
    assert not form.is_valid(), form.cleaned_data
    resposta = admin_client.post(prorrogar_url(rodada), {"termino": texto})
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Informe a data e a hora do novo prazo." in html
    assert escape(texto) in html
    assert PrazoDoFechamento.objects.count() == 1
    assert EntradaAuditoria.objects.filter(acao="rodada.prorrogar_fechamento").count() == 0
    assert prazo_do_fechamento(rodada) == T


def test_o_prazo_digitado_vale_no_horario_de_brasilia(
    admin_client: Client, relogio: RelogioControlado
) -> None:  # A-16, E06-R02
    rodada = montar(10, relogio)
    iniciar_fechamento(administrador(), rodada)
    destino = datetime(2026, 11, 4, 4, 30, tzinfo=UTC)
    with timezone.override("UTC"):
        for texto in ("2026-11-04T01:30", " 2026-11-04T01:30 "):
            form = FormularioProrrogacao({"termino": texto})
            assert form.is_valid(), form.errors
            limpo = form.cleaned_data["termino"]
            assert limpo == destino
            assert limpo.tzinfo is not None
            assert (limpo.second, limpo.microsecond) == (0, 0)
        resposta = admin_client.post(prorrogar_url(rodada), {"termino": "2026-11-04T01:30"})
    assert resposta.status_code == 302
    assert prazo_do_fechamento(rodada) == destino
