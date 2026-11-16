"""O recebimento dos produtos do fornecedor (E14-01).

O administrador registra, por produto do pedido formal, as quantidades que chegaram, em uma ou mais
entregas. O registro é só de inserção e não muda o pedido formal. Todas as operações da E14 sobre a
mesma rodada se serializam pela trava da rodada (`FOR NO KEY UPDATE`), tomada antes de qualquer
outra, e não há efeito externo: desfazer a transação basta.
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
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora
from apps.nucleo.valores import ValorInvalido, cabe_em_quantidade, eh_multiplo, quantidade
from apps.pedidos.models import LinhaDoPedidoFormal, PedidoFormal, RecebimentoDoFornecedor
from apps.pedidos.ocorrencias import somas_das_ocorrencias
from apps.rodadas.models import CondicaoDoProdutoNoCiclo, Etapa, Rodada

ZERO = Decimal("0")
MENSAGENS = {
    "acionamento_invalido": (
        "O registro não pôde ser identificado; recarregue a página e tente de novo."
    ),
    "etapa": "O recebimento só é registrado enquanto a rodada aguarda o fornecedor.",
    "produto_fora_do_pedido_formal": "Este produto não está no pedido formal da rodada.",
    "quantidade_invalida": "Informe uma quantidade maior que zero, no incremento do produto.",
    "passa_do_pedido_formal": (
        "A quantidade passa do que falta receber deste produto ({a_receber} {unidade})."
    ),
}


class RecebimentoRecusado(Exception):
    """O recebimento não pode ser registrado. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str, **valores: str) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo].format(**valores))


@dataclass(frozen=True)
class RecebimentoRegistrado:
    """O registro do acionamento. `novo` é falso quando o acionamento já tinha gerado o registro."""

    recebimento: RecebimentoDoFornecedor
    novo: bool


@dataclass(frozen=True)
class LinhaDoRecebimento:
    """A situação de uma linha do pedido formal: o que foi pedido, recebido e o que falta."""

    produto: int
    nome: str
    unidade: str
    pedida: Decimal
    recebida: Decimal
    faltante: Decimal
    nao_entregue: Decimal
    incorreta: Decimal
    a_resolver: Decimal


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
    raise RecebimentoRecusado("acionamento_invalido")


def _repeticao(
    chave: uuid.UUID, rodada: Rodada, produto: Produto, quantidade_pedida: object
) -> RecebimentoDoFornecedor | None:
    """O registro que o acionamento já gerou; com outro conteúdo, `acionamento_invalido`."""
    existente: RecebimentoDoFornecedor | None = (
        RecebimentoDoFornecedor.objects.select_related("linha", "pedido_formal")
        .filter(acionamento=chave)
        .first()
    )
    if existente is None:
        return None
    igual = (
        existente.pedido_formal.rodada_id == rodada.pk
        and existente.linha.produto_id == produto.pk
        and isinstance(quantidade_pedida, Decimal)
        and existente.quantidade == quantidade_pedida
    )
    if not igual:
        raise RecebimentoRecusado("acionamento_invalido")
    return existente


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


def _recebido(linha: LinhaDoPedidoFormal) -> Decimal:
    soma = RecebimentoDoFornecedor.objects.filter(linha=linha).aggregate(total=Sum("quantidade"))
    total: Decimal | None = soma["total"]
    return total or ZERO


def _a_resolver(linha: LinhaDoPedidoFormal, pedido_formal: PedidoFormal) -> Decimal:
    somas = somas_das_ocorrencias(pedido_formal, linha.produto)
    return linha.quantidade - _recebido(linha) - somas["faltante"] - somas["nao_entregue"]


