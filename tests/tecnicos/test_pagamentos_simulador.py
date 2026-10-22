"""E07-01: interface do provedor e simulador de pagamentos (acceptance A-1 a A-14, A-17, A-18)."""

# A spec fixa `ValueError` sem mensagem nos controles; o tipo é o contrato.
# ruff: noqa: PT011

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from apps.nucleo.tempo import InstanteSemFuso
from apps.pagamentos.provedor import (
    AvisoDoProvedor,
    AvisoInvalido,
    NovaCobranca,
    PagamentoConsultado,
    PagamentoNaoEncontrado,
    ProvedorIndisponivel,
    RecusaDoProvedor,
    SituacaoNoProvedor,
    TipoDeMovimentoNoProvedor,
    obter_provedor,
)
from apps.simulador_pagamentos.models import AvisoSimulado, CobrancaSimulada
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
T = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)
AMANHA = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)


def nova(**campos: Any) -> NovaCobranca:
    base: dict[str, Any] = {
        "chave_idempotencia": "k1",
        "referencia_externa": "ref-1",
        "valor": D("45.90"),
        "descricao": "Pedido de teste",
        "expira_em": AMANHA,
        "meio": "pix",
    }
    return NovaCobranca(**{**base, **campos})


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    relogio.congelar(T)
    return simulador_pagamentos


def criar(**campos: Any) -> str:
    return obter_provedor().criar_cobranca(nova(**campos)).pagamento.id_externo


@pytest.mark.acceptance
def test_criar_cobranca_devolve_o_pagamento_pendente(sim: Any) -> None:  # A-1
    criada = obter_provedor().criar_cobranca(nova())
    pagamento = criada.pagamento
    assert pagamento.provedor == "simulador"
    assert pagamento.situacao == SituacaoNoProvedor.PENDENTE
    assert pagamento.id_externo.startswith("sim-")
    assert pagamento.referencia_externa == "ref-1"
    assert pagamento.valor == D("45.90")
    assert pagamento.criado_em == T
    assert pagamento.aprovado_em is None
    assert pagamento.expira_em == AMANHA
    assert pagamento.consultado_em == T
    assert "pix_copia_e_cola" in criada.dados_para_pagar
    assert CobrancaSimulada.objects.count() == 1
    assert AvisoSimulado.objects.count() == 0


def test_a_mesma_chave_devolve_a_mesma_cobranca(sim: Any) -> None:  # A-2
    primeira = obter_provedor().criar_cobranca(nova())
    repetida = obter_provedor().criar_cobranca(nova())
    assert repetida.pagamento.id_externo == primeira.pagamento.id_externo
    assert CobrancaSimulada.objects.count() == 1
    with pytest.raises(RecusaDoProvedor) as erro:
        obter_provedor().criar_cobranca(nova(valor=D("46.00")))
    assert erro.value.codigo == "chave_reutilizada"
    assert CobrancaSimulada.objects.count() == 1


@pytest.mark.parametrize(
    "campos",
    [
        {"valor": D("0")},
        {"valor": D("-1")},
        {"valor": D("45.905")},
        {"valor": 45.9},
        {"chave_idempotencia": ""},
        {"chave_idempotencia": "x" * 65},
        {"referencia_externa": ""},
        {"descricao": "x" * 121},
        {"expira_em": datetime(2026, 11, 3, 13, 0)},  # noqa: DTZ001
        {"meio": "cartao"},
    ],
    ids=[
        "zero",
        "negativo",
        "tres-casas",
        "float",
        "chave-vazia",
        "chave-longa",
        "referencia-vazia",
        "descricao-longa",
        "sem-fuso",
        "cartao",
    ],
)
def test_pedido_invalido_e_recusado_antes_do_provedor(campos: dict[str, Any], sim: Any) -> None:
    # A-3
    with pytest.raises((ValueError, InstanteSemFuso)):
        nova(**campos)
    assert CobrancaSimulada.objects.count() == 0


def test_expiracao_que_nao_e_futura_e_recusada(sim: Any) -> None:  # A-3
    with pytest.raises(RecusaDoProvedor) as erro:
        obter_provedor().criar_cobranca(nova(expira_em=T))
    assert erro.value.codigo == "expiracao_invalida"
    assert CobrancaSimulada.objects.count() == 0


