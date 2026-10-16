"""E02-10: toda rota declara uma política (acceptance A-10 e A-11)."""

from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from django.views import View

from apps.contas.administracao import (
    SomenteAdministradorMixin,
    exige_reautenticacao_por_passkey,
    somente_administrador,
)
from apps.contas.permissoes import (
    POLITICAS_DE_TERCEIROS,
    ExigeCompradorAtivoMixin,
    ExigeCompradorMixin,
    ExigeFornecedorMixin,
    ExigeLoginMixin,
    Politica,
    PublicaMixin,
    entradas_de_terceiros_inexistentes,
    exige_comprador,
    exige_comprador_ativo,
    exige_fornecedor,
    exige_login,
    politica_da_view,
    publica,
    rotas_sem_politica,
)
from tests.fabricas import ContaFactory


@pytest.mark.parametrize("urlconf", ["config.urls", "tests.apoio.urls"])
def test_nenhuma_rota_do_projeto_fica_sem_politica(urlconf: str) -> None:  # A-10
    assert rotas_sem_politica(urlconf) == []


def test_entradas_de_terceiros_correspondem_a_rotas_existentes() -> None:  # A-10
    assert POLITICAS_DE_TERCEIROS  # allauth e Google precisam estar declarados
    assert entradas_de_terceiros_inexistentes("config.urls") == []


def test_rota_sem_politica_acrescentada_e_acusada_pelo_nome_ou_caminho() -> None:  # A-11
    acusadas = rotas_sem_politica("tests.apoio.urls_sem_politica")
    assert len(acusadas) == 1
    assert "teste/esquecida/" in acusadas[0]
    assert "teste_rota_esquecida" in acusadas[0]


def test_entrada_de_terceiros_para_rota_inexistente_e_acusada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-10
    monkeypatch.setitem(POLITICAS_DE_TERCEIROS, "rota_que_nao_existe", Politica.PUBLICA)
    assert entradas_de_terceiros_inexistentes("config.urls") == ["rota_que_nao_existe"]


def test_terceiros_nao_aceita_curingas() -> None:
    assert all("*" not in nome for nome in POLITICAS_DE_TERCEIROS)


def test_decoradores_gravam_a_politica_na_view() -> None:
    def base(request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")

    esperado = {
        publica: Politica.PUBLICA,
        exige_login: Politica.AUTENTICADA,
        exige_comprador: Politica.COMPRADOR,
        exige_comprador_ativo: Politica.COMPRADOR_ATIVO,
        exige_fornecedor: Politica.FORNECEDOR,
        somente_administrador: Politica.ADMINISTRADOR,
        exige_reautenticacao_por_passkey: Politica.ADMINISTRADOR,
    }
    for decorador, politica in esperado.items():
        assert politica_da_view(decorador(base)) == politica, decorador
    assert politica_da_view(base) is None


@pytest.mark.parametrize(
    ("mixin", "politica"),
    [
        (PublicaMixin, Politica.PUBLICA),
        (ExigeLoginMixin, Politica.AUTENTICADA),
        (ExigeCompradorMixin, Politica.COMPRADOR),
        (ExigeCompradorAtivoMixin, Politica.COMPRADOR_ATIVO),
        (ExigeFornecedorMixin, Politica.FORNECEDOR),
        (SomenteAdministradorMixin, Politica.ADMINISTRADOR),
    ],
)
def test_views_de_classe_declaram_a_politica_na_view_resultante(
    mixin: type, politica: Politica
) -> None:
    class Exemplo(mixin, View):  # type: ignore[misc]
        def get(self, request: HttpRequest) -> HttpResponse:
            return HttpResponse("ok")

    assert politica_da_view(Exemplo.as_view()) == politica


@pytest.mark.django_db
def test_mixin_de_comprador_ativo_recusa_suspenso_e_aceita_ativo() -> None:
    class Exemplo(ExigeCompradorAtivoMixin, View):
        def get(self, request: HttpRequest) -> HttpResponse:
            return HttpResponse("ok")

    view: Any = Exemplo.as_view()
    fabrica = RequestFactory()
    requisicao = fabrica.get("/x/")
    requisicao.user = ContaFactory.build(suspensa=True)
    with pytest.raises(PermissionDenied):
        view(requisicao)
    requisicao.user = ContaFactory.build()
    assert view(requisicao).status_code == 200


@pytest.mark.django_db
def test_mixin_de_fornecedor_expoe_o_fornecedor_vinculado() -> None:
    class Exemplo(ExigeFornecedorMixin, View):
        def get(self, request: HttpRequest) -> HttpResponse:
            return HttpResponse(str(request.fornecedor_vinculado.nome))  # type: ignore[attr-defined]

    requisicao = RequestFactory().get("/x/")
    conta = ContaFactory.build(fornecedor=True)
    from apps.fornecedores.models import Fornecedor

    conta.fornecedor = Fornecedor(nome="Horta", pk=7)
    requisicao.user = conta
    resposta: Any = Exemplo.as_view()(requisicao)
    assert resposta.content == b"Horta"
