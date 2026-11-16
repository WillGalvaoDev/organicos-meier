"""O que as telas do administrador mostram da entrega e da retirada (E14-06): o recebimento, as
ocorrências, as retiradas e o bloco da página da rodada. Tudo vem dos registros gravados e dos
serviços das E14-01 a E14-05; nenhuma página calcula regra própria.
"""

import uuid
from decimal import Decimal
from typing import Any

from django.db.models import Sum

from apps.financeiro.models import ObrigacaoComComprador, PedidoApurado, Reembolso
from apps.financeiro.reembolsos import acumulado_do_item
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos.endereco_de_retirada import endereco_vigente
from apps.pedidos.liberacao_da_retirada import liberacao_da_rodada, motivo_da_recusa
from apps.pedidos.models import (
    DescarteDeItem,
    OcorrenciaDeEntrega,
    Pedido,
    PedidoFormal,
    RecebimentoDoFornecedor,
    RetiradaDeItem,
    TipoDeOcorrencia,
)
from apps.pedidos.ocorrencias import saldo_do_item
from apps.pedidos.recebimento import recebimento_resolvido, situacao_do_recebimento
from apps.pedidos.retirada import situacao_da_retirada
from apps.rodadas.models import Etapa, Rodada

ETAPAS_DA_ENTREGA = (Etapa.AGUARDANDO_FORNECEDOR, Etapa.DISPONIVEL_PARA_RETIRADA, Etapa.CANCELADA)
ROTULO_DA_ETAPA = {
    Etapa.AGUARDANDO_FORNECEDOR: "antes da liberação",
    Etapa.DISPONIVEL_PARA_RETIRADA: "depois da liberação",
}


def _data_hora(instante: Any) -> str:
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}"


def _base(rodada: Rodada, valores: dict[str, str] | None, erro: str) -> dict[str, Any]:
    return {
        "rodada": rodada,
        "acionamento": uuid.uuid4(),
        "valores": valores or {},
        "erro": erro,
    }


def pagina_do_recebimento(
    rodada: Rodada, *, valores: dict[str, str] | None = None, erro: str = ""
) -> dict[str, Any]:
    """A tabela do recebimento, o formulário, a liberação e o histórico."""
    contexto = _base(rodada, valores, erro)
    linhas = situacao_do_recebimento(rodada)
    contexto["linhas"] = linhas
    contexto["historico"] = [
        {
            "quando": _data_hora(r.registrado_em),
            "produto": r.linha.nome,
            "quantidade": r.quantidade,
            "unidade": r.linha.unidade,
            "autor": r.autor.nome,
        }
        for r in RecebimentoDoFornecedor.objects.filter(pedido_formal__rodada=rodada)
        .select_related("linha", "autor")
        .order_by("-pk")
    ]
    contexto["aguardando"] = rodada.etapa == Etapa.AGUARDANDO_FORNECEDOR
    contexto["cancelada"] = rodada.etapa == Etapa.CANCELADA
    liberacao = liberacao_da_rodada(rodada)
    contexto["liberada"] = (
        None
        if liberacao is None
        else {
            "em": _data_hora(liberacao.liberada_em),
            "prazo": _data_hora(liberacao.prazo_final),
            "endereco": liberacao.endereco.texto,
        }
    )
    if contexto["aguardando"]:
        recusa = motivo_da_recusa(rodada)
        contexto["pode_liberar"] = recusa is None
        contexto["motivo_da_liberacao"] = "" if recusa is None else str(recusa)
        contexto["sem_endereco"] = endereco_vigente() is None
        contexto["resolvido"] = recebimento_resolvido(rodada)
    return contexto


def _soma(registros: Any) -> Decimal:
    total: Decimal | None = registros.aggregate(total=Sum("quantidade"))["total"]
    return total or Decimal("0")


def _itens_dos_pedidos_validos(pedido_formal: PedidoFormal) -> list[dict[str, Any]]:
    validos = PedidoApurado.objects.filter(apuracao__ciclo_id=pedido_formal.ciclo_id).values(
        "pedido_id"
    )
    pedidos = []
    for pedido in Pedido.objects.filter(pk__in=validos).select_related("comprador").order_by("pk"):
        itens = []
        for item in pedido.itens.order_by("pk"):
            reembolsada, _valor = acumulado_do_item(item)
            retirada = _soma(RetiradaDeItem.objects.filter(item=item))
            descartada = _soma(DescarteDeItem.objects.filter(item=item))
            itens.append(
                {
                    "item": item,
                    "pedida": item.quantidade,
                    "reembolsada": reembolsada,
                    "retirada": retirada,
                    "descartada": descartada,
                    "saldo": saldo_do_item(item),
                }
            )
        pedidos.append({"pedido": pedido, "comprador": pedido.comprador.nome, "itens": itens})
    return pedidos


