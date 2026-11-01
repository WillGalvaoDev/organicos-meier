"""O que as telas mostram da apuração final (E11-07): o bloco do administrador e os textos que
o comprador vê no pedido. Só leitura: nada aqui grava."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.catalogo.quantidades import quantidade_com_unidade
from apps.financeiro.apuracao import frete_do_ciclo
from apps.financeiro.devolucoes import situacao_da_devolucao
from apps.financeiro.devolucoes_views import GRUPO_DA_SITUACAO, ROTULO_DO_GRUPO_NO_SINGULAR
from apps.financeiro.models import ObrigacaoComComprador, Reembolso
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos.acompanhamento import CANCELAMENTOS_POR_EXTENSO
from apps.pedidos.models import (
    AberturaDoPagamento,
    ApuracaoFinal,
    CaixaInvalidada,
    MotivoDoCancelamento,
    ParcelaNoPedido,
    Pedido,
    RestauracaoDeCaixa,
    ResultadoDaApuracao,
    SituacaoDePagamento,
)
from apps.pedidos.prazos import fim_da_margem, pode_iniciar_apuracao
from apps.rodadas.models import Etapa, Rodada

MOTIVO_DO_ESTORNO = {
    "caixa_invalidada": "caixa invalidada",
    "minimo_nao_atingido": "mínimo não atingido",
}


def _data_e_hora(instante: datetime) -> str:
    local = no_fuso_da_operacao(instante)
    return f"{local:%d/%m/%Y} às {local:%H:%M}"


def _estornos(abertura: AberturaDoPagamento) -> list[dict[str, Any]]:
    """Um por reembolso gerado pela apuração, com a situação da devolução na lista da E10-07."""
    reembolsos = (
        Reembolso.objects.filter(pedido__abertura=abertura, motivo__in=list(MOTIVO_DO_ESTORNO))
        .select_related("pedido__comprador")
        .order_by("pk")
    )
    linhas = []
    for reembolso in reembolsos:
        obrigacao = ObrigacaoComComprador.objects.filter(
            origem_tipo=Reembolso._meta.label_lower, origem_id=str(reembolso.pk)
        ).first()
        situacao = (
            ROTULO_DO_GRUPO_NO_SINGULAR[GRUPO_DA_SITUACAO[situacao_da_devolucao(obrigacao)]]
            if obrigacao is not None
            else None
        )
        linhas.append(
            {
                "comprador": reembolso.pedido.comprador.nome,
                "motivo": MOTIVO_DO_ESTORNO[reembolso.motivo],
                "valor": reembolso.produtos + reembolso.servico + reembolso.frete,
                "situacao": situacao,
                "obrigacao": obrigacao.pk if obrigacao is not None else None,
            }
        )
    return linhas


def _resultado(apuracao: ApuracaoFinal, rodada: Rodada) -> dict[str, Any]:
    abertura = apuracao.abertura
    pedidos = abertura.pedidos.select_related("comprador", "estado").order_by(
        "comprador__nome", "pk"
    )
    pagos = []
    nao_pagos = []
    for pedido in pedidos:
        estado = pedido.estado
        if estado.situacao == SituacaoDePagamento.PAGO:
            pagos.append({"comprador": pedido.comprador.nome, "total": pedido.total})
        else:
            motivo = MotivoDoCancelamento(estado.motivo_do_cancelamento)
            nao_pagos.append(
                {
                    "comprador": pedido.comprador.nome,
                    "situacao": CANCELAMENTOS_POR_EXTENSO[motivo],
                }
            )
    caixas = [
        {"produto": c.produto.nome, "numero": c.numero}
        for c in CaixaInvalidada.objects.filter(apuracao=apuracao)
        .select_related("produto")
        .order_by("produto__nome", "numero")
    ]
    valida = apuracao.resultado == ResultadoDaApuracao.VALIDA
    aprovacao = getattr(apuracao, "aprovacao", None)
    bloco: dict[str, Any] = {
        "tipo": "resultado",
        "feita_em": _data_e_hora(apuracao.iniciada_em),
        "por": apuracao.autor.nome,
        "pagos": pagos,
        "nao_pagos": nao_pagos,
        "caixas": caixas,
        "valor_valido": apuracao.valor_valido,
        "minimo": apuracao.minimo,
        "atendido": valida,
        "estornos": _estornos(abertura),
        "pode_aprovar": valida and aprovacao is None and rodada.etapa == Etapa.PAGAMENTO,
        "aprovada": None,
    }
    if aprovacao is not None:
        frete = frete_do_ciclo(abertura.ciclo)
        bloco["aprovada"] = {
            "em": _data_e_hora(aprovacao.aprovada_em),
            "por": aprovacao.autor.nome,
            "frete_efetivo": frete.efetivo,
            "frete_arrecadado": frete.arrecadado,
            "deficit": frete.deficit,
        }
    return bloco


def bloco_da_apuracao(rodada: Rodada, instante: datetime) -> dict[str, Any] | None:
    """O bloco "Apuração final" da página da rodada. Mostra a apuração do último ciclo da rodada
    com abertura de pagamento (a rodada de volta em interesse a mantém até um novo pagamento);
    sem apuração, em `pagamento`, informa quando ela pode começar ou oferece o botão."""
    abertura = AberturaDoPagamento.objects.filter(rodada=rodada).order_by("-ciclo__numero").first()
    if abertura is None:
        return None
    apuracao = ApuracaoFinal.objects.filter(abertura=abertura).select_related("autor").first()
    if apuracao is not None:
        return _resultado(apuracao, rodada)
    if rodada.etapa != Etapa.PAGAMENTO:
        return None
    if pode_iniciar_apuracao(abertura, instante):
        return {"tipo": "iniciar"}
    return {"tipo": "aguardar", "a_partir_de": _data_e_hora(fim_da_margem(abertura))}


def _apuracao_do_pedido(pedido: Pedido) -> ApuracaoFinal | None:
    apuracao: ApuracaoFinal | None = ApuracaoFinal.objects.filter(
        abertura_id=pedido.abertura_id
    ).first()
    return apuracao


def _conta_impedida_no_retorno(apuracao: ApuracaoFinal, pedido: Pedido) -> bool:
    """O comprador teve as parcelas removidas no retorno por conta impedida? A fonte é o registro
    da apuração (a auditoria), e não a situação atual da conta (E11-R02)."""
    auditoria = EntradaAuditoria.objects.filter(
        acao="rodada.apuracao_final",
        objeto_tipo="rodadas.rodada",
        objeto_id=str(apuracao.abertura.rodada_id),
        alteracoes__ciclo=apuracao.ciclo_id,
    ).first()
    if auditoria is None:
        return False
    removidas = auditoria.alteracoes.get("retorno", {}).get("removidas_por_conta_impedida", [])
    return any(r["comprador"] == pedido.comprador_id for r in removidas)


def efeitos_da_apuracao_no_pedido(pedido: Pedido) -> dict[str, Any]:
    """O que o comprador vê do efeito da apuração no próprio pedido: o cancelamento por falta de
    pagamento, as unidades em caixa invalidada (com o estorno e a fila) e o retorno para interesse
    da rodada. Nunca traz dado de outro comprador, a caixa inteira nem o mínimo."""
    efeitos: dict[str, Any] = {
        "cancelado_por_inadimplencia": pedido.estado.motivo_do_cancelamento
        == MotivoDoCancelamento.INADIMPLENCIA,
        "caixas_incompletas": [],
        "rodada_voltou_para_interesse": False,
        "interesses_reservados": False,
    }
    apuracao = _apuracao_do_pedido(pedido)
    if apuracao is None or pedido.estado.situacao != SituacaoDePagamento.PAGO:
        return efeitos
    if apuracao.resultado == ResultadoDaApuracao.RETORNO_PARA_INTERESSE:
        efeitos["rodada_voltou_para_interesse"] = True
        efeitos["interesses_reservados"] = not _conta_impedida_no_retorno(apuracao, pedido)
        return efeitos
    invalidadas = set(
        CaixaInvalidada.objects.filter(apuracao=apuracao).values_list("produto_id", "numero")
    )
    for item in pedido.itens.order_by("produto_id"):
        unidades = sum(
            (
                p.quantidade
                for p in ParcelaNoPedido.objects.filter(item=item)
                if (item.produto_id, p.caixa) in invalidadas
            ),
            Decimal("0.000"),
        )
        if unidades > 0:
            efeitos["caixas_incompletas"].append(
                {
                    "nome": item.nome,
                    "quantidade": quantidade_com_unidade(unidades, item.unidade),
                    # a fila só é prometida se a apuração restaurou a parcela (E11-R01/R02)
                    "na_fila": RestauracaoDeCaixa.objects.filter(
                        apuracao=apuracao, parcela_no_pedido__item=item
                    ).exists(),
                }
            )
    return efeitos
