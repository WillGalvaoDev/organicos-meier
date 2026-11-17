"""E16-05: o comando `conferir_restauracao` (acceptance A-1 a A-12).

O comando só lê. Os testes comparam o banco antes e depois e conferem cada seção do relatório.
"""

import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import DatabaseError

from tests.apoio.entrega import arranjo_ae, registrar_endereco
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
I = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)  # noqa: E741  (12:00 em Brasília)
H = timedelta(hours=1)
SECOES = [
    "Ponto recuperado",
    "Invariante financeiro",
    "Estoque",
    "Prazos encerrados",
    "Pendências com o provedor",
    "Conciliação",
    "Reconferir com o extrato",
]


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def conferir(*argumentos: str) -> tuple[str, int]:
    saida, erro = StringIO(), StringIO()
    codigo = 0
    try:
        call_command("conferir_restauracao", *argumentos, stdout=saida, stderr=erro)
    except SystemExit as saiu:
        codigo = int(saiu.code or 0)
    return saida.getvalue() + erro.getvalue(), codigo


def secao(texto: str, titulo: str) -> str:
    """O trecho de uma seção: do título até o título da seguinte."""
    inicio = texto.index(f". {titulo}: ")
    proximo = re.search(r"^\d\. ", texto[inicio + 1 :], flags=re.MULTILINE)
    fim = inicio + 1 + proximo.start() if proximo else len(texto)
    return texto[inicio:fim]


def resultado(texto: str, titulo: str) -> str:
    return secao(texto, titulo).splitlines()[0].rsplit(": ", 1)[1]


def contagens() -> dict[str, int]:
    """As linhas de cada tabela do sistema (domínio, alertas, auditoria e Procrastinate)."""
    return {
        m._meta.label: m._default_manager.count() for m in apps.get_models() if not m._meta.proxy
    }


@pytest.fixture
def ar(relogio: RelogioControlado, sim: Any) -> Any:
    """O arranjo AR: o AE aprovado com o repasse de R$ 170,00 e um aporte de R$ 1.000,00, a
    conciliação de 19/11/2026 e um backup concluído em `I - 9h`, com o relógio em `I`."""
    from apps.financeiro.models import ConciliacaoDiaria
    from apps.financeiro.reserva import registrar_aporte
    from apps.operacao.models import BackupExterno
    from apps.pedidos.repasse import registrar_repasse

    a, _x, _y, _pf = arranjo_ae(relogio, sim, liberacao_horas=0)
    registrar_endereco(a.admin)
    relogio.congelar(I - 2 * H)
    registrar_repasse(
        a.admin, a.rodada, valor=D("170.00"), identificacao="rep-1", justificativa="Repasse"
    )
    relogio.congelar(I - H)
    registrar_aporte(a.admin, D("1000.00"), "dep-1", "Aporte inicial")
    ConciliacaoDiaria.objects.create(data=date(2026, 11, 19), resultado="ok")
    BackupExterno.objects.create(
        iniciado_em=I - 9 * H,
        concluido_em=I - 9 * H,
        ambiente="homologacao",
        chave="banco/homologacao/2026/11/organicos-homologacao-20261120T060000Z.dump.age",
        tamanho_bytes=1000,
        sha256="c" * 64,
    )
    relogio.congelar(I)
    return a


def test_o_relatorio_completo(ar: Any) -> None:  # A-1
    texto, codigo = conferir()
    posicoes = [texto.index(f"{n}. {titulo}: ") for n, titulo in enumerate(SECOES, start=1)]
    assert posicoes == sorted(posicoes)
    for titulo in SECOES:
        assert resultado(texto, titulo) in ("OK", "ATENÇÃO", "FALHA")
    assert resultado(texto, "Ponto recuperado") == "OK"
    assert "20/11/2026 03:00" in secao(texto, "Ponto recuperado")  # o backup
    assert resultado(texto, "Invariante financeiro") == "OK"
    assert "Diferença" in secao(texto, "Invariante financeiro")
    assert resultado(texto, "Estoque") == "OK"
    extrato = secao(texto, "Reconferir com o extrato")
    assert resultado(texto, "Reconferir com o extrato") == "ATENÇÃO"
    assert "R$ 1.000,00" in extrato
    assert "R$ 170,00" in extrato
    assert extrato.index("R$ 1.000,00") < extrato.index("R$ 170,00")  # do mais novo ao mais antigo
    assert "conferir com o extrato e os comprovantes." in extrato
    assert texto.strip().splitlines()[-1].startswith("Conferência: 0 falha(s), ")
    assert codigo == 0


