# E09-05 — Revalidação independente sobre 5a8b6b6

**Veredito: APROVADO.**

Revisão independente em **2026-10-29**, implementação `5a8b6b6acf696de3d546532d8590c2d10fd5ed0d`, branch `e09-implementacao`; HEAD documental `130c113`. **E09 APROVADA; R10 residual encerrado.** A delimitação técnica foi especificada em `6800f22`, antes dos testes (`91f2911`) e da correção (`5a8b6b6`). Nenhuma regra comercial ou financeira foi alterada.

Validação independente: **2433 passed in 308.21s**, suíte completa em banco de testes separado; **19 passed in 13.75s**, provas independentes. Ruff lint passou, 329 arquivos com formatação conforme, mypy sem erros em 393 arquivos, nenhuma migração pendente. As 13 provas anteriores e os três controles do parecer residual foram reexecutados sem alterar suas asserções; mais três controles verificam a composição dos escopos sob TestCase.

Aceite desta fatia mantido. Sem alteração de implementação ou critérios locais desde o parecer anterior; a guarda compartilhada foi revalidada. Nenhum achado impeditivo remanescente. Detalhes, comandos e limitações no [parecer consolidado](../E09-08/review.md).

---

# E09-05 — Revalidação independente sobre d365475

**Veredito: APROVADO no escopo desta fatia.**

Revisão executada em 2026-10-22 e concluída em 2026-10-23, base `d365475e68c26f9a2f2e58158a19d643a5aa30b2`, branch `e09-implementacao`. Conferidos os adendos de `5bdc419`, os commits de testes anteriores à produção (`afbe7c0` e `d6a09d3`), as correções e seus registros. O histórico anterior foi preservado integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2428 passed in 361.92s**; Ruff lint passou, formatação de 329 arquivos conforme, mypy sem erros em 393 arquivos e nenhuma migração pendente. As **13 provas do parecer anterior passaram, sem alteração, em 13.66s**. Controle adicional do limite declarado: **1 failed, 2 passed in 5.01s**. O único insucesso é o isolamento da guarda em `TestCase` com objeto `atomic(savepoint=False)` reutilizado; os controles com transações reais passam. Detalhes e reprodução no [parecer consolidado](../E09-08/review.md).

## Matriz e conclusão

A-1–A-17: mantida a aprovação dos fluxos da reserva. As provas independentes de cobertura cruzada e designação versus liquidação passaram novamente. R01/R02 originais e R05 continuam encerrados; nenhum defeito financeiro novo foi demonstrado. A limitação residual da guarda em TestCase fica em R10/E09-01 e impede o aceite global do contrato técnico atual.

---

# E09-05 — Revalidação independente sobre 2930ffd

**Veredito: APROVADO no escopo desta fatia.**

Revisão independente de 2026-10-22, base `2930ffddc8fc53ad21c6bb777719b19508d1a4da` (branch `e09-implementacao`). Foram conferidos os adendos de especificação e aceitação em `6dc9850`, o commit de testes Red `e3733ad`, os diffs das correções e os registros de implementação. O histórico anterior permanece integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2418 passed in 234.26s**, sem filtro; `uv run ruff check .` passou; `uv run ruff format --check .` → 329 arquivos; `uv run mypy .` → 393 arquivos sem erros; `uv run python manage.py makemigrations --check --dry-run` → nenhuma alteração pendente. Provas adicionais: **4 failed, 9 passed in 9.77s**. Reprodução completa, limites e veredito global no [parecer consolidado](../E09-08/review.md).

## Matriz e achados

A-1–A-17: testes verdes. Utilização trava destino e reserva juntos antes de ler o pendente; designação cria/trava a conta da obrigação e a reserva em ordem de PK. A-16/A-17 cobrem a inversão original e a disputa de obrigação ainda sem conta. Provas independentes de cobertura cruzada e designação versus liquidação passaram: uma cobertura apenas; duas operações válidas de designação/liquidação concluem sem o deadlock original. **R01/R02 encerrados quanto aos defeitos originais; R05 encerrado na integração periódica.** A guarda compartilhada tem o novo achado R10 na E09-01; esta aprovação local não aprova a entrega.

---

# E09-05 — Parecer independente sobre 34f9547

**Veredito: REPROVADO.**

Base: `34f9547ae7962687ed96997e3338914f985a277f`, branch `e09-implementacao`, revisão independente em 2026-10-22. Lidos documentos-base funcional v1.6 e infraestrutura v1.7, AGENTS.md, especificações, critérios, código, testes e registros das oito fatias. Histórico do implementador preservado integralmente abaixo.

Verificações independentes:

- `uv run pytest -q`: **2398 passed in 273.67s**, sem filtro, PostgreSQL e banco separado do simulador.
- `uv run ruff check .`: passou; `uv run ruff format --check .`: 328 arquivos conformes.
- `uv run mypy .`: 391 arquivos sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais, fora da suíte versionada: **9 failed in 8.57s**, pelos defeitos descritos no [parecer consolidado](../E09-08/review.md), que contém o código completo para reprodução.

Não foram alterados código de produção nem testes versionados. Testes verdes dos critérios existentes não bastam para aprovar as interações financeiras. O revisor não presenciou os ciclos TDD históricos; conferiu os registros e não trata mutação posterior como Red anterior à implementação.

## Matriz e achados

A-1–A-15: testes existentes verdes, porém não cobrem as interações que falham. **R01 bloqueador:** reserva e receita cobrem duas vezes a mesma despesa (A-6/A-7 e E09-06 A-4/A-16). **R02 bloqueador:** reserva → obrigação diverge da ordem por PK na liquidação e causa deadlock. **R05 importante:** tarefa do invariante não chama avaliar_reserva, contrariando a seção de obrigações sem cobertura da spec. O registro Red/Green da reserva não cobre essas integrações; exigir Red específico nas correções.

