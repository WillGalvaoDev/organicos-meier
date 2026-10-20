# E01-05 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com falha observada (Red). Todos usam `django_db(transaction=True)` e o marcador `concorrencia`, contra Postgres real.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec da fatia | positivo | duas operações que devolvem `"a"` e `"b"` | executo em paralelo | recebo os resultados na ordem das operações, com `valor` igual a `"a"` e `"b"` |
| A-2 | Spec da fatia | positivo | duas operações que gravam o identificador da própria conexão | executo em paralelo | os identificadores são diferentes |
| A-3 | AGENTS.md §6 | concorrência | um contador de teste com valor 0 e duas operações que leem, esperam na barreira interna e gravam `valor + 1` sem trava | executo em paralelo | o valor final é 1 (atualização perdida reproduzida) |
| A-4 | AGENTS.md §6 | concorrência | o mesmo contador com valor 0 e duas operações que incrementam com `select_for_update` dentro de `transaction.atomic` | executo em paralelo, 20 vezes seguidas, reiniciando o contador | o valor final é 2 em todas as repetições |
| A-5 | Spec da fatia | negativo | uma operação que levanta `ValueError` e outra que devolve `"ok"` | executo em paralelo | o resultado da primeira traz a exceção `ValueError`, e o da segunda traz `"ok"` |
| A-6 | Spec da fatia | negativo | uma operação que espera numa barreira que nunca se completa | executo com tempo limite de 2 segundos | `TempoEsgotado` em até cerca de 2 segundos, identificando a operação pendente. Nenhuma operação está abrindo conexão, então a limpeza não acrescenta espera relevante |
| A-7 | Spec da fatia | positivo | uma execução em paralelo concluída, com erro ou com tempo esgotado | o teste termina | não sobram conexões abertas pelas threads do utilitário (verificado pela contagem de conexões do usuário de teste no Postgres) |

## Critérios da correção R05 (revisão da especificação de 2026-10-15)

Os critérios abaixo detalham o A-7 para cada fase da abertura da conexão, conforme a seção "Correção R05" do `spec.md`.

**Instrumentação comum.** Os testes pausam a abertura de forma determinística, com `threading.Event`, instrumentando `DatabaseWrapper.get_new_connection` ou `DatabaseWrapper.ensure_connection` na classe (via `monkeypatch`). Isso vale só para as threads cujo nome começa com `concorrencia-`.

**Contagem das sessões.** É sempre feita no Postgres real (`pg_stat_activity`), pelo PID ou pelo `application_name` registrados na instrumentação, e logo depois do retorno de `executar_em_paralelo`, sem espera adicional no teste.

**Encerramento de cada teste.** Todo teste libera os eventos no `finally`, faz `join` da thread e afirma que ela terminou.

