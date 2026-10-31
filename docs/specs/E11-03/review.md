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


## Parecer independente — agente 3 — 2026-10-31

Base auditada: `1a36495`, branch `e11-implementacao`, comparada à base E10 integrada `1b9bf07`. Leitura dos documentos-base (funcional v1.7 e infraestrutura v1.8), spec/acceptance das oito fatias, implementação, testes e registros de TDD. O conteúdo anterior deste arquivo foi preservado integralmente. Evidências e reproduções completas no [parecer consolidado da E11-08](../E11-08/review.md).

**APROVADO no escopo próprio desta fatia.** A-1 a A-9 confrontados com código/testes: caixas congeladas invalidadas inteiras, nenhuma realocação, mínimo do ciclo, unidades pagas restantes, arredondamento proporcional ao subtotal, determinismo e auditoria. Modelo de apuração e caixas com proteção de só inserção; migrações incluídas na suíte. Nenhum novo achado próprio.

TDD: `ca861d2 → 91674c7`, evidências registradas conferidas. A classificação nominal passa, mas não sana os problemas de restauração e de cancelamento externo das outras fatias.
