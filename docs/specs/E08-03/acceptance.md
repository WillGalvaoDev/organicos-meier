# E08-03 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05): Red com caminhos explícitos de arquivos inteiros, sem `-k`, e tabela de cobertura do Red antes do Green. Os testes que usam o simulador declaram os dois bancos (E07-R03).

**Arranjo comum, salvo indicação:**

- abertura com `T0` = 2026-11-02 13:00 UTC, então `T0 + 24h` = 2026-11-03 13:00 UTC;
- o pedido `X` do comprador ativo A, total R$ 94,35, em `aguardando_pagamento`;
- relógio em 2026-11-02 14:00 UTC;
- fixture `simulador_pagamentos` ativa.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 4.2 | positivo | — | `pedir_pagamento(A, X)` | uma tentativa `solicitada`, número 1, chave `om-p<X>-t1`, referência `om-c<ciclo>-p<X>`; uma `ChamadaAoProvedor` `criar_cobranca` com alvo `t<tentativa>`, a mesma chave e `parametros` `{"tentativa": <id>}`; nenhuma chamada ao simulador ainda; auditoria `pedido.pedir_pagamento` |
| A-2 | Infra 4.2, 4.5 | positivo | o A-1 | `processar_chamadas()` | uma `CobrancaSimulada` com a chave, a referência, o valor 94,35, a descrição "Orgânicos Méier — pedido <X>" e `expira_em` 2026-11-03 13:00 UTC; a tentativa `criada`, com o `id_externo`, `dados_para_pagar` com o código Pix e `criada_em` 14:00; um `PagamentoNoProvedor` `pendente` |
| A-3 | Spec da fatia | positivo | o A-2 | `pedir_pagamento(A, X)` de novo | devolve a mesma tentativa; nenhuma tentativa nem chamada nova |
| A-4 | Spec da fatia | positivo | o A-2; `expirar(<id>)` no simulador e a consulta processada (o registro fica `expirado`) | `pedir_pagamento(A, X)` | uma tentativa número 2, com a chave `om-p<X>-t2` e a mesma referência; uma chamada nova |
| A-5 | T-1, Infra 4.3 | positivo e negativo | sem tentativas; a tarefa de bloqueio (E08-05) não roda | `pedir_pagamento` com o relógio em `T0 + 24h − 1 ms`, em `T0 + 24h` e em `T0 + 24h + 1 ms` | o primeiro cria a tentativa; os outros levantam `PagamentoRecusado("prazo_encerrado")`, com a mensagem "O prazo para pagar este pedido terminou em 03/11/2026 às 10:00 (horário de Brasília)."; nenhuma tentativa nem chamada nesses dois |
| A-6 | Infra 4.3 | positivo | a tentativa do primeiro caso do A-5 | `processar_chamadas()` com o relógio em `T0 + 24h` | a chamada `falhou` com `prazo_encerrado`; a tentativa `nao_criada` com `prazo_encerrado`; nenhuma `CobrancaSimulada`; o detalhe mostra "Não foi possível gerar a cobrança antes do fim do prazo." |
| A-7 | Spec da fatia | negativo | — | `pedir_pagamento` com o pedido `pago`; com o pedido `cancelado`; com A suspenso; pelo comprador B, que não é dono | `PagamentoRecusado` com `pedido_pago`, `pedido_cancelado`, `conta_inativa` e `nao_e_seu`, cada um com a sua mensagem; nada gravado |
| A-8 | Infra 4.2 | positivo | o A-1; `indisponivel()` | `processar_chamadas()`; depois `normalizar()` e `processar_chamadas()` um minuto depois | a primeira deixa a chamada `pendente` e a tentativa `solicitada`; a segunda cria a cobrança; uma `CobrancaSimulada` só, com a chave |
| A-9 | Infra 4.2, E07-R03 | positivo | o A-1; `falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=True)` | `processar_chamadas()` duas vezes, com um minuto de intervalo | uma `CobrancaSimulada` só; a tentativa `criada` com o `id_externo` dessa cobrança |
| A-10 | Spec da fatia | positivo | o A-2 | `agendar_cancelamento(tentativa, "prazo")` duas vezes, numa transação; depois `processar_chamadas()` | uma chamada `cancelar_cobranca` com alvo `t<tentativa>:prazo` e `{"id_externo": ...}`; a cobrança `cancelado` no simulador; o registro `cancelado`; com o registro já terminal, um novo `agendar_cancelamento` não agenda nada |
| A-11 | Infra 4.3, L-2 | positivo | o A-2; `aprovar_no_cancelamento(<id>)` | o cancelamento e `processar_chamadas()` | o registro fica `aprovado`, com o `aprovado_em` do simulador (a decisão sobre o pedido é da E08-04) |
| A-12 | E07-04 | negativo | uma operação de teste que levanta `FalhaDefinitiva("x")` no `executar` | `processar_chamadas()` | a chamada `falhou`, com `ultimo_erro` `x` e `concluida_em`; o `falhou` da operação chamado uma vez; nenhuma nova tentativa depois |
| A-13 | Spec da fatia | positivo | o A-1 | inspeciono os `on_commit` registrados e a fila do Procrastinate depois do commit | um pedido de execução de `processar_chamadas_ao_provedor` depois do commit; com a tarefa já na fila, a segunda tentativa de enfileirar é ignorada sem erro; dentro de uma transação desfeita, nada é enfileirado |
| A-14 | Tela, Spec §13 | positivo | o A-2 | A abre `/pedidos/` e `/pedidos/<X>/` | a lista tem o fornecedor, o total e "Aguardando pagamento até 03/11/2026 às 10:00"; o detalhe tem os itens, os quatro valores, o prazo com "Esse prazo de 24 horas não é prorrogado.", o código Pix e o aviso de confirmação; nenhum botão "Pagar com Pix", porque há tentativa aberta |
| A-15 | Tela | positivo | sem tentativa | A abre o detalhe e envia "Pagar com Pix" | o botão aparece; o `POST` redireciona para o detalhe, que mostra "Estamos gerando a sua cobrança…" |
| A-16 | Spec §2, E02-10 | negativo | X de A | B abre `/pedidos/<X>/` e faz `POST /pedidos/<X>/pagar/`; um anônimo e um fornecedor tentam as três rotas; A suspenso faz o `POST` | 404 para B nos dois; anônimo e fornecedor recusados pela política; A suspenso recusado pela política `comprador_ativo`, sem tentativa; a varredura acusa as três rotas com as políticas `comprador`, `comprador` e `comprador_ativo` |
| A-17 | Spec §2 | positivo | A suspenso, com um pedido pago e outro cancelado | A abre `/pedidos/` e os detalhes | vê os dois, com as situações, e nenhum botão de pagar |
| A-18 | Spec da fatia | negativo | o log (`caplog`) e a auditoria dos critérios A-1 a A-11 | inspeciono | nenhuma mensagem nem auditoria contém o código Pix (`SIMULADO-`), e-mail ou nome do comprador |
| A-19 | Spec da fatia | concorrência | — | duas threads fazem `pedir_pagamento(A, X)` ao mesmo tempo, com a primeira segurando a transação depois de criar a tentativa até a segunda aparecer esperando (prazo de espera com falha por asserção) | uma tentativa; uma chamada; as duas devolvem a mesma tentativa |
| A-20 | Spec da fatia | concorrência | o A-2; uma chamada `cancelar_cobranca` em execução, parada no `executar` | outra thread trava a `SituacaoDoPedido` de X e agenda `agendar_cancelamento(tentativa, "suspensao")` | a segunda thread não espera a primeira (alvo diferente) e termina antes; as duas chamadas existem; nenhum impasse |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-13, A-18 | `tests/tecnicos/test_pedidos_tentativas.py` |
| A-5 | também marcado `acceptance`, com o comentário `T-1` |
| A-14 a A-17 | `tests/tecnicos/test_pedidos_telas_comprador.py` e `tests/tecnicos/test_permissoes_politica_rotas.py` (teste existente) |
| A-19, A-20 | `tests/tecnicos/test_pedidos_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
