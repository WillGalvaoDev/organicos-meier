"""E16-02: arquivos enviados no Cloudflare R2 (acceptance A-4 a A-14).

O backend real do `django-storages` roda contra o S3 simulado pelo `moto`, sem rede nem
credenciais. A configuração é a que `config.settings.prod` monta (`config.armazenamento`).
"""

import logging
import re
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from moto import mock_aws
from PIL import Image

from apps.financeiro.models import ConfirmacaoDeDevolucaoExcepcional
from config.armazenamento import storage_do_r2
from tests.apoio import imagens
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.devolucoes import Arranjo, entrar_de_novo, levar_a_elegivel, montar_tela
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

BUCKET = "arquivos-teste"
ENDPOINT = "https://conta-de-teste.r2.cloudflarestorage.com"
CHAVE_DE_ACESSO = "AKIATESTEDOR2000000"
SEGREDO_DE_ACESSO = "segredo-do-r2-so-para-os-testes"
SENHA = "senha-forte-9271!"
PDF = b"%PDF-1.4\n%comprovante da Maria\n"
MENSAGEM = "Não foi possível enviar o arquivo. Tente de novo."
BASE = "/administracao/financeiro/devolucoes/"


@pytest.fixture
def r2(settings: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    """O arranjo R2S: o bucket `arquivos-teste` simulado e o armazenamento de produção."""
    monkeypatch.setenv("MOTO_S3_CUSTOM_ENDPOINTS", ENDPOINT)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", CHAVE_DE_ACESSO)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", SEGREDO_DE_ACESSO)
    settings.MEDIA_ROOT = tmp_path  # nada deve parar aqui: confere-se mais adiante
    with mock_aws():
        s3 = boto3.client(
            "s3",
            endpoint_url=ENDPOINT,
            region_name="us-east-1",
            aws_access_key_id=CHAVE_DE_ACESSO,
            aws_secret_access_key=SEGREDO_DE_ACESSO,
        )
        s3.create_bucket(Bucket=BUCKET)
        settings.STORAGES = {
            **settings.STORAGES,
            "default": storage_do_r2(ENDPOINT, BUCKET, CHAVE_DE_ACESSO, SEGREDO_DE_ACESSO),
        }
        yield s3
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def _chaves(s3: Any, prefixo: str = "") -> list[str]:
    resposta = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefixo)
    return [o["Key"] for o in resposta.get("Contents", [])]


def _logado(email: str, nome: str = "Ana") -> tuple[Client, Any]:
    conta = ContaFactory.create(email_normalizado=email, nome=nome)
    conta.set_password(SENHA)
    conta.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": email, "password": SENHA})
    return cliente, conta


def _enviar(cliente: Client, conteudo: bytes, nome: str = "foto.png") -> Any:
    arquivo = SimpleUploadedFile(nome, conteudo, content_type="image/png")
    return cliente.post("/perfil/", {"nome": "Ana", "avatar": arquivo})


def _corpo(resposta: Any) -> bytes:
    return b"".join(resposta.streaming_content)


def test_avatar_vai_para_o_bucket_privado(r2: Any) -> None:  # A-4
    cliente, conta = _logado("ana@x.com")
    assert _enviar(cliente, imagens.png(40, 40)).status_code == 302
    conta.refresh_from_db()
    (chave,) = _chaves(r2)
    assert chave.startswith("avatares/")
    assert chave == conta.avatar.name
    concessoes = r2.get_object_acl(Bucket=BUCKET, Key=chave)["Grants"]
    assert not [g for g in concessoes if "AllUsers" in g.get("Grantee", {}).get("URI", "")]
    from django.core.files.storage import default_storage

    assert default_storage.default_acl is None  # type: ignore[attr-defined]
    assert default_storage.querystring_auth is True  # type: ignore[attr-defined]


