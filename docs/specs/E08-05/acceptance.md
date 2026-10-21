# E08-05 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05): Red com caminhos explícitos de arquivos inteiros, sem `-k`, e tabela de cobertura do Red antes do Green. Os testes que usam o simulador declaram os dois bancos (E07-R03).

**Arranjo comum, salvo indicação:**

- `T0` = 2026-11-02 13:00 UTC, então `T0 + 24h` = 2026-11-03 13:00 UTC e `T0 + 48h` = 2026-11-04 13:00 UTC;
- os pedidos `X` (de A) e `Y` (de B) em `aguardando_pagamento`;
- fixture `simulador_pagamentos` ativa.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 4.3 | positivo | a abertura | as funções da linha do tempo em `T0 + 24h − 1 ms`, `T0 + 24h`, `T0 + 48h − 1 ms`, `T0 + 48h` e `T0 + 48h + 1 ms` | `aceita_tentativas`: verdadeiro, falso, falso, falso, falso; `em_margem`: falso, verdadeiro, verdadeiro, verdadeiro, falso; `pode_iniciar_apuracao`: falso, falso, falso, verdadeiro, verdadeiro |
| A-2 | T-4 (parte), cenário 27 | positivo | X e Y pagos antes de `T0 + 1h` | `pode_iniciar_apuracao` em `T0 + 48h − 1 ms` e em `T0 + 48h` | falso e verdadeiro; a rodada continua `pagamento` nos dois; nada foi apurado |
| A-3 | Infra 4.3, L-2 | positivo | X com uma tentativa criada e pendente; Y com uma tentativa paga | `bloquear_tentativas_vencidas_agora()` em `T0 + 24h`; depois `processar_chamadas()` | devolve 1; uma chamada `cancelar_cobranca` com alvo `t<tentativa de X>:prazo`; depois do processamento, a cobrança de X `cancelado`; nenhuma chamada para Y |
| A-4 | Spec da fatia | positivo | o A-3 depois do processamento | a tarefa de bloqueio de novo, em `T0 + 24h + 1 min` | devolve 0; nenhuma chamada nova |
| A-5 | Spec da fatia | negativo | o A-3 com o cancelamento recusado definitivamente (`RecusaDoProvedor` por `falhar_proximas` de teste) e a cobrança ainda pendente | a tarefa de bloqueio de novo, uma hora depois | nenhuma chamada nova (a `falhou` existente conta); a chamada continua `falhou` |
| A-6 | Spec da fatia | positivo | a tarefa de bloqueio em `T0 + 24h − 1 ms` | a execução | devolve 0; nada agendado |
| A-7 | Cenário 12, T-1 | positivo | a tarefa de bloqueio parada | A tenta pagar em `T0 + 24h + 5 min` | recusado com `prazo_encerrado` (E08-03); nenhuma tentativa |
| A-8 | Cenário 12, Spec §7 | negativo | relógio em `T0 + 30h` (margem) | um comprador C tenta adicionar interesse; A tenta reduzir e aumentar; A tenta pagar | interesses recusados com 409; pagamento recusado com `prazo_encerrado`; nenhum pedido muda |
| A-9 | Cenário 12, Spec §7 | positivo | relógio em `T0 + 49h`; as duas tarefas e `processar_chamadas()` executadas | inspeciono | a rodada continua `pagamento`; X e Y continuam `aguardando_pagamento`; nenhuma auditoria de apuração ou cancelamento |
| A-10 | Infra 4.3, L-6 | positivo | X com uma cobrança aprovada às `T0 + 23h`, sem aviso entregue e sem registro no sistema | `reconsultar_pagamentos_da_margem_agora()` em `T0 + 25h` | devolve 2; X `pago`, com `quitado_em` `T0 + 23h`; um `pagamento_confirmado` |
| A-11 | Spec da fatia | negativo | o arranjo do A-10, em `T0 + 23h59` e em `T0 + 48h + 1 ms` | a função da margem | devolve 0 nos dois; nada consultado |
| A-12 | Spec da fatia | negativo | `indisponivel()` em `T0 + 25h` | a função da margem | devolve 0; um log `warning` por pedido, com o motivo `indisponivel`; nada gravado nos pedidos |
| A-13 | E08-04 | positivo | um `PagamentoNoProvedor` `aprovado` da referência de X, sem destino (o receptor foi desligado por `monkeypatch` na sincronização) | a função da margem em `T0 + 25h` | o destino é decidido: X `pago` |
| A-14 | T-5, cenário 28, P-7 | negativo | — | varro as rotas e os formulários; o administrador faz `POST` em `rodadas_fechamento_prorrogar` com a rodada em `pagamento`, com um prazo futuro qualquer | nenhuma rota, campo de formulário ou serviço muda `T0`, o prazo de pagamento ou a margem; o `POST` recebe 409 com "Só um fechamento em andamento pode ser prorrogado."; nada muda; em outra rodada em `fechamento`, a prorrogação continua aceita |
| A-15 | T-5 | negativo | a abertura | `save()`, `update()` e SQL direto em `AberturaDoPagamento.t0` | recusados (E08-02 A-11); `prazo_de_pagamento` e `fim_da_margem` não mudam |
| A-16 | Infra 4.3, Spec §13 | positivo | X pago em `T0 + 2h`; Y pago em `T0 + 30h`; Z de C com tentativa aberta; W de D sem tentativa; V de E cancelado por suspensão; U de G com a chamada de criação `pendente` e `ultimo_erro` `indisponivel`; uma devolução por duplicidade em Y | o administrador abre a página de estoque em `T0 + 31h` | a linha do tempo com "Prazo de pagamento até 03/11/2026 às 10:00. Margem até 04/11/2026 às 10:00."; as situações "Pago no prazo" (X), "Pago na margem" (Y), "Pagamento pendente" (Z), "Não pago" (W), "Cancelado (suspensão)" (V) e "Sem resposta do provedor" (U); a lista de devoluções com "pagamento em duplicidade" e o valor; nenhum formulário de alteração |
| A-17 | E02-10, Spec §2 | negativo | o A-16 | um comprador e um fornecedor abrem a página | recusados pela política; nenhuma informação de pedidos exibida |
| A-18 | E06-05, E07-04 | positivo | — | inspeciono o registro de tarefas do Procrastinate | `bloquear_tentativas_vencidas` (a cada minuto) e `reconsultar_pagamentos_da_margem` (`*/10 * * * *`) existem, com `queueing_lock` |
| A-19 | Spec da fatia | negativo | duas aberturas vencidas; a primeira com `agendar_cancelamento` levantando `RuntimeError` por `monkeypatch` | a tarefa de bloqueio | a segunda é processada; log com o id da primeira e `RuntimeError` |
| A-20 | T-7 | concorrência | a cobrança de X aprovada no simulador em `T0 + 23h59`, sem aviso entregue | (i) a tarefa de bloqueio e `processar_chamadas()` em `T0 + 24h`, depois o aviso; (ii) o aviso primeiro, depois o bloqueio e o processamento; (iii) as duas sincronizações ao mesmo tempo, em threads | nos três: X `pago`, com `quitado_em` `T0 + 23h59`; um destino `quita`; um `pagamento_confirmado`; nenhuma devolução |
| A-21 | T-7 | concorrência | a cobrança de X pendente, sem aprovação | o bloqueio e um aviso de outra mudança chegam ao mesmo tempo | a cobrança `cancelado`; X `aguardando_pagamento`; nenhum destino |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-13, A-15, A-18, A-19 | `tests/tecnicos/test_pedidos_prazos.py` |
| A-7, A-8, A-9 | também marcados `acceptance`, com o comentário `cenário 12` |
| A-2 | também marcado `acceptance`, com o comentário `cenário 27 (verificação de tempo)` |
| A-14 | também marcado `acceptance`, com o comentário `T-5, cenário 28` |
| A-16, A-17 | `tests/tecnicos/test_pedidos_acompanhamento.py` |
| A-20, A-21 | `tests/tecnicos/test_pedidos_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`; A-20 marcado `acceptance`, com o comentário `T-7`) |

