"""E16-04: o backup com as ferramentas reais (acceptance A-15).

Exige `pg_dump` 17, `pg_restore`, `age` e `age-keygen`. No CI, `EXIGIR_FERRAMENTAS_DE_BACKUP=1`
faz a ausência delas falhar o teste; fora do CI, a ausência pula o teste com o motivo.
"""

import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws

from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora
from tests.fabricas import RodadaFactory

pytestmark = pytest.mark.django_db(transaction=True)

FERRAMENTAS = ("pg_dump", "pg_restore", "age", "age-keygen")
ENDPOINT = "https://conta-de-teste.r2.cloudflarestorage.com"
BUCKET = "backups-teste"
TEXTO_DA_AUDITORIA = "TEXTO-UNICO-DA-AUDITORIA-DO-TESTE"


@pytest.fixture(autouse=True)
def _ferramentas_reais() -> None:
    faltando = [f for f in FERRAMENTAS if shutil.which(f) is None]
    if not faltando:
        return
    motivo = f"ferramentas de backup ausentes: {', '.join(faltando)}"
    if os.environ.get("EXIGIR_FERRAMENTAS_DE_BACKUP") == "1":
        pytest.fail(motivo)
    pytest.skip(motivo)


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch, settings: Any) -> Iterator[Any]:
    monkeypatch.setenv("MOTO_S3_CUSTOM_ENDPOINTS", ENDPOINT)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIABACKUPTESTE0000")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "segredo-do-backup-de-teste")
    with mock_aws():
        s3 = boto3.client("s3", endpoint_url=ENDPOINT, region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        yield s3


def test_o_backup_real_decifra_e_restaura(bucket: Any, settings: Any, tmp_path: Path) -> None:
    from apps.operacao.backup import fazer_backup_externo

    chave_privada = tmp_path / "chave.txt"
    subprocess.run(["age-keygen", "-o", str(chave_privada)], check=True, capture_output=True)  # noqa: S603, S607
    publica = re.search(r"public key: (age1\w+)", chave_privada.read_text(), re.IGNORECASE)
    assert publica

    rodada = RodadaFactory.create()
    registrar_auditoria(SISTEMA, "teste.backup", rodada, {"texto": TEXTO_DA_AUDITORIA})

    settings.AMBIENTE = "homologacao"
    settings.R2_ENDPOINT = ENDPOINT
    settings.R2_BUCKET_BACKUPS = BUCKET
    settings.R2_BACKUP_ACCESS_KEY_ID = "AKIABACKUPTESTE0000"
    settings.R2_BACKUP_SECRET_ACCESS_KEY = "segredo-do-backup-de-teste"  # noqa: S105
    settings.BACKUP_CHAVE_PUBLICA_AGE = publica.group(1)

    registro = fazer_backup_externo(agora())

    cifrado = tmp_path / "backup.dump.age"
    bucket.download_file(BUCKET, registro.chave, str(cifrado))
    assert cifrado.stat().st_size == registro.tamanho_bytes
    assert TEXTO_DA_AUDITORIA.encode() not in cifrado.read_bytes()

    despejo = tmp_path / "backup.dump"
    subprocess.run(  # noqa: S603
        ["age", "--decrypt", "-i", str(chave_privada), "-o", str(despejo), str(cifrado)],  # noqa: S607
        check=True,
        capture_output=True,
    )
    lista = subprocess.run(  # noqa: S603
        ["pg_restore", "--list", str(despejo)],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "rodadas_rodada" in lista
    assert "nucleo_entradaauditoria" in lista
