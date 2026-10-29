# E09-04 — Revalidação independente sobre 5a8b6b6

**Veredito: APROVADO.**

Revisão independente em **2026-10-29**, implementação `5a8b6b6acf696de3d546532d8590c2d10fd5ed0d`, branch `e09-implementacao`; HEAD documental `130c113`. **E09 APROVADA; R10 residual encerrado.** A delimitação técnica foi especificada em `6800f22`, antes dos testes (`91f2911`) e da correção (`5a8b6b6`). Nenhuma regra comercial ou financeira foi alterada.

Validação independente: **2433 passed in 308.21s**, suíte completa em banco de testes separado; **19 passed in 13.75s**, provas independentes. Ruff lint passou, 329 arquivos com formatação conforme, mypy sem erros em 393 arquivos, nenhuma migração pendente. As 13 provas anteriores e os três controles do parecer residual foram reexecutados sem alterar suas asserções; mais três controles verificam a composição dos escopos sob TestCase.

Aceite desta fatia mantido. Sem alteração de implementação ou critérios locais desde o parecer anterior; a guarda compartilhada foi revalidada. Nenhum achado impeditivo remanescente. Detalhes, comandos e limitações no [parecer consolidado](../E09-08/review.md).

---

# E09-04 — Revalidação independente sobre d365475

**Veredito: APROVADO no escopo desta fatia.**

Revisão executada em 2026-10-22 e concluída em 2026-10-23, base `d365475e68c26f9a2f2e58158a19d643a5aa30b2`, branch `e09-implementacao`. Conferidos os adendos de `5bdc419`, os commits de testes anteriores à produção (`afbe7c0` e `d6a09d3`), as correções e seus registros. O histórico anterior foi preservado integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2428 passed in 361.92s**; Ruff lint passou, formatação de 329 arquivos conforme, mypy sem erros em 393 arquivos e nenhuma migração pendente. As **13 provas do parecer anterior passaram, sem alteração, em 13.66s**. Controle adicional do limite declarado: **1 failed, 2 passed in 5.01s**. O único insucesso é o isolamento da guarda em `TestCase` com objeto `atomic(savepoint=False)` reutilizado; os controles com transações reais passam. Detalhes e reprodução no [parecer consolidado](../E09-08/review.md).

## Matriz e conclusão

A-1–A-13: mantida a aprovação. Suíte completa e prova de tarifa com sincronização real verdes. Nenhuma mudança de entrada, escritor único ou destinação nesta rodada; sem novo achado. A E09 global ainda depende de R10.

---

# E09-04 — Revalidação independente sobre 2930ffd

**Veredito: APROVADO no escopo desta fatia.**

Revisão independente de 2026-10-22, base `2930ffddc8fc53ad21c6bb777719b19508d1a4da` (branch `e09-implementacao`). Foram conferidos os adendos de especificação e aceitação em `6dc9850`, o commit de testes Red `e3733ad`, os diffs das correções e os registros de implementação. O histórico anterior permanece integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2418 passed in 234.26s**, sem filtro; `uv run ruff check .` passou; `uv run ruff format --check .` → 329 arquivos; `uv run mypy .` → 393 arquivos sem erros; `uv run python manage.py makemigrations --check --dry-run` → nenhuma alteração pendente. Provas adicionais: **4 failed, 9 passed in 9.77s**. Reprodução completa, limites e veredito global no [parecer consolidado](../E09-08/review.md).

## Matriz e achados

A-1–A-13: testes verdes. Conferido receptor que obtém e trava o conjunto de entrada, tarifa e cobertura antes dos lançamentos, incluindo criação da obrigação de devolução; alerta condicionado à entrada nova mantém a idempotência mesmo com a obrigação criada antes. Sem novo achado próprio. O cenário independente da R07 utiliza sincronização, entrada e tarifa reais e demonstra que a falha residual está no pareamento da conciliação, não na criação da despesa/lançamento. A E09 global não está aprovada.

---

# E09-04 — Parecer independente sobre 34f9547

**Veredito: APROVADO no escopo desta fatia.**

Base: `34f9547ae7962687ed96997e3338914f985a277f`, branch `e09-implementacao`, revisão independente em 2026-10-22. Lidos documentos-base funcional v1.6 e infraestrutura v1.7, AGENTS.md, especificações, critérios, código, testes e registros das oito fatias. Histórico do implementador preservado integralmente abaixo.

Verificações independentes:

