# E05-04 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As parcelas são criadas pelos serviços da E05-01 ou pela `ParcelaFactory`, conforme indicado. A rodada está em `interesse`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 6 | positivo | produto de R$ 10,00, múltiplo 12, com 18 reservados, de um único comprador | `progresso_da_rodada(rodada)` | `total_reservado` 18; `quantidade_elegivel` 12; `caixas_completas` 1; `faltam_para_proxima_caixa` 6; `excedente` 6; `valor_bruto` R$ 180,00; `valor_elegivel` R$ 120,00 |
| A-2 | Cenário 7, Spec §6.2 | positivo | o mesmo produto; pelos serviços, A adiciona 8 e depois B adiciona 10 | `progresso_da_rodada(rodada, A)` e `progresso_da_rodada(rodada, B)` | A: `reservado` 8, `em_caixas` 8, `excedente` 0; B: `reservado` 10, `em_caixas` 4, `excedente` 6; o agregado é igual ao do A-1 |
| A-3 | Cenário 8, Spec §6.3 | positivo | o estado do A-2; depois, A adiciona mais 2 | `progresso_da_rodada(rodada, A)` e `(rodada, B)` | o total é 20 e há 1 caixa; A tem 8 em caixas e 2 excedentes (a parcela nova vem depois das de B); B continua com 4 em caixas e 6 excedentes |
| A-4 | Cenário 104, R-6 | positivo | R$ 10,00 sem múltiplo, mínimo R$ 100,00; A com 8 reservados; C com uma parcela `pendente` de 5 | `progresso_da_rodada(rodada, C)` | `valor_elegivel` R$ 80,00; `percentual` 80; `atingido` falso; `falta` R$ 20,00; C com `reservado` 0 e `pendente` 5 |
| A-14 | Spec da fatia | limite | mínimo R$ 100,00 com valor elegível R$ 99,99, R$ 100,00 e R$ 250,00; noutra rodada, mínimo R$ 0,00 sem nenhuma reserva | `progresso_da_rodada(rodada)` | `percentual` 99, 100 e 100, com `atingido` falso, verdadeiro e verdadeiro; com mínimo zero, `percentual` 100 e `atingido` verdadeiro |
| A-15 | Spec da fatia | positivo | B sem parcela no produto | `progresso_da_rodada(rodada, B)` | `do_comprador` com `reservado`, `pendente`, `em_caixas`, `excedente` e `subtotal` iguais a zero |
| A-5 | Cenário 89, Spec §9 | positivo | R$ 2,50 por kg, incremento 0,25, sem múltiplo; A e B com 0,25 cada | `progresso_da_rodada(rodada)` | `valor_elegivel` R$ 1,26; `valor_bruto` R$ 1,25 |
| A-6 | Spec §6.1 | positivo | múltiplo 1 kg, incremento 0,25, total 2,75 kg; noutro produto, múltiplo 12 e total 0 | `progresso_da_rodada(rodada)` | primeiro: 2 caixas, elegível 2, excedente 0,75, faltam 0,25; segundo: 0 caixas, faltam 12, excedente 0 |
| A-7 | Spec §6.1 | positivo | dois produtos do mesmo fornecedor com múltiplo 12, com 7 reservados cada | `progresso_da_rodada(rodada)` | 0 caixas nos dois; `valor_elegivel` 0 (produtos não se misturam para completar caixa) |
| A-8 | Cenário 4, Spec §7 | positivo | mínimo R$ 50,00; A adiciona 6 de R$ 10,00 pelo serviço | leio o progresso e releio a rodada | `atingido` verdadeiro; a etapa continua `interesse`; nenhuma escrita durante a consulta (contagem de consultas sem `INSERT` nem `UPDATE`) |
| A-9 | Spec da fatia | positivo | parcelas `removida`, `em_pedido` e `ativa` do mesmo produto | `progresso_da_rodada(rodada)` | só a `ativa` entra no total |
| A-10 | Spec da fatia | negativo | 1 produto com 2 compradores; noutro caso, 8 produtos com 30 compradores | conto as consultas (`django_assert_max_num_queries`) | o mesmo teto nos dois casos |
| A-11 | Spec §6.2, Spec §2 | negativo | o estado do A-2 | inspeciono o resultado de `progresso_da_rodada(rodada, A)` | nenhum campo contém conta, id de parcela, nome ou e-mail de B; `do_comprador` só existe com o comprador informado |
| A-12 | Spec §13 | positivo | o estado do A-2, com mínimo R$ 200,00 | o administrador abre `/administracao/rodadas/<id>/estoque/` | "Progresso elegível: R$ 120,00 de R$ 200,00" e "Faltam R$ 80,00."; na linha do produto: total 18, elegível 12, R$ 180,00, R$ 120,00, 1 caixa, faltam 6, excedente 6; nenhum nome nem e-mail de A ou B; um produto sem múltiplo mostra "—" nas colunas de caixa |
| A-13 | Spec da fatia | positivo | o produto de R$ 10,00 com 12 reservados e mínimo R$ 100,00 | altero o preço para R$ 5,00 pelo serviço do catálogo e leio o progresso | `valor_elegivel` R$ 60,00; `atingido` falso |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-11, A-13 a A-15 | `tests/tecnicos/test_interesses_progresso.py` |
| A-1, A-2, A-4 e A-8 | também marcados `acceptance`, com os comentários `cenário 6`, `cenário 7`, `cenário 104` e `cenário 4` |
| A-12 | `tests/tecnicos/test_rodadas_estoque.py` |
