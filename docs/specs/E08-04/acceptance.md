# E08-04 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05): Red com caminhos explícitos de arquivos inteiros, sem `-k`, e tabela de cobertura do Red antes do Green. Os testes que usam o simulador declaram os dois bancos (E07-R03).

**Arranjo comum, salvo indicação:**

- `T0` = 2026-11-02 13:00 UTC;
- o pedido `X` de A, total R$ 94,35, em `aguardando_pagamento`;
- uma tentativa criada às 14:00, com a cobrança simulada `P` pendente;
- fixture `simulador_pagamentos` ativa.

O pagamento chega ao sistema pelo aviso (E07-05) e por `processar_chamadas()`, salvo indicação.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §8.3 | positivo | `aprovar(P, em=2026-11-02 15:00)` | aviso e processamento às 15:01 | destino `quita`; `X` `pago`, com `quitado_por` `P` e `quitado_em` 15:00; auditoria `pedido.quitar` com `na_margem` falso; um `pagamento_confirmado` para A, com "Recebemos o pagamento do seu pedido <X> da rodada de F, no valor de R$ 94,35. O pedido está pago." e a chave `pagamento_confirmado:<X>:<A>` |
| A-2 | T-2 | positivo e negativo | três pedidos iguais; aprovações em `T0 + 48h − 1 ms`, `T0 + 48h` e `T0 + 48h + 1 ms` | o processamento | os dois primeiros quitam (com `na_margem` verdadeiro); o terceiro fica `aguardando_pagamento`, com destino `devolucao` e `aprovado_apos_a_margem` |
| A-3 | T-3, cenário 25 | positivo | `aprovar(P, em=T0 + 47h59)`; o aviso só é entregue em `T0 + 50h` | o processamento em `T0 + 50h` | destino `quita`; `quitado_em` `T0 + 47h59`; `primeiro_aviso_em` `T0 + 50h` |
| A-4 | Cenário 26 | negativo | `aprovar(P, em=T0 + 49h)` | o processamento | destino `devolucao`, `aprovado_apos_a_margem`; `X` continua `aguardando_pagamento`; nenhum `pagamento_confirmado`; auditoria `pagamento.destino`; log `warning` com o `id_externo` |
| A-5 | Infra 4.3 | negativo | uma cobrança do mesmo pedido criada pelo simulador diretamente em `T0 + 24h`, com a referência de `X`, o mesmo valor e `expira_em` `T0 + 30h` (anomalia simulada, sem `pedir_pagamento`), e aprovada em `T0 + 25h` | a sincronização dela | destino `devolucao`, `iniciado_fora_do_prazo`; com a criação em `T0 + 24h − 1 ms` e o resto igual, `quita` |
| A-6 | Cenário 39 | positivo | duas cobranças do mesmo pedido (tentativas 1 e 2, com a 1 aprovada depois de expirada), as duas aprovadas no prazo | os dois processamentos, nas duas ordens possíveis | um `quita` e um `devolucao` com `duplicidade`; `X` `pago` uma vez; um único `pagamento_confirmado`; nas duas ordens: um pedido pago e uma devolução de R$ 94,35 |
| A-7 | Infra 4.2 | positivo | o A-1 já decidido | o mesmo pagamento sincronizado de novo, por aviso, tarefa e busca (`consultar_antes_de_decidir`) | nenhum destino, auditoria nem aviso novos |
| A-8 | Spec da fatia | negativo | uma cobrança criada no simulador com a referência `om-c999-p1`, `abc` ou `om-c<outro ciclo>-p<X>`, aprovada no prazo | a sincronização | destino `sem_pedido`, `referencia_desconhecida`, com `pedido` nulo; log `error`; auditoria `pagamento.destino`; nenhum pedido muda |
| A-9 | Spec da fatia | negativo | uma resposta construída de pagamento `aprovado` sem `aprovado_em`, sincronizada pelo serviço da E07-03 | a sincronização | nenhum destino; log `error` "Pagamento <id_externo> aprovado sem horário de aprovação"; `X` não muda |
| A-10 | Spec da fatia | negativo | uma cobrança de R$ 90,00 com a referência de `X`, aprovada no prazo | a sincronização | destino `devolucao`, `valor_divergente`; `X` continua `aguardando_pagamento` |
| A-11 | Spec §2, E08-06 | positivo | `X` cancelado por suspensão às 16:00 (pela E08-06); `P` aprovado no provedor em 15:30, informado às 17:00 | a sincronização às 17:00 | destino `quita`; `X` `pago`, com `cancelado_em` e motivo limpos; auditoria `pedido.quitar` com `cancelamento_sem_efeito` `suspensao`; um `pagamento_confirmado` |
| A-12 | Spec §2, §8.3 | negativo | o A-11, com a aprovação em 16:00 (igual a `cancelado_em`) e, noutro caso, em 16:30 | a sincronização | destino `devolucao`, `pedido_cancelado`; `X` continua `cancelado` |
| A-13 | Spec §12 | positivo | o A-1 | A abre o detalhe de `X` | "Pago em 02/11/2026 às 12:00 (horário de Brasília)."; nenhum botão de pagar; nenhum código Pix |
| A-14 | Cenário 24, herdado da E04 | positivo | A com WhatsApp consentido; WhatsApp simulado com `falhar_sempre()` | a quitação do A-1; `processar_envios()` até esgotar | `X` continua `pago`; o `pagamento_confirmado` tem só site e e-mail (nenhum envio de WhatsApp); e-mail `enviado`; a central mostra o aviso |
| A-15 | Spec da fatia | negativo | um receptor de teste de `situacao_do_pagamento_mudou`, ligado depois do receptor da quitação, que levanta `RuntimeError` | o processamento do A-1; depois, sem o receptor de teste, outro processamento | o primeiro não grava destino, situação nem aviso (a sincronização é desfeita); o segundo quita |
| A-16 | T-7, Infra 4.2 | concorrência | as duas cobranças do A-6 aprovadas | duas threads sincronizam uma cada, ao mesmo tempo, com a primeira segurando a trava da situação do pedido até a segunda aparecer esperando (prazo de espera com falha por asserção) | um `quita` e um `duplicidade`; `X` `pago`; um aviso |
| A-17 | T-6, Infra 4.2 | concorrência | `P` aprovado | o aviso e uma consulta da tarefa sincronizam `P` ao mesmo tempo | um destino; uma auditoria `pedido.quitar`; um aviso |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-15 | `tests/tecnicos/test_pedidos_quitacao.py` |
| A-2 | também marcado `acceptance`, com o comentário `T-2` |
| A-3 | também marcado `acceptance`, com o comentário `T-3, cenário 25` |
| A-4 | também marcado `acceptance`, com o comentário `cenário 26` |
| A-6 | também marcado `acceptance`, com o comentário `cenário 39` |
| A-14 | marcado `acceptance`, com o comentário `cenário 24 (confirmação real)` |
| A-16, A-17 | `tests/tecnicos/test_pedidos_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
