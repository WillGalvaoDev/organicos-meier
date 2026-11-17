"""Cenário 59 da especificação funcional: o banimento vale só para o endereço de e-mail (E16-07).

IP, dispositivo e telefone não são bloqueados. Teste de caracterização: o comportamento já existia
(E02-08), então passou na primeira execução.
"""

import pytest
from django.test import Client

from apps.contas.models import EmailBanido
from apps.contas.moderacao import remover
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

SENHA = "senha-forte-9271!"
TELEFONE = "+5521999990000"
IP = "203.0.113.7"


def test_cenario_59_ip_dispositivo_e_telefone_nao_sao_bloqueados() -> None:
    admin = ContaFactory.create(administrador=True)
    banida = ContaFactory.create(email_normalizado="ana@x.com", telefone=TELEFONE)
    outra = ContaFactory.create(email_normalizado="bia@x.com", telefone=TELEFONE)
    outra.set_password(SENHA)
    outra.save()
    dispositivo = Client(REMOTE_ADDR=IP)  # o mesmo navegador (cookies) e o mesmo IP da conta banida
    dispositivo.get("/entrar/")
    remover(admin, banida)
    assert EmailBanido.objects.filter(email_normalizado="ana@x.com").exists()
    dispositivo.post("/entrar/", {"login": "bia@x.com", "password": SENHA})
    assert "_auth_user_id" in dispositivo.session
