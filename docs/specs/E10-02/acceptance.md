# E10-02 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjos.** Pedidos pagos (`SituacaoDoPedido` `pago`) montados por fábrica, com itens e valores registrados explícitos.

| Arranjo | Pedido | Itens |
|---|---|---|
| **K** | produtos 7,99, serviço 0,40 e frete 1,60 | um item de 1,000 kg a R$ 7,99/kg, subtotal 7,99, incremento 0,25 |
| **M** | produtos 0,09, serviço 0,00 e frete 0,00 | um item de 0,6 kg a R$ 0,15/kg, subtotal 0,09, incremento 0,1 |
| **N** | produtos 100,00, serviço 5,00 e frete 20,00 | os itens I1 (subtotal 25,00, quantidade 1, incremento 1) e I2 (subtotal 75,00, quantidade 3, incremento 1) |

Em todos, o autor é o administrador. As chaves são distintas por chamada, salvo quando o critério diz o contrário.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §16 nº 112, T-51 | positivo | K; depois o preço do produto no catálogo muda para R$ 9,99/kg | `reembolso_parcial(item, 0.25)` | produtos 2,00; uma linha com quantidade 0,250 e valor 2,00. Mudar o preço antes ou depois não altera o valor |
| A-2 | §16 nº 113, T-51 | positivo | K | quatro `reembolso_parcial(item, 0.25)` seguidos | produtos 2,00, 2,00, 2,00 e 1,99; soma 7,99; na quarta, serviço e frete completam exatamente 0,40 e 1,60 |
| A-3 | §16 nº 114 | positivo | K, com um parcial de 0,25 já registrado | `reembolso_integral_do_pedido(pedido)` | uma linha de quantidade 0,750 e valor 5,99; o serviço e o frete restantes; a soma de cada componente igual ao registrado |
| A-4 | §16 nº 115, T-51, T-52 | positivo e negativo | M | seis `reembolso_parcial(item, 0.1)` e depois um sétimo | produtos 0,02, 0,02, 0,02, 0,02, 0,01 e 0,00; soma 0,09; o sexto é gravado sem obrigação; o sétimo levanta `ReembolsoRecusado("passa da quantidade paga")`, sem escrita |
| A-5 | §16 nº 116 | positivo | N | `reembolso_parcial(I2, 1)`, que vale 25,00, e depois `reembolso_parcial(I1, 1)` | primeiro: produtos 25,00, serviço 1,25 e frete 5,00 (o 31,25 do §9.2). Segundo: produtos 25,00, serviço 1,25 e frete 5,00. Os acumulados ficam 50,00, 2,50 e 10,00, abaixo do registrado |
| A-6 | §16 nº 116 | positivo | um pedido com produtos 100,00, serviço 5,00, frete 20,00 e um item de subtotal 100,00, quantidade 50 e incremento 1 | `reembolso_parcial(item, 1)` | produtos 2,00, serviço 0,10 e frete 0,40 |
| A-7 | §16 nº 91, T-40, T-52 | positivo | N, com o parcial de I2 do A-5 já registrado | `reembolso_integral_do_pedido(pedido)` | linhas: I1 com quantidade 1 e 25,00; I2 com quantidade 2 e 50,00; serviço 3,75 e frete 15,00. Somando tudo do pedido: 100,00, 5,00 e 20,00, exatamente o cobrado |
| A-8 | T-52 | negativo | K | `reembolso_parcial(item, 0.3)` (não múltiplo de 0,25); `0`; `-0.25`; `0.2501` | `ReembolsoRecusado("quantidade inválida")` em todos, sem escrita |
| A-9 | §16 nº 117 | positivo | o A-2 | ler os registros | quatro `Reembolso` separados, cada um com item, quantidade e valores; `Pedido` e `ItemDoPedido` iguais aos originais (mesmos campos e nenhuma linha nova) |
| A-10 | Herdado E09 | positivo | N pago pelo simulador, com as entradas na custódia (E09-04: produtos 100,00, serviço 5,00 e frete 20,00), antes da apuração | o primeiro reembolso do A-5, depois ler a obrigação | uma `ObrigacaoComComprador` com origem no `Reembolso`, motivo do reembolso, produtos 25,00, serviço 1,25 e frete 5,00, financiada pelas custódias do comprador (F8); `sem_cobertura` 0,00 |
| A-11 | Idempotência | positivo e negativo | K | `reembolso_parcial(item, 0.25, chave="oc-1")` duas vezes; depois com a mesma chave e quantidade 0,50 | a segunda devolve o mesmo reembolso e a mesma obrigação, sem registro novo; a terceira levanta `ReembolsoConflitante`, sem escrita |
| A-12 | Pedido elegível | negativo | um pedido `aguardando_pagamento` e um `cancelado` | `reembolso_parcial` e `reembolso_integral_do_pedido` | `ReembolsoRecusado("o pedido não está pago")`, sem escrita |
| A-13 | Integral vazia | positivo | K inteiramente reembolsado | `reembolso_integral_do_pedido(pedido)` | devolve `None`; nada gravado |
| A-14 | Decisão técnica | negativo | um motivo fora da lista | `reembolso_parcial` | `ValueError`, sem escrita |
| A-15 | T-53 | concorrência | K | dois `reembolso_parcial(item, 0.5)` e um terceiro `reembolso_parcial(item, 0.25)` em paralelo, com chaves diferentes | em qualquer ordem: no máximo 1,000 kg somado; soma dos valores ≤ 7,99; nenhum registro duplicado; sem `deadlock`; quem passaria de `Q` levanta `ReembolsoRecusado` |
| A-16 | Concorrência | concorrência | N | `reembolso_parcial(I2, 1)` e `reembolso_integral_do_pedido(pedido)` em paralelo | em qualquer ordem: os acumulados do pedido ficam exatamente 100,00, 5,00 e 20,00; duas obrigações, cuja soma é 125,00 |
| A-17 | Decisão técnica | positivo | um pedido com frete 0,00 | um parcial e depois a integral | o componente frete fica 0,00 em todos os reembolsos e obrigações |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-14 e A-17 | `tests/tecnicos/test_devolucoes_reembolso.py` |
| A-15 e A-16 | `tests/tecnicos/test_devolucoes_concorrencia.py` |
| A-1, A-2, A-3, A-4, A-5, A-7 e A-9 | também `tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py`, no nível do serviço |

