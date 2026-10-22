# E09-03 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:** um administrador com passkey e um comprador.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 3.6 | positivo | nenhum alerta | `abrir_alerta("reserva_insuficiente", "geral", {"sem_cobertura": "50.00", "livre": "20.00"})` numa transação | um alerta aberto, com gravidade `aviso`; uma notificação `alerta_financeiro` para o administrador no site e um envio de e-mail na fila; nenhuma para o comprador; um log `warning` |
| A-2 | Decisão técnica | positivo | o A-1 aberto | `abrir_alerta` com o mesmo tipo e a mesma chave, com outros dados | devolve o mesmo alerta, com os dados originais; nenhuma notificação nova |
| A-3 | Decisão técnica | positivo | o A-1 aberto | `resolver_alerta("reserva_insuficiente", "geral", motivo="cobertura")`; depois `abrir_alerta` igual ao do A-1 | o primeiro fica com `resolvido_em` e o motivo; o segundo cria um alerta novo e uma notificação nova; os dois ficam no histórico |
| A-4 | Decisão técnica | negativo | nenhum alerta | `resolver_alerta` de um par sem alerta aberto | devolve `None`; nada é gravado |
| A-5 | Infra 3.4 | positivo | nenhum alerta | `abrir_alerta("invariante_violado", "geral", {"diferenca": "-10.00"})` | gravidade `critico`; título "Alerta crítico: saldo do provedor abaixo das obrigações"; corpo com "R$ 10,00" e a frase do bloqueio; log `error` |
| A-6 | Decisão técnica | negativo | o arranjo | tipo desconhecido; chave vazia; chave com 65 caracteres; dados com a chave `token` | `ValueError` nos quatro; nada é gravado |
| A-7 | §12 | negativo | o e-mail falhando (E04-03) | abrir um alerta e processar os envios | o alerta continua aberto, a notificação do site existe e o envio fica com falha registrada |
| A-8 | Decisão técnica | positivo | um `reserva_insuficiente` e um `divergencia_na_conciliacao` abertos, nessa ordem, e um `invariante_violado` aberto depois deles | `alertas_abertos()` | o crítico vem primeiro; depois os outros em ordem de abertura |
| A-9 | Decisão técnica | negativo | uma transação que abre um alerta | a transação é desfeita | nenhum alerta e nenhuma notificação |
| A-10 | Decisão técnica | concorrência | nenhum alerta | duas transações em paralelo abrem o mesmo `(tipo, chave)` | um alerta e uma notificação; as duas devolvem o mesmo `pk` |
| A-11 | E04-01 | positivo | o catálogo | `CANAIS_POR_EVENTO` e `DESTINATARIO_POR_EVENTO` de `alerta_financeiro` | site e e-mail; papel administrador; os outros eventos sem mudança |
| A-12 | Decisão técnica | positivo | nenhum administrador cadastrado | `abrir_alerta` | o alerta é gravado, sem notificação; um log com o motivo |

## Mapeamento para testes

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-9, A-11 e A-12 | `tests/tecnicos/test_financeiro_alertas.py` |
| A-10 | `tests/tecnicos/test_financeiro_concorrencia.py` |
