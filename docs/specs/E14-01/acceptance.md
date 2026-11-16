# E14-01 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

## Arranjos comuns da E14

**AE (rodada aguardando o fornecedor).** É o AF da E13 (`tests/apoio/pedido_formal.py`, `arranjo_af`), aprovado em `T0 + 48h`, com T0 = 2026-11-02 13:00 UTC (10:00 em Brasília):

| Pedido | Comprador | Itens | Produtos | Serviço | Frete | Total |
|---|---|---|---|---|---|---|
| X | A | X-P1: P1 6 un, 60,00; X-P2: P2 4 un, 20,00 | 80,00 | 4,00 | 10,35 | 94,35 |
| Y | B | Y-P1: P1 5 un, 50,00; Y-P2: P2 8 un, 40,00 | 90,00 | 4,50 | 11,65 | 106,15 |

- Pedido formal: P1 11 un (110,00); P2 12 un em 2 caixas de 6 (60,00). Incremento 1 nos dois produtos.
- O envio do pedido formal é indiferente nesta etapa. Os testes não rodam a tarefa da E13-02, salvo indicação.
- Endereço de retirada registrado pelo administrador (E14-03): `Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ`. Antes da E14-03 existir, os testes da E14-01 e da E14-02 não dependem dele.

**AE-recebido:** AE com os recebimentos P1 11 e P2 12.

**AE-liberada:** AE-recebido liberado (E14-04) em `L = T0 + 72h` (2026-11-05 13:00 UTC, 10:00 em Brasília). Prazo final: `L + 7 dias` = 2026-11-12 13:00 UTC (10:00 em Brasília).

**AE-falta:** AE com os recebimentos P1 9 e P2 12 e a ocorrência `faltante` de 2 em X-P1 (reembolso de 23,59, E14-02), liberado em `L`.

**AE-48 (cenário 48):**
- fornecedor G, com o produto Q a 10,00 a unidade, sem múltiplo, incremento 1 e mínimo de 100,00;
- o comprador C com 10 unidades de Q; frete de 20,00 na abertura; C paga; apuração e aprovação em `T0 + 48h`;
- o pedido de C: produtos 100,00, serviço 5,00, frete 20,00.

**AE-18 (cenário 18):** como o AE-48, com Q a 12,50 e C com 8 unidades (produtos 100,00, serviço 5,00, frete 20,00).

**Convenções:**
- "admin" é o administrador do apoio.
- Os acionamentos são gerados com `uuid.uuid4()` no teste.
- As quantidades são `Decimal`.

## Critérios

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §10, §14 | positivo | AE | `registrar_recebimento(admin, rodada, P1, 7, acionamento=a1)` | um `RecebimentoDoFornecedor` (linha de P1, quantidade 7,000, autor, `registrado_em` igual ao relógio); `novo = True`; `situacao_do_recebimento`: P1 pedida 11, recebida 7, a resolver 4; P2 pedida 12, recebida 0, a resolver 12. **Red esperado:** a função não existe |
| A-2 | §10 (entregas parciais) | positivo | o A-1 | `registrar_recebimento(..., P1, 4, acionamento=a2)` em `T0 + 60h` | dois registros, com os instantes de cada um; P1 recebida 11, a resolver 0; `recebimento_resolvido` falso (P2 a resolver 12) |
| A-3 | Regra 4 | positivo | AE | recebimentos P1 11 e P2 12 | `recebimento_resolvido(rodada)` verdadeiro |
| A-4 | Regra 4 | negativo | o A-1 | `registrar_recebimento(..., P1, 5, ...)` | `RecebimentoRecusado("passa_do_pedido_formal")`, com a mensagem terminada em "(4 unidade)."; nenhum registro novo |
| A-5 | Regra 4 | negativo | AE | quantidades `0`, `-1`, `1.5`, `Decimal("NaN")`, `1.0001` e o `float` `1.0` | `quantidade_invalida` em todas, sem escrita |
| A-6 | Regra 4 | negativo | AE | registrar um produto do fornecedor que não está no pedido formal (P3, cadastrado sem estoque na rodada) e um produto de outro fornecedor | `produto_fora_do_pedido_formal` nos dois |
| A-7 | Regra 4 | negativo | rodadas em `interesse`, `pagamento`, `cancelada` (AE cancelada sem reembolso) e AE-liberada | registrar | `etapa` em todas, sem escrita |
| A-8 | Regra 1 | negativo | AE | registrar com um comprador, com a conta de fornecedor de F e com `None` | `PermissionDenied`, sem escrita |
| A-9 | Regra 2 | positivo | o A-1 | repetir a chamada idêntica com a1 | devolve o mesmo registro, `novo = False`; um registro só; uma auditoria só |
| A-10 | Regra 2 | negativo | o A-1 | a1 com quantidade 3; a1 em outra rodada AE de outro fornecedor; acionamento `"abc"` e `None` | `acionamento_invalido` em todos, sem escrita |
| A-11 | Regra 6 | positivo | o A-1 | ler a auditoria | `recebimento.registrar` com o admin, a rodada, P1, 7, o acumulado 7 e o UUID a1 sob a chave `acionamento` (nenhuma chave com o termo `token`) |
| A-12 | Regra 7 | positivo | o A-2 | comparar `PedidoFormal`, linhas, `EnvioDoPedidoFormal`, previsões, pedidos, situações, pagamentos e `MovimentoFinanceiro` com o estado anterior | iguais; nenhuma notificação nova |
| A-13 | Só inserção | negativo | o A-1 | `update` e `delete` do recebimento pela aplicação e por SQL direto | recusados (proteção E01-04) |
| A-14 | Regra 4 | positivo e negativo | AE com P1 por peso (kg, incremento 0,5), pedido formal com 3,0 kg | registrar 2,5, depois 0,3 | 2,5 aceito; 0,3 `quantidade_invalida` |
| A-15 | Concorrência | concorrência | AE com P1 recebida 7; a primeira chamada (P1, 4) pausada depois da trava da rodada | a segunda chamada (P1, 4, outro acionamento) numa segunda conexão, confirmada esperando com `esperar_outra_conexao_na_trava()`; depois a primeira retomada | a primeira grava; a segunda recebe `passa_do_pedido_formal`; recebido 11 |
| A-16 | Concorrência | concorrência | AE | duas chamadas idênticas com a1 em paralelo | um registro; as duas devolvem o mesmo `pk`, uma com `novo = True` e a outra com `novo = False` |
| A-17 | Concorrência, E12 | concorrência | AE; `cancelar_rodada(..., com_reembolso=False)` pausado com as travas retidas | `registrar_recebimento` numa segunda conexão, confirmada esperando; depois o cancelamento retomado | o recebimento recebe `etapa`; nenhum registro; sem impasse |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-14 | `tests/tecnicos/test_recebimento.py` |
| A-15 a A-17 | `tests/tecnicos/test_recebimento.py`, com transações PostgreSQL reais |
