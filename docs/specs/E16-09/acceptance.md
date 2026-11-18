# E16-09 — Critérios de aceitação

Agente 1 (especificador). Cada critério permite um teste automatizado que falha antes da implementação.

- **Execução:** `pytest tests/tecnicos/test_pedidos_historico_interesses.py tests/aceitacao/test_cenario_96_historico.py`.
- **Leitura da página:** os testes leem o texto da página sem as tags, como `_texto` em `tests/tecnicos/test_fila_ponta_a_ponta.py`, e localizam a seção pelo título.
- **Teste do cenário 96:** usa pendentes reais da apuração. É o arranjo da E11-08: caixa invalidada, restauração e reabertura com o estoque livre zero, de `tests/tecnicos/test_fila_ponta_a_ponta.py`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §16.96; regras 1 a 4 | positivo | o comprador A com 6 reservados e 4 pendentes reais de um produto `P`, e o estoque livre de `P` zero | A abre `GET /pedidos/` | 200; a seção "Interesses reservados e pendentes" com a linha de `P` mostrando "Reservado: 6" e "Pendente: 4", separados. **Red esperado:** seção ausente. Teste `test_cenario_96_historico_mostra_reservado_e_pendente_com_estoque_zerado`, marcado `acceptance`; é a referência da afirmação do histórico do cenário 96 na matriz (E16-07 A-44) |
| A-2 | Regras 2 e 9 | positivo | o arranjo do A-1, mais um segundo produto de outro fornecedor com 2 reservados e 0 pendentes | A abre `GET /carrinho/` e `GET /pedidos/` | os pares (produto, reservado, pendente) das duas páginas são iguais, inclusive "Reservado: 2" e "Pendente: 0" |
| A-3 | Regras 3 e 4 | positivo | A com 0 reservado e 4 pendentes de um produto cujo fornecedor não tem rodada ativa, e o produto marcado como indisponível | A abre `GET /pedidos/` | a linha aparece com "Reservado: 0" e "Pendente: 4" e com a unidade do produto |
| A-4 | Regra 8 | negativo | A com o arranjo do A-1; o comprador B com 1 reservado de outro produto `Q` e nenhum interesse em `P` | B abre `GET /pedidos/`; B abre `GET /pedidos/?comprador=<id de A>` | nas duas, só a linha de `Q`, sem `P`, sem "Pendente: 4" e sem "Reservado: 6" |
| A-5 | Regras 5 e 6 | positivo | um comprador sem pedidos e sem interesses; outro sem pedidos e com 3 pendentes | cada um abre `GET /pedidos/` | o primeiro vê "Você ainda não tem pedidos." e "Você não tem interesses reservados nem pendentes."; o segundo vê "Você ainda não tem pedidos." e a linha com "Pendente: 3" |
| A-6 | Regra 8 | negativo (regressão) | um anônimo, uma conta de fornecedor e o administrador | cada um faz `GET /pedidos/` | a mesma resposta de antes da fatia para cada um (redirecionamento ao login e a recusa da política `exige_comprador`), sem a seção. A varredura de rotas da E02-10 continua verde |
| A-7 | Regra 7 | positivo | o arranjo do A-1 | A abre `GET /pedidos/` | a seção não tem `<form>` nem `<button>`; tem um link para `/carrinho/`; as contagens de `ParcelaDeInteresse`, `EntradaAuditoria` e `Notificacao` e os valores das parcelas de A não mudam |

| Critério | Arquivo de teste |
|---|---|
| A-1 | `tests/aceitacao/test_cenario_96_historico.py` |
| A-2 a A-7 | `tests/tecnicos/test_pedidos_historico_interesses.py` |
