# E11-03 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Arranjo AP como na E11-01 (`acceptance.md`).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §8.2 3.3, cenário 13 | positivo | AP-viável; X pago, Y sem pagamento | `iniciar_apuracao` | as caixas 1 e 2 de P2 invalidadas, as duas com B dentro: duas `CaixaInvalidada` (P2, 1) e (P2, 2); nenhuma caixa nova; nenhuma `ParcelaNoPedido` alterada. **Red esperado:** nenhuma `CaixaInvalidada` |
| A-2 | §8.2 3.5 | positivo | o A-1 | ler a `ApuracaoFinal` | `valor_valido = 60,00` (P1 de A, 60,00; P2 de A invalidado, 0,00); `minimo = 50,00`; `resultado = "valida"` |
| A-3 | §8.2 3.7 | positivo | AP-insuficiente; X pago, Y sem pagamento | `iniciar_apuracao` | `valor_valido = 60,00`; `minimo = 100,00`; `resultado = "retorno_para_interesse"` |
| A-4 | Caso-limite | positivo | AP-insuficiente; X e Y pagos | `iniciar_apuracao` | nenhuma caixa invalidada; `valor_valido = 170,00`; `valida` |
| A-5 | Caso-limite | positivo | AP-viável; ninguém pagou | `iniciar_apuracao` | as duas caixas invalidadas; `valor_valido = 0,00`; `retorno_para_interesse` |
| A-6 | §6.3, cenário 13 | positivo | um arranjo com P2 de múltiplo 6 e parcelas A 4, C 2, A 2, B 4 (caixa 1: A 4 e C 2; caixa 2: A 2 e B 4); A e C pagam, B não; P1 como no AP | `iniciar_apuracao` | só a caixa 2 invalidada; as unidades válidas de A em P2 são 4 (caixa 1) e as invalidadas 2 (caixa 2); C sem unidade invalidada; nenhuma unidade de A da caixa 2 completa outra caixa |
| A-7 | Q-7, R-1 | positivo | um produto P4 de 7,99/kg, incremento 0,25 e múltiplo 0,5; as parcelas A 0,75 kg e B 0,25 kg, nessa ordem (caixa 1: A 0,5; caixa 2: A 0,25 e B 0,25); A paga (item de 0,75 kg, subtotal 5,99), B não | `iniciar_apuracao` | só a caixa 2 invalidada; a parte invalidada de A é `arredondar(5,99 × 0,25 ÷ 0,75) = 2,00`, e o valor válido do item é 3,99; o mesmo valor de produtos que o `reembolso_parcial(item, 0.25)` da E10-02 grava para esse item sem reembolso anterior |
| A-8 | Determinismo | positivo | o A-1 | recalcular o resultado, pela função interna, sobre os mesmos registros | o mesmo valor válido, as mesmas caixas e o mesmo resultado |
| A-9 | Auditoria | positivo | o A-1 | ler a auditoria `rodada.apuracao_final` | as caixas (P2, 1) e (P2, 2), o valor válido 60,00, o mínimo 50,00 e o resultado `valida` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-9 | `tests/tecnicos/test_apuracao_resultado.py` |
