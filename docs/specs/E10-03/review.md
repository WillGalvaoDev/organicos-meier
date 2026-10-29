# E10-03 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Andaime (tipos da interface, `EstornoSimulado`, `MovimentoSimulado.id_estorno`, migração 0003, `NotImplementedError` no simulador) e testes A-1 a A-20 | `ceb68d7` | `uv run pytest tests/tecnicos/test_simulador_estornos.py` | **Red: 22 failed, 5 passed.** Os 5 são o A-17 parametrizado: a validação do `NovoEstorno` faz parte do andaime da interface e já recusa os valores e as chaves inválidas (regressão, sem Red próprio) |
| Estorno, consulta e controles no simulador | `c06d379` | o mesmo arquivo | **27 passed** |

A-18 (duas chamadas com a mesma chave em paralelo) está no mesmo arquivo, com `django_db(transaction=True)`; o `estornar` trava a cobrança antes de ler o restante, então o segundo pedido vê o primeiro e devolve o mesmo `id_estorno`.

## Decisões técnicas

- A conta do simulador não guarda a tarifa devolvida (L-7 aberta): o estorno debita só o valor estornado.
- A conclusão (`concluir_estorno`) usa `estado.concluir`, o mesmo caminho do estorno imediato, para que o movimento `devolucao` seja um só.
- A referência `docs/referencias/mercado-pago-api.md` (seção 10) foi atualizada nas duas linhas indicadas pela especificação.
- `tests/conftest.py`: prefixo `test_simulador_estornos` entra na lista dos testes com o banco do simulador.

## Revisão (agente 3)

| Achado | Classificação (bloqueador, importante, melhoria) | Evidência | Requisito |
|---|---|---|---|
| | | | |

**Decisão:** pendente

## Revalidação

—
