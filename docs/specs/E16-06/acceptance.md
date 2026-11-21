# E16-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Página:** `GET /regras/` como o comprador C autenticado, com o endereço de retirada registrado (E14-03).
- **Seções:** localizadas pelos títulos `<h2>`, com o texto normalizado (espaços colapsados, sem tags).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regras 1 e 2 | positivo | — | GET | 200; o `<h1>` "Regras de funcionamento"; os títulos "Participação", "Interesse e reservas", "Fechamento", "Pagamento", "Apuração e falta de pagamento", "Devoluções", "Cancelamento da rodada" e "Retirada", nessa ordem. **Red esperado:** só a seção "Retirada" |
| A-2 | Regra 2 | positivo | — | GET | cada parágrafo da regra 2 presente, com o texto exato, na sua seção, com os valores 24, 5 e 24 substituídos |
| A-3 | Regra 2.8 | positivo | — | GET | a seção "Retirada" com o mesmo texto da E14-03 e o endereço registrado (os testes da E14-03 continuam passando sem alteração) |
| A-4 | Regra 3 | positivo | a constante da taxa de serviço trocada no teste para 7% e a do prazo para 36 horas | GET | "taxa de serviço de 7%" e "36 horas" nos parágrafos que usam esses valores. **Red esperado:** os valores fixos do template |
| A-5 | Regra 3 | positivo | a constante do prazo de retirada trocada para 10 dias | GET | o texto de retirada com 10 dias |
| A-6 | Regra 4 | negativo | uma rodada em `pagamento` com os compradores A e B e o fornecedor F | GET como C | nenhum nome de comprador, fornecedor ou produto no HTML, além do endereço |
| A-7 | Regra 1 | negativo | — | GET anônimo; GET como a conta do fornecedor F | os mesmos resultados de acesso da E14-03 |
| A-8 | Regra 5 | positivo | — | GET na página inicial do comprador | o link "Regras de funcionamento" para `/regras/` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-8 | `tests/tecnicos/test_regras_de_funcionamento.py` |