def test_dono_e_administrador_leem_o_avatar(r2: Any, client: Client, webauthn: Any) -> None:  # A-5
    cliente, conta = _logado("ana@x.com")
    _enviar(cliente, imagens.png(40, 40))
    conta.refresh_from_db()
    rota = f"/perfil/avatar/{conta.pk}/"
    dono = cliente.get(rota)
    assert dono.status_code == 200
    assert dono["Cache-Control"] == "private, no-store"
    assert Image.open(BytesIO(_corpo(dono))).size == (40, 40)
    admin, credencial = administrador_com_passkey(client)
    entrar_de_novo(client, credencial, admin)
    visto = client.get(rota)
    assert visto.status_code == 200
    assert visto["Cache-Control"] == "private, no-store"
    assert Image.open(BytesIO(_corpo(visto))).size == (40, 40)


def test_outros_e_administrador_sem_passkey_recebem_404(
    r2: Any, client: Client, webauthn: Any
) -> None:  # A-6
    cliente, conta = _logado("ana@x.com")
    _enviar(cliente, imagens.png(40, 40))
    conta.refresh_from_db()
    rota = f"/perfil/avatar/{conta.pk}/"
    outro, _ = _logado("bia@x.com", "Bia")
    assert outro.get(rota).status_code == 404
    admin, _ = administrador_com_passkey(Client())
    sem_prova = Client()
    sem_prova.force_login(admin)
    assert sem_prova.get(rota).status_code == 404


def test_dois_envios_com_o_mesmo_nome_nao_se_sobrescrevem(r2: Any) -> None:  # A-7
    ana, conta_ana = _logado("ana@x.com")
    bia, conta_bia = _logado("bia@x.com", "Bia")
    _enviar(ana, imagens.png(30, 30), nome="foto.png")
    _enviar(bia, imagens.png(50, 50), nome="foto.png")
    conta_ana.refresh_from_db()
    conta_bia.refresh_from_db()
    assert len(set(_chaves(r2))) == 2
    assert conta_ana.avatar.name != conta_bia.avatar.name
    assert Image.open(BytesIO(_corpo(ana.get(f"/perfil/avatar/{conta_ana.pk}/")))).size == (30, 30)
    assert Image.open(BytesIO(_corpo(bia.get(f"/perfil/avatar/{conta_bia.pk}/")))).size == (50, 50)


@pytest.fixture
def montada(
    r2: Any, client: Client, webauthn: Any, relogio: RelogioControlado, simulador_pagamentos: Any
) -> tuple[Arranjo, bytes]:
    return montar_tela(client, simulador_pagamentos, relogio)


def _dados(nome: str = "Comprovante Maria.pdf") -> dict[str, Any]:
    return {
        "meio": "pix",
        "identificacao": "E2E-123",
        "justificativa": "Pix feito direto ao comprador",
        "comprovante": SimpleUploadedFile(nome, PDF, content_type="application/pdf"),
    }


def _confirmar(client: Client, a: Arranjo, credencial: bytes) -> Any:
    levar_a_elegivel(a)
    entrar_de_novo(client, credencial, a.admin)
    return client.post(f"{BASE}{a.o1.pk}/excepcional/", _dados())


def test_comprovante_no_bucket_com_chave_sem_nome_pessoal(
    r2: Any, client: Client, montada: tuple[Arranjo, bytes]
) -> None:  # A-8 e A-9
    a, credencial = montada
    assert _confirmar(client, a, credencial).status_code == 302
    (chave,) = _chaves(r2, "comprovantes/")
    assert "Maria" not in chave
    baixado = client.get(f"{BASE}{a.o1.pk}/comprovante/")
    assert baixado.status_code == 200
    assert "Comprovante Maria.pdf" in baixado["Content-Disposition"]
    assert baixado["Content-Disposition"].startswith("attachment")
    assert baixado["Content-Type"] == "application/pdf"
    assert _corpo(baixado) == PDF
    cliente = Client()
    cliente.force_login(a.comprador)
    assert cliente.get(f"{BASE}{a.o1.pk}/comprovante/").status_code == 403


