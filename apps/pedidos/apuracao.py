"""Apuração final do ciclo (E11).

A apuração tem dois atos do administrador: iniciá-la, a partir de `T0 + 48h` (esta fatia e as
seguintes), e aprovar o resultado. Iniciar reconsulta o provedor antes da transação, sem travas
(infraestrutura 4.2), e depois decide numa só transação: cancela os não pagos e grava a
`ApuracaoFinal`. A rodada continua em `pagamento`: a apuração feita é o registro, não uma etapa.

Ordem das travas da decisão: o fornecedor, a rodada, todos os produtos do fornecedor por `pk`
(e, em cada um, o estoque da rodada e as parcelas) e as `SituacaoDoPedido` de todos os pedidos da
abertura. A apuração não trava pagamento nenhum, então segue a ordem da E08-03.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import quantidade_com_unidade
from apps.catalogo.templatetags.catalogo import reais
from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.apuracao import frete_do_ciclo, registrar_apuracao_no_livro
from apps.financeiro.livro import travar_contas
from apps.financeiro.models import ApuracaoNoLivro, MotivoDoReembolso
from apps.financeiro.obrigacoes import contas_das_obrigacoes
from apps.financeiro.reembolsos import reembolso_integral_do_pedido, reembolso_parcial
from apps.fornecedores.models import Fornecedor
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao
from apps.nucleo.valores import arredondar_centavos
from apps.pagamentos.chamadas import agendar_chamada, executar_chamada_agora
from apps.pagamentos.consulta import (
    ConsultaAoProvedorFalhou,
    consultar_antes_de_decidir,
    exigir_fora_de_transacao,
    pendentes_das_referencias,
    situacao_registrada,
)
from apps.pagamentos.models import ChamadaAoProvedor, SituacaoDaChamada
from apps.pedidos.models import (
    AberturaDoPagamento,
    AprovacaoDoResultado,
    ApuracaoFinal,
    CaixaInvalidada,
    ItemDoPedido,
    MotivoDoCancelamento,
    ParcelaNoPedido,
    Pedido,
    RestauracaoDeCaixa,
    ResultadoDaApuracao,
    SituacaoDaTentativa,
    SituacaoDePagamento,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import agendar_cancelamento
from apps.pedidos.prazos import fim_da_margem, pode_iniciar_apuracao
from apps.pedidos.sinais import resultado_aprovado
from apps.rodadas.ciclos import ciclo_vigente
from apps.rodadas.fechamento import MOTIVO_DO_RETORNO_DO_PAGAMENTO, voltar_para_interesse
from apps.rodadas.models import Ciclo, EstoqueDaRodada, Etapa, Rodada

logger = logging.getLogger(__name__)

MOTIVO_DA_TENTATIVA = "apuracao"
MENSAGEM_DO_CANCELAMENTO = "O provedor não confirmou o cancelamento da cobrança {id_externo}."
MAIOR_TITULO = 150
ZERO = Decimal("0.000")
ZERO_DINHEIRO = Decimal("0.00")

MENSAGENS = {
    "fora_de_pagamento": "Só uma rodada na etapa de pagamento pode ser apurada.",
    "antes_do_prazo": (
        "A apuração só pode começar a partir de {liberada:%d/%m/%Y} às {liberada:%H:%M} "
        "(horário de Brasília)."
    ),
    "ja_apurada": "A apuração deste ciclo já foi feita.",
    "sem_apuracao": "A apuração deste ciclo ainda não foi feita.",
    "resultado_nao_valido": "Só um resultado válido pode ser aprovado.",
    "ja_aprovado": "O resultado desta apuração já foi aprovado.",
    "cobranca_aberta": "Há cobrança ainda aberta no provedor; tente de novo.",
}


class ApuracaoRecusada(Exception):
    """A apuração não pode ser feita agora. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str, liberada_em: datetime | None = None) -> None:
        self.codigo = codigo
        liberada = no_fuso_da_operacao(liberada_em) if liberada_em is not None else None
        self.mensagem = MENSAGENS[codigo].format(liberada=liberada)
        super().__init__(self.mensagem)


def _exigir_administrador(autor: Conta | None) -> Conta:
    if autor is None or autor.papel != Papel.ADMINISTRADOR:
        raise PermissionDenied
    return autor


def _conferir(rodada: Rodada, instante: datetime) -> AberturaDoPagamento:
    """As três conferências da apuração, sobre a rodada relida: em `pagamento`, ciclo ainda não
    apurado e `T0 + 48h` chegado. A primeira que falha vale."""
    if rodada.etapa != Etapa.PAGAMENTO:
        raise ApuracaoRecusada("fora_de_pagamento")
    ciclo = ciclo_vigente(rodada)
    abertura: AberturaDoPagamento | None = (
        AberturaDoPagamento.objects.filter(ciclo=ciclo).first() if ciclo else None
    )
    if abertura is None:
        raise ApuracaoRecusada("fora_de_pagamento")
    if ApuracaoFinal.objects.filter(ciclo_id=abertura.ciclo_id).exists():
        raise ApuracaoRecusada("ja_apurada")
    if not pode_iniciar_apuracao(abertura, instante):
        raise ApuracaoRecusada("antes_do_prazo", fim_da_margem(abertura))
    return abertura


