"""E15-06: o histórico de ações relevantes em `administracao/historico/` (acceptance A-1 a A-14).

A especificação pede ADM1 e ADM2 administradores, mas o banco admite um só (ver o review.md da
E15-02). Aqui ADM1 é o administrador e ADM2 é uma conta de comprador com esse nome, autora de e3.
"""

import re
from datetime import UTC, datetime
from typing import Any

import pytest
from django.test import Client

from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.devolucoes import entrar_de_novo
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, RodadaFactory

pytestmark = pytest.mark.django_db

URL = "/administracao/historico/"
E1 = datetime(2026, 11, 18, 2, 59, 59, tzinfo=UTC)
E2 = datetime(2026, 11, 18, 3, 0, 0, tzinfo=UTC)
E3 = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
AGORA = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


class Historico:
    def __init__(self, client: Client, relogio: RelogioControlado) -> None:
        from apps.nucleo.auditoria import SISTEMA, registrar_auditoria

        self.client = client
        relogio.congelar(AGORA)
        self.adm1, self.credencial = administrador_com_passkey(client)
        self.adm2 = ContaFactory.create(nome="ADM2")
        self.comprador = ContaFactory.create(nome="C")
        self.rodada = RodadaFactory.create()
        relogio.congelar(E1)
        self.e1 = registrar_auditoria(SISTEMA, "rodada.apuracao_final", self.rodada, {"pedidos": 3})
        relogio.congelar(E2)
        self.e2 = registrar_auditoria(
            self.adm1, "rodada.cancelar", self.rodada, {"com_reembolso": True}, motivo="teste"
        )
        relogio.congelar(E3)
        self.e3 = registrar_auditoria(
            self.adm2, "alerta.ciencia", self.rodada, {"tipo": "<b>x</b>"}
        )
        relogio.congelar(AGORA)
        self.relogio = relogio

    def pagina(self, consulta: str = "") -> Any:
        entrar_de_novo(self.client, self.credencial, self.adm1)
        return self.client.get(URL + consulta)


@pytest.fixture
def ah(client: Client, relogio: RelogioControlado) -> Historico:
    return Historico(client, relogio)


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _acoes(resposta: Any) -> list[str]:
    """As ações das linhas da lista, na ordem da página."""
    html = resposta.content.decode()
    return re.findall(r'<td class="acao">(.*?)</td>', html, flags=re.DOTALL)


def _nossas(resposta: Any) -> list[str]:
    return [
        a
        for a in _acoes(resposta)
        if a in ("rodada.apuracao_final", "rodada.cancelar", "alerta.ciencia")
    ]


def test_a_lista_do_mais_novo_ao_mais_antigo(ah: Historico) -> None:  # A-1
    resposta = ah.pagina()
    assert resposta.status_code == 200
    assert _nossas(resposta) == ["alerta.ciencia", "rodada.cancelar", "rodada.apuracao_final"]
    texto = _texto(resposta)
    assert "19/11/2026 09:00:00" in texto
    assert "ADM2" in texto
    assert f"{ah.e3.objeto_tipo} {ah.e3.objeto_id}" in texto
    assert "Sistema" in texto
    assert "17/11/2026 23:59:59" in texto
    assert "teste" in texto
    html = resposta.content.decode()
    linha_e3 = html[html.index('<td class="acao">alerta.ciencia') :]
    assert "—" in linha_e3[: linha_e3.index("</tr>")]


def test_o_html_das_alteracoes_e_escapado(ah: Historico) -> None:  # A-2
    html = ah.pagina().content.decode()
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html


def test_conta_ausente_vira_conta_id(ah: Historico) -> None:  # A-3
    from apps.nucleo.auditoria import EntradaAuditoria

    EntradaAuditoria.objects.create(
        autor_tipo="usuario",
        autor_id="987654",
        acao="teste.orfa",
        momento=AGORA,
        objeto_tipo="x",
        objeto_id="1",
    )
    assert "Conta 987654" in _texto(ah.pagina())


def _muitas(ah: Historico, quantas: int, acao: str = "teste.massa") -> None:
    from apps.nucleo.auditoria import EntradaAuditoria

    EntradaAuditoria.objects.bulk_create(
        [
            EntradaAuditoria(
                autor_tipo="sistema",
                acao=acao,
                momento=AGORA,
                objeto_tipo="x",
                objeto_id=str(n),
            )
            for n in range(quantas)
        ]
    )


def test_cinquenta_por_pagina(ah: Historico) -> None:  # A-4
    from apps.nucleo.auditoria import EntradaAuditoria

    _muitas(ah, 120)
    total = EntradaAuditoria.objects.count()
    assert len(_acoes(ah.pagina())) == 50
    assert len(_acoes(ah.pagina("?pagina=3"))) == min(50, total - 100)
    ultima = (total - 1) // 50 + 1
    assert len(_acoes(ah.pagina("?pagina=99"))) == total - 50 * (ultima - 1)


