# E14-06 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_recebimento_e_retirada_telas.py tests/tecnicos/test_pedidos_abertura_tela.py` (arquivos inteiros, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | **25 failed, 2 passed**. Passam por ausência as duas verificações que esperam 404: o POST de item de outra rodada (A-15) e a página de retiradas de rodada não liberada (A-20), com a rota ainda inexistente. As demais falham pelas rotas em 404 |
| Green | **27 passed** nas telas; com `test_pedidos_abertura_tela.py` e `test_permissoes_politica_rotas.py` (A-24, sem mudar a lista de rotas permitidas), **59 passed**; `mypy apps config` e `ruff` limpos |

## O que foi feito
- `apps/pedidos/entrega_tela.py` (contextos e bloco da rodada) e `apps/pedidos/entrega_views.py` (as 8 rotas), templates `rodadas/recebimento.html`, `rodadas/ocorrencias.html` e `rodadas/retiradas.html`, bloco "Entrega e retirada" em `rodadas/estoque.html`, rotas em `config/urls.py`.
- Convenções: `somente_administrador`; POST com CSRF e `acionamento` UUID novo a cada carregamento; 302 (novo e repetido), 400 (acionamento ou campos) e 409 (recusa do serviço) com o formulário preenchido; o item vem da rodada da rota (senão 404); toda escrita passa pelos serviços.
- `motivo_da_recusa(rodada)` em `liberacao_da_retirada.py`: a mesma conferência da regra 4, sem levantar, para a tela mostrar o motivo e esconder o formulário.

## Decisões técnicas
- **POST de retirada ou descarte em rodada não liberada:** 404, como o GET da página (a spec só define o 404 do GET; o serviço também recusaria com `etapa`).
- **Quantidade:** `Decimal` do texto com vírgula trocada por ponto; só o que não vira `Decimal` é "Preencha todos os campos."; valores como `1.0001` chegam ao serviço e voltam como 409 `quantidade_invalida`.
- **Produto inexistente no recebimento:** 400 "Preencha todos os campos.".
