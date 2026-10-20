# E07-06 — Revalidação independente — 2026-10-20

**APROVADO sobre `162e9e19bd9384d67c5e70d47b3fd062cc41e1b6`, branch `e07-implementacao`. E07 global: APROVADO, com melhoria não impeditiva R08.**

Matriz: **A-1 a A-10**. Revisão incremental desde `93b4a6a`; a implementação funcional desta fatia não mudou. R06 foi corrigido no apoio de concorrência da E01-05, encerrando a regressão integrada. R07 foi reconhecido no registro e os novos ciclos usam arquivos inteiros. R01 a R05 permanecem encerrados.

Verificação independente: **1945 passed in 216.94s (0:03:36)** na suíte completa; **47 testes passaram em cada uma de cinco execuções consecutivas** dos módulos de apoio/concorrência de pagamentos; **11 passed in 5.46s** nas provas preservadas de R01–R06. Lint, formatação (257 arquivos), tipos (300 arquivos) e migrações passaram.

O [parecer consolidado](../E07-01/review.md) contém a análise, os comandos, durações, matriz A-19 a A-24 da E01-05, limites de verificação histórica do TDD e R08: a mensagem de TempoEsgotado omite alias/fase, sem afetar a limpeza nem a guarda. Não há achado bloqueador ou importante aberto. A aprovação refere-se à fase 1 com simulador e não autoriza dinheiro real.

Somente pareceres foram alterados pelo revisor. Histórico integral preservado abaixo.

---

## Histórico integral preservado

# E07-06 — Revalidação independente — 2026-10-20

**Parecer da fatia: APROVADO no escopo local, sobre `636a94cacde2764e297967189c5904b58f72dde6`, branch `e07-implementacao`. E07 global: REPROVADO por R06 (IMPORTANTE).**

Matriz revalidada: **A-1 a A-10**. Consulta antes de decisões, falhas e sincronizações anteriores continuam cobertas e verdes. A aprovação local não aprova a entrega integrada.

O [parecer consolidado](../E07-01/review.md) registra a matriz das seis fatias, fontes, análise das correções, encerramento de R01–R05, achado R06 com prova reproduzível e R07 (melhoria de processo: Red de R03 usou `-k`, contrariando a prevenção vigente, sem evidência de critério omitido).

Verificação independente: suíte completa **1937 passed in 175.77s**; dez provas anteriores passam; prova nova de R06 falha (**1 failed, 10 passed in 5.85s**). `ruff check`, `ruff format --check` (257 arquivos), `mypy` (300 arquivos) e verificação de migrações passaram. Comandos, logs, adaptações justificadas das provas e código completo estão no parecer consolidado. As tabelas Red/Green foram conferidas; a revisão atual não é prova de execução histórica do Red.

R06: após timeout, uma sessão do simulador permanece ativa, a guarda informa zero pendências e a thread grava uma aprovação depois da liberação da trava. É necessário estender as garantias de E01-05 ao novo alias e revalidar antes da aprovação global. Somente pareceres foram alterados nesta revisão; conteúdo anterior preservado integralmente abaixo.

---

## Histórico integral preservado

# E07-06 — Revisão independente — 2026-10-20

**Veredito desta fatia: APROVADO no escopo local. Veredito global da E07: REPROVADO.**

Base: `d6e4d2095ac8f1128b1a315fd81e5ab579488aa3`, branch `e07-implementacao`. A-1 a A-10: busca, reconsulta dos conhecidos ausentes da busca, bloqueio nas falhas, persistência das sincronizações anteriores e concorrência conferidos. A aprovação não abrange decisões de negócio das próximas etapas nem valida o comportamento de um provedor real.

O [parecer consolidado em E07-01](../E07-01/review.md) contém fontes, matriz das seis fatias, análise dos registros de TDD, classificação e reprodução de R01 a R05, comandos e limitações. Verificação independente: **1902 testes aprovados** na suíte; provas adicionais: **8 falhas e 2 aprovações**. Ruff, formatação, mypy e verificação de migrações passaram. A suíte verde não cobre as lacunas reproduzidas. Nenhum arquivo de produção ou teste versionado foi alterado pelo revisor.

O registro anterior abaixo foi preservado integralmente e não substitui o veredito independente. A entrega integrada requer correção e nova revisão antes do encerramento.