def _obrigacao_do_reembolso(reembolso: Reembolso) -> ObrigacaoComComprador | None:
    return ObrigacaoComComprador.objects.filter(
        origem_tipo=Reembolso._meta.label_lower, origem_id=str(reembolso.pk)
    ).first()


def pagina_das_ocorrencias(
    rodada: Rodada,
    pedido_formal: PedidoFormal,
    *,
    valores: dict[str, str] | None = None,
    erro: str = "",
) -> dict[str, Any]:
    """Os pedidos válidos com os saldos, o formulário (fora de `cancelada`) e a lista."""
    contexto = _base(rodada, valores, erro)
    pedidos = _itens_dos_pedidos_validos(pedido_formal)
    contexto["pedidos"] = pedidos
    contexto["somente_leitura"] = rodada.etapa == Etapa.CANCELADA
    contexto["opcoes"] = [
        {
            "pk": linha["item"].pk,
            "rotulo": f"Pedido {bloco['pedido'].pk} — {bloco['comprador']} — {linha['item'].nome}",
        }
        for bloco in pedidos
        for linha in bloco["itens"]
        if linha["saldo"] > 0
    ]
    contexto["tipos"] = TipoDeOcorrencia.choices
    lista = []
    ocorrencias = (
        OcorrenciaDeEntrega.objects.filter(item__pedido__abertura__rodada=rodada)
        .select_related("item__pedido__comprador", "reembolso", "autor")
        .order_by("-pk")
    )
    for o in ocorrencias:
        obrigacao = _obrigacao_do_reembolso(o.reembolso)
        lista.append(
            {
                "ocorrencia": o,
                "quando": _data_hora(o.registrada_em),
                "pedido": o.item.pedido_id,
                "comprador": o.item.pedido.comprador.nome,
                "produto": o.item.nome,
                "tipo": o.get_tipo_display(),
                "unidade": o.item.unidade,
                "etapa": ROTULO_DA_ETAPA.get(o.etapa, o.etapa),
                "autor": o.autor.nome,
                "reembolso": o.reembolso,
                "obrigacao": obrigacao,
            }
        )
    contexto["ocorrencias"] = lista
    return contexto


def pagina_das_retiradas(
    rodada: Rodada, *, valores: dict[str, str] | None = None, erro: str = ""
) -> dict[str, Any]:
    """O cabeçalho da liberação, os itens por pedido, os vencidos e o histórico."""
    contexto = _base(rodada, valores, erro)
    situacao = situacao_da_retirada(rodada)
    liberacao = situacao.liberacao
    contexto["liberada_em"] = _data_hora(liberacao.liberada_em)
    contexto["prazo_final"] = _data_hora(liberacao.prazo_final)
    contexto["endereco"] = liberacao.endereco.texto
    contexto["situacao"] = situacao
    historico = [
        {
            "quando": r.registrada_em,
            "texto_quando": _data_hora(r.registrada_em),
            "pedido": r.item.pedido_id,
            "comprador": r.item.pedido.comprador.nome,
            "produto": r.item.nome,
            "unidade": r.item.unidade,
            "quantidade": r.quantidade,
            "tipo": "Retirada" if isinstance(r, RetiradaDeItem) else "Descarte",
            "autor": r.autor.nome,
        }
        for modelo in (RetiradaDeItem, DescarteDeItem)
        for r in modelo.objects.filter(item__pedido__abertura__rodada=rodada).select_related(
            "item__pedido__comprador", "autor"
        )
    ]
    contexto["historico"] = sorted(historico, key=lambda h: h["quando"], reverse=True)
    return contexto


def bloco_da_entrega(rodada: Rodada) -> dict[str, Any] | None:
    """O bloco "Entrega e retirada" da página da rodada, nas etapas da entrega com pedido formal."""
    if rodada.etapa not in ETAPAS_DA_ENTREGA:
        return None
    if not PedidoFormal.objects.filter(rodada=rodada).exists():
        return None
    if rodada.etapa == Etapa.CANCELADA:
        return {"situacao": "Rodada cancelada.", "liberada": False}
    if rodada.etapa == Etapa.DISPONIVEL_PARA_RETIRADA:
        liberacao = liberacao_da_rodada(rodada)
        prazo = _data_hora(liberacao.prazo_final) if liberacao is not None else ""
        return {"situacao": f"Retirada liberada; prazo até {prazo}.", "liberada": True}
    a_resolver = sum(1 for linha in situacao_do_recebimento(rodada) if linha.a_resolver > 0)
    return {
        "situacao": f"Aguardando o fornecedor: {a_resolver} produto(s) a resolver.",
        "liberada": False,
    }
