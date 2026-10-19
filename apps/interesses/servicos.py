"""Serviços de interesse do comprador (E05-01).

Cada operação roda numa única transação e adquire as travas na ordem global: conta do comprador,
fornecedor, rodada, produto, estoque e parcelas (por sequência). A trava do fornecedor, adquirida
por todas as operações de interesse, é o que as serializa; a das parcelas é a segunda defesa.
Uma recusa desfaz a transação inteira e não grava nada, nem auditoria.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q, Sum
from django.db.transaction import TransactionManagementError

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.quantidades import formatar_quantidade, validar_quantidade
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.interesses.consultas import SITUACOES_QUE_RESERVAM, travar_parcelas
from apps.interesses.fila import _alocar_produto
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora
from apps.nucleo.valores import ValorInvalido
from apps.nucleo.valores import quantidade as converter_quantidade
from apps.rodadas.condicoes import aceita_interesses, travar_rodada_para_interesses
from apps.rodadas.estoque import calcular_livre, travar_estoque
from apps.rodadas.models import ETAPAS_ATIVAS, EstoqueDaRodada, Rodada

_ZERO = Decimal("0.000")


class InteresseRecusado(Exception):
    """Base das recusas de interesse; `mensagem` é a que a tela mostra."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class InteresseDesatualizado(InteresseRecusado):
    def __init__(self) -> None:
        super().__init__(
            "Seu interesse neste produto mudou. Confira os valores atuais e envie de novo."
        )


class ProdutoForaDaRodada(InteresseRecusado):
    def __init__(self) -> None:
        super().__init__("Este produto não está disponível para interesse agora.")


class EstoqueInsuficiente(InteresseRecusado):
    def __init__(self, disponivel: Decimal, unidade: str) -> None:
        if disponivel == 0:
            mensagem = "Este produto está esgotado nesta rodada."
        else:
            rotulo = Unidade(unidade).label
            mensagem = f"Há apenas {formatar_quantidade(disponivel)} {rotulo} disponível."
        super().__init__(mensagem)
        self.disponivel = disponivel


class ReducaoAcimaDoReservado(InteresseRecusado):
    def __init__(self, reservado: Decimal) -> None:
        super().__init__(
            f"A redução passa da quantidade reservada ({formatar_quantidade(reservado)})."
        )
        self.reservado = reservado


@dataclass(frozen=True)
class ResumoDoInteresse:
    """Soma das parcelas do comprador no produto: `reservado` (ativas) e `pendente` (fila)."""

    reservado: Decimal
    pendente: Decimal


@dataclass
class _Travado:
    """Estado depois de todas as travas; `parcelas` são as do produto, por sequência."""

    comprador: Conta
    rodada: Rodada
    produto: Produto
    estoque: EstoqueDaRodada
    parcelas: list[ParcelaDeInteresse]

    def reservado(self) -> Decimal:
        total = sum(
            (p.quantidade_reservada for p in self.parcelas if p.situacao in SITUACOES_QUE_RESERVAM),
            _ZERO,
        )
        return total.quantize(_ZERO)

    def do_comprador(self) -> list[ParcelaDeInteresse]:
        return [p for p in self.parcelas if p.comprador_id == self.comprador.pk]


def _travar_conta(comprador: Conta) -> Conta:
    # FOR NO KEY UPDATE: não bloqueia o FOR KEY SHARE que a conferência das chaves estrangeiras
    # para a conta (notificações, auditoria) pede ao confirmar; continua serializando as
    # operações do comprador e a moderação entre si (E05-R03).
    travada = Conta.objects.select_for_update(no_key=True).get(pk=comprador.pk)
    if not travada.pode_adicionar_interesse:
        raise PermissionDenied
    return travada


def _travar(comprador: Conta, produto: Produto) -> _Travado:
    """Passos 1 a 3 e 5 comuns: conta, rodada, produto e estoque, parcelas."""
    conta = _travar_conta(comprador)
    rodada = travar_rodada_para_interesses(Fornecedor(pk=produto.fornecedor_id))
    try:
        estoque = travar_estoque(rodada, produto)
    except EstoqueDaRodada.DoesNotExist:
        raise ProdutoForaDaRodada from None
    atual = Produto.objects.get(pk=produto.pk)  # relido já travado: incremento vigente
    return _Travado(conta, rodada, atual, estoque, travar_parcelas(atual))


