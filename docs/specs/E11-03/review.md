# E11-03 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Comandos com o arquivo de teste inteiro, sem `-k`: `uv run pytest tests/tecnicos/test_apuracao_resultado.py`.

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-9 (o arranjo com C e o P4 de 7,99/kg nos testes e no apoio) | `ca861d2` | **Red: 9 failed.** `ImportError: cannot import name 'CaixaInvalidada'`; `'ApuracaoFinal' object has no attribute 'valor_valido'`; `_calcular_o_resultado` inexistente; `KeyError: 'caixas'` na auditoria |
| `CaixaInvalidada`, `resultado`/`valor_valido`/`minimo` na `ApuracaoFinal` (migração `pedidos 0009`, com `preserve_default=False`, e proteção de só inserção); `_calcular_o_resultado` e a gravação depois do cálculo | commit da fatia | **41 passed** (E11-01 a E11-03) |

## Decisões técnicas

- O cálculo devolve também `unidades_invalidadas` e `descontos` por item pago, que a E11-04 usa para os estornos; o desconto de um item é o mesmo cálculo do `reembolso_parcial` da E10-02 (A-7 prova a igualdade por um reembolso gravado numa transação desfeita).
- O mínimo é `Ciclo.minimo`, o registrado no início do fechamento.
- A migração acrescenta as três colunas com padrão só para as linhas existentes (nenhuma fora dos testes), sem manter o padrão no modelo.
