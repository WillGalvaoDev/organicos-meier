# E14-05 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_retirada.py tests/aceitacao/test_cenario_23_descarte.py` (arquivos inteiros, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | **31 failed**: `apps.pedidos.retirada`, `RetiradaDeItem` e `DescarteDeItem` inexistentes |
| Green | **31 passed**; com as E14-01, E14-02 e E14-04, **84 passed** (o saldo do item passou a descontar retirada e descarte e as ocorrências continuam verdes); `ruff` e `mypy apps/pedidos tests/apoio` limpos |

## O que foi feito
- `RetiradaDeItem` e `DescarteDeItem` (base abstrata `_RegistroDeItemDaRetirada`, só inserção, migração `0020` com as duas proteções), `registrar_retirada`, `registrar_descarte`, `situacao_da_retirada` e `RetiradaRecusada` em `apps/pedidos/retirada.py`.
- `saldo_do_item` (E14-02) estendido: quantidade − reembolsos (todos os motivos) − retirado − descartado.
- Travas: rodada (`no_key`) e situação do pedido, na ordem da ocorrência. O descarte é aceito a partir de `prazo_final` (inclusive); a retirada depois do prazo continua aceita; nada depende da situação do comprador; nenhum efeito financeiro.
- `vencidos` é calculado na leitura (`agora >= prazo_final` e saldo > 0); nenhum registro nasce da passagem do tempo.

## Decisões técnicas
- `situacao_da_retirada` levanta `LookupError` para rodada não liberada (as telas devolvem 404 antes de chamá-la).
- A-9 (item de pedido não válido): usa o AF-parcial liberado (Y não pagou), pois um item de rodada não liberada recebe `etapa`, que vem antes.
- O arquivo de aceitação do cenário 23 foi escrito no mesmo ciclo do Red (falhava pelo mesmo motivo).
