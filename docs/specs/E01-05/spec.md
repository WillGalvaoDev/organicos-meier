# E01-05 — Utilitário de testes de concorrência

Fatia 5 de 5 da milestone **E01 — Fundação de engenharia**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Reservas, fila, caixas, pagamentos, devoluções e envios exigem testes de corrida com transações reais (AGENTS.md §6). Esta fatia cria um utilitário de teste que executa operações em paralelo, cada uma com sua conexão ao Postgres, de forma determinística e sem travar a suíte. Os testes de corrida das etapas seguintes usarão esse utilitário.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| AGENTS.md §6 | Operações críticas transacionais. Testar corridas relevantes em estoque, fila, pedidos, pagamentos e estornos. |
| Especificação §15 | Transações ou mecanismo equivalente para estoque, fila, caixas e congelamento. |
| Infraestrutura 5 e testes T-6, T-7, T-21, T-31, T-45, T-49, T-53, T-55 | Testes de concorrência com `select_for_update` e transações reais. |
| pyproject.toml | Marcador `concorrencia` já declarado. |

## Escopo

**Dentro:**

- Função de teste que executa N operações em paralelo, cada uma em sua thread e com sua própria conexão ao banco.
- Barreira de sincronização que as operações podem usar para forçar um ponto de encontro, por exemplo depois de ler e antes de gravar.
- Coleta de resultados e de exceções de cada operação.
- Tempo limite: a execução falha com erro claro em vez de travar a suíte.
- Fechamento das conexões abertas pelas threads ao final.
- Dois testes de demonstração que provam que o utilitário detecta uma corrida real e confirma a correção com trava.

**Fora:**

- Testes de corrida de negócio (ficam nas etapas E05 em diante).
- Paralelismo entre processos (`pytest-xdist`).

## Regras

- **Isolamento:** cada operação roda em uma thread própria, com conexão própria ao Postgres. O teste chamador precisa usar banco transacional (`django_db(transaction=True)`) e o marcador `concorrencia`.
- **Início sincronizado:** todas as operações começam juntas, liberadas por uma barreira de início.
- **Barreira interna:** a operação pode receber uma barreira para um segundo ponto de encontro definido pelo teste.
- **Resultado:** para cada operação, devolve o valor retornado ou a exceção levantada, na mesma ordem das operações passadas.
- **Tempo limite:** se alguma operação não terminar dentro do limite (padrão definido pelo implementador e configurável), a função falha com uma exceção própria que identifica a operação pendente.
- **Conexões:** ao final, com sucesso, erro ou tempo esgotado, as conexões abertas pelas threads são fechadas, e testes seguintes não herdam conexões abertas. A garantia exata no tempo esgotado e o projeto obrigatório estão na seção "Correção R05", que prevalece sobre esta regra resumida.

## Interfaces

Módulo de testes `tests/apoio/concorrencia.py` (nomes ajustáveis pelo implementador, se mantidos o comportamento e os testes):

- `executar_em_paralelo(*operacoes, tempo_limite=...) -> list[Resultado]`
- `Resultado`, com `valor` ou `excecao`.
- `TempoEsgotado(Exception)`.
- Cada operação é uma função que recebe a barreira interna.

## Invariantes

- O utilitário não altera o comportamento transacional da operação: cada operação controla as próprias transações.
- Nenhuma exceção de thread é perdida.
- A suíte nunca fica travada por causa do utilitário: toda espera do utilitário tem limite (ver "Correção R05").

## Casos-limite e concorrência

- **Demonstração de corrida (sem trava):** duas operações leem um contador com valor 0, encontram-se na barreira interna e gravam `valor + 1`. O resultado final é 1, a atualização perdida esperada. O teste afirma esse resultado, o que prova que o utilitário reproduz a corrida de forma determinística.
- **Demonstração de correção (com trava):** duas operações incrementam o mesmo contador com `select_for_update` dentro de `transaction.atomic`, sem barreira interna. O resultado final é 2 em todas as repetições.
- **Exceção em uma operação:** uma operação levanta erro e a outra termina. O utilitário devolve a exceção da primeira e o valor da segunda.
- **Tempo limite:** uma operação espera numa barreira que nunca é completada. O utilitário levanta `TempoEsgotado` dentro do limite configurado.

