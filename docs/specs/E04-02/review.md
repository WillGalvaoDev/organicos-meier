# E04-02 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `8b4e771` (2026-10-18). E04 global: **APROVADO**. Histórico preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia e a E04-01.

## Arquivos

- `apps/notificacoes/emissao.py` (novo): `emitir_evento`, `emitir_evento_para_varios`, `ChaveDeEventoReutilizada`.
- `apps/notificacoes/models.py`: `Envio`, `SituacaoEnvio`, com `CHECK`s e índice parcial.
- `apps/notificacoes/gatilhos.py`: triggers do envio. Migração `0002_envio`.
- `tests/fabricas.py` (`EnvioFactory`); testes em `test_notificacoes_emissao.py` (novo), `test_notificacoes_modelo.py` e `test_notificacoes_concorrencia.py`.

## Decisões técnicas

- **Idempotência da emissão única:** leitura prévia pela chave; se não existe, `create` dentro de um *savepoint*. Se outra transação confirmou a mesma chave no intervalo, o `IntegrityError` da `UNIQUE` é capturado, a existente é relida (READ COMMITTED) e comparada. A segunda emissão simultânea espera a primeira confirmar (A-7).
- **Lote:** validação de todas as contas antes de gravar; um `INSERT ... ON CONFLICT (chave) DO NOTHING RETURNING id, chave` em SQL cru (o `bulk_create(ignore_conflicts=True)` do Django não devolve quais linhas entraram); uma leitura das existentes para comparar o conteúdo; um `bulk_create` dos envios. Tudo num *savepoint*, de modo que `ChaveDeEventoReutilizada` desfaz as inserções do lote. O número de consultas não depende do número de contas (A-10: teto de 8, idêntico para 1 e 30 contas).
- Os campos `criado_em` e `proxima_tentativa_em` do envio recebem o mesmo instante `agora()`.
- Logs: só um `logger.error` com o evento e o id da conta na chave reutilizada; nunca e-mail, título nem corpo.
- Trigger do envio: recusa `DELETE`, recusa alterar o conteúdo e recusa qualquer `UPDATE` de envio já concluído; permite alterar os campos de estado do envio pendente.
- `Envio` e `Notificacao` são os únicos modelos tocados; as etapas ainda não chamam a emissão (E05 em diante).

## TDD

**Red.** Andaime (modelo `Envio` sem restrições nem triggers; `emitir_evento` devolvendo objeto não gravado; lote devolvendo 0): `uv run pytest tests/tecnicos/test_notificacoes_emissao.py tests/tecnicos/test_notificacoes_modelo.py tests/tecnicos/test_notificacoes_concorrencia.py -q` deu **32 failed, 41 passed**, todas por asserção (nada gravado, banco aceitando `DELETE`/`UPDATE`/linhas inválidas, `TransactionManagementError` não levantada). Passaram já no Red os testes de E04-01 e o A-4 (transação desfeita: nada é gravado por não haver gravação no andaime).

**Green.** Mesmos arquivos: **73 passed**. Suíte completa: **1295 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

Ajustes de teste feitos antes do Red final, por erro meu na escrita (nenhuma garantia afrouxada): o valor `situacao='inexistente'` excedia o `varchar(10)` e dava `DataError` em vez de `IntegrityError`, trocado por `'outra'`; os casos de `notificacao`/`conta` nulos passaram a informar os campos que a fábrica derivava delas.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 a A-6, A-8 a A-11, A-14 | `test_notificacoes_emissao.py` (A-5 marcado `acceptance`, cenário 17) |
| A-7 | `test_notificacoes_concorrencia.py::test_duas_emissoes_com_a_mesma_chave_geram_uma_so` |
| A-12, A-13 (e `CHECK`s) | `test_notificacoes_modelo.py` |

## Limites da verificação

Os envios de WhatsApp não são criados nesta fatia (E04-04). Nenhum serviço externo é chamado. Cliente e banco reais (Postgres); sem navegador.


## Revisão independente — 0b52010 — 2026-10-17

**Parecer da fatia: REPROVADO. E04 global: REPROVADO.**

A-1 a A-14 conferidos: transação, rollback, UNIQUE, comparação de conteúdo, lote atômico, deduplicação, conteúdo congelado e consultas constantes. Probe de lote parcialmente existente passou. R01 importante: emissão única e em lote herdam a validação insuficiente do link.

Verificação independente: **1385 passed em 160,23 s** na suíte completa. Probes adicionais: **10 failed, 4 passed em 4,39 s**, mais **1 passed em 2,52 s** no caso de isolamento acrescentado. Dez falhas correspondem a R01 (oito) e R02 (duas). Lint, formatação, tipos, Django e CI passaram.

Comandos, matriz, reproduções, TDD, critérios de correção e limites no [parecer consolidado E04-07](../E04-07/review.md). Nenhum código ou teste versionado foi alterado pelo revisor.


## Correção E04-R01 — implementador (aguardando nova revisão)

A-15 (`emitir_evento` e `emitir_evento_para_varios`, com dois compradores, recusando cada link da lista e sem gravar `Notificacao` nem `Envio`; e aceitando `/catalogo/1/?q=abc#x`) está em `tests/tecnicos/test_notificacoes_link_interno.py`. Red e Green são os da E04-01: as 18 recusas de emissão falharam com `DID NOT RAISE` e passaram com a regra compartilhada de `validar_notificacao`; nenhuma validação nova foi escrita nas duas funções. O caso de aceitação passou já no Red (comportamento existente).

Verificação final da correção: suíte completa **1461 passed**; `ruff check`, `ruff format --check`, `mypy .`, `makemigrations --check --dry-run` e `manage.py check` sem erros. Nenhuma asserção existente foi afrouxada ou removida.


## Revalidação independente — 8b4e771 — 2026-10-18

**Parecer da fatia: APROVADO. E04 global: APROVADO.**

R01 encerrado também na emissão única e em lote. A-15 atendido pela validação compartilhada antes da gravação; os probes das duas entradas passam. Mantidas atomicidade e idempotência.

Suíte completa: **1461 passed em 137,79 s**. Script independente original da revisão de 0b52010, sem alterações: **15 passed em 6,78 s**. As dez falhas anteriores não se reproduzem. Lint, formatação, tipos, verificações Django e CI passaram. Evidências e limites no [parecer consolidado](../E04-07/review.md), seção deste SHA.