def _validar_total(produto: Produto, entrada: Any) -> Decimal:
    """Como `validar_quantidade`, mas aceita zero (remover tudo)."""
    try:
        if converter_quantidade(entrada) == 0:
            return _ZERO
    except ValorInvalido:
        pass  # a validação padrão recusa com a mensagem de quantidade
    return validar_quantidade(produto, entrada)


def _atender_a_fila(t: _Travado) -> None:
    """Atende os pendentes do produto e recarrega as parcelas travadas (E05-02)."""
    _alocar_produto(t.rodada, t.produto)
    t.parcelas = travar_parcelas(t.produto)


def _acrescentar(t: _Travado, quantidade: Decimal) -> None:
    livre = calcular_livre(t.estoque.limite, t.reservado())
    if livre is not None and quantidade > livre:
        raise EstoqueInsuficiente(livre, t.produto.unidade)
    parcela = ParcelaDeInteresse.objects.create(
        comprador=t.comprador,
        produto=t.produto,
        quantidade_original=quantidade,
        quantidade_reservada=quantidade,
        quantidade_pendente=_ZERO,
        situacao=SituacaoParcela.ATIVA,
    )
    registrar_auditoria(
        t.comprador,
        "interesse.adicionar",
        parcela,
        {
            "parcela": parcela.pk,
            "produto": t.produto.pk,
            "rodada": t.rodada.pk,
            "quantidade": str(quantidade),
        },
    )


def _reservado_do_comprador(t: _Travado) -> Decimal:
    return sum(
        (p.quantidade_reservada for p in t.do_comprador() if p.situacao == SituacaoParcela.ATIVA),
        _ZERO,
    ).quantize(_ZERO)


def _diminuir(t: _Travado, quantidade: Decimal) -> None:
    reservado = _reservado_do_comprador(t)
    if quantidade > reservado:
        raise ReducaoAcimaDoReservado(reservado)
    restante = quantidade
    tocadas: list[int] = []
    candidatas = [
        p
        for p in t.do_comprador()
        if p.situacao == SituacaoParcela.ATIVA and p.quantidade_reservada > 0
    ]
    for parcela in sorted(candidatas, key=lambda p: p.sequencia, reverse=True):
        if restante <= 0:
            break
        tirada = min(parcela.quantidade_reservada, restante)
        parcela.quantidade_reservada -= tirada
        if parcela.quantidade_reservada == 0:
            sem_pendencia = parcela.quantidade_pendente == 0
            parcela.situacao = (
                SituacaoParcela.REMOVIDA if sem_pendencia else SituacaoParcela.PENDENTE
            )
        parcela.save(update_fields=["quantidade_reservada", "situacao"])
        restante -= tirada
        tocadas.append(parcela.pk)
    registrar_auditoria(
        t.comprador,
        "interesse.reduzir",
        t.produto,
        {
            "produto": t.produto.pk,
            "rodada": t.rodada.pk,
            "quantidade": str(quantidade),
            "parcelas": tocadas,
        },
    )


def adicionar_interesse(comprador: Conta, produto: Produto, quantidade: Any) -> ResumoDoInteresse:
    with transaction.atomic():
        t = _travar(comprador, produto)
        valor = validar_quantidade(t.produto, quantidade)
        _atender_a_fila(t)
        _acrescentar(t, valor)
        return interesse_do_comprador(t.comprador, t.produto)


def reduzir_interesse(comprador: Conta, produto: Produto, quantidade: Any) -> ResumoDoInteresse:
    with transaction.atomic():
        t = _travar(comprador, produto)
        valor = validar_quantidade(t.produto, quantidade)
        _diminuir(t, valor)
        _atender_a_fila(t)
        return interesse_do_comprador(t.comprador, t.produto)


def _resumo_das(parcelas: list[ParcelaDeInteresse]) -> ResumoDoInteresse:
    """Reservado (parcelas `ativa`) e pendente (`ativa` e `pendente`) de uma lista travada."""
    reservado = sum(
        (p.quantidade_reservada for p in parcelas if p.situacao == SituacaoParcela.ATIVA), _ZERO
    )
    pendente = sum(
        (
            p.quantidade_pendente
            for p in parcelas
            if p.situacao in (SituacaoParcela.ATIVA, SituacaoParcela.PENDENTE)
        ),
        _ZERO,
    )
    return ResumoDoInteresse(reservado.quantize(_ZERO), pendente.quantize(_ZERO))


