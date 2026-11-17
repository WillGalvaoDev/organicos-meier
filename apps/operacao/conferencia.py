"""A conferência depois de uma restauração (E16-05): o relatório do comando `conferir_restauracao`.

Só leitura. O relatório inteiro roda numa transação marcada como somente leitura (`SET LOCAL
transaction_read_only`) e desfeita no fim: uma escrita, em qualquer seção, é erro de programação e
falha o comando. A única chamada externa é a consulta de saldo ao provedor (o simulador, na fase 1).

O relatório não traz nome, e-mail nem WhatsApp de comprador (só identificadores internos, nomes de
fornecedor, valores e datas) e nenhum segredo.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db import connection, transaction
from django.db.models import Sum

from apps.catalogo.quantidades import formatar_quantidade
from apps.catalogo.templatetags.catalogo import reais
from apps.financeiro.invariante import obrigacoes_de_terceiros
from apps.financeiro.models import (
    ConciliacaoDiaria,
    MovimentoFinanceiro,
    ParcelaDeDevolucao,
    SituacaoDaParcela,
    TipoDeMovimento,
)
from apps.interesses.consultas import total_reservado
from apps.notificacoes.models import Envio, SituacaoEnvio
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.operacao.models import BackupExterno
from apps.operacao.painel import prazos_encerrados
from apps.pagamentos.models import ChamadaAoProvedor, SituacaoDaChamada
from apps.pagamentos.provedor import ProvedorIndisponivel, RecusaDoProvedor, obter_provedor
from apps.rodadas.models import EstoqueDaRodada, Etapa

OK = "OK"
ATENCAO = "ATENÇÃO"
FALHA = "FALHA"
MAXIMO_NO_EXTRATO = 20
TIPOS_DO_EXTRATO = (
    TipoDeMovimento.APORTE,
    TipoDeMovimento.REPASSE,
    TipoDeMovimento.PAGAMENTO_DO_FRETE,
    TipoDeMovimento.RETIRADA_DE_RECEITA,
    TipoDeMovimento.DEVOLUCAO_EXCEPCIONAL,
)
FRASE_DOS_PRAZOS = (
    "Prazos vencidos durante a indisponibilidade continuam valendo (infraestrutura 6)."
)
FRASE_DO_EXTRATO = (
    "Movimentos registrados depois do ponto recuperado não estão aqui: conferir com o extrato "
    "e os comprovantes."
)


@dataclass
class Secao:
    titulo: str
    resultado: str
    linhas: list[str] = field(default_factory=list)


def _quando(instante: datetime | None) -> str:
    if instante is None:
        return "nenhum registro"
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}"


def _ponto_recuperado(instante: datetime, antes_de: datetime | None) -> Secao:
    movimento = MovimentoFinanceiro.objects.order_by("-momento").values_list("momento", flat=True)
    auditoria = EntradaAuditoria.objects.order_by("-momento").values_list("momento", flat=True)
    backup = BackupExterno.objects.order_by("-concluido_em").values_list("concluido_em", flat=True)
    return Secao(
        "Ponto recuperado",
        OK,
        [
            f"Último movimento do livro-razão: {_quando(movimento.first())}",
            f"Última entrada de auditoria: {_quando(auditoria.first())}",
            f"Último backup externo: {_quando(backup.first())}",
        ],
    )


def _invariante(instante: datetime, antes_de: datetime | None) -> Secao:
    try:
        saldo = obter_provedor().consultar_saldo()
    except (ProvedorIndisponivel, RecusaDoProvedor):
        return Secao("Invariante financeiro", ATENCAO, ["Provedor indisponível: conferir depois."])
    total = saldo.liberado + saldo.a_liberar
    terceiros = obrigacoes_de_terceiros(saldo.referente_a)
    diferenca = total - terceiros
    return Secao(
        "Invariante financeiro",
        OK if diferenca >= 0 else FALHA,
        [
            f"Saldo do provedor (liberado + a liberar): {reais(total)}",
            f"Obrigações de terceiros: {reais(terceiros)}",
            f"Diferença: {reais(diferenca)}",
        ],
    )


def _estoque(instante: datetime, antes_de: datetime | None) -> Secao:
    estoques = (
        EstoqueDaRodada.objects.exclude(rodada__etapa=Etapa.CANCELADA)
        .exclude(limite__isnull=True)
        .select_related("rodada__fornecedor", "produto")
        .order_by("rodada_id", "produto_id")
    )
    linhas = []
    for estoque in estoques:
        reservado = total_reservado(estoque.produto)
        if estoque.limite is not None and reservado > estoque.limite:
            linhas.append(
                f"{estoque.rodada.fornecedor.nome} · {estoque.produto.nome}: "
                f"reservado {formatar_quantidade(reservado)}, "
                f"estoque {formatar_quantidade(estoque.limite)}"
            )
    return Secao("Estoque", FALHA if linhas else OK, linhas)


def _prazos(instante: datetime, antes_de: datetime | None) -> Secao:
    linhas = [prazo.texto for prazo in prazos_encerrados(instante)]
    if not linhas:
        return Secao("Prazos encerrados", OK, [])
    return Secao("Prazos encerrados", ATENCAO, [*linhas, FRASE_DOS_PRAZOS])


def _pendencias(instante: datetime, antes_de: datetime | None) -> Secao:
    chamadas = ChamadaAoProvedor.objects.filter(situacao=SituacaoDaChamada.PENDENTE).count()
    devolucoes = (
        ParcelaDeDevolucao.objects.exclude(
            situacao__in=(
                SituacaoDaParcela.CONCLUIDA,
                SituacaoDaParcela.CONCLUIDA_FORA_DA_PLATAFORMA,
            )
        )
    ).count()
    envios = Envio.objects.filter(situacao=SituacaoEnvio.PENDENTE).count()
    return Secao(
        "Pendências com o provedor",
        ATENCAO if chamadas or devolucoes or envios else OK,
        [
            f"Chamadas ao provedor pendentes: {chamadas}",
            f"Devoluções não concluídas no provedor: {devolucoes}",
            f"Envios pendentes: {envios}",
        ],
    )


def _conciliacao(instante: datetime, antes_de: datetime | None) -> Secao:
    hoje = no_fuso_da_operacao(instante).date()
    ultima = ConciliacaoDiaria.objects.order_by("-data").first()
    primeiro = ultima.data + timedelta(days=1) if ultima is not None else hoje - timedelta(days=1)
    sem_conciliar = max(0, (hoje - primeiro).days)  # como a E09-07: cada dia terminado
    ultima_linha = (
        "Nenhuma conciliação registrada."
        if ultima is None
        else f"Última conciliação: {ultima.data:%d/%m/%Y}"
    )
    return Secao(
        "Conciliação",
        ATENCAO if sem_conciliar else OK,
        [ultima_linha, f"Dias encerrados sem conciliação: {sem_conciliar}"],
    )


def _extrato(instante: datetime, antes_de: datetime | None) -> Secao:
    movimentos = MovimentoFinanceiro.objects.filter(tipo__in=TIPOS_DO_EXTRATO)
    if antes_de is not None:
        movimentos = movimentos.filter(momento__lt=antes_de)
    linhas = [
        f"{_quando(m.momento)} · {TipoDeMovimento(m.tipo).label} · {reais(m.valor_total)}"
        for m in movimentos.annotate(valor_total=Sum("transferencias__valor")).order_by(
            "-momento", "-pk"
        )[:MAXIMO_NO_EXTRATO]
    ]
    if not linhas:
        return Secao("Reconferir com o extrato", OK, [])
    return Secao("Reconferir com o extrato", ATENCAO, [*linhas, FRASE_DO_EXTRATO])


Conferencia = Callable[[datetime, datetime | None], Secao]
SECOES: list[Conferencia] = [
    _ponto_recuperado,
    _invariante,
    _estoque,
    _prazos,
    _pendencias,
    _conciliacao,
    _extrato,
]


def conferir(instante: datetime, antes_de: datetime | None = None) -> list[Secao]:
    """Roda as conferências numa transação somente leitura, sempre desfeita no fim."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL transaction_read_only = on")
        secoes = [conferencia(instante, antes_de) for conferencia in list(SECOES)]
        transaction.set_rollback(True)  # nada a confirmar; também desfaz o SET LOCAL
    return secoes


def formatar(secoes: list[Secao]) -> tuple[list[str], int, int]:
    """As linhas do relatório, o número de falhas e o de atenções."""
    linhas: list[str] = []
    for numero, secao in enumerate(secoes, start=1):
        linhas.append(f"{numero}. {secao.titulo}: {secao.resultado}")
        linhas.extend(f"   {linha}" for linha in secao.linhas)
    falhas = sum(1 for s in secoes if s.resultado == FALHA)
    atencoes = sum(1 for s in secoes if s.resultado == ATENCAO)
    linhas.append(f"Conferência: {falhas} falha(s), {atencoes} atenção(ões).")
    return linhas, falhas, atencoes
