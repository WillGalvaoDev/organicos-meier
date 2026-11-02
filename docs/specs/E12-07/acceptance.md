# E12-07 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Os cenários são os do `spec.md`, com o simulador, as chamadas processadas pelo executor real e o invariante conferido no fim de cada critério.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenários 41, 43; infra 7 | positivo | AP; X pago; Y com a cobrança pendente; relógio em `T0 + 30h` | o administrador cancela pela tela com reembolso; `processar_chamadas()` até esvaziar | a cobrança de Y `cancelado` no simulador; o estorno de X concluído (94,35); a obrigação de X liquidada; o aviso `estorno` a A (E10); o invariante sem violação |
| A-2 | Cenário 51, T-19; infra 7 | positivo | o A-1, com a cobrança de Y aprovada no simulador antes do processamento do cancelamento | processar o aviso de aprovação de Y | Y `cancelado` e intacto; a devolução de destino com a obrigação integral; o alerta crítico `pagamento_depois_do_cancelamento`; depois da autorização do administrador (E10), o estorno de Y concluído |
| A-3 | Cenário 44, T-15 | positivo | AP-viável apurada; um pagamento de Y aprovado em `T0 + 48h + 1 ms` (obrigação de destino pendente) | cancelar sem reembolso; depois, com o saldo do pagamento já liberado no simulador (`PRAZO + 3 dias`; antes disso o estorno é falha temporária `saldo_insuficiente`), o administrador autoriza a devolução de destino pela tela da E10 | nenhuma obrigação nova no cancelamento; a obrigação existente continua devida, sem baixa; depois da autorização, o estorno concluído |
| A-4 | Cenários 43, 45, 91 | positivo | AP-viável apurada e aprovada, com a tarifa de X registrada | cancelar com reembolso; o administrador cobre o que falta; a tarefa de autorização; `processar_chamadas()`; a conciliação do dia | a devolução concluída; a conciliação sem divergência da devolução; a `ApuracaoNoLivro` e a `AprovacaoDoResultado` intactas |
| A-5 | Cenário 114, T-14 | positivo | um pedido pago com o item de 7,99/kg × 1 kg (produtos 7,99, serviço 0,40, frete 1,60, total 9,99) e uma devolução parcial de 0,25 kg concluída no simulador (2,50: 2,00 de produtos, 0,10 de serviço e 0,40 de frete) | cancelar com reembolso; processar | o reembolso do cancelamento com 7,49 (5,99 de produtos, 0,30 de serviço e 1,20 de frete); a soma devolvida do pedido, por componente, igual ao pago (corrigido na revisão R01–R03) |
| A-6 | T-13 | concorrência | AP; X e Y pagos | dois cancelamentos com reembolso em paralelo, com transações reais | um cancelamento; o outro `ja_cancelada`; no simulador, um estorno por pagamento depois de processar |
| A-7 | T-16, cenário 42 | negativo | AP | pelo cliente HTTP: POST com `compradores`; POST sem motivo; POST como comprador e como fornecedor | 400; aceito; recusado; recusado |
| A-8 | Cenários 41, 45 | positivo | o A-1 | abrir uma rodada nova do fornecedor com P1 no estoque | a rodada nova em `interesse`; a rodada cancelada, os pedidos X e Y, os reembolsos e as devoluções consultáveis e inalterados |

| A-9 | R01–R03, cenário 8 | positivo | AP-R (E12-02, correção R03) | o administrador cancela pela tela, com reembolso num teste e sem reembolso noutro; `processar_chamadas()` | sem exceção; o aviso de A e a página de X conforme E12-05 A-8/A-9 e E12-06 A-20/A-21; nenhum reembolso do cancelamento para X; a devolução de mínimo de X com uma única parcela de devolução no máximo; o invariante sem violação |
| A-10 | Regra comum | positivo | os testes de A-6, A-7 e A-8 | ao fim de cada um | `_invariante_ok()` chamado e sem alerta `invariante_violado` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-5, A-7 a A-10 | `tests/tecnicos/test_cancelamento_ponta_a_ponta.py` |
| A-6 | `tests/tecnicos/test_cancelamento_ponta_a_ponta.py`, com transações PostgreSQL reais |
