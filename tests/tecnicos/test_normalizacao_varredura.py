"""E02-10: nenhum fluxo compara e-mails sem normalizar (T-37; acceptance A-14 a A-16).

Duas frentes: uma propriedade (hypothesis) que executa cada fluxo com variações de caixa e espaços
e uma varredura estática do código de `apps/`. A terceira verificação do spec (consulta por
`email_normalizado` com valor que não passou por `normalizar_email` na mesma função) não é viável
por análise estática completa e é feita por revisão, registrada no `review.md`.
"""

import ast
import json
import re
import secrets
from pathlib import Path
from typing import Any

import pytest
from django.core import mail
from django.core.cache import cache
from django.db import transaction
from django.test import Client
from hypothesis import HealthCheck, assume, given, settings

import apps
from apps.contas.convites import (
    ConviteInvalido,
    EmailBanidoErro,
    MetodoCadastro,
    consumir_convite,
    emitir_convite,
)
from apps.contas.emails import email_banido
from apps.contas.models import Conta, Convite, EmailBanido, EmailEmUso
from tests.apoio.estrategias import enderecos
from tests.fabricas import ContaFactory, ConviteFactory

pytestmark = [pytest.mark.tecnico, pytest.mark.urls("tests.apoio.urls")]

SENHA = "senha-forte-9271!"
RAIZ_DE_APPS = Path(apps.__file__).resolve().parent
ARQUIVO_DA_NORMALIZACAO = RAIZ_DE_APPS / "contas" / "emails.py"


def _autenticado(cliente: Client) -> bool:
    return "_auth_user_id" in cliente.session


@pytest.mark.django_db
@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(conta_existente=enderecos(), conta_banida=enderecos())
def test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos(
    conta_existente: tuple[str, str, str],
    conta_banida: tuple[str, str, str],
    django_capture_on_commit_callbacks: Any,
) -> None:  # A-14 (T-37)
    base, variado, alias = conta_existente
    base_banida, variado_banido, alias_banido = conta_banida
    assume(len({base, alias, base_banida, alias_banido}) == 4)
    assume(base.split("@")[0] != base_banida.split("@")[0])

    with transaction.atomic():  # cada exemplo é desfeito no fim
        cache.clear()
        mail.outbox.clear()
        admin = ContaFactory.create(administrador=True, email_normalizado="adm-t37@exemplo.com")
        conta = ContaFactory.create(email_normalizado=base)
        conta.set_password(SENHA)
        conta.save()

        # unicidade da conta e emissão de convite
        with pytest.raises(EmailEmUso), transaction.atomic():
            Conta.objects.create(email_normalizado=variado, nome="Outra", papel="comprador")
        with pytest.raises(EmailEmUso):
            emitir_convite(admin, variado, "comprador")
        assert emitir_convite(admin, alias, "comprador").email_normalizado == alias

        # login por senha
        entrada = Client()
        entrada.post("/entrar/", {"login": variado, "password": SENHA})
        assert _autenticado(entrada)

        # link de acesso
        mail.outbox.clear()
        with django_capture_on_commit_callbacks(execute=True):
            Client().post("/entrar/link/", {"email": variado})
        assert [m.to for m in mail.outbox] == [[base]]
        mail.outbox.clear()
        with django_capture_on_commit_callbacks(execute=True):
            Client().post("/entrar/link/", {"email": alias})
        assert mail.outbox == []  # o alias é outro endereço, sem conta

        # recuperação de acesso
        mail.outbox.clear()
        Client().post("/recuperar-acesso/", {"email": variado})
        assert [m.to for m in mail.outbox] == [[base]]

        # Google
        google = Client()
        dados = {"sub": "g-t37", "email": variado.strip(), "email_verified": True, "name": "G"}
        google.post("/teste/retorno-google/", {"extra_data": json.dumps(dados)})
        assert _autenticado(google)
        alias_do_google = Client()
        dados["email"] = alias
        dados["sub"] = "g-t37-alias"
        alias_do_google.post("/teste/retorno-google/", {"extra_data": json.dumps(dados)})
        assert not _autenticado(alias_do_google)

        # consumo de convite: o e-mail do convite é comparado já normalizado
        token_em_uso = secrets.token_urlsafe(32)
        ConviteFactory.create(
            email_normalizado=base, token_hash=Convite.hash_do_token(token_em_uso)
        )
        with pytest.raises(ConviteInvalido) as erro:
            consumir_convite(token_em_uso, "Nome", SENHA, metodo=MetodoCadastro.SENHA)
        assert erro.value.codigo == "email_em_uso"

        # banimento
        EmailBanido.objects.create(email_normalizado=variado_banido, banido_por=admin)
        assert email_banido(variado_banido)
        assert email_banido(base_banida)
        assert not email_banido(alias_banido)
        with pytest.raises(EmailBanidoErro):
            emitir_convite(admin, variado_banido, "comprador")
        assert emitir_convite(admin, alias_banido, "comprador").email_normalizado == alias_banido
        token_banido = secrets.token_urlsafe(32)
        ConviteFactory.create(
            email_normalizado=base_banida, token_hash=Convite.hash_do_token(token_banido)
        )
        with pytest.raises(ConviteInvalido) as erro:
            consumir_convite(token_banido, "Nome", SENHA, metodo=MetodoCadastro.SENHA)
        assert erro.value.codigo == "banido"

        transaction.set_rollback(True)