def _travar(rodada_pk: int, fornecedor_id: int, compradores: list[int]) -> Rodada:
    """As travas da decisão, na ordem documentada no módulo. Devolve a rodada travada.

    Antes do fornecedor vão as contas dos compradores da abertura, por `pk`, com `FOR NO KEY
    UPDATE` como a moderação: toda operação de interesse trava a conta primeiro, e é a conta que
    serializa a suspensão ou a remoção com a apuração (a moderação só trava o fornecedor dos
    produtos em que enxerga parcelas, e a parcela restaurada ainda não está commitada). Assim a
    conta é lida sob trava para decidir a restauração (E11-04).

    Fornecedor, rodada, produtos, estoques e parcelas são travados com `FOR NO KEY UPDATE`: ele
    exclui as operações de interesse (que usam `FOR UPDATE`) e as outras apurações, mas deixa um
    pagamento que quita ou devolve inserir registros que apontam para a rodada e para o
    fornecedor. Com `FOR UPDATE`, o commit desse pagamento esperaria a conferência da chave
    estrangeira contra a apuração, que espera a trava da situação dele: impasse.
    """
    list(Conta.objects.select_for_update(no_key=True).filter(pk__in=compradores).order_by("pk"))
    Fornecedor.objects.select_for_update(no_key=True).get(pk=fornecedor_id)
    travada = Rodada.objects.select_for_update(no_key=True).get(pk=rodada_pk)
    produtos = list(
        Produto.objects.select_for_update(no_key=True)
        .filter(fornecedor_id=fornecedor_id)
        .order_by("pk")
    )
    no_estoque = set(
        EstoqueDaRodada.objects.filter(rodada_id=travada.pk).values_list("produto_id", flat=True)
    )
    for produto in produtos:
        if produto.pk in no_estoque:
            EstoqueDaRodada.objects.select_for_update(no_key=True).get(
                rodada_id=travada.pk, produto_id=produto.pk
            )
        list(
            ParcelaDeInteresse.objects.select_for_update(no_key=True)
            .filter(produto_id=produto.pk)
            .exclude(situacao=SituacaoParcela.REMOVIDA)
            .order_by("sequencia")
        )
    return travada


def _cancelar_os_nao_pagos(situacoes: list[SituacaoDoPedido], instante: datetime) -> list[int]:
    """Cada `aguardando_pagamento` passa a `cancelado` por inadimplência, sem mexer na
    composição do pedido (§7.1). Devolve os pedidos cancelados agora."""
    cancelados: list[int] = []
    for situacao in situacoes:
        if situacao.situacao != SituacaoDePagamento.AGUARDANDO_PAGAMENTO:
            continue
        situacao.situacao = SituacaoDePagamento.CANCELADO
        situacao.cancelado_em = instante
        situacao.motivo_do_cancelamento = MotivoDoCancelamento.INADIMPLENCIA
        situacao.save(update_fields=["situacao", "cancelado_em", "motivo_do_cancelamento"])
        cancelados.append(situacao.pedido_id)
    return cancelados


@dataclass(frozen=True)
class CalculoDoResultado:
    """O que a apuração decide sobre as caixas e o mínimo, só com os registros congelados e as
    situações sob trava: repetir o cálculo dá o mesmo resultado (E11-03)."""

    caixas: list[tuple[int, int]]  # (produto, número da caixa), em ordem
    unidades_invalidadas: dict[int, Decimal]  # item de pedido pago -> unidades em caixa invalidada
    descontos: dict[int, Decimal]  # item de pedido pago -> produtos do estorno proporcional
    valor_valido: Decimal
    minimo: Decimal
    resultado: str


def _calcular_o_resultado(abertura: AberturaDoPagamento, nao_pagos: set[int]) -> CalculoDoResultado:
    """Invalida a caixa inteira que tem uma parcela de pedido não pago, sem reorganizar (§6.3), e
    recalcula o mínimo só com o que os pagos ainda podem pedir (§8.2, passo 3.5). O valor das
    unidades invalidadas de um item pago é o do reembolso parcial da E10-02 para um pedido sem
    reembolso anterior: o subtotal inteiro se todas saem, senão a proporção arredondada."""
    parcelas = list(
        ParcelaNoPedido.objects.filter(item__pedido__abertura=abertura)
        .select_related("item")
        .order_by("pk")
    )
    invalidas = {
        (p.item.produto_id, p.caixa)
        for p in parcelas
        if p.item.pedido_id in nao_pagos and p.caixa is not None
    }
    unidades: dict[int, Decimal] = {}
    for parcela in parcelas:
        if parcela.item.pedido_id in nao_pagos or parcela.caixa is None:
            continue
        if (parcela.item.produto_id, parcela.caixa) in invalidas:
            unidades[parcela.item_id] = unidades.get(parcela.item_id, ZERO) + parcela.quantidade
    descontos: dict[int, Decimal] = {}
    valor_valido = ZERO_DINHEIRO
    itens = ItemDoPedido.objects.filter(pedido__abertura=abertura).exclude(pedido_id__in=nao_pagos)
    for item in itens.order_by("pk"):
        saem = unidades.get(item.pk, ZERO)
        if saem == 0:
            desconto = ZERO_DINHEIRO
        elif saem == item.quantidade:
            desconto = item.subtotal
        else:
            desconto = arredondar_centavos(item.subtotal * saem / item.quantidade)
        if saem > 0:
            descontos[item.pk] = desconto
        valor_valido += item.subtotal - desconto
    minimo = abertura.ciclo.minimo
    return CalculoDoResultado(
        caixas=sorted(invalidas),
        unidades_invalidadas=unidades,
        descontos=descontos,
        valor_valido=valor_valido,
        minimo=minimo,
        resultado=(
            ResultadoDaApuracao.VALIDA
            if valor_valido >= minimo
            else ResultadoDaApuracao.RETORNO_PARA_INTERESSE
        ),
    )