def registrar_recebimento(
    autor: Conta | None,
    rodada: Rodada,
    produto: Produto,
    quantidade_recebida: object,
    *,
    acionamento: object,
) -> RecebimentoRegistrado:
    """Registra uma entrega do produto. Só o administrador ativo (`PermissionDenied`). O
    acionamento é um UUID por envio do formulário: a repetição devolve o mesmo registro."""
    administrador = _exigir_administrador(autor)
    chave = _como_uuid(acionamento)
    existente = _repeticao(chave, rodada, produto, quantidade_recebida)
    if existente is not None:
        return RecebimentoRegistrado(existente, novo=False)
    try:
        with transaction.atomic():
            return _registrar(administrador, rodada, produto, quantidade_recebida, chave)
    except IntegrityError:
        existente = _repeticao(chave, rodada, produto, quantidade_recebida)
        if existente is None:
            raise
        return RecebimentoRegistrado(existente, novo=False)


def _registrar(
    administrador: Conta,
    rodada: Rodada,
    produto: Produto,
    quantidade_recebida: object,
    chave: uuid.UUID,
) -> RecebimentoRegistrado:
    travada = Rodada.objects.select_for_update(no_key=True).get(pk=rodada.pk)
    existente = _repeticao(chave, travada, produto, quantidade_recebida)
    if existente is not None:
        return RecebimentoRegistrado(existente, novo=False)
    if travada.etapa != Etapa.AGUARDANDO_FORNECEDOR:
        raise RecebimentoRecusado("etapa")
    pedido_formal = PedidoFormal.objects.filter(rodada=travada).first()
    linha = (
        LinhaDoPedidoFormal.objects.filter(pedido_formal=pedido_formal, produto=produto).first()
        if pedido_formal is not None
        else None
    )
    if pedido_formal is None or linha is None:
        raise RecebimentoRecusado("produto_fora_do_pedido_formal")
    incremento = CondicaoDoProdutoNoCiclo.objects.get(
        ciclo=pedido_formal.ciclo, produto=produto
    ).incremento
    if not isinstance(quantidade_recebida, Decimal) or not _quantidade_valida(
        quantidade_recebida, incremento
    ):
        raise RecebimentoRecusado("quantidade_invalida")
    a_receber = _a_resolver(linha, pedido_formal)
    if quantidade_recebida > a_receber:
        raise RecebimentoRecusado(
            "passa_do_pedido_formal",
            a_receber=formatar_quantidade(a_receber),
            unidade=linha.unidade,
        )
    recebimento = RecebimentoDoFornecedor.objects.create(
        pedido_formal=pedido_formal,
        linha=linha,
        quantidade=quantidade_recebida,
        autor=administrador,
        registrado_em=agora(),
        acionamento=chave,
    )
    registrar_auditoria(
        administrador,
        "recebimento.registrar",
        recebimento,
        {
            "rodada": travada.pk,
            "produto": produto.pk,
            "quantidade": quantidade_recebida,
            "recebido": _recebido(linha),
            "acionamento": str(chave),
        },
    )
    return RecebimentoRegistrado(recebimento, novo=True)


def situacao_do_recebimento(rodada: Rodada) -> list[LinhaDoRecebimento]:
    """Uma linha por linha do pedido formal, na ordem delas, sem trava."""
    pedido_formal = PedidoFormal.objects.filter(rodada=rodada).first()
    if pedido_formal is None:
        return []
    resultado = []
    for linha in pedido_formal.linhas.select_related("produto").order_by("pk"):
        somas = somas_das_ocorrencias(pedido_formal, linha.produto)
        recebida = _recebido(linha)
        resultado.append(
            LinhaDoRecebimento(
                produto=linha.produto_id,
                nome=linha.nome,
                unidade=linha.unidade,
                pedida=linha.quantidade,
                recebida=recebida,
                faltante=somas["faltante"],
                nao_entregue=somas["nao_entregue"],
                incorreta=somas["incorreto"],
                a_resolver=linha.quantidade - recebida - somas["faltante"] - somas["nao_entregue"],
            )
        )
    return resultado


def recebimento_resolvido(rodada: Rodada) -> bool:
    """Toda linha do pedido formal com nada a resolver: a condição da liberação (E14-04)."""
    linhas = situacao_do_recebimento(rodada)
    return bool(linhas) and all(linha.a_resolver == ZERO for linha in linhas)