def test_aprovacao_informada_depois(sim: Any, relogio: RelogioControlado) -> None:  # A-4
    # A-4 aprova em 12:59:30, antes do 13:00 do A-1; como `em` anterior a `criado_em` é
    # `ValueError` (A-5), a cobrança deste teste nasce às 12:50 (conflito dos critérios).
    relogio.congelar(T - timedelta(minutes=10))
    id_externo = criar()
    relogio.congelar(T + timedelta(minutes=10))
    aprovada_em = datetime(2026, 11, 2, 12, 59, 30, tzinfo=UTC)
    sim.aprovar(id_externo, em=aprovada_em)
    pagamento = obter_provedor().consultar_pagamento(id_externo)
    assert pagamento.situacao == SituacaoNoProvedor.APROVADO
    assert pagamento.aprovado_em == aprovada_em
    assert pagamento.consultado_em == T + timedelta(minutes=10)
    avisos = list(AvisoSimulado.objects.all())
    assert len(avisos) == 1
    aviso = avisos[0]
    assert aviso.entregas == 0
    assert aviso.id_externo == id_externo


def test_aprovacao_depois_do_vencimento_ou_do_cancelamento(sim: Any) -> None:  # A-5
    expirada, cancelada, recusada, repetida = (
        criar(chave_idempotencia=f"k{i}") for i in range(1, 5)
    )
    sim.expirar(expirada)
    sim.aprovar(expirada)
    obter_provedor().cancelar_cobranca(cancelada)
    sim.aprovar(cancelada)
    for id_externo in (expirada, cancelada):
        assert obter_provedor().consultar_pagamento(id_externo).situacao == (
            SituacaoNoProvedor.APROVADO
        )

    sim.recusar(recusada)
    sim.aprovar(repetida)
    outra = criar(chave_idempotencia="k5")
    avisos = AvisoSimulado.objects.count()
    with pytest.raises(ValueError):
        sim.aprovar(recusada)
    with pytest.raises(ValueError):
        sim.aprovar(repetida)
    with pytest.raises(ValueError):
        sim.aprovar(outra, em=T - timedelta(seconds=1))
    assert AvisoSimulado.objects.count() == avisos
    assert obter_provedor().consultar_pagamento(recusada).situacao == SituacaoNoProvedor.RECUSADO
    assert obter_provedor().consultar_pagamento(outra).situacao == SituacaoNoProvedor.PENDENTE


def test_recusar_e_expirar_so_a_partir_de_pendente(sim: Any) -> None:  # A-5
    aprovada, cancelada = criar(chave_idempotencia="k1"), criar(chave_idempotencia="k2")
    sim.aprovar(aprovada)
    obter_provedor().cancelar_cobranca(cancelada)
    antes = AvisoSimulado.objects.count()
    for id_externo in (aprovada, cancelada):
        with pytest.raises(ValueError):
            sim.recusar(id_externo)
        with pytest.raises(ValueError):
            sim.expirar(id_externo)
    assert AvisoSimulado.objects.count() == antes


def test_cancelar_so_muda_a_pendente(sim: Any) -> None:  # A-6
    pendente, aprovada = criar(chave_idempotencia="k1"), criar(chave_idempotencia="k2")
    sim.aprovar(aprovada)
    avisos = AvisoSimulado.objects.count()
    cancelada = obter_provedor().cancelar_cobranca(pendente)
    assert cancelada.situacao == SituacaoNoProvedor.CANCELADO
    assert AvisoSimulado.objects.count() == avisos + 1
    mantida = obter_provedor().cancelar_cobranca(aprovada)
    assert mantida.situacao == SituacaoNoProvedor.APROVADO
    assert AvisoSimulado.objects.count() == avisos + 1


