# E12-02 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_com_pedidos.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-16 | `349f230` | **Red: 9 failed, 9 passed.** Falhas pelo motivo esperado: Y continua `aguardando_pagamento` (A-1, A-16 ii); sem `ChamadaAoProvedor` `cancelar_cobranca` com o alvo `:cancelamento_da_rodada` (A-4, A-5); a criação da tentativa `solicitada` executa (`criada`, A-6); `DID NOT RAISE PagamentoRecusado` (A-7); auditoria sem `pedidos_cancelados` (A-14); o cancelamento não espera o pedido de pagamento (A-15). **Passaram de primeira (regressão, registrados como tais):** A-2, A-3 (a parcela de A em P1 já nasce `pendente`), A-8, A-9 (a conferência de etapa da E11 já recusa), A-10 (as tarefas já filtram a etapa `pagamento`), A-11 (o spec já previa), A-12, A-13, A-16 (i) |
| Motivo `cancelamento_da_rodada` (migração 0013: `max_length` 20 → 30 e a restrição), cancelamento dos pedidos não pagos, agendamento das cobranças (tentativas `criada` e órfãs), `rodada_cancelada` em `pedir_pagamento`, auditoria | `de6bd01` | **18 passed**; suíte completa **2838 passed** |

## Decisões técnicas
- `SituacaoDoPedido.motivo_do_cancelamento` passou a 30 caracteres: o novo motivo tem 22.
- `pedir_pagamento` lê a etapa da rodada numa consulta própria depois da trava da situação (o `select_related` do `select_for_update` travaria também a rodada). A recusa vem logo depois de `nao_e_seu`.
- Os agendamentos não disparam a execução no commit: a tarefa periódica de chamadas as processa (infraestrutura 4.8).
- Acréscimo fora do texto das fatias, para o painel não quebrar com o motivo novo: `CANCELAMENTOS_POR_EXTENSO` ganhou "Cancelado (rodada cancelada)" (o texto da E12-06). O teste da tela é da E12-06.
- Auditoria: `pedidos_cancelados` (pedido e situação anterior), `pedidos_pagos` e `cobrancas` (alvo e `id_externo`).


## Parecer independente — agente 3 — 2026-11-01

Base auditada: `8e236e5`, branch `e12-implementacao`, comparada à E11 integrada em `d098654`. Funcional v1.7, infraestrutura v1.8, especificações e critérios das sete fatias lidos antes da avaliação da implementação. Conteúdo anterior preservado integralmente. Evidências, veredito da etapa e reproduções no [parecer consolidado E12-07](../E12-07/review.md).

**REPROVADO — R03 (bloqueador), em conjunto com E12-03.** A-1 a A-16 confrontados com código e testes. Composição, motivos anteriores, ausência de novos movimentos sem reembolso, tentativas/órfãs, apuração e aprovação conferidos. A regra 2 diz que só as situações da abertura vigente são travadas e que as anteriores só são lidas, mas E12-03 chama `reembolso_integral_do_pedido` para pedidos anteriores e trava suas situações depois das contas financeiras. A prova concorrente demonstra deadlock. Alinhar esse detalhamento técnico à ordem global antes de aprovar; não é necessária decisão comercial nova.

## Correção da revisão — agente 2 — 2026-11-01

**R03 — ordem das travas (E12-02 regra 2 reescrita; A-17 e A-18).**

- **Red** (`da9f6aa`, `uv run pytest tests/tecnicos/test_cancelamento_com_pedidos.py tests/tecnicos/test_cancelamento_com_reembolso.py`):
  - A-17 `test_cancelamento_espera_a_situacao_de_ciclo_anterior_antes_das_contas_do_livro`: a terceira conexão recebeu `OperationalError: could not obtain lock on row in relation "financeiro_contafinanceira"` (o cancelamento já tinha travado as contas);
  - A-18 `test_a_primeira_trava_de_situacao_alcanca_o_pedido_do_ciclo_anterior[True]`: "uma conta do livro veio antes"; `[False]`: a primeira trava de situação não alcançava X.
- **Green** (`8d1a899`): `_travar_as_situacoes(rodada)` em `apps/pedidos/cancelamento_da_rodada.py`, chamada logo depois das travas da E12-01 e da relida da etapa: uma consulta `select_for_update()` sobre `SituacaoDoPedido` com `pedido_id` em subconsulta dos pedidos de todas as aberturas da rodada (sem junção, para não travar `pedido` nem `abertura`), `order_by("pedido_id")`.
- **Resultado:** os dois arquivos, 43 passed.
- **Invariantes da ordem, conferidos no código e por teste:**
  - sincronização (`quitacao.py:236`): pagamento, situação, contas do livro; apuração (`apuracao.py:862`): travas da E11, situações, contas; reembolso (`reembolsos.py:87`): situação já travada, sem mudar a ordem;
  - A-18 confere que a transação do cancelamento (da primeira trava de conta de comprador em diante) não trava `PagamentoNoProvedor` nem `DestinoDoPagamento`, e que nenhuma conta do livro é travada antes da primeira trava de situação;
  - a consulta prévia sincroniza pagamentos por conta própria, antes da transação; por isso a conferência começa na primeira trava de conta de comprador.
- A trava das tentativas e chamadas (`agendar_cancelamento`, `agendar_chamada`) continua depois das situações, e `travar_contas` do reembolso continua por último.


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `5705e5d`, branch `e12-implementacao`, correções desde `4370b11`. Adendos `0fdfe8f`/`f429fc6` lidos e confrontados com o código, os critérios e os registros Red/Green. Conteúdo anterior preservado. Evidências completas no [parecer consolidado E12-07](../E12-07/review.md).

**APROVADO — R03 encerrado nesta fatia.** Conferidos A-17/A-18: `_travar_as_situacoes` alcança todos os pedidos de todas as aberturas, ordenados por `pedido_id`, antes de qualquer conta do livro, nas duas indicações. A consulta não inclui junções que travem pagamentos ou destinos. Só a abertura vigente tem estados alterados. A regra 2 e a decisão técnica antiga foram alinhadas à ordem global. Prova independente da corrida passa com a adaptação de pausa documentada no consolidado.
