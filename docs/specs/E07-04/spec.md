# E07-04 — Chamadas pendentes ao provedor

Fatia 4 de 6 da milestone **E07 — Simulador de pagamentos e integração**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Uma chamada ao provedor não pode ficar presa à requisição do usuário nem se perder se o processo cair (infraestrutura 4.2, §15). A regra é:

- a chamada é registrada numa tabela, na mesma transação que muda o estado do sistema;
- a chave de idempotência é gravada antes da chamada;
- uma tarefa executa a chamada e repete as falhas temporárias com a mesma chave.

Esta fatia entrega a tabela, o registro de operações, a tarefa e a primeira operação: `consultar_pagamento`, que a E07-05 usa depois de cada aviso. As operações de criar e cancelar cobrança entram na E08, e a de estorno na E10, todas nesta mesma tabela.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §15 | "Processamento retomável após interrupção, sem aplicar transição ou estorno duas vezes." Idempotência em ações críticas e webhooks. Logs e alertas para pagamentos sem conciliação. |
| Infraestrutura 2 | Procrastinate processa as chamadas pendentes ao provedor. |
| Infraestrutura 4.2 | "Toda chamada ao provedor é registrada numa tabela na mesma transação que muda o estado, e executada por uma tarefa." Chave de idempotência gravada antes da chamada e reaproveitada nas novas tentativas. O webhook só avisa; uma tarefa consulta o pagamento antes de aplicar qualquer estado. |
| Infraestrutura 5 | `UNIQUE` em chaves de idempotência. |
| E04-03 | Precedente: processamento com `select_for_update(skip_locked=True)`, tentativas registradas e tarefa periódica com `queueing_lock`. |
| E06-05 | Precedente: falha inesperada de um item não interrompe os outros; o log tem o identificador e o tipo da exceção. |
| E07-01 a E07-03 | Provedor, erros, ambiente e `sincronizar_pagamento`. |

## Escopo

**Dentro:**

- O modelo `ChamadaAoProvedor`.
- `agendar_chamada` e o registro de operações.
- `processar_chamadas` e a tarefa periódica.
- A operação `consultar_pagamento`.

**Fora:**

- `criar_cobranca` e `cancelar_cobranca` (E08) e `estornar` (E10).
- O alerta de chamada parada ou falha (E15). Aqui elas ficam visíveis na tabela e no log.

## Decisões técnicas

- **Mesmo modelo de execução da E04-03.** Cada chamada é tentada com a linha travada (`select_for_update(skip_locked=True)`), numa transação própria. O resultado é aplicado na mesma transação. Se o processo cair durante a chamada, a transação é desfeita, a linha volta a ficar livre e a próxima execução repete com a mesma chave. A chave torna a repetição segura no provedor (E07-01 A-11).
- **Agendamento idempotente.** Há no máximo uma chamada `pendente` por (operação, alvo), garantido por `UNIQUE` parcial. Agendar de novo devolve a pendente existente. Por exemplo, dez avisos do mesmo pagamento geram uma consulta.
- **Chave gerada no agendamento:** `uuid4().hex`, ou a chave informada por quem agenda. A E08 informa a chave da cobrança (pedido, ciclo e tentativa). A chave é única na tabela.
- **Intervalos das novas tentativas**, depois de falha temporária: 1, 5, 15 e 60 minutos, e depois a cada 60 minutos. Não há limite de tentativas para falhas temporárias: desistir de uma consulta poderia deixar dinheiro recebido sem registro (§8.3). A chamada parada há muito tempo é o alerta da E15.
- **Operação registrada:** cada operação tem `executar(provedor, chamada) -> resultado`, que fala com o provedor, e `concluir(chamada, resultado)`, que aplica o resultado no banco, na mesma transação. Opcionalmente, tem `falhou(chamada, erro)`, chamada na falha definitiva.
- **A tarefa nunca decide regra de negócio.** Ela só executa, repete e registra. O que a resposta significa fica no `concluir` da operação.

## Regras

**Modelo `ChamadaAoProvedor`** (`apps/pagamentos/models.py`):

| Campo | Regra |
|---|---|
| `operacao` | nome registrado (`consultar_pagamento` nesta fatia) |
| `alvo` | texto, como o `id_externo` ou a referência |
| `parametros` | JSON, sem dados pessoais |
| `chave_idempotencia` | texto, único |
| `provedor`, `ambiente` | o provedor e `settings.AMBIENTE` no agendamento |
| `situacao` | `pendente`, `concluida` ou `falhou` |
| `tentativas` | inteiro, começa em 0 |
| `proxima_em` | instante; no agendamento, igual a `agora()` |
| `criada_em`, `concluida_em` | instantes |
| `ultimo_erro` | código curto (por exemplo, `indisponivel`, `nao_encontrado`, ou o código da recusa), sem mensagem livre |

Restrições: `UNIQUE (operacao, alvo) WHERE situacao = 'pendente'` e `CHECK` dos valores de `situacao`.

**Agendamento** (`apps/pagamentos/chamadas.py`):

