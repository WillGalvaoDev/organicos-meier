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


---

## Revisão independente — agente 3 — 2026-11-16

**Objeto:** `5b00c56`, branch `e14-especificacoes`, comparação com `bc35037` (main após E13). Fontes: especificação funcional v1.7, infraestrutura v1.8, AGENTS.md e as oito especificações e matrizes da E14. Histórico do implementador acima preservado.

A execução independente e o parecer consolidado estão em [E14-08/review.md](../E14-08/review.md), incluindo o código das contraprovas. A revisão não alterou código de produção nem os testes do implementador.

**Parecer da fatia: APROVADO.**

| Critérios | Verificação |
|---|---|
| A-1 a A-4 | Reembolso proporcional pelos valores congelados, atomicidade e obrigação com cobertura por destinação. |
| A-5 a A-12 | Saldo já reembolsado, limites formal/recebido, depois da liberação, etapas, item, tipo e quantidade. |
| A-13 a A-19 | Permissão, repetição/mismatch, centavos/zero, auditoria, só inserção e autorização financeira separada. |
| A-20 a A-24 | Pós-repasse sem cobertura, concorrência do saldo e token, cancelamento concorrente e complemento de 70,76. |

Código confrontado: `ocorrencias.py`, modelo/migração 0017 e os serviços existentes de reembolso e reserva. Testes: `test_ocorrencias.py` e cenários 18/48/49/52; incluídos na suíte independente. Sem duplicação financeira ou alteração de pedido constatada.

TDD: `6182e5e` precede `e91142e`; as asserções técnicas existiam antes da produção. Os cenários de aceitação adicionados em `ac0c38e` são reforço posterior, não evidência de Red adicional. Registros de falha e Green conferidos, sem reexecução dos snapshots históricos.