def _remover_as_parcelas_dos_inadimplentes(
    fornecedor_id: int, compradores: list[int]
) -> list[dict[str, Any]]:
    """Os inadimplentes perdem todas as parcelas `ativa`, `em_pedido` e `pendente` em produtos do
    fornecedor, inclusive de fora do estoque da rodada (§8.2, passo 3.2). A sequência e a
    quantidade original ficam; as parcelas de outros fornecedores não mudam. Nenhuma reserva é
    atendida agora: fora de interesse a fila não é atendida. Devolve o que saiu, por comprador."""
    parcelas = ParcelaDeInteresse.objects.filter(
        comprador_id__in=compradores,
        produto__fornecedor_id=fornecedor_id,
        situacao__in=(
            SituacaoParcela.ATIVA,
            SituacaoParcela.EM_PEDIDO,
            SituacaoParcela.PENDENTE,
        ),
    ).order_by("comprador_id", "produto_id", "sequencia")
    por_comprador: dict[int, list[list[object]]] = {}
    for parcela in parcelas:
        por_comprador.setdefault(parcela.comprador_id, []).append(
            [parcela.pk, str(parcela.quantidade_reservada), str(parcela.quantidade_pendente)]
        )
        parcela.quantidade_reservada = ZERO
        parcela.quantidade_pendente = ZERO
        parcela.situacao = SituacaoParcela.REMOVIDA
        parcela.save(update_fields=["quantidade_reservada", "quantidade_pendente", "situacao"])
    return [{"comprador": pk, "parcelas": removidas} for pk, removidas in por_comprador.items()]


def _avisar_o_cancelamento(pedidos: list[Pedido], fornecedor: Fornecedor) -> None:
    """O aviso de cancelamento ao comprador cujo pedido foi cancelado por esta apuração. Quem já
    tinha o pedido cancelado por suspensão ou remoção não recebe: a moderação já tratou a conta."""
    for pedido in pedidos:
        emitir_evento(
            Evento.ITENS_CANCELADOS,
            pedido.comprador,
            titulo=f"Pedido cancelado: {fornecedor.nome}"[:MAIOR_TITULO],
            corpo=(
                f"Seu pedido {pedido.pk} da rodada de {fornecedor.nome} foi cancelado porque o "
                "pagamento não foi identificado até o fim do prazo. Os itens desse fornecedor "
                "saíram do seu carrinho, inclusive reservas e quantidades pendentes. Nada foi "
                "cobrado neste pedido."
            ),
            link=f"/pedidos/{pedido.pk}/",
            chave=f"itens_cancelados:inadimplencia:{pedido.pk}:{pedido.comprador_id}",
        )


def _agendar_o_cancelamento(id_externo: str) -> ChamadaAoProvedor | None:
    """Agenda, numa transação curta só para isso, o cancelamento da cobrança com um alvo próprio da
    apuração (E07-R01): `t<tentativa>:apuracao` quando há tentativa, `<id_externo>:apuracao` para
    a cobrança sem tentativa vinculada. Uma chamada pendente do mesmo alvo é absorvida."""
    with transaction.atomic():
        tentativa = TentativaDePagamento.objects.filter(
            id_externo=id_externo, situacao=SituacaoDaTentativa.CRIADA
        ).first()
        if tentativa is not None:
            return agendar_cancelamento(tentativa, MOTIVO_DA_TENTATIVA)
        return agendar_chamada(
            "cancelar_cobranca",
            f"{id_externo}:{MOTIVO_DA_TENTATIVA}",
            parametros={"id_externo": id_externo},
        )


def _cancelar_no_provedor(pedidos: list[Pedido]) -> list[dict[str, str]]:
    """O passo 4-A da infraestrutura 4.3: cancela e confirma no provedor, fora de qualquer
    transação de negócio, cada cobrança `pendente` registrada com a referência de um pedido da
    abertura (as das tentativas `criada` e as órfãs). Se o provedor aprovar o pagamento no
    instante do cancelamento, vale o que ele registrou (P-6). Cancelamento não confirmado bloqueia
    a apuração com `ConsultaAoProvedorFalhou`; a chamada fica para o executor periódico."""
    referencias = [pedido.referencia_externa for pedido in pedidos]
    ordem = {referencia: posicao for posicao, referencia in enumerate(referencias)}
    pendentes = sorted(
        pendentes_das_referencias(referencias),
        key=lambda pagamento: (ordem[pagamento.referencia_externa], pagamento.id_externo),
    )
    canceladas: list[dict[str, str]] = []
    for pagamento in pendentes:
        id_externo, referencia = pagamento.id_externo, pagamento.referencia_externa
        chamada = _agendar_o_cancelamento(id_externo)
        if chamada is None:
            continue
        if executar_chamada_agora(chamada.pk).situacao == SituacaoDaChamada.FALHOU:
            consultar_antes_de_decidir(referencia)  # a recusa pode ser um pagamento já terminal
        situacao = situacao_registrada(id_externo)
        if situacao in (None, "pendente"):
            raise ConsultaAoProvedorFalhou(
                referencia,
                "cancelamento_nao_confirmado",
                MENSAGEM_DO_CANCELAMENTO.format(id_externo=id_externo),
            )
        canceladas.append({"id_externo": id_externo, "situacao": str(situacao)})
    return canceladas


