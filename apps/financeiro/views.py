"""Telas financeiras do administrador (E09-08).

Só o administrador. As ações que movem dinheiro ou escolhem uma origem exigem passkey recente
(`exige_reautenticacao_por_passkey`). Nenhuma view escreve no livro-razão sem passar pelos
serviços das fatias anteriores; cada recusa de serviço vira uma mensagem no formulário, sem
escrita. Valores sempre em `Decimal`, exibidos com o filtro `reais`.
"""

from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.catalogo.templatetags.catalogo import reais
from apps.contas.administracao import exige_reautenticacao_por_passkey, somente_administrador
from apps.contas.models import Conta
from apps.financeiro import reserva as servico_da_reserva
from apps.financeiro.alertas import alertas_abertos
from apps.financeiro.apuracao import cobrir_despesa as cobrir_a_despesa
from apps.financeiro.apuracao import frete_do_ciclo
from apps.financeiro.liquidez import (
    LiquidezInsuficiente,
    SaidaRepetida,
    liquidez,
    registrar_saida,
)
from apps.financeiro.livro import MovimentoInvalido, SaldoInsuficiente, conta, saldo
from apps.financeiro.models import (
    ApuracaoNoLivro,
    ConciliacaoDiaria,
    ContaFinanceira,
    DesignacaoDaReserva,
    Despesa,
    Destinacao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeAlerta,
    TipoDeMovimento,
    TransferenciaFinanceira,
)
from apps.financeiro.obrigacoes import cobrir_obrigacao_com_receita
from apps.financeiro.reserva import (
    AporteRepetido,
    CoberturaExcedente,
    DesignacaoEncerrada,
    InvarianteViolado,
    ReservaInsuficiente,
    consumido_da_designacao,
    itens_sem_cobertura,
    pendente_da_despesa,
    registrar_aporte,
    sem_cobertura_da_obrigacao,
    situacao_da_reserva,
)
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.nucleo.valores import ValorInvalido, ler_decimal_digitado
from apps.rodadas.models import Rodada

ZERO = Decimal("0.00")
POR_PAGINA = 50
MENSAGEM_DO_VALOR = (
    "Informe um valor em reais maior que zero, com até duas casas decimais (por exemplo, 1000,00)."
)
RECUSAS_DE_CAMPO = {
    "valor": MENSAGEM_DO_VALOR,
    "identificacao": "Informe a identificação do movimento no provedor (até 64 caracteres).",
    "justificativa": "Informe a justificativa.",
}


def _administrador(request: HttpRequest) -> Conta:
    autor: Conta = request.user  # type: ignore[assignment]
    return autor


def _valor_digitado(texto: str) -> Decimal | None:
    try:
        valor = ler_decimal_digitado(texto, 2)
    except ValorInvalido:
        return None
    return valor if valor > 0 else None


def _instante(instante: Any) -> str:
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}" if instante else ""


def _nome_da_conta(c: ContaFinanceira | None) -> str:
    return "exterior" if c is None else f"{c.get_destinacao_display()} {c.chave}"


# --- o resumo -----------------------------------------------------------------------------------


