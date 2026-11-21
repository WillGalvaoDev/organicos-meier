"""E16-04: backup externo diário, cifrado, no R2 (acceptance A-1 a A-12 e A-14).

As ferramentas externas (`pg_dump` e `age`) são substituídas por um dublê que grava o que recebeu
ou falha sob comando; o R2 é o S3 simulado pelo `moto`. O A-15 (ferramentas reais) fica em
`test_backup_externo_ferramentas.py`.
"""

import hashlib
import logging
import re
import subprocess
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from moto import mock_aws

from apps.nucleo.so_insercao import RegistroImutavel
from apps.operacao.backup import identificador_da_execucao as IDENTIFICADOR_REAL
from apps.operacao.models import BackupExterno
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

I = datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC)  # noqa: E741
ENDPOINT = "https://conta-de-teste.r2.cloudflarestorage.com"
BUCKET = "backups-teste"
CHAVE_DE_ACESSO = "AKIABACKUPTESTE0000"
SEGREDO_DE_ACESSO = "segredo-do-r2-de-backup-de-teste"
CHAVE_PUBLICA = "age1chavepublicadetestequenaoevalidaparaousoreal0000000000000000000000"
ID_FIXO = "0123456789abcdef0123456789abcdef"
PREFIXO_DA_CHAVE = "banco/homologacao/2026/11/organicos-homologacao-20261120T060000Z"
CHAVE_DO_OBJETO = f"{PREFIXO_DA_CHAVE}-{ID_FIXO}.dump.age"
EMAIL_NO_ERRO = "ana@exemplo.com"
SENHA_DO_BANCO = "senha-unica-do-banco-so-para-este-teste"
CONTEUDO_DO_DESPEJO = b"DESPEJO-EM-CLARO"
CONTEUDO_CIFRADO = b"CONTEUDO-CIFRADO-PELO-DUBLE"
CONTEUDO_ORIGINAL = CONTEUDO_CIFRADO


class Ferramentas:
    """O dublê de `executar_ferramenta`: grava as chamadas e falha sob comando."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[list[str], dict[str, str], int]] = []
        self.codigo_do_despejo = 0
        self.cifragem_esgota = False

    def __call__(self, args: Sequence[str], env: Mapping[str, str], timeout: int) -> None:
        self.chamadas.append((list(args), dict(env), timeout))
        if args[0] == "pg_dump":
            if self.codigo_do_despejo:
                raise subprocess.CalledProcessError(
                    self.codigo_do_despejo, list(args), stderr=EMAIL_NO_ERRO.encode()
                )
            destino = next(a for a in args if a.startswith("--file=")).split("=", 1)[1]
            Path(destino).write_bytes(CONTEUDO_DO_DESPEJO)
        elif args[0] == "age":
            if self.cifragem_esgota:
                raise subprocess.TimeoutExpired(list(args), timeout, stderr=EMAIL_NO_ERRO.encode())
            destino = args[args.index("--output") + 1]
            Path(destino).write_bytes(CONTEUDO_CIFRADO)

    def argumentos(self, programa: str) -> list[str]:
        return next(a for a, _env, _t in self.chamadas if a[0] == programa)

    def ambiente(self, programa: str) -> dict[str, str]:
        return next(e for a, e, _t in self.chamadas if a[0] == programa)

    def arquivos_temporarios(self) -> list[Path]:
        """Os arquivos que as ferramentas receberam como saída e a entrada da cifragem."""
        caminhos = []
        for args, _env, _t in self.chamadas:
            for arg in args:
                if arg.startswith("--file="):
                    caminhos.append(Path(arg.split("=", 1)[1]))
            if args[0] == "age":
                caminhos.append(Path(args[args.index("--output") + 1]))
                caminhos.append(Path(args[-1]))
        return caminhos


@pytest.fixture
def ferramentas(monkeypatch: pytest.MonkeyPatch) -> Ferramentas:
    from apps.operacao import backup

    falsas = Ferramentas()
    monkeypatch.setattr(backup, "executar_ferramenta", falsas)
    return falsas


@pytest.fixture
def ab(settings: Any, monkeypatch: pytest.MonkeyPatch, relogio: RelogioControlado) -> Iterator[Any]:
    """O arranjo AB: o relógio em `I`, o ambiente de homologação e o bucket `backups-teste`."""
    monkeypatch.setenv("MOTO_S3_CUSTOM_ENDPOINTS", ENDPOINT)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", CHAVE_DE_ACESSO)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", SEGREDO_DE_ACESSO)
    from apps.operacao import backup

    monkeypatch.setattr(backup, "identificador_da_execucao", lambda: ID_FIXO)
    relogio.congelar(I)
    settings.AMBIENTE = "homologacao"
    settings.R2_ENDPOINT = ENDPOINT
    settings.R2_BUCKET_BACKUPS = BUCKET
    settings.R2_BACKUP_ACCESS_KEY_ID = CHAVE_DE_ACESSO
    settings.R2_BACKUP_SECRET_ACCESS_KEY = SEGREDO_DE_ACESSO
    settings.BACKUP_CHAVE_PUBLICA_AGE = CHAVE_PUBLICA
    with mock_aws():
        s3 = boto3.client(
            "s3",
            endpoint_url=ENDPOINT,
            region_name="us-east-1",
            aws_access_key_id=CHAVE_DE_ACESSO,
            aws_secret_access_key=SEGREDO_DE_ACESSO,
        )
        s3.create_bucket(Bucket=BUCKET)
        yield s3


@pytest.fixture
def senha_unica(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma senha que não coincide com nenhum outro texto (a do banco de teste é curta e comum).
    Só para os testes de vazamento: com ela, nenhuma conexão nova com o banco funciona."""
    monkeypatch.setitem(connection.settings_dict, "PASSWORD", SENHA_DO_BANCO)