---

# E09-05 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- `apps/financeiro/reserva.py` (`registrar_aporte`, `designar_reserva`, `desfazer_designacao`, `utilizar_reserva`, `situacao_da_reserva`, `itens_sem_cobertura`, `obrigacoes_sem_cobertura`, `avaliar_reserva` e as cinco exceções), `models.py` (`DesignacaoDaReserva`, `DesignacaoDesfeita`), migrações `0006_designacoes_da_reserva.py` (com a trigger só-inserção) e `0007_restricoes_das_designacoes.py`.
- Testes: `tests/tecnicos/test_financeiro_reserva.py` (A-1 a A-11, A-15 e as restrições), `tests/tecnicos/test_financeiro_concorrencia.py` (A-12 a A-14), `tests/aceitacao/test_cenario_29_aporte.py`, `tests/aceitacao/test_cenario_34_reserva_insuficiente.py`. Apoio: `obrigacao_de_teste` e `despesa_de_tarifa` em `tests/apoio/financeiro.py`.

## Andaime (exceção técnica)

Antes do Red: os dois modelos (sem as restrições `CHECK`, que são comportamento testado) e as migrações; `reserva.py` com as exceções, os tipos e as assinaturas com corpo trivial (`situacao_da_reserva` zerada, listas vazias, objetos não salvos).

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_reserva.py tests/tecnicos/test_financeiro_concorrencia.py tests/aceitacao/test_cenario_29_aporte.py tests/aceitacao/test_cenario_34_reserva_insuficiente.py -q -p no:cacheprovider`: **17 falharam, 7 passaram**. Todas as falhas são asserções (`DID NOT RAISE ...`, `assert Decimal('0.00') == Decimal('70.00')`, `assert [] == [('obrigacao', Decimal('50.00'))]`).

| Critério | Teste | Resultado do Red |
|---|---|---|
| A-1 a A-3, A-6, A-15 | os testes do aporte, da designação e da utilização | saldo e livre zerados; listas vazias |
| A-2, A-4, A-7, A-8, A-10, A-11 | os testes de recusa | `DID NOT RAISE AporteRepetido / ReservaInsuficiente / CoberturaExcedente / DesignacaoEncerrada / InvarianteViolado / PermissionDenied` |
| A-5 | `test_obrigacoes_sem_cobertura_...` | `assert Decimal('0.00') == Decimal('52.00')` |
| Restrições | `test_o_banco_recusa_designacao_incoerente` | `DID NOT RAISE IntegrityError` |
| A-12 a A-14 | os três de `test_financeiro_concorrencia.py` | ver "Green" |
| A-9 | `test_nenhuma_tarefa_periodica_faz_aporte` | **passou já no Red**: nada cria aporte, nem o andaime; guarda de regressão (P-4) que percorre o registro das tarefas periódicas do Procrastinate, então vale também para as tarefas das fatias seguintes |

## Green, em dois passos (regra da concorrência)

1. **Verde funcional sem a trava da reserva:** `reserva.py` completo, mas calculando o livre sem travar a conta `reserva`. Os testes sequenciais: **14 passaram, 1 falhou** (as restrições do banco). **Red da corrida**, por asserção, nos três testes de concorrência: `assert 2 == 1` em `sum(e is None ...)` (as duas designações passam, a designação e a utilização passam, e os dois aportes iguais passam). Antes de registrar este Red, corrigi o teste do A-14: a conta `reserva` nascia dentro da própria transação paralela e, por isso, a criação dela já serializava as duas chamadas; passei a criá-la antes, para que só a trava da reserva decida.
2. **A trava:** `_travar_a_reserva()` (e a trava da conta da obrigação, quando ela existe) antes de calcular o livre, em todas as operações. Os quatro arquivos: **23 passaram, 1 falhou** (as restrições). Depois as restrições `designacao_valor_positivo`, `designacao_justificativa_preenchida` e `desfeita_justificativa_preenchida`: **24 passed**.

## Decisões técnicas

- **Quem é o autor.** `PermissionDenied` para quem não é a conta do administrador ativa (comprador, fornecedor, `AnonymousUser`, `None`). A nova autenticação por passkey fica na rota (E09-08).
- **Chave da utilização.** `cobertura:<despesa>:<uuid>`: cada decisão do administrador é um movimento próprio. A proteção contra clique duplo é do formulário (E09-08); o aporte, que tem identificação do depósito, é idempotente pela chave.
- **O valor coberto de uma despesa** é a soma das transferências dos movimentos `cobertura_de_despesa` cuja origem é a despesa (`financeiro.despesa`); a E09-06 usa a mesma origem para a cobertura pela receita.
- **O que falta cobrir numa obrigação** é o devido menos tudo que entrou na conta dela (o saldo mais o já devolvido) menos o designado ativo; nunca abaixo de zero.
- **Cálculo sem cache.** `itens_sem_cobertura` percorre todas as obrigações e despesas; a escala desta etapa não pede mais. Fica como candidata a M-n se a lista crescer.
- **Consumo da designação.** Pertence à liquidação (E09-06); o comprometido passa a descontá-lo lá.

## Verificação

`ruff check`, `ruff format --check` (313 arquivos), `mypy` (374 arquivos) e `makemigrations --check`: limpos. Os arquivos da fatia: **24 passed**; o conjunto `financeiro`, cenários 29/30/32/34/39, matriz de eventos e fronteiras: **131 passed**. A suíte completa, sem filtro, é registrada na verificação da E09-06.
