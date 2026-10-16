# E03-07 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As transições usam os auxiliares `simular_inicio_do_fechamento` e `simular_volta_para_interesse` de `tests/apoio`, até a E06 existir.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §4.4, Infra 4.10 | positivo | rodada em `interesse`, mínimo 150, produto `P` com incremento 0,5 e múltiplo 3, estoque 10; produto `Q` sem múltiplo e sem limite; produto `R` do fornecedor fora da rodada | `simular_inicio_do_fechamento` | um `Ciclo` número 1 com mínimo `150.00`; condições de `P` (0,5; 3; 10) e de `Q` (incremento; nulo; nulo); nenhuma de `R`; auditoria `ciclo.registrar_condicoes`; etapa `fechamento` |
| A-2 | Cenário 73 | positivo | o estado do A-1 | volta para interesse; alteração do mínimo para 200, do múltiplo de `P` para 6 e do estoque de `P` para 20; inclusão de `R` com limite 5; novo início de fechamento | o ciclo 1 continua com 150, 3 e 10 e sem `R`; o ciclo 2 tem 200, 6, 20 e `R` com 5 |
| A-3 | Cenário 73 | positivo | o estado do A-1, depois da volta para interesse | altero mínimo, múltiplo, incremento e estoque | todas as alterações aceitas (as condições voltam a ser editáveis) |
| A-4 | Infra 5 | negativo | um ciclo e suas condições | `UPDATE` e `DELETE` pelo ORM e por SQL direto | `RegistroImutavel` no ORM; o banco recusa por SQL |
| A-5 | Spec da fatia | negativo | rodada em `fechamento` | chamo `registrar_condicoes_do_ciclo` | `CondicoesCongeladas`; nenhum ciclo novo |
| A-6 | Spec da fatia | negativo | uma chamada fora de `transaction.atomic()` | executo | `TransactionManagementError` |
| A-7 | Spec da fatia | positivo | uma rodada sem ciclos e outra com os ciclos 1 e 2 | chamo `ciclo_vigente` | `None` e o ciclo 2 |
| A-8 | Spec da fatia | negativo | o banco | insiro por SQL direto um segundo ciclo número 1 para a mesma rodada | o banco recusa (`UNIQUE`) |
| A-9 | T-23, cenário 72 | negativo | a matriz da spec: cada condição (mínimo, múltiplo, incremento, inclusão e alteração de estoque) × cada situação (`fechamento`, `fechamento_encerrado`, `pagamento`, `aguardando_fornecedor`, sem rodada ativa depois de `disponivel_para_retirada` e depois de `cancelada`) | chamo a rota (com e sem `HX-Request: true`) e o serviço, com o administrador | 409 e `CondicoesCongeladas` em todos; nenhum valor alterado; nenhuma auditoria |
| A-10 | T-23, cenário 72, §5.1 | positivo | cada uma das quatro etapas ativas fora de `interesse` | altero o preço | aceito em todas |
| A-11 | Spec da fatia | concorrência | rodada em `interesse` e mínimo 150 | `simular_inicio_do_fechamento` trava primeiro e confirma ao ver `alterar_minimo(200)` esperando por trava (`pg_stat_activity`) | o ciclo registra 150; `alterar_minimo` recusado; mínimo 150 |
| A-12 | E03-R03, T-23, cenário 72 | negativo | a matriz da spec (cinco condições × seis situações congeladas) estendida pelas cinco classes de valor da correção E03-R03 | `POST` em cada rota, com e sem `HX-Request: true` | 409 em todos, com "As condições da rodada só podem ser alteradas na fase de interesse."; a resposta não tem o campo do valor (`name="minimo"`, `name="multiplo"`, `name="incremento"` ou `name="limite"`); nenhum valor alterado; nenhuma auditoria; nenhum `estoque_alterado` |
| A-13 | E03-R03 | negativo | a mesma matriz | chamo cada serviço com os valores mal formado, de sinal e de capacidade | `CondicoesCongeladas` em todos; nunca `ValidationError`, `IncrementoInvalido` nem `MultiploInvalido` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-8 | `tests/tecnicos/test_rodadas_ciclos.py` |
| A-9, A-10 | `tests/tecnicos/test_condicoes_congeladas_matriz.py` (marcador `tecnico`, com o comentário `T-23`) |
| A-11 | `tests/tecnicos/test_rodadas_ciclos_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
| A-2, A-3 (cenário 73); A-9, A-10 (cenário 72) | também marcados `acceptance`, com os números no comentário |
| A-12, A-13 | `tests/tecnicos/test_condicoes_congeladas_matriz.py` (marcador `tecnico`, com o comentário `T-23`) |
