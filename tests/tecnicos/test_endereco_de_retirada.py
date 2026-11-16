"""E14-03: o endereço de retirada, o registro e a auditoria (acceptance A-1 a A-4 e A-13)."""

from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction

from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = pytest.mark.django_db

ENDERECO = "Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ"


@pytest.fixture
def admin() -> Any:
    return ContaFactory.create(nome="Adm", papel="administrador")


def _definir(autor: Any, texto: Any) -> Any:
    from apps.pedidos.endereco_de_retirada import definir_endereco_de_retirada

    return definir_endereco_de_retirada(autor, texto)


def _enderecos() -> list[Any]:
    from apps.pedidos.models import EnderecoDeRetirada

    return list(EnderecoDeRetirada.objects.order_by("pk"))


def test_o_primeiro_endereco_e_o_vigente(admin: Any) -> None:  # A-1
    from apps.pedidos.endereco_de_retirada import endereco_vigente

    assert endereco_vigente() is None
    registro = _definir(admin, f"  {ENDERECO}  ")
    assert (registro.texto, registro.autor_id) == (ENDERECO, admin.pk)
    assert registro.registrado_em is not None
    vigente = endereco_vigente()
    assert vigente is not None
    assert vigente.pk == registro.pk
    (auditoria,) = EntradaAuditoria.objects.filter(acao="retirada.definir_endereco")
    assert auditoria.autor_id == str(admin.pk)
    assert auditoria.alteracoes == {"anterior": "", "novo": ENDERECO}


def test_um_endereco_novo_preserva_o_historico(admin: Any) -> None:  # A-2
    from apps.pedidos.endereco_de_retirada import endereco_vigente

    primeiro = _definir(admin, ENDERECO)
    segundo = _definir(admin, "Rua Nova, 5")
    assert [e.texto for e in _enderecos()] == [ENDERECO, "Rua Nova, 5"]
    vigente = endereco_vigente()
    assert vigente is not None
    assert vigente.pk == segundo.pk
    primeiro.refresh_from_db()
    assert primeiro.texto == ENDERECO
    auditoria = EntradaAuditoria.objects.filter(acao="retirada.definir_endereco").order_by("pk")
    ultima = auditoria.last()
    assert ultima is not None
    assert ultima.alteracoes == {"anterior": ENDERECO, "novo": "Rua Nova, 5"}


def test_textos_recusados_e_o_limite_de_500(admin: Any) -> None:  # A-3
    from apps.pedidos.endereco_de_retirada import EnderecoRecusado

    _definir(admin, ENDERECO)
    for texto, codigo in (
        (ENDERECO, "sem_alteracao"),
        ("", "texto_invalido"),
        ("   ", "texto_invalido"),
        ("x" * 501, "texto_invalido"),
    ):
        with pytest.raises(EnderecoRecusado) as erro:
            _definir(admin, texto)
        assert erro.value.codigo == codigo
    assert len(_enderecos()) == 1
    assert _definir(admin, "y" * 500).texto == "y" * 500
    assert _definir(admin, "Rua A, 1\r\nFundos").texto == "Rua A, 1\nFundos"
    with pytest.raises(EnderecoRecusado) as erro:
        _definir(admin, "Rua A, 1\nFundos")
    assert str(erro.value) == "O endereço informado é igual ao atual."


def test_so_o_administrador_define(admin: Any) -> None:  # A-4
    comprador = ContaFactory.create(nome="A")
    fornecedor = ContaFactory.create(
        nome="F", papel="fornecedor", fornecedor_id=FornecedorFactory.create().pk
    )
    for autor in (comprador, fornecedor, None):
        with pytest.raises(PermissionDenied):
            _definir(autor, ENDERECO)
    assert not _enderecos()


def test_o_endereco_so_aceita_insercao(admin: Any) -> None:  # A-13
    from apps.pedidos.models import EnderecoDeRetirada

    registro = _definir(admin, ENDERECO)
    with pytest.raises(RegistroImutavel):
        registro.save()
    with pytest.raises(RegistroImutavel):
        registro.delete()
    with pytest.raises(RegistroImutavel):
        EnderecoDeRetirada.objects.all().update(texto="x")
    with pytest.raises(RegistroImutavel):
        EnderecoDeRetirada.objects.all().delete()
    for comando in (
        "UPDATE pedidos_enderecoderetirada SET texto = 'x'",
        "DELETE FROM pedidos_enderecoderetirada",
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(comando)
