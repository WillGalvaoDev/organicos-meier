"""O backup externo diário do banco, cifrado, no R2 (E16-04).

Quatro etapas, sem transação aberta durante o despejo: `pg_dump` -> `age` (só com a chave pública,
a privada nunca fica no Fly.io) -> envio ao bucket de backups -> conferência do tamanho no bucket.
Só depois da conferência o `BackupExterno` é gravado. O despejo sem cifra nunca sai da máquina: ele
e o arquivo cifrado vivem num diretório temporário só do dono, apagado no fim com ou sem falha.

Os logs levam a chave do objeto, o tamanho, a duração, a etapa e a causa. Nunca a senha do banco, a
URL do banco, as credenciais do R2 nem a saída de erro das ferramentas (que pode citar dados).
"""

import hashlib
import logging
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections

from apps.nucleo.tempo import agora
from apps.operacao.models import BackupExterno

logger = logging.getLogger(__name__)

LIMITE_DE_CADA_FERRAMENTA = 30 * 60  # segundos


class TamanhoDivergente(Exception):
    """O tamanho do objeto no bucket não é o do arquivo cifrado enviado."""


class BackupFalhou(Exception):
    """Uma etapa do backup falhou. `etapa` é `configuracao`, `despejo`, `cifragem`, `envio` ou
    `conferencia`; `causa` é a classe do erro ou o código de saída da ferramenta."""

    def __init__(self, etapa: str, causa: str) -> None:
        self.etapa = etapa
        self.causa = causa
        super().__init__(f"Backup falhou na etapa {etapa}.")


def executar_ferramenta(args: Sequence[str], env: Mapping[str, str], timeout: int) -> None:
    """Roda uma ferramenta externa (`pg_dump` ou `age`). Substituível nos testes. A saída de erro
    é descartada: ela pode citar dados e não vai para o log."""
    subprocess.run(  # noqa: S603
        list(args),
        env=dict(env),
        timeout=timeout,
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _configuracao() -> dict[str, str]:
    valores = {
        "endpoint": settings.R2_ENDPOINT,
        "bucket": settings.R2_BUCKET_BACKUPS,
        "acesso": settings.R2_BACKUP_ACCESS_KEY_ID,
        "segredo": settings.R2_BACKUP_SECRET_ACCESS_KEY,
        "chave_publica": settings.BACKUP_CHAVE_PUBLICA_AGE,
    }
    if not all(valores.values()):
        raise ImproperlyConfigured("variáveis do backup externo ausentes")
    return valores


def _ambiente_do_banco() -> dict[str, str]:
    """As variáveis `PG*` do despejo, de `DATABASES["default"]`. A senha só vai aqui."""
    banco = connections["default"].settings_dict
    ambiente = {
        "PGHOST": str(banco.get("HOST") or "localhost"),
        "PGPORT": str(banco.get("PORT") or "5432"),
        "PGUSER": str(banco.get("USER") or ""),
        "PGPASSWORD": str(banco.get("PASSWORD") or ""),
        "PGDATABASE": str(banco["NAME"]),
        "PGSSLMODE": str(banco.get("OPTIONS", {}).get("sslmode", "prefer")),
    }
    if "PATH" in os.environ:
        ambiente["PATH"] = os.environ["PATH"]
    return ambiente


def _causa(erro: BaseException) -> str:
    if isinstance(erro, subprocess.CalledProcessError):
        return str(erro.returncode)
    if isinstance(erro, S3UploadFailedError) and (erro.__cause__ or erro.__context__):
        return type(erro.__cause__ or erro.__context__).__name__
    return type(erro).__name__


def _sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def identificador_da_execucao() -> str:
    """O identificador próprio de cada execução (128 bits aleatórios, 32 hexadecimais)."""
    return secrets.token_hex(16)


def _chave_do_objeto(instante: datetime, execucao: str) -> str:
    """`banco/<amb>/<AAAA>/<MM>/organicos-<amb>-<AAAAMMDD>T<HHMMSS>Z-<EXECUCAO>.dump.age`. O
    identificador da execução (E16-R03, regra 1-B) garante que duas execuções nunca escrevam no
    mesmo objeto, com ou sem trava: a invariante não depende da trava nem do `head_object`."""
    utc = instante.astimezone(UTC)
    ambiente = settings.AMBIENTE
    return (
        f"banco/{ambiente}/{utc:%Y}/{utc:%m}/"
        f"organicos-{ambiente}-{utc:%Y%m%d}T{utc:%H%M%S}Z-{execucao}.dump.age"
    )


def _cliente_s3(configuracao: dict[str, str]) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=configuracao["endpoint"],
        region_name="auto",
        aws_access_key_id=configuracao["acesso"],
        aws_secret_access_key=configuracao["segredo"],
        config=Config(signature_version="s3v4"),
    )


# Trava consultiva de sessão do Postgres, exclusiva do backup (E16-R03). Outras travas do projeto
# usam outras constantes (por exemplo, 7_151_013 no reenvio do pedido formal).
CHAVE_DA_TRAVA_DO_BACKUP = 7_160_416


class EmAndamento(Exception):
    """Outra execução do backup (tarefa ou comando) está com a trava."""


class ChaveExistente(Exception):
    """A chave do objeto já existe no banco ou no bucket; nada é substituído."""


@contextmanager
def _trava_do_backup() -> Iterator[None]:
    """A trava consultiva, sem transação aberta. Se a conexão cair, o Postgres a libera sozinho."""
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [CHAVE_DA_TRAVA_DO_BACKUP])
        obtida = cursor.fetchone()[0]
    if not obtida:
        raise EmAndamento
    try:
        yield
    finally:
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [CHAVE_DA_TRAVA_DO_BACKUP])
        except Exception as erro:  # a conexão caída já liberou a trava
            logger.error("backup externo: trava não liberada: erro=%s", type(erro).__name__)


