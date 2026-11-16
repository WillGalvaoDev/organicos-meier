# E15-01 — Registro do implementador

Agente 2.

## Red

- Commit `08c3367`: `uv run pytest tests/tecnicos/test_execucao_das_tarefas.py` → 14 falhas (`ModuleNotFoundError: apps.operacao`), uma por critério A-1 a A-14.

## Green

- App novo `apps/operacao` (`models.py`, `catalogo.py`, `execucao.py`, migração `0001_initial`), registrado em `INSTALLED_APPS`.
- Dez tarefas periódicas envolvidas por `execucao_monitorada` (`apps/notificacoes`, `pagamentos`, `rodadas`, `financeiro` e `pedidos` / `tarefas.py`).
- Gravação em transação própria, com `select_for_update`; a criação concorrente é decidida pelo `UNIQUE` (`_criar` é o ponto de pausa do A-9) e quem perde relê o registro.
- Resultado: `14 passed`. Tarefas e domínios relacionados: `-k "tarefa or periodic or envio or fechamento or conciliacao or invariante or pedido_formal"` → 447 passed.

## Ajustes depois do Red (só no arquivo novo, sem tocar nas asserções)

Aviso de lint do ruff (PT011 com `match`; importação do `ExecucaoDaTarefa` no A-8 para o mesmo objeto que o código usa).

## Decisões técnicas

- `execucao_monitorada` captura `Exception` (não `BaseException`): `KeyboardInterrupt` e `SystemExit` passam sem registro.
- Falha monótona: `ultima_falha_em` e `ultimo_erro` só mudam com instante maior; `falhas_seguidas` conta a falha sempre.


## Revisão independente — agente 3 — 2026-11-16

Referência auditada: `2f5958c`, branch `e15-especificacoes`, sobre `8b1739f` (E14). Foram lidos os documentos-base (funcional v1.7 e infraestrutura v1.8), as sete especificações e matrizes E15 e os registros Red/Green, antes da comparação com código e testes. Este parecer acrescenta-se ao registro do implementador, preservado integralmente. Evidências globais e código das reproduções estão em [E15-07/review.md](../E15-07/review.md).

**Veredito da fatia: APROVADO.** A-1 a A-14 confrontados com registro transacional, catálogo e envoltórios das dez tarefas: exceção original preservada, log só da classe, falha de gravação isolada, criação concorrente única, tolerância estrita e leitura sem escrita. Não identificado achado próprio nesta fatia. A falha de autoalerta pertence à regra 10 da E15-02, não ao registro da execução.

TDD: `08c3367` contém os testes antes da produção de `582e308`; o registro informa 14 falhas por módulo ausente e depois 14 aprovações. A inspeção do histórico confirma essa separação. Não reexecutei o checkout histórico do Red.
