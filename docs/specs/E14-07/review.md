# E14-07 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_retirada_comprador.py tests/tecnicos/test_portal_do_fornecedor.py` (arquivos inteiros, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | `test_retirada_comprador.py`: **7 failed, 6 passed**. Falham A-1 a A-6 e A-8 (as seções não existiam). Passam por ausência, como guardas de regressão: A-7 (antes da liberação sem seção de retirada, com a previsão), A-9 (nenhum formulário a mais), A-10 (404 de outro comprador), A-11 (403 do comprador nas rotas da E14-06, que já existiam) e A-12 (as rotas do comprador não criam registro). Os acréscimos do portal (A-13 e A-14, 2 testes) também **já passavam**: o portal não muda e as rotas da E14-06 já recusam o fornecedor |
| Green | `test_retirada_comprador.py`: **13 passed**; `test_portal_do_fornecedor.py`: **20 passed**; `test_pedidos_telas_comprador.py` verde; `mypy apps tests/apoio` e `ruff` limpos |

## O que foi feito
- `apps/pedidos/entrega_do_comprador.py` (`ocorrencias_do_pedido`, `retirada_do_pedido`), usados em `apps/pedidos/views.py` e em `templates/pedidos/detalhe.html`: seção "Ocorrências de entrega" (data, produto, tipo, quantidade, "Reembolso de R$ ..." e a situação: Devida, rótulo da parcela ou "Sem valor a devolver") e seção "Retirada" (liberação, prazo, endereço da liberação e a tabela Pedido/Reembolsado/Retirado/Descartado/A retirar, com o aviso de prazo encerrado quando há saldo). Sem formulário e sem o nome do administrador.
- A-13 e A-14 acrescentados a `tests/tecnicos/test_portal_do_fornecedor.py` (recusas do fornecedor nas rotas da E14 e conjunto de chaves do portal sem dado de recebimento, ocorrência, retirada, descarte ou endereço; nada disso no HTML nem no CSV).

## Decisões técnicas
- A linha da ocorrência traz data e hora de Brasília (a spec diz "data"); o teste confere os dois.
- "Reembolsado" na tabela de retirada soma o da apuração e o das ocorrências (spec, E14-07 regra 2).
