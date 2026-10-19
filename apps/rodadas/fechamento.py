"""Início do fechamento e prazo de 24 horas (E06-01).

O início registra as condições do ciclo, confere o mínimo elegível, grava `fechamento` e o prazo
na mesma transação, com as travas de `registrar_condicoes_do_ciclo` (fornecedor, rodada, produtos
e estoques). Toda operação de interesse trava o fornecedor primeiro e a edição de preço trava o
produto, então nada muda entre a conferência do mínimo e a gravação da etapa.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Max
from django.db.transaction import TransactionManagementError

from apps.catalogo.models import Produto
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.interesses.consultas import travar_parcelas
from apps.interesses.fila import alocar_pendentes
from apps.interesses.models import SituacaoParcela
from apps.interesses.progresso import progresso_da_rodada
from apps.interesses.servicos import interesse_do_comprador
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao, prazo_encerrado, somar_horas
from apps.rodadas.avisos import (
    ExcedenteRemovido,
    avisar_excedentes_removidos,
    avisar_fechamento_iniciado,
    avisar_retorno_para_interesse,
    compradores_com_reserva,
)
from apps.rodadas.ciclos import ciclo_vigente, registrar_condicoes_do_ciclo
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.estoque import travar_estoque
from apps.rodadas.models import (
    ETAPAS_ATIVAS,
    Ciclo,
    Etapa,
    OrigemDoPrazo,
    PrazoDoFechamento,
    Rodada,
)

logger = logging.getLogger(__name__)

HORAS_DO_FECHAMENTO = 24

MENSAGENS = {
    "sem_rodada_ativa": "Este fornecedor não tem rodada ativa.",
    "fora_de_interesse": "O fechamento só pode começar com a rodada em interesse.",
    "minimo_nao_atingido": "O fechamento só pode começar com o mínimo elegível atingido.",
    "fora_de_fechamento": "Só um fechamento em andamento pode ser prorrogado.",
    "prazo_encerrado": "O prazo deste fechamento já terminou e não pode mais ser prorrogado.",
    "prazo_nao_posterior": "O novo prazo precisa ser posterior ao prazo atual, {prazo}.",
    "fora_de_fechamento_encerrado": (
        "Só uma rodada com o fechamento encerrado pode voltar para interesse."
    ),
}

MOTIVOS_DE_RETORNO = ("minimo_nao_atingido",)


class TransicaoRecusada(Exception):
    """Mudança de etapa recusada. `codigo` diz o motivo; `mensagem` é a que a tela mostra."""

    def __init__(self, codigo: str, prazo: datetime | None = None) -> None:
        self.codigo = codigo
        self.mensagem = MENSAGENS[codigo]
        if prazo is not None:  # só `prazo_nao_posterior`: mostra o prazo vigente em Brasília
            local = no_fuso_da_operacao(prazo)
            self.mensagem = self.mensagem.format(prazo=f"{local:%d/%m/%Y} às {local:%H:%M}")
        super().__init__(self.mensagem)


def iniciar_fechamento(autor: Conta | None, rodada: Rodada) -> Ciclo:
    """Inicia o fechamento da rodada ativa em `interesse`, com o mínimo elegível atingido."""
    if autor is None or autor.papel != Papel.ADMINISTRADOR:
        raise PermissionDenied
    with transaction.atomic():
        try:
            ciclo = registrar_condicoes_do_ciclo(rodada)
        except CondicoesCongeladas as erro:
            codigo = (
                "sem_rodada_ativa" if erro.codigo == "sem_rodada_ativa" else "fora_de_interesse"
            )
            raise TransicaoRecusada(codigo) from None
        travada = Rodada.objects.select_related("fornecedor").get(pk=ciclo.rodada_id)
        progresso = progresso_da_rodada(travada)
        if not progresso.atingido:
            raise TransicaoRecusada("minimo_nao_atingido")
        travada.etapa = Etapa.FECHAMENTO
        travada.save(update_fields=["etapa"])
        prazo = PrazoDoFechamento.objects.create(
            ciclo=ciclo,
            termina_em=somar_horas(ciclo.iniciado_em, HORAS_DO_FECHAMENTO),
            origem=OrigemDoPrazo.INICIO,
            autor=autor,
        )
        registrar_auditoria(
            autor,
            "rodada.iniciar_fechamento",
            travada,
            {
                "rodada": travada.pk,
                "ciclo": ciclo.pk,
                "termina_em": prazo.termina_em.isoformat(),
                "valor_elegivel": str(progresso.valor_elegivel),
                "minimo": str(progresso.minimo),
            },
        )
        avisar_fechamento_iniciado(travada, ciclo, prazo.termina_em)
    rodada.etapa = Etapa.FECHAMENTO
    return ciclo


def prazo_do_fechamento(rodada: Rodada) -> datetime | None:
    """Maior `termina_em` do ciclo vigente com a rodada em fechamento; `None` nas outras etapas.

    Leitura sem trava, só para telas e tarefas escolherem candidatas: quem decide relê sob trava.
    """
    atual = Rodada.objects.filter(
        pk=rodada.pk, etapa__in=(Etapa.FECHAMENTO, Etapa.FECHAMENTO_ENCERRADO)
    ).first()
    return prazo_do_ciclo(atual) if atual is not None else None


def prazo_do_ciclo(rodada: Rodada) -> datetime | None:
    """Maior `termina_em` do ciclo vigente da rodada, sem consultar a etapa (E06-R01).

    Quem já leu a rodada em `fechamento` encontra o prazo desse ciclo mesmo que a etapa tenha
    mudado depois: as linhas de prazo só recebem inserções. `None` sem ciclo ou sem linha de prazo.
    """
    ciclo = ciclo_vigente(rodada)
    if ciclo is None:
        return None
    instante: datetime | None = ciclo.prazos.aggregate(prazo=Max("termina_em"))["prazo"]
    return instante


def prorrogar_fechamento(autor: Conta | None, rodada: Rodada, novo_termino: datetime) -> datetime:
    """Estende o prazo do fechamento em andamento, antes de ele terminar (E06-04).

    Só estende (o novo prazo é posterior ao vigente), só antes do instante do prazo vigente
    (mesmo que a tarefa de encerramento ainda não tenha rodado) e sem limite de vezes. Cada
    prorrogação é uma linha nova de prazo mais uma auditoria, na mesma transação. O instante
    precisa ter fuso (`InstanteSemFuso`).
    """
    if autor is None or autor.papel != Papel.ADMINISTRADOR:
        raise PermissionDenied
    somar_horas(novo_termino, 0)  # recusa o instante sem fuso antes de qualquer trava
    with transaction.atomic():
        Fornecedor.objects.select_for_update().get(pk=rodada.fornecedor_id)
        ativa = (
            Rodada.objects.select_for_update()
            .filter(fornecedor_id=rodada.fornecedor_id, etapa__in=ETAPAS_ATIVAS)
            .first()
        )
        if ativa is None or ativa.pk != rodada.pk or ativa.etapa != Etapa.FECHAMENTO:
            raise TransicaoRecusada("fora_de_fechamento")
        prazo = prazo_do_fechamento(ativa)
        ciclo = ciclo_vigente(ativa)
        if prazo is None or ciclo is None:
            raise RuntimeError("rodada em fechamento sem prazo gravado")
        if prazo_encerrado(agora(), prazo):  # o instante é lido depois das travas
            raise TransicaoRecusada("prazo_encerrado")
        if novo_termino <= prazo:
            raise TransicaoRecusada("prazo_nao_posterior", prazo)
        PrazoDoFechamento.objects.create(
            ciclo=ciclo, termina_em=novo_termino, origem=OrigemDoPrazo.PRORROGACAO, autor=autor
        )
        registrar_auditoria(
            autor,
            "rodada.prorrogar_fechamento",
            ativa,
            {
                "rodada": ativa.pk,
                "ciclo": ciclo.pk,
                "anterior": prazo.astimezone(UTC).isoformat(),
                "novo": novo_termino.astimezone(UTC).isoformat(),
            },
        )
    return novo_termino


@dataclass(frozen=True)
class ResultadoDoEncerramento:
    rodada: Rodada
    ciclo: Ciclo
    removidas: dict[int, Decimal]
    etapa_final: str


def _divisao_dos_excedentes(rodada: Rodada) -> list[ExcedenteRemovido]:
    """Remove das parcelas `ativa` o que não completa caixa e devolve o que saiu, por parcela.

    Mesma divisão da E05-04: as parcelas entram nas caixas por ordem de `sequencia`, e as últimas
    adições perdem primeiro (§6.3, §5). Produto sem múltiplo não tem excedente. O que sai deixa
    a reserva e não vira pendência; a pendência que a parcela já tinha não muda.
    """
    saidas: list[ExcedenteRemovido] = []
    for estoque in rodada.estoques.order_by("produto_id"):
        travar_estoque(rodada, estoque.produto)
        produto = Produto.objects.get(pk=estoque.produto_id)
        parcelas = travar_parcelas(produto)
        if produto.multiplo is None:
            continue
        ativas = [
            p
            for p in parcelas
            if p.situacao == SituacaoParcela.ATIVA and p.quantidade_reservada > 0
        ]
        total = sum((p.quantidade_reservada for p in ativas), Decimal("0.000"))
        restante = (total // produto.multiplo) * produto.multiplo
        for parcela in ativas:
            em_caixas = min(parcela.quantidade_reservada, restante)
            restante -= em_caixas
            removida = parcela.quantidade_reservada - em_caixas
            if removida == 0:
                continue
            parcela.quantidade_reservada = em_caixas
            if em_caixas == 0:
                sem_pendencia = parcela.quantidade_pendente == 0
                parcela.situacao = (
                    SituacaoParcela.REMOVIDA if sem_pendencia else SituacaoParcela.PENDENTE
                )
            parcela.save(update_fields=["quantidade_reservada", "situacao"])
            saidas.append(
                ExcedenteRemovido(parcela.comprador_id, produto, removida, Decimal("0"), parcela.pk)
            )
    return saidas


def _por_comprador_e_produto(saidas: list[ExcedenteRemovido]) -> list[ExcedenteRemovido]:
    """Uma linha por par (comprador, produto), com a soma removida e o reservado que ficou."""
    somas: dict[tuple[int, int], ExcedenteRemovido] = {}
    for saida in saidas:
        chave = (saida.comprador_id, saida.produto.pk)
        antiga = somas.get(chave)
        if antiga is None:
            mantida = interesse_do_comprador(Conta(pk=saida.comprador_id), saida.produto).reservado
            somas[chave] = ExcedenteRemovido(
                saida.comprador_id, saida.produto, saida.removida, mantida
            )
        else:
            somas[chave] = ExcedenteRemovido(
                antiga.comprador_id,
                antiga.produto,
                antiga.removida + saida.removida,
                antiga.mantida,
            )
    return [somas[chave] for chave in sorted(somas)]


def encerrar_fechamento(rodada: Rodada) -> ResultadoDoEncerramento | None:
    """Encerra o fechamento vencido: grava `fechamento_encerrado`, tira os excedentes e avisa.

    A etapa e o prazo são relidos sob as travas (fornecedor e rodada); sem fechamento vencido,
    não faz nada e devolve `None`. Tudo acontece numa transação: uma falha desfaz o encerramento
    e a próxima execução da tarefa o refaz. Depois de tirar os excedentes, verifica o mínimo com os
    valores que ficaram: não atingido volta a rodada para interesse (E06-06).
    """
    with transaction.atomic():
        Fornecedor.objects.select_for_update().get(pk=rodada.fornecedor_id)
        travada = Rodada.objects.select_for_update().filter(pk=rodada.pk).first()
        if travada is None or travada.etapa != Etapa.FECHAMENTO:
            return None
        prazo = prazo_do_fechamento(travada)
        ciclo = ciclo_vigente(travada)
        if prazo is None or ciclo is None:
            raise RuntimeError("rodada em fechamento sem prazo gravado")
        if not prazo_encerrado(agora(), prazo):  # o instante é lido depois das travas
            return None
        travada.etapa = Etapa.FECHAMENTO_ENCERRADO
        travada.save(update_fields=["etapa"])
        participantes = compradores_com_reserva(travada)  # antes de tirar os excedentes
        saidas = _divisao_dos_excedentes(travada)
        avisar_excedentes_removidos(travada, ciclo, _por_comprador_e_produto(saidas))
        progresso = progresso_da_rodada(
            Rodada.objects.select_related("fornecedor").get(pk=travada.pk)
        )
        if progresso.atingido:
            resultado = "aguardando_pagamento"
        else:
            resultado = "retorno_para_interesse"
            voltar_para_interesse(
                travada, motivo="minimo_nao_atingido", destinatarios=participantes
            )
        registrar_auditoria(
            SISTEMA,
            "rodada.encerrar_fechamento",
            travada,
            {
                "rodada": travada.pk,
                "ciclo": ciclo.pk,
                "prazo": prazo.isoformat(),
                "removidas": [[s.parcela_id, s.produto.pk, str(s.removida)] for s in saidas],
                "valor_elegivel": str(progresso.valor_elegivel),
                "minimo": str(progresso.minimo),
                "resultado": resultado,
            },
        )
        removidas: dict[int, Decimal] = {}
        for saida in saidas:
            anterior = removidas.get(saida.produto.pk, Decimal("0"))
            removidas[saida.produto.pk] = anterior + saida.removida
    etapa_final = (
        Etapa.FECHAMENTO_ENCERRADO if resultado == "aguardando_pagamento" else Etapa.INTERESSE
    )
    rodada.etapa = etapa_final
    return ResultadoDoEncerramento(rodada, ciclo, removidas, etapa_final)


def encerrar_fechamentos_vencidos() -> int:
    """Encerra os fechamentos cujo prazo vigente já chegou. Devolve quantos foram encerrados.

    A busca é sem trava; cada rodada é decidida por `encerrar_fechamento`, que relê etapa e
    prazo sob trava. Uma falha numa rodada vai para o log (id e tipo da exceção, sem dado
    pessoal) e não impede as demais.
    """
    encerradas = 0
    for rodada in Rodada.objects.filter(etapa=Etapa.FECHAMENTO).order_by("fornecedor_id", "pk"):
        prazo = prazo_do_fechamento(rodada)
        if prazo is None or not prazo_encerrado(agora(), prazo):
            continue
        try:
            resultado = encerrar_fechamento(rodada)
        except Exception as erro:
            logger.error(
                "falha ao encerrar o fechamento: rodada=%s erro=%s", rodada.pk, type(erro).__name__
            )
            continue
        if resultado is not None:
            encerradas += 1
    return encerradas


def voltar_para_interesse(
    rodada: Rodada, *, motivo: str, destinatarios: list[Conta] | None = None
) -> None:
    """Devolve à fase de interesse a rodada com o fechamento encerrado (E06-06).

    Não altera o ciclo, o prazo, as condições registradas nem a sequência das parcelas: o ciclo
    é histórico, e o próximo início de fechamento registra outro. Como a fase de interesse
    recomeça e houve estoque liberado, atende a fila de pendentes (E05-02). Avisa os
    `destinatarios` (por padrão, os compradores com reserva na rodada agora). Exige transação.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("voltar_para_interesse exige uma transação aberta.")
    if motivo not in MOTIVOS_DE_RETORNO:
        raise ValueError(f"motivo desconhecido: {motivo!r}")
    Fornecedor.objects.select_for_update().get(pk=rodada.fornecedor_id)
    travada = Rodada.objects.select_for_update().filter(pk=rodada.pk).first()
    if travada is None or travada.etapa != Etapa.FECHAMENTO_ENCERRADO:
        raise TransicaoRecusada("fora_de_fechamento_encerrado")
    ciclo = ciclo_vigente(travada)
    if ciclo is None:
        raise RuntimeError("rodada com fechamento encerrado sem ciclo")
    travada.etapa = Etapa.INTERESSE
    travada.save(update_fields=["etapa"])
    registrar_auditoria(
        SISTEMA,
        "rodada.voltar_para_interesse",
        travada,
        {"rodada": travada.pk, "ciclo": ciclo.pk, "motivo": motivo},
    )
    alocar_pendentes(Fornecedor.objects.get(pk=travada.fornecedor_id))
    contas = compradores_com_reserva(travada) if destinatarios is None else destinatarios
    avisar_retorno_para_interesse(travada, ciclo, contas)
    rodada.etapa = Etapa.INTERESSE
