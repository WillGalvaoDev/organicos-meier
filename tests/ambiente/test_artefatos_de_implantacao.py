"""E16-01: artefatos de implantação (acceptance A-12 a A-14).

Só lê os arquivos: a construção da imagem é conferida no CI (A-15).
"""

import re
import tomllib
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
SEGREDOS = (
    "SECRET_KEY",
    "DATABASE_URL",
    "EMAIL_HOST_PASSWORD",
    "GOOGLE_CLIENT_SECRET",
    "SEGREDO_AVISOS_SIMULADOR",
    "GOOGLE_CLIENT_ID",
    "EMAIL_HOST_USER",
    "EMAIL_HOST",
    "EMAIL_BACKEND",
    "DEFAULT_FROM_EMAIL",
    "ALLOWED_HOSTS",
    "ORIGEM_PUBLICA",
)


def _texto(nome: str) -> str:
    return (RAIZ / nome).read_text(encoding="utf-8")


def test_dockerfile_e_dockerignore() -> None:  # A-12
    ignorados = {
        linha.strip().rstrip("/") for linha in _texto(".dockerignore").splitlines() if linha.strip()
    }
    for caminho in (".env", ".venv", "media", ".git", "staticfiles"):
        assert caminho in ignorados, caminho
    dockerfile = _texto("Dockerfile")
    assert "uv sync --locked --no-dev" in dockerfile
    usuario = re.findall(r"^USER\s+(\S+)", dockerfile, flags=re.MULTILINE)
    assert usuario
    assert usuario[-1] not in ("root", "0")
    assert "postgresql-client-17" in dockerfile
    assert "age" in dockerfile
    for linha in dockerfile.splitlines():
        if linha.strip().startswith("ENV"):
            for nome in ("SECRET_KEY", "DATABASE_URL", "PASSWORD", "SENHA"):
                assert nome not in linha, linha


def test_fly_toml() -> None:  # A-13
    config = tomllib.loads(_texto("fly.toml"))
    assert config["primary_region"] == "gru"
    processos = config["processes"]
    assert "gunicorn config.wsgi" in processos["web"]
    assert "procrastinate worker" in processos["worker"]
    assert "migrate --noinput" in config["deploy"]["release_command"]
    http = config["http_service"]
    assert http["internal_port"] == 8000
    assert http["force_https"] is True
    verificacao = http["checks"][0]
    assert verificacao["path"] == "/saude/"
    assert verificacao["method"].upper() == "GET"
    assert verificacao["interval"] == "30s"
    assert verificacao["timeout"] == "5s"
    ambiente = config["env"]
    assert ambiente == {
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "AMBIENTE": "homologacao",
        "PROVEDOR_PAGAMENTOS": "simulador",
        "CANAL_WHATSAPP": "desligado",
        "TZ": "UTC",
    }
    for nome in SEGREDOS:
        assert nome not in ambiente


def test_ci_constroi_a_imagem() -> None:  # A-14
    fluxo = yaml.safe_load(_texto(".github/workflows/ci.yml"))
    jobs = fluxo["jobs"]
    passos_da_imagem = [p.get("run", "") for j in jobs.values() for p in j["steps"]]
    construcao = [p for p in passos_da_imagem if "docker build" in p]
    assert construcao
    assert not any("push" in p for p in construcao)
    passos = [p.get("run", "") for p in jobs["verificacoes"]["steps"]]
    for comando in ("uv sync --locked", "ruff check", "ruff format --check", "mypy", "pytest"):
        assert any(comando in p for p in passos), comando


# --- E16-05: o procedimento de restauração (A-13) -----------------------------------------------

TITULOS_DA_RESTAURACAO = (
    "Quando restaurar e quem decide",
    "Congelar",
    "Caminho A, Neon",
    "Caminho B, backup externo",
    "Conferir",
    "Reativar",
    "Avisar os afetados",
    "Guarda da chave privada",
    "Teste cronometrado",
    "RTO e RPO",
)
COLUNAS_DO_REGISTRO = (
    "Data",
    "Caminho",
    "Ponto recuperado",
    "Início",
    "Fim",
    "Duração",
    "Resultado da conferência",
    "Observações",
)


