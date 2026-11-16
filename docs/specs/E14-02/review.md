# E14-02 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_ocorrencias.py tests/tecnicos/test_recebimento.py` (arquivos inteiros, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `6182e5e` | **33 failed** em `test_ocorrencias.py`: `registrar_ocorrencia`, `OcorrenciaRecusada` e `OcorrenciaDeEntrega` inexistentes (`ImportError`/`AttributeError` nos testes de corrida) |
| Green | commit "E14-02: Green ..." | **58 passed** (33 de ocorrências + 25 do recebimento, que passou a ler as somas reais) |
| Aceitação | commit seguinte | `tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py`: 4 passed. **Escrito depois do Green (Red tardio)**: repete os cenários pelo mesmo serviço; o Red dos mesmos comportamentos está no arquivo técnico. |

## O que foi feito
- `OcorrenciaDeEntrega` e `TipoDeOcorrencia` (só inserção, migração `0017` com `instalar_protecao_so_insercao`), `registrar_ocorrencia`, `saldo_do_item`, `somas_das_ocorrencias` (agora reais, no lugar do scaffolding da E14-01) e `OcorrenciaRecusada` em `apps/pedidos/ocorrencias.py`.
- Travas na ordem da spec: `Rodada` (`no_key`) → `SituacaoDoPedido` → contas (dentro de `reembolso_parcial`). Reembolso pela chave `ocorrencia:<uuid>` e motivo `ocorrencia_de_entrega`.
- `recebido_da_linha` passou para `ocorrencias.py` (evita importação circular); `recebimento.py` o importa (Refactor, testes da E14-01 verdes).

## Decisões técnicas
- **A-16 (item M):** o item de 0,6 kg é inserido no pedido X por `itens_do_pedido` (apoio da E10) e a rodada fica `disponivel_para_retirada` por `update`, porque o produto desse item não tem linha no pedido formal e as conferências de recebimento só existem em `aguardando_fornecedor` (regra 6). A cobertura da conferência de linha está em A-7 e A-8.
- **Item sem linha no pedido formal em `aguardando_fornecedor`:** recusado com `passa_do_pedido_formal` e "(0 ...)" (caso que a spec não descreve; um item de pedido válido sempre tem linha).
- **A-20:** o repasse total usa `liberacao_horas=0` no simulador (como a E14-08 prevê).
- **Auditoria:** quantidade e componentes como `Decimal` (JSON em texto); os testes comparam por valor.