def _contexto_do_resumo() -> dict[str, Any]:
    fornecedores = [
        {"conta": c, "saldo": saldo(c), "liquidez": liquidez(c)}
        for c in ContaFinanceira.objects.filter(
            destinacao=Destinacao.OBRIGACAO_FORNECEDOR
        ).select_related("fornecedor", "rodada")
    ]
    receitas = [
        {"conta": c, "saldo": saldo(c), "liquidez": liquidez(c)}
        for c in ContaFinanceira.objects.filter(
            destinacao=Destinacao.RECEITA_SERVICO
        ).select_related("rodada__fornecedor")
    ]
    custodias: dict[tuple[int, int], dict[str, Any]] = {}
    for c in ContaFinanceira.objects.filter(destinacao=Destinacao.CUSTODIA).select_related(
        "rodada__fornecedor", "ciclo"
    ):
        chave = (c.rodada_id or 0, c.ciclo_id or 0)
        linha = custodias.setdefault(chave, {"conta": c, "saldo": ZERO})
        linha["saldo"] += saldo(c)
    fretes = [
        {"apuracao": a, "relatorio": frete_do_ciclo(a.ciclo)}
        for a in ApuracaoNoLivro.objects.select_related("ciclo__rodada__fornecedor").order_by("pk")
    ]
    obrigacoes = []
    for o in ObrigacaoComComprador.objects.select_related("comprador", "rodada").order_by("pk"):
        destino = ContaFinanceira.objects.filter(
            destinacao=Destinacao.OBRIGACAO_COMPRADOR, chave=f"o{o.pk}"
        ).first()
        financiado = (
            sum((t.valor for t in TransferenciaFinanceira.objects.filter(para=destino)), ZERO)
            if destino
            else ZERO
        )
        liquidado = (
            sum(
                (
                    t.valor
                    for t in TransferenciaFinanceira.objects.filter(de=destino, para__isnull=True)
                ),
                ZERO,
            )
            if destino
            else ZERO
        )
        designado = sum(
            (
                d.valor - consumido_da_designacao(d)
                for d in DesignacaoDaReserva.objects.filter(obrigacao=o, desfeita__isnull=True)
            ),
            ZERO,
        )
        obrigacoes.append(
            {
                "obrigacao": o,
                "financiado": financiado,
                "designado": designado,
                "liquidado": liquidado,
                "sem_cobertura": sem_cobertura_da_obrigacao(o),
            }
        )
    pendencias = []
    for item in itens_sem_cobertura():
        if item.tipo == "obrigacao":
            pendencias.append(
                {"item": item, "obrigacao": ObrigacaoComComprador.objects.get(pk=item.objeto_id)}
            )
        else:
            pendencias.append({"item": item, "despesa": Despesa.objects.get(pk=item.objeto_id)})
    designacoes = [
        {"designacao": d, "restante": d.valor - consumido_da_designacao(d)}
        for d in DesignacaoDaReserva.objects.filter(desfeita__isnull=True).order_by("pk")
        if d.valor - consumido_da_designacao(d) > 0
    ]
    return {
        "alertas": alertas_abertos(),
        "fornecedores": fornecedores,
        "receitas": receitas,
        "custodias": list(custodias.values()),
        "fretes": fretes,
        "obrigacoes": obrigacoes,
        "a_cobrir": saldo(conta(Destinacao.DESPESAS_A_COBRIR)),
        "reserva": situacao_da_reserva(),
        "aviso_da_reserva": _aviso_da_reserva(),
        "pendencias": pendencias,
        "designacoes": designacoes,
        "rodadas_com_receita": [r["conta"].rodada for r in receitas if r["saldo"] > 0],
        "conciliacao": ConciliacaoDiaria.objects.order_by("-data").first(),
    }


def _aviso_da_reserva() -> str | None:
    aberto = [a for a in alertas_abertos(TipoDeAlerta.RESERVA_INSUFICIENTE)]
    if not aberto:
        return None
    dados = aberto[0].dados
    return (
        "Reserva insuficiente: obrigações sem cobertura de "
        f"{reais(Decimal(str(dados.get('sem_cobertura', '0'))))} para um saldo livre de "
        f"{reais(Decimal(str(dados.get('livre', '0'))))}."
    )


def _resumo(request: HttpRequest, erro: str | None = None, status: int = 200) -> HttpResponse:
    contexto = _contexto_do_resumo()
    contexto["erro"] = erro
    return render(request, "financeiro/resumo.html", contexto, status=status)


@somente_administrador
@require_GET
def resumo(request: HttpRequest) -> HttpResponse:
    return _resumo(request)


# --- movimentos ---------------------------------------------------------------------------------


@somente_administrador
@require_GET
def movimentos(request: HttpRequest) -> HttpResponse:
    consulta = MovimentoFinanceiro.objects.order_by("-pk")
    destinacao = request.GET.get("destinacao", "")
    rodada = request.GET.get("rodada", "")
    if destinacao and destinacao in Destinacao.values:
        condicao = Q(transferencias__de__destinacao=destinacao) | Q(
            transferencias__para__destinacao=destinacao
        )
        if rodada.isdigit():
            condicao = Q(
                transferencias__de__destinacao=destinacao, transferencias__de__rodada_id=rodada
            ) | Q(
                transferencias__para__destinacao=destinacao, transferencias__para__rodada_id=rodada
            )
        consulta = consulta.filter(condicao).distinct()
    pagina = Paginator(consulta, POR_PAGINA).get_page(request.GET.get("pagina"))
    autores = {
        str(c.pk): c.nome
        for c in Conta.objects.filter(
            pk__in=[int(m.autor_id) for m in pagina if m.autor_id and m.autor_id.isdigit()]
        )
    }
    linhas = []
    for m in pagina:
        transferencias = list(m.transferencias.select_related("de", "para").order_by("pk"))
        linhas.append(
            {
                "movimento": m,
                "tipo": TipoDeMovimento(m.tipo).label,
                "momento": _instante(m.momento),
                "autor": "Sistema"
                if m.autor_id is None
                else autores.get(m.autor_id, "Conta removida"),
                "transferencias": [
                    {"de": _nome_da_conta(t.de), "para": _nome_da_conta(t.para), "valor": t.valor}
                    for t in transferencias
                ],
            }
        )
    contexto = {
        "linhas": linhas,
        "pagina": pagina,
        "destinacoes": Destinacao.choices,
        "destinacao": destinacao,
        "rodada": rodada,
    }
    return render(request, "financeiro/movimentos.html", contexto)


