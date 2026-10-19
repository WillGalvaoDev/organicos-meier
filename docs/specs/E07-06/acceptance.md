# E07-06 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05). Salvo indicação, o relógio está em 2026-11-02 13:00 UTC, a fixture `simulador_pagamentos` está ativa e as cobranças simuladas usam a referência `"ref-1"`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 4.2, Spec §8.3 | positivo | uma cobrança `P` aprovada às 12:30, sem nenhum aviso entregue e sem registro no sistema | `consultar_antes_de_decidir("ref-1")` | devolve um registro, `aprovado`, com `aprovado_no_provedor_em` 12:30 e `primeiro_aviso_em` nulo; a consulta no histórico tem origem `busca`; uma auditoria e um sinal |
| A-2 | Infra 4.2 | positivo | duas cobranças `P1` e `P2` da referência, as duas aprovadas, criadas em instantes diferentes; uma terceira de outra referência | o serviço | devolve `P1` e `P2`, nessa ordem; a terceira não é registrada |
| A-3 | L-6 | positivo | `P` registrado `pendente`; depois `aprovar(P)`; a busca do simulador por `"ref-1"` monkeypatched para devolver lista vazia | o serviço | `P` é reconsultado diretamente e fica `aprovado`; a consulta tem origem `decisao`; devolve `[P]` |
| A-4 | Infra 4.2 | negativo | `P` registrado; `indisponivel()` | o serviço | `ConsultaAoProvedorFalhou` com `motivo` `indisponivel` e `__cause__` `ProvedorIndisponivel`; nenhuma consulta nova no histórico; o log tem a referência e o motivo |
| A-5 | Infra 4.2 | negativo | `P1` e `P2` registrados; a busca devolve só `P1`; a reconsulta de `P2` falha com `falhar_proximas(1, operacao="consultar_pagamento")` | o serviço | `ConsultaAoProvedorFalhou` com `indisponivel`; a sincronização de `P1` pela busca continua gravada |
| A-6 | Spec da fatia | negativo | um `PagamentoNoProvedor` registrado para `"ref-1"` com um `id_externo` que o simulador não conhece (criado pelo serviço de sincronização com uma resposta construída), e a busca vazia | o serviço | `ConsultaAoProvedorFalhou` com `motivo` `nao_encontrado` |
| A-7 | Spec da fatia | positivo | nenhuma cobrança com a referência | o serviço | devolve lista vazia, sem erro |
| A-8 | Spec da fatia | positivo | `P` aprovado e já registrado `aprovado` | o serviço duas vezes | duas consultas novas no histórico (uma por chamada, origem `busca`); nenhuma auditoria nem sinal novos |
| A-9 | Spec da fatia | negativo | o serviço levanta `ConsultaAoProvedorFalhou` | inspeciono a mensagem da exceção e o log | nenhum contém valor, descrição nem dados para pagar |
| A-10 | Infra 4.2 | concorrência | `P` aprovado e registrado `pendente`; um aviso de `P` com a consulta agendada | `processar_chamadas()` numa thread, segurando a trava da linha de `P` dentro de `sincronizar_pagamento`, enquanto o serviço roda noutra thread e espera (prazo de espera com falha por asserção) | os dois terminam; `P` fica `aprovado`; uma única auditoria de mudança; um sinal |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-9 | `tests/tecnicos/test_pagamentos_consulta.py` |
| A-1 | também marcado `acceptance`, com o comentário `§8.3 identificado na apuração` |
| A-10 | `tests/tecnicos/test_pagamentos_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
