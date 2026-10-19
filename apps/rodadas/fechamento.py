"""Início do fechamento e prazo de 24 horas (E06-01).

O início registra as condições do ciclo, confere o mínimo elegível, grava `fechamento` e o prazo
na mesma transação, com as travas de `registrar_condicoes_do_ciclo` (fornecedor, rodada, produtos
e estoques). Toda operação de interesse trava o fornecedor primeiro e a edição de preço trava o
produto, então nada muda entre a conferência do mínimo e a gravação da etapa.
"""

from datetime import datetime

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max

from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.interesses.progresso import progresso_da_rodada
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao, prazo_encerrado, somar_horas
from apps.rodadas.avisos import avisar_fechamento_iniciado
from apps.rodadas.ciclos import ciclo_vigente, registrar_condicoes_do_ciclo
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.models import (
    ETAPAS_ATIVAS,
    Ciclo,
    Etapa,
    OrigemDoPrazo,
    PrazoDoFechamento,
    Rodada,
)

HORAS_DO_FECHAMENTO = 24

MENSAGENS = {
    "sem_rodada_ativa": "Este fornecedor não tem rodada ativa.",
    "fora_de_interesse": "O fechamento só pode começar com a rodada em interesse.",
    "minimo_nao_atingido": "O fechamento só pode começar com o mínimo elegível atingido.",
    "fora_de_fechamento": "Só um fechamento em andamento pode ser prorrogado.",
    "prazo_encerrado": "O prazo deste fechamento já terminou e não pode mais ser prorrogado.",
    "prazo_nao_posterior": "O novo prazo precisa ser posterior ao prazo atual, {prazo}.",
}


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
    ciclo = ciclo_vigente(atual) if atual is not None else None
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
                "anterior": prazo.isoformat(),
                "novo": novo_termino.isoformat(),
            },
        )
    return novo_termino
