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
