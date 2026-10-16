"""E02-02: ponto único de decisão de acesso (acceptance A-9)."""

import pytest

from apps.contas.acesso import AcessoRecusado, Metodo, verificar_acesso
from apps.contas.models import EmailBanido, Situacao
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db


def _conta(papel: str = "comprador", situacao: str = "ativa", email: str = "ana@x.com"):  # type: ignore[no-untyped-def]
    if papel == "administrador":
        return ContaFactory.create(administrador=True, email_normalizado=email)
    if papel == "fornecedor":
        return ContaFactory.create(fornecedor=True, email_normalizado=email, situacao=situacao)
    return ContaFactory.create(email_normalizado=email, situacao=situacao)


def _banir(email: str) -> None:
    quem = ContaFactory.create(email_normalizado="quem.baniu@x.com")
    EmailBanido.objects.create(email_normalizado=email, banido_por=quem)


@pytest.mark.parametrize("metodo", list(Metodo))
@pytest.mark.parametrize("situacao", ["ativa", "suspensa"])
@pytest.mark.parametrize("papel", ["comprador", "fornecedor"])
def test_acesso_permitido_para_ativa_e_suspensa_em_todos_os_metodos(
    papel: str, situacao: str, metodo: Metodo
) -> None:
    conta = _conta(papel, situacao)
    verificar_acesso(conta, conta.email_normalizado, metodo)  # não levanta


@pytest.mark.parametrize("metodo", list(Metodo))
def test_acesso_recusa_email_banido_antes_de_qualquer_outra_regra(metodo: Metodo) -> None:
    conta = _conta()
    _banir("ana@x.com")
    with pytest.raises(AcessoRecusado) as erro:
        verificar_acesso(conta, "  ANA@x.com ", metodo)
    assert erro.value.codigo == "banido"


@pytest.mark.parametrize("metodo", list(Metodo))
def test_acesso_recusa_email_banido_mesmo_sem_conta(metodo: Metodo) -> None:
    _banir("ninguem@x.com")
    with pytest.raises(AcessoRecusado) as erro:
        verificar_acesso(None, "ninguem@x.com", metodo)
    assert erro.value.codigo == "banido"


@pytest.mark.parametrize("metodo", list(Metodo))
def test_acesso_recusa_conta_inexistente(metodo: Metodo) -> None:
    with pytest.raises(AcessoRecusado) as erro:
        verificar_acesso(None, "ninguem@x.com", metodo)
    assert erro.value.codigo == "sem_conta"


@pytest.mark.parametrize("metodo", list(Metodo))
@pytest.mark.parametrize("papel", ["comprador", "fornecedor"])
def test_acesso_recusa_conta_removida(papel: str, metodo: Metodo) -> None:
    conta = _conta(papel, Situacao.REMOVIDA)
    with pytest.raises(AcessoRecusado) as erro:
        verificar_acesso(conta, conta.email_normalizado, metodo)
    assert erro.value.codigo == "removida"


@pytest.mark.parametrize("metodo", [Metodo.LINK, Metodo.GOOGLE])
def test_acesso_recusa_administrador_por_link_e_google(metodo: Metodo) -> None:
    admin = _conta("administrador", email="admin@x.com")
    with pytest.raises(AcessoRecusado) as erro:
        verificar_acesso(admin, "admin@x.com", metodo)
    assert erro.value.codigo == "metodo_nao_permitido_admin"


@pytest.mark.parametrize("metodo", [Metodo.SENHA, Metodo.PASSKEY])
def test_acesso_nao_recusa_administrador_por_senha_e_passkey_na_funcao(metodo: Metodo) -> None:
    admin = _conta("administrador", email="admin@x.com")
    verificar_acesso(admin, "admin@x.com", metodo)  # a recusa temporária fica no adaptador


def test_acesso_codigo_nao_expoe_o_email() -> None:
    with pytest.raises(AcessoRecusado) as erro:
        verificar_acesso(None, "segredo@x.com", Metodo.SENHA)
    assert "segredo" not in str(erro.value)
