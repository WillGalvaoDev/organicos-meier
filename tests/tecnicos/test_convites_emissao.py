"""E02-04: emissão de convites pela tela e pelo serviço (acceptance A-1 a A-10 e A-17 a A-19)."""

import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import Client

from apps.contas.convites import ConviteInvalido, EmailBanidoErro, emitir_convite
from apps.contas.emails import EmailInvalido
from apps.contas.models import Conta, Convite, EmailBanido, EmailEmUso
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = pytest.mark.django_db(transaction=True)

T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)
ROTA = "/administracao/convites/"


@pytest.fixture
def admin(client: Client, webauthn: Any, relogio: Any) -> Conta:
    conta = administrador_logado(client)
    relogio.congelar(T)
    return conta


def _emitir(client: Client, email: str, papel: str = "comprador", fornecedor: Any = "") -> Any:
    return client.post(ROTA, {"email": email, "papel": papel, "fornecedor": fornecedor})


def _token_do_ultimo_email() -> str:
    achados = re.findall(r"/convite/([A-Za-z0-9_-]+)/", str(mail.outbox[-1].body))
    assert achados, mail.outbox[-1].body
    return str(achados[0])


def test_emissao_de_comprador_grava_convite_com_validade_de_24h(
    client: Client, admin: Conta
) -> None:  # A-1
    resposta = _emitir(client, " Bia@X.com")
    assert resposta.status_code == 302
    convite = Convite.objects.get()
    assert convite.email_normalizado == "bia@x.com"
    assert convite.papel == "comprador"
    assert convite.fornecedor is None
    assert convite.emitido_em == T
    assert convite.expira_em == T + timedelta(hours=24)
    assert convite.consumido_em is None
    assert convite.conta_criada is None
    assert convite.emitido_por == admin


def test_email_do_convite_tem_link_finalidade_e_expiracao_em_sao_paulo(
    client: Client, admin: Conta
) -> None:  # A-2
    _emitir(client, " Bia@X.com")
    assert len(mail.outbox) == 1
    mensagem = mail.outbox[0]
    assert mensagem.to == ["bia@x.com"]
    corpo = str(mensagem.body)
    assert re.search(r"http://testserver/convite/[A-Za-z0-9_-]+/", corpo)
    assert "comprador" in corpo.lower()
    assert "15/10/2026 às 12:00" in corpo  # T + 24h = 15/10 15:00 UTC = 12:00 em São Paulo
    assert mensagem.subject


def test_token_so_existe_como_hash(client: Client, admin: Conta) -> None:  # A-3
    _emitir(client, "bia@x.com")
    token = _token_do_ultimo_email()
    convite = Convite.objects.get()
    assert convite.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert convite.token_hash == Convite.hash_do_token(token)
    for campo in convite._meta.concrete_fields:
        assert token not in str(getattr(convite, campo.attname))
    for entrada in EntradaAuditoria.objects.all():
        assert token not in str(entrada.alteracoes)
        assert token not in entrada.motivo


def test_tokens_sao_diferentes_e_longos(client: Client, admin: Conta) -> None:  # A-4
    _emitir(client, "bia@x.com")
    primeiro = _token_do_ultimo_email()
    _emitir(client, "caio@x.com")
    segundo = _token_do_ultimo_email()
    assert primeiro != segundo
    assert len(primeiro) >= 43
    assert len(segundo) >= 43


def test_convite_de_fornecedor_vincula_o_fornecedor_e_cita_o_nome(
    client: Client, admin: Conta
) -> None:  # A-5
    fornecedor = FornecedorFactory.create(nome="Horta do Zé")
    resposta = _emitir(client, "ze@x.com", "fornecedor", fornecedor.pk)
    assert resposta.status_code == 302
    convite = Convite.objects.get()
    assert convite.papel == "fornecedor"
    assert convite.fornecedor == fornecedor
    assert "Horta do Zé" in str(mail.outbox[0].body)


@pytest.mark.parametrize(
    "dados",
    [
        {"papel": "fornecedor", "fornecedor": ""},
        {"papel": "comprador", "fornecedor": "FORNECEDOR"},
        {"papel": "fornecedor", "fornecedor": "999999"},
        {"papel": "administrador", "fornecedor": ""},
        {"papel": "gerente", "fornecedor": ""},
    ],
    ids=[
        "fornecedor_sem_fornecedor",
        "comprador_com_fornecedor",
        "fornecedor_inexistente",
        "papel_administrador",
        "papel_inexistente",
    ],
)
def test_tela_recusa_combinacoes_invalidas(
    client: Client, admin: Conta, dados: dict[str, str]
) -> None:  # A-6
    fornecedor = FornecedorFactory.create()
    if dados["fornecedor"] == "FORNECEDOR":
        dados = {**dados, "fornecedor": str(fornecedor.pk)}
    resposta = client.post(ROTA, {"email": "bia@x.com", **dados})
    assert resposta.status_code == 200
    assert Convite.objects.count() == 0
    assert len(mail.outbox) == 0


def test_tela_recusa_email_invalido(client: Client, admin: Conta) -> None:
    resposta = _emitir(client, "lixo")
    assert resposta.status_code == 200
    assert Convite.objects.count() == 0


