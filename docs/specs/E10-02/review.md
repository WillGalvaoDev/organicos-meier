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

## Revisão (agente 3)

| Achado | Classificação (bloqueador, importante, melhoria) | Evidência | Requisito |
|---|---|---|---|
| | | | |

**Decisão:** pendente

## Revalidação

—