| ID | Fase da operação no tempo esgotado | Dado | Então |
|---|---|---|---|
| A-8 | `ANTES`: ainda não chamou `connect` | a thread é pausada antes da abertura (por exemplo, numa instrumentação de `ensure_connection` que espera antes de chamar o original) e liberada depois do retorno | `TempoEsgotado`. Quando liberada, a abertura é recusada, nenhuma sessão com o `application_name` da operação chega a existir e a operação não executa |
| A-9 | `ABRINDO`, sem sessão criada | o teste do revisor `test_abertura_em_andamento_conclui_apos_varredura` (review da E01-05, revalidação 523cd9c), incorporado **sem alteração** | o teste passa: `TempoEsgotado`, 0 sessões, thread encerrada, operação não executada |
| A-10 | `ABRINDO`, sem sessão criada (versão rápida) | o mesmo cenário do A-9, com a abertura liberada por um `threading.Timer` de 0,5 s, iniciado antes da chamada | `TempoEsgotado` depois de pelo menos 0,5 s e antes de `tempo_limite + tempo_limite_limpeza`, com 0 sessões no retorno |
| A-11 | `ABRINDO`, com sessão criada e ainda não entregue ao wrapper | o teste do revisor `test_timeout_com_connect_ja_em_execucao` (revalidação e7eec3c), incorporado **sem alteração** | o teste passa: 0 sessões no retorno e operação não executada |
| A-12 | `ABERTA` | o teste do revisor `test_r05_timeout_durante_abertura` (revalidação 6b7b9ab, com pausa depois de `ensure_connection`) e o teste versionado de retomada tardia | 0 sessões no retorno. Quando retomada, a operação não executa SQL com sucesso (o `SELECT 42` não produz resultado) e não abre outra conexão. A classe do erro recebido pela thread retomada não é fixada: vale `TempoEsgotado` ou um erro do driver pela sessão encerrada |
| A-13 | `ABERTA` com trava de linha | o teste versionado `test_utilitario_timeout_libera_trava_de_linha` | a linha volta a ser travável com `select_for_update(nowait=True)` logo depois do retorno |
| A-14 | erro na abertura | `get_new_connection` instrumentado para levantar `OperationalError` | sem tempo esgotado: o erro aparece em `Resultado.excecao`. Com tempo esgotado: `TempoEsgotado`. Nos dois casos, 0 sessões |
| A-15 | `ABRINDO` além do prazo de limpeza | `tempo_limite=0.2`, `tempo_limite_limpeza=0.5` e a abertura pausada até o teste liberar | `LimpezaIncompleta` (e não `TempoEsgotado`) em até cerca de 0,7 s, citando a operação e a fase `ABRINDO`; a pendência fica no registro da guarda |
| A-16 | guarda entre testes | o estado deixado pelo A-15: a pendência registrada, com a abertura liberada | `aguardar_limpezas_pendentes` termina com 0 sessões e esvazia o registro. Com a abertura ainda pausada e um prazo curto, ela levanta `LimpezaIncompleta` citando a operação. Na fixture `autouse`, essa exceção vira `pytest.fail` |
| A-17 | configuração (revisto em 2026-10-16, R06) | uma conexão aberta por uma thread do utilitário, com `tempo_limite_limpeza` em `0.5`, `1`, `10.5` e o padrão | `SHOW application_name` devolve o nome exclusivo da operação. Em todos os casos, `connect_timeout` é igual a `CONNECT_TIMEOUT_DAS_THREADS`, um `int` fixo, maior que zero, menor que o prazo de limpeza padrão e menor que o prazo padrão da guarda. Não se exige `connect_timeout` menor que `tempo_limite_limpeza`. Com prazo de limpeza menor ou igual ao limite do driver, uma abertura lenta resulta em `LimpezaIncompleta` (A-15) |
| A-18 | regressão completa | todos os testes do módulo, executados 5 vezes seguidas, e a suíte completa | todos passam em todas as execuções. A duração do módulo fica registrada no `review.md` |
| A-19 | `ABERTA` no alias do simulador, bloqueada numa trava de linha (E07-R06) | a prova do revisor `test_timeout_limpa_tambem_a_conexao_do_simulador` (revalidação `636a94c` da E07), incorporada **sem alteração** | o teste passa: `TempoEsgotado`; 0 sessões com o PID do simulador logo depois do retorno; nenhuma pendência na guarda; depois de liberada a trava, a cobrança continua `pendente` e a thread termina |
| A-20 | `ABRINDO` no alias do simulador, terminando dentro do prazo de limpeza (E07-R06) | uma cobrança simulada pendente; a operação abre `default` antes da barreira e depois chama `aprovar` pelo simulador; `get_new_connection` instrumentado na classe pausa só a abertura do wrapper de alias `simulador_pagamentos`, liberada por um `threading.Timer` de 0,5 s iniciado antes da chamada; `tempo_limite=0.2` | `TempoEsgotado` depois de pelo menos 0,5 s; 0 sessões com qualquer nome da operação logo depois do retorno; a aprovação não executou: a cobrança continua `pendente`, também depois de a thread terminar |
| A-21 | `ABRINDO` no alias do simulador além do prazo de limpeza; depois, a guarda (E07-R06) | o arranjo do A-20, com a abertura pausada até o teste liberar, `tempo_limite=0.2` e `tempo_limite_limpeza=0.5`; depois, a abertura liberada e `aguardar_limpezas_pendentes(30)` | `LimpezaIncompleta`, e não `TempoEsgotado`, com a mensagem citando a operação, `simulador_pagamentos` e `ABRINDO`; `limpezas_pendentes()` igual a 1; depois da liberação, a guarda termina com 0 sessões de todos os nomes da operação e esvazia o registro; a cobrança continua `pendente` |
| A-22 | `ANTES` no alias do simulador: abertura tentada depois do tempo esgotado (E07-R06) | uma cobrança simulada pendente; a operação abre `default` e espera num `threading.Event` que o teste só libera depois do retorno de `executar_em_paralelo`; depois tenta `aprovar` pelo simulador e guarda a exceção numa lista do teste; `tempo_limite=0.2` | `TempoEsgotado` no retorno; depois de liberada, a operação recebe `TempoEsgotado` ao abrir `simulador_pagamentos`, sem sessão com o nome desse alias em `pg_stat_activity` em nenhum momento conferido; a cobrança continua `pendente`; a thread termina |
| A-23 | configuração em todos os aliases (E07-R06) | (i) duas operações que leem, em `default` e em `simulador_pagamentos`, `SHOW application_name` e `get_connection_params()["connect_timeout"]`; (ii) `connections.settings["simulador_pagamentos"]["HOST"]` trocado por `monkeypatch` para outro valor e, noutros casos, `PORT` e `USER` | (i) cada nome é `<prefixo>-<indice>-<alias>`, distinto por operação e por alias, e o `connect_timeout` é `CONNECT_TIMEOUT_DAS_THREADS` nos dois aliases; (ii) `ValueError` citando `simulador_pagamentos`, antes de qualquer thread começar: nenhuma operação executa |
| A-24 | regressão completa (E07-R06) | A-1 a A-18 sem nenhuma alteração; `tests/tecnicos/test_apoio_concorrencia.py` e `tests/tecnicos/test_pagamentos_concorrencia.py` executados 5 vezes seguidas; a suíte completa | todos passam em todas as execuções; as durações ficam registradas no `review.md` da E07-01 |