@pytest.mark.acceptance
@pytest.mark.parametrize("situacao", ["ativa", "suspensa", "removida"])
@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_emissao_recusa_email_ja_em_uso_por_qualquer_conta(
    admin: Conta, fornecedor: bool, situacao: str
) -> None:  # A-7, cenário 80
    ContaFactory.create(
        email_normalizado="ana@exemplo.com", situacao=situacao, fornecedor=fornecedor
    )
    with pytest.raises(EmailEmUso):
        emitir_convite(admin, "  Ana@Exemplo.com ", "comprador")
    assert Convite.objects.count() == 0
    assert len(mail.outbox) == 0


def test_tela_mostra_recusa_de_email_em_uso(client: Client, admin: Conta) -> None:
    ContaFactory.create(email_normalizado="ana@exemplo.com")
    resposta = _emitir(client, " ANA@exemplo.com")
    assert resposta.status_code == 200
    assert "já está em uso" in resposta.content.decode()
    assert Convite.objects.count() == 0


def test_emissao_recusa_email_banido(admin: Conta) -> None:  # A-8
    EmailBanido.objects.create(email_normalizado="ana@x.com", banido_por=admin)
    with pytest.raises(EmailBanidoErro):
        emitir_convite(admin, "ANA@x.com", "comprador")
    assert Convite.objects.count() == 0
    assert len(mail.outbox) == 0


def test_emissao_para_alias_de_email_banido_funciona(admin: Conta) -> None:  # A-9, cenário 59
    EmailBanido.objects.create(email_normalizado="ana@x.com", banido_por=admin)
    emitir_convite(admin, "ana+1@x.com", "comprador")
    assert Convite.objects.filter(email_normalizado="ana+1@x.com").exists()


def test_convites_repetidos_para_o_mesmo_email_sao_permitidos(admin: Conta) -> None:  # A-10
    primeiro = emitir_convite(admin, "bia@x.com", "comprador")
    segundo = emitir_convite(admin, "bia@x.com", "comprador")
    assert primeiro.pk != segundo.pk
    assert primeiro.token_hash != segundo.token_hash
    assert Convite.objects.filter(email_normalizado="bia@x.com").count() == 2


def test_emissao_recusa_email_invalido_e_combinacoes_no_servico(admin: Conta) -> None:
    fornecedor = FornecedorFactory.create()
    with pytest.raises(EmailInvalido):
        emitir_convite(admin, "lixo", "comprador")
    with pytest.raises(ConviteInvalido):
        emitir_convite(admin, "a@x.com", "administrador")
    with pytest.raises(ConviteInvalido):
        emitir_convite(admin, "a@x.com", "fornecedor")
    with pytest.raises(ConviteInvalido):
        emitir_convite(admin, "a@x.com", "comprador", fornecedor)
    assert Convite.objects.count() == 0


def test_auditoria_da_emissao_nao_tem_email_nem_token(client: Client, admin: Conta) -> None:  # A-17
    fornecedor = FornecedorFactory.create()
    _emitir(client, "ze@x.com", "fornecedor", fornecedor.pk)
    convite = Convite.objects.get()
    entrada = EntradaAuditoria.objects.get(acao="convite.emitir")
    assert entrada.autor_tipo == "usuario"
    assert entrada.autor_id == str(admin.pk)
    assert entrada.alteracoes == {
        "convite": convite.pk,
        "papel": "fornecedor",
        "fornecedor": fornecedor.pk,
    }
    assert "ze@x.com" not in str(entrada.alteracoes)
    assert entrada.objeto_id == str(convite.pk)
    assert _token_do_ultimo_email() not in str(entrada.alteracoes)


def test_transacao_desfeita_nao_deixa_convite_nem_email(
    admin: Conta, django_capture_on_commit_callbacks: Any
) -> None:  # A-18

    def emitir_e_falhar() -> None:
        with transaction.atomic():
            emitir_convite(admin, "bia@x.com", "comprador")
            raise RuntimeError("falha depois de emitir")

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(RuntimeError):
            emitir_e_falhar()
    assert callbacks == []
    assert len(mail.outbox) == 0
    assert Convite.objects.count() == 0
    assert EntradaAuditoria.objects.filter(acao="convite.emitir").count() == 0


def test_falha_no_envio_mantem_o_convite_e_nao_vaza_dados(
    client: Client, admin: Conta, settings: Any, caplog: pytest.LogCaptureFixture
) -> None:  # A-19
    settings.EMAIL_BACKEND = "tests.apoio.email_falho.BackendQueFalha"
    with caplog.at_level(logging.DEBUG):
        resposta = _emitir(client, "bia@x.com")
        seguida = client.get(ROTA)
    assert resposta.status_code == 302
    assert Convite.objects.count() == 1
    assert "Convite criado, mas o e-mail não pôde ser enviado. Emita um novo convite." in (
        seguida.content.decode()
    )
    assert "bia@x.com" not in caplog.text
    assert "bia@x.com" not in caplog.text.lower()
    for convite in Convite.objects.all():
        assert convite.token_hash not in caplog.text


def test_emissao_sem_requisicao_usa_a_origem_configurada(admin: Conta, settings: Any) -> None:
    settings.ORIGEM_PUBLICA = "https://organicosmeier.exemplo.com.br"
    emitir_convite(admin, "bia@x.com", "comprador")
    assert "https://organicosmeier.exemplo.com.br/convite/" in str(mail.outbox[0].body)


def test_modelo_nao_aceita_papel_administrador_na_validacao(admin: Conta) -> None:
    convite = Convite(
        email_normalizado="a@x.com",
        papel="administrador",
        token_hash="0" * 64,
        emitido_por=admin,
        emitido_em=T,
        expira_em=T + timedelta(hours=24),
    )
    with pytest.raises(ValidationError):
        convite.full_clean()
