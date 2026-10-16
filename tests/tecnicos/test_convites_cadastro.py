"""E02-05: cadastro por convite (acceptance A-1 a A-12 e A-15 a A-18)."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from django.test import Client

from apps.contas.convites import ConviteInvalido, MetodoCadastro, consumir_convite, validar_convite
from apps.contas.models import Conta, Convite, EmailBanido, Papel
from apps.nucleo.auditoria import EntradaAuditoria
from tests.fabricas import ContaFactory, ConviteFactory, FornecedorFactory

pytestmark = pytest.mark.django_db

SENHA = "senha-forte-9271!"
T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)
MS = timedelta(milliseconds=1)
INVALIDO = "Este convite não é mais válido. Solicite um novo convite ao administrador."


def _convite(**campos: Any) -> tuple[Convite, str]:
    """Convite com token conhecido pelo teste."""
    token = secrets.token_urlsafe(32)
    convite = ConviteFactory.create(token_hash=Convite.hash_do_token(token), **campos)
    return convite, token


def _rota(token: str) -> str:
    return f"/convite/{token}/"


def _cadastrar(client: Client, token: str, **extras: Any) -> Any:
    dados = {"nome": "Bia", "senha": SENHA, "confirmacao": SENHA, **extras}
    return client.post(_rota(token), dados)


def _autenticado(client: Client) -> bool:
    return "_auth_user_id" in client.session


def test_pagina_mostra_email_so_leitura_finalidade_e_campos(client: Client) -> None:  # A-1
    _, token = _convite(email_normalizado="bia@x.com")
    resposta = client.get(_rota(token))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "bia@x.com" in html
    assert 'name="email"' not in html  # e-mail só para leitura
    assert "comprador" in html.lower()
    for campo in ("nome", "senha", "confirmacao"):
        assert f'name="{campo}"' in html


def test_pagina_de_fornecedor_cita_o_nome_do_fornecedor(client: Client) -> None:
    fornecedor = FornecedorFactory.create(nome="Horta do Zé")
    _, token = _convite(fornecedor=True, fornecedor_id=fornecedor.pk)
    assert "Horta do Zé" in client.get(_rota(token)).content.decode()


def test_get_nao_consome_o_convite(client: Client) -> None:
    convite, token = _convite()
    client.get(_rota(token))
    client.get(_rota(token))
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert Conta.objects.filter(papel="comprador").count() == 0


@pytest.mark.acceptance
def test_cadastro_cria_conta_email_verificado_e_sessao(client: Client) -> None:  # A-2, cenário 1
    convite, token = _convite(email_normalizado="bia@x.com")
    resposta = _cadastrar(client, token)
    assert resposta.status_code == 302
    assert resposta["Location"] == "/inicio/"
    conta = Conta.objects.get(email_normalizado="bia@x.com")
    assert conta.papel == Papel.COMPRADOR
    assert conta.situacao == "ativa"
    assert conta.nome == "Bia"
    assert conta.check_password(SENHA)
    endereco = EmailAddress.objects.get(user=conta)
    assert (endereco.email, endereco.verified, endereco.primary) == ("bia@x.com", True, True)
    convite.refresh_from_db()
    assert convite.consumido_em is not None
    assert convite.conta_criada == conta
    assert _autenticado(client)
    assert "Bia" in client.get("/inicio/").content.decode()


@pytest.mark.acceptance
def test_convite_consumido_nao_pode_ser_reutilizado(client: Client) -> None:  # A-3, cenário 1
    _, token = _convite(email_normalizado="bia@x.com")
    _cadastrar(client, token)
    outro = Client()
    for resposta in (outro.get(_rota(token)), _cadastrar(outro, token)):
        assert resposta.status_code == 410
        assert INVALIDO in resposta.content.decode()
    assert Conta.objects.filter(email_normalizado="bia@x.com").count() == 1


@pytest.mark.acceptance
@pytest.mark.parametrize(
    ("deslocamento", "aceito"),
    [(-MS, True), (timedelta(0), False), (MS, False)],
    ids=["um_ms_antes", "no_limite", "um_ms_depois"],
)
def test_fronteira_de_24h_no_post(
    client: Client, relogio: Any, deslocamento: timedelta, aceito: bool
) -> None:  # A-4, cenário 1
    _, token = _convite(emitido_em=T)
    relogio.congelar(T + timedelta(hours=24) + deslocamento)
    resposta = _cadastrar(client, token)
    if aceito:
        assert resposta.status_code == 302
        assert Conta.objects.filter(papel="comprador").count() == 1
    else:
        assert resposta.status_code == 410
        assert INVALIDO in resposta.content.decode()
        assert Conta.objects.filter(papel="comprador").count() == 0


def test_valido_no_get_e_expirado_no_post_e_recusado(client: Client, relogio: Any) -> None:  # A-5
    convite, token = _convite(emitido_em=T)
    relogio.congelar(T + timedelta(hours=23))
    assert client.get(_rota(token)).status_code == 200
    relogio.congelar(T + timedelta(hours=24))
    assert _cadastrar(client, token).status_code == 410
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert Conta.objects.filter(papel="comprador").count() == 0


@pytest.mark.acceptance
def test_campos_extras_do_post_sao_ignorados_comprador(
    client: Client,
) -> None:  # A-6, cenários 1 e 62
    fornecedor = FornecedorFactory.create()
    _, token = _convite(email_normalizado="bia@x.com")
    _cadastrar(client, token, email="outra@x.com", papel="fornecedor", fornecedor=fornecedor.pk)
    conta = Conta.objects.get(email_normalizado="bia@x.com")
    assert conta.papel == "comprador"
    assert conta.fornecedor is None
    assert not Conta.objects.filter(email_normalizado="outra@x.com").exists()


@pytest.mark.acceptance
def test_campos_extras_do_post_sao_ignorados_fornecedor(client: Client) -> None:  # A-7, cenário 1
    f1 = FornecedorFactory.create(nome="F1")
    f2 = FornecedorFactory.create(nome="F2")
    _, token = _convite(fornecedor=True, fornecedor_id=f1.pk, email_normalizado="ze@x.com")
    _cadastrar(client, token, fornecedor=f2.pk, papel="comprador")
    conta = Conta.objects.get(email_normalizado="ze@x.com")
    assert conta.papel == "fornecedor"
    assert conta.fornecedor == f1


def test_email_banido_depois_da_emissao_e_recusado(client: Client) -> None:  # A-8
    convite, token = _convite(email_normalizado="ana@x.com")
    EmailBanido.objects.create(
        email_normalizado="ana@x.com", banido_por=ContaFactory.create(email_normalizado="q@x.com")
    )
    assert client.get(_rota(token)).status_code == 410
    assert _cadastrar(client, token).status_code == 410
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert not Conta.objects.filter(email_normalizado="ana@x.com").exists()


@pytest.mark.acceptance
def test_email_que_virou_conta_depois_da_emissao_e_recusado(
    client: Client,
) -> None:  # A-9, cenário 80
    primeiro, token_a = _convite(email_normalizado="ana@x.com")
    _, token_b = _convite(email_normalizado="ana@x.com")
    _cadastrar(client, token_b)
    assert Conta.objects.filter(email_normalizado="ana@x.com").count() == 1
    outro = Client()
    resposta = _cadastrar(outro, token_a)
    assert resposta.status_code == 410
    assert Conta.objects.filter(email_normalizado="ana@x.com").count() == 1
    primeiro.refresh_from_db()
    assert primeiro.consumido_em is None


@pytest.mark.parametrize(
    "dados",
    [
        {"nome": ""},
        {"nome": "     "},
        {"nome": "x" * 151},
        {"senha": "curta1", "confirmacao": "curta1"},
        {"senha": "1234567890123", "confirmacao": "1234567890123"},
        {"confirmacao": "outra-senha-forte-5530!"},
    ],
    ids=[
        "nome_vazio",
        "nome_so_espacos",
        "nome_longo",
        "senha_curta",
        "senha_numerica",
        "confirmacao_diferente",
    ],
)
def test_validacao_de_nome_e_senha_devolve_formulario(
    client: Client, dados: dict[str, str]
) -> None:  # A-10
    convite, token = _convite(email_normalizado="bia@x.com")
    base = {"nome": "Bia", "senha": SENHA, "confirmacao": SENHA}
    resposta = client.post(_rota(token), {**base, **dados})
    assert resposta.status_code == 200
    assert resposta.context["form"].errors
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert not Conta.objects.filter(email_normalizado="bia@x.com").exists()
    assert not _autenticado(client)


def test_nome_com_espacos_nas_pontas_e_aparado(client: Client) -> None:
    _, token = _convite(email_normalizado="bia@x.com")
    _cadastrar(client, token, nome="  Bia Souza  ")
    assert Conta.objects.get(email_normalizado="bia@x.com").nome == "Bia Souza"


def test_token_alterado_ou_aleatorio_e_recusado(client: Client) -> None:  # A-11
    _, token = _convite()
    alterado = token[:-1] + ("A" if token[-1] != "A" else "B")
    for falso in (alterado, secrets.token_urlsafe(32)):
        assert client.get(_rota(falso)).status_code == 410
        resposta = _cadastrar(client, falso)
        assert resposta.status_code == 410
        assert INVALIDO in resposta.content.decode()
    assert Conta.objects.filter(papel="comprador").count() == 0


def test_conta_autenticada_nao_usa_convite(client: Client) -> None:  # A-12
    convite, token = _convite(email_normalizado="bia@x.com")
    client.force_login(ContaFactory.create(email_normalizado="ana@x.com"))
    pagina = client.get(_rota(token))
    assert "Saia da conta atual para usar este convite." in pagina.content.decode()
    assert 'name="senha"' not in pagina.content.decode()
    resposta = _cadastrar(client, token)
    assert "Saia da conta atual para usar este convite." in resposta.content.decode()
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert not Conta.objects.filter(email_normalizado="bia@x.com").exists()


def test_auditoria_do_cadastro_nao_tem_dado_pessoal(client: Client) -> None:  # A-15
    convite, token = _convite(email_normalizado="bia@x.com")
    _cadastrar(client, token)
    conta = Conta.objects.get(email_normalizado="bia@x.com")
    entrada = EntradaAuditoria.objects.get(acao="convite.consumir")
    assert entrada.autor_tipo == "usuario"
    assert entrada.autor_id == str(conta.pk)
    assert entrada.alteracoes == {"convite": convite.pk, "conta": conta.pk, "papel": "comprador"}
    texto = str(entrada.alteracoes) + entrada.motivo
    for segredo in ("bia@x.com", SENHA, token):
        assert segredo not in texto


def test_conta_criada_entra_depois_por_senha_sem_novo_convite(client: Client) -> None:  # A-16
    _, token = _convite(email_normalizado="bia@x.com")
    _cadastrar(client, token)
    client.post("/sair/")
    assert not _autenticado(client)
    client.post("/entrar/", {"login": " BIA@x.com ", "password": SENHA})
    assert _autenticado(client)


@pytest.mark.acceptance
def test_comprador_e_fornecedor_com_emails_diferentes_sao_contas_independentes(
    client: Client,
) -> None:  # A-17, cenário 81
    fornecedor = FornecedorFactory.create(nome="Horta")
    _, token_a = _convite(email_normalizado="ana@exemplo.com")
    _, token_b = _convite(
        email_normalizado="ana.fornecedor@exemplo.com", fornecedor=True, fornecedor_id=fornecedor.pk
    )
    _cadastrar(client, token_a, nome="Ana Compradora")
    segundo = Client()
    _cadastrar(segundo, token_b, nome="Ana Fornecedora")
    assert Conta.objects.filter(email_normalizado__startswith="ana").count() == 2
    inicio_a = client.get("/inicio/").content.decode()
    inicio_b = segundo.get("/inicio/").content.decode()
    assert "Ana Compradora" in inicio_a
    assert "Ana Fornecedora" not in inicio_a
    assert "Ana Fornecedora" in inicio_b
    assert "Ana Compradora" not in inicio_b
    assert "comprador" in inicio_a.lower()
    assert "fornecedor" in inicio_b.lower()


def _inexistente() -> str:
    return secrets.token_urlsafe(32)


def _consumido() -> str:
    _, token = _convite(consumido=True)
    return token


def _expirado() -> str:
    _, token = _convite(emitido_em=datetime(2020, 1, 1, tzinfo=UTC))
    return token


def _banido() -> str:
    convite, token = _convite(email_normalizado="banido@x.com")
    EmailBanido.objects.create(
        email_normalizado="banido@x.com",
        banido_por=ContaFactory.create(email_normalizado="q@x.com"),
    )
    assert convite.pk
    return token


def _em_uso() -> str:
    _, token = _convite(email_normalizado="usado@x.com")
    ContaFactory.create(email_normalizado="usado@x.com")
    return token


@pytest.mark.parametrize(
    ("preparar", "codigo"),
    [
        (_inexistente, "inexistente"),
        (_consumido, "consumido"),
        (_expirado, "expirado"),
        (_banido, "banido"),
        (_em_uso, "email_em_uso"),
    ],
)
def test_codigo_interno_corresponde_a_causa_e_a_pagina_e_identica(
    client: Client, preparar: Any, codigo: str
) -> None:  # A-18
    token = preparar()
    with pytest.raises(ConviteInvalido) as erro:
        validar_convite(token)
    assert erro.value.codigo == codigo
    with pytest.raises(ConviteInvalido) as erro:
        consumir_convite(token, "Bia", SENHA, metodo=MetodoCadastro.SENHA)
    assert erro.value.codigo == codigo
    assert INVALIDO in client.get(_rota(token)).content.decode()


def test_corpo_da_resposta_e_identico_nas_cinco_causas() -> None:  # A-18
    corpos = set()
    for preparar in (_inexistente, _consumido, _expirado, _banido, _em_uso):
        resposta = Client().get(_rota(preparar()))
        assert resposta.status_code == 410
        corpos.add(resposta.content)
    assert len(corpos) == 1


def test_servico_valida_nome_e_senha_alem_do_formulario() -> None:
    from django.core.exceptions import ValidationError

    _, token = _convite()
    for nome, senha in [("", SENHA), ("   ", SENHA), ("x" * 151, SENHA), ("Bia", "curta1")]:
        with pytest.raises(ValidationError):
            consumir_convite(token, nome, senha, metodo=MetodoCadastro.SENHA)
    assert Convite.objects.filter(consumido_em__isnull=False).count() == 0


# Teste do revisor (E02-10/review.md, revalidação 8f4dc36), copiado sem alteração do corpo.
# Nome original: test_cadastro_recusa_senha_igual_ao_nome
@pytest.mark.django_db
def test_cadastro_recusa_senha_igual_ao_nome(client):  # type: ignore[no-untyped-def]
    token = "token-revisor-similaridade"  # noqa: S105
    convite = ConviteFactory.create(token_hash=Convite.hash_do_token(token))
    senha = "NomeCompletoExclusivo9271"
    resposta = client.post(
        f"/convite/{token}/", {"nome": senha, "senha": senha, "confirmacao": senha}
    )
    assert resposta.status_code == 200
    assert not Conta.objects.filter(email_normalizado=convite.email_normalizado).exists()


def _codigos_do_campo_senha(resposta: Any) -> list[str]:
    return [str(e.code) for e in resposta.context["form"].errors.as_data().get("senha", [])]


def test_cadastro_recusa_senha_semelhante_ao_nome_com_mensagem(client: Client) -> None:
    # A-19 (a) e (b)
    convite, token = _convite(email_normalizado="bia@x.com")
    casos = [
        ("NomeCompletoExclusivo9271", "NomeCompletoExclusivo9271"),
        ("Marina Quintela Abreu", "MarinaQuintelaAbreu"),
    ]
    for nome, senha in casos:
        resposta = client.post(_rota(token), {"nome": nome, "senha": senha, "confirmacao": senha})
        assert resposta.status_code == 200
        assert "password_too_similar" in _codigos_do_campo_senha(resposta)
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert not Conta.objects.filter(email_normalizado="bia@x.com").exists()


def test_cadastro_recusa_senha_semelhante_ao_email(client: Client) -> None:  # A-20
    convite, token = _convite(email_normalizado="quintelaabreu2026@exemplo.com")
    resposta = client.post(
        _rota(token),
        {"nome": "Beatriz", "senha": "quintelaabreu2026", "confirmacao": "quintelaabreu2026"},
    )
    assert resposta.status_code == 200
    assert "password_too_similar" in _codigos_do_campo_senha(resposta)
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert not Conta.objects.filter(email_normalizado="quintelaabreu2026@exemplo.com").exists()


def test_servico_tambem_recusa_senha_semelhante_ao_nome() -> None:
    from django.core.exceptions import ValidationError

    convite, token = _convite(email_normalizado="bia@x.com")
    with pytest.raises(ValidationError):
        consumir_convite(
            token, "Marina Quintela Abreu", "MarinaQuintelaAbreu", metodo=MetodoCadastro.SENHA
        )
    convite.refresh_from_db()
    assert convite.consumido_em is None