## Correção R05 — revisão da especificação em 2026-10-15

Esta seção foi escrita pelo especificador depois de quatro rodadas de reprovação pelo mesmo bloqueador (R05/A-7, commits `72288d3`, `6b7b9ab`, `e7eec3c` e `523cd9c`). Ela substitui a interpretação aberta da regra "Conexões" por uma garantia precisa e por um projeto obrigatório. O implementador segue esta seção, e o revisor avalia contra ela.

### Diagnóstico

- **Por que as correções falharam:** cada rodada tratou só a janela de tempo do último exemplo do revisor:
  - fechar o wrapper;
  - registrar o wrapper antes de abrir;
  - encerrar o backend pelo `application_name`.
- **Onde estava o problema:** a raiz é a mesma nas três. Quando o tempo esgota, o chamador decide o que limpar olhando um instante só, mas a thread pendente pode estar no meio de `connect()`. O Python não permite interromper essa chamada, e ela pode criar a sessão depois de qualquer consulta ou fechamento feito pelo chamador.
- **Conflito da spec original:** as duas regras se contradiziam nesse caso:
  - "sem conexões residuais" exige esperar a abertura em curso terminar;
  - "a suíte nunca trava" proíbe esperar sem limite.

  A spec não dizia como as duas convivem.
- **Consequência:** nenhuma consulta adicional, em qualquer instante, resolve o problema. É preciso saber em que fase cada thread está e esperar a saída da fase de abertura, com limite e com falha explícita quando o limite estoura.

### Garantia exigida

Quando `executar_em_paralelo` termina com tempo esgotado e levanta `TempoEsgotado`, cada operação pendente fica numa destas situações:

1. **Nunca abriu conexão:** já não pode abrir nenhuma.
2. **Abriu conexão:** a sessão foi encerrada no Postgres, a operação já não pode abrir outra conexão e não executa SQL com sucesso.
3. **Estava abrindo:** a abertura terminou (com sucesso ou erro) dentro do limite de limpeza, e a sessão resultante foi fechada sem executar a operação.

Duas verificações completam a garantia:

- **No servidor:** antes de levantar `TempoEsgotado`, o chamador confirma em `pg_stat_activity` que nenhuma sessão das operações pendentes existe, pelo `application_name` exclusivo de cada operação.
- **Quando a garantia não pode ser cumprida:** se uma abertura não termina dentro do limite de limpeza, ou se uma sessão não desaparece, o utilitário levanta `LimpezaIncompleta` em vez de `TempoEsgotado`. Essa exceção é uma falha de teste, nunca um resultado aceitável, e o restante da suíte fica protegido pela guarda entre testes.

O que **não** se exige: interromper a thread Python. Ela pode continuar viva, bloqueada fora do banco (numa barreira do teste ou em `time.sleep`), desde que sem conexão e sem poder abrir uma.

### Projeto obrigatório

**1. Fases por operação, protegidas por uma única trava.**

- Cada operação tem um estado: `ANTES`, `ABRINDO`, `ABERTA` ou `SEM_CONEXAO`.
- O estado e o indicador `expirado` são lidos e alterados só sob o mesmo `threading.Condition`, um por chamada de `executar_em_paralelo`.

**2. `connect` controlado em cada wrapper, instalado pela própria thread antes de qualquer abertura.**

A thread substitui o `connect` do seu wrapper (atributo de instância) por uma função que segue este passo a passo:

1. Sob a trava: se `expirado`, levanta `TempoEsgotado` sem abrir nada. Senão, passa o estado para `ABRINDO`.
2. Fora da trava: chama o `connect` original. Ele chama `get_new_connection` da classe, e não deve ser sobrescrito, para que os testes possam instrumentá-lo.
3. Se o `connect` original levantar erro: sob a trava, passa o estado para `SEM_CONEXAO`, notifica e repassa o erro.
4. Se ele retornar: sob a trava, verifica `expirado`.
   - Se não expirou, passa o estado para `ABERTA` e notifica.
   - Se expirou, fecha a conexão recém-aberta fora da trava, passa o estado para `SEM_CONEXAO`, notifica e levanta `TempoEsgotado`.

   A operação de negócio não executa.