def _gravar_a_apuracao(
    autor: Conta,
    abertura: AberturaDoPagamento,
    instante: datetime,
    situacoes: list[SituacaoDoPedido],
    calculo: CalculoDoResultado,
) -> ApuracaoFinal:
    """Grava a `ApuracaoFinal` com o resultado e as caixas invalidadas, depois do cálculo."""
    pagos = sum(1 for s in situacoes if s.situacao == SituacaoDePagamento.PAGO)
    apuracao = ApuracaoFinal.objects.create(
        ciclo_id=abertura.ciclo_id,
        abertura=abertura,
        autor=autor,
        iniciada_em=instante,
        pedidos_pagos=pagos,
        pedidos_nao_pagos=len(situacoes) - pagos,
        resultado=calculo.resultado,
        valor_valido=calculo.valor_valido,
        minimo=calculo.minimo,
    )
    for produto_id, numero in calculo.caixas:
        CaixaInvalidada.objects.create(apuracao=apuracao, produto_id=produto_id, numero=numero)
    return apuracao


@dataclass
class EfeitoNoPedido:
    """O que a apuração viável fez no pedido pago com unidades em caixa invalidada (E11-04)."""

    pedido: Pedido
    itens: list[tuple[str, str, Decimal]] = field(default_factory=list)  # nome, unidade, quantidade
    estorno: Decimal = ZERO_DINHEIRO
    reembolsos: list[dict[str, Any]] = field(default_factory=list)
    restauracoes: list[dict[str, Any]] = field(default_factory=list)
    nao_restauradas: list[dict[str, Any]] = field(default_factory=list)

    def como_dados(self) -> dict[str, Any]:
        return {
            "pedido": self.pedido.pk,
            "reembolsos": self.reembolsos,
            "restauracoes": self.restauracoes,
            "nao_restauradas": self.nao_restauradas,
        }


MOTIVO_DA_NAO_RESTAURACAO: dict[str, str] = {
    Situacao.SUSPENSA: "conta_suspensa",
    Situacao.REMOVIDA: "conta_removida",
}


def _restaurar_na_fila(
    apuracao: ApuracaoFinal, efeito: EfeitoNoPedido, item: ItemDoPedido, invalidadas: set[Any]
) -> None:
    """Cada `ParcelaNoPedido` do item numa caixa invalidada volta à fila de pendentes, na posição
    original (a sequência não muda e nenhuma parcela é criada). A parcela fica sem reserva na
    rodada apurada, inclusive a parte válida, que continua só no pedido. A conta suspensa ou
    removida não pode ter interesses: a parcela não é restaurada e a auditoria registra o motivo."""
    pedido = efeito.pedido
    conta = Conta.objects.get(pk=pedido.comprador_id)
    for no_pedido in ParcelaNoPedido.objects.filter(item=item).order_by("pk"):
        if (item.produto_id, no_pedido.caixa) not in invalidadas:
            continue
        if RestauracaoDeCaixa.objects.filter(parcela_no_pedido=no_pedido).exists():
            continue
        parcela = ParcelaDeInteresse.objects.get(pk=no_pedido.parcela_id)
        # só a conta impede a restauração: a parcela `removida` porque o comprador tirou a sobra
        # pendente continua dona das unidades pagas (E11-R01)
        motivo = MOTIVO_DA_NAO_RESTAURACAO.get(str(conta.situacao))
        if motivo is not None:
            efeito.nao_restauradas.append(
                {"parcela_no_pedido": no_pedido.pk, "parcela": parcela.pk, "motivo": motivo}
            )
            continue
        RestauracaoDeCaixa.objects.create(
            apuracao=apuracao,
            parcela_no_pedido=no_pedido,
            parcela=parcela,
            quantidade=no_pedido.quantidade,
        )
        parcela.quantidade_pendente += no_pedido.quantidade
        parcela.quantidade_reservada = ZERO
        parcela.situacao = SituacaoParcela.PENDENTE
        parcela.save(update_fields=["quantidade_pendente", "quantidade_reservada", "situacao"])
        efeito.restauracoes.append(
            {
                "parcela_no_pedido": no_pedido.pk,
                "parcela": parcela.pk,
                "quantidade": str(no_pedido.quantidade),
            }
        )


def _contas_impedidas(compradores: set[int]) -> dict[int, str]:
    """A situação da conta de cada comprador: comprador -> motivo, só se suspensa ou removida."""
    impedidas: dict[int, str] = {}
    for comprador_id in sorted(compradores):
        motivo = MOTIVO_DA_NAO_RESTAURACAO.get(str(Conta.objects.get(pk=comprador_id).situacao))
        if motivo is not None:
            impedidas[comprador_id] = motivo
    return impedidas


def _contas_impedidas_dos_pagantes(pagos: list[Pedido]) -> dict[int, str]:
    """A situação da conta dos pagantes, lida uma só vez, com as contas travadas pela apuração
    (E11-05 regra 2-A). Decide a remoção das parcelas, a não restauração, os destinatários do aviso
    e o registro da auditoria."""
    return _contas_impedidas({p.comprador_id for p in pagos})


