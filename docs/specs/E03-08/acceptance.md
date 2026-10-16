# E03-08 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Os dados são criados pelas fábricas da E03.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §13 | positivo | fornecedor `F` com rodada em `interesse` e o produto "Banana" (kg, incremento 0,25, R$ 7,99, sem múltiplo, limite 10, 6 reservados) | um comprador ativo abre `/catalogo/F/` | 200 com "Banana", "R$ 7,99 / kg", o incremento "0,25 kg" e "4 kg disponível" |
| A-2 | Spec §4.2, §13 | positivo | o produto "Maçã" (unidade, incremento 2, múltiplo 12, sem limite) em `F` | abro a página | múltiplo "12" e "Sem limite" |
| A-3 | Spec da fatia | positivo | produtos com estoque 0 e com limite 10 e 10 reservados | abro a página | "Esgotado" nos dois |
| A-4 | Spec da fatia, D-1 | positivo e negativo | produtos de `F`: um fora da rodada, um indisponível na rodada e um disponível na rodada | abro a página | o de fora não aparece; o indisponível aparece com "Produto indisponível" junto à descrição; o disponível aparece sem a marcação |
| A-5 | Spec §4.3 | positivo | fornecedores `"Zeta"` (rodada em `fechamento`, um produto disponível), `"Alfa"` (rodada em `interesse`), `"Sem"` (sem rodada ativa), `"Vazio"` (rodada sem produto incluído) e `"Marcado"` (rodada com um único produto, indisponível) | abro `/catalogo/` | `Alfa`, `Marcado` e `Zeta`, nessa ordem, com as etapas; `Sem` e `Vazio` ausentes |
| A-6 | Spec da fatia | negativo | o fornecedor `Sem` e um id inexistente | abro `/catalogo/<id>/` | 404 nos dois, com o mesmo corpo |
| A-7 | Spec §2 | positivo | um comprador suspenso | abro `/catalogo/` e `/catalogo/F/` | 200 nos dois |
| A-8 | Spec §2, §15 | negativo | uma conta de fornecedor, o administrador (com passkey) e um visitante anônimo | abro as duas rotas | 403, 403 e redirecionamento para `/entrar/` |
| A-9 | Spec §2, §6.2 | negativo | `F` com e-mail de pedido, mínimo, prazo, frete e uma conta vinculada; parcelas de dois compradores | abro a página como comprador | a resposta não contém o e-mail do pedido, o mínimo, o prazo, o texto do frete, o nome ou o e-mail da conta vinculada, nem nomes ou e-mails dos compradores |
| A-10 | Spec da fatia | positivo | `F` com 1 produto e, noutro teste, com 20 | conto as consultas da página (`django_assert_max_num_queries`) | o mesmo teto nos dois casos |
| A-11 | Spec da fatia | positivo | um fornecedor com rodada ativa sem produto incluído | abro a página dele | 200 com "Nenhum produto nesta rodada." |
| A-12 | E02-10 | positivo | as rotas desta fatia | rodo a varredura de políticas | política `comprador` declarada nas duas |
| A-13 | D-1 | positivo | um produto indisponível no catálogo | o administrador o marca como disponível e abro a página de novo | a marcação "Produto indisponível" não aparece mais |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-6, A-9 a A-11, A-13 | `tests/tecnicos/test_catalogo_comprador.py` |
| A-7, A-8 | `tests/tecnicos/test_catalogo_permissoes.py` |
| A-12 | coberto pelo teste existente `tests/tecnicos/test_permissoes_politica_rotas.py` |
