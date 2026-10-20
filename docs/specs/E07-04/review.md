# E07-04 — Revalidação independente — 2026-10-20

**Parecer da fatia: REPROVADO na integração, sobre `636a94cacde2764e297967189c5904b58f72dde6`, branch `e07-implementacao`. E07 global: REPROVADO por R06 (IMPORTANTE).**

Matriz revalidada: **A-1 a A-22**. R01, R02 e R03 encerrados. R06 afeta a limpeza e o isolamento das provas concorrentes que utilizam a conexão própria do simulador. A aprovação local não aprova a entrega integrada.

O [parecer consolidado](../E07-01/review.md) registra a matriz das seis fatias, fontes, análise das correções, encerramento de R01–R05, achado R06 com prova reproduzível e R07 (melhoria de processo: Red de R03 usou `-k`, contrariando a prevenção vigente, sem evidência de critério omitido).

Verificação independente: suíte completa **1937 passed in 175.77s**; dez provas anteriores passam; prova nova de R06 falha (**1 failed, 10 passed in 5.85s**). `ruff check`, `ruff format --check` (257 arquivos), `mypy` (300 arquivos) e verificação de migrações passaram. Comandos, logs, adaptações justificadas das provas e código completo estão no parecer consolidado. As tabelas Red/Green foram conferidas; a revisão atual não é prova de execução histórica do Red.

R06: após timeout, uma sessão do simulador permanece ativa, a guarda informa zero pendências e a thread grava uma aprovação depois da liberação da trava. É necessário estender as garantias de E01-05 ao novo alias e revalidar antes da aprovação global. Somente pareceres foram alterados nesta revisão; conteúdo anterior preservado integralmente abaixo.

---

## Histórico integral preservado

# E07-04 — Revisão independente — 2026-10-20

**Veredito desta fatia: REPROVADO. Veredito global da E07: REPROVADO.**

Base: `d6e4d2095ac8f1128b1a315fd81e5ab579488aa3`, branch `e07-implementacao`. A-1 a A-16 examinados. R01 (bloqueador): deduplicação pode absorver aviso depois de a consulta em andamento ter lido o provedor. R02 (importante): chamada anterior sem parâmetros perde o transporte do primeiro recebimento. R03 (importante): rollback inesperado desfaz também a cobrança simulada já aceita; a repetição devolve outro identificador.

O [parecer consolidado em E07-01](../E07-01/review.md) contém fontes, matriz das seis fatias, análise dos registros de TDD, classificação e reprodução de R01 a R05, comandos e limitações. Verificação independente: **1902 testes aprovados** na suíte; provas adicionais: **8 falhas e 2 aprovações**. Ruff, formatação, mypy e verificação de migrações passaram. A suíte verde não cobre as lacunas reproduzidas. Nenhum arquivo de produção ou teste versionado foi alterado pelo revisor.

O registro anterior abaixo foi preservado integralmente e não substitui o veredito independente. A entrega integrada requer correção e nova revisão antes do encerramento.

---

## Registro do implementador preservado

# E07-04 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§8.3, 15), infraestrutura v1.7 (2, 4.2, 5), `spec.md` e `acceptance.md` da fatia, E04-03 e E06-05 (padrão da tarefa e do lote), E07-01 a E07-03.

## Arquivos

- `apps/pagamentos/models.py`: `ChamadaAoProvedor`, `SituacaoDaChamada` e `migrations/0002_chamadaaoprovedor.py` (`UNIQUE (operacao, alvo) WHERE situacao = 'pendente'`, `CHECK` da situação, chave de idempotência única).
- `apps/pagamentos/chamadas.py`: `agendar_chamada`, `processar_chamadas`, `registrar_operacao`, `Operacao`, `OPERACOES`, `FalhaTemporaria`, `INTERVALOS_EM_MINUTOS` e a operação `consultar_pagamento`.
- `apps/pagamentos/tarefas.py`: `processar_chamadas_ao_provedor` (periódica, a cada minuto, com `queueing_lock`).
- `tests/apoio/chamadas.py` (a operação de teste `criar_cobranca_de_teste`, registrada só dentro de um bloco), `tests/apoio/models.py` (`CobrancaDeTeste`, `FalhaDeTeste`) e a migração `tests/apoio/migrations/0005_*`.
- Testes: `test_pagamentos_chamadas.py` (A-1 a A-13, A-16) e, em `test_pagamentos_concorrencia.py`, A-14 e A-15.

## Ciclo TDD

**Andaime (exceção técnica, sem comportamento):** o modelo e a migração, as definições de `Operacao`, do registro e de `FalhaTemporaria`, `agendar_chamada` devolvendo uma chamada não salva, `processar_chamadas` devolvendo 0 e a operação `consultar_pagamento` registrada com funções neutras (para os testes encontrarem o nome). A tarefa periódica e a lógica de agendamento, execução e novas tentativas não existiam.

### Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pagamentos_chamadas.py tests/tecnicos/test_pagamentos_concorrencia.py -q`: **15 failed, 4 passed**. Falhas por asserção: `esperava 1 chamada, há 0`, `assert 0 == 1`, `assert 0 == 3`, `assert 0 == 2`, `assert []`, `DID NOT RAISE IntegrityError`, `DID NOT RAISE TransactionManagementError` e, na concorrência, as asserções de espera (`a outra conexão não ficou esperando pela trava`, `a primeira execução não chegou a chamar o provedor`).

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_agendar_cria_a_chamada_pendente` | falhou |
| A-2 | `test_agendar_de_novo_devolve_a_pendente` | falhou |
| A-3 | `test_agendar_exige_transacao_e_operacao_registrada` | falhou (`DID NOT RAISE TransactionManagementError`) |
| A-4 | `test_a_chamada_aprovada_e_sincronizada` | falhou |
| A-5, A-6 | `test_novas_tentativas_com_intervalos_crescentes` | falhou |
| A-7 | `test_repeticao_depois_de_o_provedor_aceitar_usa_a_mesma_chave` | falhou |
| A-8 | `test_recusa_definitiva_encerra_a_chamada` | falhou |
| A-9 | `test_pagamento_nao_encontrado_ate_24_horas` | falhou |
| A-10 | `test_uma_chamada_com_falha_nao_impede_as_outras` | falhou (`assert 0 == 3`) |
| A-11 | `test_o_limite_do_lote_respeita_a_ordem` | falhou |
| A-12 | `test_restricoes_da_tabela` | falhou (`DID NOT RAISE IntegrityError`: o andaime não tinha as chamadas) — a migração já tinha as restrições, mas o teste parte de uma chamada que o agendamento ainda não criava |
| A-13 | `test_a_tarefa_esta_registrada_como_periodica` | falhou (`assert 0 == 1` candidatas) |
| A-14 | `test_duas_execucoes_nao_tentam_a_mesma_chamada` | falhou por asserção, contra o andaime |
| A-15 | `test_agendamentos_concorrentes_do_mesmo_alvo` | falhou por asserção, contra o andaime |
| A-16 | `test_o_log_nao_leva_parametros_chave_nem_dados_da_cobranca` | falhou (`assert mensagens`: nenhum log de chamada) |
| extra | `test_o_registro_de_operacoes_comeca_com_a_consulta` | **passou no Red**: o andaime já registrava a operação; protege contra regressão |

As outras 3 que passaram no Red são testes da E07-01 e E07-03 do mesmo arquivo de concorrência.

### Green

Os dois arquivos: **19 passed**. Suíte completa: **1878 passed** (eram 1862). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` (com as configurações de teste, por causa do app de apoio) sem erros.

Uma primeira versão do Green envolvia `executar` e `concluir` num único savepoint e o A-7 falhou (`assert 0 == 1`): o rollback desfazia a `CobrancaSimulada`, que faz o papel do provedor e não pode sumir com a nossa transação. Corrigido para `executar` fora do savepoint e só `concluir` dentro (registrado abaixo).

## Decisões técnicas (derivadas da spec)

- **O estado do provedor não é desfeito pela nossa transação.** `executar` roda fora do savepoint; `concluir` roda dentro, e uma exceção dele desfaz só o que ele gravou (A-10). Numa exceção inesperada do próprio `executar`, o bloco da chamada é desfeito (nesse caso também o que o simulador gravou no mesmo banco; um provedor real não seria afetado).
- **Uma exceção inesperada nunca repete na mesma execução:** as chamadas já vistas na execução saem da consulta, para uma chamada defeituosa não prender o lote.
- **`PagamentoNaoEncontrado`** é traduzido dentro de `consultar_pagamento`: `FalhaTemporaria("nao_encontrado")` antes de 24 horas (`prazo_encerrado` sobre `criada_em` mais 24 h) e `RecusaDoProvedor("nao_encontrado")` depois, que fecha a chamada como `falhou`. O motor da tarefa só conhece três desfechos (sucesso, `ProvedorIndisponivel`/`FalhaTemporaria`, `RecusaDoProvedor`).
- **Intervalos** pelo número de tentativas já feitas: 1, 5, 15 e 60 minutos, e 60 depois; sem limite de tentativas.
- **Agendamento:** a releitura depois do `IntegrityError` só devolve uma chamada pendente; se a violação foi de outra restrição (por exemplo, chave informada repetida), o erro continua.
- **Log:** `Chamada ao provedor <id>: <operacao> <resultado>`, sem parâmetros, chave nem alvo; a falha inesperada traz o tipo da exceção.

## Limites da verificação

