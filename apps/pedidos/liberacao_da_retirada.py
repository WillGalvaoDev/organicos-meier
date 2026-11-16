"""A liberação da retirada e o encerramento da rodada (E14-04).

Resolvido o recebimento (tudo recebido ou coberto por ocorrência `faltante`/`nao_entregue`), o
administrador libera a retirada: a rodada passa a `disponivel_para_retirada` (fora das etapas
ativas, então o fornecedor pode abrir outra), as reservas `em_pedido` deixam de consumir o estoque
da rodada seguinte, e cada comprador com saldo a retirar é avisado, com o endereço e o prazo de
sete dias. Nada aqui move dinheiro nem muda pedido, item, pagamento ou pedido formal.

As travas são as da apuração e do cancelamento (`_travar` da E11-01), na mesma ordem: a trava da
rodada vem antes de qualquer trava de situação ou de conta do livro, então a liberação se
serializa com o recebimento, as ocorrências, o cancelamento e as operações de interesse.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.catalogo.quantidades import formatar_quantidade
from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.models import PedidoApurado
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao
from apps.pedidos.apuracao import _travar
from apps.pedidos.cancelamento_da_rodada import _compradores_envolvidos
from apps.pedidos.endereco_de_retirada import endereco_vigente
from apps.pedidos.models import EnderecoDeRetirada, LiberacaoDaRetirada, Pedido, PedidoFormal
from apps.pedidos.ocorrencias import saldo_do_item
from apps.pedidos.recebimento import situacao_do_recebimento
from apps.rodadas.models import Etapa, Rodada

__all__ = [
    "LiberacaoRecusada",
    "liberacao_da_rodada",
    "liberar_retirada",
    "motivo_da_recusa",
]

PRAZO_DE_RETIRADA = timedelta(days=7)
ZERO = Decimal("0.000")
MENSAGENS = {
    "ja_liberada": "A retirada desta rodada já foi liberada.",
    "etapa": "A retirada só é liberada quando a rodada aguarda o fornecedor.",
    "sem_endereco": "Registre o endereço de retirada antes de liberar.",
    "recebimento_pendente": "Ainda falta resolver: {pendencias}.",
}


class LiberacaoRecusada(Exception):
    """A liberação não pode ser feita. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str, **valores: str) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo].format(**valores))


def liberacao_da_rodada(rodada: Rodada) -> LiberacaoDaRetirada | None:
    """A liberação da rodada, ou `None` se a retirada ainda não foi liberada."""
    return LiberacaoDaRetirada.objects.filter(rodada=rodada).select_related("endereco").first()


def _conferir_a_etapa(etapa: str) -> None:
    if etapa == Etapa.DISPONIVEL_PARA_RETIRADA:
        raise LiberacaoRecusada("ja_liberada")
    if etapa != Etapa.AGUARDANDO_FORNECEDOR:
        raise LiberacaoRecusada("etapa")


def _conferir_as_condicoes(rodada: Rodada) -> EnderecoDeRetirada:
    """As conferências da regra 4, na ordem: a primeira que falha vale. Devolve o endereço
    vigente, lido sob as travas."""
    _conferir_a_etapa(rodada.etapa)
    endereco = endereco_vigente()
    if endereco is None:
        raise LiberacaoRecusada("sem_endereco")
    pendentes = [
        f"{linha.nome} ({formatar_quantidade(linha.a_resolver)} {linha.unidade})"
        for linha in situacao_do_recebimento(rodada)
        if linha.a_resolver > 0
    ]
    if pendentes:
        raise LiberacaoRecusada("recebimento_pendente", pendencias="; ".join(pendentes))
    return endereco


def motivo_da_recusa(rodada: Rodada) -> LiberacaoRecusada | None:
    """Por que a liberação seria recusada agora, sem trava, para as telas; `None` se pode."""
    try:
        _conferir_as_condicoes(rodada)
    except LiberacaoRecusada as recusa:
        return recusa
    return None


