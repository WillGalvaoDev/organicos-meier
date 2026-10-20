"""E01-02: campos de modelo de dinheiro e quantidade (acceptance A-16, A-17, A-19, A-20)."""

import importlib
import sys
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from tests.apoio.models import ModeloValores

D = Decimal


@pytest.mark.django_db
def test_campos_limite_da_precisao_gravam_e_relem_identicos() -> None:  # A-16
    criado = ModeloValores.objects.create(preco=D("9999999999.99"), peso=D("999999999.999"))
    relido = ModeloValores.objects.get(pk=criado.pk)
    assert relido.preco == D("9999999999.99")
    assert relido.peso == D("999999999.999")


@pytest.mark.django_db
def test_campos_preservam_casas_definidas() -> None:
    criado = ModeloValores.objects.create(preco=D("8"), peso=D("2"))
    relido = ModeloValores.objects.get(pk=criado.pk)
    assert str(relido.preco) == "8.00"
    assert str(relido.peso) == "2.000"


@pytest.mark.parametrize(
    "campos",
    [
        {"preco": D("10000000000.00"), "peso": D("1")},
        {"preco": D("1"), "peso": D("1000000000.000")},
    ],
)
def test_campos_recusam_valor_acima_da_precisao(campos: dict[str, Decimal]) -> None:  # A-17
    with pytest.raises(ValidationError):
        ModeloValores(**campos).full_clean()


def test_campos_recusam_float_na_validacao() -> None:  # A-19
    with pytest.raises(ValidationError) as erro:
        ModeloValores(preco=7.99, peso=0.25).full_clean()
    assert set(erro.value.message_dict) == {"preco", "peso"}


def test_campos_aceitam_decimal_valido() -> None:
    ModeloValores(preco=D("7.99"), peso=D("0.25")).full_clean()


def test_app_de_testes_fora_da_producao(monkeypatch: pytest.MonkeyPatch) -> None:  # A-20
    monkeypatch.setenv("AMBIENTE", "homologacao")  # obrigatórios em prod.py (E07-02)
    monkeypatch.setenv("SEGREDO_AVISOS_SIMULADOR", "segredo-de-teste")
    for modulo in ("config.settings.base", "config.settings.prod"):
        ja_importado = modulo in sys.modules
        configuracao = importlib.import_module(modulo)
        if ja_importado:
            configuracao = importlib.reload(configuracao)
        assert "apoio_testes" not in configuracao.INSTALLED_APPS
        assert not any("apoio" in app for app in configuracao.INSTALLED_APPS)
