"""Linha do tempo da cobrança (E08-05), contada a partir de `T0` e nunca gravada à parte.

- `T0 + 24h`: fim do prazo de pagamento; novas tentativas são recusadas e as pendentes canceladas.
- `T0 + 24h` a `T0 + 48h`: margem; só se confirmam e se conciliam os pagamentos já iniciados.
- `T0 + 48h`: a apuração pode começar, mas só com a autorização do administrador (E11).

Como `AberturaDoPagamento` só aceita inserção e nenhuma rota muda `T0`, nenhum prazo pode ser
alterado nem prorrogado. A rodada continua em `pagamento` o tempo todo: a margem e a "apuração
possível" são situações de tempo, calculadas aqui.
"""

from datetime import datetime

from apps.nucleo.tempo import ate_o_limite, prazo_encerrado, somar_horas
from apps.pedidos.models import AberturaDoPagamento

HORAS_DO_PRAZO_DE_PAGAMENTO = 24
HORAS_DA_MARGEM = 48


def prazo_de_pagamento(abertura: AberturaDoPagamento) -> datetime:
    """`T0 + 24h`."""
    return somar_horas(abertura.t0, HORAS_DO_PRAZO_DE_PAGAMENTO)


def fim_da_margem(abertura: AberturaDoPagamento) -> datetime:
    """`T0 + 48h`."""
    return somar_horas(abertura.t0, HORAS_DA_MARGEM)


def aceita_tentativas(abertura: AberturaDoPagamento, instante: datetime) -> bool:
    """Antes de `T0 + 24h` (o próprio instante já é bloqueado)."""
    return not prazo_encerrado(instante, prazo_de_pagamento(abertura))


def em_margem(abertura: AberturaDoPagamento, instante: datetime) -> bool:
    """De `T0 + 24h` a `T0 + 48h`, com os dois extremos incluídos."""
    return not aceita_tentativas(abertura, instante) and ate_o_limite(
        instante, fim_da_margem(abertura)
    )


def pode_iniciar_apuracao(abertura: AberturaDoPagamento, instante: datetime) -> bool:
    """A partir de `T0 + 48h`. Responde só ao tempo: a autorização do administrador e a
    recusa no servidor quando isto devolve falso são da apuração (E11)."""
    return prazo_encerrado(instante, fim_da_margem(abertura))
