"""Os alertas de falha de comunicação e do provedor (E15-04): seis verificações.

Os tipos de **fato** registram um acontecimento passado e se encerram pela ciência do administrador
(`apps.operacao.ciencia`). A verificação de um fato devolve cada fato que não tem alerta do par com
`aberto_em` posterior (ou igual) ao instante dele, esteja esse alerta aberto ou resolvido: um fato
já alertado e com ciência não volta, e um fato novo do mesmo par abre outro alerta.

As verificações só leem; nenhuma muda pagamento, chamada, envio ou destino. Os dados não levam
dado pessoal de comprador.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Max
from django.urls import reverse

from apps.catalogo.templatetags.catalogo import reais
from apps.financeiro.models import AlertaFinanceiro, Gravidade, TipoDeAlerta
from apps.notificacoes.models import Envio, SituacaoEnvio
from apps.operacao.tipos import Classificacao, Natureza, data_e_hora, registrar_tipo
from apps.operacao.verificacao import registrar_verificacao
from apps.pagamentos.models import (
    ChamadaAoProvedor,
    ConsultaDoPagamento,
    DivergenciaDaConsulta,
    PagamentoNoProvedor,
    SequenciaDeAvisosRecusados,
    SituacaoDaChamada,
)
from apps.pedidos.models import DestinoDaDecisao, DestinoDoPagamento, MotivoDoDestino

JANELA_DA_FALHA_DE_MENSAGEM = timedelta(hours=24)
OPERACOES_COM_ALERTA = ("cancelar_cobranca", "consultar_pagamento")
LIMITE_DE_RECUSAS = 5

Dados = dict[str, Any]


def _sem_alerta_posterior(tipo: str, fatos: dict[str, tuple[datetime, Dados]]) -> dict[str, Dados]:
    """Os fatos (chave -> instante e dados) sem alerta do par aberto a partir do instante deles."""
    ultimos = dict(
        AlertaFinanceiro.objects.filter(tipo=tipo, chave__in=list(fatos))
        .values_list("chave")
        .annotate(ultimo=Max("aberto_em"))
    )
    return {
        chave: dados
        for chave, (instante, dados) in fatos.items()
        if chave not in ultimos or ultimos[chave] < instante
    }


# --- falha de mensagem (condição) ---------------------------------------------------------------


def _falhas_de_mensagem(instante: datetime) -> dict[str, Dados]:
    recentes = Envio.objects.filter(
        situacao=SituacaoEnvio.FALHOU, concluido_em__gte=instante - JANELA_DA_FALHA_DE_MENSAGEM
    )
    resumo = recentes.aggregate(quantidade=Count("pk"), mais_recente=Max("concluido_em"))
    if not resumo["quantidade"]:
        return {}
    return {
        "geral": {
            "quantidade": resumo["quantidade"],
            "mais_recente": resumo["mais_recente"].isoformat(),
        }
    }


# --- chamada ao provedor que falhou (fato) ------------------------------------------------------


def _chamadas_que_falharam(instante: datetime) -> dict[str, Dados]:
    fatos: dict[str, tuple[datetime, Dados]] = {}
    chamadas = ChamadaAoProvedor.objects.filter(
        situacao=SituacaoDaChamada.FALHOU,
        operacao__in=OPERACOES_COM_ALERTA,
        concluida_em__isnull=False,
    )
    for chamada in chamadas:
        if chamada.concluida_em is None:
            continue
        fatos[f"chamada:{chamada.pk}"] = (
            chamada.concluida_em,
            {
                "chamada": chamada.pk,
                "operacao": chamada.operacao,
                "alvo": chamada.alvo,
                "erro": chamada.ultimo_erro,
                "concluida_em": chamada.concluida_em.isoformat(),
            },
        )
    return _sem_alerta_posterior(TipoDeAlerta.CHAMADA_AO_PROVEDOR_FALHOU.value, fatos)


# --- consulta com divergência (fato) ------------------------------------------------------------


def _consultas_divergentes(instante: datetime) -> dict[str, Dados]:
    linhas = (
        ConsultaDoPagamento.objects.exclude(divergencia="")
        .values("pagamento__id_externo", "divergencia")
        .annotate(ultima=Max("consultado_em"))
    )
    fatos: dict[str, tuple[datetime, Dados]] = {}
    for linha in linhas:
        id_externo, divergencia = linha["pagamento__id_externo"], linha["divergencia"]
        fatos[f"{id_externo}:{divergencia}"] = (
            linha["ultima"],
            {
                "pagamento": id_externo,
                "divergencia": divergencia,
                "consultado_em": linha["ultima"].isoformat(),
            },
        )
    return _sem_alerta_posterior(TipoDeAlerta.CONSULTA_COM_DIVERGENCIA.value, fatos)


# --- pagamento sem pedido (fato) ----------------------------------------------------------------


def _pagamentos_sem_pedido(instante: datetime) -> dict[str, Dados]:
    fatos: dict[str, tuple[datetime, Dados]] = {}
    destinos = DestinoDoPagamento.objects.filter(
        destino=DestinoDaDecisao.SEM_PEDIDO
    ).select_related("pagamento")
    for destino in destinos:
        pagamento = destino.pagamento
        fatos[f"pagamento:{pagamento.id_externo}"] = (
            destino.decidido_em,
            {
                "pagamento": pagamento.id_externo,
                "valor": str(pagamento.valor),
                "motivo": destino.motivo,
                "decidido_em": destino.decidido_em.isoformat(),
            },
        )
    return _sem_alerta_posterior(TipoDeAlerta.PAGAMENTO_SEM_PEDIDO.value, fatos)


# --- pagamento aprovado sem horário (condição) --------------------------------------------------


def _pagamentos_sem_horario(instante: datetime) -> dict[str, Dados]:
    parados = PagamentoNoProvedor.objects.filter(
        situacao="aprovado", aprovado_no_provedor_em__isnull=True, destino__isnull=True
    )
    return {
        f"pagamento:{p.id_externo}": {"pagamento": p.id_externo, "valor": str(p.valor)}
        for p in parados
    }


# --- avisos recusados em sequência (condição) ---------------------------------------------------


def _avisos_recusados(instante: datetime) -> dict[str, Dados]:
    sequencia = SequenciaDeAvisosRecusados.objects.filter(pk=1).first()
    if sequencia is None or sequencia.recusas_seguidas < LIMITE_DE_RECUSAS:
        return {}
    primeira = sequencia.primeira_em or sequencia.ultima_em
    if primeira is None:
        return {}
    return {
        "geral": {
            "recusas": sequencia.recusas_seguidas,
            "primeira_em": primeira.isoformat(),
        }
    }


# --- textos e registro --------------------------------------------------------------------------


def _classificar(
    tipo: TipoDeAlerta,
    natureza: Natureza,
    titulo: str,
    corpo: Callable[[Dados], str],
    link: Callable[[Dados], str],
    verificacao: Callable[[datetime], dict[str, Dados]],
) -> None:
    registrar_tipo(
        tipo.value,
        Classificacao(
            gravidade=Gravidade.AVISO, natureza=natureza, titulo=titulo, corpo=corpo, link=link
        ),
    )
    registrar_verificacao(tipo.value, verificacao)


def _painel(dados: Dados) -> str:
    return reverse("painel_administracao")


_classificar(
    TipoDeAlerta.FALHA_DE_MENSAGEM,
    Natureza.CONDICAO,
    "Falha no envio de mensagens",
    lambda d: (
        f"{d['quantidade']} mensagem(ns) não foram entregues nas últimas 24 horas. "
        f"A mais recente falhou em {data_e_hora(d['mais_recente'])}."
    ),
    lambda d: reverse("envios_lista") + "?situacao=falhou",
    _falhas_de_mensagem,
)
_classificar(
    TipoDeAlerta.CHAMADA_AO_PROVEDOR_FALHOU,
    Natureza.FATO,
    "Chamada ao provedor falhou",
    lambda d: (
        f"A operação {d['operacao']} para {d['alvo']} falhou no provedor ({d['erro']}) "
        f"em {data_e_hora(d['concluida_em'])}."
    ),
    _painel,
    _chamadas_que_falharam,
)
_classificar(
    TipoDeAlerta.CONSULTA_COM_DIVERGENCIA,
    Natureza.FATO,
    "Divergência na consulta ao provedor",
    lambda d: (
        f"A consulta do pagamento {d['pagamento']} divergiu em "
        f"{DivergenciaDaConsulta(d['divergencia']).label} em {data_e_hora(d['consultado_em'])}."
    ),
    _painel,
    _consultas_divergentes,
)
_classificar(
    TipoDeAlerta.PAGAMENTO_SEM_PEDIDO,
    Natureza.FATO,
    "Pagamento sem pedido",
    lambda d: (
        f"O pagamento {d['pagamento']} de {reais(d['valor'])} foi aprovado sem pedido "
        f"correspondente ({MotivoDoDestino(d['motivo']).label})."
    ),
    _painel,
    _pagamentos_sem_pedido,
)
_classificar(
    TipoDeAlerta.PAGAMENTO_SEM_HORARIO_DE_APROVACAO,
    Natureza.CONDICAO,
    "Pagamento aprovado sem horário",
    lambda d: (
        f"O pagamento {d['pagamento']} de {reais(d['valor'])} está aprovado no provedor sem o "
        "horário de aprovação, e a decisão sobre ele está parada."
    ),
    _painel,
    _pagamentos_sem_horario,
)
_classificar(
    TipoDeAlerta.AVISOS_RECUSADOS_EM_SEQUENCIA,
    Natureza.CONDICAO,
    "Avisos do provedor recusados",
    lambda d: (
        f"{d['recusas']} avisos seguidos do provedor de pagamentos foram recusados como não "
        f"autênticos desde {data_e_hora(d['primeira_em'])}. "
        "Confira o segredo de verificação dos avisos."
    ),
    _painel,
    _avisos_recusados,
)
