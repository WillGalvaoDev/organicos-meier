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


## Revisão independente — agente 3 — 2026-11-13

Base auditada: `9af6251`, branch `e13-especificacoes`, sobre `9851bb5`. Requisitos lidos antes do código: especificação funcional v1.7, infraestrutura v1.8 e os `spec.md`/`acceptance.md` das oito fatias. Os registros do implementador acima foram preservados integralmente.

**Veredito da fatia: APROVADO.** A etapa E13 permanece REPROVADA por E13-R01/E13-R02.

| Critérios | Conferência |
|---|---|
| A-1 a A-6 | Consulta obrigatória antes do repasse, isolamento por fornecedor/rodada e limite ao liberado, inclusive quando outro fornecedor tem saldo. |
| A-7 a A-11 e A-17 | Obrigação existente, repetição, autorização, contrato fora de transação, cancelamento com/sem reembolso e concorrência real do limite financeiro. |
| A-12 a A-16 | Liquidez do frete: entradas liberadas e coberturas de déficit, menos todas as saídas; sem consulta adicional não prevista. |
| A-18 a A-22 | Relatórios, históricos, passkey recente, validações, respostas e links. |

`test_repasse.py` e `test_repasse_telas.py`: **27 testes passaram**. A consulta antecede a transação; leitura do limite e lançamento ficam sob a trava da conta. A baixa usa apenas a conta da destinação. O cenário ponta a ponta também exercita conciliação e cancelamento após repasse.

Confirmado o ajuste autorizado do arranjo do E09-07 A-25: a cobertura de frete substitui a apuração simulada sem liquidez; as asserções de identificação de 64 caracteres e conciliação foram preservadas. Não houve afrouxamento desse critério.

TDD: `c054e0e` → `2bdb7bb` (serviços, 17 testes) e `542fb3c` → `90b348f` (tela, 10 testes), com mudanças e registros conferidos. Sem achado próprio impeditivo. Evidências gerais em [E13-08](../E13-08/review.md).


## Revalidação independente das correções — agente 3 — 2026-11-13

Base auditada: `5055047`, branch `e13-especificacoes`, comparada com `7616ae8`. Histórico anterior preservado integralmente.

**APROVADO — mantida a aprovação.** Sem alteração de produção nesta fatia. Seus 27 testes passaram na matriz completa, incluindo consulta, liquidez, concorrência, segregação e telas. Consolidação em [E13-08](../E13-08/review.md).