def test_objeto_ausente_no_bucket_da_404(
    r2: Any, client: Client, montada: tuple[Arranjo, bytes]
) -> None:  # A-10
    a, credencial = montada
    _confirmar(client, a, credencial)
    for chave in _chaves(r2, "comprovantes/"):
        r2.delete_object(Bucket=BUCKET, Key=chave)
    assert client.get(f"{BASE}{a.o1.pk}/comprovante/").status_code == 404
    cliente, conta = _logado("ana@x.com")
    _enviar(cliente, imagens.png(40, 40))
    conta.refresh_from_db()
    r2.delete_object(Bucket=BUCKET, Key=conta.avatar.name)
    assert cliente.get(f"/perfil/avatar/{conta.pk}/").status_code == 404


@pytest.fixture
def upload_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `put_object` do S3 passa a falhar com `ClientError`; as leituras continuam."""
    import botocore.client

    original = botocore.client.BaseClient._make_api_call

    def falha(self: Any, operacao: str, parametros: Any) -> Any:
        if operacao in ("PutObject", "CreateMultipartUpload", "UploadPart"):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "negado"}}, operacao)
        return original(self, operacao, parametros)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", falha)


def test_falha_no_envio_do_avatar(
    r2: Any, upload_falha: None, caplog: pytest.LogCaptureFixture
) -> None:  # A-11 e A-13
    cliente, conta = _logado("ana@x.com")
    with caplog.at_level(logging.INFO):
        resposta = _enviar(cliente, imagens.png(40, 40), nome="Foto da Ana.png")
    assert resposta.status_code == 503
    assert MENSAGEM in resposta.content.decode()
    conta.refresh_from_db()
    assert not conta.avatar
    assert _chaves(r2) == []
    _sem_dado_sensivel(caplog, "Foto da Ana")


def test_falha_no_envio_do_comprovante(
    r2: Any,
    upload_falha: None,
    client: Client,
    montada: tuple[Arranjo, bytes],
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-12 e A-13
    from apps.financeiro.models import MovimentoFinanceiro
    from apps.nucleo.auditoria import EntradaAuditoria

    a, credencial = montada
    parcela = levar_a_elegivel(a)
    movimentos = MovimentoFinanceiro.objects.count()
    auditorias = EntradaAuditoria.objects.count()
    entrar_de_novo(client, credencial, a.admin)
    with caplog.at_level(logging.INFO):
        resposta = client.post(f"{BASE}{a.o1.pk}/excepcional/", _dados())
    assert resposta.status_code == 503
    assert MENSAGEM in resposta.content.decode()
    assert ConfirmacaoDeDevolucaoExcepcional.objects.count() == 0
    assert MovimentoFinanceiro.objects.count() == movimentos
    assert EntradaAuditoria.objects.filter(acao__contains="devolucao_excepcional").count() == 0
    assert EntradaAuditoria.objects.count() == auditorias
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"  # a obrigação segue devida
    _sem_dado_sensivel(caplog, "Comprovante Maria")


def _sem_dado_sensivel(caplog: pytest.LogCaptureFixture, nome_do_arquivo: str) -> None:
    falhas = [r for r in caplog.records if "ClientError" in r.getMessage()]
    assert falhas, "esperava um log da falha do armazenamento"
    for registro in caplog.records:
        mensagem = registro.getMessage()
        assert CHAVE_DE_ACESSO not in mensagem
        assert SEGREDO_DE_ACESSO not in mensagem
        assert "X-Amz-Signature" not in mensagem
        assert nome_do_arquivo not in mensagem


def test_nenhum_template_ou_codigo_usa_url_dos_arquivos() -> None:  # A-14
    raiz = Path(__file__).resolve().parents[2]
    padrao = re.compile(r"\.(avatar|comprovante)\.url\b")
    achados = [
        str(caminho.relative_to(raiz))
        for pasta in ("apps", "templates")
        for caminho in (raiz / pasta).rglob("*")
        if caminho.suffix in (".py", ".html") and padrao.search(caminho.read_text("utf-8"))
    ]
    assert achados == []
