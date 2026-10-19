# E06-05 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Nos critérios de concorrência, valem as regras de prevenção da correção E05-R04 (E05-01).

Salvo indicação:

- O fornecedor `F` ("Sítio Boa Terra") tem mínimo R$ 0,00. Com isso, a verificação da E06-06 nunca devolve a rodada para interesse nestes critérios.
- O produto `P` ("Ovos") custa R$ 10,00, tem múltiplo 12, incremento 1 e não tem limite.
- As parcelas são criadas pelos serviços da E05-01, na ordem indicada.
- O fechamento é iniciado às 2026-11-02 13:30 UTC, com prazo `T` = 2026-11-03 13:30 UTC.
- O relógio é controlado com `time-machine`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 7, Spec §6.3 | positivo | A adiciona 8 e depois B adiciona 10 | em `T`, `encerrar_fechamento(rodada)` | etapa `fechamento_encerrado`; A com 8; a parcela de B `ativa` com 4 reservados e `quantidade_original` 10; B recebe um aviso `excedentes_removidos` com título "Excedentes removidos: Ovos" e corpo com "6 unidade de Ovos não completaram caixa" e "Continuam no seu interesse: 4 unidade"; A não recebe aviso; uma auditoria `rodada.encerrar_fechamento` com autor `SISTEMA` e `removidas` `[[<parcela de B>, <P>, "6.000"]]` |
| A-2 | Spec §6.3, §5 | positivo | A adiciona 6, B adiciona 4 e A adiciona mais 5 (total 15) | `encerrar_fechamento` em `T` | ficam 12: A(6), B(4) e a segunda parcela de A com 2; saem 3 da última parcela; A recebe um aviso com "3" removidas e "8" mantidas |
| A-3 | Spec da fatia | positivo | A com 7 | `encerrar_fechamento` em `T` | a parcela de A fica `removida`; o aviso tem "7" removidas e "0" mantidas |
| A-4 | Spec da fatia | positivo | A com 12 e B com 12 | `encerrar_fechamento` em `T` | nada removido; nenhum aviso; `removidas` vazia; etapa `fechamento_encerrado` |
| A-5 | Spec §6.1, Infra 4.10 | positivo | `K` em kg, múltiplo 1, incremento 0,25; A com 1,5 e depois B com 1,25 | `encerrar_fechamento` em `T` | ficam 2 kg: A com 1,5 e B com 0,5; o aviso de B tem "0,75 kg" removidas |
| A-6 | Spec da fatia, R-6 | positivo | A com uma parcela `ativa` de 5 reservados e 3 pendentes (por fábrica), a única de `P` | `encerrar_fechamento` em `T` | a parcela fica `pendente`, com 0 reservado e 3 pendentes |
| A-7 | Spec da fatia | positivo | um produto `Q` sem múltiplo com A em 7 | `encerrar_fechamento` em `T` | `Q` intacto; nenhum aviso de `Q` |
| A-8 | Spec da fatia | negativo | o estado do A-1 | `encerrar_fechamento` em `T − 1 ms`; depois em `T`; depois de novo | a primeira devolve `None` sem gravar; a segunda encerra; a terceira devolve `None`, sem auditoria nem aviso novos |
| A-9 | Cenário 4, Spec §7 | negativo | uma rodada de outro fornecedor em `interesse` com o mínimo atingido; outra em `fechamento` com prazo futuro | `encerrar_fechamentos_vencidos()` | nenhuma das duas muda; devolve 0 |
| A-10 | Spec §15 | positivo | três fornecedores com fechamento vencido; o segundo faz `encerrar_fechamento` levantar `RuntimeError` por `monkeypatch` | `encerrar_fechamentos_vencidos()` | devolve 2; o primeiro e o terceiro ficam em `fechamento_encerrado`; o segundo continua em `fechamento`, sem nada gravado; o log tem o id da rodada e o tipo da exceção, sem e-mail nem nome; uma nova chamada sem a falha encerra o segundo |
| A-11 | E04-03 | positivo | — | inspeciono o registro de tarefas do Procrastinate | a tarefa `encerrar_fechamentos_vencidos` existe, é periódica a cada minuto e tem `queueing_lock` |
| A-12 | Spec da fatia | negativo | o estado do A-1; o envio do aviso levanta `RuntimeError` por `monkeypatch` | `encerrar_fechamento` em `T` | a exceção chega a quem chamou; etapa `fechamento`; B continua com 10; nenhuma auditoria |
| A-13 | E06-04 | positivo | em `T − 1 h`, o prazo é prorrogado para `T + 1 h` | `encerrar_fechamentos_vencidos()` em `T + 1 min`; depois em `T + 1 h` | a primeira não encerra (devolve 0); a segunda encerra |
| A-14 | Spec da fatia | concorrência | o estado do A-1, em `T` | duas chamadas de `encerrar_fechamento` em threads, a primeira segurando as travas | uma encerra e a outra devolve `None`; um único aviso para B; B com 4 |
| A-15 | E05-R03 | concorrência | o estado do A-1, em `T` | `encerrar_fechamento` trava o fornecedor e espera a barreira, enquanto `suspender(admin, B)` faz a pausa na substituta de `remover_interesses_do_comprador` (E05-07 A-15); depois da barreira, os dois seguem | os dois terminam sem exceção nem `OperationalError`; B fica `suspensa` e sem parcela `ativa`; nenhuma reserva de B no fim |
| A-16 | E03-03 | concorrência | o estado do A-1, em `T` | `editar_produto(admin, P, preco="11.00")` segura a trava do produto enquanto `encerrar_fechamento` espera | os dois terminam; o preço é 11,00; B com 4 |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-13 | `tests/tecnicos/test_rodadas_fechamento_encerramento.py` |
| A-1 | também marcado `acceptance`, com o comentário `cenário 7` |
| A-14 a A-16 | `tests/tecnicos/test_rodadas_fechamento_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
