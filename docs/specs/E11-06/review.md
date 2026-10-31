# E11-06 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Comandos com o arquivo de teste inteiro, sem `-k`: `uv run pytest tests/tecnicos/test_apuracao_aprovacao.py`.

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-13 | `5a97b88` | **Red: 14 failed, 1 error.** `ImportError: cannot import name 'aprovar_resultado'` (a função não existia), `AprovacaoDoResultado` e `resultado_aprovado` inexistentes |
| `AprovacaoDoResultado` (migração `pedidos 0011` e proteção de só inserção), sinal `resultado_aprovado`, `aprovar_resultado` (nova consulta, conferências sob trava, pedidos válidos, apuração no livro, etapa, auditoria) | commit da fatia | **87 passed** (E11-01 a E11-06) |

## Decisões técnicas

- Travas da aprovação: fornecedor e rodada com `FOR NO KEY UPDATE` (como na E11-01); depois as contas, que `registrar_apuracao_no_livro` trava pela regra única da E09. Não trava contas de compradores nem situações: a aprovação não altera nenhum pedido.
- Ordem das conferências: etapa (`fora_de_pagamento`), apuração do ciclo (`sem_apuracao`), resultado (`resultado_nao_valido`), aprovação existente (`ja_aprovado`).
- Pedido válido: pago e com ao menos um item cujas unidades invalidadas são menos que a quantidade (`_pedidos_validos`).

## Riscos remanescentes e limites de verificação

- O receptor de `resultado_aprovado` é da E13; a spec fixa que uma exceção dele desfaz o avanço (testado com um receptor que falha).
