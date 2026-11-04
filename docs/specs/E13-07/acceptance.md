# E13-07 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Contas:** a conta do fornecedor F (papel `fornecedor`, vinculada a F) e a de um segundo fornecedor G com produtos e uma rodada próprios.
- **Arranjos:** AF (E13-01) para F; uma rodada de G em `interesse` com o produto Q.
- **Listas de campos:** as chaves das tabelas da `spec.md` são as constantes de referência dos testes.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §2, cenário 67 | positivo | AF | GET `fornecedor/` como F | 200; "F"; P1 e P2 com unidade, preço e múltiplo (P2: 6); a rodada do AF com "Aguardando fornecedor"; nada de G. **Red esperado:** 404 |
| A-2 | Infra 4.13 | positivo | AF | chamar a função do painel | as chaves de cada bloco exatamente iguais às da regra 4 |
| A-3 | §6.2, herdado E05 | positivo | uma rodada de F em `interesse` com as parcelas do AP (antes da abertura) | GET `fornecedor/rodadas/<pk>/` como F | a etapa "Interesse"; P1 com total 11, valor R$ 110,00; P2 com total 12, 2 caixas completas, 0 faltando e excedente 0; o percentual de progresso; nem o mínimo em valor nem nomes de compradores |
| A-4 | Infra 4.13 | positivo | o A-3 | chamar a função da rodada | as chaves exatamente iguais às da regra 6 |
| A-5 | Regra 7 | positivo | a rodada AP em `pagamento` | GET a rodada como F | "Pagamento" e a frase da regra 7; nenhuma quantidade, valor de pedido ou pagamento |
| A-6 | §10, cenário 67 | positivo | AF | GET a rodada como F | o pedido formal nº, emitido em 04/11/2026 10:00, as linhas de P1 e P2 com quantidade, caixas, preço e valor, o total R$ 170,00 e a "Previsão de entrega: 11/11/2026"; sem tentativas, destino, frete, serviço ou repasse |
| A-7 | E13-05 | positivo | AF com a previsão ajustada para 14/11/2026 | GET a rodada como F | a previsão 14/11/2026 |
| A-8 | Regra 8 | positivo | AF cancelada (E12) | GET a rodada como F | "Cancelada"; o pedido formal consultável; sem a previsão |
| A-9 | Regra 10, T-27 | positivo | AF | GET `fornecedor/rodadas/<pk>/pedido-formal.csv` como F | `text/csv`; anexo `pedido-formal-<pk>.csv`; o cabeçalho exato da regra 10; duas linhas: `P1;unidade;11;;;10,00;110,00` e `P2;unidade;12;6;2;5,00;60,00`; nenhuma outra coluna |
| A-10 | Regra 10 | negativo | uma rodada de F em `pagamento` | GET a exportação como F | 404 |
| A-11 | Regra 2, cenário 21, T-27 | negativo | AF e a rodada de G | GET `fornecedor/rodadas/<rodada de G>/` e a exportação dela como F; GET `fornecedor/rodadas/999999/` | 404 nos três, com o mesmo corpo de resposta |
| A-12 | Cenário 21, T-27 | negativo | AF | como F: GET `pedidos/<X>/`, POST `pedidos/<X>/pagar/`, GET `administracao/financeiro/`, `administracao/financeiro/reserva/`, `administracao/financeiro/movimentos/`, `administracao/financeiro/devolucoes/<obrigação>/`, `administracao/usuarios/`, `administracao/rodadas/<pk>/pedido-formal/` e `administracao/rodadas/<pk>/saidas/` | 403 em todas, sem nome de comprador, valor de serviço ou saldo da reserva no corpo |
| A-13 | T-25 | negativo | AF | como F: GET `carrinho/`, POST `interesses/`, GET `catalogo/` e `catalogo/<F>/` | 403 em todas |
| A-14 | T-25 | negativo | AF | como o comprador A: GET `fornecedor/`, a rodada e a exportação | 403 nas três |
| A-15 | Regra 1 | negativo | AF | como administrador e como anônimo: GET `fornecedor/` | 403; redirecionamento para o login |
| A-16 | Regra 3 | negativo | AF | ler o HTML das páginas de F e o CSV | nenhum nome nem e-mail de A ou de B; nenhum "R$ 8,50" (serviço) nem "R$ 22,00" (frete); nenhum link para `pedidos/<X>/` ou `pedidos/<Y>/` |
| A-17 | Regra 11 | positivo | — | GET `inicio/` como F e como A | F com o link "Minhas rodadas" para `fornecedor/`; A sem ele |
| A-18 | Sem escrita | negativo | AF | POST nas três rotas do fornecedor como F | 405 nas três |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-18 | `tests/tecnicos/test_portal_do_fornecedor.py` |
