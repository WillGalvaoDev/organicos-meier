"""Os alertas de atraso de processamento (E15-03): cinco verificações de condição.

Elas olham o efeito esperado de cada processamento, e não só se a tarefa roda (E15-01): acusam o
item que deveria ter andado e não andou. Só leem; nenhuma muda rodada, envio, chamada ou
conciliação. Os dados não levam dado pessoal de comprador.
"""

from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Min
from django.urls import reverse

from apps.financeiro.conciliacao import limites_do_dia
from apps.financeiro.models import ConciliacaoDiaria, Gravidade, TipoDeAlerta
from apps.notificacoes.models import Envio, SituacaoEnvio
from apps.operacao.tipos import Classificacao, Natureza, data_e_hora, registrar_tipo
from apps.operacao.verificacao import registrar_verificacao
from apps.pagamentos.models import ChamadaAoProvedor, SituacaoDaChamada
from apps.pedidos.models import EnvioDoPedidoFormal, SituacaoDoEnvio
from apps.rodadas.fechamento import prazo_do_fechamento
from apps.rodadas.models import Etapa, Rodada

MARGEM_DE_ATRASO = timedelta(minutes=5)
LIMITE_DA_CONCILIACAO = timedelta(hours=24)
LIMITE_DA_CHAMADA_PENDENTE = timedelta(hours=25)

Dados = dict[str, Any]


def _atrasado(instante: datetime, limite: datetime) -> bool:
    """Atrasado é estritamente depois da margem (regra comum 1)."""
    return instante - limite > MARGEM_DE_ATRASO


def _data(iso: str) -> str:
    return f"{date.fromisoformat(iso):%d/%m/%Y}"


# --- fechamento ---------------------------------------------------------------------------------


def _fechamentos(instante: datetime) -> dict[str, Dados]:
    achados: dict[str, Dados] = {}
    for rodada in Rodada.objects.filter(etapa=Etapa.FECHAMENTO).select_related("fornecedor"):
        prazo = prazo_do_fechamento(rodada)
        if prazo is not None and _atrasado(instante, prazo):
            achados[f"rodada:{rodada.pk}"] = {
                "rodada": rodada.pk,
                "fornecedor": rodada.fornecedor.nome,
                "prazo": prazo.isoformat(),
            }
    return achados


# --- pedido formal ------------------------------------------------------------------------------


def _pedidos_formais(instante: datetime) -> dict[str, Dados]:
    achados: dict[str, Dados] = {}
    envios = EnvioDoPedidoFormal.objects.filter(
        situacao=SituacaoDoEnvio.EM_ANDAMENTO, proxima_tentativa_em__isnull=False
    ).select_related("pedido_formal__fornecedor")
    for envio in envios:
        prevista = envio.proxima_tentativa_em
        if prevista is not None and _atrasado(instante, prevista):
            achados[f"pedido_formal:{envio.pedido_formal_id}"] = {
                "pedido_formal": envio.pedido_formal_id,
                "rodada": envio.pedido_formal.rodada_id,
                "fornecedor": envio.pedido_formal.fornecedor.nome,
                "prevista_para": prevista.isoformat(),
            }
    return achados


# --- conciliação --------------------------------------------------------------------------------


def _conciliacoes(instante: datetime) -> dict[str, Dados]:
    ultima = ConciliacaoDiaria.objects.order_by("-data").first()
    if ultima is None:
        return {}
    pendente = ultima.data + timedelta(days=1)
    fim = limites_do_dia(pendente)[1]
    if instante - fim <= LIMITE_DA_CONCILIACAO:
        return {}
    return {
        f"dia:{pendente.isoformat()}": {
            "dia": pendente.isoformat(),
            "ultima_conciliada": ultima.data.isoformat(),
        }
    }


# --- chamadas ao provedor -----------------------------------------------------------------------