- `uv run pytest -q`: **2398 passed in 273.67s**, sem filtro, PostgreSQL e banco separado do simulador.
- `uv run ruff check .`: passou; `uv run ruff format --check .`: 328 arquivos conformes.
- `uv run mypy .`: 391 arquivos sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais, fora da suíte versionada: **9 failed in 8.57s**, pelos defeitos descritos no [parecer consolidado](../E09-08/review.md), que contém o código completo para reprodução.

Não foram alterados código de produção nem testes versionados. Testes verdes dos critérios existentes não bastam para aprovar as interações financeiras. O revisor não presenciou os ciclos TDD históricos; conferiu os registros e não trata mutação posterior como Red anterior à implementação.

## Matriz e achados

A-1–A-13: testes existentes verdes. Conferidos entrada por componentes na mesma transação da destinação, obrigação integral dos pagamentos não quitantes, tarifa sem desviar recursos de terceiros, preenchimento tardio, idempotência e alertas. A-11/A-12 reutilizam proteções de pagamento/situação herdadas; não se exige inventar Red histórico de uma proteção anterior. A limitação de sensibilidade de A-12 permanece em M-7. Nenhum achado próprio novo na criação das entradas. R05 trata a avaliação periódica de insuficiência exigida na integração E09-05/E09-07. A E09 global não está aprovada.

---

# E09-04 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- `apps/pedidos/sinais.py` (sinal `destino_do_pagamento_decidido`) e `apps/pedidos/quitacao.py` (o sinal é enviado por `_gravar_destino`, logo depois de gravar o destino, na mesma transação).
- `apps/financeiro/entradas.py` (`registrar_entrada`, `registrar_tarifa`, `registrar_tarifas_pendentes_agora`), `receptores.py`, `tarefas.py` (tarefa `registrar_tarifas_pendentes`, a cada 10 minutos), `apps.py` (liga o receptor), `models.py` (`ObrigacaoComComprador`, `Despesa`, `TipoDeDespesa`), migrações `0004_obrigacao_e_despesa.py` (com a trigger só-inserção) e `0005_restricoes_da_obrigacao_e_da_despesa.py`.
- `apps/pagamentos/consulta.py`: leitura nova `pagamentos_com_tarifa_e_destino()`.
- Testes: `tests/tecnicos/test_financeiro_entradas.py` (A-1, A-2, A-5 a A-10, A-13 e as restrições), `tests/tecnicos/test_financeiro_concorrencia.py` (A-11, A-12), `tests/aceitacao/test_cenario_30_tarifa.py`, `tests/aceitacao/test_cenario_39_dois_pagamentos.py`. Apoio: `pedido_composto` em `tests/apoio/financeiro.py`.

## Andaime (exceção técnica)

