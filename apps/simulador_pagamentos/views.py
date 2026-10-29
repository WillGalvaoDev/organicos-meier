"""Tela do simulador de pagamentos (E08-07): quem faz o papel de quem paga o Pix.

Só o administrador, e só com o simulador configurado (`PROVEDOR_PAGAMENTOS`); sem ele, as rotas
respondem 404. A tela usa os mesmos controles dos testes (`controle.py`) e aprova com o instante
atual. O plano de falhas e os controles só de teste não aparecem aqui.
"""

from collections.abc import Callable
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo.templatetags.catalogo import reais
from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.nucleo.valores import ValorInvalido, ler_decimal_digitado
from apps.pagamentos.provedor import PagamentoNaoEncontrado, SituacaoNoProvedor
from apps.simulador_pagamentos import controle, estado
from apps.simulador_pagamentos.models import CobrancaSimulada

NOME_DO_PROVEDOR = "simulador"
SITUACOES_POR_EXTENSO = {
    SituacaoNoProvedor.PENDENTE: "Pendente",
    SituacaoNoProvedor.APROVADO: "Aprovada",
    SituacaoNoProvedor.RECUSADO: "Recusada",
    SituacaoNoProvedor.CANCELADO: "Cancelada",
    SituacaoNoProvedor.EXPIRADO: "Expirada",
}
ACOES: dict[str, tuple[Callable[[str], None], str]] = {
    "aprovar": (controle.aprovar, "aprovada"),
    "recusar": (controle.recusar, "recusada"),
    "expirar": (controle.expirar, "expirada"),
}


def _exigir_simulador() -> None:
    if settings.PROVEDOR_PAGAMENTOS != NOME_DO_PROVEDOR:
        raise Http404


def _instante(instante: object) -> str:
    if instante is None:
        return ""
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}"  # type: ignore[arg-type]


def _pagina(request: HttpRequest, erro: str | None = None, status: int = 200) -> HttpResponse:
    cobrancas = []
    for cobranca in CobrancaSimulada.objects.order_by("-pk"):
        situacao = SituacaoNoProvedor(cobranca.situacao)
        cobrancas.append(
            {
                "cobranca": cobranca,
                "situacao": SITUACOES_POR_EXTENSO[situacao],
                "criada_em": _instante(cobranca.criado_em),
                "vence_em": _instante(cobranca.expira_em),
                "aprovada_em": _instante(cobranca.aprovado_em),
                "pode_aprovar": situacao
                in (
                    SituacaoNoProvedor.PENDENTE,
                    SituacaoNoProvedor.CANCELADO,
                    SituacaoNoProvedor.EXPIRADO,
                ),
                "pode_encerrar": situacao == SituacaoNoProvedor.PENDENTE,
            }
        )
    contexto = {
        "cobrancas": cobrancas,
        "avisos_pendentes": len(controle.avisos_pendentes()),
        "erro": erro,
    }
    return render(request, "simulador_pagamentos/lista.html", contexto, status=status)


@somente_administrador
@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    _exigir_simulador()
    return _pagina(request)


def _agir(request: HttpRequest, id_externo: str, acao: str) -> HttpResponse:
    _exigir_simulador()
    controlar, participio = ACOES[acao]
    try:
        cobranca = estado.obter(id_externo)
        controlar(id_externo)
    except PagamentoNaoEncontrado:
        raise Http404 from None
    except ValueError:
        mensagem = f"A cobrança {id_externo} não pode ser {participio} na situação atual."
        return _pagina(request, mensagem, status=409)
    autor: Conta = request.user  # type: ignore[assignment]
    registrar_auditoria(autor, f"simulador.{acao}", cobranca, {"id_externo": id_externo})
    messages.success(request, f"Cobrança {id_externo} {participio}.")
    return redirect("simulador_pagamentos_lista")


@somente_administrador
@require_POST
def aprovar(request: HttpRequest, id_externo: str) -> HttpResponse:
    return _agir(request, id_externo, "aprovar")


@somente_administrador
@require_POST
def recusar(request: HttpRequest, id_externo: str) -> HttpResponse:
    return _agir(request, id_externo, "recusar")


@somente_administrador
@require_POST
def expirar(request: HttpRequest, id_externo: str) -> HttpResponse:
    return _agir(request, id_externo, "expirar")


MENSAGEM_DO_VALOR = (
    "Informe um valor em reais maior que zero, com até duas casas decimais (por exemplo, 1000,00)."
)


def _valor_digitado(texto: str) -> Decimal | None:
    try:
        valor = ler_decimal_digitado(texto, 2)
    except ValorInvalido:
        return None
    return valor if valor > 0 else None


@somente_administrador
@require_POST
def depositar(request: HttpRequest) -> HttpResponse:
    _exigir_simulador()
    valor = _valor_digitado(request.POST.get("valor", ""))
    if valor is None:
        return _pagina(request, MENSAGEM_DO_VALOR, status=400)
    controle.depositar(valor)
    autor: Conta = request.user  # type: ignore[assignment]
    registrar_auditoria(autor, "simulador.depositar", autor, {"valor": str(valor)})
    messages.success(request, f"Depósito de {reais(valor)} registrado.")
    return redirect("simulador_pagamentos_lista")


@somente_administrador
@require_POST
def saida(request: HttpRequest) -> HttpResponse:
    _exigir_simulador()
    valor = _valor_digitado(request.POST.get("valor", ""))
    if valor is None:
        return _pagina(request, MENSAGEM_DO_VALOR, status=400)
    descricao = request.POST.get("descricao", "").strip()
    if not descricao:
        return _pagina(request, "Informe a descrição da saída.", status=400)
    controle.registrar_saida(valor, descricao=descricao)
    autor: Conta = request.user  # type: ignore[assignment]
    registrar_auditoria(autor, "simulador.registrar_saida", autor, {"valor": str(valor)})
    messages.success(request, f"Saída de {reais(valor)} registrada.")
    return redirect("simulador_pagamentos_lista")


@somente_administrador
@require_POST
def entregar(request: HttpRequest) -> HttpResponse:
    _exigir_simulador()
    entregues = len(controle.entregar_avisos())
    autor: Conta = request.user  # type: ignore[assignment]
    registrar_auditoria(autor, "simulador.entregar_avisos", autor, {"avisos": entregues})
    messages.success(request, f"{entregues} aviso(s) entregue(s).")
    return redirect("simulador_pagamentos_lista")