**3. Fim da thread.** No `finally`, a thread fecha as próprias conexões e, sob a trava, passa o estado para `SEM_CONEXAO` e notifica.

**4. Tempo esgotado no chamador, nesta ordem:**

1. Sob a trava: marca `expirado` e tira um retrato dos estados. A partir daqui, nenhuma operação em `ANTES` consegue entrar em `ABRINDO`.
2. Aborta as barreiras de início e interna.
3. Operações `ABERTA`: torna o wrapper inutilizável e encerra a sessão no servidor (`pg_terminate_backend` filtrado pelo `application_name` da operação, excluindo o PID do chamador).
4. Operações `ABRINDO`: espera, com `Condition.wait` e prazo, até nenhuma operação estar em `ABRINDO`. O prazo é `tempo_limite_limpeza`. A espera só termina pela mudança de estado ou pelo fim do prazo, e não é uma espera fixa.
5. Encerra no servidor qualquer sessão restante das operações pendentes e consulta `pg_stat_activity`, repetindo até zero sessões ou até o fim do prazo de limpeza restante. Como `pg_terminate_backend` e o fechamento pelo cliente são assíncronos no servidor, esta confirmação é obrigatória.
6. Se tudo ficou limpo, levanta `TempoEsgotado` com os nomes das operações pendentes. Se o prazo de limpeza estourou com alguma operação em `ABRINDO` ou alguma sessão restante, registra a pendência na guarda entre testes e levanta `LimpezaIncompleta`, identificando as operações e a fase de cada uma.

**5. Abertura com limite no driver.** Texto revisto em 2026-10-16 para encerrar o R06. Ver "Correção R06".

- **Valor:** as conexões das threads usam `connect_timeout` do libpq com um valor fixo, a constante `CONNECT_TIMEOUT_DAS_THREADS = 10`, inteiro em segundos. O valor não depende de `tempo_limite_limpeza`.
- **Finalidade:** garantir que toda abertura real termine em tempo finito. Assim, a guarda entre testes sempre consegue resolver uma pendência.
- **O que esse limite não garante:** que a abertura termine dentro de `tempo_limite_limpeza`.
- **Prazo de limpeza maior que o limite do driver** (inclusive o padrão, 30 s > 10 s): uma abertura real lenta termina dentro do prazo de limpeza.
- **Prazo de limpeza menor ou igual ao limite do driver** (por exemplo, 0,5 s ou 1 s): uma abertura real lenta pode passar do prazo. Isso resulta em `LimpezaIncompleta`, registro e guarda, que é o comportamento previsto no A-15, e não um defeito.

**6. Guarda entre testes.**

- O módulo mantém um registro de limpezas pendentes, preenchido só quando `LimpezaIncompleta` é levantada.
- Uma fixture `autouse` em `tests/conftest.py` roda antes de cada teste, mas só age se o registro não estiver vazio. Ela:
  1. espera, com prazo, as threads registradas saírem de `ABRINDO`;
  2. encerra as sessões delas no servidor e confirma zero sessões;
  3. limpa o registro.
- Se ainda restar sessão, a fixture falha o teste com `pytest.fail`, citando a operação de origem.
- Assim, nenhum teste roda em silêncio com conexão herdada.
- Para acessar o banco fora de um teste com `django_db`, a guarda usa `django_db_blocker.unblock()`.

### Parâmetros

| Parâmetro | Padrão | Observação |
|---|---|---|
| `tempo_limite` | 30 s | Já existente. |
| `tempo_limite_limpeza` | 30 s | Novo argumento de `executar_em_paralelo`. Precisa cobrir as aberturas instrumentadas dos testes do revisor, que chegam a cerca de 10 s. |
| `connect_timeout` das threads | 10 s, fixo | Constante `CONNECT_TIMEOUT_DAS_THREADS`, igual para qualquer `tempo_limite_limpeza`. É menor que o prazo de limpeza padrão (30 s) e que o prazo padrão da guarda (30 s). |
| prazo da guarda entre testes | 30 s | Maior que `CONNECT_TIMEOUT_DAS_THREADS`, para que uma abertura real pendente sempre termine dentro dele. |

