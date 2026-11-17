# E15-03 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo:** o AO da E15-02 (administradores ativos e todas as tarefas em dia).
- **Execução:** `verificar_operacao_agora()` chamada diretamente. Os registros de domínio são montados pelos apoios das etapas anteriores (`tests/apoio`).
- **Instantes:** `I = 2026-11-20 12:00 UTC`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Fechamento | positivo | rodada de F em `fechamento` com o prazo em `I` | verificar em `I + 5min` e em `I + 5min + 1s` | nada na primeira; na segunda, `fechamento_nao_encerrado` com a chave `rodada:<pk>`, o corpo "O fechamento da rodada de <F> terminou em 20/11/2026 09:00 e ainda não foi encerrado." e o link de `rodadas_estoque`. **Red esperado:** o tipo não existe |
| A-2 | Fechamento | positivo | o A-1 | `encerrar_fechamentos_vencidos()`; verificar | o alerta resolvido |
| A-3 | Fechamento | negativo | rodada em `fechamento` com o prazo prorrogado para `I + 1h` | verificar em `I + 10min` | nenhum alerta |
| A-4 | Pedido formal | positivo | pedido formal em `em_andamento` com `proxima_tentativa_em = I` (E13-02) | verificar em `I + 6min` | `pedido_formal_atrasado` com a chave `pedido_formal:<pk>` e o link de `rodadas_pedido_formal` |
| A-5 | Pedido formal | positivo | o A-4 | `processar_pedidos_formais()` com o e-mail aceito; verificar | o alerta resolvido (envio concluído) |
| A-6 | Pedido formal | negativo | pedidos formais `concluido_com_falhas` e `interrompido` com `proxima_tentativa_em` antiga | verificar | nenhum `pedido_formal_atrasado` |
| A-7 | Conciliação | positivo | última `ConciliacaoDiaria` de 17/11/2026, portanto `P = 18/11/2026`, que termina em `2026-11-19 03:00 UTC` (`limites_do_dia`) | verificar em `2026-11-20 03:00:00 UTC` e em `2026-11-20 03:00:01 UTC` | nada na primeira; na segunda, `conciliacao_atrasada` com a chave `dia:2026-11-18`, o corpo "O dia 18/11/2026 terminou há mais de 24 horas e ainda não foi conciliado. A última conciliação é de 17/11/2026." e o link de `financeiro_conciliacoes` |
| A-8 | Regra 6 | positivo | o A-7 aberto; `ConciliacaoDiaria` de 18/11 gravada; relógio em `21/11/2026 03:00:01 UTC` | verificar | o alerta de `dia:2026-11-18` resolvido e um novo de `dia:2026-11-19` aberto |
| A-9 | Regra 4 | negativo | nenhuma `ConciliacaoDiaria` | verificar em qualquer instante | nenhum `conciliacao_atrasada` |
| A-10 | Chamadas | positivo | uma chamada `pendente` com `proxima_em = I` e outra com `criada_em = I − 25h − 1s` e `proxima_em` futura | verificar em `I + 5min + 1s` | um `chamadas_ao_provedor_atrasadas` com a chave `geral`, `quantidade = 2` e `mais_antiga` igual ao `criada_em` da segunda |
| A-11 | Chamadas | positivo | o A-10 | as duas chamadas concluídas; verificar | o alerta resolvido |
| A-12 | Chamadas | negativo | chamada `pendente` com `proxima_em = I + 1min`, criada em `I − 2h` | verificar em `I` | nada |
| A-13 | Envios | positivo | dois `Envio` `pendente`, com `proxima_tentativa_em` em `I` e em `I + 1min` | verificar em `I + 6min + 1s` | `envios_atrasados` com `quantidade = 2` e o link de `envios_lista` |
| A-14 | Regra 5 | positivo | o A-13 aberto; um terceiro envio atrasado | verificar | o mesmo alerta, com os dados de antes (`quantidade = 2`); nenhuma notificação nova |
| A-15 | Invariante | negativo | os arranjos do A-1, A-4, A-10 e A-13 | verificar e comparar os registros de domínio antes e depois | rodada, envios, chamadas e conciliações iguais |
| A-16 | Regra 2 | negativo | os alertas abertos nos critérios acima | ler `dados` e o corpo | nenhum nome, e-mail ou WhatsApp de comprador |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-16 | `tests/tecnicos/test_alertas_de_atraso.py` |
