"""E02-09: avatar (acceptance A-10 a A-15)."""

from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from apps.contas.perfil import AvatarInvalido, processar_avatar
from tests.apoio import imagens
from tests.apoio.admin_fluxos import administrador_com_passkey, administrador_logado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db(transaction=True)

SENHA = "senha-forte-9271!"


@pytest.fixture(autouse=True)
def _midia_temporaria(settings: Any, tmp_path: Path) -> None:
    settings.MEDIA_ROOT = tmp_path


def _logado(email: str = "ana@x.com", **campos: Any) -> tuple[Client, Any]:
    conta = ContaFactory.create(email_normalizado=email, nome="Ana", **campos)
    conta.set_password(SENHA)
    conta.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": email, "password": SENHA})
    return cliente, conta


def _enviar(cliente: Client, conteudo: bytes, nome: str = "foto.png", **extras: Any) -> Any:
    arquivo = SimpleUploadedFile(nome, conteudo, content_type="image/png")
    return cliente.post("/perfil/", {"nome": "Ana", "avatar": arquivo, **extras})


def _arquivos(tmp_path: Path) -> list[Path]:
    return [p for p in tmp_path.rglob("*") if p.is_file()]


def test_png_valido_e_gravado_com_nome_uuid(tmp_path: Path) -> None:  # A-10
    cliente, conta = _logado()
    resposta = _enviar(cliente, imagens.png(100, 100), nome="minha foto original.png")
    assert resposta.status_code == 302
    conta.refresh_from_db()
    assert conta.avatar
    nome = Path(conta.avatar.name)
    assert nome.parent.name == "avatares"
    assert nome.suffix == ".png"
    assert len(nome.stem) == 36  # UUID
    assert "minha" not in conta.avatar.name
    (arquivo,) = _arquivos(tmp_path)
    with Image.open(arquivo) as imagem:
        assert imagem.format == "PNG"
        assert imagem.size == (100, 100)


@pytest.mark.parametrize(
    ("conteudo", "formato", "sufixo"),
    [(imagens.webp(), "WEBP", ".webp"), (imagens.jpeg_com_gps(), "JPEG", ".jpg")],
)
def test_webp_e_jpeg_sao_aceitos(
    tmp_path: Path, conteudo: bytes, formato: str, sufixo: str
) -> None:
    cliente, conta = _logado()
    _enviar(cliente, conteudo, nome="foto.bin")
    conta.refresh_from_db()
    assert conta.avatar.name.endswith(sufixo)
    (arquivo,) = _arquivos(tmp_path)
    with Image.open(arquivo) as imagem:
        assert imagem.format == formato


def test_jpeg_com_gps_e_gravado_sem_exif(tmp_path: Path) -> None:  # A-11
    original = Image.open(BytesIO(imagens.jpeg_com_gps()))
    assert 0x8825 in original.getexif()  # sanidade: a imagem de teste tem GPS
    cliente, _ = _logado()
    _enviar(cliente, imagens.jpeg_com_gps(), nome="gps.jpg")
    (arquivo,) = _arquivos(tmp_path)
    with Image.open(arquivo) as gravada:
        exif = gravada.getexif()
        assert 0x8825 not in exif
        assert 0x010F not in exif
        assert len(exif) == 0
    assert b"FabricanteTeste" not in arquivo.read_bytes()


def test_metadados_de_texto_do_png_sao_removidos(tmp_path: Path) -> None:
    cliente, _ = _logado()
    _enviar(cliente, imagens.png_com_texto_de_metadados())
    (arquivo,) = _arquivos(tmp_path)
    assert b"Fulana de Tal" not in arquivo.read_bytes()


@pytest.mark.parametrize(
    "conteudo",
    [
        b"isto e apenas texto, nao uma imagem",
        imagens.gif(),
        imagens.png_com_mais_de_2mb(),
        imagens.png(4097, 10),
        imagens.png(10, 4097),
    ],
    ids=["texto_com_extensao_png", "gif", "2mb_mais_1_byte", "4097_de_largura", "4097_de_altura"],
)
def test_arquivo_invalido_e_recusado_sem_gravar_nada(tmp_path: Path, conteudo: bytes) -> None:
    # A-12
    cliente, conta = _logado()
    resposta = _enviar(cliente, conteudo)
    assert resposta.status_code == 200
    assert resposta.context["form"].errors
    conta.refresh_from_db()
    assert not conta.avatar
    assert _arquivos(tmp_path) == []