def _chamadas(instante: datetime) -> dict[str, Dados]:
    pendentes = ChamadaAoProvedor.objects.filter(situacao=SituacaoDaChamada.PENDENTE)
    atrasadas = [
        c
        for c in pendentes
        if _atrasado(instante, c.proxima_em) or instante - c.criada_em > LIMITE_DA_CHAMADA_PENDENTE
    ]
    if not atrasadas:
        return {}
    mais_antiga = min(c.criada_em for c in atrasadas)
    return {"geral": {"quantidade": len(atrasadas), "mais_antiga": mais_antiga.isoformat()}}


# --- envios -------------------------------------------------------------------------------------


def _envios(instante: datetime) -> dict[str, Dados]:
    atrasados = Envio.objects.filter(
        situacao=SituacaoEnvio.PENDENTE, proxima_tentativa_em__lt=instante - MARGEM_DE_ATRASO
    )
    resumo = atrasados.aggregate(menor=Min("proxima_tentativa_em"))
    if resumo["menor"] is None:
        return {}
    return {"geral": {"quantidade": atrasados.count(), "mais_antigo": resumo["menor"].isoformat()}}


def _classificar(tipo: TipoDeAlerta, titulo: str, corpo: Any, link: Any) -> None:
    registrar_tipo(
        tipo.value,
        Classificacao(
            gravidade=Gravidade.AVISO,
            natureza=Natureza.CONDICAO,
            titulo=titulo,
            corpo=corpo,
            link=link,
        ),
    )


_classificar(
    TipoDeAlerta.FECHAMENTO_NAO_ENCERRADO,
    "Fechamento não encerrado",
    lambda d: (
        f"O fechamento da rodada de {d['fornecedor']} terminou em {data_e_hora(d['prazo'])} "
        "e ainda não foi encerrado."
    ),
    lambda d: reverse("rodadas_estoque", args=[d["rodada"]]),
)
_classificar(
    TipoDeAlerta.PEDIDO_FORMAL_ATRASADO,
    "Envio do pedido formal atrasado",
    lambda d: (
        f"A tentativa automática do pedido formal da rodada de {d['fornecedor']} estava prevista "
        f"para {data_e_hora(d['prevista_para'])} e não foi feita."
    ),
    lambda d: reverse("rodadas_pedido_formal", args=[d["rodada"]]),
)
_classificar(
    TipoDeAlerta.CONCILIACAO_ATRASADA,
    "Conciliação atrasada",
    lambda d: (
        f"O dia {_data(d['dia'])} terminou há mais de 24 horas e ainda não foi conciliado. "
        f"A última conciliação é de {_data(d['ultima_conciliada'])}."
    ),
    lambda d: reverse("financeiro_conciliacoes"),
)
_classificar(
    TipoDeAlerta.CHAMADAS_AO_PROVEDOR_ATRASADAS,
    "Chamadas ao provedor atrasadas",
    lambda d: (
        f"{d['quantidade']} chamada(s) ao provedor de pagamentos estão pendentes além do "
        f"previsto. A mais antiga é de {data_e_hora(d['mais_antiga'])}."
    ),
    lambda d: reverse("painel_administracao"),
)
_classificar(
    TipoDeAlerta.ENVIOS_ATRASADOS,
    "Notificações atrasadas",
    lambda d: (
        f"{d['quantidade']} notificação(ões) aguardam envio além do previsto, "
        f"desde {data_e_hora(d['mais_antigo'])}."
    ),
    lambda d: reverse("envios_lista"),
)

registrar_verificacao(TipoDeAlerta.FECHAMENTO_NAO_ENCERRADO.value, _fechamentos)
registrar_verificacao(TipoDeAlerta.PEDIDO_FORMAL_ATRASADO.value, _pedidos_formais)
registrar_verificacao(TipoDeAlerta.CONCILIACAO_ATRASADA.value, _conciliacoes)
registrar_verificacao(TipoDeAlerta.CHAMADAS_AO_PROVEDOR_ATRASADAS.value, _chamadas)
registrar_verificacao(TipoDeAlerta.ENVIOS_ATRASADOS.value, _envios)