def _chaves(s3: Any) -> list[str]:
    return [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])]


def _fazer(instante: datetime = I) -> Any:
    from apps.operacao.backup import fazer_backup_externo

    return fazer_backup_externo(instante)


def _soltar_o_identificador(monkeypatch: pytest.MonkeyPatch) -> None:
    """Volta ao identificador aleatório de verdade (o arranjo AB o força)."""
    from apps.operacao import backup

    monkeypatch.setattr(backup, "identificador_da_execucao", IDENTIFICADOR_REAL)


def test_backup_completo(
    ab: Any, ferramentas: Ferramentas, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-1
    _soltar_o_identificador(monkeypatch)
    registro = _fazer()
    assert isinstance(registro, BackupExterno)
    assert re.fullmatch(re.escape(PREFIXO_DA_CHAVE) + r"-[0-9a-f]{32}\.dump\.age", registro.chave)
    assert registro.ambiente == "homologacao"
    assert registro.tamanho_bytes == len(CONTEUDO_CIFRADO)
    assert registro.sha256 == hashlib.sha256(CONTEUDO_CIFRADO).hexdigest()
    assert registro.iniciado_em == I
    assert registro.concluido_em >= registro.iniciado_em
    assert _chaves(ab) == [registro.chave]
    objeto = ab.head_object(Bucket=BUCKET, Key=registro.chave)
    assert objeto["Metadata"]["sha256"] == registro.sha256
    assert ab.get_object(Bucket=BUCKET, Key=registro.chave)["Body"].read() == CONTEUDO_CIFRADO


def test_o_despejo_recebe_a_conexao_pelo_ambiente(
    ab: Any, ferramentas: Ferramentas, senha_unica: None
) -> None:  # A-2
    _fazer()
    args = ferramentas.argumentos("pg_dump")
    assert {"--format=custom", "--no-owner", "--no-privileges"} <= set(args)
    assert not [a for a in args if SENHA_DO_BANCO in a]
    ambiente = ferramentas.ambiente("pg_dump")
    assert ambiente["PGPASSWORD"] == SENHA_DO_BANCO
    assert ambiente["PGDATABASE"] == connection.settings_dict["NAME"]
    assert {"PGHOST", "PGPORT", "PGUSER", "PGSSLMODE"} <= set(ambiente)


def test_a_cifragem_usa_so_a_chave_publica(ab: Any, ferramentas: Ferramentas) -> None:  # A-3
    _fazer()
    args = ferramentas.argumentos("age")
    assert "--encrypt" in args
    assert args[args.index("--recipient") + 1] == CHAVE_PUBLICA
    despejo = next(a for a in ferramentas.argumentos("pg_dump") if a.startswith("--file="))
    assert args[-1] == despejo.split("=", 1)[1]  # a entrada da cifragem é o despejo
    assert "PGPASSWORD" not in ferramentas.ambiente("age")


@pytest.fixture
def envio_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    import botocore.client

    original = botocore.client.BaseClient._make_api_call

    def falha(self: Any, operacao: str, parametros: Any) -> Any:
        if operacao in ("PutObject", "CreateMultipartUpload", "UploadPart"):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "negado"}}, operacao)
        return original(self, operacao, parametros)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", falha)


