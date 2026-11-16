"""As ocorrências de entrega com reembolso pontual (E14-02).

O administrador registra, por item do pedido, a quantidade faltante, incorreta ou não entregue. Cada
ocorrência gera o reembolso pontual do item (E10-02: serviço e frete proporcionais, obrigação com o
comprador da E09-06), sem alterar o pedido nem a etapa da rodada. A devolução é autorizada à parte,
pelo fluxo da E10.

Travas, nesta ordem: a rodada (`FOR NO KEY UPDATE`, a mesma de todas as operações da E14), a
situação do pedido (a trava dos reembolsos do pedido) e, dentro do reembolso, as contas do
livro-razão. Nenhum efeito externo acontece aqui: desfazer a transação basta.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import formatar_quantidade
from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.models import ObrigacaoComComprador, PedidoApurado, Reembolso
from apps.financeiro.reembolsos import ReembolsoRegistrado, acumulado_do_item, reembolso_parcial
from apps.financeiro.reserva import sem_cobertura_da_obrigacao
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora
from apps.nucleo.valores import ValorInvalido, cabe_em_quantidade, eh_multiplo, quantidade
from apps.pedidos.models import (
    DescarteDeItem,
    ItemDoPedido,
    LinhaDoPedidoFormal,
    OcorrenciaDeEntrega,
    PedidoFormal,
    RecebimentoDoFornecedor,
    RetiradaDeItem,
    SituacaoDoPedido,
    TipoDeOcorrencia,
)
from apps.rodadas.models import Etapa, Rodada

__all__ = [
    "OcorrenciaRecusada",
    "OcorrenciaRegistrada",
    "TipoDeOcorrencia",
    "recebido_da_linha",
    "registrar_ocorrencia",
    "saldo_do_item",
    "somas_das_ocorrencias",
]

ZERO = Decimal("0")
MOTIVO_DO_REEMBOLSO = "ocorrencia_de_entrega"
MENSAGENS = {
    "acionamento_invalido": (
        "O registro não pôde ser identificado; recarregue a página e tente de novo."
    ),
    "etapa": (
        "Ocorrências só são registradas depois da aprovação do resultado e antes do cancelamento."
    ),
    "item_fora_do_pedido_formal": "Este item não está entre os pedidos válidos da rodada.",
    "tipo_invalido": "Escolha o tipo da ocorrência.",
    "quantidade_invalida": "Informe uma quantidade maior que zero, no incremento do produto.",
    "passa_do_saldo_do_item": "A quantidade passa do saldo deste item ({saldo} {unidade}).",
    "passa_do_pedido_formal": (
        "A quantidade passa do que ainda não foi recebido deste produto ({a_resolver} {unidade})."
    ),
    "passa_do_recebido": (
        "A quantidade passa do que já foi recebido deste produto ({recebido} {unidade})."
    ),
}


class OcorrenciaRecusada(Exception):
    """A ocorrência não pode ser registrada. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str, **valores: str) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo].format(**valores))


@dataclass(frozen=True)
class OcorrenciaRegistrada:
    """O registro do acionamento. `nova` é falso quando ele já tinha gerado a ocorrência."""

    ocorrencia: OcorrenciaDeEntrega
    reembolso: ReembolsoRegistrado
    nova: bool


# --- leituras para as outras fatias ------------------------------------------------------------


def recebido_da_linha(linha: LinhaDoPedidoFormal) -> Decimal:
    """A soma dos recebimentos do produto da linha (E14-01)."""
    soma = RecebimentoDoFornecedor.objects.filter(linha=linha).aggregate(total=Sum("quantidade"))
    total: Decimal | None = soma["total"]
    return total or ZERO


def somas_das_ocorrencias(pedido_formal: PedidoFormal, produto: Produto) -> dict[str, Decimal]:
    """A soma por tipo das ocorrências registradas em `aguardando_fornecedor`, dos itens dos
    pedidos válidos do ciclo do pedido formal (E14-01)."""
    validos = PedidoApurado.objects.filter(apuracao__ciclo_id=pedido_formal.ciclo_id).values(
        "pedido_id"
    )
    linhas = (
        OcorrenciaDeEntrega.objects.filter(
            etapa=Etapa.AGUARDANDO_FORNECEDOR, item__produto=produto, item__pedido_id__in=validos
        )
        .values("tipo")
        .annotate(total=Sum("quantidade"))
    )
    somas = {tipo: ZERO for tipo in TipoDeOcorrencia.values}
    for linha in linhas:
        somas[linha["tipo"]] = linha["total"]
    return somas


