# E13-06 — Registro da implementação (agente 2, 2026-11-04)

Comandos: `uv run pytest tests/tecnicos/test_repasse.py` e `tests/tecnicos/test_repasse_telas.py` (arquivos inteiros, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red (serviços) | `c054e0e` | **17 failed**: `apps.pedidos.repasse` não existe e `liquidez()` recusa o frete (`ValueError`) |
| Green (serviços) | `2bdb7bb` | **17 passed** (A-17 com transações reais) |
| Red (tela) | `542fb3c` | **9 failed, 1 passed** (rotas e página inexistentes; o 404 sem apuração passa por ausência da rota) |
| Green (tela) | `90b348f` | **10 passed** |

## O que foi feito
- `registrar_repasse` e `registrar_pagamento_do_frete` em `apps/pedidos/repasse.py`; consulta antes do repasse, fora de transação; leitura do liberado sob a trava da conta, para a auditoria.
- **Liquidez do frete** em `apps/financeiro/liquidez.py`: `liquidez()` aceita o frete (as coberturas de déficit contam como liberadas) e `pagamento_do_frete` passa a limitar pelo liberado.
- Tela `administracao/rodadas/<pk>/saidas/` e as rotas de repasse e de frete (`exige_reautenticacao_por_passkey`).

## Teste anterior ajustado — para o revisor confirmar
- O A-25 da E09-R06 (`tests/tecnicos/test_financeiro_conciliacao.py::test_identificacao_de_64_caracteres_e_conciliavel`) semeava o frete por uma apuração simulada, sem pagamento liberado, e pagava 5,00 dele. Com a regra 8 da E13-06 (o frete só paga o liberado) esse pagamento passa a ser recusado (`LiquidezInsuficiente`). Só o **arranjo** mudou: o frete agora é semeado por uma cobertura de déficit da receita de serviço, que conta como liberada. As asserções (identificações de 64 caracteres conciliáveis, os dois alertas) não mudaram. Nenhum outro teste anterior mudou (os de E09 e cenários 31 e 40 seguem verdes).
