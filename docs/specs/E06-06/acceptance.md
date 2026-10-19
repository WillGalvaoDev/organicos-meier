# E06-06 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Nos critérios de concorrência, valem as regras de prevenção da correção E05-R04 (E05-01).

Salvo indicação:

- O fornecedor `F` ("Sítio Boa Terra") tem rodada com `P` ("Ovos", R$ 10,00, múltiplo 12, incremento 1, sem limite).
- As parcelas são criadas pelos serviços da E05-01 antes do início do fechamento.
- O fechamento é iniciado com o mínimo atingido às 2026-11-02 13:30 UTC, com prazo `T` = 2026-11-03 13:30 UTC.
- O mínimo do fornecedor é ajustado antes do início, porque depois ele fica congelado.
- O relógio é controlado com `time-machine`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 9, Spec §7 | positivo | mínimo R$ 100,00; A com 12 e B com 6 (bruto R$ 180,00, elegível R$ 120,00) | `encerrar_fechamento` em `T` | etapa final `fechamento_encerrado`; B com 0 e o aviso de excedentes; nenhum aviso `retorno_para_interesse`; auditoria `rodada.encerrar_fechamento` com `valor_elegivel` "120.00", `minimo` "100.00" e `resultado` `aguardando_pagamento` |
| A-2 | Cenário 9, Spec §6.3 | positivo | mínimo R$ 150,00; A com 15 e B com 1 (bruto R$ 160,00, elegível R$ 120,00); o mínimo foi atingido no início porque C tinha 8, e C reduziu para 0 durante o fechamento | `encerrar_fechamento` em `T` | etapa final `interesse`; A com 12; B com 0 (`removida`); A e B recebem um aviso `retorno_para_interesse` cada, com título "Rodada de volta ao interesse: Sítio Boa Terra", "não há estornos" no corpo, sem "150,00" nem "120,00", e chave `retorno_para_interesse:<ciclo>:<conta>`; C não recebe; auditorias `rodada.encerrar_fechamento` com `resultado` `retorno_para_interesse` e `rodada.voltar_para_interesse` com motivo `minimo_nao_atingido` |
| A-3 | Spec §5.1 | positivo | mínimo R$ 120,00; A com 12 (R$ 120,00) | `editar_produto(admin, P, preco="9.00")` em `T − 1 h`; em `T − 30 min`, leio a etapa; em `T`, `encerrar_fechamento` | em `T − 30 min`, a etapa ainda é `fechamento`; em `T`, a rodada volta para `interesse` |
| A-4 | Cenário 5 | positivo | mínimo R$ 100,00; A com 12 | em `T − 2 h`, A reduz para 0; em `T − 1 h`, B adiciona 12; em `T`, `encerrar_fechamento` | o prazo continua `T` o tempo todo; a etapa final é `fechamento_encerrado` |
| A-5 | Cenário 73, Spec §4.4 | positivo | o estado final do A-2 | `alterar_minimo(admin, F, "80,00")` e `alterar_estoque(admin, <estoque de P>, "30")` | aceitos; o ciclo do A-2 e as suas condições continuam com os valores originais (mínimo R$ 150,00) |
| A-6 | Spec §5.2 | positivo | mínimo R$ 120,00; limite de `P` 16; A com 15 e B com 1 (estoque cheio; elegível R$ 120,00 no início); D com uma parcela `pendente` de 3 (por fábrica); em `T − 1 h`, o preço passa a R$ 9,00 (elegível R$ 108,00) | `encerrar_fechamento` em `T` | saem 3 de A e 1 de B; a rodada volta para `interesse`; D fica com 3 reservados, na mesma transação, com uma auditoria `interesse.alocar_pendentes`; total reservado 15 ≤ 16 |
| A-7 | Spec da fatia | positivo | o estado final do A-2 | `iniciar_fechamento` de novo (com o mínimo ajustado para R$ 80,00 e A com 12) | aceito; ciclo número 2; uma linha de prazo nova; A recebe um novo `fechamento_iniciado` |
| A-8 | Spec da fatia | negativo | a rodada em `interesse`, em `fechamento` e em `pagamento` | `voltar_para_interesse(rodada, motivo="minimo_nao_atingido")` dentro de uma transação | `fora_de_fechamento_encerrado` nos três; nada gravado |
| A-9 | Spec da fatia | negativo | a rodada em `fechamento_encerrado` | `voltar_para_interesse` com `motivo="outro"`; e fora de transação | `ValueError`; `TransactionManagementError`; nada gravado |
| A-10 | E03-07 | positivo | os auxiliares trocados conforme a E06-01 e esta spec | rodo `tests/tecnicos/test_rodadas_ciclos.py` | verde; o diff de `tests/apoio/ciclos.py` nesta fatia mostra só a troca de `simular_volta_para_interesse` |
| A-11 | Spec da fatia | negativo | o estado do A-2; `emitir_evento_para_varios` levanta `RuntimeError` no aviso de retorno | `encerrar_fechamento` em `T` | a exceção chega a quem chamou; etapa `fechamento`; B continua com 1; nenhuma auditoria nem aviso de excedentes |
| A-12 | Spec da fatia | concorrência | o estado do A-2 | `encerrar_fechamento` segura as travas em `T`, enquanto `adicionar_interesse(D, P, "12")` espera a trava do fornecedor | depois do encerramento, a adição é aceita na rodada já em `interesse`; D tem 12; total reservado coerente |
| A-13 | E06-R04 | positivo e negativo | mínimo R$ 100,00; `P` a R$ 10,00 com limite 20; A com 10 reservados; fechamento iniciado; B com uma parcela `pendente` de 2 (por fábrica); a rodada posta em `fechamento_encerrado` por `update()` | numa transação, `voltar_para_interesse(rodada, motivo="minimo_nao_atingido")`; noutro caso igual, com `destinatarios=[A]` | nos dois, B fica com 2 reservados; os avisos `retorno_para_interesse` vão só para A, nos dois casos |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-9, A-11 | `tests/tecnicos/test_rodadas_fechamento_retorno.py` |
| A-1, A-2, A-4 e A-5 | também marcados `acceptance`, com os comentários `cenário 9 (suficiente)`, `cenário 9 (insuficiente)`, `cenário 5` e `cenário 73` |
| A-10 | `tests/tecnicos/test_rodadas_ciclos.py` (arquivo existente) |
| A-13 | `tests/tecnicos/test_rodadas_fechamento_retorno.py`; inclui literalmente a prova `test_destinatarios_do_retorno_antes_da_alocacao` do revisor de `2fbf143` |
| A-12 | `tests/tecnicos/test_rodadas_fechamento_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
