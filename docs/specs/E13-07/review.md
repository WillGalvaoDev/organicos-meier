# E13-07 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_portal_do_fornecedor.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `0952f9f` | **13 failed, 5 passed** (rotas do portal inexistentes). Passam por ausência ou por políticas que já existiam: A-10, A-11, A-12, A-13 e A-16; ficam como regressão |
| Green | `9235d17` | **18 passed** |

## O que foi feito
- `apps/fornecedores/portal.py` (serializadores com lista fechada e CSV), `apps/fornecedores/portal_views.py` (`exige_fornecedor`, `Rodada.objects.filter(fornecedor=request.fornecedor_vinculado)`), três rotas (`fornecedor_painel`, `fornecedor_rodada`, `fornecedor_pedido_formal_csv`), dois templates e o link "Minhas rodadas" em `inicio/`.

## Ponto para o especificador
- **"0 faltando" no A-3.** Para P2 com 12 unidades em caixas de 6, o critério diz "2 caixas completas, 0 faltando". O `progresso_da_rodada` da E05 (que a regra cita como fonte) devolve `faltam_para_proxima_caixa = 6` nesse caso (a conta é `múltiplo − total % múltiplo`; o teste E05 `test_interesses_progresso.py:54` fixa esse valor). O portal segue o critério: mostra **0** quando as caixas estão fechadas e o valor da E05 nos demais casos. Se a intenção era mostrar 6, é uma linha em `_faltam` (`apps/fornecedores/portal.py`) e no teste.
- No A-15, o administrador chega à rota do fornecedor só com a passkey: com `force_login` (sem prova de passkey) o redirecionamento para cadastrar a passkey vem antes da política da rota. O teste entra por passkey, como nas demais telas.