# --- reserva ------------------------------------------------------------------------------------


@somente_administrador
@require_GET
def reserva(request: HttpRequest) -> HttpResponse:
    return _pagina_da_reserva(request)


def _pagina_da_reserva(
    request: HttpRequest, erro: str | None = None, status: int = 200
) -> HttpResponse:
    autores = {str(c.pk): c.nome for c in Conta.objects.filter(papel="administrador")}
    aportes = [
        {
            "movimento": m,
            "momento": _instante(m.momento),
            "identificacao": m.chave.split(":", 1)[1],
            "valor": sum((t.valor for t in m.transferencias.all()), ZERO),
            "autor": autores.get(m.autor_id or "", "Sistema"),
        }
        for m in MovimentoFinanceiro.objects.filter(tipo=TipoDeMovimento.APORTE).order_by("-pk")
    ]
    utilizacoes = [
        {
            "movimento": m,
            "momento": _instante(m.momento),
            "valor": sum((t.valor for t in m.transferencias.all()), ZERO),
            "autor": autores.get(m.autor_id or "", "Sistema"),
        }
        for m in MovimentoFinanceiro.objects.filter(
            tipo=TipoDeMovimento.COBERTURA_DE_DESPESA,
            transferencias__de__destinacao=Destinacao.RESERVA,
        )
        .distinct()
        .order_by("-pk")
    ]
    designacoes = []
    for d in DesignacaoDaReserva.objects.select_related("obrigacao").order_by("-pk"):
        desfeita = getattr(d, "desfeita", None)
        consumido = consumido_da_designacao(d)
        situacao = "Desfeita" if desfeita else ("Consumida" if consumido >= d.valor else "Ativa")
        designacoes.append(
            {
                "designacao": d,
                "momento": _instante(d.criada_em),
                "situacao": situacao,
                "autor": autores.get(d.autor_id, "Conta removida"),
                "desfeita": desfeita,
                "ativa": situacao == "Ativa",
            }
        )
    contexto = {
        "aportes": aportes,
        "utilizacoes": utilizacoes,
        "designacoes": designacoes,
        "reserva": situacao_da_reserva(),
        "aviso_da_reserva": _aviso_da_reserva(),
        "erro": erro,
    }
    return render(request, "financeiro/reserva.html", contexto, status=status)


def _recusa_de_servico(erro: Exception) -> tuple[str, int]:
    if isinstance(erro, MovimentoInvalido):
        return RECUSAS_DE_CAMPO.get(erro.codigo, "O movimento é inválido."), 400
    if isinstance(erro, AporteRepetido):
        return "Este depósito já foi registrado como aporte.", 409
    if isinstance(erro, SaidaRepetida):
        return "Esta saída já foi registrada.", 409
    if isinstance(erro, DesignacaoEncerrada):
        return "Esta designação já foi desfeita ou consumida.", 409
    if isinstance(erro, ReservaInsuficiente):
        livre = situacao_da_reserva().livre
        return f"O valor passa do saldo livre da reserva ({reais(livre)}).", 409
    if isinstance(erro, InvarianteViolado):
        return (
            "O saldo do provedor está abaixo das obrigações: a reserva e as retiradas de receita "
            "estão bloqueadas.",
            409,
        )
    if isinstance(erro, SaldoInsuficiente):
        return "O saldo da conta de origem não cobre o valor.", 409
    return "Não foi possível registrar a operação.", 409


