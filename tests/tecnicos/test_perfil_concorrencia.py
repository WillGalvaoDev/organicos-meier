"""E02-09, correção E02-R01: o perfil não restaura valores antigos (acceptance A-20 a A-25).

A gravação do perfil altera só os campos do perfil e decide tudo a partir da linha travada. A
intercalação determinística envolve `views.atualizar_perfil` por `monkeypatch`: a alteração
concorrente acontece depois da leitura da view e antes da chamada à função original, que é a função
sob teste e nunca é substituída.
"""

import re
import threading
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.contas import views
from apps.contas.models import Conta, EmailBanido, Situacao
from apps.contas.moderacao import remover, suspender
from apps.contas.perfil import atualizar_perfil
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio import imagens
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db(transaction=True)

E164 = "+5521999998888"


@pytest.fixture(autouse=True)
def _midia_temporaria(settings: Any, tmp_path: Path) -> None:
    settings.MEDIA_ROOT = tmp_path


# Teste do revisor (E02-10/review.md, revalidação 8f4dc36), copiado sem alteração do corpo,
# exceto a expectativa do parâmetro `remover`, que passa a ser 403 com a situação `removida` e o
# nome inalterado (spec E02-09, item 4 da regra).
# Nome original: test_perfil_preserva_alteracao_concorrente
@pytest.mark.parametrize("acao", ["suspender", "remover", "senha"])
def test_perfil_preserva_alteracao_concorrente(client, monkeypatch, acao):  # type: ignore[no-untyped-def]
    admin = ContaFactory.create(administrador=True)
    conta = ContaFactory.create()
    conta.set_password("senha-antiga-forte-9271!")
    conta.save()
    client.force_login(conta)
    original = views.atualizar_perfil  # type: ignore[attr-defined]

    def intercalar(lida, **kwargs):  # type: ignore[no-untyped-def]
        atual = Conta.objects.get(pk=lida.pk)
        if acao == "suspender":
            suspender(admin, atual)
        elif acao == "remover":
            remover(admin, atual)
        else:
            atual.set_password("senha-nova-forte-9262!")
            atual.save(update_fields=["password"])
        return original(lida, **kwargs)

    monkeypatch.setattr(views, "atualizar_perfil", intercalar)
    nome_anterior = conta.nome
    resposta = client.post("/perfil/", {"nome": "Nome editado"})
    conta.refresh_from_db()
    if acao == "remover":
        assert resposta.status_code == 403
        assert conta.nome == nome_anterior
    else:
        assert resposta.status_code == 302
        assert conta.nome == "Nome editado"
    if acao == "senha":
        assert conta.check_password("senha-nova-forte-9262!")
    else:
        assert conta.situacao == {"suspender": "suspensa", "remover": "removida"}[acao]


def _intercalar(monkeypatch: pytest.MonkeyPatch, acao: Any) -> None:
    original = views.atualizar_perfil  # type: ignore[attr-defined]

    def intercalar(lida: Conta, **kwargs: Any) -> Any:
        acao(Conta.objects.get(pk=lida.pk))
        return original(lida, **kwargs)

    monkeypatch.setattr(views, "atualizar_perfil", intercalar)


def _comprador(**campos: Any) -> tuple[Client, Conta]:
    conta = ContaFactory.create(email_normalizado="ana@x.com", nome="Ana", **campos)
    cliente = Client()
    cliente.force_login(conta)
    return cliente, conta


def _arquivos(tmp_path: Path) -> list[Path]:
    return [p for p in tmp_path.rglob("*") if p.is_file()]


def test_suspensao_depois_da_leitura_e_preservada(monkeypatch: pytest.MonkeyPatch) -> None:
    # A-20
    admin = ContaFactory.create(administrador=True)
    cliente, conta = _comprador()
    _intercalar(monkeypatch, lambda atual: suspender(admin, atual))
    resposta = cliente.post("/perfil/", {"nome": "Ana Souza"})
    assert resposta.status_code == 302
    conta.refresh_from_db()
    assert conta.nome == "Ana Souza"
    assert conta.situacao == Situacao.SUSPENSA
    assert conta.pode_adicionar_interesse is False
    assert EntradaAuditoria.objects.filter(acao="conta.reativar").count() == 0
    assert EntradaAuditoria.objects.filter(acao="conta.suspender").count() == 1


def test_remocao_depois_da_leitura_recusa_o_perfil_e_nao_grava_avatar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:  # A-21 (cenário 58)
    admin = ContaFactory.create(administrador=True)
    cliente, conta = _comprador()
    _intercalar(monkeypatch, lambda atual: remover(admin, atual))
    arquivo = SimpleUploadedFile("a.png", imagens.png(40, 40), content_type="image/png")
    resposta = cliente.post(
        "/perfil/",
        {"nome": "Nome novo", "telefone": "(21) 99999-8888", "whatsapp": "on", "avatar": arquivo},
    )
    assert resposta.status_code == 403
    conta.refresh_from_db()
    assert conta.nome == "Ana"
    assert conta.telefone is None
    assert conta.situacao == Situacao.REMOVIDA
    assert EmailBanido.objects.filter(email_normalizado="ana@x.com").exists()
    assert EntradaAuditoria.objects.filter(acao__startswith="perfil.").count() == 0
    assert _arquivos(tmp_path) == []
    assert not conta.avatar