- **Duração máxima de uma chamada:** `tempo_limite + tempo_limite_limpeza`.
- **Sem abertura em andamento:** quando nenhuma operação está em `ABRINDO`, a limpeza leva só o tempo de confirmar no servidor. Por isso o A-6 continua valendo, com cerca de 2 s.

### Interfaces acrescentadas

- `executar_em_paralelo(*operacoes, tempo_limite=30.0, tempo_limite_limpeza=30.0) -> list[Resultado]`
- `LimpezaIncompleta(Exception)`. Não é subclasse de `TempoEsgotado`, para que um `pytest.raises(TempoEsgotado)` não esconda a falha de limpeza.
- `aguardar_limpezas_pendentes(prazo: float) -> None` em `tests/apoio/concorrencia.py`. Ela faz o trabalho da guarda e levanta `LimpezaIncompleta` se restar sessão. A fixture `autouse` em `tests/conftest.py` só a chama quando o registro não está vazio e converte a exceção em `pytest.fail`. O A-16 testa a função diretamente.

### O que não fazer

- Não acrescentar consultas ou esperas fixas em outros instantes: essa abordagem já falhou quatro vezes.
- Não sobrescrever `get_new_connection` no wrapper da instância. Isso esconderia a instrumentação dos testes, que é feita na classe, e tornaria os testes inválidos.
- Não fechar pelo chamador um wrapper que esteja em `ABRINDO`: quem fecha é a própria thread, no passo 2.4.
- Não remover nem afrouxar os testes de R05 já versionados, nem os testes do revisor incorporados.

## Correção R06 — revisão da especificação em 2026-10-16

O revisor encerrou o R05 no commit `b709ce3` e apontou o R06. A falha é da especificação, e não da implementação: o projeto obrigatório (item 5) exigia `connect_timeout` inteiro e menor que `tempo_limite_limpeza`, enquanto o A-15 exige aceitar um prazo de limpeza de 0,5 s. Não existe inteiro positivo menor que 0,5, então as duas regras não podiam valer juntas. A implementação tentou conciliá-las com `min(10, max(1, ceil(tempo_limite_limpeza) - 1))`, que dá 1 s para 0,5 s e também não cumpre a desigualdade em 1 s.

### Decisão técnica

- **Desigualdade removida:** a exigência "`connect_timeout` menor que `tempo_limite_limpeza`" deixa de existir.
- **Por que ela não era necessária:** a correção do R05 não depende dela. Quem garante a ausência de sessão residual é a espera pela saída de `ABRINDO`, a confirmação no servidor e, quando o prazo estoura, a exceção `LimpezaIncompleta` com a guarda.
- **Novo papel do `connect_timeout`:** só garantir que uma abertura real termine em tempo finito, para que a guarda resolva a pendência. Para isso basta um valor fixo, menor que o prazo da guarda.
- **A-15 mantido:** o comportamento continua igual.
- **A-17 reescrito:** passa a verificar a constante fixa em vários prazos de limpeza, e não mais uma desigualdade.

### O que o implementador faz

1. **Red:** em `tests/tecnicos/test_apoio_concorrencia.py`, parametrizar o teste do A-17 com `tempo_limite_limpeza` em `0.5`, `1`, `10.5` e o padrão (sem o argumento). Em cada caso, o valor lido dentro da operação por `connection.get_connection_params()["connect_timeout"]` precisa ser igual a `CONNECT_TIMEOUT_DAS_THREADS`. Com a fórmula atual, os casos `0.5`, `1` e `10.5` falham, porque devolvem 1, 1 e 10 em vez do valor fixo; isso deve ser registrado no `review.md`.
   - **Atenção:** em `10.5`, a fórmula atual devolve 10, que já é o valor da constante, então a asserção de igualdade passa antes da correção. O Red desse caso vem só dos valores `0.5` e `1`. O caso `10.5` fica como cobertura.
2. **Constantes no mesmo teste:** afirmar também que a constante é `int`, maior que zero, menor que `TEMPO_LIMITE_LIMPEZA_PADRAO` e menor que o prazo padrão de `guarda_entre_testes`.
3. **Green:** em `tests/apoio/concorrencia.py`:
   - criar a constante `CONNECT_TIMEOUT_DAS_THREADS = 10`;
   - criar `TEMPO_LIMITE_LIMPEZA_PADRAO = 30.0`, que ainda não existe, e usá-la como padrão de `tempo_limite_limpeza`. Essa extração é andaime do passo 1, feito antes do Red;
   - substituir a fórmula da linha 183 pela constante;
   - remover a importação de `math`, se ela ficar sem uso.
