# E08-01 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05): Red com caminhos explícitos de arquivos inteiros, sem `-k` nem seleção por nome, e tabela de cobertura do Red antes do Green.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 10 | positivo | comprador 1 com um item de R$ 100,00 × 1; comprador 2 com um item de R$ 300,00 × 1; frete R$ 40,00 | `calcular_cobranca` | comprador 1: produtos 100,00, serviço 5,00, frete 10,00, total 115,00; comprador 2: 300,00, 15,00, 30,00, 345,00 |
| A-2 | T-39, cenários 88 e 89 | positivo | itens 7,99 × 0,250; 2,50 × 0,250; 12,99 × 0,350 | o cálculo | subtotais 2,00, 0,63 e 4,55 |
| A-3 | Cenário 89 | positivo | um comprador com dois produtos, cada um 2,50 × 0,250 | o cálculo | `P` 1,26, e não 1,25 |
| A-4 | Cenário 64 | positivo | 12,99 × 0,350 | o cálculo | subtotal 4,55, arredondado uma vez só, a partir de 4,5465 |
| A-5 | Spec §9 | positivo | três compradores com `P` de R$ 10,00 cada; frete R$ 10,00 | o cálculo | fretes 3,34, 3,33 e 3,33, com o centavo extra no de menor `comprador_id`; soma 10,00 |
| A-6 | Spec §9 | positivo | compradores com `P` 0,01, 0,01 e 99,98; frete R$ 0,05 | o cálculo | a soma dos fretes é 0,05; a distribuição segue o maior resto, com desempate por `comprador_id` (o teste fixa o resultado esperado calculado à mão) |
| A-7 | Spec §9 | positivo | o arranjo do A-1, com os compradores em ordem inversa na entrada | o cálculo | resultado idêntico ao do A-1, na mesma ordem de saída |
| A-8 | Spec §9 | positivo | frete R$ 0,00 | o cálculo | todos os fretes 0,00; total = produtos + serviço |
| A-9 | Spec §9 | positivo | `P` de R$ 0,10 | o cálculo | serviço 0,01 (0,005 arredonda para cima); com `P` 0,09, serviço 0,00 (0,0045) |
| A-10 | Spec da fatia | negativo | frete `-0.01`, frete `40.001`, frete `float` 40.0; preço `float`; quantidade 0 ou com quatro casas; comprador repetido; produto repetido num comprador; lista vazia; comprador sem item | o cálculo | `ValueError` em todos |
| A-11 | R-1, T-39 | positivo e negativo | — | a varredura estática nova, pela árvore de sintaxe (`ast`), sobre os módulos de dinheiro e quantidade: `apps/pedidos`, `apps/pagamentos`, `apps/simulador_pagamentos`, `apps/catalogo`, `apps/interesses`, `apps/rodadas`, `apps/fornecedores` e `apps/nucleo/valores.py`, sem as migrações; depois, a mesma varredura sobre um arquivo temporário com `x = 1.5`, `float(y)` e `models.FloatField()` | nenhum literal `float`, chamada a `float` nem `FloatField` nos módulos; no arquivo temporário, as três ocorrências acusadas, com arquivo e linha |
| A-12 | Spec da fatia | positivo | 200 casos gerados com semente fixa (de 1 a 30 compradores, preços e quantidades válidos, frete de 0 a 500) | o cálculo | em todos: soma dos fretes = `F`; `P` = soma dos subtotais; total = soma das partes; todos os valores com duas casas; nenhum frete negativo |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-10, A-12 | `tests/tecnicos/test_pedidos_calculo.py` |
| A-1 | também marcado `acceptance`, com o comentário `cenário 10` |
| A-2 | também marcado `acceptance`, com o comentário `T-39` |
| A-11 | `tests/tecnicos/test_varredura_float.py`, com a varredura em `tests/apoio/` (código de teste, não de produção) |
