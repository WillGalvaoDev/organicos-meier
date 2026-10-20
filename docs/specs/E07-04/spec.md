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

## Correção E07-R01, R02 e R03 (2026-10-20)

Parecer: `docs/specs/E07-01/review.md`, sobre `d6e4d20`.

### R01 — aviso absorvido por uma consulta em andamento

**Diagnóstico.** A tarefa trava a chamada pendente e consulta o provedor. Até a tarefa confirmar, a linha continua `pendente` para as outras conexões. Um aviso que chega nesse intervalo chama `agendar_chamada`, que lê a pendente sem trava e a devolve. A tarefa conclui com a resposta obtida antes do aviso, e o aviso fica sem nenhuma consulta posterior.

O revisor reproduziu o caso: o provedor está `aprovado`, o registro continua `pendente` e a única chamada está concluída. Eu especifiquei a coalescência ("devolve a pendente existente") sem distinguir a chamada que ainda não começou da que já está em execução.

**Regra.** A coalescência só acontece com uma chamada que ainda vai consultar o provedor depois de quem agendou:

1. `agendar_chamada` trava a chamada pendente do par com `select_for_update()`, **sem** `skip_locked` e sem `nowait`. Se uma execução da tarefa está com a linha travada, o agendamento espera essa execução terminar.
2. Depois da espera, a condição `situacao = 'pendente'` é conferida na versão nova da linha. É o comportamento do Postgres em `READ COMMITTED`.
   - Se a chamada foi concluída ou falhou, não há pendente, e o agendamento cria uma chamada nova, que vai consultar depois.
   - Se a chamada continua pendente (falha temporária, ou erro inesperado desfeito), o agendamento a devolve, e ela ainda vai consultar depois.
3. Quando encontra a pendente, quem agendou fica com a trava até o fim da própria transação. Nesse tempo, `processar_chamadas` pula a chamada (`skip_locked`) e a tenta numa execução seguinte. Assim, a consulta sempre acontece depois que o agendamento terminou.
4. O conflito da restrição única na criação continua tratado com releitura, agora também com `select_for_update()`.

A restrição `UNIQUE (operacao, alvo) WHERE situacao = 'pendente'` e a idempotência continuam iguais, e os critérios A-1 a A-16 continuam valendo.

**Invariante nova.** Nenhum agendamento é absorvido por uma execução que já consultou o provedor. A chamada que `agendar_chamada` devolve só executa `executar` depois que a transação de quem agendou termina.

**Custo e limites.**

- **Espera.** O agendamento pode esperar a execução em andamento da mesma chamada. No simulador, essa execução termina logo. Com o provedor real (fase 2a), o tempo máximo da chamada ao provedor limita a espera, e esse tempo é definido junto com a integração real.
- **Ordem das travas.** A execução trava a chamada e, dentro de `concluir`, as linhas que a operação usa. Quem agenda o mesmo par (operação, alvo) dentro de uma transação que já trava essas mesmas linhas pode entrar em impasse com uma execução em andamento. O Postgres detecta o impasse e desfaz uma das transações, sem efeito duplicado. Mesmo assim, as operações da E08 e da E10 devem evitá-lo: ou agendam antes de travar as linhas que o `concluir` trava, ou usam um alvo próprio por tentativa.
- Nesta fatia, `consultar_pagamento` não tem esse risco. O aviso (E07-05) só grava o próprio `AvisoRecebido`, que o `concluir` não toca.

**Alternativa descartada.** Não esperar, e criar uma segunda chamada pendente para o mesmo par quando a primeira está em execução. Isso exigiria trocar a restrição única e os critérios A-12 e A-15, além de uma regra nova para escolher entre duas pendentes.

### R02 — o horário do aviso se perde na coalescência

**Diagnóstico.** O horário do recebimento do aviso só viaja nos parâmetros da chamada. Quando já existe uma chamada pendente, por exemplo agendada pela tarefa e sem parâmetros, `agendar_chamada` a devolve "sem alterá-la", e o horário do aviso se perde. O `primeiro_aviso_em` fica nulo, embora o `AvisoRecebido` tenha o horário. A spec da E07-05 supunha que cada aviso criaria a própria chamada.

**Regra.**

- `Operacao` ganha um campo opcional: `combinar(atuais: dict, novos: dict) -> dict`.
- Quando `agendar_chamada` devolve uma pendente (com a trava do R01) e recebeu `parametros`, ela grava `parametros = combinar(atuais, novos)`. Isso só acontece se a operação tiver `combinar` e o resultado for diferente do atual.
  - Só `parametros` muda. `chave_idempotencia`, `proxima_em`, `tentativas` e `criada_em` continuam iguais, e o A-2 continua valendo.
  - Se a operação não tem `combinar`, os parâmetros não mudam.
- `combinar` de `consultar_pagamento`:
  - `aviso_recebido_em`: o mais antigo dos dois, comparado como instante e gravado em ISO 8601 UTC. Se nenhum dos dois tem o campo, ele continua ausente;
  - `origem`: `aviso`, se qualquer um dos dois for `aviso`; senão, a atual.
- Com o R01, todo aviso de pagamento entrega o seu horário a uma consulta que acontece depois dele. Ou o horário é combinado numa pendente que ainda não começou, ou vai numa chamada nova.
- `sincronizar_pagamento` (E07-03) não muda: só grava `primeiro_aviso_em` quando ele está nulo.

### R03 — falha local depois de o provedor aceitar

**Diagnóstico.** Ver a correção R03 da E07-01: o simulador gravava na conexão do sistema, e o rollback da chamada desfazia a cobrança já aceita. Os critérios desta fatia só cobriam a falha temporária depois de aceitar (A-7), que não desfaz nada.

**Regra.** `processar_chamadas` não muda. O rollback continua desfazendo só o que o sistema gravou: a chamada e os efeitos de `concluir`. Com a conexão própria do simulador, o que ele aceitou continua gravado, e a repetição com a mesma chave devolve a mesma cobrança. Com isso, o comentário de `_tentar` passa a ser verdadeiro.

### TDD

Os critérios A-17 a A-22 seguem Red → Green → Refactor, com as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05). Sobre a prova do revisor em `d6e4d20`:

- `test_falha_local_nao_apaga_cobranca_aceita` (R03) entra nos testes, com o alias do simulador no marcador.
- `test_aviso_durante_consulta_nao_e_perdido` (R01) não entra literalmente:
  - a prova espera que o aviso termine enquanto a tarefa está parada com a trava;
  - com a regra acima, é o aviso que espera a tarefa, e a prova ficaria parada até o prazo de 20 segundos.

  O A-17 desta fatia e o A-15 da E07-05 reproduzem a mesma intercalação. Neles, a tarefa fica parada até a outra thread terminar ou aparecer esperando a trava, o que vier primeiro.
  - No código atual, o aviso termina sem esperar, e o teste falha pela situação final (`pendente` em vez de `aprovado`). Esse é o Red esperado.
  - Com a correção, o aviso aparece esperando, e o teste segue até o fim.

## Dependências e decisões em aberto

- Depende de E04-03 (padrão da tarefa), E07-01, E07-02 e E07-03.
- Sem decisões em aberto.
