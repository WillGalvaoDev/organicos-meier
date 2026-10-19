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
from apps.interesses.progresso import progresso_da_rodada
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import somar_horas
from apps.rodadas.ciclos import ciclo_vigente, registrar_condicoes_do_ciclo
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.models import Ciclo, Etapa, OrigemDoPrazo, PrazoDoFechamento, Rodada

HORAS_DO_FECHAMENTO = 24

MENSAGENS = {
    "sem_rodada_ativa": "Este fornecedor não tem rodada ativa.",
    "fora_de_interesse": "O fechamento só pode começar com a rodada em interesse.",
    "minimo_nao_atingido": "O fechamento só pode começar com o mínimo elegível atingido.",
}


class TransicaoRecusada(Exception):
    """Mudança de etapa recusada. `codigo` diz o motivo; `mensagem` é a que a tela mostra."""

    def __init__(self, codigo: str) -> None:
        self.codigo = codigo
        self.mensagem = MENSAGENS[codigo]
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