def test_cancelamento_que_coincide_com_o_pagamento(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-7
    id_externo = criar()
    destino = T + timedelta(minutes=20)
    sim.aprovar_no_cancelamento(id_externo, em=destino)
    relogio.congelar(destino)
    resultado = obter_provedor().cancelar_cobranca(id_externo)
    assert resultado.situacao == SituacaoNoProvedor.APROVADO
    assert resultado.aprovado_em == destino
    assert AvisoSimulado.objects.count() == 1


def test_buscar_por_referencia(sim: Any, relogio: RelogioControlado) -> None:  # A-8
    primeira = criar(chave_idempotencia="k1")
    relogio.congelar(T + timedelta(minutes=1))
    segunda = criar(chave_idempotencia="k2")
    criar(chave_idempotencia="k3", referencia_externa="ref-2")
    sim.aprovar(primeira)
    sim.aprovar(segunda)
    achados = obter_provedor().buscar_por_referencia("ref-1")
    assert [p.id_externo for p in achados] == [primeira, segunda]
    assert all(p.situacao == SituacaoNoProvedor.APROVADO for p in achados)
    assert obter_provedor().buscar_por_referencia("ref-x") == []


def test_identificador_desconhecido(sim: Any) -> None:  # A-9
    with pytest.raises(PagamentoNaoEncontrado):
        obter_provedor().consultar_pagamento("sim-999")
    with pytest.raises(PagamentoNaoEncontrado):
        obter_provedor().cancelar_cobranca("sim-999")


def test_provedor_indisponivel(sim: Any) -> None:  # A-10
    provedor = obter_provedor()
    sim.indisponivel()
    operacoes = [
        lambda: provedor.criar_cobranca(nova()),
        lambda: provedor.consultar_pagamento("sim-1"),
        lambda: provedor.buscar_por_referencia("ref-1"),
        lambda: provedor.cancelar_cobranca("sim-1"),
        lambda: provedor.verificar_aviso(b"{}", {}, {}),
    ]
    for operacao in operacoes:
        with pytest.raises(ProvedorIndisponivel):
            operacao()
    assert CobrancaSimulada.objects.count() == 0
    sim.normalizar()
    provedor.criar_cobranca(nova())
    assert CobrancaSimulada.objects.count() == 1


def test_tempo_esgotado_depois_de_o_provedor_aceitar(sim: Any) -> None:  # A-11
    sim.falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=True)
    with pytest.raises(ProvedorIndisponivel):
        obter_provedor().criar_cobranca(nova())
    assert CobrancaSimulada.objects.count() == 1
    repetida = obter_provedor().criar_cobranca(nova())
    assert repetida.pagamento.id_externo == CobrancaSimulada.objects.get().id_externo
    assert CobrancaSimulada.objects.count() == 1


def test_falha_antes_de_executar_nao_grava(sim: Any) -> None:  # A-11
    sim.falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=False)
    with pytest.raises(ProvedorIndisponivel):
        obter_provedor().criar_cobranca(nova())
    assert CobrancaSimulada.objects.count() == 0
    obter_provedor().criar_cobranca(nova())
    assert CobrancaSimulada.objects.count() == 1


def test_falhar_proximas_de_outra_operacao_nao_atinge(sim: Any) -> None:  # A-11
    sim.falhar_proximas(1, operacao="cancelar_cobranca")
    id_externo = criar()
    with pytest.raises(ProvedorIndisponivel):
        obter_provedor().cancelar_cobranca(id_externo)
    assert obter_provedor().cancelar_cobranca(id_externo).situacao == (SituacaoNoProvedor.CANCELADO)


def test_atraso_de_consistencia(sim: Any) -> None:  # A-12
    id_externo = criar()
    sim.atrasar_consistencia(id_externo, consultas=2)
    sim.aprovar(id_externo)
    consultas = [obter_provedor().consultar_pagamento(id_externo) for _ in range(3)]
    assert [c.situacao for c in consultas] == [
        SituacaoNoProvedor.PENDENTE,
        SituacaoNoProvedor.PENDENTE,
        SituacaoNoProvedor.APROVADO,
    ]
    assert consultas[0].aprovado_em is None
    assert consultas[1].aprovado_em is None
    assert consultas[2].aprovado_em == T