@exige_reautenticacao_por_passkey
@require_http_methods(["GET", "POST"])
def aporte(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return render(request, "financeiro/aporte.html", {"reserva": situacao_da_reserva()})
    valor = _valor_digitado(request.POST.get("valor", ""))
    identificacao = request.POST.get("identificacao", "").strip()
    justificativa = request.POST.get("justificativa", "").strip()
    erro: str | None = None
    if valor is None:
        erro = MENSAGEM_DO_VALOR
    elif not identificacao:
        erro = "Informe a identificação do depósito no provedor."
    elif not justificativa:
        erro = "Informe a justificativa."
    if erro is None and valor is not None:
        try:
            with transaction.atomic():
                registrar_aporte(_administrador(request), valor, identificacao, justificativa)
        except (MovimentoInvalido, AporteRepetido) as recusa:
            erro, status = _recusa_de_servico(recusa)
            return _formulario(request, "financeiro/aporte.html", erro, status, request.POST)
        messages.success(request, f"Aporte de {reais(valor)} registrado.")
        return redirect("financeiro_reserva")
    return _formulario(request, "financeiro/aporte.html", erro or "", 400, request.POST)


def _formulario(
    request: HttpRequest, modelo: str, erro: str, status: int, dados: Any, extra: Any = None
) -> HttpResponse:
    contexto = {"erro": erro, "dados": dados, "reserva": situacao_da_reserva(), **(extra or {})}
    return render(request, modelo, contexto, status=status)


# --- designar, desfazer e cobrir ----------------------------------------------------------------


def _valor_e_justificativa(request: HttpRequest) -> tuple[Decimal | None, str, str | None]:
    valor = _valor_digitado(request.POST.get("valor", ""))
    justificativa = request.POST.get("justificativa", "").strip()
    if valor is None:
        return None, justificativa, MENSAGEM_DO_VALOR
    if not justificativa:
        return valor, justificativa, "Informe a justificativa."
    return valor, justificativa, None


@exige_reautenticacao_por_passkey
@require_POST
def designar(request: HttpRequest, pk: int) -> HttpResponse:
    obrigacao = get_object_or_404(ObrigacaoComComprador, pk=pk)
    valor, justificativa, erro = _valor_e_justificativa(request)
    if erro is not None or valor is None:
        return _resumo(request, erro, 400)
    try:
        with transaction.atomic():
            servico_da_reserva.designar_reserva(
                _administrador(request), obrigacao, valor, justificativa
            )
    except CoberturaExcedente:
        falta = reais(sem_cobertura_da_obrigacao(obrigacao))
        return _resumo(request, f"O valor passa do que falta cobrir na obrigação ({falta}).", 409)
    except (ReservaInsuficiente, InvarianteViolado, MovimentoInvalido) as recusa:
        mensagem, status = _recusa_de_servico(recusa)
        return _resumo(request, mensagem, status)
    messages.success(request, f"Designação de {reais(valor)} registrada.")
    return redirect("financeiro_reserva")


@exige_reautenticacao_por_passkey
@require_POST
def desfazer_designacao(request: HttpRequest, pk: int) -> HttpResponse:
    designacao = get_object_or_404(DesignacaoDaReserva, pk=pk)
    justificativa = request.POST.get("justificativa", "").strip()
    if not justificativa:
        return _pagina_da_reserva(request, "Informe a justificativa.", 400)
    try:
        with transaction.atomic():
            servico_da_reserva.desfazer_designacao(
                _administrador(request), designacao, justificativa
            )
    except (DesignacaoEncerrada, MovimentoInvalido) as recusa:
        mensagem, status = _recusa_de_servico(recusa)
        return _pagina_da_reserva(request, mensagem, status)
    messages.success(request, "Designação desfeita.")
    return redirect("financeiro_reserva")


@exige_reautenticacao_por_passkey
@require_POST
def cobrir_obrigacao(request: HttpRequest, pk: int) -> HttpResponse:
    obrigacao = get_object_or_404(ObrigacaoComComprador, pk=pk)
    fonte = _rodada_da_receita(request.POST.get("rodada", ""))
    valor, justificativa, erro = _valor_e_justificativa(request)
    if erro is not None or valor is None:
        return _resumo(request, erro, 400)
    try:
        with transaction.atomic():
            cobrir_obrigacao_com_receita(
                _administrador(request), obrigacao, fonte, valor, justificativa
            )
    except CoberturaExcedente:
        falta = reais(sem_cobertura_da_obrigacao(obrigacao))
        return _resumo(request, f"O valor passa do que falta cobrir na obrigação ({falta}).", 409)
    except (SaldoInsuficiente, MovimentoInvalido) as recusa:
        mensagem, status = _recusa_de_servico(recusa)
        return _resumo(request, mensagem, status)
    messages.success(request, f"Cobertura de {reais(valor)} registrada.")
    return redirect("financeiro_resumo")


def _rodada_da_receita(texto: str) -> Rodada:
    if not texto.isdigit():
        raise Http404
    return get_object_or_404(Rodada, pk=int(texto))


@exige_reautenticacao_por_passkey
@require_POST
def cobrir_despesa(request: HttpRequest, pk: int) -> HttpResponse:
    despesa = get_object_or_404(Despesa, pk=pk)
    texto = request.POST.get("fonte", "")
    fonte: Any
    if texto == "reserva":
        fonte = "reserva"
    elif texto.startswith("receita:"):
        fonte = ("receita", _rodada_da_receita(texto.split(":", 1)[1]))
    else:
        return _resumo(request, "Escolha a fonte da cobertura.", 400)
    valor, justificativa, erro = _valor_e_justificativa(request)
    if erro is not None or valor is None:
        return _resumo(request, erro, 400)
    try:
        with transaction.atomic():
            cobrir_a_despesa(
                _administrador(request),
                despesa,
                fonte=fonte,
                valor=valor,
                justificativa=justificativa,
            )
    except CoberturaExcedente:
        falta = reais(pendente_da_despesa(despesa))
        return _resumo(request, f"O valor passa do que falta cobrir na despesa ({falta}).", 409)
    except (ReservaInsuficiente, InvarianteViolado, SaldoInsuficiente, MovimentoInvalido) as recusa:
        mensagem, status = _recusa_de_servico(recusa)
        return _resumo(request, mensagem, status)
    messages.success(request, f"Cobertura de {reais(valor)} registrada.")
    return redirect("financeiro_resumo")


# --- retirada da receita ------------------------------------------------------------------------


def _rodadas_da_retirada() -> list[dict[str, Any]]:
    return [
        {"rodada": c.rodada, "saldo": saldo(c), "liquidez": liquidez(c)}
        for c in ContaFinanceira.objects.filter(destinacao=Destinacao.RECEITA_SERVICO)
        .select_related("rodada__fornecedor")
        .order_by("pk")
    ]


@exige_reautenticacao_por_passkey
@require_http_methods(["GET", "POST"])
def retirada(request: HttpRequest) -> HttpResponse:
    rodadas = {"rodadas": _rodadas_da_retirada()}
    if request.method == "GET":
        return render(request, "financeiro/retirada.html", rodadas)
    rodada = _rodada_da_receita(request.POST.get("rodada", ""))
    valor = _valor_digitado(request.POST.get("valor", ""))
    identificacao = request.POST.get("identificacao", "").strip()
    justificativa = request.POST.get("justificativa", "").strip()
    if valor is None:
        return _formulario(
            request, "financeiro/retirada.html", MENSAGEM_DO_VALOR, 400, request.POST, rodadas
        )
    if not identificacao:
        erro = "Informe a identificação da saída no provedor."
        return _formulario(request, "financeiro/retirada.html", erro, 400, request.POST, rodadas)
    if not justificativa:
        erro = "Informe a justificativa."
        return _formulario(request, "financeiro/retirada.html", erro, 400, request.POST, rodadas)
    receita = conta(Destinacao.RECEITA_SERVICO, rodada=rodada.pk)
    try:
        with transaction.atomic():
            registrar_saida(
                _administrador(request),
                tipo="retirada_de_receita",
                conta=receita,
                valor=valor,
                identificacao=identificacao,
                justificativa=justificativa,
            )
    except LiquidezInsuficiente:
        liberado = reais(liquidez(receita).liberado)
        erro = f"Só {liberado} da receita desta rodada estão liberados no provedor."
        return _formulario(request, "financeiro/retirada.html", erro, 409, request.POST, rodadas)
    except (SaidaRepetida, InvarianteViolado, SaldoInsuficiente, MovimentoInvalido) as recusa:
        erro, status = _recusa_de_servico(recusa)
        return _formulario(request, "financeiro/retirada.html", erro, status, request.POST, rodadas)
    messages.success(request, f"Retirada de {reais(valor)} registrada.")
    return redirect("financeiro_resumo")


# --- conciliações -------------------------------------------------------------------------------


@somente_administrador
@require_GET
def conciliacoes(request: HttpRequest) -> HttpResponse:
    pagina = Paginator(ConciliacaoDiaria.objects.order_by("-data"), POR_PAGINA).get_page(
        request.GET.get("pagina")
    )
    return render(request, "financeiro/conciliacoes.html", {"pagina": pagina})