4. **Comentários:** alinhar o comentário da linha 182 e qualquer docstring que prometa "uma abertura real nunca passa do prazo de limpeza" ao texto do item 5. O limite do driver garante término finito, e só garante término dentro do prazo quando esse prazo é maior que 10 s.
5. **Prazo da guarda:** se o prazo padrão de `guarda_entre_testes` em `tests/conftest.py` não for uma constante nomeada, extraí-lo para uma, para que a asserção do passo 2 não repita o número.
6. **Regressão:** rodar o módulo 5 vezes seguidas e a suíte completa, ruff, mypy e `makemigrations --check`, e registrar tudo no `review.md`.

### Testes de verificação do revisor

- **`test_connect_timeout_inferior_ao_prazo_curto`** (revalidação `b709ce3`): afirma `0 < connect_timeout < 0.5`, ou seja, a desigualdade que esta correção removeu. Ele fica **substituído pelo A-17 reescrito** e não deve ser incorporado nem usado como critério.
- **`test_r05_retomada`** (revisões anteriores): exige que a thread retomada receba `TempoEsgotado`. O contrato (A-12) exige só que nenhum SQL execute com sucesso e que nenhuma conexão nova seja aberta, sem fixar a classe do erro, como o próprio revisor registrou. Quando a sessão já foi encerrada no servidor, um `OperationalError` do driver também cumpre o contrato.

### Fora desta correção

Nenhuma outra mudança no utilitário. R01 a R05 estão encerrados e não são reabertos.

## Correção E07-R06 — limpeza em todos os aliases (2026-10-20)

Origem: revalidação da E07 sobre `636a94c` (`docs/specs/E07-01/review.md`, R06). A correção R03 da E07 deu ao simulador de pagamentos uma conexão própria, o alias `simulador_pagamentos`. O utilitário desta fatia só controla a conexão `default`. As garantias das correções R05 e R06 acima continuam valendo e passam a valer para todo alias.

### Diagnóstico

O utilitário instala o `connect` controlado, o `application_name` exclusivo e o `connect_timeout` só no wrapper `connections["default"]` de cada thread. A fase da operação descreve só essa conexão. Uma operação que usa o simulador abre uma segunda sessão, que fica fora de tudo isso:

- a sessão não tem nome exclusivo, e o encerramento e a confirmação em `pg_stat_activity` não a encontram;
- a abertura dela não passa pelo controle, e uma abertura depois do tempo esgotado não é recusada;
- a fase não registra essa sessão, e a guarda não tem como resolvê-la.

O revisor reproduziu o caso: a operação ficou bloqueada numa trava de linha do simulador, o utilitário levantou `TempoEsgotado` dizendo que a limpeza estava concluída, e a sessão do simulador continuou viva. Quando a trava foi liberada, ela gravou a aprovação depois do retorno.

Eu introduzi o alias na E07 sem estender a garantia desta fatia. A spec da E01-05 tinha sido escrita com uma conexão por thread.

### Garantia exigida

A garantia da correção R05 passa a valer **por operação e por alias**. Quando `executar_em_paralelo` levanta `TempoEsgotado`, cada conexão de cada operação pendente, em qualquer alias de `settings.DATABASES`, fica numa das três situações da correção R05:

- nunca abriu e já não pode abrir;
- abriu, e a sessão foi encerrada no servidor;
- estava abrindo, terminou dentro do prazo de limpeza e foi fechada sem executar a operação.

A confirmação de zero sessões no servidor cobre todas as sessões das operações pendentes, em todos os aliases. Se isso não for possível, o utilitário levanta `LimpezaIncompleta`, e a pendência fica na guarda, como antes.

### Projeto obrigatório (complementa os itens 1 a 6 da correção R05)