## Correção E10-R01 (2026-10-30)

Valem a seção da correção no `spec.md`, o "Padrão das corridas" (E09-01, `spec.md`, como na E09) e a correção E10-R08 (E10-07, `spec.md`). O A-16 abaixo **substitui** o A-16 original.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-16 (reescrito) | Concorrência, R01 | concorrência | N | `reembolso_parcial(I2, 1)` e `reembolso_integral_do_pedido(pedido)` em paralelo, em duas execuções. Na primeira, o parcial pausa logo depois da trava da `SituacaoDoPedido` e a integral começa; na segunda, é a integral que pausa no mesmo ponto | **Parcial primeiro:** dois reembolsos e duas obrigações, cuja soma é 125,00. **Integral primeiro:** um reembolso e uma obrigação de 125,00, e o parcial levanta `ReembolsoRecusado` (quantidade acima do restante), sem escrita. Nas duas, os acumulados do pedido ficam exatamente 100,00, 5,00 e 20,00 |
| A-18 | R01 | negativo | K; `reembolso_parcial(item, 0.25, chave="mesma-chave", motivo="cancelamento_da_rodada")` feito | `reembolso_integral_do_pedido(pedido, chave="mesma-chave", motivo="cancelamento_da_rodada")` | `ReembolsoConflitante`; um reembolso só (`tipo = parcial`); uma obrigação; os acumulados iguais aos de antes. **Red esperado:** devolve o parcial, sem erro |
| A-19 | R01 | negativo | K com um item; `reembolso_integral_do_pedido(pedido, chave="int-1")` feito, com a linha (item, quantidade total) | `reembolso_parcial(item, <a quantidade total>, chave="int-1")`, com o mesmo motivo | `ReembolsoConflitante`; nada novo. **Red esperado:** as linhas coincidem e a integral é devolvida |
| A-20 | R01 | positivo | o A-19 antes do parcial | `reembolso_integral_do_pedido` de novo, com a mesma chave e o mesmo motivo | devolve o mesmo reembolso, com `tipo = integral`; nada novo. Regressão: esperado verde no código atual, sem Red, salvo pela ausência do campo `tipo` |

| Critério | Arquivo de teste |
|---|---|
| A-16 | `tests/tecnicos/test_devolucoes_concorrencia.py` |
| A-18 a A-20 | `tests/tecnicos/test_devolucoes_reembolso.py` |
