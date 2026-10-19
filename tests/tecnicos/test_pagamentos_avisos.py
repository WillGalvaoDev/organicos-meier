"""E07-05: recebimento idempotente dos avisos do provedor (acceptance A-1 a A-11 e A-14)."""

import hashlib
import hmac
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.conf import settings
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import Client
from django.urls import resolve, reverse

from apps.contas.permissoes import Politica
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from apps.pagamentos.avisos import TAMANHO_MAXIMO_DO_AVISO
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import (
    AvisoRecebido,
    ChamadaAoProvedor,
    ConsultaDoPagamento,
    PagamentoNoProvedor,
)
from apps.pagamentos.provedor import NovaCobranca, SituacaoNoProvedor, obter_provedor
from apps.pagamentos.sinais import situacao_do_pagamento_mudou
from apps.simulador_pagamentos.models import AvisoSimulado
from apps.simulador_pagamentos.provedor import ProvedorSimulado
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
URL = "/pagamentos/avisos/"
CRIACAO = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
APROVACAO = datetime(2026, 11, 2, 12, 58, tzinfo=UTC)
T = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)
AMANHA = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)


class Sinais:
    def __init__(self) -> None:
        self.recebidos: list[tuple[Any, Any]] = []

    def __call__(self, sender: Any, anterior: Any, atual: Any, **kwargs: Any) -> None:
        self.recebidos.append((anterior, atual))


@pytest.fixture
def sinais() -> Iterator[Sinais]:
    receptor = Sinais()
    situacao_do_pagamento_mudou.connect(receptor, weak=False, dispatch_uid="avisos")
    yield receptor
    situacao_do_pagamento_mudou.disconnect(dispatch_uid="avisos")


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any, sinais: Sinais) -> Any:
    relogio.congelar(T)
    return simulador_pagamentos


def criar_cobranca(relogio: RelogioControlado) -> str:
    """Cria `P` às 12:00; o relógio volta para 13:00."""
    relogio.congelar(CRIACAO)
    nova = NovaCobranca("k1", "ref-1", D("45.90"), "Pedido de teste", AMANHA)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    relogio.congelar(T)
    return id_externo


@pytest.fixture
def p(sim: Any, relogio: RelogioControlado) -> str:
    """`P`, aprovada às 12:58; o relógio fica em 13:00."""
    id_externo = criar_cobranca(relogio)
    sim.aprovar(id_externo, em=APROVACAO)
    return id_externo


@pytest.fixture
def aviso(p: str) -> AvisoSimulado:
    return AvisoSimulado.objects.get(id_externo=p)