def _restaurar_as_reservas_dos_pagantes(
    abertura: AberturaDoPagamento, pagos: list[int], impedidas: dict[int, str] | None = None
) -> tuple[list[list[object]], list[dict[str, Any]]]:
    """No retorno para interesse as reservas de quem pagou continuam na própria rodada, com a
    ordem original (E11-05): cada parcela que aparece num pedido pago passa a `ativa`, com a
    reserva igual à soma congelada nesse ciclo (a pendência não muda). Isso vale para a que ficou
    `em_pedido` e para a que ficou `pendente` com a parte congelada só no pedido (E08-02). As
    unidades de caixa invalidada ficam reservadas: no retorno não há fila. Só a conta impede a
    restauração (suspensa ou removida: as parcelas dela saem antes, E11-R02); a situação atual da
    parcela, inclusive `removida` pela sobra pendente que o comprador tirou, não impede
    (E11-R01)."""
    somas: dict[int, Decimal] = {}
    donos: dict[int, int] = {}
    linhas = ParcelaNoPedido.objects.filter(
        item__pedido__abertura=abertura, item__pedido_id__in=pagos
    ).select_related("item__pedido")
    for linha in linhas.order_by("pk"):
        somas[linha.parcela_id] = somas.get(linha.parcela_id, ZERO) + linha.quantidade
        donos[linha.parcela_id] = linha.item.pedido.comprador_id
    if impedidas is None:  # chamada direta: a mesma leitura da situação, para os donos
        impedidas = _contas_impedidas(set(donos.values()))
    restauradas: list[list[object]] = []
    nao_restauradas: list[dict[str, Any]] = []
    for parcela_pk in sorted(somas):
        parcela = ParcelaDeInteresse.objects.get(pk=parcela_pk)
        motivo = impedidas.get(donos[parcela_pk])
        if motivo is not None:
            nao_restauradas.append({"parcela": parcela.pk, "motivo": motivo})
            continue
        parcela.quantidade_reservada = somas[parcela_pk]
        parcela.situacao = SituacaoParcela.ATIVA
        parcela.save(update_fields=["quantidade_reservada", "situacao"])
        restauradas.append([parcela.pk, str(parcela.quantidade_reservada)])
    return restauradas, nao_restauradas


def _remover_as_parcelas_das_contas_impedidas(
    rodada: Rodada, impedidas: dict[int, str]
) -> list[dict[str, Any]]:
    """No retorno, a reserva de uma conta que não pode ter interesses (suspensa ou removida) não
    pode ocupar o estoque da rodada devolvida ao interesse (§2, E05-07): cada parcela do pagante
    em produto do fornecedor, `em_pedido`, `ativa` ou `pendente`, passa a `removida`, com reserva e
    pendência zero. A sequência e a quantidade original ficam, e o pedido não muda (E11-R02).
    Acontece antes da conferência do estoque e da fila, que usam o que sobra. Devolve, por
    parcela, o motivo e as quantidades que ela tinha."""
    removidas: list[dict[str, Any]] = []
    for comprador_id, motivo in sorted(impedidas.items()):
        parcelas = ParcelaDeInteresse.objects.filter(
            comprador_id=comprador_id,
            produto__fornecedor_id=rodada.fornecedor_id,
            situacao__in=(
                SituacaoParcela.ATIVA,
                SituacaoParcela.EM_PEDIDO,
                SituacaoParcela.PENDENTE,
            ),
        ).order_by("produto_id", "sequencia")
        for parcela in parcelas:
            removidas.append(
                {
                    "comprador": comprador_id,
                    "parcela": parcela.pk,
                    "motivo": motivo,
                    "reservada": str(parcela.quantidade_reservada),
                    "pendente": str(parcela.quantidade_pendente),
                }
            )
            parcela.quantidade_reservada = ZERO
            parcela.quantidade_pendente = ZERO
            parcela.situacao = SituacaoParcela.REMOVIDA
            parcela.save(update_fields=["quantidade_reservada", "quantidade_pendente", "situacao"])
    return removidas


def _conferir_o_estoque(rodada: Rodada) -> None:
    """Com o estoque travado, o total reservado de cada produto da rodada cabe no limite. Deve
    valer sempre (as reservas restauradas couberam na abertura e o estoque não muda fora do
    interesse); se falhar, a apuração inteira é desfeita e o log diz o produto."""
    for estoque in EstoqueDaRodada.objects.filter(rodada_id=rodada.pk).select_related("produto"):
        reservado = total_reservado(estoque.produto)
        if estoque.limite is not None and reservado > estoque.limite:
            logger.error(
                "Retorno para interesse: produto %s com reserva %s acima do limite %s",
                estoque.produto_id,
                reservado,
                estoque.limite,
            )
            raise RuntimeError("o total reservado passa do estoque da rodada")


def _devolver_integralmente(apuracao: ApuracaoFinal, pedidos: list[Pedido]) -> list[dict[str, Any]]:
    """A devolução integral de cada pedido pago (E10-02): a obrigação, financiada pela custódia do
    ciclo, espera a autorização do administrador. Sem apuração no livro."""
    gravados: list[dict[str, Any]] = []
    _travar_as_contas_das_devolucoes(apuracao, pedidos)
    for pedido in pedidos:
        registrado = reembolso_integral_do_pedido(
            pedido,
            chave=f"minimo:{apuracao.pk}:{pedido.pk}",
            motivo=MotivoDoReembolso.MINIMO_NAO_ATINGIDO,
            autor=SISTEMA,
        )
        if registrado is None:
            continue
        reembolso = registrado.reembolso
        gravados.append(
            {
                "chave": reembolso.chave,
                "pedido": pedido.pk,
                "produtos": str(reembolso.produtos),
                "servico": str(reembolso.servico),
                "frete": str(reembolso.frete),
            }
        )
    return gravados


