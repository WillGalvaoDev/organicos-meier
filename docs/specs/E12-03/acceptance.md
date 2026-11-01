# E12-03 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo:** AP, como na E12-02 (X de A, 94,35: produtos 80,00, serviço 4,00, frete 10,35; Y de B, 106,15).
- **Cancelamento:** `cancelar_rodada(admin, rodada, com_reembolso=True)`, fora de transação.
- **Relógio:** salvo indicação, `T0 + 2h`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §7.2, cenário 43 | positivo | AP; X pago pelo simulador; Y sem pagamento | cancelar com reembolso | um `Reembolso` de X, tipo `integral`, motivo `cancelamento_da_rodada`, autor o administrador, chave `cancelamento:<rodada>:<A>:<X>`, com produtos 80,00, serviço 4,00 e frete 10,35; uma `ObrigacaoComComprador` de 94,35 financiada pela custódia (sem cobertura zero); nenhum reembolso para Y. **Red esperado:** nenhum reembolso |
| A-2 | Regra 5, §7.2 | positivo | o A-1 | inspecionar as devoluções depois do retorno de `cancelar_rodada` | uma `ParcelaDeDevolucao` `solicitada` de 94,35, para o pagamento de X, `autorizada_por` vazio (sistema); uma chamada `estornar` agendada; a auditoria `financeiro.devolucao_autorizada`. **Red esperado:** a obrigação sem parcela |
| A-3 | §9.2, cenário 91 | positivo | o A-2; `processar_chamadas()` | inspecionar | o estorno de 94,35 concluído no simulador; a obrigação liquidada (E10-04); a soma dos `ItemReembolsado` de X igual aos subtotais dos itens |
| A-4 | Infra 4.2, herdado E07 | negativo | AP; X pago; `falhar_proximas(1, operacao="consultar_pagamento")` no simulador | cancelar com reembolso | `ConsultaAoProvedorFalhou`; a rodada na etapa anterior; Y `aguardando_pagamento`; nenhum `CancelamentoDaRodada`, reembolso, obrigação nem chamada nova |
| A-5 | Regra 2 | positivo | AP; a cobrança de Y aprovada no simulador em `T0 + 1h30`, sem aviso entregue | cancelar com reembolso | a consulta prévia quita Y antes das travas; Y `pago`; reembolsos integrais de X e de Y (106,15) |
| A-6 | T-14, infra 4.8 | positivo | AP-viável apurada (E11-01 a E11-04): X pago, Y inadimplente; a obrigação de caixa invalidada de A (23,59) pendente de autorização | cancelar com reembolso | o reembolso do cancelamento de X com 70,76 (produtos 60,00, serviço 3,00, frete 7,76); a obrigação de 23,59 continua sem parcela, à espera da autorização do administrador; a soma dos reembolsos de X = 94,35 |
| A-7 | Cenário 114, infra 4.12 | positivo | um pedido pago com um item de 7,99/kg × 1 kg (incremento 0,25) e uma ocorrência parcial já registrada por `reembolso_parcial(item, 0,25, motivo="ocorrencia_de_entrega")` (2,00) | cancelar com reembolso | o reembolso do cancelamento devolve exatamente 5,99 nesse item; o serviço e o frete pelo saldo exato de cada componente |
| A-8 | Regra 4 | positivo | AP-insuficiente apurada (retorno ao interesse, E11-05) com X pago e a devolução integral de mínimo (94,35) pendente; depois um ciclo 2 iniciado e a rodada em `fechamento` | cancelar com reembolso | nenhum reembolso novo para X (sem saldo); a auditoria lista X entre os pagos sem reembolso novo |
| A-9 | Infra 3.2, E09-06 | positivo | AP-viável apurada e aprovada (`aguardando_fornecedor`), X pago, sem tarifa | cancelar com reembolso | a obrigação de X `depois_da_apuracao`, financiada por obrigação com o fornecedor (produtos), receita de serviço (serviço) e frete (frete), sem falta de cobertura; os saldos dessas contas diminuídos exatamente pelos componentes |
| A-10 | Regra 5, regra 6 | positivo | o A-9 com a tarifa de X registrada (a receita de serviço de X menor que o serviço) | cancelar com reembolso; depois `cobrir_obrigacao_com_receita` (ou a designação da reserva) pelo que falta; depois `autorizar_devolucoes_do_cancelamento_agora()` | a obrigação com falta de cobertura e sem parcela depois do cancelamento (o log com `DevolucaoRecusada`); depois da cobertura, a tarefa cria a parcela `solicitada` |
| A-11 | Regra 5 | positivo | AP; X pago; o simulador falhando a próxima consulta só na autorização (depois do commit; dublê da consulta na `autorizar_devolucao`) | cancelar com reembolso | o cancelamento confirma e retorna; a obrigação sem parcela; depois `autorizar_devolucoes_do_cancelamento_agora()` cria a parcela |
| A-12 | Regra 6 | negativo | o A-2 | `autorizar_devolucoes_do_cancelamento_agora()` duas vezes | nenhuma parcela nova; nenhuma chamada nova |
| A-13 | Regra 6, escopo | negativo | uma obrigação de outro motivo (caixa invalidada) sem parcela | `autorizar_devolucoes_do_cancelamento_agora()` | não é autorizada |
| A-14 | Cenário 43 | negativo | AP; nenhum pagamento | cancelar com reembolso | nenhum reembolso, obrigação ou parcela; X e Y `cancelado` por `cancelamento_da_rodada` |
| A-15 | Cenário 46, E10-06 | positivo | o A-2; o estorno no simulador com falha definitiva comprovada | `processar_chamadas()`; a reconsulta da E10 | a parcela elegível para a devolução excepcional; a confirmação excepcional pelo administrador liquida a obrigação; nenhuma segunda parcela nem segunda confirmação |
| A-16 | Auditoria | positivo | o A-1 | ler a auditoria `rodada.cancelar` | o reembolso de X com a chave e os componentes; `com_reembolso` verdadeiro |
| A-17 | T-13 | concorrência | AP; X e Y pagos | dois `cancelar_rodada(..., com_reembolso=True)` em paralelo, o primeiro pausado depois de gravar os reembolsos, antes do commit | o segundo recebe `ja_cancelada`; um reembolso por pedido; uma obrigação e uma parcela por pedido; a soma devolvida de cada pedido igual ao pago |
| A-18 | Concorrência | concorrência | AP; X pago; a cobrança de Y aprovada no simulador | o cancelamento pausado depois das travas, antes do commit; o aviso de aprovação de Y processado em paralelo | o aviso espera a trava da situação de Y; depois do commit, Y `cancelado` por `cancelamento_da_rodada`, sem reembolso do cancelamento; o destino do pagamento de Y é o da E12-04 |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-16 | `tests/tecnicos/test_cancelamento_com_reembolso.py` |
| A-17 e A-18 | `tests/tecnicos/test_cancelamento_com_reembolso.py`, com transações PostgreSQL reais |