@pytest.fixture
def chamadas_ao_simulador(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    registradas: list[str] = []
    original = ProvedorSimulado.consultar_pagamento

    def contar(self: ProvedorSimulado, id_externo: str) -> Any:
        registradas.append(id_externo)
        return original(self, id_externo)

    monkeypatch.setattr(ProvedorSimulado, "consultar_pagamento", contar)
    return registradas


def unico(itens: Any) -> Any:
    achados = list(itens)
    assert len(achados) == 1, f"esperava 1 registro, há {len(achados)}"
    return achados[0]


def assinar(corpo: bytes) -> dict[str, str]:
    assinatura = hmac.new(
        settings.SEGREDO_AVISOS_SIMULADOR.encode(), corpo, hashlib.sha256
    ).hexdigest()
    return {"X-Simulador-Assinatura": f"sha256={assinatura}"}


def enviar(corpo: bytes, cabecalhos: dict[str, str], metodo: str = "post") -> Any:
    return getattr(Client(), metodo)(
        URL, data=corpo, content_type="application/json", headers=cabecalhos
    )


def enviar_aviso(aviso: AvisoSimulado) -> Any:
    from apps.simulador_pagamentos.controle import corpo_e_cabecalhos

    corpo, cabecalhos = corpo_e_cabecalhos(aviso)
    return enviar(corpo, cabecalhos)


def uma_chamada() -> ChamadaAoProvedor:
    todas = list(ChamadaAoProvedor.objects.all())
    assert len(todas) == 1, f"esperava 1 chamada, há {len(todas)}"
    return todas[0]


def test_aviso_valido_registra_e_agenda_a_consulta(
    p: str, aviso: AvisoSimulado, chamadas_ao_simulador: list[str]
) -> None:  # A-1
    resposta = enviar_aviso(aviso)
    assert resposta.status_code == 200
    assert resposta.content == b""
    registros = list(AvisoRecebido.objects.all())
    assert len(registros) == 1
    recebido = registros[0]
    assert recebido.provedor == "simulador"
    assert recebido.id_evento == aviso.id_evento
    assert recebido.tipo == "pagamento"
    assert recebido.id_externo == p
    assert recebido.recebido_em == T
    chamada = uma_chamada()
    assert chamada.operacao == "consultar_pagamento"
    assert chamada.alvo == p
    assert chamada.situacao == "pendente"
    assert chamada.parametros == {
        "origem": "aviso",
        "aviso_recebido_em": "2026-11-02T13:00:00+00:00",
    }
    assert PagamentoNoProvedor.objects.count() == 0
    assert chamadas_ao_simulador == []


def test_a_consulta_aplica_a_aprovacao_do_provedor(
    p: str, aviso: AvisoSimulado, relogio: RelogioControlado, sinais: Sinais
) -> None:  # A-2
    enviar_aviso(aviso)
    relogio.congelar(T + MIN)
    processar_chamadas()
    registros = list(PagamentoNoProvedor.objects.all())
    assert len(registros) == 1
    pagamento = registros[0]
    assert pagamento.situacao == SituacaoNoProvedor.APROVADO
    assert pagamento.aprovado_no_provedor_em == APROVACAO
    assert pagamento.primeiro_aviso_em == T
    assert [c.origem for c in ConsultaDoPagamento.objects.all()] == ["aviso"]
    assert EntradaAuditoria.objects.filter(acao="pagamento.situacao").count() == 1
    assert len(sinais.recebidos) == 1


@pytest.mark.acceptance
def test_aviso_repetido_nao_repete_efeitos(
    p: str, aviso: AvisoSimulado, relogio: RelogioControlado, sinais: Sinais
) -> None:  # A-3, cenário 17 (pagamento)
    enviar_aviso(aviso)
    relogio.congelar(T + MIN)
    processar_chamadas()
    for _ in range(4):
        assert enviar_aviso(aviso).status_code == 200
    assert AvisoRecebido.objects.count() == 1
    assert ChamadaAoProvedor.objects.count() == 1
    assert processar_chamadas() == 0
    assert EntradaAuditoria.objects.filter(acao="pagamento.situacao").count() == 1
    assert len(sinais.recebidos) == 1


def test_aviso_nao_autentico_e_recusado(
    p: str, aviso: AvisoSimulado, caplog: pytest.LogCaptureFixture
) -> None:  # A-4
    from apps.simulador_pagamentos.controle import corpo_e_cabecalhos, reemitir_aviso

    corpo, cabecalhos = corpo_e_cabecalhos(aviso)
    outro = reemitir_aviso(p)
    _, cabecalhos_do_outro = corpo_e_cabecalhos(outro)
    nao_json = b"isto nao e json"
    caplog.set_level(logging.DEBUG)
    casos = [
        (corpo, {}),
        (corpo, cabecalhos_do_outro),
        (bytes([corpo[0] ^ 1]) + corpo[1:], cabecalhos),
        (nao_json, assinar(nao_json)),
    ]
    for corpo_ruim, cabecalhos_ruins in casos:
        assert enviar(corpo_ruim, cabecalhos_ruins).status_code == 401
    assert AvisoRecebido.objects.count() == 0
    assert ChamadaAoProvedor.objects.count() == 0
    mensagens = [r.getMessage() for r in caplog.records if r.name.startswith("apps.pagamentos")]
    assert sum("Aviso de pagamento recusado" in m for m in mensagens) == 4
    for mensagem in mensagens:
        assert corpo.decode() not in mensagem
        assert cabecalhos["X-Simulador-Assinatura"] not in mensagem
        assert "isto nao e json" not in mensagem


def test_corpo_grande_e_metodos_errados(p: str, aviso: AvisoSimulado) -> None:  # A-5
    grande = b"x" * (TAMANHO_MAXIMO_DO_AVISO + 1)
    assert enviar(grande, assinar(grande)).status_code == 400
    assert AvisoRecebido.objects.count() == 0
    for metodo in ("get", "put", "delete"):
        assert enviar(b"", {}, metodo).status_code == 405, metodo


def test_tipo_desconhecido_e_registrado_sem_consulta(p: str) -> None:  # A-6
    corpo = json.dumps(
        {"id_evento": "sim-ev-900", "tipo": "teste_desconhecido", "id_externo": p}
    ).encode()
    assert enviar(corpo, assinar(corpo)).status_code == 200
    recebido = unico(AvisoRecebido.objects.all())
    assert recebido.tipo == "teste_desconhecido"
    assert ChamadaAoProvedor.objects.count() == 0


def pendente_com_dois_avisos(
    sim: Any, relogio: RelogioControlado
) -> tuple[str, AvisoSimulado, AvisoSimulado]:
    id_externo = criar_cobranca(relogio)
    sim.expirar(id_externo)
    sim.aprovar(id_externo)
    a1, a2 = AvisoSimulado.objects.filter(id_externo=id_externo).order_by("pk")
    return id_externo, a1, a2


def test_avisos_diferentes_antes_da_consulta_geram_uma_chamada(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-7
    id_externo, a1, a2 = pendente_com_dois_avisos(sim, relogio)
    assert sim.entregar_avisos([a1, a1, a2]) == [200, 200, 200]
    assert AvisoRecebido.objects.filter(id_externo=id_externo).count() == 2
    assert uma_chamada().situacao == "pendente"
    relogio.congelar(T + MIN)
    processar_chamadas()
    assert uma_chamada().situacao == "concluida"
    pagamento = unico(PagamentoNoProvedor.objects.all())
    assert pagamento.primeiro_aviso_em == T
    assert pagamento.situacao == SituacaoNoProvedor.APROVADO


def test_a_ordem_dos_avisos_nao_muda_o_resultado(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-8
    _, a1, a2 = pendente_com_dois_avisos(sim, relogio)
    sim.entregar_avisos([a2])
    processar_chamadas()
    sim.entregar_avisos([a1])
    relogio.congelar(T + MIN)
    processar_chamadas()
    assert unico(PagamentoNoProvedor.objects.all()).situacao == SituacaoNoProvedor.APROVADO
    consultas = list(ConsultaDoPagamento.objects.order_by("pk"))
    assert [c.situacao for c in consultas] == ["aprovado", "aprovado"]
    entrada = unico(EntradaAuditoria.objects.filter(acao="pagamento.situacao"))
    assert entrada.alteracoes["anterior"] is None


def test_o_horario_do_aviso_nao_decide_o_da_aprovacao(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-9
    id_externo = criar_cobranca(relogio)
    sim.aprovar(id_externo, em=T)
    aviso = AvisoSimulado.objects.get(id_externo=id_externo)
    relogio.congelar(T + timedelta(hours=2))
    assert enviar_aviso(aviso).status_code == 200
    relogio.congelar(T + timedelta(hours=2, minutes=1))
    processar_chamadas()
    pagamento = unico(PagamentoNoProvedor.objects.all())
    assert pagamento.aprovado_no_provedor_em == T
    assert pagamento.primeiro_aviso_em == T + timedelta(hours=2)
    assert pagamento.ultima_consulta_em == T + timedelta(hours=2, minutes=1)


def test_a_rota_de_avisos_e_publica() -> None:  # A-10
    callback = resolve(reverse("pagamentos_avisos")).func
    assert callback.politica_de_acesso is Politica.PUBLICA  # type: ignore[attr-defined]


def test_aviso_novo_de_pagamento_ja_consultado_agenda_outra_consulta(
    p: str, aviso: AvisoSimulado, sim: Any, relogio: RelogioControlado, sinais: Sinais
) -> None:  # A-11
    enviar_aviso(aviso)
    relogio.congelar(T + MIN)
    processar_chamadas()
    outro = sim.reemitir_aviso(p)
    assert enviar_aviso(outro).status_code == 200
    relogio.congelar(T + 2 * MIN)
    assert processar_chamadas() == 1
    chamadas = list(ChamadaAoProvedor.objects.order_by("pk"))
    assert [c.situacao for c in chamadas] == ["concluida", "concluida"]
    assert ConsultaDoPagamento.objects.count() == 2
    assert EntradaAuditoria.objects.filter(acao="pagamento.situacao").count() == 1
    assert len(sinais.recebidos) == 1


def test_o_aviso_recebido_so_aceita_insercao(p: str, aviso: AvisoSimulado) -> None:  # A-14
    enviar_aviso(aviso)
    recebido = unico(AvisoRecebido.objects.all())
    recebido.tipo = "outro"
    with pytest.raises(RegistroImutavel):
        recebido.save()
    with pytest.raises(RegistroImutavel):
        recebido.delete()
    with pytest.raises(RegistroImutavel):
        AvisoRecebido.objects.all().update(tipo="outro")
    for sql in (
        "UPDATE pagamentos_avisorecebido SET tipo = 'outro'",
        "DELETE FROM pagamentos_avisorecebido",
    ):
        with (
            pytest.raises(DatabaseError, match="só aceita inserção"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(sql)
    with pytest.raises(IntegrityError), transaction.atomic():
        AvisoRecebido.objects.create(
            provedor=recebido.provedor,
            id_evento=recebido.id_evento,
            tipo="pagamento",
            id_externo=p,
        )
    assert unico(AvisoRecebido.objects.all()).tipo == "pagamento"
