# E09-04 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:**

- O pedido X do comprador B, aberto como na E08 (`tests/apoio/pedidos.py`), com produtos R$ 100,00, serviço R$ 5,00 e frete R$ 20,00, total R$ 125,00, na rodada `r` e no ciclo `c`.
- A tarifa do simulador para Pix em 1% e a liberação em 24h.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 3.2, Herdado E08 | positivo | uma tentativa criada de X | aprovar às `T0 + 1h` e sincronizar | destino `quita`; um movimento `entrada_de_pagamento` com a chave `entrada:<destino>`; custódias de B em `r`/`c`: produtos 100,00, serviço 5,00 e frete 20,00; nenhuma conta de fornecedor ou de receita tocada |
| A-2 | §16 nº 30, Infra 3.2 | positivo | o A-1 | o mesmo | uma `Despesa` `tarifa` de 1,25 com a rodada `r`; um movimento `tarifa` F4; `despesas_a_cobrir` em −1,25; as custódias continuam 100,00/5,00/20,00; `Pedido` e itens iguais |
| A-3 | §16 nº 39 | positivo | duas tentativas de X aprovadas às `T0 + 1h` e `T0 + 2h` | sincronizar as duas | um destino `quita` e um `devolucao`/`duplicidade`; uma entrada na custódia (125,00) e uma `ObrigacaoComComprador` com `integral = 125.00`, motivo `duplicidade` e saldo financiado de 125,00 em `obrigacao_comprador`; um alerta `duplicidade` aberto; duas despesas de tarifa |
| A-4 | P-6, §8.3 | positivo | uma tentativa de X criada antes de `T0 + 24h` e aprovada às `T0 + 48h + 1s` | sincronizar | destino `devolucao`/`aprovado_apos_a_margem`; obrigação de 125,00 financiada pelo pagamento; alerta `aprovado_apos_a_margem` com a chave `id_externo`; nada na custódia |
| A-5 | Herdado E08 | positivo | um pagamento aprovado com referência desconhecida (destino `sem_pedido`) | sincronizar | obrigação com comprador, rodada e pedido nulos e `integral` igual ao valor; movimento F2; nenhum alerta de duplicidade ou margem; a despesa de tarifa com rodada nula |
| A-6 | E08-04 | positivo | os motivos `iniciado_fora_do_prazo`, `pedido_cancelado` e `valor_divergente`, um caso parametrizado cada | sincronizar | obrigação de devolução com o motivo do destino e o valor do pagamento, financiada por F2; nenhum alerta |
| A-7 | Idempotência | positivo | o A-1 registrado | `registrar_entrada(destino)` e `registrar_tarifa(pagamento)` chamados de novo; e a reconsulta da margem do pedido | nenhum movimento, obrigação ou despesa nova |
| A-8 | Tarifa depois | positivo | um pagamento aprovado e sincronizado sem tarifa (resposta montada sem `tarifa`, como na E09-02 A-10); depois uma consulta que traz a tarifa 1,25 | `registrar_tarifas_pendentes_agora()` | depois da primeira sincronização, nenhuma despesa; depois da segunda e da tarefa, uma despesa e um movimento `tarifa`; a tarefa devolve 1; rodar de novo devolve 0 |
| A-9 | Decisão técnica | negativo | tarifa zero no simulador | aprovar e sincronizar | nenhuma despesa e nenhum movimento `tarifa` |
| A-10 | E07-03 | negativo | um receptor de teste que levanta exceção depois do receptor financeiro (só uma vez) | aprovar e sincronizar; depois sincronizar de novo | na primeira, nada fica: nem destino, nem entrada, nem obrigação, nem despesa, nem alerta; na segunda, tudo uma vez só |
| A-11 | §16 nº 39 | concorrência | duas tentativas de X aprovadas no simulador | as duas sincronizações em paralelo | em qualquer ordem: uma entrada na custódia de 125,00, uma obrigação de 125,00 e as somas das custódias de X iguais ao total; sem `deadlock` |
| A-12 | Idempotência | concorrência | uma tentativa aprovada | sincronização por aviso e reconsulta da margem do mesmo pagamento em paralelo | uma entrada e uma despesa |
| A-13 | Decisão técnica | positivo | um pedido aberto com frete `F = 0` e um com produtos de R$ 0,01 (serviço arredondado a 0,00) | aprovar, sincronizar cada um | a soma das transferências de entrada é o `valor` do pagamento; nenhuma transferência tem valor zero; o componente zerado não aparece |

## Mapeamento para testes

| Critério | Arquivo de teste |
|---|---|
| A-1, A-2 e A-5 a A-10, A-13 | `tests/tecnicos/test_financeiro_entradas.py` |
| A-2 | também `tests/aceitacao/test_cenario_30_tarifa.py` (registro; a cobertura fica na E09-06) |
| A-3 e A-4 | `tests/tecnicos/test_financeiro_entradas.py` e `tests/aceitacao/test_cenario_39_dois_pagamentos.py` |
| A-11 e A-12 | `tests/tecnicos/test_financeiro_concorrencia.py` |