def _falha_do_backup(instante: datetime = I) -> Any:
    from apps.operacao.backup import BackupFalhou

    with pytest.raises(BackupFalhou) as erro:
        _fazer(instante)
    return erro.value


def test_falha_do_despejo(ab: Any, ferramentas: Ferramentas) -> None:  # A-4 (despejo)
    ferramentas.codigo_do_despejo = 1
    falha = _falha_do_backup()
    assert (falha.etapa, falha.causa) == ("despejo", "1")
    _nada_ficou(ab, ferramentas)


def test_cifragem_com_tempo_esgotado(ab: Any, ferramentas: Ferramentas) -> None:  # A-4 (cifragem)
    ferramentas.cifragem_esgota = True
    falha = _falha_do_backup()
    assert (falha.etapa, falha.causa) == ("cifragem", "TimeoutExpired")
    _nada_ficou(ab, ferramentas)


def test_falha_do_envio(ab: Any, ferramentas: Ferramentas, envio_falha: None) -> None:  # A-4
    falha = _falha_do_backup()
    assert (falha.etapa, falha.causa) == ("envio", "ClientError")
    _nada_ficou(ab, ferramentas)


def _nada_ficou(s3: Any, ferramentas: Ferramentas) -> None:
    assert BackupExterno.objects.count() == 0
    assert _chaves(s3) == []
    for caminho in ferramentas.arquivos_temporarios():
        assert not caminho.exists()
        assert not caminho.parent.exists()


