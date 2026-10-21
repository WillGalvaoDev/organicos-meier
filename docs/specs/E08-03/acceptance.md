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

## Correção E08-R02 e E08-R03 — criação de cobrança que não pode mais ser paga (2026-10-21)

Valem as regras de prevenção do início deste arquivo e as da correção E08-R06 (E08-02, `spec.md`). Isso inclui as duas linhas por critério de concorrência: o verde funcional sem a proteção e o Red da corrida. O Red é observável no código atual. As provas R02 e R03 do parecer mostram uma cobrança `pendente` sem cancelamento.

Arranjo comum da fatia. "Parar a criação no provedor" quer dizer um envoltório de teste no provedor configurado: ele chama o simulador de verdade e depois segura a thread num `threading.Event`, com prazo de espera e falha por asserção.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-21 | Correção R02 | negativo | o A-1 (tentativa `solicitada`); depois, a situação de `X` passa a `cancelado` pela suspensão de A (E08-06) | `processar_chamadas()` | a chamada `falhou` com `pedido_cancelado`; a tentativa `nao_criada` com `pedido_cancelado`; nenhuma `CobrancaSimulada`; o simulador registrou uma `buscar_por_referencia` e nenhuma `criar_cobranca` |
| A-22 | Correção R02 | negativo | tentativa 1 criada e expirada; tentativa 2 `solicitada`; depois, a cobrança 1 aprovada no simulador e sincronizada, o que deixa `X` `pago` | `processar_chamadas()` | a chamada da tentativa 2 `falhou` com `pedido_pago`; a tentativa 2 `nao_criada`; uma `CobrancaSimulada` só, a da tentativa 1 |
| A-23 | Correção R03 | positivo | relógio em `T0 + 23h59min30s`; o A-1; `falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=True)` | `processar_chamadas()`; relógio em `T0 + 24h01min`; `processar_chamadas()` duas vezes | a primeira deixa a cobrança criada no simulador e a chamada `pendente`; na segunda: chamada `falhou` com `prazo_encerrado`, tentativa `nao_criada` com `prazo_encerrado`, o pagamento registrado como `pendente`, uma chamada `cancelar_cobranca` com alvo `t<tentativa>:recuperacao:1` e o `id_externo` da cobrança, e um log `warning` "Cobrança sem tentativa encontrada na recusa da criação"; na terceira: a cobrança `cancelado` no simulador e no registro; uma `CobrancaSimulada` só, nenhuma criada depois do prazo |
| A-24 | Correção R03 | positivo | o arranjo do A-23, mas a primeira execução falha por exceção local no `concluir` (`RuntimeError` por `monkeypatch`, só uma vez) depois de o simulador criar a cobrança | as mesmas execuções do A-23 | a primeira desfaz a chamada, que fica `pendente` com o contador inalterado; o resto como no A-23: a órfã é encontrada e cancelada |
| A-25 | Correção R03 | negativo | o A-1, com o pedido cancelado como no A-21 | (i) `indisponivel()` e `processar_chamadas()`; depois `normalizar()` e `processar_chamadas()` um minuto depois; (ii) a busca levanta `RecusaDoProvedor("x")` (falha de teste) | (i) a primeira deixa a chamada `pendente` com `indisponivel` e a tentativa `solicitada`; a segunda termina como o A-21; (ii) a chamada `falhou` com `pedido_cancelado`, a tentativa `nao_criada` e um log `warning` com a tentativa e o código `x` |
| A-26 | Correção R03, §8.3 | positivo | o arranjo do A-23, com a cobrança órfã aprovada no simulador às `T0 + 24h00min30s`, depois do prazo | a segunda execução do A-23 | o `falhou` sincroniza o pagamento `aprovado`; pela E08-04, criado antes de `T0 + 24h` e aprovado antes de `T0 + 48h`, ele quita: destino `quita`, `X` `pago` com `quitado_em` `T0 + 24h00min30s`, um `pagamento_confirmado`; nenhum cancelamento agendado, porque não há órfã pendente |
| A-27 | Correção R02 | concorrência | o arranjo do A-22 antes da aprovação: tentativa 1 expirada e tentativa 2 `solicitada`; a criação da tentativa 2 parada no provedor, depois de criar | outra thread aprova a cobrança 1 no simulador e a sincroniza, o que quita `X` (E08-04), e termina; depois a criação é liberada | a outra thread termina sem esperar a criação; a tentativa `criada`; uma chamada `cancelar_cobranca` com alvo `t<tentativa>:pedido_pago`; depois de `processar_chamadas()`, a cobrança `cancelado` |
| A-28 | Correção R02 | positivo | a tentativa `solicitada` do A-21, antes do processamento; e a `nao_criada` com `pedido_cancelado` depois dele | A abre `/pedidos/<X>/` | a página mostra "Cancelado" e nenhuma das mensagens "Estamos gerando a sua cobrança…" e "Não foi possível gerar a cobrança antes do fim do prazo." |

O cancelamento com a moderação durante a criação (suspensão e remoção) está na E08-06, A-11 reescrito e A-13 a A-15.

## Mapeamento para testes da correção

| Critério | Arquivo de teste |
|---|---|
| A-21 a A-26 | `tests/tecnicos/test_pedidos_tentativas.py` |
| A-27 | `tests/tecnicos/test_pedidos_concorrencia.py` |
| A-28 | `tests/tecnicos/test_pedidos_telas_comprador.py` |

## Correção E08-R06

O A-19 desta fatia recebe o tratamento da seção "Correção E08-R06" de `docs/specs/E08-02/spec.md`.
