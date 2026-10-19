# E06-01 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Nos critérios de concorrência, valem as regras de prevenção da correção E05-R04 (E05-01):

1. o teste é escrito e falha antes da trava ou da conferência que ele exige;
2. toda espera de sincronização tem prazo e termina em falha de asserção.

Salvo indicação, o fornecedor `F` tem mínimo R$ 100,00 e rodada em `interesse`, com o produto `P` (unidade, incremento 1, R$ 10,00, limite 20). O relógio é controlado com `time-machine`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 5, Spec §7 | positivo | A com 10 reservados (R$ 100,00); o relógio em 2026-11-02 13:30 UTC | `iniciar_fechamento(admin, rodada)` | etapa `fechamento`; um ciclo novo com as condições vigentes (E03-07); uma linha de `PrazoDoFechamento` `inicio` com `termina_em` 2026-11-03 13:30 UTC, igual a `ciclo.iniciado_em` + 24 h; `prazo_do_fechamento(rodada)` devolve esse instante; uma auditoria `rodada.iniciar_fechamento` com rodada, ciclo, `termina_em`, `valor_elegivel` "100.00" e `minimo` "100.00" |
| A-2 | Cenário 104, R-6 | negativo | A com 8 reservados; C com uma parcela `pendente` de 5 | `iniciar_fechamento(admin, rodada)` | `TransicaoRecusada` com `minimo_nao_atingido` e a mensagem da spec; etapa `interesse`; nenhum ciclo, prazo ou auditoria novos |
| A-3 | Spec §6.1 | negativo e positivo | `P` com múltiplo 12; A com 11 reservados (R$ 110,00 bruto, R$ 0,00 elegível); depois, B adiciona 1 | `iniciar_fechamento` antes e depois da adição de B | antes: recusa `minimo_nao_atingido`; depois: aceito (12 em caixa, R$ 120,00) |
| A-4 | Cenário 4 | negativo | A com 20 reservados (valor elegível acima do mínimo) | o relógio avança 30 dias; chamo `processar_envios()` (E04-03) e `alocar_pendentes(F)` (E05-02) dentro de uma transação | etapa `interesse`; nenhum ciclo nem prazo; nada inicia o fechamento sozinho. A E06-05 repete a verificação com a tarefa de encerramento (A-9 de lá) |
| A-5 | Spec da fatia | negativo | um comprador, uma conta de fornecedor e um anônimo (`None`) | `iniciar_fechamento` | `PermissionDenied` em todos; nada gravado |
| A-6 | E03-07 | negativo | (a) a rodada já em `fechamento` pelo serviço; (b) a rodada em `pagamento` por `update()`; (c) uma rodada `disponivel_para_retirada` do fornecedor, sem rodada ativa | `iniciar_fechamento(admin, rodada)` | `fora_de_interesse` em (a) e (b), com um único ciclo em (a); `sem_rodada_ativa` em (c); nada gravado |
| A-7 | Spec da fatia | limite | mínimo R$ 0,00 e nenhuma reserva; noutro caso, mínimo R$ 100,00 e valor elegível R$ 100,00 exato | `iniciar_fechamento` | aceito nos dois |
| A-8 | Spec §15 | limite | o relógio em 2026-11-02 02:30 UTC (23:30 de 01/11 em São Paulo) | `iniciar_fechamento` | `termina_em` 2026-11-03 02:30 UTC |
| A-9 | Cenários 72 e 107, T-23 | negativo | rodada em `fechamento` pelo serviço | `alterar_minimo`, `alterar_estoque`, `alterar_multiplo` e `alterar_incremento`; depois `editar_produto` com preço novo | as quatro primeiras recusadas com `CondicoesCongeladas`; o preço é aceito |
| A-10 | Spec da fatia | negativo | uma linha de `PrazoDoFechamento` gravada | `save()` de novo, `update()` e `delete()` pelo ORM e por SQL direto; uma segunda linha `inicio` para o mesmo ciclo | `RegistroImutavel` ou `IntegrityError` em todos; a linha não muda |
| A-11 | E03-07 | positivo | os auxiliares trocados conforme a spec | rodo `tests/tecnicos/test_rodadas_ciclos.py` | verde; o diff desse arquivo e de `tests/apoio/ciclos.py` mostra só os dois ajustes autorizados |
| A-12 | Spec da fatia, Infra 5 | concorrência | A com 10 reservados | (a) `reduzir_interesse(A, P, "1")` segura as travas enquanto `iniciar_fechamento` espera; (b) `iniciar_fechamento` segura as travas enquanto a redução espera | (a) o início é recusado com `minimo_nao_atingido`, e a rodada continua em `interesse`; (b) o início confirma, e a redução é aceita no fechamento, com o prazo inalterado; sem deadlock |
| A-13 | E03-02, T-23 | concorrência | A com 10 reservados | `iniciar_fechamento` segura as travas enquanto `alterar_minimo(admin, F, "50,00")` espera | o início confirma; a alteração do mínimo é recusada com `CondicoesCongeladas`; o ciclo registra R$ 100,00 |
| A-14 | Spec da fatia | concorrência | A com 10 reservados | duas chamadas de `iniciar_fechamento` em threads | uma confirma e a outra recebe `fora_de_interesse`; um único ciclo e uma única linha `inicio` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-10 | `tests/tecnicos/test_rodadas_fechamento_inicio.py` |
| A-1, A-2 e A-4 | também marcados `acceptance`, com os comentários `cenário 5`, `cenário 104` e `cenário 4` |
| A-11 | `tests/tecnicos/test_rodadas_ciclos.py` (arquivo existente, com os ajustes autorizados) |
| A-12 a A-14 | `tests/tecnicos/test_rodadas_fechamento_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