Antes do Red: o sinal (definido, sem ser enviado); os modelos `ObrigacaoComComprador` e `Despesa` (só a unicidade) e as migrações; as três funções de `entradas.py` com corpo trivial (`None`, `None`, `0`). O envio do sinal e o receptor **não** estavam no andaime: são o comportamento.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_entradas.py tests/tecnicos/test_financeiro_concorrencia.py tests/aceitacao/test_cenario_30_tarifa.py tests/aceitacao/test_cenario_39_dois_pagamentos.py -q -p no:cacheprovider` contra o andaime: **16 falharam, 5 passaram**.

Na primeira execução, 17 erros eram de infraestrutura de teste: `DatabaseOperationForbidden: Database threaded connections to 'simulador_pagamentos' are not allowed`. O gancho de `tests/conftest.py` só declara o banco do simulador para os prefixos `test_pagamentos_`, `test_pedidos_` e `test_simulador_pagamentos_`; acrescentei `test_financeiro_`, `test_cenario_30_` e `test_cenario_39_`. Depois, oito falhas eram `ValueError: not enough values to unpack`; troquei a desestruturação por `_um(...)`, que afirma `len == 1` com mensagem. E um dos testes do apoio de concorrência aprovava a segunda cobrança antes de ela existir (`aprovação anterior à criação da cobrança`); corrigi o instante. Nenhuma dessas correções mudou o que os testes exigem.

| Critério | Teste | Resultado do Red |
|---|---|---|
| A-1, A-2 | `test_pagamento_que_quita_...`, `test_a_tarifa_vira_despesa_...`, `test_cenario_30_...` | `esperava 1 registro, há 0` (nenhum movimento nem despesa) |
| A-3, A-4 | os dois de `test_cenario_39_...` | idem; `assert 0 == 1` nas obrigações |
| A-5, A-6 | `test_pagamento_sem_pedido_...`, `test_outros_motivos_...` (3) | `esperava 1 registro, há 0` |
| A-8, A-9, A-13 | `test_tarifa_informada_depois_...`, `test_tarifa_zero_...`, `test_componentes_zerados_...` | `assert 0 == 1`, `esperava 1 registro, há 0` |
| A-10 | `test_excecao_depois_do_receptor_financeiro_desfaz_tudo` | `DID NOT RAISE RuntimeError` (o sinal ainda não é enviado) |
| A-11, A-12 | `test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo`, `test_aviso_e_reconsulta_...` | `assert 0 == 1` (nenhuma entrada) |
| Restrições | `test_o_banco_recusa_obrigacao_e_despesa_incoerentes` | `DID NOT RAISE IntegrityError` |
| A-7 | `test_repetir_nao_cria_nada_de_novo` | **passou já no Red**: sem nada registrado, nada se repete; guarda de regressão que só vale depois do Green |

## Green

Primeiro o envio do sinal na quitação, o receptor e os três serviços: **20 passaram, 1 falhou** (as restrições do banco, ainda sem `CHECK`). Depois as restrições (`obrigacao_origem_preenchida`, `obrigacao_componentes_nao_negativos`, `obrigacao_devido_positivo`, `obrigacao_pedido_todo_ou_nada`, `despesa_valor_positivo`, `despesa_coerente_com_o_tipo`): os quatro arquivos, **21 passed**.

**A-11 e A-12 e as proteções que já existiam.** As travas são da E08-04 (pagamento → situação do pedido) e da E09-01 (contas do livro), então os dois testes passaram assim que a entrada existiu. Sensibilidade por mutação (não é Red), com `test_financeiro_concorrencia.py` inteiro, por `scratchpad/mutacoes_e09.py`:

| Mutação | Resultado |
|---|---|
| `decidir_destino` sem `select_for_update` da situação do pedido | **1 falhou, 5 passaram**: `test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo` (A-11) |
| `lancar` sem a trava das contas | 2 falharam: os A-14 e A-15 da E09-01; os da E09-04 continuam verdes (a trava do pagamento e da situação já serializa) |
| `sincronizar_pagamento` sem a trava do pagamento | **nenhuma falha**: **limite declarado do A-12** |

Cada mutação foi restaurada e o arquivo inteiro voltou a **6 passed**. Sobre o limite do A-12: sem a trava do pagamento, a sincronização concorrente do mesmo pagamento ainda é contida pela trava da situação do pedido (a segunda decisão encontra o destino existente), pela chave idempotente do movimento e pela unicidade da despesa. O teste protege o resultado (uma entrada e uma despesa), mas não detecta a retirada dessa trava em particular. Não reforcei o teste: seria dependência de implementação.

## Testes antigos e infraestrutura de teste ajustados

- `tests/conftest.py`: os três prefixos novos no gancho do banco do simulador (acima).
- Nenhum teste de E07 ou E08 foi alterado nesta fatia.

## Decisões técnicas

- **Origem da obrigação.** `ObrigacaoComComprador.origem_tipo/origem_id` guardam `pedidos.destinodopagamento` e a `pk` do destino, com `UNIQUE`; o movimento de entrada guarda o pagamento como origem, como a spec manda.
- **O alerta abre uma vez, com a obrigação.** `registrar_entrada` só chama `abrir_alerta` quando a obrigação acabou de nascer; repetir o registro depois de o alerta ser resolvido (E09-06) não o reabre.
- **A tarefa trava antes de registrar.** `registrar_tarifas_pendentes_agora` trava o pagamento (primeira trava da ordem global) em transação própria por pagamento, e só conta a despesa que ela mesma criou.
- **`entradas.py` não cita as classes de pagamento** (heurística M-2): usa um `Protocol` e `consulta.py`.
- **Pedido sem componente.** Componente com valor zero não gera transferência (A-13).

## Verificação

Os quatro arquivos da fatia: **21 passed**. Suíte completa, sem filtro, com o estado da fatia: `uv run pytest -q -p no:cacheprovider` → **2292 passed in 286.76s**; `ruff check`, `ruff format --check` (309 arquivos), `mypy` (368 arquivos) e `makemigrations --check`: limpos.
