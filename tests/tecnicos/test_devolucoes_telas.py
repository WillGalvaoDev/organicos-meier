"""E10-07: telas do administrador para as devoluções (acceptance A-1 a A-12)."""

import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.financeiro.devolucoes import autorizar_devolucao
from apps.financeiro.models import (
    ConfirmacaoDeDevolucaoExcepcional,
    ParcelaDeDevolucao,
)
from apps.notificacoes.models import Notificacao
from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor
from tests.apoio.devolucoes import (
    Arranjo,
    entrar_de_novo,
    levar_a_elegivel,
    montar_tela,
    obrigacao_sem_cobertura,
    parcela_de_fabrica,
)
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
BASE = "/administracao/financeiro/devolucoes/"
PDF = b"%PDF-1.4\n%comprovante\n"


@pytest.fixture(autouse=True)
def midia(settings: Any, tmp_path: Path) -> Path:
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def montada(
    client: Client, webauthn: Any, relogio: RelogioControlado, simulador_pagamentos: Any
) -> tuple[Arranjo, bytes]:
    return montar_tela(client, simulador_pagamentos, relogio)


@pytest.fixture
def a(montada: tuple[Arranjo, bytes]) -> Arranjo:
    return montada[0]


@pytest.fixture
def credencial(montada: tuple[Arranjo, bytes]) -> bytes:
    return montada[1]


def _secao(html: str, grupo: str) -> str:
    achado = re.search(rf'<section id="grupo-{grupo}">(.*?)</section>', html, re.DOTALL)
    assert achado is not None, f"sem a seção {grupo}"
    return achado.group(1)


def test_a_lista_mostra_cada_obrigacao_no_seu_grupo(client: Client, a: Arranjo) -> None:  # A-1
    grupos = {
        "solicitada": "solicitadas",
        "falha_temporaria": "falhas",
        "em_processamento": "em-processamento",
        "falha_definitiva": "falhas",
        "elegivel_excepcional": "elegiveis",
        "concluida": "concluidas",
        "concluida_fora_da_plataforma": "concluidas",
    }
    parcelas = {situacao: parcela_de_fabrica(a, situacao) for situacao in grupos}
    resposta = client.get(BASE)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Autorização não é dinheiro devolvido" in html
    assert f'data-obrigacao="{a.o1.pk}"' in _secao(html, "pendentes")
    for situacao, grupo in grupos.items():
        marca = f'data-obrigacao="{parcelas[situacao].obrigacao_id}"'
        assert marca in _secao(html, grupo), situacao
    linha_o1 = re.search(rf'<tr data-obrigacao="{a.o1.pk}".*?</tr>', html, re.DOTALL)
    assert linha_o1 is not None
    texto = linha_o1.group(0)
    assert "31,25" in texto
    assert "Ocorrência na entrega" in texto
    assert str(a.pedido.pk) in texto
    assert a.comprador.nome in texto
    falha = re.search(
        rf'<tr data-obrigacao="{parcelas["falha_temporaria"].obrigacao_id}".*?</tr>',
        html,
        re.DOTALL,
    )
    assert falha is not None
    assert "indisponivel" in falha.group(0)


def test_autorizar_pela_tela(client: Client, a: Arranjo) -> None:  # A-2
    resposta = client.post(f"{BASE}{a.o1.pk}/autorizar/")
    assert resposta.status_code == 302
    assert resposta["Location"].endswith(f"{BASE}{a.o1.pk}/")
    parcela = ParcelaDeDevolucao.objects.get(obrigacao=a.o1)
    assert parcela.situacao == "solicitada"
    detalhe = client.get(resposta["Location"])
    assert "Devolução solicitada ao provedor" in detalhe.content.decode()
    (aviso,) = Notificacao.objects.filter(conta=a.comprador, evento="estorno")
    assert aviso.titulo == "Estorno solicitado"
    assert "31,25" in aviso.corpo
    assert "Ocorrência na entrega" in aviso.corpo


def test_autorizar_exige_passkey_recente(
    client: Client, a: Arranjo, relogio: RelogioControlado
) -> None:  # A-3
    relogio.avancar(timedelta(hours=2))
    resposta = client.post(f"{BASE}{a.o1.pk}/autorizar/")
    assert resposta.status_code == 302
    assert "reautenticar" in resposta["Location"] or "reauthenticate" in resposta["Location"]
    assert ParcelaDeDevolucao.objects.count() == 0


ROTAS = [
    ("get", ""),
    ("get", "{o}/"),
    ("post", "{o}/autorizar/"),
    ("post", "{o}/tentar-de-novo/"),
    ("get", "{o}/excepcional/"),
    ("post", "{o}/excepcional/"),
    ("get", "{o}/comprovante/"),
]


@pytest.mark.parametrize(("metodo", "rota"), ROTAS)
def test_so_o_administrador_acessa(a: Arranjo, metodo: str, rota: str) -> None:  # A-4
    caminho = BASE + rota.format(o=a.o1.pk)
    fornecedor = ContaFactory.create(fornecedor=True)
    for conta in (a.comprador, fornecedor):
        cliente = Client()
        cliente.force_login(conta)
        assert getattr(cliente, metodo)(caminho).status_code == 403
    anonimo = getattr(Client(), metodo)(caminho)
    assert anonimo.status_code == 302
    assert "/entrar/" in anonimo["Location"]
    assert ParcelaDeDevolucao.objects.count() == 0