1. **Aliases cobertos:** todos os de `settings.DATABASES`, e não só os que a operação vai usar. O utilitário não precisa saber quais aliases a operação usa.
2. **Mesmo servidor.**
   - Antes de iniciar qualquer thread, o utilitário confere que todo alias tem `HOST`, `PORT` e `USER` iguais aos de `default`. Assim, `pg_stat_activity` e `pg_terminate_backend`, executados pela conexão `default` do chamador, alcançam todas as sessões. `NAME` pode ser diferente.
   - Se algum alias não cumprir isso, o utilitário levanta `ValueError` com o nome do alias, sem iniciar nenhuma thread.
3. **Nome exclusivo por operação e por alias:** `application_name = <prefixo>-<indice>-<alias>`, com o mesmo `connect_timeout` fixo (`CONNECT_TIMEOUT_DAS_THREADS`) em todos.
4. **`connect` controlado em cada wrapper.**
   - A thread instala o `connect` controlado do item 2 da correção R05 no wrapper de **cada** alias, antes de qualquer abertura.
   - A conexão `default` continua aberta antes da barreira de início, como hoje. Os outros aliases abrem só quando a operação os usar, sempre pelo `connect` controlado.
   - Uma abertura depois de `expirado` levanta `TempoEsgotado` sem abrir nada, como no item 2.1.
5. **Fase por alias.**
   - Cada operação guarda uma fase por alias (`ANTES`, `ABRINDO`, `ABERTA` ou `SEM_CONEXAO`), sob o mesmo `threading.Condition` da chamada.
   - A operação está "abrindo" se qualquer alias dela estiver em `ABRINDO`.
   - No `finally`, a thread fecha todas as conexões (`connections.close_all()`) e passa todos os aliases para `SEM_CONEXAO`.
6. **Tempo esgotado.** Os passos do item 4 da correção R05 valem sobre o conjunto de nomes de todas as operações pendentes em todos os aliases:
   - encerrar as sessões abertas;
   - esperar a saída de `ABRINDO` em qualquer alias, com prazo;
   - encerrar o que restar e confirmar zero sessões;
   - levantar `TempoEsgotado` ou `LimpezaIncompleta`.
7. **Descrição das pendências.** As mensagens de `TempoEsgotado` e `LimpezaIncompleta`, e o registro da guarda, citam a operação, o alias e a fase. Por exemplo: `0:bloqueada (default SEM_CONEXAO, simulador_pagamentos ABRINDO)`.
8. **Guarda entre testes:** sem mudança de interface. `aguardar_limpezas_pendentes` usa os nomes de todos os aliases da pendência.

### O que não fazer

- Não fechar conexões só no `finally` da thread como forma de limpeza: o `finally` só roda quando a operação termina, e a thread pode estar bloqueada no banco.
- Não juntar o simulador à conexão `default`, nem remover o isolamento transacional da correção R03 da E07.
- Não limitar a cobertura a uma lista fixa de aliases dentro do utilitário.
- Não alterar, afrouxar nem remover os critérios A-1 a A-18 nem os testes já versionados. Eles continuam valendo para `default`.

### Interfaces

Nenhuma interface nova. `executar_em_paralelo`, `TempoEsgotado`, `LimpezaIncompleta`, `limpezas_pendentes`, `aguardar_limpezas_pendentes` e as constantes continuam com o mesmo contrato. Muda só o alcance da garantia.

### TDD

- **Critérios:** A-19 a A-23 seguem Red → Green → Refactor, com as regras de prevenção da correção E06-R05 (E06-05).
- **Comandos do Red:** sempre com caminhos explícitos de arquivos inteiros, sem `-k` e sem escolher funções pelo nome, por exemplo `uv run pytest tests/tecnicos/test_apoio_concorrencia.py -q` (ver R07 na E07-01).
- **Prova do revisor:** `test_timeout_limpa_tambem_a_conexao_do_simulador` (revalidação `636a94c`) entra **sem alteração** no A-19. No código atual, ela falha pela asserção final: `sessoes_apos_timeout` 1 e `situacao_depois` `aprovado`.
- **Mudança de interface:** nenhuma, então não há andaime.

## Dependências e decisões em aberto

- Depende de E01-01 (CI, com Postgres real).
- O modelo de contador usado nas demonstrações fica no app só de testes `tests/apoio` (definido na spec da E01-02).
- Sem decisões em aberto.