---

## Registro do implementador preservado

# E07-06 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§8.3, 15), infraestrutura v1.7 (4.2, 4.3, 4.4), `spec.md` e `acceptance.md` da fatia, E07-01 e E07-03.

## Arquivos

- `apps/pagamentos/consulta.py`: `consultar_antes_de_decidir` e `ConsultaAoProvedorFalhou`.
- Testes: `tests/tecnicos/test_pagamentos_consulta.py` (A-1 a A-9) e, em `test_pagamentos_concorrencia.py`, A-10. Sem migração.

## Ciclo TDD

**Andaime (exceção técnica):** a exceção `ConsultaAoProvedorFalhou` (dados) e a função devolvendo lista vazia, sem consultar nada.

### Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pagamentos_consulta.py tests/tecnicos/test_pagamentos_concorrencia.py -q`: **9 failed, 8 passed**. Falhas por asserção: `assert [] == ['sim-1']`, `assert [] == ['sim-2', 'sim-3']`, `assert [] == ['busca', 'busca']`, `Failed: DID NOT RAISE ConsultaAoProvedorFalhou` (4) e, na concorrência, `a outra conexão não ficou esperando pela trava`. Os 8 que passaram são os testes de concorrência das fatias anteriores e o A-7.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_pagamento_aprovado_sem_aviso_e_identificado` (`acceptance`) | falhou (`assert [] == ['sim-1']`) |
| A-2 | `test_dois_pagamentos_aprovados_da_mesma_referencia` | falhou |
| A-3 | `test_busca_atrasada_e_corrigida_pela_reconsulta` | falhou |
| A-4 | `test_provedor_fora_do_ar_bloqueia` | falhou (`DID NOT RAISE`) |
| A-5 | `test_falha_numa_reconsulta_bloqueia_mas_mantem_o_que_foi_sincronizado` | falhou (`DID NOT RAISE`) |
| A-6 | `test_pagamento_registrado_que_o_provedor_nao_conhece_bloqueia` | falhou (`DID NOT RAISE`) |
| A-7 | `test_referencia_sem_pagamento_devolve_lista_vazia` | **passou no Red**: o andaime já devolve lista vazia; é o resultado esperado e o teste protege o caso contra regressão |
| A-8 | `test_consultas_repetidas_so_acrescentam_historico` | falhou |
| A-9 | `test_a_falha_nao_revela_valor_descricao_nem_dados_para_pagar` | falhou (`DID NOT RAISE`) |
| A-10 | `test_consulta_antes_de_decidir_durante_o_processamento_do_aviso` | falhou por asserção (espera da outra conexão: o andaime não toma a trava da linha) |

### Green

Os dois arquivos: **17 passed**. Suíte completa: **1902 passed** (eram 1892). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` (com as configurações de teste) sem erros.

## Decisões técnicas (derivadas da spec)

- Cada resposta da busca e cada reconsulta é sincronizada em `transaction.atomic()` próprio (savepoint quando há transação aberta); o que já foi sincronizado fica gravado se uma consulta posterior falhar (A-5).
- A reconsulta cobre os registros do mesmo provedor e da mesma referência que não vieram na busca, em ordem de `criado_no_provedor_em` e `id_externo`.
- Os três erros do provedor (`ProvedorIndisponivel`, `RecusaDoProvedor`, `PagamentoNaoEncontrado`) viram `ConsultaAoProvedorFalhou` com motivo `indisponivel`, `recusa` e `nao_encontrado`, com a exceção original encadeada; o log leva só a referência e o motivo.
- O serviço não segura travas durante a consulta (quem chama o usa antes de abrir a transação da decisão); a trava da linha só existe dentro de cada `sincronizar_pagamento`.

## Decisões que devem chamar o serviço

A tabela da spec (E08: aprovação do resultado da cobrança; E10: devolução; E11: apuração final; E12: cancelamento com reembolso; E13: pedido formal e repasse) fica registrada para as etapas seguintes; nenhuma decisão existe ainda, então nada nesta fatia a chama.

## Limites da verificação

Postgres real; o simulador é o único provedor. O bloqueio na tela e as mensagens ao administrador, e os testes de "nada é decidido quando o serviço levanta", são de cada etapa que chamar o serviço. Nenhuma mutação aplicada nesta fatia.
