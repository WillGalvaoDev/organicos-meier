# E14-05 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:** os da E14-01. AE-liberada: `L = T0 + 72h`; prazo final `L + 7 dias` = 2026-11-12 13:00 UTC (10:00 em Brasília).
- **Chamadas:** `registrar_retirada(admin, item, quantidade, acionamento=...)` e `registrar_descarte(...)`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §11 | positivo | AE-liberada; relógio em `L + 1 dia` | retirada de 4 em X-P1 | uma `RetiradaDeItem` (item, 4,000, autor, instante); `saldo_do_item(X-P1)` = 2. **Red esperado:** a função não existe |
| A-2 | §11 (momentos diferentes) | positivo | o A-1 | em `L + 3 dias`, retirada de 2 em X-P1 | dois registros, com os instantes de cada um; saldo 0 |
| A-3 | Regra 4 | negativo | o A-1 | retirada de 3 em X-P1 | `passa_do_saldo_do_item`, com "(2 unidade)."; nada gravado |
| A-4 | Cenário 22, regra 6 | positivo | AE-liberada; relógio em `L + 10 dias` (depois do prazo) | retirada de 5 em Y-P1 | aceita |
| A-5 | Cenário 23, regra 4 | negativo | AE-liberada; relógio em `prazo_final − 1 ms` | descarte de 6 em X-P1 | `antes_do_prazo`, com "a partir de 12/11/2026 10:00 (horário de Brasília)"; nada gravado |
| A-6 | Cenário 23 | positivo | AE-liberada; relógio exatamente em `prazo_final` | descarte de 6 em X-P1 | aceito; saldo 0 |
| A-7 | Cenário 23 | positivo | AE-liberada com X-P1 retirada 4; relógio em `L + 8 dias`, sem nenhum descarte | `situacao_da_retirada(rodada)` | `prazo_encerrado` verdadeiro; `vencidos` com X-P1 (saldo 2), X-P2 (4), Y-P1 (5) e Y-P2 (8); nenhum `DescarteDeItem` gravado; o saldo de cada item igual ao de antes do prazo |
| A-8 | Regra 4 | negativo | AE-recebido (antes da liberação) e AE cancelada | retirada e descarte em cada uma | `etapa` em todas, sem escrita |
| A-9 | Regra 4 | negativo | AE-liberada | quantidades `0`, `-1`, `0.5`, `1.0001` e o `float` `1.0`; um item de pedido não válido (de outro ciclo ou de outra rodada) | `quantidade_invalida` e `item_fora_do_pedido_formal`, sem escrita |
| A-10 | Regra 5, E14-02 | positivo e negativo | AE-liberada com X-P1 retirada 4 | ocorrência `incorreto` de 2 em X-P1 (E14-02); depois retirada de 1 em X-P1 | a ocorrência aceita (saldo 0); a retirada `passa_do_saldo_do_item` |
| A-11 | Regra 5 | positivo | AE-falta | `situacao_da_retirada` | X-P1: pedida 6, em ocorrências 2, retirada 0, descartada 0, saldo 4 |
| A-12 | Regra 5 | positivo | AF-parcial liberado (X-P2 com as 4 unidades reembolsadas na apuração) | `situacao_da_retirada` | X-P2: pedida 4, reembolsada na apuração 4, saldo 0; nenhum vencido nele depois do prazo |
| A-13 | Regra 7, cenário 19 | positivo | AE-liberada com A suspenso; outro arranjo com A removido | retirada de 6 em X-P1 | aceita nos dois |
| A-14 | Regra 1 | negativo | AE-liberada | retirada e descarte com A, com o fornecedor e com `None` | `PermissionDenied`, sem escrita |
| A-15 | Regra 2 | positivo e negativo | o A-1 com a1 | repetir idêntico; a1 com quantidade 1; `"abc"` | o mesmo registro, `novo = False`, uma auditoria; `acionamento_invalido` nos outros dois, sem escrita |
| A-16 | Regra 8 | positivo | o A-6 | comparar reembolsos, obrigações, `MovimentoFinanceiro`, pedidos e itens com o estado anterior | iguais |
| A-17 | Regra 9 | positivo | o A-1 e o A-6 | ler a auditoria | `retirada.registrar` e `descarte.registrar` com o autor, o pedido, o item, a quantidade, o saldo depois e o UUID sob `acionamento`; nenhum nome ou e-mail de comprador |
| A-18 | Só inserção | negativo | o A-1 e o A-6 | `update` e `delete` pela aplicação e por SQL direto | recusados |
| A-19 | Concorrência | concorrência | AE-liberada; a retirada de 4 em X-P1 pausada com as travas retidas | a ocorrência `incorreto` de 4 em X-P1 numa segunda conexão, confirmada esperando com `esperar_outra_conexao_na_trava()`; depois a retirada retomada | a retirada grava; a ocorrência `passa_do_saldo_do_item`; nenhum reembolso novo |
| A-20 | Concorrência | concorrência | AE-liberada; a retirada de 4 em X-P1 pausada | uma segunda retirada de 4 em X-P1 (outro acionamento), confirmada esperando; depois a primeira retomada | a primeira grava; a segunda `passa_do_saldo_do_item`; retirada 4 |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-18 | `tests/tecnicos/test_retirada.py` |
| A-19 e A-20 | `tests/tecnicos/test_retirada.py`, com transações PostgreSQL reais |
| A-5 a A-7 | também `tests/aceitacao/test_cenario_23_descarte.py` |
