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


## Parecer independente — agente 3 — 2026-10-31

Base auditada: `1a36495`, branch `e11-implementacao`, comparada à base E10 integrada `1b9bf07`. Leitura dos documentos-base (funcional v1.7 e infraestrutura v1.8), spec/acceptance das oito fatias, implementação, testes e registros de TDD. O conteúdo anterior deste arquivo foi preservado integralmente. Evidências e reproduções completas no [parecer consolidado da E11-08](../E11-08/review.md).

**APROVADO no escopo próprio revalidado; sem liberar o avanço da etapa com os achados abertos.** A-1 a A-13 confrontados com código/testes: nova consulta, bloqueio por falha, autorização, exclusão de pedidos inteiramente invalidados, lançamentos de custódia/fornecedor/serviço/frete, déficit sem cobrar mais do pagante, unicidade da aprovação, auditoria e rollback quando o receptor do sinal falha. Não encontrado achado próprio nesse fluxo.

TDD: `5a97b88 → d54cdf7`, registros conferidos. Pedido formal e repasse continuam na E13. Os problemas do início/retorno não são resolvidos por aprovar o resultado.


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `0af24ad`, branch `e11-implementacao`; correções desde o parecer `3aa8858` sobre `1a36495`. Requisitos corrigidos em `732b7bb`, código, testes e registros Red/Green confrontados. Conteúdo anterior preservado. Evidências e prova residual no [parecer consolidado E11-08](../E11-08/review.md).

**APROVADO nesta revalidação, sem achado próprio.** Sem alteração de implementação específica nesta rodada; aprovação administrativa e regressões incluídas na suíte completa. A etapa E11 permanece REPROVADA por R02 residual.