def test_o_procedimento_de_restauracao() -> None:  # A-13
    texto = _texto("docs/operacao/restauracao.md")
    titulos = re.findall(r"^#{2,3}\s+(?:\d+\.\s*)?(.+?)\s*$", texto, flags=re.MULTILINE)
    posicoes = []
    for esperado in TITULOS_DA_RESTAURACAO:
        achados = [i for i, t in enumerate(titulos) if t.startswith(esperado)]
        assert achados, f"falta a seção: {esperado}"
        posicoes.append(achados[0])
    assert posicoes == sorted(posicoes)
    assert "Registro dos testes" in texto
    cabecalho = next(
        linha
        for linha in texto.splitlines()
        if linha.startswith("| Data") and "Ponto recuperado" in linha
    )
    colunas = [c.strip() for c in cabecalho.strip("|").split("|")]
    assert colunas == list(COLUNAS_DO_REGISTRO)
    for comando in (
        "fly scale count worker=0",
        "pg_restore --no-owner --no-privileges",
        "python manage.py conferir_restauracao",
    ):
        assert comando in texto, comando


# --- E16-08: homologação executada e relatório final (A-1 a A-4) -------------------------------
# A-5 a A-15 são de execução (evidências no `review.md`, conferidas pelo revisor).

SECOES_DA_HOMOLOGACAO = (
    "Componentes",
    "Variáveis e segredos",
    "Implantar e atualizar",
    "Monitoramento",
    "Credenciais e menor privilégio",
    "Custos observados",
)
SECOES_DO_RELATORIO = (
    "Resumo",
    "Critério de saída",
    "Etapas entregues",
    "Homologação",
    "Recuperação",
    "Melhorias",
    "Exceções e limitações",
    "Pendências para a fase 2a",
    "Custos",
)
BLOQUEADA = (
    "E16-08 bloqueada por dependência: exige a execução do teste de restauração na homologação "
    "(contas da fase 0) e a decisão do responsável sobre as melhorias (regra 10)"
)


