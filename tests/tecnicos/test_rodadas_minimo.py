"""E03-02: alteração do mínimo (acceptance A-8 a A-13 e A-18)."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client

from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory, RodadaFactory

pytestmark = pytest.mark.django_db

MENSAGEM = "As condições da rodada só podem ser alteradas na fase de interesse."
ETAPAS_CONGELADAS = [
    Etapa.FECHAMENTO,
    Etapa.FECHAMENTO_ENCERRADO,
    Etapa.PAGAMENTO,
    Etapa.AGUARDANDO_FORNECEDOR,
]


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _url(fornecedor: Fornecedor) -> str:
    return f"/administracao/fornecedores/{fornecedor.pk}/minimo/"


def _fornecedor_com_rodada(etapa: Etapa) -> Fornecedor:
    fornecedor = FornecedorFactory.create(minimo=Decimal("150.00"))
    RodadaFactory.create(fornecedor=fornecedor, etapa=etapa)
    return fornecedor


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_altera_o_minimo_em_interesse_e_audita(admin_client: Client) -> None:  # A-8, cenário 71
    fornecedor = _fornecedor_com_rodada(Etapa.INTERESSE)
    resposta = admin_client.post(_url(fornecedor), {"minimo": "200,00"})
    assert resposta.status_code == 302
    assert resposta["Location"] == f"/administracao/fornecedores/{fornecedor.pk}/"
    fornecedor.refresh_from_db()
    assert fornecedor.minimo == Decimal("200.00")
    entrada = EntradaAuditoria.objects.get(acao="fornecedor.alterar_minimo")
    assert entrada.alteracoes == {
        "fornecedor": fornecedor.pk,
        "anterior": "150.00",
        "novo": "200.00",
    }


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("etapa", ETAPAS_CONGELADAS)
def test_minimo_congelado_pela_rota(admin_client: Client, etapa: Etapa) -> None:  # A-9, cenário 72
    fornecedor = _fornecedor_com_rodada(etapa)
    resposta = admin_client.post(_url(fornecedor), {"minimo": "200,00"})
    assert resposta.status_code == 409
    assert MENSAGEM in resposta.content.decode()
    fornecedor.refresh_from_db()
    assert fornecedor.minimo == Decimal("150.00")
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("etapa", ETAPAS_CONGELADAS)
def test_minimo_congelado_pelo_servico(etapa: Etapa) -> None:  # A-9, T-23
    admin = ContaFactory.create(administrador=True)
    fornecedor = _fornecedor_com_rodada(etapa)
    with pytest.raises(CondicoesCongeladas, match=MENSAGEM) as erro:
        alterar_minimo(admin, fornecedor, "200,00")
    assert erro.value.codigo == "fora_de_interesse"
    fornecedor.refresh_from_db()
    assert fornecedor.minimo == Decimal("150.00")
    assert EntradaAuditoria.objects.count() == 0


def test_sem_rodada_ativa_recusa_pela_rota_e_pelo_servico(admin_client: Client) -> None:  # A-10
    sem_rodada = FornecedorFactory.create(minimo=Decimal("150.00"))
    terminada = _fornecedor_com_rodada(Etapa.DISPONIVEL_PARA_RETIRADA)
    admin = Conta.objects.get(papel=Papel.ADMINISTRADOR)
    for fornecedor in (sem_rodada, terminada):
        resposta = admin_client.post(_url(fornecedor), {"minimo": "200,00"})
        assert resposta.status_code == 409
        assert MENSAGEM in resposta.content.decode()
        with pytest.raises(CondicoesCongeladas) as erro:
            alterar_minimo(admin, fornecedor, "200,00")
        assert erro.value.codigo == "sem_rodada_ativa"
        fornecedor.refresh_from_db()
        assert fornecedor.minimo == Decimal("150.00")
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.parametrize("valor", ["0", "0,001", "abc"])
def test_minimo_invalido_e_erro_de_formulario(admin_client: Client, valor: str) -> None:  # A-11
    fornecedor = _fornecedor_com_rodada(Etapa.INTERESSE)
    resposta = admin_client.post(_url(fornecedor), {"minimo": valor})
    assert resposta.status_code == 200
    assert "minimo" in resposta.context["form"].errors
    fornecedor.refresh_from_db()
    assert fornecedor.minimo == Decimal("150.00")
    assert EntradaAuditoria.objects.count() == 0


def test_servico_recusa_valor_invalido() -> None:
    admin = ContaFactory.create(administrador=True)
    fornecedor = _fornecedor_com_rodada(Etapa.INTERESSE)
    with pytest.raises(ValidationError):
        alterar_minimo(admin, fornecedor, "0")
    with pytest.raises(ValidationError):
        alterar_minimo(admin, fornecedor, 200.0)  # type: ignore[arg-type]
    fornecedor.refresh_from_db()
    assert fornecedor.minimo == Decimal("150.00")


def test_mesmo_valor_nao_grava_nem_audita(admin_client: Client) -> None:  # A-12
    fornecedor = _fornecedor_com_rodada(Etapa.INTERESSE)
    resposta = admin_client.post(_url(fornecedor), {"minimo": "150,00"})
    assert resposta.status_code == 302
    assert EntradaAuditoria.objects.count() == 0


def test_get_fora_de_interesse_mostra_mensagem_sem_formulario(admin_client: Client) -> None:  # A-13
    fornecedor = _fornecedor_com_rodada(Etapa.FECHAMENTO)
    resposta = admin_client.get(_url(fornecedor))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert MENSAGEM in html
    assert 'name="minimo"' not in html


def test_get_em_interesse_mostra_o_formulario(admin_client: Client) -> None:
    fornecedor = _fornecedor_com_rodada(Etapa.INTERESSE)
    resposta = admin_client.get(_url(fornecedor))
    assert resposta.status_code == 200
    assert 'name="minimo"' in resposta.content.decode()


def test_comprador_nao_pode_ser_autor() -> None:  # A-18
    from apps.rodadas.servicos import abrir_rodada

    comprador = ContaFactory.create()
    fornecedor = _fornecedor_com_rodada(Etapa.INTERESSE)
    outro = FornecedorFactory.create()
    with pytest.raises(PermissionDenied):
        alterar_minimo(comprador, fornecedor, "200,00")
    with pytest.raises(PermissionDenied):
        abrir_rodada(comprador, outro)
    fornecedor.refresh_from_db()
    assert fornecedor.minimo == Decimal("150.00")
    assert not Rodada.objects.filter(fornecedor=outro).exists()
    assert EntradaAuditoria.objects.count() == 0
