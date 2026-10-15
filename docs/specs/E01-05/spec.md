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

**5. Abertura com limite no driver.** As conexões das threads usam `connect_timeout` do libpq (inteiro, em segundos, menor que `tempo_limite_limpeza`). Assim, uma abertura real nunca dura mais que o prazo de limpeza, e a espera do passo 4.4 tem fim também fora dos testes instrumentados.

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
| `connect_timeout` das threads | 10 s | Menor que o prazo de limpeza padrão. |

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

## Dependências e decisões em aberto

- Depende de E01-01 (CI, com Postgres real).
- O modelo de contador usado nas demonstrações fica no app só de testes `tests/apoio` (definido na spec da E01-02).
- Sem decisões em aberto.