# --- varredura estática ---------------------------------------------------------------------


def _menciona_email(no: ast.AST) -> bool:
    for filho in ast.walk(no):
        nomes = []
        if isinstance(filho, ast.Name):
            nomes.append(filho.id)
        elif isinstance(filho, ast.Attribute):
            nomes.append(filho.attr)
        elif isinstance(filho, ast.Constant) and isinstance(filho.value, str):
            nomes.append(filho.value)
        if any("email" in nome.lower() for nome in nomes):
            return True
    return False


def analisar_codigo(codigo: str, caminho: str, *, permite_minusculas: bool = False) -> list[str]:
    """Acusa comparações de e-mail que não passam por `normalizar_email` (T-37).

    Procura `email__iexact`/`email_normalizado__iexact` (como argumento nomeado ou como texto) e
    `.lower()`/`.casefold()` sobre expressões que mencionam e-mail, fora de `apps/contas/emails.py`
    (`permite_minusculas`).
    """
    achados: list[str] = []
    for no in ast.walk(ast.parse(codigo)):
        if isinstance(no, ast.keyword) and no.arg and re.fullmatch(r"\w*email\w*__iexact", no.arg):
            achados.append(f"{caminho}: consulta {no.arg}")
        if (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and re.fullmatch(r"\w*email\w*__iexact", no.value)
        ):
            achados.append(f"{caminho}:{no.lineno}: texto {no.value}")
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr in {"lower", "casefold"}
            and not permite_minusculas
            and _menciona_email(no.func.value)
        ):
            achados.append(f"{caminho}:{no.lineno}: .{no.func.attr}() sobre e-mail")
    return achados


def test_codigo_de_apps_nao_compara_email_sem_normalizar() -> None:  # A-15 (T-37)
    achados: list[str] = []
    arquivos = [p for p in RAIZ_DE_APPS.rglob("*.py") if "migrations" not in p.parts]
    assert len(arquivos) > 10  # sanidade: a varredura encontrou o código
    for arquivo in arquivos:
        achados += analisar_codigo(
            arquivo.read_text(encoding="utf-8"),
            str(arquivo.relative_to(RAIZ_DE_APPS)),
            permite_minusculas=arquivo == ARQUIVO_DA_NORMALIZACAO,
        )
    assert achados == []


def test_varredura_acusa_iexact_em_arquivo_temporario(tmp_path: Path) -> None:  # A-16 (T-37)
    arquivo = tmp_path / "ruim.py"
    arquivo.write_text("Conta.objects.filter(email_normalizado__iexact=x)\n", encoding="utf-8")
    achados = analisar_codigo(arquivo.read_text(encoding="utf-8"), arquivo.name)
    assert achados
    assert "email_normalizado__iexact" in achados[0]


@pytest.mark.parametrize(
    "linha",
    [
        "Conta.objects.filter(email__iexact=x)",
        "filtro = {'email_normalizado__iexact': x}",
        "x = conta.email_normalizado.lower()",
        "y = email.casefold()",
        "z = str(dados['email']).lower()",
    ],
)
def test_varredura_acusa_outras_formas(linha: str) -> None:
    assert analisar_codigo(linha + "\n", "x.py")


def test_varredura_nao_acusa_codigo_correto_nem_lower_de_outros_nomes() -> None:
    codigo = (
        "e = normalizar_email(texto)\n"
        "Conta.objects.filter(email_normalizado=e)\n"
        "nome = valor.lower()\n"
    )
    assert analisar_codigo(codigo, "ok.py") == []


def test_o_arquivo_da_normalizacao_pode_usar_lower() -> None:
    codigo = "def f(email):\n    return email.strip().lower()\n"
    assert analisar_codigo(codigo, "emails.py", permite_minusculas=True) == []
    assert analisar_codigo(codigo, "outro.py")[0].startswith("outro.py")
