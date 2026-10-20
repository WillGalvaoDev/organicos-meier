# E08-07 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05): Red com caminhos explícitos de arquivos inteiros, sem `-k`, e tabela de cobertura do Red antes do Green. Os testes declaram os dois bancos (E07-R03).

**Arranjo comum, salvo indicação:**

- relógio em 2026-11-02 14:00 UTC;
- fixture `simulador_pagamentos` ativa;
- uma cobrança `P` pendente, criada pela tentativa de um pedido (E08-03);
- uma cobrança `Q` já `aprovado`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Herdado da E07 | positivo | — | o administrador abre `/administracao/simulador-pagamentos/` | 200; "Simulador de pagamentos" e "Ambiente de teste. Nenhum dinheiro real é movimentado."; `P` e `Q` com `id_externo`, referência, valor, situação e instantes em horário de Brasília; `P` com "Aprovar", "Recusar" e "Expirar"; `Q` sem botões; "Entregar avisos pendentes (1)", por causa do aviso da aprovação de `Q` |
| A-2 | Herdado da E07 | positivo | — | `POST …/<P>/aprovar/`; depois `POST …/avisos/entregar/`; depois `processar_chamadas()` | redireciona com "Cobrança <P> aprovada."; a entrega redireciona com "2 aviso(s) entregue(s)."; o pedido de `P` fica `pago` (E08-04); auditorias `simulador.aprovar` e `simulador.entregar_avisos` |
| A-3 | Herdado da E07 | positivo | outras duas cobranças pendentes | `POST …/recusar/` numa e `POST …/expirar/` na outra | situações `recusado` e `expirado`; as mensagens de sucesso; um aviso para cada |
| A-4 | E07-01 | negativo | — | `POST …/<Q>/recusar/` e `POST …/<Q>/expirar/` | 409 com "A cobrança <Q> não pode ser recusada na situação atual." e "… expirada …"; nada muda |
| A-5 | Spec da fatia | negativo | — | `POST …/sim-999/aprovar/`; `GET …/<P>/aprovar/` | 404; 405 |
| A-6 | E02-10 | negativo | — | comprador, fornecedor e anônimo abrem a lista e fazem os `POST` | recusados pela política; nada muda; a varredura acusa as cinco rotas com a política `administrador` |
| A-7 | AGENTS.md §7 | negativo | `PROVEDOR_PAGAMENTOS` trocado por `monkeypatch` para um valor diferente de `simulador` (só a checagem da view; `obter_provedor` não é chamado) | o administrador abre a lista e faz um `POST` | 404 nos dois |
| A-8 | E07-01 A-16 | positivo | — | a varredura de importações do E07-01 | continua passando: só `apps/pagamentos/provedor.py` e `apps/simulador_pagamentos/` importam o simulador |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-5, A-7 | `tests/tecnicos/test_simulador_pagamentos_tela.py` |
| A-6 | o mesmo arquivo e `tests/tecnicos/test_permissoes_politica_rotas.py` (teste existente) |
| A-8 | `tests/tecnicos/test_pagamentos_fronteiras.py` (teste existente) |