def test_atraso_de_consistencia_vale_tambem_para_a_busca(sim: Any) -> None:  # A-12
    id_externo = criar()
    sim.aprovar(id_externo)
    sim.atrasar_consistencia(id_externo, consultas=1)
    atrasado = obter_provedor().buscar_por_referencia("ref-1")
    assert [p.situacao for p in atrasado] == [SituacaoNoProvedor.PENDENTE]
    atual = obter_provedor().buscar_por_referencia("ref-1")
    assert [p.situacao for p in atual] == [SituacaoNoProvedor.APROVADO]


class Receptor:
    def __init__(self) -> None:
        self.corpos: list[bytes] = []

    def __call__(self, corpo: bytes, cabecalhos: dict[str, str]) -> int:
        self.corpos.append(corpo)
        return 200


def tres_avisos(sim: Any) -> list[AvisoSimulado]:
    for i in (1, 2, 3):
        sim.aprovar(criar(chave_idempotencia=f"k{i}"))
    avisos = list(AvisoSimulado.objects.order_by("pk"))
    assert len(avisos) == 3
    return avisos


def test_avisos_atrasados_repetidos_fora_de_ordem_e_perdidos(sim: Any) -> None:  # A-13
    a1, a2, a3 = tres_avisos(sim)
    receptor = Receptor()
    codigos = sim.entregar_avisos([a3, a1], vezes=2, receptor=receptor)
    sim.descartar(a2)
    assert codigos == [200, 200, 200, 200]
    ordem = [json.loads(corpo)["id_evento"] for corpo in receptor.corpos]
    assert ordem == [a3.id_evento, a3.id_evento, a1.id_evento, a1.id_evento]
    a1.refresh_from_db()
    a2.refresh_from_db()
    a3.refresh_from_db()
    assert (a1.entregas, a2.entregas, a3.entregas) == (2, 0, 2)
    assert sim.avisos_pendentes() == []


def test_avisos_pendentes_na_ordem_de_criacao(sim: Any) -> None:  # A-13
    a1, a2, a3 = tres_avisos(sim)
    assert sim.avisos_pendentes() == [a1, a2, a3]
    sim.entregar_avisos([a2], receptor=Receptor())
    assert sim.avisos_pendentes() == [a1, a3]


def test_reemitir_aviso_nao_muda_a_situacao(sim: Any) -> None:  # A-13
    id_externo = criar()
    sim.aprovar(id_externo)
    novo = sim.reemitir_aviso(id_externo)
    assert novo.id_externo == id_externo
    assert AvisoSimulado.objects.count() == 2
    assert len({a.id_evento for a in AvisoSimulado.objects.all()}) == 2
    assert obter_provedor().consultar_pagamento(id_externo).situacao == (
        SituacaoNoProvedor.APROVADO
    )


def test_verificacao_do_aviso(sim: Any) -> None:  # A-14
    aviso = tres_avisos(sim)[0]
    corpo, cabecalhos = sim.corpo_e_cabecalhos(aviso)
    provedor = obter_provedor()
    assert provedor.verificar_aviso(corpo, cabecalhos, {}) == AvisoDoProvedor(
        aviso.id_evento, "pagamento", aviso.id_externo
    )
    adulterado = bytes([corpo[0] ^ 1]) + corpo[1:]
    outra = {"X-Simulador-Assinatura": "sha256=" + "0" * 64}
    casos = [(adulterado, cabecalhos), (corpo, {}), (corpo, outra), (b"nao e json", cabecalhos)]
    for corpo_ruim, cabecalhos_ruins in casos:
        with pytest.raises(AvisoInvalido):
            provedor.verificar_aviso(corpo_ruim, cabecalhos_ruins, {})


def test_corpo_que_nao_e_json_com_assinatura_valida_e_invalido(sim: Any) -> None:  # A-14
    import hashlib
    import hmac

    from django.conf import settings

    corpo = b"nao e json"
    assinatura = hmac.new(
        settings.SEGREDO_AVISOS_SIMULADOR.encode(), corpo, hashlib.sha256
    ).hexdigest()
    with pytest.raises(AvisoInvalido):
        obter_provedor().verificar_aviso(
            corpo, {"X-Simulador-Assinatura": f"sha256={assinatura}"}, {}
        )


