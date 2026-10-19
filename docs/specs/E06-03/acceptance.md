# E06-03 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Nos critérios de concorrência, valem as regras de prevenção da correção E05-R04 (E05-01). Salvo indicação, a rodada de `F` entra em `fechamento` por `iniciar_fechamento` às 2026-11-02 13:30 UTC, com prazo às 2026-11-03 13:30 UTC (`T`); `P` tem limite 20; A tem 10 reservados. A tarefa de encerramento **não** roda. O relógio é controlado com `time-machine`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §15, E01-03 | limite | o estado padrão | `adicionar_interesse(B, P, "1")` em `T − 1 ms`, em `T` e em `T + 1 ms` | aceita em `T − 1 ms`; `InteressesBloqueados` com `prazo_encerrado` e a mensagem de sempre nos outros dois; a etapa continua `fechamento` |
| A-2 | Spec §5 | negativo | o relógio em `T + 1 min` | `reduzir_interesse(A, P, "1")`, `definir_interesse(A, P, "5")` e `definir_interesse(A, P, "0")` | `prazo_encerrado` nas três; reservado de A continua 10; nenhuma auditoria nova |
| A-3 | E05-02 | negativo | o relógio em `T + 1 min`; C com uma parcela `pendente` de 3 e livre 10 | `alocar_pendentes(F)` | devolve 0; C continua pendente; nenhuma auditoria `interesse.alocar_pendentes` |
| A-4 | E05-03, E05-07 | positivo | o relógio em `T + 1 min`; A também com 2 pendentes em `P`; C com 3 pendentes | `remover_pendente(A, P, "2")`; depois `suspender(admin, A)` | a remoção é aceita; a suspensão remove a parcela de A e libera 10, mas a fila não é atendida (C continua com 3 pendentes) |
| A-5 | E05-05 | negativo | o relógio em `T + 1 min` | A abre `/carrinho/` e `/catalogo/<F>/`; `POST /interesses/` com `quantidade=5` | nenhuma das páginas tem formulário de quantidade para `P`; o formulário "Remover pendentes" continua, se A tiver pendência; o `POST` responde 409 com "Os interesses deste fornecedor não podem ser alterados nesta etapa." |
| A-6 | Spec da fatia | negativo | uma rodada em `fechamento` por `update()`, sem nenhuma linha de prazo | `aceita_interesses(rodada, agora())` | `RuntimeError` |
| A-7 | Spec da fatia | positivo | rodada em `interesse` | `aceita_interesses` em qualquer instante | verdadeiro; nas etapas `fechamento_encerrado`, `pagamento` e `aguardando_fornecedor`, falso |
| A-8 | Spec da fatia | positivo | — | inspeciono o `review.md` e o diff dos testes existentes | a lista dos pontos de `apps/` trocados para `aceita_interesses`, com pelo menos os cinco citados na spec; a lista dos testes que receberam `dar_prazo_de_teste`; nenhuma asserção existente alterada; a suíte inteira verde |
| A-9 | Spec §15 | concorrência | o relógio em `T − 50 ms` | uma adição de B segura a trava do fornecedor (pausa depois de `travar_rodada_para_interesses`) enquanto outra adição de C espera; o relógio passa de `T` antes de a primeira confirmar | a de B confirma (validou antes de `T`); a de C é recusada com `prazo_encerrado`, porque lê `agora()` depois de obter as travas |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-7 | `tests/tecnicos/test_rodadas_fechamento_prazo.py` |
| A-1 | também marcado `acceptance`, com o comentário `§15 validar prazo nas ações` |
| A-8 | conferido pelo revisor no `review.md` |
| A-9 | `tests/tecnicos/test_rodadas_fechamento_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`). Como `time-machine` não atravessa threads de forma confiável, o teste pode controlar o relógio com `monkeypatch` de `agora` nos módulos que a leem, com um relógio compartilhado entre as threads. O meio usado fica registrado |