def _avisar_o_retorno(
    apuracao: ApuracaoFinal, fornecedor: Fornecedor, pedidos: list[Pedido]
) -> None:
    """O aviso de retorno para interesse a cada comprador pagante, com chave própria (não colide
    com a do ciclo, da E06-06). O mínimo do fornecedor não aparece."""
    for pedido in pedidos:
        emitir_evento(
            Evento.RETORNO_PARA_INTERESSE,
            pedido.comprador,
            titulo=f"Rodada de volta ao interesse: {fornecedor.nome}"[:MAIOR_TITULO],
            corpo=(
                f"A rodada de {fornecedor.nome} voltou para a fase de interesse porque os "
                "pagamentos confirmados não atingiram o mínimo do fornecedor. Seus interesses "
                "continuam reservados na rodada, na ordem original, e você pode alterá-los. "
                f"O valor pago de {reais(pedido.total)} será devolvido integralmente depois da "
                "autorização do administrador."
            ),
            link=f"/pedidos/{pedido.pk}/",
            chave=f"retorno_para_interesse:apuracao:{apuracao.pk}:{pedido.comprador_id}",
        )


def _travar_as_contas_das_devolucoes(apuracao: ApuracaoFinal, pedidos: list[Pedido]) -> None:
    """Cada estorno cria uma obrigação e trava as contas dela, e a regra do livro-razão manda
    travar em ordem crescente de `pk`. Com mais de um pagante a criar obrigação, o conjunto das
    contas de todos é travado de uma vez antes da primeira (as contas das obrigações novas nascem
    com `pk` maior e vêm depois)."""
    compradores = {p.comprador_id: p.comprador for p in pedidos}
    ciclo = apuracao.ciclo
    contas = contas_das_obrigacoes(
        ciclo.rodada, ciclo, [compradores[pk] for pk in sorted(compradores)]
    )
    travar_contas(*contas)


def _estornar_e_restaurar(
    apuracao: ApuracaoFinal, calculo: CalculoDoResultado
) -> list[EfeitoNoPedido]:
    """Com o resultado válido: para cada pedido pago com unidades em caixa invalidada, o estorno
    proporcional por item (E10-02, que gera a obrigação e espera a autorização na lista de
    devoluções) e a volta das unidades à fila. As chaves únicas tornam o passo idempotente: o
    reembolso é por `caixa:<apuração>:<item>` e a restauração por `ParcelaNoPedido`."""
    itens = list(
        ItemDoPedido.objects.filter(pk__in=list(calculo.unidades_invalidadas))
        .select_related("pedido")
        .order_by("pedido_id", "pk")
    )
    invalidadas = set(calculo.caixas)
    _travar_as_contas_das_devolucoes(apuracao, [item.pedido for item in itens])
    efeitos: dict[int, EfeitoNoPedido] = {}
    for item in itens:
        efeito = efeitos.setdefault(item.pedido_id, EfeitoNoPedido(item.pedido))
        quantidade = calculo.unidades_invalidadas[item.pk]
        reembolso = reembolso_parcial(
            item,
            quantidade,
            chave=f"caixa:{apuracao.pk}:{item.pk}",
            motivo=MotivoDoReembolso.CAIXA_INVALIDADA,
            autor=SISTEMA,
        ).reembolso
        if reembolso.produtos != calculo.descontos[item.pk]:
            raise RuntimeError("o estorno de produtos difere do desconto do valor válido")
        efeito.itens.append((item.nome, item.unidade, quantidade))
        efeito.estorno += reembolso.produtos + reembolso.servico + reembolso.frete
        efeito.reembolsos.append(
            {
                "chave": reembolso.chave,
                "item": item.pk,
                "quantidade": str(quantidade),
                "produtos": str(reembolso.produtos),
                "servico": str(reembolso.servico),
                "frete": str(reembolso.frete),
            }
        )
        _restaurar_na_fila(apuracao, efeito, item, invalidadas)
    return list(efeitos.values())


def _avisar_a_caixa_incompleta(
    apuracao: ApuracaoFinal, fornecedor: Fornecedor, efeitos: list[EfeitoNoPedido]
) -> None:
    """O aviso ao comprador pagante cujas unidades estavam em caixa invalidada."""
    for efeito in efeitos:
        pedido = efeito.pedido
        lista = ", ".join(
            f"{quantidade_com_unidade(quantidade, unidade)} de {nome}"
            for nome, unidade, quantidade in efeito.itens
        )
        fila = (
            " Essas unidades voltaram para a fila de pendentes do fornecedor, na posição "
            "original, e serão reservadas quando houver estoque numa próxima rodada."
            if efeito.restauracoes
            else ""
        )
        emitir_evento(
            Evento.ITENS_CANCELADOS,
            pedido.comprador,
            titulo=f"Itens em caixa incompleta: {fornecedor.nome}"[:MAIOR_TITULO],
            corpo=(
                f"{lista} estavam em caixa que ficou incompleta por falta de pagamento de outro "
                f"comprador. O estorno de {reais(efeito.estorno)} foi registrado e será feito "
                f"depois da autorização do administrador.{fila}"
            ),
            link=f"/pedidos/{pedido.pk}/",
            chave=f"itens_cancelados:caixa:{apuracao.pk}:{pedido.comprador_id}",
        )


