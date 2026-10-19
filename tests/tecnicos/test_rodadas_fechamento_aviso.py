"""E06-02: aviso de início do fechamento (acceptance A-1 a A-7)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection

from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.notificacoes.models import Envio, Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import agora
from apps.rodadas import avisos
from apps.rodadas.fechamento import iniciar_fechamento
from apps.rodadas.models import Ciclo, Etapa, PrazoDoFechamento, Rodada
from tests.apoio.ciclos import simular_volta_para_interesse
from tests.apoio.interesses import cenario, pendente, reservada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, EstoqueDaRodadaFactory, ProdutoFactory

pytestmark = pytest.mark.django_db

D = Decimal
T0 = datetime(2026, 11, 2, 13, 30, tzinfo=UTC)
EVENTO = "fechamento_iniciado"


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def avisos_de(conta: Conta) -> list[Notificacao]:
    return list(Notificacao.objects.filter(conta=conta, evento=EVENTO).order_by("pk"))


def montar(nome: str = "Sítio Boa Terra") -> tuple[Rodada, Any]:
    rodada, produto, _ = cenario(None, preco=D("10.00"))
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(nome=nome)
    return rodada, produto


@pytest.mark.acceptance
def test_so_quem_tem_reserva_na_rodada_recebe_o_aviso(relogio: RelogioControlado) -> None:
    # A-1, §12 início do fechamento
    relogio.congelar(T0)
    rodada, produto = montar()
    a, b, c, d = (ContaFactory.create() for _ in range(4))
    reservada(a, produto, 6)
    reservada(b, produto, 4)
    pendente(c, produto, 3)
    ciclo = iniciar_fechamento(admin(), rodada)
    assert len(avisos_de(a)) == 1
    assert len(avisos_de(b)) == 1
    assert avisos_de(c) == []
    assert avisos_de(d) == []
    aviso = avisos_de(a)[0]
    assert aviso.titulo == "Fechamento iniciado: Sítio Boa Terra"
    assert "03/11/2026 às 10:30 (horário de Brasília)" in aviso.corpo
    assert "sem precisar confirmar nada" in aviso.corpo
    assert aviso.corpo == (
        "A rodada de Sítio Boa Terra entrou na etapa de fechamento. O prazo termina em "
        "03/11/2026 às 10:30 (horário de Brasília). Até lá, você ainda pode alterar seus "
        "interesses, sem precisar confirmar nada. No fim do prazo, as unidades que não "
        "completarem caixa serão removidas."
    )
    assert aviso.link == "/carrinho/"
    assert aviso.chave == f"fechamento_iniciado:{ciclo.pk}:{a.pk}"
    assert avisos_de(b)[0].chave == f"fechamento_iniciado:{ciclo.pk}:{b.pk}"


def test_envios_de_email_e_whatsapp_seguem_a_matriz(relogio: RelogioControlado) -> None:  # A-2
    relogio.congelar(T0)
    rodada, produto = montar()
    a = ContaFactory.create(telefone="+5521999990000", whatsapp_consentido_em=agora())
    b = ContaFactory.create()
    reservada(a, produto, 6)
    reservada(b, produto, 4)
    iniciar_fechamento(admin(), rodada)
    envios = Envio.objects.filter(notificacao__evento=EVENTO)
    assert sorted(envios.filter(canal="email").values_list("conta_id", flat=True)) == sorted(
        [a.pk, b.pk]
    )
    assert list(envios.filter(canal="whatsapp").values_list("conta_id", flat=True)) == [a.pk]


def test_varias_parcelas_e_produtos_geram_um_aviso(relogio: RelogioControlado) -> None:  # A-3
    relogio.congelar(T0)
    rodada, produto = montar()
    segundo = ProdutoFactory.create(fornecedor=rodada.fornecedor, unidade="unidade")
    EstoqueDaRodadaFactory.create(rodada=rodada, produto=segundo, limite=None)
    a = ContaFactory.create()
    reservada(a, produto, 6)
    reservada(a, produto, 2)
    reservada(a, segundo, 3)
    iniciar_fechamento(admin(), rodada)
    assert len(avisos_de(a)) == 1


def test_falha_na_emissao_desfaz_o_inicio(
    monkeypatch: pytest.MonkeyPatch, relogio: RelogioControlado
) -> None:  # A-4
    relogio.congelar(T0)
    rodada, produto = montar()
    reservada(ContaFactory.create(), produto, 10)

    def estoura(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("falha na emissão")

    monkeypatch.setattr(avisos, "emitir_evento_para_varios", estoura)
    with pytest.raises(RuntimeError):
        iniciar_fechamento(admin(), rodada)
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.INTERESSE
    assert Ciclo.objects.count() == 0
    assert PrazoDoFechamento.objects.count() == 0
    assert EntradaAuditoria.objects.filter(acao="rodada.iniciar_fechamento").count() == 0
    assert Notificacao.objects.filter(evento=EVENTO).count() == 0


def test_sem_destinatarios_nao_emite_nada() -> None:  # A-5
    rodada, _ = montar()
    with connection.cursor() as cursor:  # o banco recusa mínimo zero; só neste teste
        cursor.execute(
            "ALTER TABLE fornecedores_fornecedor DROP CONSTRAINT fornecedor_minimo_positivo"
        )
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(minimo=D("0.00"))
    iniciar_fechamento(admin(), rodada)
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO
    assert Notificacao.objects.filter(evento=EVENTO).count() == 0


def test_novo_ciclo_gera_novo_aviso(relogio: RelogioControlado) -> None:  # A-6
    relogio.congelar(T0)
    rodada, produto = montar()
    a = ContaFactory.create()
    reservada(a, produto, 10)
    primeiro = iniciar_fechamento(admin(), rodada)
    simular_volta_para_interesse(rodada)
    segundo = iniciar_fechamento(admin(), rodada)
    assert primeiro.pk != segundo.pk
    assert [n.chave for n in avisos_de(a)] == [
        f"fechamento_iniciado:{primeiro.pk}:{a.pk}",
        f"fechamento_iniciado:{segundo.pk}:{a.pk}",
    ]


def test_titulo_cortado_em_150_caracteres(relogio: RelogioControlado) -> None:  # A-7
    relogio.congelar(T0)
    rodada, produto = montar(nome="N" * 150)
    a = ContaFactory.create()
    reservada(a, produto, 10)
    iniciar_fechamento(admin(), rodada)
    recebidos = avisos_de(a)
    assert len(recebidos) == 1
    assert len(recebidos[0].titulo) == 150
    assert recebidos[0].titulo.startswith("Fechamento iniciado: ")