def test_o_comando_nao_grava_nada(ar: Any) -> None:  # A-2
    antes = contagens()
    conferir()
    assert contagens() == antes


def test_a_escrita_durante_a_conferencia_falha(ar: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # A-3
    from apps.nucleo.auditoria import SISTEMA, EntradaAuditoria, registrar_auditoria
    from apps.operacao import conferencia

    def escreve(instante: Any, antes_de: Any) -> Any:
        registrar_auditoria(SISTEMA, "teste.conferencia", ar.rodada, {"x": 1})

    monkeypatch.setattr(conferencia, "SECOES", [*conferencia.SECOES, escreve])
    antes = EntradaAuditoria.objects.count()
    with pytest.raises(DatabaseError):
        conferir()
    assert EntradaAuditoria.objects.count() == antes


def test_invariante_violado_e_falha(ar: Any, sim: Any) -> None:  # A-4
    from apps.financeiro.models import AlertaFinanceiro

    sim.ajustar_saldo(D("-100000.00"))
    texto, codigo = conferir()
    assert resultado(texto, "Invariante financeiro") == "FALHA"
    assert "-" in secao(texto, "Invariante financeiro")
    assert codigo == 1
    assert "1 falha(s)" in texto.strip().splitlines()[-1]
    assert not AlertaFinanceiro.objects.filter(tipo="invariante_violado").exists()


def test_provedor_indisponivel_e_atencao(ar: Any, sim: Any) -> None:  # A-5
    sim.indisponivel()
    texto, codigo = conferir()
    assert resultado(texto, "Invariante financeiro") == "ATENÇÃO"
    assert "Provedor indisponível: conferir depois." in texto
    assert codigo == 0


def test_estoque_estourado_e_falha(ar: Any) -> None:  # A-6
    from apps.contas.models import Conta
    from apps.rodadas.models import EstoqueDaRodada
    from tests.apoio.interesses import cenario, reservada
    from tests.fabricas import ContaFactory

    rodada, produto, estoque = cenario(limite="30", nome="Q", preco=D("10.00"))
    reservada(ContaFactory.create(nome="Comprador Secreto"), produto, 18)
    EstoqueDaRodada.objects.filter(pk=estoque.pk).update(limite=D("10"))
    assert Conta.objects.exists()
    texto, codigo = conferir()
    secao_do_estoque = secao(texto, "Estoque")
    assert resultado(texto, "Estoque") == "FALHA"
    assert "Q" in secao_do_estoque
    assert rodada.fornecedor.nome in secao_do_estoque
    assert "18" in secao_do_estoque
    assert "10" in secao_do_estoque
    assert "Comprador Secreto" not in texto
    assert codigo == 1


def test_prazo_encerrado_e_atencao(sim: Any, relogio: RelogioControlado) -> None:  # A-7
    from apps.rodadas.fechamento import prazo_do_fechamento
    from tests.apoio.ciclos import simular_inicio_do_fechamento
    from tests.apoio.interesses import cenario, reservada
    from tests.fabricas import ContaFactory

    rodada, produto, _estoque = cenario(limite="30", nome="Q", preco=D("10.00"), multiplo=D("12"))
    reservada(ContaFactory.create(), produto, 18)
    simular_inicio_do_fechamento(rodada)
    prazo = prazo_do_fechamento(rodada)
    assert prazo is not None
    relogio.congelar(prazo + 2 * H)
    texto, codigo = conferir()
    assert resultado(texto, "Prazos encerrados") == "ATENÇÃO"
    assert "fechamento vencido" in secao(texto, "Prazos encerrados")
    assert (
        "Prazos vencidos durante a indisponibilidade continuam valendo (infraestrutura 6)." in texto
    )
    assert codigo == 0


def test_pendencias_com_o_provedor(sim: Any, relogio: RelogioControlado) -> None:  # A-8
    from apps.notificacoes.models import Envio
    from apps.pagamentos.models import ChamadaAoProvedor
    from tests.apoio.devolucoes import arranjo_da_devolucao, parcela_de_fabrica
    from tests.fabricas import EnvioFactory

    a = arranjo_da_devolucao(sim, relogio)
    parcela_de_fabrica(a, "em_processamento")
    ChamadaAoProvedor.objects.create(
        operacao="cancelar_cobranca",
        alvo="x",
        chave_idempotencia="k-x",
        provedor="simulador",
        ambiente="teste",
        situacao="pendente",
        proxima_em=I,
    )
    EnvioFactory.create_batch(2)
    pendentes = ChamadaAoProvedor.objects.filter(situacao="pendente").count()
    envios = Envio.objects.filter(situacao="pendente").count()
    assert envios >= 2
    texto, _codigo = conferir()
    trecho = secao(texto, "Pendências com o provedor")
    assert resultado(texto, "Pendências com o provedor") == "ATENÇÃO"
    assert f"Chamadas ao provedor pendentes: {pendentes}" in trecho
    assert "Devoluções não concluídas no provedor: 1" in trecho
    assert f"Envios pendentes: {envios}" in trecho


def test_dias_sem_conciliacao(ar: Any, relogio: RelogioControlado) -> None:  # A-9
    relogio.congelar(I + timedelta(days=2))
    texto, _codigo = conferir()
    trecho = secao(texto, "Conciliação")
    assert resultado(texto, "Conciliação") == "ATENÇÃO"
    assert "19/11/2026" in trecho
    assert "Dias encerrados sem conciliação: 2" in trecho


def test_antes_de_limita_o_extrato(ar: Any) -> None:  # A-10
    primeiro, _ = conferir("--antes-de", "2026-11-20T11:30")
    extrato = secao(primeiro, "Reconferir com o extrato")
    assert "R$ 1.000,00" in extrato
    assert "R$ 170,00" in extrato
    segundo, _ = conferir("--antes-de", "2026-11-20T10:30")
    extrato = secao(segundo, "Reconferir com o extrato")
    assert "R$ 170,00" in extrato
    assert "R$ 1.000,00" not in extrato


def test_antes_de_invalido(ar: Any) -> None:  # A-11
    texto, codigo = conferir("--antes-de", "ontem")
    assert "Instante inválido: use AAAA-MM-DDTHH:MM." in texto
    assert codigo == 2
    assert "Ponto recuperado" not in texto


def test_o_relatorio_nao_traz_dados_pessoais_nem_segredos(ar: Any) -> None:  # A-12
    from apps.contas.models import Conta

    compradores = Conta.objects.exclude(papel="administrador")
    assert compradores.exists()
    texto, _codigo = conferir()
    for conta in compradores:
        for valor in (conta.nome, conta.email_normalizado, conta.telefone):
            if valor:
                assert str(valor) not in texto, valor
    assert "postgres://" not in texto
    assert "DATABASE_URL" not in texto


# --- correção E16-R04: o estoque da conferência é o da rodada ativa ---------------------------


def _estoque_do_produto(
    sim: Any, relogio: RelogioControlado, etapa_antiga: str, limite_novo: str, etapa_nova: str
) -> tuple[str, int]:
    from apps.rodadas.models import Etapa  # noqa: F401
    from tests.fabricas import (
        EstoqueDaRodadaFactory,
        FornecedorFactory,
        ParcelaFactory,
        ProdutoFactory,
        RodadaFactory,
    )

    relogio.congelar(I)
    fornecedor = FornecedorFactory.create()
    produto = ProdutoFactory.create(fornecedor=fornecedor)
    velha = RodadaFactory.create(fornecedor=fornecedor, etapa=etapa_antiga)
    nova = RodadaFactory.create(fornecedor=fornecedor, etapa=etapa_nova)
    EstoqueDaRodadaFactory.create(rodada=velha, produto=produto, limite=D("1"))
    EstoqueDaRodadaFactory.create(rodada=nova, produto=produto, limite=D(limite_novo))
    ParcelaFactory.create(produto=produto, quantidade_original=D("5"), quantidade_reservada=D("5"))
    texto, codigo = conferir()
    return texto, codigo


def test_estoque_historico_nao_acusa_falha(sim: Any, relogio: RelogioControlado) -> None:  # A-14
    texto, codigo = _estoque_do_produto(sim, relogio, "disponivel_para_retirada", "10", "interesse")
    assert resultado(texto, "Estoque") == "OK"
    assert codigo == 0


def test_excesso_real_no_estoque_atual_continua_falha(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-15
    texto, codigo = _estoque_do_produto(sim, relogio, "disponivel_para_retirada", "3", "interesse")
    trecho = secao(texto, "Estoque")
    assert resultado(texto, "Estoque") == "FALHA"
    linhas = [linha for linha in trecho.splitlines()[1:] if linha.strip()]
    assert len(linhas) == 1
    assert "reservado 5" in linhas[0]
    assert "estoque 3" in linhas[0]
    assert "estoque 1" not in trecho
    assert codigo == 1


def test_rodada_cancelada_nao_entra_no_estoque(sim: Any, relogio: RelogioControlado) -> None:
    # A-16
    texto, _codigo = _estoque_do_produto(sim, relogio, "cancelada", "10", "pagamento")
    assert resultado(texto, "Estoque") == "OK"