def _auditar_a_apuracao(
    autor: Conta,
    rodada: Rodada,
    abertura: AberturaDoPagamento,
    instante: datetime,
    situacoes: list[SituacaoDoPedido],
    cancelados: list[int],
    anteriores: dict[int, str],
    inadimplentes: list[dict[str, Any]],
    calculo: CalculoDoResultado,
    efeitos: list[EfeitoNoPedido],
    retorno: dict[str, Any] | None,
    cobrancas_canceladas: list[dict[str, str]],
) -> None:
    pagos = [s.pedido_id for s in situacoes if s.situacao == SituacaoDePagamento.PAGO]
    nao_pagos = [s.pedido_id for s in situacoes if s.situacao != SituacaoDePagamento.PAGO]
    dados: dict[str, Any] = {
        "rodada": rodada.pk,
        "ciclo": abertura.ciclo_id,
        "iniciada_em": instante.isoformat(),
        "pagos": pagos,
        "nao_pagos": [[pk, anteriores[pk]] for pk in nao_pagos],
        "cancelados_agora": cancelados,
        "inadimplentes": inadimplentes,
        "caixas": [[produto_id, numero] for produto_id, numero in calculo.caixas],
        "valor_valido": str(calculo.valor_valido),
        "minimo": str(calculo.minimo),
        "resultado": calculo.resultado,
        "pedidos": [efeito.como_dados() for efeito in efeitos],
        "cobrancas_canceladas": cobrancas_canceladas,
    }
    if retorno is not None:
        dados["retorno"] = retorno
    registrar_auditoria(autor, "rodada.apuracao_final", rodada, dados)


def _retornar_para_interesse(
    apuracao: ApuracaoFinal,
    rodada: Rodada,
    abertura: AberturaDoPagamento,
    pedidos: list[Pedido],
    situacoes: list[SituacaoDoPedido],
) -> dict[str, Any]:
    """O ramo do mínimo não atendido (E11-05): restaura as reservas dos pagantes, confere o estoque,
    devolve a rodada ao interesse (que atende a fila com o estoque liberado pelos inadimplentes) e
    gera a devolução integral dos pedidos pagos. Não apura no livro: não há frete efetivo."""
    pagos_ids = [s.pedido_id for s in situacoes if s.situacao == SituacaoDePagamento.PAGO]
    pagos = [p for p in pedidos if p.pk in pagos_ids]
    impedidas = _contas_impedidas_dos_pagantes(pagos)
    removidas = _remover_as_parcelas_das_contas_impedidas(rodada, impedidas)
    restauradas, nao_restauradas = _restaurar_as_reservas_dos_pagantes(
        abertura, pagos_ids, impedidas
    )
    _conferir_o_estoque(rodada)
    voltar_para_interesse(rodada, motivo=MOTIVO_DO_RETORNO_DO_PAGAMENTO, destinatarios=[])
    reembolsos = _devolver_integralmente(apuracao, pagos)
    # o aviso fala de interesses reservados: só quem tem conta ativa o recebe (E11-R02)
    _avisar_o_retorno(
        apuracao, rodada.fornecedor, [p for p in pagos if p.comprador_id not in impedidas]
    )
    return {
        "restauradas": restauradas,
        "contas_impedidas": [
            {"comprador": comprador_id, "motivo": motivo}
            for comprador_id, motivo in sorted(impedidas.items())
        ],
        "removidas_por_conta_impedida": removidas,
        "nao_restauradas": nao_restauradas,
        "reembolsos": reembolsos,
    }


def _conferir_a_aprovacao(rodada: Rodada) -> ApuracaoFinal:
    """As conferências da aprovação sobre a rodada relida: em `pagamento`, ciclo vigente apurado
    com resultado válido e ainda não aprovado. A primeira que falha vale."""
    if rodada.etapa != Etapa.PAGAMENTO:
        raise ApuracaoRecusada("fora_de_pagamento")
    ciclo = ciclo_vigente(rodada)
    apuracao: ApuracaoFinal | None = (
        ApuracaoFinal.objects.filter(ciclo=ciclo).first() if ciclo else None
    )
    if apuracao is None:
        raise ApuracaoRecusada("sem_apuracao")
    if apuracao.resultado != ResultadoDaApuracao.VALIDA:
        raise ApuracaoRecusada("resultado_nao_valido")
    if AprovacaoDoResultado.objects.filter(apuracao=apuracao).exists():
        raise ApuracaoRecusada("ja_aprovado")
    return apuracao


def _pedidos_validos(calculo: CalculoDoResultado, pagos: list[Pedido]) -> list[Pedido]:
    """Os pedidos pagos com ao menos uma unidade fora das caixas invalidadas. Um pedido pago só
    com unidades invalidadas não é válido: a custódia dele já financiou os reembolsos (E11-04)."""
    com_unidade_valida = {
        item.pedido_id
        for item in ItemDoPedido.objects.filter(pedido__in=pagos)
        if calculo.unidades_invalidadas.get(item.pk, ZERO) < item.quantidade
    }
    return [pedido for pedido in pagos if pedido.pk in com_unidade_valida]


def _registrar_a_apuracao_no_livro(
    autor: Conta, ciclo: Ciclo, validos: list[Pedido]
) -> ApuracaoNoLivro:
    """A apuração final aprovada no livro-razão (E09-06): a custódia dos pedidos válidos vai para a
    obrigação com o fornecedor, a receita de serviço e o frete; o frete dos inadimplentes vira
    déficit do administrador (P-1)."""
    return registrar_apuracao_no_livro(ciclo, validos, autor=autor)