def test_verificacao_aceita_cabecalho_em_qualquer_caixa(sim: Any) -> None:  # A-14
    aviso = tres_avisos(sim)[0]
    corpo, cabecalhos = sim.corpo_e_cabecalhos(aviso)
    minusculo = {nome.lower(): valor for nome, valor in cabecalhos.items()}
    assert obter_provedor().verificar_aviso(corpo, minusculo, {}).id_evento == aviso.id_evento


def test_o_log_nao_leva_dado_do_pedido(sim: Any, caplog: pytest.LogCaptureFixture) -> None:
    # A-17
    caplog.set_level(logging.DEBUG)
    id_externo = criar()
    sim.aprovar(id_externo)
    obter_provedor().consultar_pagamento(id_externo)
    obter_provedor().buscar_por_referencia("ref-1")
    obter_provedor().cancelar_cobranca(id_externo)
    sim.entregar_avisos(receptor=Receptor())
    mensagens = [r.getMessage() for r in caplog.records if r.name.startswith("apps.simulador")]
    assert mensagens
    for mensagem in mensagens:
        for proibido in ("45.90", "45,90", "ref-1", "Pedido de teste", "SIMULADO-"):
            assert proibido not in mensagem, mensagem
    assert any(id_externo in m for m in mensagens)


def sequencia(sim: Any) -> dict[str, Any]:
    primeira = criar(chave_idempotencia="k1")
    criar(chave_idempotencia="k2")
    sim.aprovar(primeira, em=T + timedelta(minutes=5))
    achados = obter_provedor().buscar_por_referencia("ref-1")
    return {
        "situacoes": [p.situacao for p in achados],
        "aprovado_em": [p.aprovado_em for p in achados],
        "criado_em": [p.criado_em for p in achados],
        "ordem": [p.id_externo == primeira for p in achados],
    }


def test_a_mesma_sequencia_da_o_mesmo_resultado(sim: Any) -> None:  # A-18
    primeiro = sequencia(sim)
    assert primeiro["situacoes"] == [SituacaoNoProvedor.APROVADO, SituacaoNoProvedor.PENDENTE]
    AvisoSimulado.objects.all().delete()
    CobrancaSimulada.objects.all().delete()
    assert sequencia(sim) == primeiro


def test_producao_recusa_o_simulador_em_obter_provedor(settings: Any) -> None:  # A-9
    settings.AMBIENTE = "producao"
    with pytest.raises(ImproperlyConfigured, match="não pode ser usado em produção"):
        obter_provedor()
    settings.AMBIENTE = "homologacao"
    assert obter_provedor().nome == "simulador"


SP = ZoneInfo("America/Sao_Paulo")


def em_sp(instante: datetime) -> datetime:
    return instante.astimezone(SP)


def confere_utc(pagamento: Any, expira_em: datetime = AMANHA) -> None:
    assert pagamento.criado_em.tzinfo is UTC
    assert pagamento.expira_em.tzinfo is UTC
    assert pagamento.consultado_em.tzinfo is UTC
    assert pagamento.expira_em == expira_em
    if pagamento.aprovado_em is not None:
        assert pagamento.aprovado_em.tzinfo is UTC


