# E13-08 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal_ponta_a_ponta.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-8 | `876f836` | **9 passed** |

## Sobre o Red
A fatia, pelo `spec.md`, não cria comportamento novo: exercita o que as E13-01 a E13-07 e as E09 a E12 entregaram. Não há Red de código de produção; os testes passaram na primeira execução completa (depois de dois ajustes do próprio teste, abaixo). Isso é registrado como Red tardio, e não como Red. Como evidência complementar, três mutações temporárias na produção (revertidas com `git checkout -- <arquivo>`; árvore limpa depois):

| Mutação | Resultado do arquivo |
|---|---|
| `_codigo_da_recusa` deixa de recusar o reenvio com o ciclo `em_andamento` (`reenvio_do_pedido_formal.py`) | 2 failed (A-2, A-3 cenário 118) |
| o repasse deixa de limitar pelo liberado (`liquidez.py`, `SAIDAS["repasse"]`) | 3 failed (A-5, A-6, A-7) |
| o receptor não gera o pedido formal (`receptores.py`) | 9 failed |

## Ajustes do próprio teste (nenhum afrouxa asserção de comportamento)
- Durante o ciclo automático e na rodada cancelada a página não traz o botão (e por isso o token): o POST do teste leva um UUID próprio.
- A-8 é conferido nos estados dos A-1, A-5 e A-6 por `_o_fornecedor_ve_so_o_permitido`, chamado ao fim de cada um (portal, CSV e as recusas da E13-07 A-12 e A-13).
- A-3 usa cookies copiados da sessão do administrador em cada thread (a sessão está no banco) e a pausa de `enviar_email` com `esperar_outra_conexao_na_trava()`.

## Verificação final da etapa (E13-01 a E13-08)

- `uv run pytest` (suíte inteira, sem `-k`): **3068 testes: 3066 passed e 2 failed na execução inteira; após o ajuste da lista de rotas, 3067 passed e 1 failed (M-10, preexistente)**.
- `uv run ruff check --no-cache .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run python manage.py makemigrations --check`: limpos (resultado no relatório de entrega).
- Resultado da suíte inteira: 2 falhas, ambas tratadas. (1) `test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete` listava as rotas com "pedido/frete" no nome: acrescentei à lista de permitidas as quatro rotas novas da E13 (`rodadas_pedido_formal`, `rodadas_pedido_formal_reenviar`, `fornecedor_pedido_formal_csv`, `rodadas_saidas_frete`), nenhuma altera o pedido congelado; o critério do teste (nenhuma rota altera pedido, item, T0 ou frete cobrado) não mudou. **Revisor: confirmar.** (2) `test_devolucoes_reembolso.py::test_o_reembolso_gera_a_obrigacao_financiada_pela_custodia` falha também isolada e sem relação com a E13: não congela o relógio e o prazo do pedido de `T0` terminou em 03/11/2026 (relógio real). Registrado como M-10 em `docs/melhorias.md`, sem alterar o teste.
- Sem push, PR nem merge: aguardam o parecer do agente 3. O PR à `main` atualizará o README (Parte 1) nas duas línguas e a milestone 13.