def test_limites_exatos_sao_aceitos() -> None:
    arquivo = SimpleUploadedFile("a.png", imagens.png(4096, 8), content_type="image/png")
    assert processar_avatar(arquivo).size > 0


def test_servico_recusa_o_que_nao_e_imagem() -> None:
    with pytest.raises(AvatarInvalido):
        processar_avatar(SimpleUploadedFile("a.png", b"texto", content_type="image/png"))


def test_trocar_e_remover_apagam_o_arquivo_anterior(tmp_path: Path) -> None:  # A-13
    cliente, conta = _logado()
    _enviar(cliente, imagens.png(50, 50))
    conta.refresh_from_db()
    primeiro = conta.avatar.name
    assert len(_arquivos(tmp_path)) == 1

    _enviar(cliente, imagens.png(60, 60))
    conta.refresh_from_db()
    assert conta.avatar.name != primeiro
    arquivos = _arquivos(tmp_path)
    assert len(arquivos) == 1
    assert not (tmp_path / primeiro).exists()

    resposta = cliente.post("/perfil/", {"nome": "Ana", "remover_avatar": "on"})
    assert resposta.status_code == 302
    conta.refresh_from_db()
    assert not conta.avatar
    assert _arquivos(tmp_path) == []


def test_envio_recusado_nao_apaga_o_avatar_atual(tmp_path: Path) -> None:
    cliente, conta = _logado()
    _enviar(cliente, imagens.png(50, 50))
    _enviar(cliente, b"nao e imagem")
    conta.refresh_from_db()
    assert conta.avatar
    assert len(_arquivos(tmp_path)) == 1


def test_dono_e_administrador_veem_o_avatar(client: Client, webauthn: Any) -> None:  # A-14
    cliente, conta = _logado()
    _enviar(cliente, imagens.png(40, 40))
    conta.refresh_from_db()
    rota = f"/perfil/avatar/{conta.pk}/"

    dono = cliente.get(rota)
    assert dono.status_code == 200
    assert dono["Content-Type"] == "image/png"
    conteudo = b"".join(dono.streaming_content)  # type: ignore[attr-defined]
    assert Image.open(BytesIO(conteudo)).size == (40, 40)

    administrador_logado(client)
    visto_pelo_admin = client.get(rota)
    assert visto_pelo_admin.status_code == 200
    assert visto_pelo_admin["Content-Type"] == "image/png"


def test_outros_nao_veem_o_avatar(webauthn: Any) -> None:  # A-15
    dono, conta = _logado()
    _enviar(dono, imagens.png(40, 40))
    conta.refresh_from_db()
    rota = f"/perfil/avatar/{conta.pk}/"

    outro, _ = _logado("bia@x.com")
    assert outro.get(rota).status_code == 404
    fornecedor, _ = _logado("forn@x.com", fornecedor=True)
    assert fornecedor.get(rota).status_code == 404
    anonimo = Client().get(rota)
    assert anonimo.status_code == 302
    assert anonimo["Location"].startswith("/entrar/")


def test_avatar_inexistente_ou_sem_foto_da_404() -> None:
    cliente, conta = _logado()
    assert cliente.get(f"/perfil/avatar/{conta.pk}/").status_code == 404
    assert cliente.get("/perfil/avatar/999999/").status_code == 404


def test_administrador_sem_prova_de_passkey_nao_ve_avatar_de_outra_conta(
    webauthn: Any,
) -> None:
    dono, conta = _logado()
    _enviar(dono, imagens.png(40, 40))
    conta.refresh_from_db()
    admin, _ = administrador_com_passkey(Client())
    sem_prova = Client()
    sem_prova.force_login(admin)  # sessão sem registro de autenticação por passkey
    assert sem_prova.get(f"/perfil/avatar/{conta.pk}/").status_code == 404