def test_filtro_por_acao(ah: Historico) -> None:  # A-5
    resposta = ah.pagina("?acao=rodada.cancelar")
    assert _nossas(resposta) == ["rodada.cancelar"]
    html = resposta.content.decode()
    opcoes = re.findall(r'<option value="([^"]*)"', html)
    nossas = [
        o for o in opcoes if o in ("alerta.ciencia", "rodada.apuracao_final", "rodada.cancelar")
    ]
    assert nossas == sorted(nossas)
    assert len(nossas) == 3


def test_filtro_por_autor(ah: Historico) -> None:  # A-6
    assert _nossas(ah.pagina("?autor=sistema")) == ["rodada.apuracao_final"]
    assert _nossas(ah.pagina(f"?autor={ah.adm1.pk}")) == ["rodada.cancelar"]
    opcoes = re.findall(r'<option value="([^"]*)"', ah.pagina("").content.decode())
    autores = opcoes[opcoes.index("sistema") :]
    assert autores == ["sistema", str(ah.adm1.pk)]  # sem o comprador C nem ADM2 (comprador)


def test_o_intervalo_de_datas_e_o_dia_de_brasilia(ah: Historico) -> None:  # A-7 e A-8
    assert _nossas(ah.pagina("?de=2026-11-18&ate=2026-11-18")) == ["rodada.cancelar"]
    assert _nossas(ah.pagina("?de=2026-11-17&ate=2026-11-17")) == ["rodada.apuracao_final"]


def test_filtros_combinados_sem_resultado(ah: Historico) -> None:  # A-9
    resposta = ah.pagina("?acao=rodada.cancelar&autor=sistema")
    assert "Nenhuma ação encontrada." in _texto(resposta)
    assert _nossas(resposta) == []


@pytest.mark.parametrize(
    ("consulta", "nome"),
    [
        ("?acao=inexistente", "acao"),
        ("?autor=abc", "autor"),
        ("?de=18/11/2026", "de"),
        ("?de=2026-11-19&ate=2026-11-18", "de"),
    ],
)
def test_filtro_invalido_e_ignorado(ah: Historico, consulta: str, nome: str) -> None:  # A-10
    resposta = ah.pagina(consulta)
    assert resposta.status_code == 200
    assert f"Filtro inválido ignorado: {nome}." in _texto(resposta)
    assert len(_nossas(resposta)) == 3


def test_autor_que_nao_e_administrador_e_invalido(ah: Historico) -> None:  # A-10
    resposta = ah.pagina(f"?autor={ah.comprador.pk}")
    assert "Filtro inválido ignorado: autor." in _texto(resposta)
    assert len(_nossas(resposta)) == 3


def test_autor_comprador_com_nome_de_administrador_e_invalido(ah: Historico) -> None:  # A-10
    resposta = ah.pagina(f"?autor={ah.adm2.pk}")
    assert "Filtro inválido ignorado: autor." in _texto(resposta)
    assert len(_nossas(resposta)) == 3


def test_o_invalido_nao_atrapalha_o_valido(ah: Historico) -> None:  # A-10
    resposta = ah.pagina("?acao=rodada.cancelar&autor=abc")
    assert "Filtro inválido ignorado: autor." in _texto(resposta)
    assert _nossas(resposta) == ["rodada.cancelar"]


def test_a_paginacao_mantem_os_filtros(ah: Historico) -> None:  # A-11
    _muitas(ah, 120, "teste.massa")
    html = ah.pagina("?acao=teste.massa&pagina=2").content.decode()
    assert "acao=teste.massa" in html
    assert re.search(r'href="\?[^"]*acao=teste.massa[^"]*pagina=1', html) or re.search(
        r'href="\?[^"]*pagina=1[^"]*acao=teste.massa', html
    )


def test_a_leitura_nao_grava(ah: Historico) -> None:  # A-12
    from apps.nucleo.auditoria import EntradaAuditoria

    antes = EntradaAuditoria.objects.count()
    ah.pagina()
    ah.pagina("?acao=rodada.cancelar")
    assert EntradaAuditoria.objects.count() == antes


def test_acesso_e_metodo(ah: Historico) -> None:  # A-13
    entrar_de_novo(ah.client, ah.credencial, ah.adm1)
    assert ah.client.post(URL).status_code == 405
    for conta in (ah.comprador, ContaFactory.create(fornecedor=True)):
        cliente = Client()
        cliente.force_login(conta)
        assert cliente.get(URL).status_code == 403
    anonimo = Client().get(URL)
    assert anonimo.status_code == 302
    assert "/entrar/" in anonimo["Location"]


def test_o_link_no_painel(ah: Historico) -> None:  # A-14
    entrar_de_novo(ah.client, ah.credencial, ah.adm1)
    html = ah.client.get("/administracao/").content.decode()
    assert 'href="/administracao/historico/"' in html
    assert "Histórico de ações" in html