def _titulos(texto: str) -> list[str]:
    return re.findall(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", texto, flags=re.MULTILINE)


def _em_ordem(texto: str, esperados: tuple[str, ...]) -> None:
    titulos = _titulos(texto)
    posicoes = []
    for esperado in esperados:
        achados = [i for i, t in enumerate(titulos) if t == esperado]
        assert achados, f"falta a seção: {esperado}"
        posicoes.append(achados[0])
    assert posicoes == sorted(posicoes)


def _variaveis_obrigatorias() -> set[str]:
    from tests.ambiente.apoio import variaveis_obrigatorias

    return variaveis_obrigatorias()


def test_o_documento_de_homologacao() -> None:  # A-1
    texto = _texto("docs/operacao/homologacao.md")
    _em_ordem(texto, SECOES_DA_HOMOLOGACAO)
    inicio = texto.index("## Variáveis e segredos")
    fim = texto.index("\n## ", inicio + 1)
    secao = texto[inicio:fim]
    obrigatorias = _variaveis_obrigatorias()
    assert {"SECRET_KEY", "DATABASE_URL", "SENTRY_DSN", "R2_BUCKET_BACKUPS"} <= obrigatorias
    for nome in sorted(obrigatorias):
        assert f"`{nome}`" in secao, f"variável sem documentação: {nome}"
    assert not re.search(r"sk_[A-Za-z0-9]", texto)
    assert not re.search(r"age1[a-z0-9]{20,}", texto)
    assert not re.search(r"postgres(?:ql)?://[^\s:@]+:[^\s@]+@", texto)
    assert "AKIA" not in texto


def test_o_relatorio_final_tem_a_estrutura() -> None:  # A-2
    texto = _texto("docs/relatorio-fase1.md")
    _em_ordem(texto, SECOES_DO_RELATORIO)
    inicio = texto.index("## Critério de saída")
    fim = texto.index("\n## ", inicio + 1)
    linhas = [linha for linha in texto[inicio:fim].splitlines() if linha.startswith("|")]
    assert len(linhas) >= 5  # cabeçalho, separador e as três linhas da infraestrutura 7
    corpo = " ".join(linhas).lower()
    for item in ("cenários 1–119", "t-1–t-55", "teste de restauração"):  # noqa: RUF001
        assert item in corpo, item
    assert "rastreabilidade-fase1.md" in texto
    assert "operacao/restauracao.md" in texto


@pytest.mark.xfail(strict=True, reason=BLOQUEADA)
def test_o_registro_da_restauracao_e_o_rto() -> None:  # A-3
    texto = _texto("docs/operacao/restauracao.md")
    inicio = texto.index("### Registro dos testes")
    fim = texto.index("\n## ", inicio)
    linhas = [
        [c.strip() for c in linha.strip("|").split("|")]
        for linha in texto[inicio:fim].splitlines()
        if linha.startswith("|") and not linha.startswith("|---")
    ][1:]  # sem o cabeçalho
    assert len(linhas) >= 2
    assert {linha[1][-1:] for linha in linhas} >= {"A", "B"}
    assert all(c and c != "—" for linha in linhas for c in linha)
    rto = re.search(r"\*\*RTO:\*\*[^\n]*?(\d+(?:[.,]\d+)?)\s*(?:horas|h)\b", texto)
    assert rto, "RTO numérico em horas"


@pytest.mark.xfail(strict=True, reason=BLOQUEADA)
def test_as_melhorias_tem_decisao() -> None:  # A-4
    texto = _texto("docs/melhorias.md")
    inicio = texto.index("## Pendentes")
    fim = texto.index("\n## Encerradas")
    pendentes = [linha for linha in texto[inicio:fim].splitlines() if re.match(r"\| M-\d+ ", linha)]
    assert pendentes
    for linha in pendentes:
        assert re.search(r"fase 2a|fase 2b|fase 3", linha, flags=re.IGNORECASE), linha[:60]


# --- correção E16-R01: a construção da imagem é autossuficiente (A-16 a A-19) --------------------


def test_o_run_do_collectstatic_tem_todas_as_variaveis() -> None:  # A-16
    from tests.ambiente.apoio import conferir_dockerfile, variaveis_obrigatorias

    obrigatorias = variaveis_obrigatorias()
    assert conferir_dockerfile(_texto("Dockerfile"), obrigatorias) == []


def test_a_coleta_de_estaticos_carrega_as_configuracoes_de_producao() -> None:  # A-17
    import os
    import subprocess
    import sys

    from tests.ambiente.apoio import ambiente_da_coleta

    ambiente = ambiente_da_coleta(_texto("Dockerfile"))
    assert ambiente
    # o `.env` local (ignorado pelo git) não pode esconder uma variável que falta
    codigo = (
        "import environ;"
        "environ.Env.read_env = classmethod(lambda cls, *a, **k: None);"
        "from django.core.management import execute_from_command_line;"
        "execute_from_command_line(['manage.py', 'collectstatic', '--noinput', '--dry-run'])"
    )
    resultado = subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env={
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONPATH": str(RAIZ),
            **ambiente,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr[-800:]


def test_a_conferencia_acusa_o_que_falta() -> None:  # A-18
    from tests.ambiente.apoio import conferir_dockerfile, variaveis_obrigatorias

    dockerfile = _texto("Dockerfile")
    sem_sentry = re.sub(r"\s*SENTRY_DSN=\S+", "", dockerfile)
    problemas = conferir_dockerfile(sem_sentry, variaveis_obrigatorias())
    assert any("SENTRY_DSN" in p for p in problemas)
    novo = {
        "config/settings/base.py": 'X = env("VARIAVEL_NOVA")\nY = env("COM_PADRAO", default="")\n',
        "config/settings/prod.py": "",
    }
    obrigatorias = variaveis_obrigatorias(novo)
    assert obrigatorias == {"VARIAVEL_NOVA"}
    assert any("VARIAVEL_NOVA" in p for p in conferir_dockerfile(dockerfile, obrigatorias))
    com_host_real = dockerfile.replace(
        "ALLOWED_HOSTS=construcao.invalid", "ALLOWED_HOSTS=exemplo.com.br"
    )
    assert any("host não fictício" in p for p in conferir_dockerfile(com_host_real, set()))
    com_env = dockerfile.replace("EXPOSE 8000", "ENV SENTRY_DSN=x\nEXPOSE 8000")
    assert any("ENV" in p for p in conferir_dockerfile(com_env, {"SENTRY_DSN"}))


def test_o_ci_recusa_segredos_na_configuracao_da_imagem() -> None:  # A-19
    fluxo = yaml.safe_load(_texto(".github/workflows/ci.yml"))
    passos = [p.get("run", "") for p in fluxo["jobs"]["imagem"]["steps"]]
    inspecao = [p for p in passos if "docker image inspect" in p]
    assert inspecao
    for nome in ("SECRET_KEY", "DATABASE_URL", "SENTRY_DSN", "R2_", "BACKUP_"):
        assert nome in inspecao[0], nome


# --- correção E16-R07: os custos citam as faixas da infraestrutura 10, linha a linha (A-16) -----


def test_os_custos_seguem_a_infraestrutura_10() -> None:  # A-16 (E16-08)
    for arquivo in ("docs/operacao/homologacao.md", "docs/relatorio-fase1.md"):
        texto = _texto(arquivo)
        assert "US$ 15–35" in texto, arquivo  # noqa: RUF001
        for linha in texto.splitlines():
            if "US$ 8–15" in linha:  # noqa: RUF001
                assert "Fly.io" in linha, f"{arquivo}: US$ 8–15 só vale para o Fly.io: {linha[:80]}"  # noqa: RUF001
    homologacao = _texto("docs/operacao/homologacao.md")
    for faixa in ("US$ 8–15", "US$ 5–20", "US$ 0–2", "US$ 15–35"):  # noqa: RUF001
        assert faixa in homologacao, faixa
