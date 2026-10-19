# E06-04 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Nos critérios de concorrência, valem as regras de prevenção da correção E05-R04 (E05-01). Salvo indicação, a rodada de `F` entra em `fechamento` por `iniciar_fechamento` às 2026-11-02 13:30 UTC, com prazo `T` = 2026-11-03 13:30 UTC, e A tem 10 reservados de `P`. O relógio é controlado com `time-machine`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 28, Spec §7 | positivo | o relógio em `T − 2 h` | `prorrogar_fechamento(admin, rodada, T + 24 h)` | devolve `T + 24 h`; `prazo_do_fechamento` devolve `T + 24 h`; duas linhas de prazo no ciclo (`inicio` e `prorrogacao`); uma auditoria `rodada.prorrogar_fechamento` com `anterior` e `novo` em ISO 8601 UTC |
| A-2 | Spec da fatia | positivo | o estado do A-1 | em `T + 1 h`, `adicionar_interesse(B, P, "1")` | aceita (o bloqueio da E06-03 usa o prazo novo) |
| A-3 | Spec da fatia | positivo | o relógio em `T − 2 h` | prorrogo para `T + 24 h` e depois para `T + 48 h` | o prazo vigente é `T + 48 h`; três linhas de prazo; duas auditorias |
| A-4 | Spec da fatia | limite | — | `prorrogar_fechamento` para `T + 1 h` em `T − 1 ms`, em `T` e em `T + 1 ms` | aceita em `T − 1 ms`; recusada com `prazo_encerrado` e a mensagem da spec nos outros dois, sem gravar nada |
| A-5 | Spec da fatia | negativo | o relógio em `T − 2 h` | `prorrogar_fechamento` para `T` e para `T − 1 h` | `prazo_nao_posterior` nos dois, com a mensagem "O novo prazo precisa ser posterior ao prazo atual, 03/11/2026 às 10:30."; nada gravado |
| A-6 | Spec da fatia | negativo | (a) a rodada em `interesse`; (b) em `fechamento_encerrado` por `update()`; (c) em `pagamento` por `update()`; (d) uma rodada antiga, que não é mais a ativa | `prorrogar_fechamento(admin, rodada, T + 24 h)` | `fora_de_fechamento` em todos; nada gravado |
| A-7 | Spec §13 | negativo | um comprador, uma conta de fornecedor e `None` | `prorrogar_fechamento` | `PermissionDenied`; nada gravado |
| A-8 | E01-03 | negativo | o relógio em `T − 2 h` | `prorrogar_fechamento` com um `datetime` sem fuso | `InstanteSemFuso`; nada gravado |
| A-9 | Cenário 5, Spec §7 | negativo | o relógio em `T − 2 h`; A reduz para 1 e o valor elegível cai abaixo do mínimo | leio o prazo | continua `T`; nenhuma linha `prorrogacao` |
| A-10 | Spec da fatia | concorrência | o relógio em `T − 2 h` | duas prorrogações em threads: uma para `T + 24 h`, outra para `T + 12 h`, com a de `T + 24 h` segurando as travas primeiro | a de `T + 24 h` confirma; a de `T + 12 h` recebe `prazo_nao_posterior`; o prazo vigente é `T + 24 h` |
| A-11 | Spec da fatia | concorrência | o relógio em `T − 10 ms`; outra transação segura a trava do fornecedor | `prorrogar_fechamento(admin, rodada, T + 24 h)` é chamada e espera a trava; o relógio passa de `T` antes de a trava ser solta | recusada com `prazo_encerrado`, porque o prazo é lido depois das travas; nenhuma linha `prorrogacao`. O relógio é compartilhado entre as threads, como na E06-03 A-9 |
| A-12 | E06-R03 | positivo | o fechamento iniciado às 2026-11-02 13:30 UTC (prazo 2026-11-03 13:30 UTC) | `prorrogar_fechamento(admin, rodada, datetime(2026, 11, 4, 1, 30, tzinfo=ZoneInfo("America/Sao_Paulo")))`; noutro caso, com um instante em `+05:30` equivalente | `alteracoes["novo"]` igual a `"2026-11-04T04:30:00+00:00"` e `alteracoes["anterior"]` igual a `"2026-11-03T13:30:00+00:00"` nos dois; `prazo_do_fechamento` igual a 2026-11-04 04:30 UTC |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-9 | `tests/tecnicos/test_rodadas_fechamento_prorrogacao.py` |
| A-12 | `tests/tecnicos/test_rodadas_fechamento_prorrogacao.py`; inclui literalmente a prova `test_prorrogacao_audita_utc` do revisor de `2fbf143` |
| A-1 e A-9 | também marcados `acceptance`, com os comentários `cenário 28` e `cenário 5` |
| A-10, A-11 | `tests/tecnicos/test_rodadas_fechamento_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
