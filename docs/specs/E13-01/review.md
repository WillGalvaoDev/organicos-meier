# E13-01 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `75c589d` | **19 failed**: `ImportError: cannot import name 'PedidoFormal'` (nenhum `PedidoFormal`, como o critério A-1 prevê) |
| Green | `83d2ec9` | **19 passed**; regressão `test_apuracao_aprovacao.py`, `test_apuracao_telas.py` e `test_cancelamento_ponta_a_ponta.py`: 38 passed |

## O que foi feito
- Modelos `PedidoFormal`, `LinhaDoPedidoFormal`, `PrevisaoDeEntrega` (só inserção, com a trigger da E01-04) e `EnvioDoPedidoFormal` (migrações `0014` e `0015`); serviço `gerar_pedido_formal` em `apps/pedidos/pedido_formal.py` e o receptor de `resultado_aprovado` em `apps/pedidos/receptores.py`.
- O valor por linha reaproveita `_calcular_o_resultado` da apuração (E11-03), o mesmo desconto do estorno proporcional.

## Decisões técnicas e pontos para o especificador
- **Número no corpo.** O corpo cita "Pedido formal nº <pk>" e o registro não pode ser alterado depois de gravado; o `pk` é reservado com `nextval` da sequência antes da inserção.
- **Unidade no e-mail.** O critério A-6 escreve `11 unidade` e `1 kg`: o e-mail usa o valor gravado em `unidade` (`unidade`, `kg`, ...), e não o rótulo curto (`un`) de `quantidade_com_unidade`.
- **Recusas sem aprovação válida.** `gerar_pedido_formal(None)` e uma aprovação de resultado que não é `valida` levantam `ValueError`, sem escrita (A-12).
- **Teste de infraestrutura.** Os arquivos `test_pedido_formal*`, `test_previsao_de_entrega*`, `test_repasse*` e `test_portal_do_fornecedor*` entraram na lista de prefixos de `tests/conftest.py` que liga o banco do simulador (sem isso o fixture do simulador é recusado).