def _exigir_estado(esperado: ResumoDoInteresse | None, atual: ResumoDoInteresse) -> None:
    """Recusa o envio feito sobre um estado que já mudou (E05-R02). Sem `esperado`, não confere."""
    if esperado is None:
        return
    esperado_exato = ResumoDoInteresse(
        esperado.reservado.quantize(_ZERO), esperado.pendente.quantize(_ZERO)
    )
    if esperado_exato != atual:
        raise InteresseDesatualizado


def _tirar_pendencias(
    conta: Conta, produto: Produto, parcelas: list[ParcelaDeInteresse], quantidade: Decimal
) -> None:
    """Reduz a pendência das parcelas mais recentes primeiro e audita (E05-03)."""
    na_fila = [
        p for p in parcelas if p.situacao in (SituacaoParcela.ATIVA, SituacaoParcela.PENDENTE)
    ]
    restante = quantidade
    tocadas: list[int] = []
    for parcela in sorted(na_fila, key=lambda p: p.sequencia, reverse=True):
        if restante <= 0:
            break
        tirada = min(parcela.quantidade_pendente, restante)
        if tirada <= 0:
            continue
        parcela.quantidade_pendente -= tirada
        if parcela.quantidade_reservada == 0 and parcela.quantidade_pendente == 0:
            parcela.situacao = SituacaoParcela.REMOVIDA
        parcela.save(update_fields=["quantidade_pendente", "situacao"])
        restante -= tirada
        tocadas.append(parcela.pk)
    registrar_auditoria(
        conta,
        "interesse.remover_pendente",
        produto,
        {"produto": produto.pk, "quantidade": str(quantidade), "parcelas": tocadas},
    )


def definir_interesse(
    comprador: Conta,
    produto: Produto,
    total: Any,
    *,
    esperado: ResumoDoInteresse | None = None,
) -> ResumoDoInteresse:
    """Leva o reservado do comprador ao total desejado; zero remove o item inteiro (E05-R02).

    Com `esperado` (o resumo que a página mostrou) diferente do estado travado, recusa sem gravar.
    Se o pedido já está cumprido, devolve o estado atual sem gravar nem auditar, mesmo com
    `esperado` diferente. A fila é atendida pela FIFO, inclusive as pendências do próprio
    comprador, então o resumo final pode diferir do total.
    """
    with transaction.atomic():
        t = _travar(comprador, produto)
        desejado = _validar_total(t.produto, total)
        atual = _resumo_das(t.do_comprador())
        if desejado > 0 and atual.reservado == desejado:
            return atual
        if desejado == 0 and atual == ResumoDoInteresse(_ZERO, _ZERO):
            return atual
        _exigir_estado(esperado, atual)
        if desejado == 0:
            if atual.pendente > 0:
                _tirar_pendencias(t.comprador, t.produto, t.do_comprador(), atual.pendente)
            if atual.reservado > 0:
                _diminuir(t, atual.reservado)
            _atender_a_fila(t)
        elif desejado > atual.reservado:
            _atender_a_fila(t)
            reservado = _reservado_do_comprador(t)
            if desejado > reservado:
                _acrescentar(t, desejado - reservado)
        else:
            _diminuir(t, atual.reservado - desejado)
            _atender_a_fila(t)
        return interesse_do_comprador(t.comprador, t.produto)


def interesse_do_comprador(comprador: Conta, produto: Produto) -> ResumoDoInteresse:
    soma = ParcelaDeInteresse.objects.filter(
        comprador_id=comprador.pk, produto_id=produto.pk
    ).aggregate(
        reservado=Sum("quantidade_reservada", filter=Q(situacao=SituacaoParcela.ATIVA)),
        pendente=Sum(
            "quantidade_pendente",
            filter=Q(situacao__in=(SituacaoParcela.ATIVA, SituacaoParcela.PENDENTE)),
        ),
    )
    return ResumoDoInteresse(
        reservado=(soma["reservado"] or _ZERO).quantize(_ZERO),
        pendente=(soma["pendente"] or _ZERO).quantize(_ZERO),
    )


class RemocaoAcimaDoPendente(InteresseRecusado):
    def __init__(self, pendente: Decimal) -> None:
        super().__init__(
            f"A remoção passa da quantidade pendente ({formatar_quantidade(pendente)})."
        )
        self.pendente = pendente