def test_provedor_fora_do_ar_na_autorizacao(client: Client, a: Arranjo) -> None:  # A-5
    a.sim.indisponivel()
    resposta = client.post(f"{BASE}{a.o1.pk}/autorizar/")
    assert resposta.status_code == 503
    assert "Não foi possível consultar o provedor; tente de novo" in resposta.content.decode()
    assert ParcelaDeDevolucao.objects.count() == 0


def test_obrigacao_sem_cobertura_responde_409(client: Client, a: Arranjo) -> None:  # A-6
    obrigacao = obrigacao_sem_cobertura(a)
    resposta = client.post(f"{BASE}{obrigacao.pk}/autorizar/")
    assert resposta.status_code == 409
    assert "cobrir antes" in resposta.content.decode()
    assert ParcelaDeDevolucao.objects.count() == 0


def test_tentar_de_novo_antecipa_a_chamada(client: Client, a: Arranjo) -> None:  # A-7
    a.sim.falhar_proximas(1, operacao="estornar")
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "falha_temporaria"
    resposta = client.post(f"{BASE}{a.o1.pk}/tentar-de-novo/")
    assert resposta.status_code == 302
    chamada = ChamadaAoProvedor.objects.get(operacao="estornar")
    assert chamada.proxima_em <= agora()


def test_acoes_forjadas_na_parcela_concluida_dao_409(client: Client, a: Arranjo) -> None:  # A-8
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert client.post(f"{BASE}{a.o1.pk}/tentar-de-novo/").status_code == 409
    assert client.post(f"{BASE}{a.o1.pk}/excepcional/", _dados()).status_code == 409
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"


def _dados(**campos: Any) -> dict[str, Any]:
    return {
        "meio": "pix",
        "identificacao": "E2E-123",
        "justificativa": "Pix feito direto ao comprador",
        "comprovante": SimpleUploadedFile("c.pdf", PDF, content_type="application/pdf"),
        **campos,
    }


def test_confirmacao_excepcional_pela_tela(
    client: Client, a: Arranjo, credencial: bytes
) -> None:  # A-9
    parcela = levar_a_elegivel(a)
    entrar_de_novo(client, credencial, a.admin)
    formulario = client.get(f"{BASE}{a.o1.pk}/excepcional/")
    assert formulario.status_code == 200
    assert 'enctype="multipart/form-data"' in formulario.content.decode()
    resposta = client.post(f"{BASE}{a.o1.pk}/excepcional/", _dados())
    assert resposta.status_code == 302
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida_fora_da_plataforma"
    assert ConfirmacaoDeDevolucaoExcepcional.objects.count() == 1
    avisos = list(Notificacao.objects.filter(conta=a.comprador, evento="estorno"))
    realizacao = [n for n in avisos if n.titulo == "Devolução realizada"]
    assert len(realizacao) == 1
    assert "por Pix" in realizacao[0].corpo
    assert "E2E-123" not in realizacao[0].corpo


def test_excepcional_com_devolucao_pendente_responde_409(
    client: Client, a: Arranjo
) -> None:  # A-10
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    assert client.get(f"{BASE}{a.o1.pk}/excepcional/").status_code == 409
    resposta = client.post(f"{BASE}{a.o1.pk}/excepcional/", _dados())
    assert resposta.status_code == 409
    assert "há devolução pendente na plataforma" in resposta.content.decode()
    assert ConfirmacaoDeDevolucaoExcepcional.objects.count() == 0


def test_comprovante_ausente_ou_invalido_volta_400(
    client: Client, a: Arranjo, credencial: bytes
) -> None:  # A-11
    levar_a_elegivel(a)
    entrar_de_novo(client, credencial, a.admin)
    sem_arquivo = _dados()
    del sem_arquivo["comprovante"]
    invalido = _dados(comprovante=SimpleUploadedFile("c.pdf", b"texto puro"))
    for dados in (sem_arquivo, invalido):
        resposta = client.post(f"{BASE}{a.o1.pk}/excepcional/", dados)
        assert resposta.status_code == 400
        assert 'role="alert"' in resposta.content.decode()
    assert ConfirmacaoDeDevolucaoExcepcional.objects.count() == 0


def test_so_o_administrador_baixa_o_comprovante(
    client: Client, a: Arranjo, credencial: bytes
) -> None:  # A-12
    levar_a_elegivel(a)
    entrar_de_novo(client, credencial, a.admin)
    client.post(f"{BASE}{a.o1.pk}/excepcional/", _dados())
    baixado = client.get(f"{BASE}{a.o1.pk}/comprovante/")
    assert baixado.status_code == 200
    assert baixado["Content-Disposition"].startswith("attachment")
    assert baixado["Content-Type"] == "application/pdf"
    assert b"".join(baixado.streaming_content) == PDF  # type: ignore[attr-defined]
    outro = ContaFactory.create()
    for conta in (a.comprador, outro):
        cliente = Client()
        cliente.force_login(conta)
        assert cliente.get(f"{BASE}{a.o1.pk}/comprovante/").status_code == 403