def test_senha_trocada_depois_da_leitura_e_preservada(monkeypatch: pytest.MonkeyPatch) -> None:
    # A-22
    conta = ContaFactory.create(email_normalizado="ana@x.com", nome="Ana")
    conta.set_password("S1-senha-forte-1111!")
    conta.save()
    cliente = Client()
    cliente.force_login(conta)  # a sessão nasce depois da senha S1 (o hash da sessão a acompanha)

    def trocar(atual: Conta) -> None:
        atual.set_password("S2-senha-forte-2222!")
        atual.save(update_fields=["password"])

    _intercalar(monkeypatch, trocar)
    assert cliente.post("/perfil/", {"nome": "Ana Souza"}).status_code == 302
    conta.refresh_from_db()
    assert conta.check_password("S2-senha-forte-2222!")
    assert not conta.check_password("S1-senha-forte-1111!")


def test_gravacao_do_perfil_so_atribui_as_colunas_do_perfil() -> None:  # A-23
    cliente, conta = _comprador()
    with CaptureQueriesContext(connection) as consultas:
        resposta = cliente.post(
            "/perfil/", {"nome": "Ana Souza", "telefone": "(21) 99999-8888", "whatsapp": "on"}
        )
    assert resposta.status_code == 302
    sqls = [c["sql"] for c in consultas.captured_queries]
    atualizacoes = [i for i, sql in enumerate(sqls) if sql.startswith('UPDATE "contas_conta"')]
    assert len(atualizacoes) == 1, [sql for sql in sqls if "contas_conta" in sql]
    atribuidas = set(re.findall(r'"(\w+)" =', sqls[atualizacoes[0]].split(" WHERE ")[0]))
    assert atribuidas == {"nome", "telefone", "whatsapp_consentido_em", "avatar"}
    travas = [
        i
        for i, sql in enumerate(sqls)
        if 'FROM "contas_conta"' in sql and sql.rstrip().endswith("FOR UPDATE")
    ]
    assert travas
    assert min(travas) < atualizacoes[0]
    conta.refresh_from_db()
    assert conta.nome == "Ana Souza"


def test_dois_consentimentos_simultaneos_geram_uma_auditoria() -> None:  # A-24
    for repeticao in range(10):
        conta = ContaFactory.create(email_normalizado=f"ana{repeticao}@x.com", telefone=E164)
        lidas = [Conta.objects.get(pk=conta.pk), Conta.objects.get(pk=conta.pk)]

        def consentir(barreira: threading.Barrier, lida: Conta = lidas[0]) -> None:
            barreira.wait(timeout=5)
            atualizar_perfil(lida, nome="Ana", telefone=E164, whatsapp=True)

        def consentir_outra(barreira: threading.Barrier, lida: Conta = lidas[1]) -> None:
            barreira.wait(timeout=5)
            atualizar_perfil(lida, nome="Ana", telefone=E164, whatsapp=True)

        resultados = executar_em_paralelo(consentir, consentir_outra)
        assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
        conta.refresh_from_db()
        assert conta.whatsapp_consentido_em is not None
        assert (
            EntradaAuditoria.objects.filter(
                acao="perfil.whatsapp_consentir", objeto_id=str(conta.pk)
            ).count()
            == 1
        ), repeticao


def test_perfil_e_suspensao_simultaneos_terminam_suspensos_com_nome_novo() -> None:  # A-25
    admin = ContaFactory.create(administrador=True)
    for repeticao in range(10):
        conta = ContaFactory.create(email_normalizado=f"bia{repeticao}@x.com", nome="Bia")
        lida = Conta.objects.get(pk=conta.pk)

        def perfil(barreira: threading.Barrier, lida: Conta = lida) -> None:
            barreira.wait(timeout=5)
            atualizar_perfil(lida, nome="Bia Nova", telefone=None, whatsapp=False)

        def suspensao(barreira: threading.Barrier, pk: int = conta.pk) -> None:
            barreira.wait(timeout=5)
            suspender(admin, Conta.objects.get(pk=pk))

        resultados = executar_em_paralelo(perfil, suspensao)
        assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
        conta.refresh_from_db()
        assert conta.situacao == Situacao.SUSPENSA, repeticao
        assert conta.nome == "Bia Nova"
        assert (
            EntradaAuditoria.objects.filter(acao="conta.suspender", objeto_id=str(conta.pk)).count()
            == 1
        )
