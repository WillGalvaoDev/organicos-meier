# E13-04 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal_telas.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `918e29e` | **17 failed, 1 passed** (404: página e rota inexistentes). O A-15 já passava: o 404 sem pedido formal vale também para a rota ainda inexistente; a prova do 404 da rota existente veio no Green |
| Green | `5521462` | **18 passed**; regressão `test_apuracao_telas.py` e `test_cancelamento_telas.py`: 29 passed |

## O que foi feito
- Página `administracao/rodadas/<pk>/pedido-formal/` (`rodadas_pedido_formal`), rota `.../reenviar/` (`rodadas_pedido_formal_reenviar`) e o bloco "Pedido formal" na página da rodada. Contexto em `apps/pedidos/pedido_formal_tela.py`; token novo (`uuid4`) a cada carregamento.
- Um token de outro pedido formal (`token_invalido` do serviço) responde 400 "Recarregue a página e tente de novo.", como o token ausente ou malformado.


## Revisão independente — agente 3 — 2026-11-13

Base auditada: `9af6251`, branch `e13-especificacoes`, sobre `9851bb5`. Requisitos lidos antes do código: especificação funcional v1.7, infraestrutura v1.8 e os `spec.md`/`acceptance.md` das oito fatias. Os registros do implementador acima foram preservados integralmente.

**Veredito do escopo próprio da fatia: APROVADO.** A integração do reenvio continua impedida pelo E13-R01 da E13-03; a E13 não está aprovada.

A-1 a A-17 conferidos contra views, contexto e template: acesso administrativo, 404/405, conteúdo gravado, histórico, estado do automático, token novo por carregamento, recusa/replay e respostas de falha do provedor. Campos extras não alteram assunto, corpo ou quantidades. CSRF permanece no formulário e no middleware. `test_pedido_formal_telas.py`: **18 testes passaram**.

O tratamento HTTP não corrige a corrida do serviço descrita em [E13-03](../E13-03/review.md); após a correção, revalidar também a rota.

TDD: `918e29e` introduz testes antes do Green `5521462`. O registro distingue corretamente o caso que já passava por 404 da rota inexistente (17 falhas/1 sucesso), seguido por 18 sucessos. Não foi encontrado outro achado próprio impeditivo. Evidências gerais em [E13-08](../E13-08/review.md).

## Revalidação da rota após o E13-R01 — implementador — 2026-11-13

O A-9 do E13-08 (dois POST com o mesmo token em pedidos formais diferentes) está em `tests/tecnicos/test_pedido_formal_ponta_a_ponta.py` e passa; `test_pedido_formal_telas.py` continua verde (68 testes dos quatro módulos do pedido formal). Detalhes em [E13-03](../E13-03/review.md).


## Revalidação independente das correções — agente 3 — 2026-11-13

Base auditada: `5055047`, branch `e13-especificacoes`, comparada com `7616ae8`. Histórico anterior preservado integralmente.

**APROVADO, inclusive a integração antes impedida por E13-R01.** Sem alteração de produção nesta fatia. Seus 18 testes passaram; o novo E13-08 A-9 confirmou o POST vencedor com redirecionamento, o segundo com 400 e apenas um e-mail/tentativa. R01 encerrado pelo serviço corrigido. Evidências em [E13-08](../E13-08/review.md).