def aprovar_resultado(autor: Conta | None, rodada: Rodada) -> AprovacaoDoResultado:
    """Aprova o resultado válido da apuração e avança a rodada para `aguardando_fornecedor`.

    Só o administrador (`PermissionDenied`). Só fora de transação (`RuntimeError`): a nova consulta
    ao provedor vem antes da decisão e, se falhar, bloqueia o avanço. Um pagamento descoberto agora
    segue as regras da E11-01 (devolução e alerta) e não refaz o resultado (§7.1, §8.3).
    """
    administrador = _exigir_administrador(autor)
    exigir_fora_de_transacao()
    atual = Rodada.objects.get(pk=rodada.pk)
    apuracao = _conferir_a_aprovacao(atual)
    pedidos = list(Pedido.objects.filter(abertura_id=apuracao.abertura_id).order_by("pk"))
    for pedido in pedidos:
        consultar_antes_de_decidir(pedido.referencia_externa)
    with transaction.atomic():
        Fornecedor.objects.select_for_update(no_key=True).get(pk=atual.fornecedor_id)
        travada = Rodada.objects.select_for_update(no_key=True).get(pk=atual.pk)
        apuracao = _conferir_a_aprovacao(travada)
        abertura = apuracao.abertura
        situacoes = list(
            SituacaoDoPedido.objects.filter(pedido__abertura=abertura).order_by("pedido_id")
        )
        pagos_ids = {s.pedido_id for s in situacoes if s.situacao == SituacaoDePagamento.PAGO}
        nao_pagos = {s.pedido_id for s in situacoes} - pagos_ids
        calculo = _calcular_o_resultado(abertura, nao_pagos)
        validos = _pedidos_validos(calculo, [p for p in pedidos if p.pk in pagos_ids])
        ciclo = abertura.ciclo
        _registrar_a_apuracao_no_livro(administrador, ciclo, validos)
        travada.etapa = Etapa.AGUARDANDO_FORNECEDOR
        travada.save(update_fields=["etapa"])
        instante = agora()
        aprovacao = AprovacaoDoResultado.objects.create(
            apuracao=apuracao, autor=administrador, aprovada_em=instante
        )
        frete = frete_do_ciclo(ciclo)
        registrar_auditoria(
            administrador,
            "rodada.aprovar_resultado",
            travada,
            {
                "rodada": travada.pk,
                "ciclo": ciclo.pk,
                "apuracao": apuracao.pk,
                "pedidos_validos": [p.pk for p in validos],
                "frete_efetivo": str(frete.efetivo),
                "frete_arrecadado": str(frete.arrecadado),
                "deficit": str(frete.deficit),
            },
        )
        resultado_aprovado.send(
            sender=AprovacaoDoResultado, rodada=travada, ciclo=ciclo, apuracao=apuracao
        )
    rodada.etapa = Etapa.AGUARDANDO_FORNECEDOR
    return aprovacao


def iniciar_apuracao(autor: Conta | None, rodada: Rodada) -> ApuracaoFinal:
    """Inicia a apuração final do ciclo vigente da rodada em `pagamento`, a partir de `T0 + 48h`.

    Só o administrador (`PermissionDenied`). Só fora de transação (`RuntimeError`): a reconsulta
    ao provedor vem antes da decisão. Uma `ConsultaAoProvedorFalhou` bloqueia a apuração.
    """
    administrador = _exigir_administrador(autor)
    exigir_fora_de_transacao()
    atual = Rodada.objects.get(pk=rodada.pk)
    abertura = _conferir(atual, agora())
    pedidos = list(Pedido.objects.filter(abertura=abertura).order_by("pk"))
    for pedido in pedidos:
        consultar_antes_de_decidir(pedido.referencia_externa)
    canceladas_no_provedor = _cancelar_no_provedor(pedidos)
    pedido_ids = [p.pk for p in pedidos]
    with transaction.atomic():
        travada = _travar(atual.pk, atual.fornecedor_id, sorted({p.comprador_id for p in pedidos}))
        instante = agora()  # lido depois das travas
        _conferir(travada, instante)
        if pendentes_das_referencias([p.referencia_externa for p in pedidos]):
            raise ApuracaoRecusada("cobranca_aberta")
        situacoes = list(
            SituacaoDoPedido.objects.select_for_update()
            .filter(pedido_id__in=pedido_ids)
            .order_by("pedido_id")
        )
        anteriores = {s.pedido_id: s.situacao for s in situacoes}
        nao_pagos = {s.pedido_id for s in situacoes if s.situacao != SituacaoDePagamento.PAGO}
        cancelados = _cancelar_os_nao_pagos(situacoes, instante)
        compradores = [p.comprador_id for p in pedidos if p.pk in nao_pagos]
        inadimplentes = _remover_as_parcelas_dos_inadimplentes(travada.fornecedor_id, compradores)
        calculo = _calcular_o_resultado(abertura, nao_pagos)
        _avisar_o_cancelamento([p for p in pedidos if p.pk in cancelados], travada.fornecedor)
        apuracao = _gravar_a_apuracao(administrador, abertura, instante, situacoes, calculo)
        efeitos: list[EfeitoNoPedido] = []
        if calculo.resultado == ResultadoDaApuracao.VALIDA:
            efeitos = _estornar_e_restaurar(apuracao, calculo)
            _avisar_a_caixa_incompleta(apuracao, travada.fornecedor, efeitos)
        retorno: dict[str, Any] | None = None
        if calculo.resultado == ResultadoDaApuracao.RETORNO_PARA_INTERESSE:
            retorno = _retornar_para_interesse(apuracao, travada, abertura, pedidos, situacoes)
        _auditar_a_apuracao(
            administrador,
            travada,
            abertura,
            instante,
            situacoes,
            cancelados,
            anteriores,
            inadimplentes,
            calculo,
            efeitos,
            retorno,
            canceladas_no_provedor,
        )
        return apuracao