def test_tamanho_divergente_apaga_o_objeto(
    ab: Any, ferramentas: Ferramentas, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-5
    import botocore.client

    original = botocore.client.BaseClient._make_api_call

    def tamanho_errado(self: Any, operacao: str, parametros: Any) -> Any:
        resposta = original(self, operacao, parametros)
        if operacao == "HeadObject":
            resposta["ContentLength"] += 1
        return resposta

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", tamanho_errado)
    falha = _falha_do_backup()
    assert falha.etapa == "conferencia"
    assert _chaves(ab) == []
    assert BackupExterno.objects.count() == 0


def test_nada_sobra_no_diretorio_temporario(ab: Any, ferramentas: Ferramentas) -> None:  # A-6
    _fazer()
    arquivos = ferramentas.arquivos_temporarios()
    assert arquivos
    for caminho in arquivos:
        assert not caminho.exists()
        assert not caminho.parent.exists()


def test_a_criacao_do_diretorio_so_do_dono(ab: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # A-6
    import os
    import stat

    from apps.operacao import backup

    modos: list[int] = []

    def espia(args: Any, env: Any, timeout: int) -> None:
        if args[0] == "pg_dump":
            destino = Path(next(a for a in args if a.startswith("--file=")).split("=", 1)[1])
            modos.append(stat.S_IMODE(os.stat(destino.parent).st_mode))
            destino.write_bytes(CONTEUDO_DO_DESPEJO)
        else:
            Path(args[args.index("--output") + 1]).write_bytes(CONTEUDO_CIFRADO)

    monkeypatch.setattr(backup, "executar_ferramenta", espia)
    _fazer()
    if os.name == "posix":
        assert modos == [0o700]


def test_o_registro_so_aceita_insercao(ab: Any, ferramentas: Ferramentas) -> None:  # A-7
    registro = _fazer()
    with pytest.raises(RegistroImutavel):
        BackupExterno.objects.filter(pk=registro.pk).update(tamanho_bytes=1)
    with pytest.raises(RegistroImutavel):
        BackupExterno.objects.filter(pk=registro.pk).delete()
    for sql in (
        "UPDATE operacao_backupexterno SET tamanho_bytes = 5",
        "DELETE FROM operacao_backupexterno",
    ):
        with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql)

    def novo(**campos: Any) -> BackupExterno:
        base: dict[str, Any] = {
            "iniciado_em": I,
            "concluido_em": I,
            "ambiente": "homologacao",
            "chave": "outra/chave.dump.age",
            "tamanho_bytes": 10,
            "sha256": "a" * 64,
        }
        return BackupExterno.objects.create(**{**base, **campos})

    for campos in (
        {"chave": registro.chave},
        {"tamanho_bytes": 0},
        {"sha256": "a" * 63},
        {"sha256": "g" * 64},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            novo(**campos)
    assert novo().pk


def test_os_logs_nao_vazam_segredos(
    ab: Any, ferramentas: Ferramentas, caplog: pytest.LogCaptureFixture, senha_unica: None
) -> None:  # A-8
    with caplog.at_level(logging.INFO):
        _fazer()
        ferramentas.codigo_do_despejo = 1
        _falha_do_backup(I + timedelta(hours=1))
        ferramentas.codigo_do_despejo = 0
        ferramentas.cifragem_esgota = True
        _falha_do_backup(I + timedelta(hours=2))
    mensagens = [r.getMessage() for r in caplog.records if r.name.startswith("apps.operacao")]
    assert any(CHAVE_DO_OBJETO in m and "tamanho=" in m and "duracao=" in m for m in mensagens)
    assert any("etapa=despejo" in m and "causa=1" in m for m in mensagens)
    assert any("etapa=cifragem" in m and "TimeoutExpired" in m for m in mensagens)
    texto = " ".join(r.getMessage() for r in caplog.records)
    for proibido in (
        SENHA_DO_BANCO,
        "DATABASE_URL",
        CHAVE_DE_ACESSO,
        SEGREDO_DE_ACESSO,
        EMAIL_NO_ERRO,
    ):
        assert proibido not in texto, proibido


def test_a_tarefa_e_o_catalogo() -> None:  # A-9
    from procrastinate.contrib.django import app

    from apps.operacao import tarefas
    from apps.operacao.catalogo import POR_NOME

    assert tarefas.backup_diario is not None
    candidatas = [
        p for p in app.periodic_registry.periodic_tasks.values() if p.task.name == "backup_diario"
    ]
    assert len(candidatas) == 1
    assert candidatas[0].cron == "0 6 * * *"
    assert candidatas[0].task.queueing_lock == "backup_diario"
    entrada = POR_NOME["backup_diario"]
    assert entrada.descricao == "Backup externo diário"
    assert entrada.intervalo.total_seconds() == 1440 * 60
    assert entrada.tolerancia.total_seconds() == 1560 * 60


def test_a_tarefa_grava_o_backup_e_a_execucao(ab: Any, ferramentas: Ferramentas) -> None:  # A-10
    from apps.operacao import tarefas
    from apps.operacao.models import ExecucaoDaTarefa

    tarefas.backup_diario(timestamp=0)
    assert BackupExterno.objects.count() == 1
    assert ExecucaoDaTarefa.objects.get(nome="backup_diario").ultima_conclusao_em is not None


def test_a_tarefa_repassa_a_falha(
    ab: Any, ferramentas: Ferramentas, envio_falha: None
) -> None:  # A-11
    from apps.operacao import tarefas
    from apps.operacao.backup import BackupFalhou
    from apps.operacao.models import ExecucaoDaTarefa

    with pytest.raises(BackupFalhou):
        tarefas.backup_diario(timestamp=0)
    assert ExecucaoDaTarefa.objects.get(nome="backup_diario").ultimo_erro == "BackupFalhou"
    assert BackupExterno.objects.count() == 0


def test_o_comando_backup_externo(
    ab: Any, ferramentas: Ferramentas, relogio: RelogioControlado
) -> None:  # A-12
    saida = StringIO()
    call_command("backup_externo", stdout=saida)
    assert CHAVE_DO_OBJETO.rsplit("T", 1)[0] in saida.getvalue()
    assert str(len(CONTEUDO_CIFRADO)) in saida.getvalue()
    relogio.congelar(I + timedelta(hours=1))  # outra chave: a mesma seria recusada na reserva
    ferramentas.codigo_do_despejo = 1
    saida, erro = StringIO(), StringIO()
    with pytest.raises(SystemExit) as saiu:
        call_command("backup_externo", stdout=saida, stderr=erro)
    assert saiu.value.code == 1
    assert "Backup falhou na etapa despejo." in saida.getvalue() + erro.getvalue()


def test_sem_configuracao_a_tarefa_falha_visivel(settings: Any) -> None:  # regra 8
    from apps.operacao.backup import BackupFalhou, fazer_backup_externo

    settings.R2_BUCKET_BACKUPS = ""
    with pytest.raises(BackupFalhou) as erro:
        fazer_backup_externo(I)
    assert (erro.value.etapa, erro.value.causa) == ("configuracao", "ImproperlyConfigured")


def test_o_backup_manda_checkins_ao_sentry(ab: Any, ferramentas: Ferramentas) -> None:  # A-14
    import sentry_sdk

    from apps.operacao import tarefas
    from config.observabilidade import opcoes_do_sentry
    from tests.tecnicos.test_observabilidade import DSN, TransporteEmMemoria

    tm = TransporteEmMemoria()
    sentry_sdk.init(**opcoes_do_sentry(DSN, "homologacao", None, transport=tm))
    try:
        tarefas.backup_diario(timestamp=0)
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.get_global_scope().set_client(None)
    checkins = tm.checkins()
    assert [c["status"] for c in checkins] == ["in_progress", "ok"]
    assert {c["monitor_slug"] for c in checkins} == {"backup-diario"}
    configuracao = checkins[0]["monitor_config"]
    assert configuracao["schedule"] == {"type": "crontab", "value": "0 6 * * *"}
    assert (configuracao["checkin_margin"], configuracao["max_runtime"]) == (120, 60)


# --- correção E16-R03: um backup confirmado nunca é substituído (A-18 a A-25) ---------------------


def _trocar_o_conteudo_cifrado(monkeypatch: pytest.MonkeyPatch, novo: bytes) -> None:
    import sys

    monkeypatch.setattr(sys.modules[__name__], "CONTEUDO_CIFRADO", novo)


def _sha_do_objeto(s3: Any) -> str:
    corpo = s3.get_object(Bucket=BUCKET, Key=CHAVE_DO_OBJETO)["Body"].read()
    return hashlib.sha256(corpo).hexdigest()


def test_repetir_com_o_mesmo_instante_nao_substitui(
    ab: Any, ferramentas: Ferramentas, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-18
    from apps.operacao import backup

    _soltar_o_identificador(monkeypatch)
    primeiro = _fazer()
    _trocar_o_conteudo_cifrado(monkeypatch, b"OUTRO-BACKUP-CIFRADO")
    segundo = _fazer()  # o mesmo instante: outra chave, o primeiro intacto
    assert segundo.chave != primeiro.chave
    assert ab.get_object(Bucket=BUCKET, Key=primeiro.chave)["Body"].read() == CONTEUDO_ORIGINAL
    assert BackupExterno.objects.count() == 2
    for registro in BackupExterno.objects.all():
        corpo = ab.get_object(Bucket=BUCKET, Key=registro.chave)["Body"].read()
        assert hashlib.sha256(corpo).hexdigest() == registro.sha256
    # um identificador repetido (improvável) é recusado antes de qualquer trabalho
    chamadas = len(ferramentas.chamadas)
    identificador = primeiro.chave.rsplit("-", 1)[1].removesuffix(".dump.age")
    monkeypatch.setattr(backup, "identificador_da_execucao", lambda: identificador)
    falha = _falha_do_backup()
    assert (falha.etapa, falha.causa) == ("reserva", "ChaveExistente")
    assert len(ferramentas.chamadas) == chamadas  # despejo e cifragem não foram chamados
    assert ab.get_object(Bucket=BUCKET, Key=primeiro.chave)["Body"].read() == CONTEUDO_ORIGINAL
    assert BackupExterno.objects.count() == 2


def test_objeto_sem_registro_tambem_e_protegido(ab: Any, ferramentas: Ferramentas) -> None:
    # A-19
    ab.put_object(Bucket=BUCKET, Key=CHAVE_DO_OBJETO, Body=b"SOBRA-DE-ENVIO-INTERROMPIDO")
    falha = _falha_do_backup()
    assert (falha.etapa, falha.causa) == ("reserva", "ChaveExistente")
    assert ab.get_object(Bucket=BUCKET, Key=CHAVE_DO_OBJETO)["Body"].read() == (
        b"SOBRA-DE-ENVIO-INTERROMPIDO"
    )
    assert BackupExterno.objects.count() == 0
    assert ferramentas.chamadas == []


@pytest.fixture
def trava_ocupada() -> Iterator[None]:
    """Outra conexão do banco segura a trava do backup."""
    import psycopg

    from apps.operacao.backup import CHAVE_DA_TRAVA_DO_BACKUP

    banco = connection.settings_dict
    outra = psycopg.connect(
        host=banco["HOST"] or "localhost",
        port=banco["PORT"] or 5432,
        user=banco["USER"],
        password=banco["PASSWORD"],
        dbname=banco["NAME"],
        autocommit=True,
    )
    outra.execute("SELECT pg_advisory_lock(%s)", [CHAVE_DA_TRAVA_DO_BACKUP])
    try:
        yield
    finally:
        outra.close()


def test_trava_ocupada_recusa_sem_rodar_nada(
    ab: Any, ferramentas: Ferramentas, trava_ocupada: None
) -> None:  # A-20
    falha = _falha_do_backup()
    assert (falha.etapa, falha.causa) == ("reserva", "EmAndamento")
    assert ferramentas.chamadas == []
    assert _chaves(ab) == []
    assert BackupExterno.objects.count() == 0


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True)
def test_duas_execucoes_ao_mesmo_tempo(
    ab: Any, monkeypatch: pytest.MonkeyPatch, relogio: RelogioControlado
) -> None:  # A-21
    import threading

    from django.db import connections

    from apps.operacao import backup
    from apps.operacao.backup import BackupFalhou, fazer_backup_externo

    a_no_despejo = threading.Event()
    b_tentou = threading.Event()
    falsas = Ferramentas()

    def ferramenta(args: Any, env: Any, timeout: int) -> None:
        if args[0] == "pg_dump" and threading.current_thread().name == "A":
            a_no_despejo.set()
            assert b_tentou.wait(15), "a segunda execução não chegou a tentar"
        falsas(args, env, timeout)

    monkeypatch.setattr(backup, "executar_ferramenta", ferramenta)
    resultados: dict[str, Any] = {}

    def correr(nome: str) -> None:
        try:
            if nome == "B":
                assert a_no_despejo.wait(15)
            resultados[nome] = fazer_backup_externo(I)
        except BackupFalhou as falha:
            resultados[nome] = falha
        finally:
            if nome == "B":
                b_tentou.set()
            connections.close_all()

    threads = [threading.Thread(target=correr, args=(n,), name=n) for n in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(40)
    concluidas = [r for r in resultados.values() if isinstance(r, BackupExterno)]
    falhas = [r for r in resultados.values() if isinstance(r, BackupFalhou)]
    assert len(concluidas) == 1
    assert len(falhas) == 1
    assert (falhas[0].etapa, falhas[0].causa) in {
        ("reserva", "EmAndamento"),
        ("reserva", "ChaveExistente"),
    }
    assert BackupExterno.objects.count() == 1
    assert _sha_do_objeto(ab) == concluidas[0].sha256


def _trancas_do_backup() -> int:
    from apps.operacao.backup import CHAVE_DA_TRAVA_DO_BACKUP

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = %s",
            [CHAVE_DA_TRAVA_DO_BACKUP],
        )
        return int(cursor.fetchone()[0])


def test_falha_no_envio_nao_deixa_objeto_nem_trava(
    ab: Any, ferramentas: Ferramentas, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-22
    import botocore.client

    original = botocore.client.BaseClient._make_api_call
    estado = {"falhar": True}

    def intermitente(self: Any, operacao: str, parametros: Any) -> Any:
        if estado["falhar"] and operacao in ("PutObject", "CreateMultipartUpload", "UploadPart"):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "negado"}}, operacao)
        return original(self, operacao, parametros)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", intermitente)
    falha = _falha_do_backup()
    assert falha.etapa == "envio"
    assert _trancas_do_backup() == 0
    assert _chaves(ab) == []
    estado["falhar"] = False
    from apps.operacao.backup import fazer_backup_externo

    assert fazer_backup_externo(I).chave == CHAVE_DO_OBJETO
    assert _trancas_do_backup() == 0
    assert fazer_backup_externo(I + timedelta(hours=1)).chave.endswith(
        f"20261120T070000Z-{ID_FIXO}.dump.age"
    )
    assert _trancas_do_backup() == 0


