"""Cancelamento da rodada pelo administrador (E12).

O administrador cancela a rodada inteira por decisão própria, sem motivo, indicando se existe
reembolso devido (§7, §7.2, 17.2). Esta fatia (E12-01) entrega o registro, as recusas, as travas e
o efeito nos interesses; as seguintes acrescentam os pedidos, o reembolso e o aviso.

Ordem das travas: a mesma da apuração (E11, com a correção E11-R04, `FOR NO KEY UPDATE`): as contas
dos compradores envolvidos, o fornecedor, a rodada, os produtos do fornecedor, os estoques da
rodada e as parcelas não removidas. O cancelamento concorre com a apuração, as operações de
interesse, a moderação e o encerramento do fechamento, e essa ordem evita impasse com eles.
"""

import logging
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Exists, OuterRef

from apps.catalogo.templatetags.catalogo import reais
from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.devolucoes import DevolucaoRecusada, autorizar_devolucao
from apps.financeiro.livro import travar_contas
from apps.financeiro.models import MotivoDoReembolso, ObrigacaoComComprador, ParcelaDeDevolucao
from apps.financeiro.obrigacoes import contas_das_obrigacoes
from apps.financeiro.reembolsos import reembolso_integral_do_pedido
from apps.financeiro.reserva import sem_cobertura_da_obrigacao
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import agendar_chamada
from apps.pagamentos.consulta import (
    ConsultaAoProvedorFalhou,
    consultar_antes_de_decidir,
    exigir_fora_de_transacao,
    pendentes_das_referencias,
)
from apps.pedidos.apuracao import _travar
from apps.pedidos.models import (
    AberturaDoPagamento,
    CancelamentoDaRodada,
    MotivoDoCancelamento,
    Pedido,
    SituacaoDaTentativa,
    SituacaoDePagamento,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import agendar_cancelamento
from apps.rodadas.ciclos import ciclo_vigente
from apps.rodadas.models import Etapa, Rodada

logger = logging.getLogger(__name__)

MAIOR_MENSAGEM = 1000
MAIOR_TITULO = 150
MOTIVO_NO_ALVO = MotivoDoCancelamento.CANCELAMENTO_DA_RODADA.value
ETAPAS_COM_PEDIDOS = (Etapa.PAGAMENTO, Etapa.AGUARDANDO_FORNECEDOR)
ZERO = Decimal("0.000")

MENSAGENS = {
    "rodada_inexistente": "A rodada não existe.",
    "ja_cancelada": "Esta rodada já foi cancelada.",
    "rodada_encerrada": "A rodada já foi encerrada e não pode ser cancelada.",
    "indicacao_obrigatoria": "Informe se existe reembolso devido.",
    "mensagem_longa": "A mensagem passa de 1000 caracteres.",
}


class CancelamentoRecusado(Exception):
    """O cancelamento foi recusado; `codigo` identifica a recusa e a mensagem é a da tela."""

    @staticmethod
    def mensagem_de(codigo: str) -> str:
        return MENSAGENS[codigo]

    def __init__(self, codigo: str) -> None:
        super().__init__(MENSAGENS[codigo])
        self.codigo = codigo


def _conferir_a_etapa(etapa: str) -> None:
    """A etapa precisa ser cancelável: as ativas. A cancelada e a encerrada têm recusa própria."""
    if etapa == Etapa.CANCELADA:
        raise CancelamentoRecusado("ja_cancelada")
    if etapa == Etapa.DISPONIVEL_PARA_RETIRADA:
        raise CancelamentoRecusado("rodada_encerrada")


def _compradores_envolvidos(rodada: Rodada) -> list[int]:
    """Os donos das parcelas não removidas dos produtos do fornecedor e os compradores dos pedidos
    de todas as aberturas da rodada, por `pk`."""
    donos = ParcelaDeInteresse.objects.filter(produto__fornecedor_id=rodada.fornecedor_id).exclude(
        situacao=SituacaoParcela.REMOVIDA
    )
    compradores = set(donos.values_list("comprador_id", flat=True))
    compradores |= set(
        Pedido.objects.filter(abertura__rodada_id=rodada.pk).values_list("comprador_id", flat=True)
    )
    return sorted(compradores)


def _pedidos_da_abertura_vigente(rodada: Rodada) -> list[Pedido]:
    """Os pedidos da abertura do ciclo vigente, nas etapas que têm pedido congelado. Os das
    aberturas anteriores já foram apurados (retorno ao interesse) e só são lidos."""
    if rodada.etapa not in ETAPAS_COM_PEDIDOS:
        return []
    ciclo = ciclo_vigente(rodada)
    abertura = AberturaDoPagamento.objects.filter(ciclo=ciclo).first() if ciclo else None
    if abertura is None:
        return []
    return list(Pedido.objects.filter(abertura=abertura).order_by("pk"))


def _cancelar_os_pedidos_nao_pagos(
    pedidos: list[Pedido], instante: Any
) -> tuple[list[dict[str, Any]], list[int]]:
    """Regra 3: cada pedido `aguardando_pagamento` passa a `cancelado` pelo cancelamento da
    rodada, com as situações já travadas. Os já cancelados não mudam; os pagos continuam pagos.
    A composição do pedido não é tocada (§7.1). Devolve os cancelados agora e os pagos."""
    cancelados: list[dict[str, Any]] = []
    pagos: list[int] = []
    situacoes = (
        SituacaoDoPedido.objects.select_for_update()
        .filter(pedido__in=pedidos)
        .order_by("pedido_id")
    )
    for situacao in situacoes:
        if situacao.situacao == SituacaoDePagamento.PAGO:
            pagos.append(situacao.pedido_id)
        elif situacao.situacao == SituacaoDePagamento.AGUARDANDO_PAGAMENTO:
            cancelados.append(
                {"pedido": situacao.pedido_id, "situacao_anterior": str(situacao.situacao)}
            )
            situacao.situacao = SituacaoDePagamento.CANCELADO
            situacao.cancelado_em = instante
            situacao.motivo_do_cancelamento = MotivoDoCancelamento.CANCELAMENTO_DA_RODADA
            situacao.save(update_fields=["situacao", "cancelado_em", "motivo_do_cancelamento"])
    return cancelados, pagos


def _agendar_o_cancelamento_das_cobrancas(pedidos: list[Pedido]) -> list[dict[str, str]]:
    """Regra 6: agenda, na transação, o cancelamento no provedor de cada cobrança pendente: a das
    tentativas `criada` (de pedido cancelado ou pago) e as órfãs, sem tentativa vinculada. O alvo
    próprio do motivo evita esperar uma chamada em andamento (E07-R01). A tentativa `solicitada`,
    sem cobrança, não recebe agendamento: a criação já recusa o pedido cancelado."""
    agendadas: list[dict[str, str]] = []
    tentativas = list(
        TentativaDePagamento.objects.filter(pedido__in=pedidos).order_by("pedido_id", "numero")
    )
    com_tentativa = {t.id_externo for t in tentativas if t.id_externo}
    for tentativa in tentativas:
        if tentativa.situacao != SituacaoDaTentativa.CRIADA:
            continue
        chamada = agendar_cancelamento(tentativa, MOTIVO_NO_ALVO)
        if chamada is not None:
            agendadas.append({"alvo": chamada.alvo, "id_externo": str(tentativa.id_externo)})
    for pagamento in pendentes_das_referencias([p.referencia_externa for p in pedidos]):
        if pagamento.id_externo in com_tentativa:
            continue
        chamada = agendar_chamada(
            "cancelar_cobranca",
            f"{pagamento.id_externo}:{MOTIVO_NO_ALVO}",
            parametros={"id_externo": pagamento.id_externo},
        )
        agendadas.append({"alvo": chamada.alvo, "id_externo": pagamento.id_externo})
    return agendadas


def _remover_os_interesses(fornecedor_id: int) -> list[dict[str, Any]]:
    """Regra 6: cada parcela `ativa` ou `em_pedido` perde a reserva. Com parte pendente, vira
    `pendente` (a fila do fornecedor não pertence a ciclo nenhum, §5.2); sem ela, `removida`. As
    parcelas já `pendente` não mudam; nenhuma é criada e nenhuma sequência muda. Com as parcelas
    já travadas por `_travar`."""
    alteradas: list[dict[str, Any]] = []
    parcelas = (
        ParcelaDeInteresse.objects.filter(
            produto__fornecedor_id=fornecedor_id,
            situacao__in=(SituacaoParcela.ATIVA, SituacaoParcela.EM_PEDIDO),
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


def _consultar_antes_de_cancelar(rodada: Rodada) -> None:
    """Regra 2 da E12-03: antes das travas e fora de transação, consulta o provedor sobre cada
    pedido pago de qualquer abertura da rodada e sobre os `aguardando_pagamento` da abertura
    vigente, por `pk`. Uma `ConsultaAoProvedorFalhou` bloqueia o cancelamento, sem escrita; o
    pagamento sincronizado agora segue as regras da E08-04 (pode quitar um pedido)."""
    vigente = ciclo_vigente(rodada)
    pedidos = Pedido.objects.filter(abertura__rodada_id=rodada.pk).select_related(
        "abertura", "estado"
    )
    for pedido in pedidos.order_by("pk"):
        situacao = pedido.estado.situacao
        aguardando = (
            situacao == SituacaoDePagamento.AGUARDANDO_PAGAMENTO
            and vigente is not None
            and pedido.abertura.ciclo_id == vigente.pk
        )
        if situacao == SituacaoDePagamento.PAGO or aguardando:
            consultar_antes_de_decidir(pedido.referencia_externa)


def _reembolsar_os_pedidos_pagos(
    rodada: Rodada, autor: Conta
) -> tuple[list[dict[str, Any]], list[int], list[ObrigacaoComComprador]]:
    """Regra 4: o reembolso integral de cada pedido pago da rodada (todas as aberturas), relido
    sob as travas, pelo que ainda não foi devolvido. As contas do livro de todas as obrigações a
    criar são travadas de uma vez antes da primeira (regra única da E09). Devolve os reembolsos
    gerados, os pedidos pagos sem nada restante e as obrigações criadas."""
    pagos = list(
        Pedido.objects.filter(
            abertura__rodada_id=rodada.pk, estado__situacao=SituacaoDePagamento.PAGO
        )
        .select_related("abertura__ciclo", "comprador")
        .order_by("pk")
    )
    por_ciclo: dict[int, tuple[Any, dict[int, Conta]]] = {}
    for pedido in pagos:
        _, compradores = por_ciclo.setdefault(pedido.abertura.ciclo_id, (pedido.abertura.ciclo, {}))
        compradores[pedido.comprador_id] = pedido.comprador
    contas = []
    for ciclo, compradores in por_ciclo.values():
        contas.extend(
            contas_das_obrigacoes(rodada, ciclo, [compradores[pk] for pk in sorted(compradores)])
        )
    travar_contas(*contas)
    reembolsos: list[dict[str, Any]] = []
    sem_reembolso: list[int] = []
    obrigacoes: list[ObrigacaoComComprador] = []
    for pedido in pagos:
        chave = f"cancelamento:{rodada.pk}:{pedido.comprador_id}:{pedido.pk}"
        registrado = reembolso_integral_do_pedido(
            pedido, chave=chave, motivo=MotivoDoReembolso.CANCELAMENTO_DA_RODADA, autor=autor
        )
        if registrado is None:
            sem_reembolso.append(pedido.pk)
            continue
        r = registrado.reembolso
        reembolsos.append(
            {
                "chave": chave,
                "pedido": pedido.pk,
                "comprador": pedido.comprador_id,
                "produtos": str(r.produtos),
                "servico": str(r.servico),
                "frete": str(r.frete),
            }
        )
        if registrado.obrigacao is not None:
            obrigacoes.append(registrado.obrigacao)
    return reembolsos, sem_reembolso, obrigacoes


def _autorizar(obrigacao: ObrigacaoComComprador) -> bool:
    """Autoriza a devolução pelo sistema (a indicação do cancelamento já é a autorização). Falha
    não é relançada: fica no log, e a obrigação espera a tarefa periódica."""
    try:
        autorizar_devolucao(obrigacao, autor=SISTEMA)
    except (ConsultaAoProvedorFalhou, DevolucaoRecusada) as erro:
        logger.warning(
            "Autorização da devolução do cancelamento: obrigação %s, %s: %s",
            obrigacao.pk,
            type(erro).__name__,
            erro,
        )
        return False
    except Exception as erro:
        logger.error(
            "Autorização da devolução do cancelamento: obrigação %s, erro inesperado %s",
            obrigacao.pk,
            type(erro).__name__,
        )
        return False
    return True


def autorizar_devolucoes_do_cancelamento_agora() -> int:
    """Regra 6: autoriza as obrigações do cancelamento sem parcela e sem falta de cobertura. A
    cobertura é escolha do administrador (P-2, P-3) e não é uma nova autorização. Repetir nunca
    cria segunda parcela. Devolve quantas autorizações deram certo."""
    sem_parcela = ObrigacaoComComprador.objects.filter(
        motivo=MotivoDoReembolso.CANCELAMENTO_DA_RODADA
    ).exclude(Exists(ParcelaDeDevolucao.objects.filter(obrigacao=OuterRef("pk"))))
    autorizadas = 0
    for obrigacao in sem_parcela.order_by("pk"):
        if sem_cobertura_da_obrigacao(obrigacao) > 0:
            continue
        autorizadas += _autorizar(obrigacao)
    return autorizadas


def _emitir_o_aviso(
    cancelamento: CancelamentoDaRodada, conta: Conta, *, corpo: str, link: str
) -> None:
    """Um aviso `rodada_cancelada` por cancelamento e comprador (a chave não repete)."""
    fornecedor = cancelamento.rodada.fornecedor.nome
    emitir_evento(
        Evento.RODADA_CANCELADA,
        conta,
        titulo=f"Rodada cancelada: {fornecedor}"[:MAIOR_TITULO],
        corpo=corpo,
        link=link,
        chave=f"rodada_cancelada:{cancelamento.pk}:{conta.pk}",
    )


def _corpo_do_aviso(
    fornecedor: str,
    *,
    com_reembolso: bool,
    mensagem: str,
    devolver: Decimal | None,
    pago: bool,
    cancelado_agora: bool,
    na_fila: bool,
) -> str:
    """O texto para um comprador, só com o que é dele (§2, §6.2): a rodada cancelada, a situação
    dele, a fila e a mensagem do administrador."""
    frases = [f"A rodada de {fornecedor} foi cancelada pelo administrador."]
    if devolver is not None:
        frases.append(
            f"O valor pago ainda não devolvido, {reais(devolver)}, será devolvido integralmente "
            "pela plataforma de pagamentos."
        )
    elif pago and com_reembolso:
        frases.append("As devoluções já devidas do seu pedido continuam em andamento.")
    elif pago:
        frases.append(
            "O cancelamento não inicia novas devoluções. As devoluções já devidas continuam em "
            "andamento."
        )
    else:
        frases.append(
            "Seu pedido foi cancelado e nada foi cobrado."
            if cancelado_agora
            else "Seus interesses nesta rodada foram removidos."
        )
        frases.append(
            "Reembolso integral para quem pagou." if com_reembolso else "Sem novas devoluções."
        )
    if na_fila:
        frases.append(
            "Suas quantidades pendentes continuam na fila do fornecedor para as próximas rodadas."
        )
    if mensagem:
        frases.append(f"Mensagem do administrador: {mensagem}")
    return " ".join(frases)


def _avisar_os_compradores(
    cancelamento: CancelamentoDaRodada,
    pedidos: list[Pedido],
    cancelados: list[dict[str, Any]],
    pagos: list[int],
    parcelas: list[dict[str, Any]],
    reembolsos: list[dict[str, Any]],
    sem_reembolso: list[int],
) -> None:
    """E12-05: o aviso a cada comprador que tem reserva, pedido ou reembolso na rodada. Quem só
    tem pendente na fila do fornecedor não recebe: o cancelamento não muda nada dele."""
    rodada = cancelamento.rodada
    por_comprador: dict[int, Pedido] = {p.comprador_id: p for p in pedidos}
    pagos_ids = set(pagos)
    cancelados_ids = {c["pedido"] for c in cancelados}
    devolver: dict[int, Decimal] = {}
    do_reembolso: dict[int, int] = {}
    for r in reembolsos:
        total = Decimal(r["produtos"]) + Decimal(r["servico"]) + Decimal(r["frete"])
        devolver[r["comprador"]] = devolver.get(r["comprador"], Decimal("0.00")) + total
        do_reembolso.setdefault(r["comprador"], r["pedido"])
    sem_saldo: dict[int, int] = {
        comprador: pedido
        for pedido, comprador in Pedido.objects.filter(pk__in=sem_reembolso).values_list(
            "pk", "comprador_id"
        )
    }
    destinatarios = (
        {p["comprador"] for p in parcelas} | set(por_comprador) | set(devolver) | set(sem_saldo)
    )
    na_fila = set(
        ParcelaDeInteresse.objects.filter(
            produto__fornecedor_id=rodada.fornecedor_id,
            situacao=SituacaoParcela.PENDENTE,
            quantidade_pendente__gt=0,
            comprador_id__in=destinatarios,
        ).values_list("comprador_id", flat=True)
    )
    for conta in Conta.objects.filter(pk__in=destinatarios).order_by("pk"):
        pedido = por_comprador.get(conta.pk)
        pago = (
            (pedido is not None and pedido.pk in pagos_ids)
            or conta.pk in devolver
            or conta.pk in sem_saldo
        )
        link = "/carrinho/"
        if pedido is not None:
            link = f"/pedidos/{pedido.pk}/"
        elif conta.pk in do_reembolso:
            link = f"/pedidos/{do_reembolso[conta.pk]}/"
        elif conta.pk in sem_saldo:
            link = f"/pedidos/{sem_saldo[conta.pk]}/"
        corpo = _corpo_do_aviso(
            rodada.fornecedor.nome,
            com_reembolso=cancelamento.com_reembolso,
            mensagem=cancelamento.mensagem,
            devolver=devolver.get(conta.pk),
            pago=pago,
            cancelado_agora=pedido is not None and pedido.pk in cancelados_ids,
            na_fila=conta.pk in na_fila,
        )
        _emitir_o_aviso(cancelamento, conta, corpo=corpo, link=link)


def _gravar_o_cancelamento(
    autor: Conta,
    rodada: Rodada,
    instante: Any,
    etapa_anterior: str,
    *,
    com_reembolso: bool,
    mensagem: str,
) -> CancelamentoDaRodada:
    return CancelamentoDaRodada.objects.create(
        rodada=rodada,
        autor=autor,
        cancelada_em=instante,
        com_reembolso=com_reembolso,
        mensagem=mensagem,
        etapa_anterior=etapa_anterior,
    )


def cancelar_rodada(
    autor: Conta | None, rodada: Rodada, *, com_reembolso: bool, mensagem: str = ""
) -> CancelamentoDaRodada:
    """Cancela a rodada inteira (E12-01). Só o administrador ativo, fora de transação, com
    `com_reembolso` exatamente `True` ou `False` e a mensagem opcional de até 1000 caracteres.
    Não recebe lista de compradores, motivo nem informação do fornecedor (T-16)."""
    if (
        autor is None
        or getattr(autor, "papel", None) != Papel.ADMINISTRADOR
        or getattr(autor, "situacao", None) != Situacao.ATIVA
    ):
        raise PermissionDenied
    exigir_fora_de_transacao()
    if com_reembolso is not True and com_reembolso is not False:
        raise CancelamentoRecusado("indicacao_obrigatoria")
    mensagem = mensagem.strip()
    if len(mensagem) > MAIOR_MENSAGEM:
        raise CancelamentoRecusado("mensagem_longa")
    atual = Rodada.objects.filter(pk=rodada.pk).first()
    if atual is None:
        raise CancelamentoRecusado("rodada_inexistente")
    _conferir_a_etapa(atual.etapa)
    if com_reembolso:
        _consultar_antes_de_cancelar(atual)
    with transaction.atomic():
        travada = _travar(atual.pk, atual.fornecedor_id, _compradores_envolvidos(atual))
        instante = agora()  # lido depois das travas
        _conferir_a_etapa(travada.etapa)  # relida sob a trava
        etapa_anterior = str(travada.etapa)
        pedidos = _pedidos_da_abertura_vigente(travada)
        cancelados, pagos = _cancelar_os_pedidos_nao_pagos(pedidos, instante)
        parcelas = _remover_os_interesses(travada.fornecedor_id)
        cobrancas = _agendar_o_cancelamento_das_cobrancas(pedidos)
        reembolsos: list[dict[str, Any]] = []
        sem_reembolso: list[int] = []
        obrigacoes: list[ObrigacaoComComprador] = []
        if com_reembolso:
            reembolsos, sem_reembolso, obrigacoes = _reembolsar_os_pedidos_pagos(travada, autor)
        travada.etapa = Etapa.CANCELADA
        travada.save(update_fields=["etapa"])
        cancelamento = _gravar_o_cancelamento(
            autor,
            travada,
            instante,
            etapa_anterior,
            com_reembolso=com_reembolso,
            mensagem=mensagem,
        )
        _avisar_os_compradores(
            cancelamento, pedidos, cancelados, pagos, parcelas, reembolsos, sem_reembolso
        )
        registrar_auditoria(
            autor,
            "rodada.cancelar",
            travada,
            {
                "rodada": travada.pk,
                "etapa_anterior": etapa_anterior,
                "cancelada_em": instante.isoformat(),
                "com_reembolso": com_reembolso,
                "com_mensagem": bool(mensagem),
                "parcelas": parcelas,
                "pedidos_cancelados": cancelados,
                "pedidos_pagos": pagos,
                "cobrancas": cobrancas,
                "reembolsos": reembolsos,
                "pagos_sem_reembolso": sem_reembolso,
            },
        )
    # depois do commit: cada autorização consulta o provedor fora de transação (E10-04)
    for obrigacao in sorted(obrigacoes, key=lambda o: o.pk):
        _autorizar(obrigacao)
    return cancelamento
