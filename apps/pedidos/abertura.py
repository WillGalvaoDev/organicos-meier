"""Abertura do pagamento e congelamento dos pedidos (E08-02).

O administrador informa o frete e o servidor, numa só transação: registra `T0`, refaz com as
travas os dois passos do encerramento do fechamento (a divisão por sequência e a verificação do
mínimo), congela um pedido por comprador e avisa os compradores. Sem o mínimo, a rodada volta
para interesse e nenhum pedido é criado.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.catalogo.models import Produto
from apps.catalogo.templatetags.catalogo import reais
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.progresso import progresso_da_rodada
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao, somar_horas
from apps.nucleo.valores import ValorInvalido, cabe_em_dinheiro, dinheiro
from apps.pedidos.calculo import CompradorACobrar, ItemACobrar, calcular_cobranca
from apps.pedidos.models import (
    AberturaDoPagamento,
    ItemDoPedido,
    ParcelaNoPedido,
    Pedido,
    SituacaoDePagamento,
    SituacaoDoPedido,
)
from apps.rodadas.avisos import (
    MOMENTO_ABERTURA_DO_PAGAMENTO,
    avisar_excedentes_removidos,
    compradores_com_reserva,
)
from apps.rodadas.ciclos import ciclo_vigente
from apps.rodadas.fechamento import (
    TransicaoRecusada,
    _divisao_dos_excedentes,
    _por_comprador_e_produto,
    voltar_para_interesse,
)
from apps.rodadas.models import Ciclo, Etapa, Rodada

logger = logging.getLogger(__name__)

HORAS_DO_PRAZO_DE_PAGAMENTO = 24
MAIOR_TITULO = 150
ACAO = "rodada.abrir_pagamento"
MOTIVO_DO_RETORNO = "minimo_nao_atingido_na_abertura"

_ZERO = Decimal("0.000")


@dataclass(frozen=True)
class ResultadoDaAbertura:
    abertura: AberturaDoPagamento | None
    etapa_final: str


def _validar_frete(frete: Any) -> Decimal:
    if isinstance(frete, bool) or not isinstance(frete, Decimal):
        raise ValueError("o frete deve ser Decimal")
    try:
        valor = dinheiro(frete)
    except ValorInvalido as erro:
        raise ValueError(f"frete inválido: {erro}") from None
    if valor < 0:
        raise ValueError("o frete não pode ser negativo")
    if not cabe_em_dinheiro(valor):
        raise ValueError("o frete passa da capacidade do campo")
    return valor


@dataclass(frozen=True)
class _Linha:
    parcela: ParcelaDeInteresse
    caixa: int | None
    quantidade: Decimal


def _linhas_do_produto(produto: Produto, parcelas: list[ParcelaDeInteresse]) -> list[_Linha]:
    """Numera as caixas pela ordem de `sequencia`: a primeira recebe as primeiras `m` unidades,
    a segunda as seguintes, e uma parcela que cruza o limite gera duas linhas (§6.3)."""
    linhas: list[_Linha] = []
    acumulado = _ZERO
    for parcela in parcelas:
        restante = parcela.quantidade_reservada
        if produto.multiplo is None:
            linhas.append(_Linha(parcela, None, restante))
            continue
        while restante > 0:
            caixa = int(acumulado // produto.multiplo) + 1
            parte = min(restante, caixa * produto.multiplo - acumulado)
            linhas.append(_Linha(parcela, caixa, parte))
            acumulado += parte
            restante -= parte
    return linhas


def _congelar(
    rodada: Rodada,
    ciclo: Ciclo,
    autor: Conta,
    t0: datetime,
    frete: Decimal,
    ativas: list[ParcelaDeInteresse],
) -> AberturaDoPagamento:
    produtos = list(
        Produto.objects.filter(pk__in=rodada.estoques.values("produto_id")).order_by("pk")
    )
    linhas: list[_Linha] = []
    for produto in produtos:
        linhas += _linhas_do_produto(produto, [p for p in ativas if p.produto_id == produto.pk])
    por_comprador: dict[int, dict[int, Decimal]] = {}
    for parcela in ativas:
        itens = por_comprador.setdefault(parcela.comprador_id, {})
        itens[parcela.produto_id] = itens.get(parcela.produto_id, _ZERO) + (
            parcela.quantidade_reservada
        )
    por_id = {p.pk: p for p in produtos}
    cobrancas = calcular_cobranca(
        [
            CompradorACobrar(
                comprador_id,
                tuple(
                    ItemACobrar(produto_id, por_id[produto_id].preco, quantidade)
                    for produto_id, quantidade in itens.items()
                ),
            )
            for comprador_id, itens in por_comprador.items()
        ],
        frete,
    )
    abertura = AberturaDoPagamento.objects.create(
        ciclo=ciclo,
        rodada=rodada,
        t0=t0,
        frete=frete,
        total_produtos=sum((c.produtos for c in cobrancas), Decimal("0.00")),
        autor=autor,
    )
    compradores = Conta.objects.in_bulk([c.comprador_id for c in cobrancas])
    for cobranca in cobrancas:
        pedido = Pedido.objects.create(
            abertura=abertura,
            comprador=compradores[cobranca.comprador_id],
            produtos=cobranca.produtos,
            servico=cobranca.servico,
            frete=cobranca.frete,
            total=cobranca.total,
        )
        SituacaoDoPedido.objects.create(
            pedido=pedido, situacao=SituacaoDePagamento.AGUARDANDO_PAGAMENTO
        )
        criados = ItemDoPedido.objects.bulk_create(
            [
                ItemDoPedido(
                    pedido=pedido,
                    produto=por_id[item.produto_id],
                    nome=por_id[item.produto_id].nome,
                    unidade=por_id[item.produto_id].unidade,
                    incremento=por_id[item.produto_id].incremento,
                    multiplo=por_id[item.produto_id].multiplo,
                    preco_unitario=item.preco_unitario,
                    quantidade=item.quantidade,
                    subtotal=item.subtotal,
                )
                for item in cobranca.itens
            ]
        )
        item_por_produto = {i.produto_id: i for i in criados}
        ParcelaNoPedido.objects.bulk_create(
            [
                ParcelaNoPedido(
                    item=item_por_produto[linha.parcela.produto_id],
                    parcela=linha.parcela,
                    caixa=linha.caixa,
                    quantidade=linha.quantidade,
                )
                for linha in linhas
                if linha.parcela.comprador_id == cobranca.comprador_id
            ]
        )
    return abertura


def _soltar_a_reserva(ativas_congeladas: list[ParcelaDeInteresse]) -> None:
    """A parte reservada vai para o pedido. Sem pendente, a parcela passa a `em_pedido` com a
    reserva; com pendente, volta à fila (`pendente`, reserva zero) na mesma posição."""
    for parcela in ativas_congeladas:
        if parcela.quantidade_pendente == 0:
            parcela.situacao = SituacaoParcela.EM_PEDIDO
            parcela.save(update_fields=["situacao"])
        else:
            parcela.situacao = SituacaoParcela.PENDENTE
            parcela.quantidade_reservada = _ZERO
            parcela.save(update_fields=["situacao", "quantidade_reservada"])


def _avisar_pagamento_aberto(abertura: AberturaDoPagamento, fornecedor: Fornecedor) -> None:
    prazo = no_fuso_da_operacao(somar_horas(abertura.t0, HORAS_DO_PRAZO_DE_PAGAMENTO))
    for pedido in abertura.pedidos.select_related("comprador").order_by("pk"):
        corpo = (
            f"Seu pedido da rodada de {fornecedor.nome} foi congelado. "
            f"Produtos: {reais(pedido.produtos)}. Serviço: {reais(pedido.servico)}. "
            f"Frete: {reais(pedido.frete)}. Total: {reais(pedido.total)}. "
            f"Pague até {prazo:%d/%m/%Y} às {prazo:%H:%M} (horário de Brasília). "
            "Esse prazo de 24 horas não é prorrogado."
        )
        emitir_evento(
            Evento.PAGAMENTO_ABERTO,
            pedido.comprador,
            titulo=f"Pagamento aberto: {fornecedor.nome}"[:MAIOR_TITULO],
            corpo=corpo,
            link=f"/pedidos/{pedido.pk}/",
            chave=f"pagamento_aberto:{pedido.pk}:{pedido.comprador_id}",
        )


def abrir_pagamento(autor: Conta | None, rodada: Rodada, frete: Decimal) -> ResultadoDaAbertura:
    """Abre o pagamento da rodada com o fechamento encerrado (E08-02).

    Só o administrador. `frete` inválido: `ValueError`. Rodada fora de `fechamento_encerrado`:
    `TransicaoRecusada`. Mínimo não atingido depois de refeitas as caixas: a rodada volta para
    interesse, sem pedidos, e `etapa_final` é `interesse`.
    """
    if autor is None or autor.papel != Papel.ADMINISTRADOR:
        raise PermissionDenied
    valor_do_frete = _validar_frete(frete)
    with transaction.atomic():
        Fornecedor.objects.select_for_update().get(pk=rodada.fornecedor_id)
        travada = (
            Rodada.objects.select_for_update()
            .select_related("fornecedor")
            .filter(pk=rodada.pk)
            .first()
        )
        if travada is None or travada.etapa != Etapa.FECHAMENTO_ENCERRADO:
            raise TransicaoRecusada("fora_de_fechamento_encerrado_para_pagamento")
        ciclo = ciclo_vigente(travada)
        if ciclo is None:
            raise RuntimeError("rodada com fechamento encerrado sem ciclo")
        t0 = agora()  # lido depois das travas
        participantes = compradores_com_reserva(travada)
        saidas = _divisao_dos_excedentes(travada)
        avisar_excedentes_removidos(
            travada,
            ciclo,
            _por_comprador_e_produto(saidas),
            momento=MOMENTO_ABERTURA_DO_PAGAMENTO,
        )
        progresso = progresso_da_rodada(travada)
        removidas = [[s.parcela_id, s.produto.pk, str(s.removida)] for s in saidas]
        comum: dict[str, Any] = {
            "rodada": travada.pk,
            "ciclo": ciclo.pk,
            "t0": t0.isoformat(),
            "removidas": removidas,
        }
        if not progresso.atingido:
            voltar_para_interesse(travada, motivo=MOTIVO_DO_RETORNO, destinatarios=participantes)
            registrar_auditoria(
                autor,
                ACAO,
                travada,
                {
                    **comum,
                    "frete": str(valor_do_frete),
                    "valor_elegivel": str(progresso.valor_elegivel),
                    "minimo": str(progresso.minimo),
                    "resultado": "retorno_para_interesse",
                },
            )
            rodada.etapa = Etapa.INTERESSE
            return ResultadoDaAbertura(None, Etapa.INTERESSE)
        congeladas = list(
            ParcelaDeInteresse.objects.filter(
                produto__in=travada.estoques.values("produto_id"),
                situacao=SituacaoParcela.ATIVA,
                quantidade_reservada__gt=0,
            ).order_by("produto_id", "sequencia")
        )
        abertura = _congelar(travada, ciclo, autor, t0, valor_do_frete, congeladas)
        if abertura.total_produtos != progresso.valor_elegivel:
            raise RuntimeError("o total dos produtos difere do valor elegível da rodada")
        _soltar_a_reserva(congeladas)
        travada.etapa = Etapa.PAGAMENTO
        travada.save(update_fields=["etapa"])
        registrar_auditoria(
            autor,
            ACAO,
            travada,
            {
                **comum,
                "frete": str(valor_do_frete),
                "total_produtos": str(abertura.total_produtos),
                "pedidos": abertura.pedidos.count(),
                "resultado": "pagamento",
            },
        )
        _avisar_pagamento_aberto(abertura, travada.fornecedor)
    rodada.etapa = Etapa.PAGAMENTO
    return ResultadoDaAbertura(abertura, Etapa.PAGAMENTO)
