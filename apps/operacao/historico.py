"""O histórico de ações relevantes (E15-06): a consulta, só de leitura, às `EntradaAuditoria`.

Mostra todas as entradas, da mais nova para a mais antiga, com o código da ação gravado (sem
tradução). A auditoria não copia dados pessoais: o nome do autor vem da conta atual e, se a conta
não existir, fica só o id. Filtro inválido é ignorado e avisado; nada é gravado, nem auditoria de
leitura.
"""

import json
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import QuerySet

from apps.contas.models import Conta, Papel
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import FUSO_DA_OPERACAO, no_fuso_da_operacao

POR_PAGINA = 50
SISTEMA = "sistema"
FILTROS = ("acao", "autor", "de", "ate")


def _dia(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto) if len(texto) == 10 else None
    except ValueError:
        return None


def _inicio_do_dia(dia: date) -> datetime:
    return datetime.combine(dia, datetime.min.time(), tzinfo=FUSO_DA_OPERACAO)


def _filtrar(
    entradas: QuerySet[EntradaAuditoria], parametros: Any
) -> tuple[QuerySet[EntradaAuditoria], dict[str, str], list[str]]:
    """Aplica os filtros válidos. Devolve a consulta, os filtros aplicados e os nomes dos inválidos
    (ignorados)."""
    aplicados: dict[str, str] = {}
    invalidos: list[str] = []
    acao = parametros.get("acao", "")
    if acao:
        if EntradaAuditoria.objects.filter(acao=acao).exists():
            entradas = entradas.filter(acao=acao)
            aplicados["acao"] = acao
        else:
            invalidos.append("acao")
    autor = parametros.get("autor", "")
    if autor:
        if autor == SISTEMA:
            entradas = entradas.filter(autor_tipo=EntradaAuditoria.AutorTipo.SISTEMA)
            aplicados["autor"] = autor
        elif (
            autor.isdigit()
            and Conta.objects.filter(pk=int(autor), papel=Papel.ADMINISTRADOR).exists()
        ):
            entradas = entradas.filter(
                autor_tipo=EntradaAuditoria.AutorTipo.USUARIO, autor_id=str(int(autor))
            )
            aplicados["autor"] = autor
        else:
            invalidos.append("autor")
    de, ate = parametros.get("de", ""), parametros.get("ate", "")
    dia_de = _dia(de) if de else None
    dia_ate = _dia(ate) if ate else None
    if de and dia_de is None:
        invalidos.append("de")
    if ate and dia_ate is None:
        invalidos.append("ate")
    if dia_de and dia_ate and dia_de > dia_ate:
        invalidos.append("de")  # o intervalo ao contrário vale como inválido: ambos são ignorados
        dia_de = dia_ate = None
    if dia_de:
        entradas = entradas.filter(momento__gte=_inicio_do_dia(dia_de))
        aplicados["de"] = de
    if dia_ate:
        entradas = entradas.filter(momento__lt=_inicio_do_dia(dia_ate + timedelta(days=1)))
        aplicados["ate"] = ate
    return entradas, aplicados, invalidos


def _autores(entradas: list[EntradaAuditoria]) -> dict[str, str]:
    ids = {
        int(e.autor_id)
        for e in entradas
        if e.autor_tipo == EntradaAuditoria.AutorTipo.USUARIO
        and e.autor_id
        and e.autor_id.isdigit()
    }
    return {str(c.pk): c.nome for c in Conta.objects.filter(pk__in=ids)}


def _autor(entrada: EntradaAuditoria, nomes: dict[str, str]) -> str:
    if entrada.autor_tipo == EntradaAuditoria.AutorTipo.SISTEMA:
        return "Sistema"
    return nomes.get(entrada.autor_id or "", f"Conta {entrada.autor_id}")


def _alteracoes(entrada: EntradaAuditoria) -> list[str]:
    alteracoes = entrada.alteracoes

    def compacto(valor: Any) -> str:
        return json.dumps(valor, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))

    if not isinstance(alteracoes, dict):
        return [compacto(alteracoes)]
    return [f"{chave}: {compacto(valor)}" for chave, valor in alteracoes.items()]


def contexto_do_historico(parametros: Any) -> dict[str, Any]:
    entradas, aplicados, invalidos = _filtrar(
        EntradaAuditoria.objects.order_by("-momento", "-pk"), parametros
    )
    pagina = Paginator(entradas, POR_PAGINA).get_page(parametros.get("pagina"))
    nomes = _autores(list(pagina.object_list))
    linhas = [
        {
            "quando": f"{no_fuso_da_operacao(e.momento):%d/%m/%Y %H:%M:%S}",
            "autor": _autor(e, nomes),
            "acao": e.acao,
            "objeto": f"{e.objeto_tipo} {e.objeto_id}",
            "motivo": e.motivo or "—",
            "alteracoes": _alteracoes(e),
        }
        for e in pagina.object_list
    ]
    return {
        "linhas": linhas,
        "pagina": pagina,
        "invalidos": invalidos,
        "filtros": aplicados,
        "consulta": urlencode(aplicados),
        "acoes": list(
            EntradaAuditoria.objects.order_by("acao").values_list("acao", flat=True).distinct()
        ),
        "administradores": list(Conta.objects.filter(papel=Papel.ADMINISTRADOR).order_by("nome")),
    }