```
agendar_chamada(operacao: str, alvo: str, *, parametros: dict | None = None, chave_idempotencia: str | None = None) -> ChamadaAoProvedor
```

- Exige transação aberta (`TransactionManagementError`) e operação registrada (`ValueError`).
- Se já existe uma chamada `pendente` com a mesma operação e o mesmo alvo, devolve essa chamada sem alterá-la.
- Caso contrário, cria a chamada `pendente`, com `proxima_em = agora()`.
- Agendamentos concorrentes do mesmo par resultam numa chamada só. O conflito da restrição é tratado com uma releitura, sem `IntegrityError` para quem chamou.

**Execução:**

```
processar_chamadas(*, limite: int = 100) -> int
```

Para cada chamada `pendente` com `proxima_em <= agora()`, em ordem de `proxima_em` e `id`, até `limite`, numa transação por chamada:

1. Trava a linha com `skip_locked`. Se outra execução já a travou, pula.
2. Chama `executar(obter_provedor(), chamada)`.
3. **Sucesso:** `concluir(chamada, resultado)`; depois, `situacao = concluida`, `tentativas + 1`, `concluida_em = agora()`.
4. **`ProvedorIndisponivel`:** `tentativas + 1`, `ultimo_erro = "indisponivel"` e `proxima_em` pelo intervalo da tentativa.
5. **`RecusaDoProvedor(codigo)`:** `situacao = falhou`, `ultimo_erro = codigo`, `concluida_em` e `falhou(chamada, erro)`, se a operação tiver.
6. **Qualquer outra exceção** (de `executar` ou de `concluir`): a transação da chamada é desfeita, e a chamada fica como estava, para a próxima execução. O log registra o id da chamada, a operação e o tipo da exceção, sem parâmetros. As outras chamadas continuam.
7. Devolve quantas chamadas foram tentadas.

O instante de `agora()` é lido depois da trava.

**Tarefa** (`apps/pagamentos/tarefas.py`): `processar_chamadas_ao_provedor`, periódica a cada minuto, com `queueing_lock` igual ao nome, como as tarefas da E04-03 e da E06-05.

**Operação `consultar_pagamento`:**

- `alvo`: o `id_externo`. `parametros`: opcionalmente, `aviso_recebido_em` (ISO 8601 em UTC) e `origem` (`aviso` ou `tarefa`; padrão `tarefa`).
- `executar`: `provedor.consultar_pagamento(alvo)`.
- `concluir`: `sincronizar_pagamento(resultado, origem=<origem>, aviso_recebido_em=<parâmetro>)` (E07-03).
- `PagamentoNaoEncontrado`:
  - antes de 24 horas desde `criada_em`, é tratado como falha temporária, com `ultimo_erro = "nao_encontrado"`, porque pode ser atraso de consistência (L-6);
  - a partir de 24 horas, a chamada fica `falhou`, com `ultimo_erro = "nao_encontrado"`.

  O limite de 24 horas usa `prazo_encerrado` (E01-03).

**Log:** `"Chamada ao provedor <id>: <operacao> <resultado>"`, com o resultado `concluida`, `nova tentativa em <instante>` ou `falhou <codigo>`. Sem parâmetros nem alvo além do `id_externo`.

## Interfaces

- `apps/pagamentos/models.py`: `ChamadaAoProvedor`, com a migração.
- `apps/pagamentos/chamadas.py`: `agendar_chamada`, `processar_chamadas`, `registrar_operacao` (ou um decorador equivalente), `INTERVALOS` e a operação `consultar_pagamento`.
- `apps/pagamentos/tarefas.py`: a tarefa periódica.
- `tests/apoio`: uma operação de teste, `criar_cobranca_de_teste`, registrada só nos testes, que chama `provedor.criar_cobranca` com a chave da chamada e grava o `id_externo` devolvido numa tabela de apoio. Ela prova a repetição com a mesma chave antes de a E08 existir.

## Invariantes

- Toda chamada ao provedor feita pela tarefa usa a chave gravada na linha, igual em todas as tentativas.
- Há no máximo uma chamada `pendente` por (operação, alvo).
- Uma chamada `concluida` ou `falhou` nunca é executada de novo.
- Uma chamada nunca é executada por duas execuções ao mesmo tempo.

## Casos-limite e concorrência

- **Processo cai depois de o provedor aceitar e antes de gravar:** a próxima execução repete com a mesma chave, e o provedor devolve o mesmo resultado (simulado com `falhar_proximas(..., depois_de_executar=True)`).
- **Duas tarefas ao mesmo tempo** (o `queueing_lock` falhou ou há dois workers): cada chamada é executada por uma só, por causa do `skip_locked`.
- **Provedor fora do ar por horas:** a chamada continua `pendente`, com as tentativas e o próximo instante gravados; volta a funcionar quando o provedor volta.
- **Erro inesperado no `concluir`:** nada da chamada é gravado, e as outras chamadas do lote são processadas.

## Dependências e decisões em aberto

- Depende de E04-03 (padrão da tarefa), E07-01, E07-02 e E07-03.
- Sem decisões em aberto.
