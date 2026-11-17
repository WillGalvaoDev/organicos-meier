"""O histórico de ações relevantes (E15-06): a consulta, só de leitura, às `EntradaAuditoria`.

Mostra todas as entradas, da mais nova para a mais antiga, com o código da ação gravado (sem
tradução). A auditoria não copia dados pessoais: o nome do autor vem da conta atual e, se a conta
não existir, fica só o id. Filtro inválido é ignorado e avisado; nada é gravado, nem auditoria de
leitura.
"""

import json
import re
from datetime import UTC, date, datetime, timedelta
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


_FORMA_DO_AUTOR = re.compile(r"[1-9][0-9]{0,17}")  # cabe sempre no pk (BigAutoField)
_FORMA_DA_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # só dígitos ASCII


def _dia(texto: str) -> date | None:
    """`aaaa-mm-dd` exato, dígitos ASCII e data que existe; outra forma é inválida."""
    if _FORMA_DA_DATA.fullmatch(texto) is None:
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _instante(dia: date, *, fim: bool) -> datetime | None:
    """O começo do dia em Brasília, ou o começo do dia seguinte (limite superior exclusivo).
    Instante que não existe (depois de 9999-12-31) ou que sai do intervalo em UTC: `None`, e o
    limite não é aplicado."""
    try:
        base = dia + timedelta(days=1) if fim else dia
        instante = datetime.combine(base, datetime.min.time(), tzinfo=FUSO_DA_OPERACAO)
        instante.astimezone(UTC)
    except OverflowError:
        return None
    return instante


def _filtrar(
    entradas: QuerySet[EntradaAuditoria], parametros: Any, acoes: list[str]
) -> tuple[QuerySet[EntradaAuditoria], dict[str, str], list[str]]:
    """Aplica os filtros válidos. Devolve a consulta, os filtros aplicados e os nomes dos inválidos
    (ignorados)."""
    aplicados: dict[str, str] = {}
    invalidos: list[str] = []
    acao = parametros.get("acao", "")
    if acao:
        if acao in acoes:  # igualdade em memória: nada recebido vai ao banco antes de validado
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
            _FORMA_DO_AUTOR.fullmatch(autor)
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
        aplicados["de"] = de
        if (inicio := _instante(dia_de, fim=False)) is not None:
            entradas = entradas.filter(momento__gte=inicio)
    if dia_ate:
        aplicados["ate"] = ate
        if (limite := _instante(dia_ate, fim=True)) is not None:
            entradas = entradas.filter(momento__lt=limite)
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
    acoes = list(
        EntradaAuditoria.objects.order_by("acao").values_list("acao", flat=True).distinct()
    )
    entradas, aplicados, invalidos = _filtrar(
        EntradaAuditoria.objects.order_by("-momento", "-pk"), parametros, acoes
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
        "acoes": acoes,
        "administradores": list(Conta.objects.filter(papel=Papel.ADMINISTRADOR).order_by("nome")),
    }