def saldo_do_item(item: ItemDoPedido) -> Decimal:
    """O que o comprador ainda tem para receber ou retirar: a quantidade do item menos tudo o que
    foi reembolsado (qualquer motivo), retirado e descartado (E14-05). Sem trava, para as
    telas."""
    reembolsada, _valor = acumulado_do_item(item)
    retirada = RetiradaDeItem.objects.filter(item=item).aggregate(total=Sum("quantidade"))
    descartada = DescarteDeItem.objects.filter(item=item).aggregate(total=Sum("quantidade"))
    saldo: Decimal = (
        item.quantidade - reembolsada - (retirada["total"] or ZERO) - (descartada["total"] or ZERO)
    )
    return saldo


# --- o registro --------------------------------------------------------------------------------


def _exigir_administrador(autor: Conta | None) -> Conta:
    if autor is None or autor.papel != Papel.ADMINISTRADOR or autor.situacao != Situacao.ATIVA:
        raise PermissionDenied
    return autor


def _como_uuid(acionamento: object) -> uuid.UUID:
    if isinstance(acionamento, uuid.UUID):
        return acionamento
    if isinstance(acionamento, str) and acionamento:
        try:
            return uuid.UUID(acionamento)
        except ValueError:
            pass
    raise OcorrenciaRecusada("acionamento_invalido")


def _registrada(ocorrencia: OcorrenciaDeEntrega) -> OcorrenciaRegistrada:
    reembolso = ocorrencia.reembolso
    obrigacao = ObrigacaoComComprador.objects.filter(
        origem_tipo=Reembolso._meta.label_lower, origem_id=str(reembolso.pk)
    ).first()
    sem_cobertura = sem_cobertura_da_obrigacao(obrigacao) if obrigacao is not None else ZERO
    return OcorrenciaRegistrada(
        ocorrencia, ReembolsoRegistrado(reembolso, obrigacao, sem_cobertura), False
    )


def _repeticao(
    chave: uuid.UUID, item: ItemDoPedido, quantidade_pedida: object, tipo: object
) -> OcorrenciaRegistrada | None:
    """A ocorrência que o acionamento já gerou; com outro conteúdo, `acionamento_invalido`."""
    existente: OcorrenciaDeEntrega | None = (
        OcorrenciaDeEntrega.objects.select_related("reembolso").filter(acionamento=chave).first()
    )
    if existente is None:
        return None
    igual = (
        existente.item_id == item.pk
        and existente.tipo == tipo
        and isinstance(quantidade_pedida, Decimal)
        and existente.quantidade == quantidade_pedida
    )
    if not igual:
        raise OcorrenciaRecusada("acionamento_invalido")
    return _registrada(existente)


def _quantidade_valida(valor: object, incremento: Decimal) -> bool:
    if not isinstance(valor, Decimal) or not valor.is_finite() or valor <= 0:
        return False
    try:
        return (
            quantidade(valor) == valor
            and cabe_em_quantidade(valor)
            and eh_multiplo(valor, incremento)
        )
    except ValorInvalido:
        return False


def registrar_ocorrencia(
    autor: Conta | None,
    item: ItemDoPedido,
    quantidade_afetada: object,
    tipo: object,
    *,
    acionamento: object,
) -> OcorrenciaRegistrada:
    """Registra a ocorrência e o reembolso pontual dela. Só o administrador ativo
    (`PermissionDenied`). O acionamento é um UUID por envio do formulário: a repetição devolve a
    mesma ocorrência."""
    administrador = _exigir_administrador(autor)
    chave = _como_uuid(acionamento)
    existente = _repeticao(chave, item, quantidade_afetada, tipo)
    if existente is not None:
        return existente
    try:
        with transaction.atomic():
            return _registrar(administrador, item, quantidade_afetada, tipo, chave)
    except IntegrityError:
        existente = _repeticao(chave, item, quantidade_afetada, tipo)
        if existente is None:
            raise
        return existente