def _objeto_existe(cliente: Any, bucket: str, chave: str) -> bool:
    """`head_object`: 404 é chave livre; outro erro do R2 é propagado."""
    try:
        cliente.head_object(Bucket=bucket, Key=chave)
    except ClientError as erro:
        codigo = str(erro.response.get("Error", {}).get("Code", ""))
        status = erro.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if codigo in ("404", "NoSuchKey", "NotFound") or status == 404:
            return False
        raise
    return True


def _reservar(cliente: Any, bucket: str, chave: str, *, so_o_bucket: bool = False) -> None:
    """Confere que a chave está livre (no banco e no bucket); senão, `BackupFalhou("reserva")`."""
    if not so_o_bucket and BackupExterno.objects.filter(chave=chave).exists():
        raise _falhar("reserva", ChaveExistente())
    try:
        existe = _objeto_existe(cliente, bucket, chave)
    except (ClientError, BotoCoreError) as erro:
        raise _falhar("reserva", erro) from erro
    if existe:
        raise _falhar("reserva", ChaveExistente())


def _falhar(etapa: str, erro: BaseException) -> BackupFalhou:
    falha = BackupFalhou(etapa, _causa(erro))
    logger.error("backup externo falhou: etapa=%s causa=%s", etapa, falha.causa)
    return falha


def fazer_backup_externo(instante: datetime) -> BackupExterno:
    """Faz o backup e devolve o registro. Qualquer falha levanta `BackupFalhou` sem gravar nada.

    Antes do despejo, a rotina reserva a chave (E16-R03): trava consultiva do Postgres (a tarefa e o
    comando manual não rodam juntos) e conferência de que a chave não existe no banco nem no bucket.
    Um objeto do bucket de backups nunca é substituído."""
    inicio = time.monotonic()
    try:
        configuracao = _configuracao()
    except ImproperlyConfigured as erro:
        raise _falhar("configuracao", erro) from erro
    chave = _chave_do_objeto(instante, identificador_da_execucao())
    cliente = _cliente_s3(configuracao)
    try:
        with _trava_do_backup():
            _reservar(cliente, configuracao["bucket"], chave)
            return _fazer_o_backup(instante, configuracao, chave, cliente, inicio)
    except EmAndamento as erro:
        raise _falhar("reserva", erro) from erro


def _fazer_o_backup(
    instante: datetime,
    configuracao: dict[str, str],
    chave: str,
    cliente: Any,
    inicio: float,
) -> BackupExterno:
    diretorio = Path(tempfile.mkdtemp(prefix="bkp-"))
    diretorio.chmod(0o700)
    try:
        despejo = diretorio / "banco.dump"
        cifrado = diretorio / "banco.dump.age"
        ambiente = _ambiente_do_banco()
        try:
            executar_ferramenta(
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    f"--file={despejo}",
                ],
                ambiente,
                LIMITE_DE_CADA_FERRAMENTA,
            )
        except Exception as erro:
            raise _falhar("despejo", erro) from erro
        try:
            executar_ferramenta(
                [
                    "age",
                    "--encrypt",
                    "--recipient",
                    configuracao["chave_publica"],
                    "--output",
                    str(cifrado),
                    str(despejo),
                ],
                {k: v for k, v in ambiente.items() if k == "PATH"},
                LIMITE_DE_CADA_FERRAMENTA,
            )
        except Exception as erro:
            raise _falhar("cifragem", erro) from erro
        despejo.unlink(missing_ok=True)  # o despejo em claro não precisa mais existir
        tamanho = cifrado.stat().st_size
        sha256 = _sha256(cifrado)
        # defesa a mais: a trava pode ter se perdido (queda da conexão) durante o despejo. A
        # invariante vem do identificador único da chave, não desta conferência (E16-R03, 1-B)
        _reservar(cliente, configuracao["bucket"], chave, so_o_bucket=True)
        try:
            cliente.upload_file(
                str(cifrado),
                configuracao["bucket"],
                chave,
                ExtraArgs={"Metadata": {"sha256": sha256}},
            )
        except (ClientError, BotoCoreError, S3UploadFailedError) as erro:
            raise _falhar("envio", erro) from erro
        try:
            no_bucket = cliente.head_object(Bucket=configuracao["bucket"], Key=chave)[
                "ContentLength"
            ]
        except (ClientError, BotoCoreError) as erro:
            raise _falhar("conferencia", erro) from erro
        if no_bucket != tamanho:
            _apagar_objeto_com_defeito(cliente, configuracao["bucket"], chave)
            raise _falhar("conferencia", TamanhoDivergente())
    finally:
        shutil.rmtree(diretorio, ignore_errors=True)
    registro = BackupExterno.objects.create(
        iniciado_em=instante,
        concluido_em=agora(),
        ambiente=settings.AMBIENTE,
        chave=chave,
        tamanho_bytes=tamanho,
        sha256=sha256,
    )
    logger.info(
        "backup externo concluído: chave=%s tamanho=%d duracao=%.1fs",
        chave,
        tamanho,
        time.monotonic() - inicio,
    )
    return registro


def _apagar_objeto_com_defeito(cliente: Any, bucket: str, chave: str) -> None:
    try:
        cliente.delete_object(Bucket=bucket, Key=chave)
    except (ClientError, BotoCoreError) as erro:
        logger.error("backup externo: objeto com defeito não apagado: erro=%s", type(erro).__name__)