**Exigências de TDD para estes critérios:**

- **Red pela asserção:** o Red de cada critério é registrado no `review.md` com a falha da asserção, e não com erro de importação.
- **Interface nova (`LimpezaIncompleta`, `tempo_limite_limpeza`):** primeiro entra a interface mínima, sem comportamento, registrada como andaime. Só depois se observa o Red da asserção.
- **Critérios que já passam antes da correção (A-12 e A-13):** são registrados como cobertura de regressão, sem Red.
- **Red esperado no commit `523cd9c`:** A-9 e A-10, com `assert 1 == 0`; A-15 e A-16, porque `LimpezaIncompleta` ainda não existe e o comportamento falta; A-17, se o `connect_timeout` estiver ausente.

**Exigências de TDD da correção E07-R06 (A-19 a A-24):**

- **Banco:** os testes usam `django_db(transaction=True, databases=["default", "simulador_pagamentos"])` e o marcador `concorrencia`.
- **Red esperado em `636a94c`:**
  - A-19, pela asserção final da prova (`sessoes_apos_timeout` 1 e `situacao_depois` `aprovado`);
  - A-20 e A-22, porque a aprovação executa depois do tempo esgotado;
  - A-21, porque o retorno é `TempoEsgotado`, e não `LimpezaIncompleta`;
  - A-23, porque o nome do alias do simulador não é exclusivo e porque o `ValueError` não é levantado.
- **Comandos:** com caminhos explícitos de arquivos inteiros, sem `-k` (R07 da E07-01).
- **Cobertura do Red:** a tabela de cobertura do Red fica no `review.md` da E07-01, antes do Green.

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1, A-2, A-5 a A-7 | `tests/tecnicos/test_apoio_concorrencia.py::test_utilitario_*` |
| A-3, A-4 | `tests/tecnicos/test_apoio_concorrencia.py::test_demonstracao_*` |
| A-8 a A-17 | `tests/tecnicos/test_apoio_concorrencia.py::test_r05_*`, com os três testes do revisor copiados literalmente e o nome original no comentário |
| A-18 | evidência no `review.md` |
| A-19 a A-23 | `tests/tecnicos/test_apoio_concorrencia.py::test_e07_r06_*`; o A-19 copia literalmente a prova do revisor, com o nome original no comentário |
| A-24 | evidência no `review.md` da E07-01 |
