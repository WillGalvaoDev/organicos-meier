"""O alerta `tarefa_atrasada` (E15-02): uma ocorrência por tarefa com estado `atrasada`."""

from datetime import datetime
from typing import Any

from django.urls import reverse

from apps.financeiro.models import Gravidade, TipoDeAlerta
from apps.operacao.execucao import ATRASADA, situacao_das_tarefas
from apps.operacao.models import ExecucaoDaTarefa
from apps.operacao.tipos import Classificacao, Natureza, data_e_hora, registrar_tipo
from apps.operacao.verificacao import registrar_verificacao

TIPO = TipoDeAlerta.TAREFA_ATRASADA.value


def _corpo(dados: dict[str, Any]) -> str:
    sem_conclusao = ExecucaoDaTarefa.objects.filter(
        nome=dados["tarefa"], ultima_conclusao_em__isnull=True
    ).exists()
    desde = data_e_hora(dados["referencia"])
    inicio = (
        f"A tarefa {dados['descricao']} não tem execução concluída desde {desde}."
        if sem_conclusao
        else f"A tarefa {dados['descricao']} não conclui desde {desde}."
    )
    return f"{inicio} Ela deveria rodar a cada {dados['intervalo_minutos']} minuto(s)."


def _verificar(instante: datetime) -> dict[str, dict[str, Any]]:
    atrasadas: dict[str, dict[str, Any]] = {}
    for situacao in situacao_das_tarefas(instante):
        if situacao.estado != ATRASADA or situacao.atrasada_desde is None:
            continue
        referencia = situacao.ultima_conclusao_em or situacao.monitorada_desde
        if referencia is None:
            continue
        atrasadas[situacao.nome] = {
            "tarefa": situacao.nome,
            "descricao": situacao.descricao,
            "referencia": referencia.isoformat(),
            "atrasada_desde": situacao.atrasada_desde.isoformat(),
            "intervalo_minutos": int(situacao.intervalo.total_seconds() // 60),
        }
    return atrasadas


registrar_tipo(
    TIPO,
    Classificacao(
        gravidade=Gravidade.AVISO,
        natureza=Natureza.CONDICAO,
        titulo="Tarefa atrasada",
        corpo=_corpo,
        link=lambda dados: reverse("painel_administracao"),
    ),
)
registrar_verificacao(TIPO, _verificar)