## Correção E08-R01 e E08-R03 — reconsulta de todos os pedidos e bloqueio por pagamento (2026-10-21)

Valem as regras de prevenção do início deste arquivo e as da correção E08-R06 (E08-02, `spec.md`). O Red é observável no código atual: as provas R01 e R03 do parecer falham.

**Cobrança órfã de teste:** uma cobrança criada no simulador com `criar_cobranca` (um helper de teste), com a referência do pedido e uma chave que não é de nenhuma tentativa. Ela representa a resposta de criação perdida.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-22 | Correção R01, Infra 4.3, §8.3 | positivo | tentativa 1 de `X` criada, expirada e sincronizada; tentativa 2 criada, aprovada às `T0 + 3h` e sincronizada, o que deixa `X` `pago`; às `T0 + 25h`, a cobrança 1 aprovada no simulador, sem aviso entregue | `reconsultar_pagamentos_da_margem_agora()` às `T0 + 25h` | os destinos de `X` são exatamente `quita` (cobrança 2) e `devolucao` com `duplicidade` (cobrança 1); `X` continua `pago`, com o `quitado_em` original; um `pagamento_confirmado` só |
| A-23 | Correção R01 | positivo | `X` `pago`, `Y` `aguardando_pagamento` e `V` (de E) `cancelado`, todos da mesma abertura | a função da margem às `T0 + 25h` | devolve 3; o simulador registrou uma `buscar_por_referencia` para cada um dos três |
| A-24 | Correção R03, Infra 4.3 | positivo | uma cobrança órfã de teste de `Y`, criada às `T0 + 23h` e `pendente` | a função da margem às `T0 + 25h`; depois `bloquear_tentativas_vencidas_agora()`; depois `processar_chamadas()`; depois o bloqueio de novo | a reconsulta registra o pagamento `pendente`; o bloqueio devolve 1 e agenda `cancelar_cobranca` com alvo `p<pagamento>:prazo` e o `id_externo`; o processamento deixa a cobrança `cancelado` no simulador e no registro; o segundo bloqueio devolve 0 |
| A-25 | Correção R03 | negativo | o A-24 depois da reconsulta, com uma chamada `cancelar_cobranca` já existente para esse `id_externo` com alvo `t<tentativa>:recuperacao:1`: (i) `pendente`; (ii) `falhou` | o bloqueio | nos dois, devolve 0 e não agenda nada |
| A-26 | Correção R03 | positivo | uma cobrança órfã de teste pendente para `X` (`pago`) e outra para `V` (`cancelado`), registradas pela reconsulta | o bloqueio às `T0 + 25h` e `processar_chamadas()` | as duas são canceladas, com alvos `p<pagamento>:prazo`; `X` continua `pago`; `V` continua `cancelado`; nenhum destino novo |
| A-27 | Correção R03, prova do parecer | positivo | às `T0 + 23h59min30s`, A pede o pagamento de `Y`; `falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=True)`; `processar_chamadas()` | às `T0 + 24h01min`: `processar_chamadas()`, a função da margem, o bloqueio e `processar_chamadas()` | a cobrança `cancelado` no simulador; a tentativa `nao_criada` com `prazo_encerrado`; o pagamento conhecido; uma única chamada `cancelar_cobranca` para o `id_externo`, a de recuperação; o bloqueio não agendou outra |
| A-28 | Correção R01, R03 | negativo | o arranjo do A-24, com o relógio em `T0 + 23h59min` | a função da margem e o bloqueio | a margem devolve 0 e nada é consultado; o bloqueio devolve 0 e nada é agendado (fora da margem e antes do prazo) |

## Mapeamento para testes da correção

| Critério | Arquivo de teste |
|---|---|
| A-22 a A-28 | `tests/tecnicos/test_pedidos_prazos.py` |
| A-22 | também marcado `acceptance`, com o comentário `§8.3 duplicidade na margem` |
