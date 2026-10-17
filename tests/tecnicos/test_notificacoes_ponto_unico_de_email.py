"""E04-05: todo e-mail da aplicação sai por `enviar_email` (acceptance A-8)."""

import re
from pathlib import Path

CHAMADA = re.compile(r"(?<!def )\b(EmailMessage|EmailMultiAlternatives|send_mail|send_mass_mail)\(")
PERMITIDO = Path("apps/notificacoes/canais.py")


def test_so_o_canal_de_email_chama_a_api_de_email_do_django() -> None:  # A-8
    encontrados = []
    for arquivo in Path("apps").rglob("*.py"):
        if arquivo.as_posix() == PERMITIDO.as_posix():
            continue
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if CHAMADA.search(linha):
                encontrados.append(f"{arquivo.as_posix()}:{numero}")
    assert encontrados == []