def remover_pendente(
    comprador: Conta,
    produto: Produto,
    quantidade: Any,
    *,
    esperado: ResumoDoInteresse | None = None,
) -> ResumoDoInteresse:
    """Reduz só a quantidade pendente do comprador, em qualquer etapa (E05-03).

    Trava, nesta ordem, a conta, o fornecedor, o produto e as parcelas. Não usa a rodada nem o
    estoque, porque pendentes não fazem parte de nenhum ciclo, e não chama a fila: remover
    pendente não libera estoque.
    """
    with transaction.atomic():
        conta = _travar_conta(comprador)
        Fornecedor.objects.select_for_update().get(pk=produto.fornecedor_id)
        atual = Produto.objects.select_for_update().get(pk=produto.pk)
        valor = validar_quantidade(atual, quantidade)
        parcelas = [p for p in travar_parcelas(atual) if p.comprador_id == conta.pk]
        estado = _resumo_das(parcelas)
        _exigir_estado(esperado, estado)
        if valor > estado.pendente:
            raise RemocaoAcimaDoPendente(estado.pendente)
        _tirar_pendencias(conta, atual, parcelas, valor)
        return interesse_do_comprador(conta, atual)


MOTIVOS_DE_REMOCAO = {
    "suspensao": "interesse.remover_por_suspensao",
    "remocao_da_conta": "interesse.remover_por_remocao_da_conta",
}


def remover_interesses_do_comprador(conta: Conta, *, motivo: str) -> int:
    """Remove as parcelas `ativa` e `pendente` do comprador e atende a fila onde couber (E05-07).

    Chamada dentro da transação de `suspender` ou `remover`, com a conta já travada. Não depende
    da etapa: as travas seguem a ordem global (fornecedores por id; em cada um, a rodada ativa, os
    produtos por id, o estoque e as parcelas). A fila só é atendida quando a rodada aceita
    reservas. Parcelas `em_pedido` não mudam. Devolve quantas parcelas foram removidas.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("remover_interesses_do_comprador exige uma transação.")
    if motivo not in MOTIVOS_DE_REMOCAO:
        raise ValueError(f"motivo desconhecido: {motivo!r}")
    if conta.papel != Papel.COMPRADOR:
        return 0
    na_fila = (SituacaoParcela.ATIVA, SituacaoParcela.PENDENTE)
    produtos = list(
        Produto.objects.filter(parcelas__comprador_id=conta.pk, parcelas__situacao__in=na_fila)
        .distinct()
        .order_by("pk")
    )
    if not produtos:
        return 0
    por_fornecedor: dict[int, list[Produto]] = {}
    for produto in produtos:
        por_fornecedor.setdefault(produto.fornecedor_id, []).append(produto)
    removidas: list[list[Any]] = []
    for fornecedor_id in sorted(por_fornecedor):
        Fornecedor.objects.select_for_update().get(pk=fornecedor_id)
        rodada = (
            Rodada.objects.select_for_update()
            .filter(fornecedor_id=fornecedor_id, etapa__in=ETAPAS_ATIVAS)
            .first()
        )
        for produto in por_fornecedor[fornecedor_id]:
            Produto.objects.select_for_update().get(pk=produto.pk)
            tem_estoque = (
                rodada is not None
                and EstoqueDaRodada.objects.select_for_update()
                .filter(rodada_id=rodada.pk, produto_id=produto.pk)
                .exists()
            )
            liberou = False
            for parcela in travar_parcelas(produto):
                if parcela.comprador_id != conta.pk or parcela.situacao not in na_fila:
                    continue
                removidas.append(
                    [
                        parcela.pk,
                        str(parcela.quantidade_reservada),
                        str(parcela.quantidade_pendente),
                    ]
                )
                liberou = liberou or parcela.quantidade_reservada > 0
                parcela.quantidade_reservada = _ZERO
                parcela.quantidade_pendente = _ZERO
                parcela.situacao = SituacaoParcela.REMOVIDA
                parcela.save(
                    update_fields=["quantidade_reservada", "quantidade_pendente", "situacao"]
                )
            aceita = rodada is not None and aceita_interesses(rodada, agora())
            if liberou and tem_estoque and aceita and rodada is not None:
                _alocar_produto(rodada, produto)
    if removidas:
        registrar_auditoria(
            SISTEMA,
            MOTIVOS_DE_REMOCAO[motivo],
            conta,
            {"conta": conta.pk, "parcelas": removidas},
        )
    return len(removidas)
