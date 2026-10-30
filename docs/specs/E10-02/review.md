# E10-02 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Andaime (modelos `Reembolso` e `ItemReembolsado`, migração 0011 com a trava só-inserção, assinaturas que levantam `NotImplementedError`) e testes A-1 a A-14 e A-17 | `2c8329c` | `uv run pytest tests/tecnicos/test_devolucoes_reembolso.py tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py` | **Red: 25 failed** (`NotImplementedError`) |
| Green funcional, **sem** a trava do pedido | `Green, sem a trava` | os mesmos arquivos | 25 passed |
| Corridas A-15 e A-16 (`tests/tecnicos/test_devolucoes_concorrencia.py`) | `80c4a9b` | o arquivo da corrida, sem a trava | **Red: 3 failed** (`1.250 <= 1.000`; segundo `ReembolsoRecusado` não levantado; acumulado do pedido `125,00` em vez de `100,00`) |
| Trava do pedido (`select_for_update` na `SituacaoDoPedido`, antes de ler qualquer acumulado) | `Green das corridas` | os três arquivos | **28 passed** |

O Red das fatias usa um andaime com `NotImplementedError`: o comportamento não existe, então o teste falha pela ausência dele, e não por uma asserção sobre um valor errado. O andaime (modelos, migração e assinaturas) é scaffolding sem comportamento testável.

| Critério | Teste |
|---|---|
| A-1 a A-14, A-17 | `tests/tecnicos/test_devolucoes_reembolso.py` |
| A-15 e A-16 | `tests/tecnicos/test_devolucoes_concorrencia.py` (`Corrida`: A pausa depois de ler o acumulado e B começa nesse ponto) |
| Cenários 90, 91, 112 a 117 | `tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py` |

## Decisões técnicas (derivadas, sem escalar)

- Os registros ficam em `apps/financeiro` (`models.py`, `reembolsos.py`), ao lado da obrigação que cada reembolso gera; as rotas da E10-07 estão sob o menu financeiro.
- A integral recalcula o restante: na repetição com a mesma chave só o pedido e o motivo são conferidos (as linhas restantes já foram consumidas). O parcial confere também o item e a quantidade.
- `autor` vazio no `Reembolso` é o `SISTEMA`.
- `tests/conftest.py`: os prefixos `test_devolucoes_`, `test_cenarios_`, `test_simulador_estornos`, `test_t08_` e `test_t09_` passaram a usar os dois bancos do simulador (a lista é por prefixo de arquivo).

## Verificações executadas

Ver o registro final da E10 em `docs/specs/E10-07/review.md`.

## Revisão independente — agente 3 — 2026-10-30

Objeto: branch `e10-implementacao`, commit `9ce04adcdb1b6186ee5c932ef38170989e4d19cf`, comparado à especificação de `cd735c3`. Fontes: funcional v1.7, infraestrutura v1.8, `spec.md` e `acceptance.md` das sete fatias, AGENTS.md. Os registros do implementador acima foram preservados.

A suíte existente passou integralmente (**2600 passed in 270.31s**, execução independente iniciada em 2026-10-29). Isso não encerra os requisitos: os testes adicionais do revisor expõem os casos abaixo. Comandos, limitações, histórico TDD e reproduções estão no [parecer consolidado](../E10-07/review.md).

**Decisão da fatia: REPROVADO.**

| Critérios | Evidência | Resultado |
|---|---|---|
| A-1 a A-10, A-12 a A-14 e A-17 | `test_devolucoes_reembolso.py` e cenários 90/91/112–117: snapshots, centavos, quantidade, imutabilidade e obrigação | Cenários existentes verdes |
| A-11 e regra de idempotência | Mesmo conteúdo parcial passa; colisão entre parcial e integral não é recusada | R01 aberto |
| A-15 e A-16 | `test_devolucoes_concorrencia.py`; trava da situação do pedido antes dos acumulados | Corridas existentes verdes; A-16 força parcial primeiro, não demonstra literalmente as duas ordens |

### R01 — importante — integral aceita chave de um parcial com conteúdo diferente

Referências: E10-02/spec.md, “Idempotência pela chave”; funcional §9.2; `apps/financeiro/reembolsos.py:94` e `:215`.

Reprodução: pedido K, parcial de 0,25 com chave `mesma-chave` e motivo `cancelamento_da_rodada`; chamar a integral com a mesma chave e motivo. Esperado: `ReembolsoConflitante`. Observado: devolve o parcial, sem erro e sem completar o restante. `_existente(..., linhas=None)` dispensa a comparação das linhas para toda integral, inclusive quando a chave pertence a outra solicitação. Preservar a repetição legítima da integral sem aceitar silenciosamente um pedido diferente.

Histórico: `2c8329c → ae25659` (funcional) e `80c4a9b → dd57ba6` (corridas) dão rastreabilidade ao Red/Green registrado. A frase de A-16 que exige duas obrigações “em qualquer ordem” precisa ser compatibilizada tecnicamente com A-4/A-8 e a recusa de quantidade excedente: se a integral ganhar, o parcial subsequente não pode criar nova devolução. Não autoriza alterar o limite financeiro.