def test_erro_do_r2_na_reserva(
    ab: Any, ferramentas: Ferramentas, monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:  # A-23
    import botocore.client

    original = botocore.client.BaseClient._make_api_call

    def nega(self: Any, operacao: str, parametros: Any) -> Any:
        if operacao == "HeadObject":
            raise ClientError({"Error": {"Code": "403", "Message": "negado"}}, operacao)
        return original(self, operacao, parametros)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", nega)
    with caplog.at_level(logging.ERROR):
        falha = _falha_do_backup()
    assert (falha.etapa, falha.causa) == ("reserva", "ClientError")
    assert ferramentas.chamadas == []
    assert any("etapa=reserva" in r.getMessage() for r in caplog.records)


def test_objeto_que_aparece_durante_o_despejo_nao_e_substituido(
    ab: Any, ferramentas: Ferramentas, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-24
    from apps.operacao import backup

    def despeja_e_outra_escrita(args: Any, env: Any, timeout: int) -> None:
        ferramentas(args, env, timeout)
        if args[0] == "pg_dump":
            ab.put_object(Bucket=BUCKET, Key=CHAVE_DO_OBJETO, Body=b"ESCRITA-DE-OUTRO")

    monkeypatch.setattr(backup, "executar_ferramenta", despeja_e_outra_escrita)
    falha = _falha_do_backup()
    assert (falha.etapa, falha.causa) == ("reserva", "ChaveExistente")
    assert ab.get_object(Bucket=BUCKET, Key=CHAVE_DO_OBJETO)["Body"].read() == b"ESCRITA-DE-OUTRO"
    assert BackupExterno.objects.count() == 0


def test_comando_e_tarefa_na_reserva(
    ab: Any, ferramentas: Ferramentas, trava_ocupada: None
) -> None:  # A-25
    saida, erro = StringIO(), StringIO()
    with pytest.raises(SystemExit) as saiu:
        call_command("backup_externo", stdout=saida, stderr=erro)
    texto = saida.getvalue() + erro.getvalue()
    assert saiu.value.code == 1
    assert "Backup falhou na etapa reserva." in texto
    assert "Outro backup está em andamento." in texto


def test_comando_e_tarefa_com_a_chave_existente(ab: Any, ferramentas: Ferramentas) -> None:
    # A-25
    from apps.operacao import tarefas
    from apps.operacao.backup import BackupFalhou
    from apps.operacao.models import ExecucaoDaTarefa

    ab.put_object(Bucket=BUCKET, Key=CHAVE_DO_OBJETO, Body=b"JA-EXISTE")
    saida, erro = StringIO(), StringIO()
    with pytest.raises(SystemExit) as saiu:
        call_command("backup_externo", stdout=saida, stderr=erro)
    texto = saida.getvalue() + erro.getvalue()
    assert saiu.value.code == 1
    assert "Já existe um backup com esta chave; nada foi substituído." in texto
    with pytest.raises(BackupFalhou):
        tarefas.backup_diario(timestamp=0)
    assert ExecucaoDaTarefa.objects.get(nome="backup_diario").ultimo_erro == "BackupFalhou"


# --- correção residual E16-R03: a chave é única por execução (A-26 e A-27) ------------------------


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True)
def test_perda_da_trava_nao_substitui_backup_confirmado(
    ab: Any, monkeypatch: pytest.MonkeyPatch, relogio: RelogioControlado
) -> None:  # A-26 (reprodução do revisor de 2026-11-18, sem forçar o identificador)
    import threading

    from django.db import connections

    from apps.operacao import backup

    _soltar_o_identificador(monkeypatch)
    livre = threading.Event()
    concluido = threading.Event()
    resultados: dict[str, Any] = {}
    original = backup._reservar

    def ferramenta(args: Any, env: Any, timeout: int) -> None:
        if args[0] == "pg_dump":
            if threading.current_thread().name == "A":
                connections["default"].close()  # a sessão cai: a trava de A se perde
            destino = next(a for a in args if a.startswith("--file=")).split("=", 1)[1]
            Path(destino).write_bytes(b"dump")
        else:
            Path(args[args.index("--output") + 1]).write_bytes(
                threading.current_thread().name.encode()
            )

    def reservar(*args: Any, **kwargs: Any) -> Any:
        original(*args, **kwargs)
        if threading.current_thread().name == "A" and kwargs.get("so_o_bucket"):
            livre.set()
            assert concluido.wait(20), "B não concluiu"

    def executar(nome: str) -> None:
        try:
            if nome == "B":
                assert livre.wait(20), "A não chegou à segunda conferência"
            resultados[nome] = backup.fazer_backup_externo(I)
        except Exception as erro:
            resultados[nome] = erro
        finally:
            connections.close_all()
            if nome == "B":
                concluido.set()

    monkeypatch.setattr(backup, "executar_ferramenta", ferramenta)
    monkeypatch.setattr(backup, "_reservar", reservar)
    threads = [threading.Thread(target=executar, args=(n,), name=n) for n in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(40)
    assert all(not thread.is_alive() for thread in threads)
    assert isinstance(resultados["B"], BackupExterno), resultados
    for registro in BackupExterno.objects.all():
        corpo = ab.get_object(Bucket=BUCKET, Key=registro.chave)["Body"].read()
        assert hashlib.sha256(corpo).hexdigest() == registro.sha256, registro.chave
    objeto_de_b = ab.get_object(Bucket=BUCKET, Key=resultados["B"].chave)["Body"].read()
    assert hashlib.sha256(objeto_de_b).hexdigest() == resultados["B"].sha256


def test_o_identificador_da_execucao(
    ab: Any, ferramentas: Ferramentas, monkeypatch: pytest.MonkeyPatch, settings: Any
) -> None:  # A-27
    _soltar_o_identificador(monkeypatch)
    primeiro = _fazer()
    segundo = _fazer()
    ids = [r.chave.rsplit("-", 1)[1].removesuffix(".dump.age") for r in (primeiro, segundo)]
    assert ids[0] != ids[1]
    for identificador in ids:
        assert re.fullmatch(r"[0-9a-f]{32}", identificador)
        assert settings.AMBIENTE not in identificador
        assert str(connection.settings_dict["NAME"]) not in identificador