def _conferir_o_pedido_formal(
    etapa: str,
    item: ItemDoPedido,
    pedido_formal: PedidoFormal,
    tipo: str,
    quantidade_afetada: Decimal,
) -> None:
    """Só antes da liberação: o recebimento é conferido pelo produto da linha (E14-01)."""
    if etapa != Etapa.AGUARDANDO_FORNECEDOR:
        return
    linha = LinhaDoPedidoFormal.objects.filter(
        pedido_formal=pedido_formal, produto_id=item.produto_id
    ).first()
    if linha is None:
        raise OcorrenciaRecusada("passa_do_pedido_formal", a_resolver="0", unidade=item.unidade)
    somas = somas_das_ocorrencias(pedido_formal, linha.produto)
    recebido = recebido_da_linha(linha)
    if tipo == TipoDeOcorrencia.INCORRETO:
        if somas[tipo] + quantidade_afetada > recebido:
            raise OcorrenciaRecusada(
                "passa_do_recebido", recebido=formatar_quantidade(recebido), unidade=linha.unidade
            )
        return
    a_resolver = linha.quantidade - recebido - somas["faltante"] - somas["nao_entregue"]
    if quantidade_afetada > a_resolver:
        raise OcorrenciaRecusada(
            "passa_do_pedido_formal",
            a_resolver=formatar_quantidade(a_resolver),
            unidade=linha.unidade,
        )


def _registrar(
    administrador: Conta,
    item: ItemDoPedido,
    quantidade_afetada: object,
    tipo: object,
    chave: uuid.UUID,
) -> OcorrenciaRegistrada:
    atual = ItemDoPedido.objects.select_related("pedido__abertura").get(pk=item.pk)
    pedido = atual.pedido
    travada = Rodada.objects.select_for_update(no_key=True).get(pk=pedido.abertura.rodada_id)
    SituacaoDoPedido.objects.select_for_update().get(pedido=pedido)
    existente = _repeticao(chave, atual, quantidade_afetada, tipo)
    if existente is not None:
        return existente
    if travada.etapa not in (Etapa.AGUARDANDO_FORNECEDOR, Etapa.DISPONIVEL_PARA_RETIRADA):
        raise OcorrenciaRecusada("etapa")
    pedido_formal = PedidoFormal.objects.filter(ciclo_id=pedido.abertura.ciclo_id).first()
    valido = (
        pedido_formal is not None
        and PedidoApurado.objects.filter(
            apuracao__ciclo_id=pedido.abertura.ciclo_id, pedido=pedido
        ).exists()
    )
    if not valido or pedido_formal is None:
        raise OcorrenciaRecusada("item_fora_do_pedido_formal")
    if not isinstance(tipo, str) or tipo not in TipoDeOcorrencia.values:
        raise OcorrenciaRecusada("tipo_invalido")
    if not isinstance(quantidade_afetada, Decimal) or not _quantidade_valida(
        quantidade_afetada, atual.incremento
    ):
        raise OcorrenciaRecusada("quantidade_invalida")
    saldo = saldo_do_item(atual)
    if quantidade_afetada > saldo:
        raise OcorrenciaRecusada(
            "passa_do_saldo_do_item", saldo=formatar_quantidade(saldo), unidade=atual.unidade
        )
    _conferir_o_pedido_formal(travada.etapa, atual, pedido_formal, tipo, quantidade_afetada)
    reembolso = reembolso_parcial(
        atual,
        quantidade_afetada,
        chave=f"ocorrencia:{chave}",
        motivo=MOTIVO_DO_REEMBOLSO,
        autor=administrador,
    )
    ocorrencia = OcorrenciaDeEntrega.objects.create(
        item=atual,
        tipo=tipo,
        quantidade=quantidade_afetada,
        etapa=travada.etapa,
        reembolso=reembolso.reembolso,
        autor=administrador,
        registrada_em=agora(),
        acionamento=chave,
    )
    obrigacao = reembolso.obrigacao
    registrar_auditoria(
        administrador,
        "ocorrencia.registrar",
        ocorrencia,
        {
            "pedido": pedido.pk,
            "item": atual.pk,
            "tipo": tipo,
            "quantidade": quantidade_afetada,
            "etapa": travada.etapa,
            "reembolso": {
                "produtos": reembolso.reembolso.produtos,
                "servico": reembolso.reembolso.servico,
                "frete": reembolso.reembolso.frete,
            },
            "obrigacao": obrigacao.pk if obrigacao is not None else None,
            "acionamento": str(chave),
        },
    )
    return OcorrenciaRegistrada(ocorrencia, reembolso, True)