def _liberar_as_reservas(fornecedor_id: int) -> list[dict[str, Any]]:
    """Cada parcela `em_pedido` perde a reserva: com parte pendente vira `pendente` (a fila do
    fornecedor, §5.2), sem ela vira `removida` (a mesma transição do cancelamento, E12-01 regra
    6). As parcelas `ativa` e `pendente` não mudam; nenhuma é criada e nenhuma sequência muda.
    Com as parcelas já travadas por `_travar`."""
    alteradas: list[dict[str, Any]] = []
    parcelas = (
        ParcelaDeInteresse.objects.filter(
            produto__fornecedor_id=fornecedor_id, situacao=SituacaoParcela.EM_PEDIDO
        )
        .order_by("produto_id", "sequencia")
        .select_related("produto")
    )
    for parcela in parcelas:
        nova = (
            SituacaoParcela.PENDENTE
            if parcela.quantidade_pendente > 0
            else SituacaoParcela.REMOVIDA
        )
        alteradas.append(
            {
                "parcela": parcela.pk,
                "comprador": parcela.comprador_id,
                "situacao_anterior": str(parcela.situacao),
                "situacao_nova": str(nova),
                "reservada_anterior": str(parcela.quantidade_reservada),
                "pendente_mantida": str(parcela.quantidade_pendente),
            }
        )
        parcela.quantidade_reservada = ZERO
        parcela.situacao = nova
        parcela.save(update_fields=["quantidade_reservada", "situacao"])
    return alteradas


def _data_hora(instante: datetime) -> tuple[str, str]:
    local = no_fuso_da_operacao(instante)
    return f"{local:%d/%m/%Y}", f"{local:%H:%M}"


def _avisar_os_compradores(liberacao: LiberacaoDaRetirada, pedido_formal: PedidoFormal) -> int:
    """Um aviso por pedido válido do ciclo com algum item de saldo maior que zero. O comprador
    suspenso recebe; o removido não (acesso bloqueado, §2)."""
    nome = pedido_formal.fornecedor.nome
    data, hora = _data_hora(liberacao.prazo_final)
    endereco = liberacao.endereco.texto.replace("\n", ", ")
    validos = PedidoApurado.objects.filter(apuracao__ciclo_id=pedido_formal.ciclo_id).values(
        "pedido_id"
    )
    avisados = 0
    pedidos = Pedido.objects.filter(pk__in=validos).select_related("comprador").order_by("pk")
    for pedido in pedidos:
        if pedido.comprador.situacao == Situacao.REMOVIDA:
            continue
        if not any(saldo_do_item(item) > 0 for item in pedido.itens.all()):
            continue
        emitir_evento(
            Evento.RETIRADA_LIBERADA,
            pedido.comprador,
            titulo=f"Retirada liberada: {nome}"[:150],
            corpo=(
                f"Os produtos do seu pedido {pedido.pk} da rodada de {nome} estão disponíveis "
                f"para retirada em {endereco}. Retire até {data} às {hora} (horário de "
                "Brasília). Restrições de dia ou horário são publicadas nos comunicados."
            ),
            link=f"/pedidos/{pedido.pk}/",
            chave=f"{Evento.RETIRADA_LIBERADA.value}:{liberacao.pk}:{pedido.comprador_id}",
        )
        avisados += 1
    return avisados


def liberar_retirada(autor: Conta | None, rodada: Rodada) -> LiberacaoDaRetirada:
    """Libera a retirada da rodada que aguarda o fornecedor. Só o administrador ativo
    (`PermissionDenied`).

    A conferência prévia, sem trava, só olha a etapa: o recebimento, o endereço e as ocorrências
    podem mudar por operações concorrentes que esperam a trava da rodada, e só as conferências
    sob as travas valem (E14-04, A-22)."""
    if autor is None or autor.papel != Papel.ADMINISTRADOR or autor.situacao != Situacao.ATIVA:
        raise PermissionDenied
    atual = Rodada.objects.get(pk=rodada.pk)
    _conferir_a_etapa(atual.etapa)
    with transaction.atomic():
        travada = _travar(atual.pk, atual.fornecedor_id, _compradores_envolvidos(atual))
        instante = agora()  # lido depois das travas
        endereco = _conferir_as_condicoes(travada)
        pedido_formal = PedidoFormal.objects.select_related("fornecedor").get(rodada=travada)
        travada.etapa = Etapa.DISPONIVEL_PARA_RETIRADA
        travada.save(update_fields=["etapa"])
        liberacao = LiberacaoDaRetirada.objects.create(
            rodada=travada,
            ciclo=pedido_formal.ciclo,
            pedido_formal=pedido_formal,
            liberada_em=instante,
            prazo_final=instante + PRAZO_DE_RETIRADA,
            endereco=endereco,
            autor=autor,
        )
        parcelas = _liberar_as_reservas(travada.fornecedor_id)
        avisados = _avisar_os_compradores(liberacao, pedido_formal)
        registrar_auditoria(
            autor,
            "rodada.liberar_retirada",
            travada,
            {
                "rodada": travada.pk,
                "liberacao": liberacao.pk,
                "liberada_em": liberacao.liberada_em,
                "prazo_final": liberacao.prazo_final,
                "endereco": liberacao.endereco.texto,
                "parcelas": parcelas,
                "compradores_avisados": avisados,
            },
        )
    return liberacao