Postgres real; o worker do Procrastinate não foi executado como processo (a tarefa é conferida no registro e a rotina é chamada direto). A concorrência de A-14 usa um evento para manter a primeira execução dentro de `executar` até a segunda terminar. Criar/cancelar cobrança (E08), estorno (E10) e o alerta de chamada parada (E15) são de outras etapas. Nenhuma mutação aplicada nesta fatia.


---

## Correções E07-R01, R02 e R03 — registro do implementador (2026-10-20)

Status: correções implementadas; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `docs/specs/E07-01/review.md` (parecer sobre `d6e4d20`), `spec.md` e `acceptance.md` desta fatia (seção "Correção E07-R01, R02 e R03", A-17 a A-22) e a prova `test_falha_local_nao_apaga_cobranca_aceita`.

### Arquivos

- `apps/pagamentos/chamadas.py`: `_pendente` trava a pendente do par com `select_for_update()` (sem `skip_locked`, sem `nowait`); `_absorver` aplica `Operacao.combinar`; novo campo opcional `combinar` em `Operacao`; `_combinar_consulta` para `consultar_pagamento` (horário mais antigo em ISO UTC; origem `aviso` se qualquer um for aviso).
- R03: `processar_chamadas` não mudou; o comentário de `_tentar` passou a descrever a conexão própria do simulador (ver a E07-01).
- Testes: `test_pagamentos_chamadas.py` (A-20, A-21, A-22) e `test_pagamentos_concorrencia.py` (A-17, A-18, A-19). `tests/apoio/trava.py`: `outra_conexao_esperando()`.

### Red (arquivos inteiros, sem `-k`)

R01/R02, `uv run pytest tests/tecnicos/test_pagamentos_chamadas.py tests/tecnicos/test_pagamentos_avisos.py tests/tecnicos/test_pagamentos_concorrencia.py -q`: **6 failed, 49 passed**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-17 | `test_aviso_durante_a_consulta_nao_e_absorvido` | falhou: `assert 49 != 49` (a chamada devolvida foi a mesma da tarefa: o aviso foi absorvido) |
| A-18 | `test_a_tarefa_pula_a_chamada_que_o_agendamento_segura` | falhou: `assert 1 == 0` (a tarefa consultou com a chamada em poder do agendamento) |
| A-19 | `test_aviso_que_espera_a_falha_temporaria_combina_o_horario` | falhou: `assert {} == {'origem': 'aviso', ...}` |
| A-20 | `test_agendar_de_novo_combina_o_horario_do_aviso` | falhou: `assert {} == {...}` |
| A-20 | `test_operacao_sem_combinar_mantem_os_primeiros_parametros` | **passou no Red** (controle: sem `combinar`, os parâmetros não mudam) |
| E07-05 A-15 | `test_aviso_durante_a_consulta_espera_e_gera_outra_consulta` | falhou: `assert ['concluida'] == ['concluida', 'concluida']` |
| E07-05 A-16 | `..._preservado_com_consulta_ja_agendada[tarefa-antes]` | falhou: `assert {} == {...}` |
| E07-05 A-16 | `..._preservado_com_consulta_ja_agendada[sem-tarefa]` e `test_aviso_apos_consulta_concluida_atualiza` | **passaram no Red** (os controles do revisor: o aviso que cria a própria consulta e o que chega depois da conclusão) |

R03: ver o registro da E07-01 (A-21 e A-22 desta fatia falharam por `assert 0 == 1`; 5 falhas no total do `-k pagamentos`).

### Green

Os três arquivos mais `test_pagamentos_consulta.py`: **64 passed** (R01/R02); `-k pagamentos` com R03: **146 passed**. Suíte completa: **1937 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

### Decisões técnicas

- **Intercalação sem ponto cego.** Os testes A-17 e A-19 usam, para a tarefa parada, a espera "a outra thread terminar ou aparecer esperando a trava, o que vier primeiro" (`_aguardar`), com falha por asserção no prazo de 15 s. No código antigo a outra thread termina primeiro (Red); no corrigido ela aparece esperando a trava (Green).
- **Quem agenda e encontra a pendente fica com a trava** até o fim da transação dele; `processar_chamadas` pula a chamada (`skip_locked`). O risco de impasse com as operações da E08 e da E10 (agendar antes de travar as linhas que o `concluir` trava, ou um alvo por tentativa) fica registrado para essas etapas; `consultar_pagamento` não o tem.
- **`combinar`** só roda quando há `parametros` novos e a operação o define; só `parametros` é gravado (`update_fields`), de modo que chave, `proxima_em`, tentativas e criação não mudam.

### Limites da verificação

Postgres real; threads reais; sem o worker como processo. As operações da E08/E10 não existem ainda. Nenhuma mutação aplicada nestas correções.
