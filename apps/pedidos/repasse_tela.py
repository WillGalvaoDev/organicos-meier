"""O que a tela das saídas da rodada mostra (E13-06): a obrigação com o fornecedor, o frete e os
históricos de repasses e pagamentos do frete. Tudo vem do livro-razão."""

from typing import Any

from apps.contas.models import Conta
from apps.financeiro.apuracao import frete_do_ciclo
from apps.financeiro.liquidez import liquidez
from apps.financeiro.livro import conta, saldo
from apps.financeiro.models import (
    ApuracaoNoLivro,
    Destinacao,
    TipoDeMovimento,
    TransferenciaFinanceira,
)
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.rodadas.models import Rodada


def rodada_tem_apuracao_no_livro(rodada: Rodada) -> bool:
    return ApuracaoNoLivro.objects.filter(ciclo__rodada=rodada).exists()


def _historico(origem: Any, tipo: TipoDeMovimento) -> list[dict[str, Any]]:
    saidas = (
        TransferenciaFinanceira.objects.filter(de=origem, movimento__tipo=tipo)
        .select_related("movimento")
        .order_by("-movimento__pk")
    )
    autores = {
        str(c.pk): c.nome
        for c in Conta.objects.filter(
            pk__in=[int(s.movimento.autor_id) for s in saidas if s.movimento.autor_id]
        )
    }
    return [
        {
            "momento": f"{no_fuso_da_operacao(s.movimento.momento):%d/%m/%Y %H:%M}",
            "valor": s.valor,
            "identificacao": s.movimento.chave.removeprefix("saida:"),
            "justificativa": s.movimento.justificativa,
            "autor": autores.get(s.movimento.autor_id or "", ""),
        }
        for s in saidas
    ]


def pagina_das_saidas(rodada: Rodada) -> dict[str, Any]:
    """O contexto da página: dois blocos, o repasse e o frete."""
    obrigacao = conta(
        Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=rodada.fornecedor_id, rodada=rodada.pk
    )
    frete = conta(Destinacao.FRETE, rodada=rodada.pk)
    apuracao = ApuracaoNoLivro.objects.filter(ciclo__rodada=rodada).order_by("pk").first()
    if apuracao is None:
        raise ValueError("a rodada não tem apuração no livro")
    return {
        "rodada": rodada,
        "fornecedor": rodada.fornecedor,
        "obrigacao": {
            "saldo": saldo(obrigacao),
            "liquidez": liquidez(obrigacao),
            "historico": _historico(obrigacao, TipoDeMovimento.REPASSE),
        },
        "frete": {
            "relatorio": frete_do_ciclo(apuracao.ciclo),
            "saldo": saldo(frete),
            "liquidez": liquidez(frete),
            "historico": _historico(frete, TipoDeMovimento.PAGAMENTO_DO_FRETE),
        },
    }
