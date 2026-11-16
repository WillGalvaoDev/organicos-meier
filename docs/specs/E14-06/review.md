`# E14-06 — Registro da implementação (agente 2, 2026-11-16)
`
`Comando: `uv run pytest tests/tecnicos/test_recebimento_e_retirada_telas.py tests/tecnicos/test_pedidos_abertura_tela.py` (arquivos inteiros, sem `-k`).
`
`| Etapa | Resultado |
`|---|---|
`| Red | **25 failed, 2 passed**. Passam por ausência as duas verificações que esperam 404: o POST de item de outra rodada (A-15) e a página de retiradas de rodada não liberada (A-20), com a rota ainda inexistente. As demais falham pelas rotas em 404 |
`| Green | **27 passed** nas telas; com `test_pedidos_abertura_tela.py` e `test_permissoes_politica_rotas.py` (A-24, sem mudar a lista de rotas permitidas), **59 passed**; `mypy apps config` e `ruff` limpos |
`
`## O que foi feito
`- `apps/pedidos/entrega_tela.py` (contextos e bloco da rodada) e `apps/pedidos/entrega_views.py` (as 8 rotas), templates `rodadas/recebimento.html`, `rodadas/ocorrencias.html` e `rodadas/retiradas.html`, bloco "Entrega e retirada" em `rodadas/estoque.html`, rotas em `config/urls.py`.
`- Convenções: `somente_administrador`; POST com CSRF e `acionamento` UUID novo a cada carregamento; 302 (novo e repetido), 400 (acionamento ou campos) e 409 (recusa do serviço) com o formulário preenchido; o item vem da rodada da rota (senão 404); toda escrita passa pelos serviços.
`- `motivo_da_recusa(rodada)` em `liberacao_da_retirada.py`: a mesma conferência da regra 4, sem levantar, para a tela mostrar o motivo e esconder o formulário.
`
`## Decisões técnicas
`- **POST de retirada ou descarte em rodada não liberada:** 404, como o GET da página (a spec só define o 404 do GET; o serviço também recusaria com `etapa`).
`- **Quantidade:** `Decimal` do texto com vírgula trocada por ponto; só o que não vira `Decimal` é "Preencha todos os campos."; valores como `1.0001` chegam ao serviço e voltam como 409 `quantidade_invalida`.
`- **Produto inexistente no recebimento:** 400 "Preencha todos os campos.".
`
`
`---
`
`## Revisão independente — agente 3 — 2026-11-16
`
`**Objeto:** `5b00c56`, branch `e14-especificacoes`, comparação com `bc35037` (main após E13). Fontes: especificação funcional v1.7, infraestrutura v1.8, AGENTS.md e as oito especificações e matrizes da E14. Histórico do implementador acima preservado.
`
`A execução independente e o parecer consolidado estão em [E14-08/review.md](../E14-08/review.md), incluindo o código das contraprovas. A revisão não alterou código de produção nem os testes do implementador.
`
`**Parecer da fatia: REPROVADO — E14-R01 (reflexo) e E14-R03 (importante).**
`
`| Critérios | Verificação |
`|---|---|
`| A-1 a A-10 | Recebimento, UUID por carregamento, replay sequencial, recusas, vírgula e liberação. |
`| A-11 a A-16 | Ocorrências, valores/cobertura, item de outra rodada e cancelada somente leitura. |
`| A-17 a A-21 | Retirada, descarte manual/prazo, acesso antes de liberar e bloco da rodada. |
`| A-22 a A-25 | Autorização, GET 405, allowlist anterior preservada e campos extras ignorados. |
`
`Os testes existentes dessa matriz passam na execução independente. Eles não verificam a preservação dos campos nas recusas de retirada/descarte nem o replay simultâneo dessas operações. E14-R01 está descrito na E14-05; a rota usa `resultado.novo` para selecionar a mensagem e herda a classificação incorreta.
`
`### E14-R03 — recusa perde ou substitui a quantidade enviada
`
`- **Requisito:** E14-06, convenção comum 3: recusa 409 com mensagem e **formulário preenchido**.
`- **Local:** `templates/rodadas/retiradas.html:34` e `:57`; `_pagina_das_retiradas` já fornece `valores`, porém o template não os usa.
`- **Reprodução:** AE-liberada, administrador autenticado por passkey, X-P1 com saldo 6, relógio no prazo final. POST de quantidade `7` para retirada ou descarte.
`- **Evidência:** ambas as rotas respondem corretamente 409; no formulário do item enviado, a retirada volta com quantidade vazia (`''`) e o descarte com `6`, em vez de `7`. `test_recusa_preserva_quantidade[False/True]` falha nessas asserções. No descarte, o formulário altera silenciosamente a quantidade que um reenvio usará.
`- **Correção esperada:** repopular somente o formulário/operação/item que originou a recusa, preservando o valor digitado e os valores padrão dos demais; testar negativa pelas duas rotas, sem relaxar a recusa de saldo.
`
`TDD: `3ee2653` antes de `f53999e`; as duas verificações que já passavam na ausência das rotas estão identificadas no registro do implementador. Não representam Red dos novos comportamentos. A allowlist de abertura de pedidos permaneceu intacta.
`
`
`---
`
`## Correção do implementador — reprovação de 2026-11-16
`
`**E14-R01 (A-26) e E14-R03 (A-27 a A-29).**
`- Red \`e69bedc\`: \`uv run pytest tests/tecnicos/test_recebimento_e_retirada_telas.py\` → 4 falhas: A-26 (as duas respostas com "Retirada registrada"); A-27 e A-29 com a quantidade do formulário vazia (`''` em vez de `7` e `6,5`); A-28 com `6` em vez de `7`.
`- Green: a rota passa o `digitado` (operação, item, texto exato) à página só na resposta 409 (`entrega_views.py`); `templates/rodadas/retiradas.html` repovoa só o formulário da operação e do item recusados; os demais ficam como num carregamento normal. A-26 passa com a correção da E14-05. Arquivo: 31 passed.
