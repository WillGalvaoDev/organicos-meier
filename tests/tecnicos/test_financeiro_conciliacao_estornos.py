"""E10-05: conciliação dos estornos e conclusão tardia (acceptance A-1 a A-9)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.financeiro.conciliacao import conciliar_dia, limites_do_dia
from apps.financeiro.devolucoes import autorizar_devolucao
from apps.financeiro.models import (
    AlertaFinanceiro,
    ConciliacaoDiaria,
    MovimentoFinanceiro,
    ParcelaDeDevolucao,
)
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pagamentos.provedor import (
    MovimentoNoProvedor,
    SaldoNoProvedor,
    TipoDeMovimentoNoProvedor,
    obter_provedor,
)
from apps.simulador_pagamentos.estado import obter_estorno
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.devolucoes import Arranjo, arranjo_da_devolucao, parcial
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
DIA = date(2026, 11, 2)


@pytest.fixture
def a(relogio: RelogioControlado, simulador_pagamentos: Any) -> Arranjo:
    return arranjo_da_devolucao(simulador_pagamentos, relogio)


def _alertas(tipo: str) -> list[AlertaFinanceiro]:
    return list(AlertaFinanceiro.objects.filter(tipo=tipo, resolvido_em=None).order_by("pk"))


def _conciliar(a: Arranjo, data: date = DIA) -> ConciliacaoDiaria:
    _, fim = limites_do_dia(data)
    a.relogio.congelar(fim + H)
    return conciliar_dia(data)


def _diferenca(c: ConciliacaoDiaria) -> Decimal:
    return D(str(c.resumo["diferenca"]))


def _devolver(a: Arranjo) -> ParcelaDeDevolucao:
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    return parcela


def test_devolucao_concluida_tem_par_no_livro(a: Arranjo) -> None:  # A-1
    parcela = _devolver(a)
    assert parcela.situacao == "concluida"
    conciliacao = _conciliar(a)
    assert conciliacao.resumo["sem_par"] == 0
    assert conciliacao.resumo["movimentos"] == 3  # pagamento, depósito e estorno
    assert _diferenca(conciliacao) == D("0.00")
    assert conciliacao.resultado == "ok"
    assert _alertas("divergencia_na_conciliacao") == []


def test_estorno_sem_parcela_e_so_divergencia(a: Arranjo) -> None:  # A-2
    from apps.pagamentos.provedor import NovoEstorno

    estorno = obter_provedor().estornar(NovoEstorno(a.pagamento.id_externo, D("10.00"), "avulso"))
    conciliacao = _conciliar(a)
    assert conciliacao.resultado == "divergente"
    (alerta,) = _alertas("divergencia_na_conciliacao")
    assert alerta.dados["id_estorno"] == estorno.id_estorno
    assert _alertas("devolucao_concluida_tardiamente") == []


def _elegivel_com_estorno_tardio(a: Arranjo) -> tuple[ParcelaDeDevolucao, EstornoSimulado]:
    """Recusa que o provedor processa mesmo assim: a parcela fica elegível (a verificação não
    vê o estorno invisível) e depois o provedor conclui o estorno."""
    a.sim.recusar_mas_processar(a.pagamento.id_externo, "meio_nao_permite_estorno")
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    invisivel = EstornoSimulado.objects.get()
    a.sim.concluir_estorno(invisivel.id_estorno)
    return parcela, invisivel


def test_estorno_tardio_de_parcela_elegivel_e_adotado(a: Arranjo) -> None:  # A-3
    parcela, estorno = _elegivel_com_estorno_tardio(a)
    _conciliar(a)
    (divergencia,) = _alertas("divergencia_na_conciliacao")
    assert divergencia.dados["id_estorno"] == estorno.id_estorno
    (tardio,) = _alertas("devolucao_concluida_tardiamente")
    assert tardio.gravidade == "critico"
    assert tardio.chave == estorno.id_estorno
    assert (tardio.dados["parcela"], tardio.dados["valor"]) == (parcela.pk, "31.25")
    assert ChamadaAoProvedor.objects.filter(
        operacao="verificar_estornos", alvo=f"parcela:{parcela.pk}", situacao="pendente"
    ).exists()
    processar_chamadas()
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.id_estorno) == ("concluida", estorno.id_estorno)
    assert MovimentoFinanceiro.objects.filter(chave=f"devolucao:{estorno.id_estorno}").count() == 1
    assert _alertas("devolucao_concluida_tardiamente") == []
    assert _alertas("devolucao_elegivel_excepcional") == []


def test_estorno_tardio_depois_da_devolucao_fora_da_plataforma_e_em_dobro(
    a: Arranjo,
) -> None:  # A-4
    parcela, estorno = _elegivel_com_estorno_tardio(a)
    ParcelaDeDevolucao.objects.filter(pk=parcela.pk).update(situacao="concluida_fora_da_plataforma")
    antes = MovimentoFinanceiro.objects.count()
    _conciliar(a)
    (tardio,) = _alertas("devolucao_concluida_tardiamente")
    assert tardio.dados["devolvida_em_dobro"] is True
    assert tardio.chave == estorno.id_estorno
    assert MovimentoFinanceiro.objects.count() == antes
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida_fora_da_plataforma"
    assert not ChamadaAoProvedor.objects.filter(operacao="verificar_estornos", situacao="pendente")


class _SaldoFixo:
    """O provedor simulado real, com o saldo lido num instante anterior (o relatório assíncrono)."""

    def __init__(self, saldo: SaldoNoProvedor) -> None:
        self._saldo = saldo

    def consultar_saldo(self) -> SaldoNoProvedor:
        return self._saldo

    def __getattr__(self, nome: str) -> Any:
        return getattr(obter_provedor(), nome)


def test_estorno_concluido_antes_do_instante_do_saldo_e_lancado_depois(
    a: Arranjo, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-5
    _, fim = limites_do_dia(DIA)
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    a.relogio.congelar(fim - timedelta(minutes=10))  # 23:50
    a.sim.concluir_estorno(EstornoSimulado.objects.get().id_estorno)
    a.relogio.congelar(fim - timedelta(minutes=5))  # 23:55
    saldo_das_2355 = obter_provedor().consultar_saldo()
    a.relogio.congelar(fim + timedelta(minutes=10))  # 00:10 de D + 1
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    monkeypatch.setattr(
        "apps.financeiro.conciliacao.obter_provedor", lambda: _SaldoFixo(saldo_das_2355)
    )
    conciliacao = _conciliar(a)
    assert conciliacao.resumo["sem_par"] == 0
    assert _diferenca(conciliacao) == D("0.00")
    assert conciliacao.resultado == "ok"


def test_dois_estornos_de_mesmo_valor_pareiam_cada_um_pelo_seu_id(a: Arranjo) -> None:  # A-6
    primeira = _devolver(a)
    o2 = parcial(a.i2, "1").obrigacao
    segunda = autorizar_devolucao(o2, autor=a.admin)
    processar_chamadas()
    segunda.refresh_from_db()
    assert (primeira.situacao, segunda.situacao) == ("concluida", "concluida")
    assert primeira.id_estorno != segunda.id_estorno
    conciliacao = _conciliar(a)
    assert conciliacao.resumo["sem_par"] == 0
    assert conciliacao.resultado == "ok"


class _ComDevolucaoSemId:
    """Um dublê do protocolo com um movimento `devolucao` sem `id_estorno`."""

    def __init__(self, quando: datetime) -> None:
        self._quando = quando

    def consultar_saldo(self) -> SaldoNoProvedor:
        return SaldoNoProvedor(D("-10.00"), D("0.00"), self._quando, self._quando)

    def listar_movimentos(self, desde: datetime, ate: datetime) -> list[MovimentoNoProvedor]:
        movimento = MovimentoNoProvedor(
            "mov-sem-id",
            TipoDeMovimentoNoProvedor.DEVOLUCAO,
            "refund",
            D("-10.00"),
            "sim-1",
            self._quando,
            self._quando,
        )
        return [movimento] if desde <= self._quando < ate else []


def test_devolucao_sem_id_de_estorno_e_divergencia_comum(
    a: Arranjo, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-8
    inicio, _ = limites_do_dia(DIA)
    duble = _ComDevolucaoSemId(inicio + 12 * H)
    monkeypatch.setattr("apps.financeiro.conciliacao.obter_provedor", lambda: duble)
    conciliacao = _conciliar(a)
    assert conciliacao.resultado == "divergente"
    assert [al.chave for al in _alertas("divergencia_na_conciliacao")][:1] == ["mov-sem-id"]
    assert _alertas("devolucao_concluida_tardiamente") == []


def test_estorno_concluido_antes_do_acompanhamento_e_so_pendencia_ate_o_dia_seguinte(
    a: Arranjo,
) -> None:  # A-9
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    estorno = EstornoSimulado.objects.get()
    a.sim.concluir_estorno(estorno.id_estorno)
    _conciliar(a)
    assert len(_alertas("divergencia_na_conciliacao")) == 1
    assert _alertas("devolucao_concluida_tardiamente") == []
    a.relogio.avancar(timedelta(hours=1))
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    _conciliar(a, DIA + timedelta(days=1))
    assert _alertas("divergencia_na_conciliacao") == []


def test_devolucao_excepcional_nao_aparece_na_conciliacao(
    a: Arranjo, tmp_path: Any, settings: Any
) -> None:  # A-7
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.financeiro.devolucoes import confirmar_devolucao_excepcional
    from apps.financeiro.livro import saldo_total_esperado
    from tests.apoio.devolucoes import levar_a_elegivel

    settings.MEDIA_ROOT = tmp_path
    parcela = levar_a_elegivel(a)
    antes = saldo_total_esperado()
    confirmar_devolucao_excepcional(
        parcela,
        autor=a.admin,
        meio="pix",
        identificacao="E2E-1",
        justificativa="Pix direto",
        comprovante=SimpleUploadedFile("c.pdf", b"%PDF-1.4 x"),
    )
    assert saldo_total_esperado() == antes
    conciliacao = _conciliar(a)
    assert conciliacao.resumo["sem_par"] == 0
    assert _diferenca(conciliacao) == D("0.00")
    assert conciliacao.resultado == "ok"
    assert _alertas("divergencia_na_conciliacao") == []


# --- E10-R05 e R09: estorno sem baixa e adoção na reconsulta (A-10 a A-16) ----------------------


def _pdf() -> Any:
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile("c.pdf", b"%PDF-1.4 comprovante")


def _confirmar(a: Arranjo, parcela: ParcelaDeDevolucao) -> Any:
    from apps.financeiro.devolucoes import confirmar_devolucao_excepcional

    return confirmar_devolucao_excepcional(
        parcela,
        autor=a.admin,
        meio="pix",
        identificacao="E2E-1",
        justificativa="Pix direto",
        comprovante=_pdf(),
    )


def _arranjo_r(a: Arranjo, *, ate_a_elegivel: bool = True) -> tuple[ParcelaDeDevolucao, str]:
    """Estorno recusado que conclui tarde: a parcela passa por `falha_definitiva` (e fica
    `elegivel_excepcional`, se `ate_a_elegivel`) com o `id_estorno` guardado."""
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    id_estorno = EstornoSimulado.objects.get().id_estorno
    a.sim.recusar_estorno(id_estorno, "estado_invalido")
    if ate_a_elegivel:
        processar_chamadas()
    else:
        processar_chamadas(limite=1)
    parcela.refresh_from_db()
    assert parcela.situacao == ("elegivel_excepcional" if ate_a_elegivel else "falha_definitiva")
    assert parcela.id_estorno == id_estorno
    return parcela, id_estorno


def _concluir_tarde(a: Arranjo, id_estorno: str) -> None:
    """O dublê do risco residual (infraestrutura 4.7): o estorno recusado volta a processar e
    conclui. Não afirma que a API real reverte uma recusa (L-7)."""
    EstornoSimulado.objects.filter(pk=obter_estorno(id_estorno).pk).update(
        situacao="em_processamento"
    )
    a.sim.concluir_estorno(id_estorno)


def _elegivel_com_estorno_visivel_em_processamento(a: Arranjo) -> ParcelaDeDevolucao:
    a.sim.recusar_mas_processar(a.pagamento.id_externo, "meio_nao_permite_estorno")
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    EstornoSimulado.objects.update(visivel=True)
    return parcela


def test_estorno_reencontrado_em_processamento_na_elegivel_e_adotado(a: Arranjo) -> None:  # A-10
    from apps.financeiro.devolucoes import DevolucaoRecusada

    parcela = _elegivel_com_estorno_visivel_em_processamento(a)
    estorno = EstornoSimulado.objects.get()
    with pytest.raises(DevolucaoRecusada):
        _confirmar(a, parcela)
    processar_chamadas()
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.id_estorno) == ("em_processamento", estorno.id_estorno)
    assert ChamadaAoProvedor.objects.filter(
        operacao="acompanhar_estorno", alvo=f"parcela:{parcela.pk}", situacao="pendente"
    ).exists()
    assert _alertas("devolucao_elegivel_excepcional") == []
    resolvido = AlertaFinanceiro.objects.get(tipo="devolucao_elegivel_excepcional")
    assert resolvido.motivo_da_resolucao == "estorno encontrado no provedor e adotado"


def test_estorno_adotado_em_processamento_conclui_sem_novo_aviso_de_andamento(
    a: Arranjo,
) -> None:  # A-11
    from apps.financeiro.devolucoes import DevolucaoRecusada
    from apps.notificacoes.models import Notificacao

    parcela = _elegivel_com_estorno_visivel_em_processamento(a)
    with pytest.raises(DevolucaoRecusada):
        _confirmar(a, parcela)
    processar_chamadas()
    estorno = EstornoSimulado.objects.get()
    a.sim.concluir_estorno(estorno.id_estorno)
    a.relogio.avancar(timedelta(hours=1))
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert MovimentoFinanceiro.objects.filter(chave=f"devolucao:{estorno.id_estorno}").count() == 1
    titulos = [
        n.titulo
        for n in Notificacao.objects.filter(conta=a.comprador, evento="estorno").order_by("pk")
    ]
    assert titulos.count("Estorno concluído") == 1
    assert titulos.count("Estorno em andamento") == 1  # o da elegibilidade, e nenhum depois


def test_confirmacao_recusada_quando_o_estorno_da_propria_parcela_conclui_tarde(
    a: Arranjo, settings: Any, tmp_path: Any
) -> None:  # A-12
    from apps.financeiro.devolucoes import DevolucaoRecusada
    from apps.financeiro.models import ConfirmacaoDeDevolucaoExcepcional

    settings.MEDIA_ROOT = tmp_path
    parcela, id_estorno = _arranjo_r(a)
    _concluir_tarde(a, id_estorno)
    with pytest.raises(
        DevolucaoRecusada, match="há devolução em processamento ou concluída no provedor"
    ):
        _confirmar(a, parcela)
    assert not ConfirmacaoDeDevolucaoExcepcional.objects.exists()
    assert not MovimentoFinanceiro.objects.filter(tipo="devolucao_excepcional").exists()
    assert not list(tmp_path.rglob("*.pdf"))
    assert ChamadaAoProvedor.objects.filter(
        operacao="verificar_estornos", alvo=f"parcela:{parcela.pk}", situacao="pendente"
    ).exists()
    processar_chamadas()
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.id_estorno) == ("concluida", id_estorno)
    assert MovimentoFinanceiro.objects.filter(chave=f"devolucao:{id_estorno}").count() == 1


def test_conclusao_tardia_depois_da_confirmacao_e_devolucao_em_dobro(
    a: Arranjo, settings: Any, tmp_path: Any
) -> None:  # A-13
    settings.MEDIA_ROOT = tmp_path
    parcela, id_estorno = _arranjo_r(a)
    _confirmar(a, parcela)
    _concluir_tarde(a, id_estorno)
    antes = MovimentoFinanceiro.objects.count()
    _conciliar(a)
    (alerta,) = _alertas("devolucao_concluida_tardiamente")
    assert alerta.gravidade == "critico"
    assert alerta.chave == id_estorno
    assert alerta.dados["parcela"] == parcela.pk
    assert alerta.dados["situacao"] == "concluida_fora_da_plataforma"
    assert alerta.dados["devolvida_em_dobro"] is True
    assert MovimentoFinanceiro.objects.count() == antes
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida_fora_da_plataforma"
    assert not ChamadaAoProvedor.objects.filter(operacao="verificar_estornos", situacao="pendente")


def test_reconsulta_em_falha_definitiva_adota_o_estorno_que_concluiu_tarde(
    a: Arranjo,
) -> None:  # A-14
    from apps.financeiro.models import HistoricoDaDevolucao

    parcela, id_estorno = _arranjo_r(a, ate_a_elegivel=False)
    _concluir_tarde(a, id_estorno)
    processar_chamadas()
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.id_estorno) == ("concluida", id_estorno)
    assert MovimentoFinanceiro.objects.filter(chave=f"devolucao:{id_estorno}").count() == 1
    assert not HistoricoDaDevolucao.objects.filter(
        parcela=parcela, situacao="elegivel_excepcional"
    ).exists()


def test_alerta_critico_com_id_conhecido_em_falha_definitiva(a: Arranjo) -> None:  # A-15
    parcela, id_estorno = _arranjo_r(a, ate_a_elegivel=False)
    _concluir_tarde(a, id_estorno)
    _conciliar(a)
    (alerta,) = _alertas("devolucao_concluida_tardiamente")
    assert alerta.gravidade == "critico"
    assert alerta.chave == id_estorno
    assert alerta.dados["devolvida_em_dobro"] is False
    assert (
        ChamadaAoProvedor.objects.filter(
            operacao="verificar_estornos", alvo=f"parcela:{parcela.pk}", situacao="pendente"
        ).count()
        == 1
    )


def test_estorno_assumido_por_parcela_em_processamento_nao_bloqueia_outra_confirmacao(
    a: Arranjo, settings: Any, tmp_path: Any
) -> None:  # A-16 (regressão da definição)
    from django.db import transaction

    from apps.financeiro.reserva import designar_reserva
    from tests.apoio.devolucoes import parcela_de_fabrica

    settings.MEDIA_ROOT = tmp_path
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    em_processamento = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    a.sim.concluir_estorno(EstornoSimulado.objects.get().id_estorno)
    outra = parcela_de_fabrica(a, "elegivel_excepcional", "10.00")
    with transaction.atomic():
        designar_reserva(a.admin, outra.obrigacao, outra.obrigacao.devido, "Cobrir")
    confirmacao = _confirmar(a, outra)
    assert confirmacao.pk is not None
    em_processamento.refresh_from_db()
    assert em_processamento.situacao == "em_processamento"
