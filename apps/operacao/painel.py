"""O painel do administrador (E15-05): tudo calculado na leitura da página.

O painel não cria regra de negócio nem escreve: cada ação e cada linha apontam para a tela que já
executa ou detalha o assunto. Quando o worker para, ele é a única forma de ver isso (E15-01,
"Limitação"). Não mostra nome, e-mail nem WhatsApp de comprador: rodadas e ações são por
fornecedor, e os valores são agregados.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.urls import reverse

from apps.catalogo.quantidades import formatar_quantidade
from apps.catalogo.templatetags.catalogo import reais
from apps.financeiro.alertas import TEXTO_POR_TIPO, alertas_abertos
from apps.financeiro.devolucoes import situacao_da_devolucao
from apps.financeiro.liquidez import liquidez
from apps.financeiro.models import (
    AlertaFinanceiro,
    ConciliacaoDiaria,
    ContaFinanceira,
    Destinacao,
    Gravidade,
    ObrigacaoComComprador,
)
from apps.financeiro.reserva import itens_sem_cobertura
from apps.interesses.progresso import progresso_da_rodada
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.operacao.execucao import ATRASADA, SEM_REGISTRO, situacao_das_tarefas
from apps.operacao.tipos import CLASSIFICACAO, Natureza, link_do_alerta
from apps.pedidos.endereco_de_retirada import endereco_vigente
from apps.pedidos.liberacao_da_retirada import liberacao_da_rodada
from apps.pedidos.models import (
    AberturaDoPagamento,
    ApuracaoFinal,
    EnvioDoPedidoFormal,
    PedidoFormal,
    ResultadoDaApuracao,
    SituacaoDoEnvio,
)
from apps.pedidos.prazos import fim_da_margem, pode_iniciar_apuracao, prazo_de_pagamento
from apps.pedidos.recebimento import recebimento_resolvido, situacao_do_recebimento
from apps.pedidos.retirada import situacao_da_retirada
from apps.rodadas.fechamento import prazo_do_fechamento
from apps.rodadas.models import Etapa, Rodada

TRACO = "—"
ZERO = Decimal("0")
ORDEM_DAS_ETAPAS = {valor: indice for indice, valor in enumerate(Etapa.values)}
ETAPAS_DO_PAINEL = (
    Etapa.INTERESSE,
    Etapa.FECHAMENTO,
    Etapa.FECHAMENTO_ENCERRADO,
    Etapa.PAGAMENTO,
    Etapa.AGUARDANDO_FORNECEDOR,
    Etapa.DISPONIVEL_PARA_RETIRADA,
)


@dataclass(frozen=True)
class AcaoNecessaria:
    rodada: int | None
    fornecedor: str | None
    texto: str
    link: str


@dataclass(frozen=True)
class LinhaDaRodada:
    rodada: int
    fornecedor: str
    etapa: str
    minimo: str
    caixas: list[str]
    prazo: str
    link: str


@dataclass(frozen=True)
class PrazoEncerrado:
    texto: str
    link: str


def _data(instante: datetime) -> str:
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}"


def _rodadas_do_painel() -> list[Rodada]:
    rodadas = Rodada.objects.filter(etapa__in=ETAPAS_DO_PAINEL).select_related("fornecedor")
    return sorted(rodadas, key=lambda r: (ORDEM_DAS_ETAPAS[r.etapa], r.fornecedor.nome, r.pk))


def _abertura(rodada: Rodada) -> AberturaDoPagamento | None:
    return AberturaDoPagamento.objects.filter(rodada=rodada).order_by("-pk").first()


def _conta_de_leitura(destinacao: str, chave: str) -> ContaFinanceira | None:
    """A conta, sem criá-la (`livro.conta` cria no primeiro uso, e o painel só lê)."""
    return ContaFinanceira.objects.filter(destinacao=destinacao, chave=chave).first()


def _itens_da_retirada(rodada: Rodada) -> tuple[Any, list[Any]]:
    """A situação da retirada da rodada liberada e os itens com saldo; sem liberação, `None`."""
    if liberacao_da_rodada(rodada) is None:
        return None, []
    situacao = situacao_da_retirada(rodada)
    com_saldo = [i for p in situacao.pedidos for i in p.itens if i.saldo > 0]
    return situacao, com_saldo


# --- ações necessárias --------------------------------------------------------------------------


def _acoes_da_rodada(rodada: Rodada, instante: datetime) -> list[tuple[str, str]]:
    """Os pares `(texto, nome da rota)` das ações da rodada, na ordem da especificação."""
    estoque = "rodadas_estoque"
    acoes: list[tuple[str, str]] = []
    if rodada.etapa == Etapa.INTERESSE and progresso_da_rodada(rodada).atingido:
        acoes.append(("Mínimo atingido: o fechamento pode ser iniciado.", estoque))
    if rodada.etapa == Etapa.FECHAMENTO_ENCERRADO:
        acoes.append(("Fechamento encerrado: aguarda a abertura do pagamento.", estoque))
    if rodada.etapa == Etapa.PAGAMENTO:
        abertura = _abertura(rodada)
        if abertura is not None:
            apuracao = ApuracaoFinal.objects.filter(abertura=abertura).first()
            if apuracao is None and pode_iniciar_apuracao(abertura, instante):
                acoes.append(
                    (f"Apta para a apuração final desde {_data(fim_da_margem(abertura))}.", estoque)
                )
            elif (
                apuracao is not None
                and apuracao.resultado == ResultadoDaApuracao.VALIDA
                and not hasattr(apuracao, "aprovacao")
            ):
                acoes.append(("Apuração feita: aguarda a aprovação do resultado.", estoque))
    if rodada.etapa == Etapa.AGUARDANDO_FORNECEDOR:
        acoes += _acoes_do_pedido_formal(rodada)
    if rodada.etapa in (Etapa.AGUARDANDO_FORNECEDOR, Etapa.DISPONIVEL_PARA_RETIRADA):
        acoes += _acoes_das_saidas(rodada)
    if rodada.etapa == Etapa.DISPONIVEL_PARA_RETIRADA:
        situacao, _com_saldo = _itens_da_retirada(rodada)
        if situacao is not None and situacao.prazo_encerrado and situacao.vencidos:
            acoes.append(
                (
                    f"Prazo de retirada encerrado: {len(situacao.vencidos)} item(ns) "
                    "pendente(s) de decisão.",
                    "rodadas_retiradas",
                )
            )
    return acoes


def _acoes_do_pedido_formal(rodada: Rodada) -> list[tuple[str, str]]:
    acoes: list[tuple[str, str]] = []
    pedido_formal = PedidoFormal.objects.filter(rodada=rodada).first()
    if pedido_formal is None:
        return acoes
    envio = EnvioDoPedidoFormal.objects.filter(pedido_formal=pedido_formal).first()
    if envio is not None and envio.situacao == SituacaoDoEnvio.CONCLUIDO_COM_FALHAS:
        acoes.append(
            (
                "O pedido formal não foi enviado depois das três tentativas: reenvie.",
                "rodadas_pedido_formal",
            )
        )
    if recebimento_resolvido(rodada):
        texto = "Recebimento resolvido: a retirada pode ser liberada."
        if endereco_vigente() is None:
            texto += " Registre antes o endereço de retirada."
        acoes.append((texto, "rodadas_recebimento"))
    else:
        a_resolver = sum(1 for linha in situacao_do_recebimento(rodada) if linha.a_resolver > 0)
        if a_resolver:
            acoes.append(
                (f"Recebimento: {a_resolver} produto(s) a resolver.", "rodadas_recebimento")
            )
    return acoes


def _acoes_das_saidas(rodada: Rodada) -> list[tuple[str, str]]:
    acoes: list[tuple[str, str]] = []
    obrigacao = _conta_de_leitura(
        Destinacao.OBRIGACAO_FORNECEDOR, f"f{rodada.fornecedor_id}:r{rodada.pk}"
    )
    frete = _conta_de_leitura(Destinacao.FRETE, f"r{rodada.pk}")
    if obrigacao is not None and liquidez(obrigacao).liberado > 0:
        valor = reais(liquidez(obrigacao).liberado)
        acoes.append((f"Repasse ao fornecedor liberado: {valor}.", "rodadas_saidas"))
    if frete is not None and liquidez(frete).liberado > 0:
        acoes.append(
            (f"Pagamento do frete liberado: {reais(liquidez(frete).liberado)}.", "rodadas_saidas")
        )
    return acoes


def _acoes_globais() -> list[AcaoNecessaria]:
    acoes: list[AcaoNecessaria] = []
    devidas = [
        o
        for o in ObrigacaoComComprador.objects.order_by("pk")
        if situacao_da_devolucao(o) == "devida" and o.devido > 0
    ]
    if devidas:
        soma = sum((o.devido for o in devidas), ZERO)
        acoes.append(
            AcaoNecessaria(
                None,
                None,
                f"Devoluções a autorizar: {len(devidas)} ({reais(soma)}).",
                reverse("financeiro_devolucoes"),
            )
        )
    sem_cobertura = itens_sem_cobertura()
    if sem_cobertura:
        soma = sum((i.valor for i in sem_cobertura), ZERO)
        acoes.append(
            AcaoNecessaria(
                None,
                None,
                f"Itens sem cobertura: {len(sem_cobertura)} ({reais(soma)}).",
                reverse("financeiro_reserva"),
            )
        )
    return acoes


def acoes_necessarias(instante: datetime) -> list[AcaoNecessaria]:
    """As ações que esperam o administrador: primeiro as das rodadas (por fornecedor e rodada),
    depois as globais."""
    acoes: list[AcaoNecessaria] = []
    for rodada in _rodadas_do_painel():
        for texto, rota in _acoes_da_rodada(rodada, instante):
            acoes.append(
                AcaoNecessaria(
                    rodada.pk,
                    rodada.fornecedor.nome,
                    texto,
                    reverse(rota, args=[rodada.pk]),
                )
            )
    return acoes + _acoes_globais()


# --- rodadas ------------------------------------------------------------------------------------


def _caixas(rodada: Rodada) -> list[str]:
    linhas = []
    for produto in progresso_da_rodada(rodada).produtos:
        if produto.produto.multiplo is None or produto.excedente <= 0:
            continue
        faltam = formatar_quantidade(produto.faltam_para_proxima_caixa or ZERO)
        linhas.append(
            f"{produto.produto.nome}: {formatar_quantidade(produto.excedente)} "
            f"{produto.produto.unidade} aguardando, faltam {faltam} para a próxima caixa"
        )
    return linhas


def _prazo_da_rodada(rodada: Rodada) -> str:
    if rodada.etapa in (Etapa.FECHAMENTO, Etapa.FECHAMENTO_ENCERRADO):
        prazo = prazo_do_fechamento(rodada)
        if prazo is None:
            return TRACO
        rotulo = "Fecha em" if rodada.etapa == Etapa.FECHAMENTO else "Encerrado em"
        return f"{rotulo} {_data(prazo)}"
    if rodada.etapa == Etapa.PAGAMENTO:
        abertura = _abertura(rodada)
        if abertura is None:
            return TRACO
        return (
            f"Pagamento até {_data(prazo_de_pagamento(abertura))}; "
            f"margem até {_data(fim_da_margem(abertura))}"
        )
    if rodada.etapa == Etapa.DISPONIVEL_PARA_RETIRADA:
        liberacao = liberacao_da_rodada(rodada)
        return TRACO if liberacao is None else f"Retirada até {_data(liberacao.prazo_final)}"
    return TRACO


def rodadas_do_painel(instante: datetime) -> list[LinhaDaRodada]:
    """As rodadas em andamento. Uma rodada liberada só aparece enquanto algum item tem saldo."""
    linhas: list[LinhaDaRodada] = []
    for rodada in _rodadas_do_painel():
        if rodada.etapa == Etapa.DISPONIVEL_PARA_RETIRADA and not _itens_da_retirada(rodada)[1]:
            continue
        minimo = TRACO
        caixas: list[str] = []
        if rodada.etapa in (Etapa.INTERESSE, Etapa.FECHAMENTO, Etapa.FECHAMENTO_ENCERRADO):
            progresso = progresso_da_rodada(rodada)
            minimo = (
                f"{reais(progresso.valor_elegivel)} de {reais(progresso.minimo)} "
                f"({progresso.percentual}%)"
            )
        if rodada.etapa in (Etapa.INTERESSE, Etapa.FECHAMENTO):
            caixas = _caixas(rodada)
        linhas.append(
            LinhaDaRodada(
                rodada=rodada.pk,
                fornecedor=rodada.fornecedor.nome,
                etapa=str(Etapa(rodada.etapa).label),
                minimo=minimo,
                caixas=caixas,
                prazo=_prazo_da_rodada(rodada),
                link=reverse("rodadas_estoque", args=[rodada.pk]),
            )
        )
    return linhas


# --- prazos encerrados --------------------------------------------------------------------------


def prazos_encerrados(instante: datetime) -> list[PrazoEncerrado]:
    """As rodadas cujo prazo terminou e que esperam o administrador ou uma tarefa."""
    linhas: list[PrazoEncerrado] = []
    for rodada in _rodadas_do_painel():
        nome = rodada.fornecedor.nome
        estoque = reverse("rodadas_estoque", args=[rodada.pk])
        if rodada.etapa == Etapa.FECHAMENTO:
            prazo = prazo_do_fechamento(rodada)
            if prazo is not None and prazo <= instante:
                texto = (
                    f"{nome}: fechamento vencido em {_data(prazo)}, "
                    "aguardando o encerramento automático."
                )
                linhas.append(PrazoEncerrado(texto, estoque))
        elif rodada.etapa == Etapa.FECHAMENTO_ENCERRADO:
            prazo = prazo_do_fechamento(rodada)
            if prazo is not None:
                linhas.append(
                    PrazoEncerrado(f"{nome}: fechamento encerrado em {_data(prazo)}.", estoque)
                )
        elif rodada.etapa == Etapa.PAGAMENTO:
            abertura = _abertura(rodada)
            if (
                abertura is not None
                and not ApuracaoFinal.objects.filter(abertura=abertura).exists()
                and fim_da_margem(abertura) <= instante
            ):
                linhas.append(
                    PrazoEncerrado(
                        f"{nome}: margem encerrada em {_data(fim_da_margem(abertura))}.", estoque
                    )
                )
        elif rodada.etapa == Etapa.DISPONIVEL_PARA_RETIRADA:
            liberacao = liberacao_da_rodada(rodada)
            _situacao, com_saldo = _itens_da_retirada(rodada)
            if liberacao is not None and liberacao.prazo_final <= instante and com_saldo:
                texto = (
                    f"{nome}: retirada encerrada em {_data(liberacao.prazo_final)}, "
                    "com itens pendentes."
                )
                linhas.append(PrazoEncerrado(texto, reverse("rodadas_retiradas", args=[rodada.pk])))
    return linhas


# --- alertas e tarefas --------------------------------------------------------------------------


def _titulo_e_corpo(alerta: AlertaFinanceiro) -> tuple[str, str]:
    classificacao = CLASSIFICACAO.get(alerta.tipo)
    if classificacao is not None:
        return classificacao.titulo, classificacao.corpo(alerta.dados)
    titulo, montar_corpo = TEXTO_POR_TIPO[alerta.tipo]
    return titulo, montar_corpo(alerta.dados)


def _alertas() -> list[dict[str, Any]]:
    linhas = []
    for alerta in alertas_abertos():
        titulo, corpo = _titulo_e_corpo(alerta)
        classificacao = CLASSIFICACAO.get(alerta.tipo)
        linhas.append(
            {
                "pk": alerta.pk,
                "gravidade": "Crítico" if alerta.gravidade == Gravidade.CRITICO else "Aviso",
                "titulo": titulo,
                "corpo": corpo,
                "aberto_em": _data(alerta.aberto_em),
                "link": link_do_alerta(alerta),
                "ciencia": classificacao is not None and classificacao.natureza == Natureza.FATO,
            }
        )
    return linhas


def _tarefas(instante: datetime) -> list[dict[str, Any]]:
    linhas = []
    for tarefa in situacao_das_tarefas(instante):
        if tarefa.estado == ATRASADA and tarefa.atrasada_desde is not None:
            situacao = f"Atrasada desde {_data(tarefa.atrasada_desde)}"
        elif tarefa.estado == SEM_REGISTRO:
            situacao = "Sem registro de execução"
        else:
            situacao = "Em dia"
        falha = ""
        if tarefa.ultima_falha_em is not None:
            falha = f"Última falha em {_data(tarefa.ultima_falha_em)}: {tarefa.ultimo_erro}"
        linhas.append(
            {
                "descricao": tarefa.descricao,
                "ultima_conclusao": (
                    _data(tarefa.ultima_conclusao_em) if tarefa.ultima_conclusao_em else TRACO
                ),
                "situacao": situacao,
                "falha": falha,
            }
        )
    return linhas


def _ultima_conciliacao() -> str:
    ultima = ConciliacaoDiaria.objects.order_by("-data").first()
    if ultima is None:
        return "Nenhuma conciliação registrada."
    rotulo = ConciliacaoDiaria.Resultado(ultima.resultado).label
    return f"Última conciliação: {ultima.data:%d/%m/%Y} ({rotulo})"


def contexto_do_painel(instante: datetime) -> dict[str, Any]:
    """Tudo o que a página mostra, lido uma vez com o `instante` dado."""
    return {
        "alertas": _alertas(),
        "acoes": acoes_necessarias(instante),
        "rodadas": rodadas_do_painel(instante),
        "prazos_encerrados": prazos_encerrados(instante),
        "tarefas": _tarefas(instante),
        "ultima_conciliacao": _ultima_conciliacao(),
    }
