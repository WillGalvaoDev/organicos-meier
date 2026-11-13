# E13-01 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

## Arranjo comum da E13 (arranjo AF)

O arranjo AP da E11 (`tests/apoio/apuracao.py`, `arranjo_ap`), com o fornecedor F de prazo padrão de 7 dias e e-mail do pedido `pedidos@f.example`:

| Produto | Preço | Múltiplo | Parcelas, em ordem de sequência |
|---|---|---|---|
| P1 | 10,00 | — | A 6; B 5 |
| P2 | 5,00 | 6 | A 4; B 6; B 2 |

- **AF (aprovada, os dois pagos):**
  - AP-viável (mínimo 50,00), X e Y pagos pelo simulador;
  - relógio em `T0 + 48h` (2026-11-04 10:00 em Brasília): `iniciar_apuracao` e depois `aprovar_resultado`;
  - a rodada em `aguardando_fornecedor`.
- **AF-parcial:** como o AF, com Y sem pagamento. A apuração cancela Y e invalida as duas caixas de P2 (E11-03 A-1); valor válido 60,00.
- **"Aprovar":** sempre por `aprovar_resultado(admin, rodada)`, fora de transação, como na E11-06.

Valores esperados:

| Arranjo | Linhas | Total |
|---|---|---|
| AF | P1: 11 unidade, 110,00; P2: 12 unidade em 2 caixas de 6, 60,00 | 170,00 |
| AF-parcial | P1: 6 unidade, 60,00; sem linha de P2 | 60,00 |

## Critérios

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §10, infra 4.14 | positivo | AF antes da aprovação | aprovar | um `PedidoFormal` com a aprovação, o ciclo, a rodada, F, `emitido_em = T0 + 48h`, `prazo_entrega_dias = 7` e `total_produtos = 170,00`; duas `LinhaDoPedidoFormal` com os valores da tabela (P2 com `multiplo = 6` e `caixas = 2`; P1 com os dois nulos). **Red esperado:** nenhum `PedidoFormal` |
| A-2 | §10, R-6 | positivo | AF-parcial | aprovar | uma linha só, de P1, com 6 e 60,00; total 60,00; nenhuma unidade de B nem das caixas invalidadas |
| A-3 | Regra 4, regra 7 | positivo | AF e AF-parcial | aprovar; ler o movimento da `ApuracaoNoLivro` | `total_produtos` igual à soma do componente de produtos transferido para `obrigacao_fornecedor(F, rodada)` nos dois casos |
| A-4 | Regra 5 | positivo | AF | aprovar | uma `PrevisaoDeEntrega` `padrao`, sem autor, com `data = 2026-11-11`; `previsao_inicial = 2026-11-11`; `previsao_vigente(ciclo)` devolve essa previsão |
| A-5 | Regra 5, calendário | positivo | AF com a aprovação em 2026-11-05 02:30 UTC (23:30 de 04/11 em Brasília) | aprovar | `data = 2026-11-11` (conta o dia de Brasília, não o de UTC) |
| A-6 | Regra 6 | positivo | AF; F sem informações de frete | aprovar | o assunto `Pedido formal nº <pk> — Orgânicos Méier — F`; o corpo exatamente com as linhas: `Pedido formal nº <pk>`, `Fornecedor: F`, `Rodada <rodada>, ciclo 1`, `Emitido em 04/11/2026 10:00 (horário de Brasília)`, vazia, `Produtos:`, `- P1: 11 unidade × R$ 10,00 = R$ 110,00`, `- P2: 12 unidade em 2 caixa(s) de 6 unidade × R$ 5,00 = R$ 60,00`, `Total dos produtos: R$ 170,00`, vazia, `Condições de entrega:` e `Previsão de entrega: 11/11/2026 (prazo padrão de 7 dias)` |
| A-7 | Regra 6 | positivo | AF; F com as informações de frete "Entrega no galpão às terças" | aprovar | o corpo termina com `Informações de frete: Entrega no galpão às terças` |
| A-8 | §2, §10 | negativo | AF, com os nomes e e-mails de A e de B conhecidos | aprovar; ler o assunto, o corpo, as linhas e a auditoria `pedido_formal.gerar` | nenhum deles contém o nome ou o e-mail de A ou de B, "Comprador", "serviço", o valor do serviço (8,50) nem o frete (22,00); a auditoria e as linhas não têm chave de comprador nem de pedido |
| A-9 | Regra 3, fracionário | positivo | um arranjo com P4 de 7,99/kg, incremento 0,25 e múltiplo 0,5, com A 0,75 e B 0,25 (caixa 1: A 0,5; caixa 2: A 0,25 e B 0,25), os dois pagos, e P1 como no AP | aprovar | a linha de P4 com `quantidade = 1`, `caixas = 2` e o valor igual à soma dos subtotais dos dois itens; no corpo, `1 kg em 2 caixa(s) de 0,5 kg` |
| A-10 | Herdado E11-03, regra 4 | positivo | o arranjo da E11-03 A-6 (P2 com A 4, C 2, A 2, B 4; B não paga; só a caixa 2 invalidada), aprovado | aprovar | a linha de P2 com 6 unidades em 1 caixa e o valor de 6 × 5,00 = 30,00; P1 sem as unidades de B |
| A-11 | Regra 8 | positivo | o A-1 | `gerar_pedido_formal(aprovacao)` de novo, numa transação | devolve o mesmo pedido formal; nenhum registro novo (pedido, linha, previsão, envio ou auditoria) |
| A-12 | Regra 11 | negativo | AF apurada e não aprovada; e, em outro teste, AP-insuficiente apurada (retorno ao interesse) | procurar `PedidoFormal`; chamar a função interna de geração sem aprovação | nenhum pedido formal; a função recusa sem escrita |
| A-13 | Regra 9 | positivo | o A-1 | ler o `EnvioDoPedidoFormal` | `em_andamento`, `automaticas = 0`, `proxima_tentativa_em = T0 + 48h`; nenhuma tentativa registrada e nenhum e-mail enviado (`mail.outbox` vazio) |
| A-14 | Infra 4.14, E01-04 | negativo | o A-1 | `save()`, `update()` e `delete()` no `PedidoFormal`, numa linha e na previsão; `UPDATE` e `DELETE` por SQL direto | recusados pela aplicação (`RegistroImutavel`) e pela trigger |
| A-15 | Regra 7 | negativo | AF; o teste altera, só na transação do teste, o valor que o cálculo da linha devolve (mutação controlada da função interna de valor) | aprovar | `PedidoFormalIncoerente`; a aprovação desfeita: sem `AprovacaoDoResultado`, sem `ApuracaoNoLivro`, a rodada em `pagamento` |
| A-16 | Herdado E11 | positivo | o A-1 | ler a auditoria `pedido_formal.gerar` | autor `SISTEMA`; o pedido formal, o ciclo, as linhas (produto, quantidade, caixas, valor), o total 170,00 e a previsão `2026-11-11` |
| A-17 | T-47 | positivo | AF com `pendente_a_p1 = 2` (A com 2 pendentes em P1) | aprovar | a linha de P1 com 11, sem as 2 pendentes; a parcela de A continua com o pendente 2 |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-17 | `tests/tecnicos/test_pedido_formal.py` |