def test_toda_resposta_do_simulador_vem_em_utc(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-21, E07-R04
    provedor = obter_provedor()
    local = nova(expira_em=em_sp(AMANHA))
    assert local.expira_em.utcoffset() != timedelta(0)
    criada = provedor.criar_cobranca(local).pagamento
    confere_utc(criada)

    segunda = criar(chave_idempotencia="k2", expira_em=em_sp(AMANHA))
    sim.aprovar_no_cancelamento(segunda, em=em_sp(T))
    cancelada = provedor.cancelar_cobranca(segunda)
    assert cancelada.situacao == SituacaoNoProvedor.APROVADO
    confere_utc(cancelada)
    assert cancelada.aprovado_em == T

    relogio.congelar(T - timedelta(minutes=10))  # a aprovação informada é anterior a T
    terceira = criar(chave_idempotencia="k3", expira_em=em_sp(AMANHA))
    relogio.congelar(T)
    sim.atrasar_consistencia(terceira, consultas=1)
    sim.aprovar(terceira, em=em_sp(T - timedelta(minutes=1)))
    atrasada = provedor.consultar_pagamento(terceira)
    assert atrasada.situacao == SituacaoNoProvedor.PENDENTE
    confere_utc(atrasada)
    normal = provedor.consultar_pagamento(terceira)
    assert normal.situacao == SituacaoNoProvedor.APROVADO
    confere_utc(normal)
    assert normal.aprovado_em == T - timedelta(minutes=1)
    for achado in provedor.buscar_por_referencia("ref-1"):
        confere_utc(achado)


def test_pagamento_consultado_recusa_instante_sem_fuso() -> None:  # A-21
    agora_sem_fuso = datetime(2026, 11, 2, 13, 0)  # noqa: DTZ001
    with pytest.raises(InstanteSemFuso):
        PagamentoConsultado(
            "simulador",
            "sim-1",
            "ref-1",
            D("45.90"),
            SituacaoNoProvedor.PENDENTE,
            agora_sem_fuso,
            None,
            AMANHA,
            T,
        )


AVISO_OK: dict[str, Any] = {"id_evento": "sim-ev-1", "tipo": "pagamento", "id_externo": "sim-1"}


@pytest.mark.parametrize("campo", ["id_evento", "tipo", "id_externo"])
def test_aviso_fora_do_esquema_e_invalido(campo: str) -> None:  # A-22, E07-R05
    limite = {"id_evento": 64, "tipo": 40, "id_externo": 64}[campo]
    invalidos = ["x" * (limite + 1), "", "a\x00b", 5]
    for valor in invalidos:
        with pytest.raises(AvisoInvalido):
            AvisoDoProvedor(**{**AVISO_OK, campo: valor})
    no_limite = AvisoDoProvedor(**{**AVISO_OK, campo: "x" * limite})
    assert getattr(no_limite, campo) == "x" * limite


def test_aviso_no_limite_com_caracteres_acentuados() -> None:  # A-22
    aviso = AvisoDoProvedor(**{**AVISO_OK, "id_evento": "é" * 64})
    assert aviso.id_evento == "é" * 64


def test_verificar_aviso_recusa_corpo_assinado_fora_do_limite(sim: Any) -> None:  # A-22
    corpo = json.dumps({**AVISO_OK, "id_evento": "x" * 65}).encode()
    assinatura = hmac.new(
        settings.SEGREDO_AVISOS_SIMULADOR.encode(), corpo, hashlib.sha256
    ).hexdigest()
    with pytest.raises(AvisoInvalido):
        obter_provedor().verificar_aviso(
            corpo, {"X-Simulador-Assinatura": f"sha256={assinatura}"}, {}
        )


def test_o_estado_do_simulador_sobrevive_ao_rollback_do_sistema(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-19, E07-R03
    segunda = criar(chave_idempotencia="k2")
    terceira = criar(chave_idempotencia="k3")
    avisos_antes = AvisoSimulado.objects.count()
    dentro: list[str] = []

    def bloco_que_falha() -> None:
        with transaction.atomic():
            dentro.append(obter_provedor().criar_cobranca(nova()).pagamento.id_externo)
            sim.aprovar(segunda)
            obter_provedor().cancelar_cobranca(terceira)
            raise RuntimeError("desfaz o bloco")

    with pytest.raises(RuntimeError, match="desfaz o bloco"):
        bloco_que_falha()
    assert CobrancaSimulada.objects.filter(chave_idempotencia="k1").count() == 1
    provedor = obter_provedor()
    assert provedor.consultar_pagamento(segunda).situacao == SituacaoNoProvedor.APROVADO
    assert provedor.consultar_pagamento(terceira).situacao == SituacaoNoProvedor.CANCELADO
    assert AvisoSimulado.objects.count() == avisos_antes + 2
    assert provedor.criar_cobranca(nova()).pagamento.id_externo == dentro[0]
    assert CobrancaSimulada.objects.filter(chave_idempotencia="k1").count() == 1


# --- E09-02: tarifa, liberação, saldo e movimentos da conta (A-1 a A-7, A-11, A-14 a A-16) ------

H = timedelta(hours=1)
TIPO = TipoDeMovimentoNoProvedor


def _cobranca_aprovada_com_tarifa(sim: Any, relogio: RelogioControlado) -> str:
    """A cobrança C de R$ 125,00, com tarifa de 0,99% e liberação em 24h, aprovada em T + 1h."""
    sim.definir_tarifa("pix", percentual=D("0.99"), fixa=D("0.00"))
    sim.definir_liberacao("pix", horas=24)
    id_externo = criar(valor=D("125.00"))
    relogio.congelar(T + H)
    sim.aprovar(id_externo)
    return id_externo


def test_a_aprovacao_informa_a_tarifa_e_a_liberacao(sim: Any, relogio: RelogioControlado) -> None:
    id_externo = _cobranca_aprovada_com_tarifa(sim, relogio)  # A-1
    consultado = obter_provedor().consultar_pagamento(id_externo)
    assert consultado.tarifa == D("1.24")  # 125,00 x 0,99% = 1,2375, para cima
    assert consultado.liberado_em == T + 25 * H


def test_antes_da_aprovacao_tarifa_e_liberacao_vem_nulas(sim: Any) -> None:  # A-2
    consultado = obter_provedor().consultar_pagamento(criar(valor=D("125.00")))
    assert consultado.situacao == SituacaoNoProvedor.PENDENTE
    assert (consultado.tarifa, consultado.liberado_em) == (None, None)


def test_o_saldo_separa_o_liberado_do_a_liberar(sim: Any, relogio: RelogioControlado) -> None:
    _cobranca_aprovada_com_tarifa(sim, relogio)  # A-3
    relogio.congelar(T + 2 * H)
    antes = obter_provedor().consultar_saldo()
    assert (antes.liberado, antes.a_liberar) == (D("0.00"), D("123.76"))
    relogio.congelar(T + 25 * H)  # o limite é inclusivo
    depois = obter_provedor().consultar_saldo()
    assert (depois.liberado, depois.a_liberar) == (D("123.76"), D("0.00"))


def test_movimentos_da_conta_em_ordem_e_com_ids_estaveis(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-4
    id_externo = _cobranca_aprovada_com_tarifa(sim, relogio)
    relogio.congelar(T + 3 * H)
    sim.depositar(D("1000.00"))
    sim.registrar_saida(D("50.00"), descricao="repasse")
    movimentos = obter_provedor().listar_movimentos(T, T + 4 * H)
    assert [(m.tipo, m.valor, m.id_externo) for m in movimentos] == [
        (TIPO.PAGAMENTO, D("125.00"), id_externo),
        (TIPO.TARIFA, D("-1.24"), id_externo),
        (TIPO.DEPOSITO, D("1000.00"), None),
        (TIPO.SAIDA, D("-50.00"), None),
    ]
    assert [m.ocorrido_em for m in movimentos] == [T + H, T + H, T + 3 * H, T + 3 * H]
    assert movimentos[0].liberado_em == movimentos[1].liberado_em == T + 25 * H
    assert movimentos[2].liberado_em == T + 3 * H
    assert movimentos[3].descricao_no_provedor == "repasse"
    assert [m.id_movimento for m in obter_provedor().listar_movimentos(T, T + 4 * H)] == [
        m.id_movimento for m in movimentos
    ]
    assert len({m.id_movimento for m in movimentos}) == 4
    assert [m.tipo for m in obter_provedor().listar_movimentos(T + 2 * H, T + 4 * H)] == [
        TIPO.DEPOSITO,
        TIPO.SAIDA,
    ]  # desde inclusivo, ate exclusivo


def test_movimentos_e_controles_recusam_entradas_invalidas(sim: Any) -> None:  # A-5
    provedor = obter_provedor()
    with pytest.raises(InstanteSemFuso):
        provedor.listar_movimentos(datetime(2026, 11, 2, 13, 0), T)  # noqa: DTZ001
    with pytest.raises(InstanteSemFuso):
        provedor.listar_movimentos(T, datetime(2026, 11, 2, 13, 0))  # noqa: DTZ001
    with pytest.raises(ValueError):
        provedor.listar_movimentos(T + H, T)
    for invalido in (D("0"), D("-1"), 1.0):
        with pytest.raises(ValueError):
            sim.depositar(invalido)
        with pytest.raises(ValueError):
            sim.registrar_saida(invalido, descricao="x")


def test_saldo_e_movimentos_seguem_o_plano_de_indisponibilidade(sim: Any) -> None:  # A-6
    provedor = obter_provedor()
    sim.indisponivel()
    with pytest.raises(ProvedorIndisponivel):
        provedor.consultar_saldo()
    with pytest.raises(ProvedorIndisponivel):
        provedor.listar_movimentos(T, T + H)
    sim.normalizar()
    assert provedor.consultar_saldo().liberado == D("0.00")
    assert provedor.listar_movimentos(T, T + H) == []


def test_falhar_proximas_vale_para_o_saldo(sim: Any) -> None:  # A-7
    sim.falhar_proximas(1, operacao="consultar_saldo")
    with pytest.raises(ProvedorIndisponivel):
        obter_provedor().consultar_saldo()
    assert obter_provedor().consultar_saldo().liberado == D("0.00")


def test_ajuste_aparece_nos_movimentos_e_no_saldo(sim: Any, relogio: RelogioControlado) -> None:
    _cobranca_aprovada_com_tarifa(sim, relogio)  # A-11
    relogio.congelar(T + 5 * H)
    sim.ajustar_saldo(D("-0.50"))
    ajustes = [m for m in obter_provedor().listar_movimentos(T, T + 6 * H) if m.tipo == TIPO.AJUSTE]
    assert [m.valor for m in ajustes] == [D("-0.50")]
    relogio.congelar(T + 25 * H)
    assert obter_provedor().consultar_saldo().liberado == D("123.26")


@pytest.mark.django_db(transaction=True)
@pytest.mark.concorrencia
def test_duas_aprovacoes_concorrentes_geram_um_par_de_movimentos(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-14
    from apps.simulador_pagamentos.models import MovimentoSimulado
    from tests.apoio.concorrencia import executar_em_paralelo

    sim.definir_tarifa("pix", percentual=D("0.99"), fixa=D("0.00"))
    id_externo = criar(valor=D("125.00"))
    relogio.congelar(T + H)

    def aprovar(barreira: Any) -> None:
        barreira.wait(timeout=10)
        sim.aprovar(id_externo)

    resultados = executar_em_paralelo(aprovar, aprovar)
    erros = [r.excecao for r in resultados if r.excecao is not None]
    assert len(erros) == 1
    assert isinstance(erros[0], ValueError)
    assert sorted(MovimentoSimulado.objects.values_list("tipo", flat=True)) == [
        "pagamento",
        "tarifa",
    ]


def test_o_saldo_diz_a_que_instante_se_refere(sim: Any, relogio: RelogioControlado) -> None:  # A-16
    relogio.congelar(T + 2 * H)
    saldo = obter_provedor().consultar_saldo()
    assert saldo.referente_a == saldo.consultado_em == T + 2 * H
    assert all(m.tipo != TIPO.OUTRO for m in obter_provedor().listar_movimentos(T, T + 3 * H))


def test_reiniciar_apaga_movimentos_e_planos(sim: Any, relogio: RelogioControlado) -> None:  # A-15
    _cobranca_aprovada_com_tarifa(sim, relogio)
    sim.depositar(D("10.00"))
    sim.reiniciar()
    relogio.congelar(T + 2 * H)
    assert obter_provedor().listar_movimentos(T, T + 3 * H) == []
    saldo = obter_provedor().consultar_saldo()
    assert (saldo.liberado, saldo.a_liberar) == (D("0.00"), D("0.00"))
    id_externo = criar(chave_idempotencia="k-novo", valor=D("125.00"))
    sim.aprovar(id_externo)
    consultado = obter_provedor().consultar_pagamento(id_externo)
    assert (consultado.tarifa, consultado.liberado_em) == (D("0.00"), T + 2 * H)
