# E03-04 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As violações de restrição são testadas por SQL direto, ou pelo ORM quando o efeito no banco é o mesmo.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 4.10 | positivo | um comprador e um produto | crio três parcelas em sequência | três `sequencia` distintas e crescentes na ordem de criação; quantidades gravadas como `Decimal` com três casas |
| A-2 | Infra 4.10 | negativo | uma parcela | `UPDATE` direto de `sequencia`, `comprador_id`, `produto_id` e `quantidade_original`, um por vez | o banco recusa cada um (trigger) |
| A-3 | Infra 4.10 | negativo | uma parcela | `DELETE` direto | o banco recusa |
| A-4 | Infra 4.10 | negativo | o banco | insiro ou atualizo parcelas com: original 0; reservada -1; pendente -1; reservada 5 e pendente 4 com original 8; `removida` com reservada 1; `pendente` com reservada 1 | recusa em cada caso (`CHECK`) |
| A-5 | Cenário 75 | positivo | uma parcela original 8 | atualizo para reservada 4, pendente 4, `ativa`; depois reservada 0, pendente 8, `pendente`; depois 0 e 0, `removida` | as três atualizações aceitas |
| A-6 | Infra 4.10 | positivo | parcelas de um produto `X`: `ativa` com 6 reservadas; `em_pedido` com 2; `pendente` com 0 reservadas e 3 pendentes; `removida`; e uma `ativa` com 5 reservadas de outro produto `Y` | chamo `total_reservado(X)` | `Decimal("8.000")` |
| A-7 | Infra 4.10 | positivo | um produto sem parcelas | chamo `total_reservado` | `Decimal("0.000")` |
| A-8 | Infra 4.12, Q-6 | positivo | as parcelas do A-6, mais uma `ativa` com 4 reservadas e 4 pendentes | chamo `quantidades_em_uso(X)` | os valores 6, 2, 3, 4 e 4 (em qualquer ordem); nada da parcela removida nem do produto `Y` |
| A-9 | Infra 4.10 | concorrência | um produto | 20 inserções de parcelas em paralelo (`executar_em_paralelo`) | 20 sequências distintas |
| A-10 | Spec da fatia | negativo | uma criação de parcela pelo ORM com `sequencia=1` informada | executo | a sequência gravada vem da sequência do banco, ou a criação é recusada, conforme a escolha registrada pelo implementador; nunca fica gravado o valor informado |
| A-11 | Spec da fatia | positivo | a opção de travar escolhida pelo implementador | chamo `total_reservado` e `quantidades_em_uso` com trava dentro de `transaction.atomic()` e capturo as consultas | a consulta das parcelas usa `FOR UPDATE` e `ORDER BY` na sequência |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-5, A-10 | `tests/tecnicos/test_interesses_parcela_modelo.py` |
| A-6 a A-8, A-11 | `tests/tecnicos/test_interesses_consultas.py` |
| A-9 | `tests/tecnicos/test_interesses_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
