# E14-07 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:** os da E14-01. `PX = /pedidos/<pk de X>/`, a página do pedido de A.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §13, regra 1 | positivo | AE com a ocorrência `faltante` de 2 em X-P1 | GET `PX` como A | a seção "Ocorrências de entrega" com a data, P1, "Faltante", "2 unidade", "Reembolso de R$ 23,59" e a situação "Devida" (obrigação sem parcela). **Red esperado:** a seção não existe |
| A-2 | Regra 1 | positivo | o A-1 com a devolução autorizada e concluída no simulador (E10) | GET `PX` | a situação "Concluída" |
| A-3 | Regra 2, §11 | positivo | AE-liberada com X-P1 retirado 4 | GET `PX` como A | "Retirada liberada em 05/11/2026 10:00. Retire até 12/11/2026 10:00 (horário de Brasília)."; o endereço; X-P1: pedido 6, reembolsado 0, retirado 4, descartado 0, a retirar 2; X-P2: 4, 0, 0, 0, 4 |
| A-4 | Regra 2, cenário 23 | positivo | o A-3; relógio em `L + 8 dias`, sem descarte | GET `PX` | "Prazo de retirada encerrado em 12/11/2026 10:00."; descartado 0 em todos |
| A-5 | Regra 2 | positivo | o A-4 com o descarte de 2 em X-P1 | GET `PX` | X-P1: descartado 2, a retirar 0 |
| A-6 | Regra 2 | positivo | AE-falta | GET `PX` | X-P1: pedido 6, reembolsado 2, a retirar 4 |
| A-7 | Regra 3 | positivo | AE | GET `PX` | sem a seção de retirada; a previsão de entrega da E13-05 presente |
| A-8 | Regra 2, cenário 19 | positivo | AE-liberada com A suspenso | GET `PX` como A | 200 com a seção de retirada |
| A-9 | Regra 4, cenário 50 | negativo | AE-liberada com ocorrência | GET `PX` como A | nenhum `form` nem botão além dos que a página já tinha antes da E14 (comparação com a página de AE sem ocorrência); nenhum campo `tipo`, `item` ou `quantidade` |
| A-10 | Regra 6 | negativo | AE com ocorrência em X | GET `PX` como B | a recusa da E08, sem os dados da ocorrência |
| A-11 | Regra 7, cenário 50 | negativo | AE e AE-liberada | como A, POST em cada rota da E14-06 com o pk de X-P1 e em `administracao/retirada/endereco/` | 403 em todas; nenhuma `OcorrenciaDeEntrega`, `RecebimentoDoFornecedor`, `RetiradaDeItem`, `DescarteDeItem`, `Reembolso` ou `EnderecoDeRetirada` nova |
| A-12 | Regra 8, cenários 47 e 50 | negativo | AE | como A, POST em `PX` e em `/pedidos/<pk de X>/pagar/` com `item=<X-P1>`, `tipo=faltante`, `quantidade=2` | nenhum registro da E14; o pedido e os itens iguais; a resposta é a de hoje dessas rotas |
| A-13 | Regra 9 | negativo | AE-liberada | como a conta de fornecedor de F: GET e POST nas rotas da E14-06, em `administracao/retirada/endereco/` e em `regras/` | 403 em todas, sem escrita |
| A-14 | Regra 10, cenários 21 e 67 | positivo | AE-liberada com ocorrência, retirada e descarte | como F, GET `fornecedor/rodadas/<pk>/` e o CSV | a etapa "Disponível para retirada"; o pedido formal; sem previsão; as chaves dos serializadores iguais às listas da E13-07 (teste por conjunto de chaves); nenhum nome de comprador, endereço, tipo de ocorrência ou quantidade retirada no HTML nem no CSV |
| A-15 | E14-R02, regra 5 corrigida | negativo | AE com a ocorrência `faltante` de 2 em X-P1; depois o cancelamento da rodada sem reembolso | GET `PX` como A | 200; sem os títulos `<h2>Ocorrências de entrega</h2>` e `<h2>Retirada</h2>`; as frases do cancelamento da E12; a seção "Estornos" com a obrigação de R$ 23,59 da ocorrência e o estado real; a `OcorrenciaDeEntrega`, o `Reembolso` e a obrigação iguais aos de antes do cancelamento. **Red esperado:** a seção "Ocorrências de entrega" presente |
| A-16 | E14-R02, regra 5 corrigida | negativo | o mesmo do A-15, com o cancelamento com reembolso; `processar_chamadas()` | GET `PX` como A; GET da página do pedido Y como B (sem ocorrência) | sem o título `<h2>Ocorrências de entrega</h2>` em X; na seção "Estornos" de X, a obrigação da ocorrência (23,59) e a do cancelamento (70,76); a ocorrência e as obrigações intactas; a página de Y sem as seções desta fatia |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-12, A-15 e A-16 | `tests/tecnicos/test_retirada_comprador.py` |
| A-13 e A-14 | `tests/tecnicos/test_portal_do_fornecedor.py` (acréscimos) |
