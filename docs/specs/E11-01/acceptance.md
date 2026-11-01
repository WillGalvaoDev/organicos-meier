# E11-01 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

## Arranjo comum da E11 (arranjo AP)

As fatias da E11 usam o mesmo arranjo, montado pelo apoio de testes da E08 (`tests/apoio/pedidos.py`, `montar_arranjo`), com o pagamento aberto em `T0` e frete de 22,00:

| Produto | Preço | Múltiplo | Parcelas, em ordem de sequência |
|---|---|---|---|
| P1 | 10,00 | — | A 6; B 5 |
| P2 | 5,00 | 6 | A 4; B 6; B 2 |

- **Caixas de P2:** a caixa 1 tem A 4 e B 2 (parte da parcela de 6); a caixa 2 tem B 4 (o resto da parcela de 6) e B 2.
- **Pedido X, de A:** produtos 80,00, serviço 4,00, frete 10,35, total 94,35.
- **Pedido Y, de B:** produtos 90,00, serviço 4,50, frete 11,65, total 106,15.
- **AP-viável:** mínimo de 50,00. **AP-insuficiente:** mínimo de 100,00.
- **"Pago pelo simulador":** o comprador pede o pagamento (E08-03) antes de `T0 + 24h`, `processar_chamadas()` cria a cobrança, e o simulador a aprova no instante indicado. Salvo indicação, a aprovação é em `T0 + 2h`, com o aviso entregue.
- **Relógio:** salvo indicação, em `T0 + 48h` na apuração.
- O autor é o administrador do apoio.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | T-4, P-8 | negativo | AP-viável; X e Y pagos pelo simulador; relógio em `T0 + 48h − 1 ms` | `iniciar_apuracao(admin, rodada)` | `ApuracaoRecusada("antes_do_prazo")`, com `T0 + 48h` na mensagem em Brasília; nenhuma consulta ao provedor registrada no simulador; nenhuma escrita (sem `ApuracaoFinal`, situações iguais, nenhuma chamada nova) |
| A-2 | T-4 | positivo | o A-1, com o relógio em `T0 + 48h` exato | `iniciar_apuracao` | uma `ApuracaoFinal` com `iniciada_em = T0 + 48h`, 2 pagos e 0 não pagos; a rodada continua `pagamento` |
| A-3 | Permissão | negativo | AP-viável | `iniciar_apuracao` com um comprador, com um fornecedor e com `None` | `PermissionDenied` nos três, sem escrita |
| A-4 | Etapa | negativo | uma rodada em `fechamento_encerrado` e outra em `interesse` | `iniciar_apuracao` | `ApuracaoRecusada("fora_de_pagamento")`, sem escrita |
| A-5 | §8.2 3.2 | positivo | AP-viável; X pago pelo simulador; Y sem pagamento | `iniciar_apuracao` | X `pago`; Y `cancelado`, com `motivo_do_cancelamento = "inadimplencia"` e `cancelado_em = T0 + 48h`; `pedidos_pagos = 1` e `pedidos_nao_pagos = 1`; a auditoria `rodada.apuracao_final` com os `pk` de X (pago) e de Y (não pago, situação anterior `aguardando_pagamento`, cancelado agora). **Red esperado:** a função não existe |
| A-6 | §7.1 | positivo | o A-5 | comparar `Pedido`, `ItemDoPedido` e `ParcelaNoPedido` antes e depois | iguais, campo a campo, e nenhuma linha nova |
| A-7 | Herdado E08 | positivo | AP-viável; X pago; Y cancelado por suspensão de B (E08-06) durante a margem | `iniciar_apuracao` | Y continua `cancelado` com o motivo `suspensao`; conta como não pago; nenhuma alteração de `cancelado_em` |
| A-8 | Infra 4.3 | positivo | AP-viável; X pago; Y com uma tentativa `criada` e a cobrança pendente no simulador | `iniciar_apuracao` | uma `ChamadaAoProvedor` `cancelar_cobranca` pendente com o alvo `t<tentativa>:apuracao`; repetir a chamada não é possível (`ja_apurada`), e a chamada continua única |
| A-9 | P-6, cenário 26 | positivo | AP-viável; X pago; a cobrança de Y criada antes de `T0 + 24h` e aprovada no simulador em `T0 + 48h + 1 ms`, sem aviso entregue; relógio em `T0 + 49h` | `iniciar_apuracao` | a reconsulta registra o pagamento; destino `devolucao` com o motivo `aprovado_apos_a_margem`, e a obrigação integral (E09-04); Y `cancelado` por `inadimplencia`. **Red esperado:** sem reconsulta, o pagamento não fica registrado na apuração |
| A-10 | P-6, infra 4.3 | positivo | o A-9 com a aprovação de Y em `T0 + 48h` exato, sem aviso entregue | `iniciar_apuracao` | a reconsulta quita Y antes da classificação: Y `pago`; 2 pagos e 0 não pagos |
| A-11 | E07-06, infra 4.3 | negativo | AP-viável; X pago; `falhar_proximas(1, operacao="consultar_pagamento")` (ou a busca por referência) no simulador | `iniciar_apuracao` | `ConsultaAoProvedorFalhou`; sem `ApuracaoFinal`; Y continua `aguardando_pagamento`; nenhuma chamada de cancelamento nova |
| A-12 | Contrato da consulta | negativo | AP-viável, num teste com `transaction=True` | `iniciar_apuracao` dentro de `transaction.atomic()` aberto pelo teste | `RuntimeError`; nenhuma consulta registrada no simulador; nenhuma escrita |
| A-13 | Idempotência | negativo | o A-5 feito | `iniciar_apuracao` de novo | `ApuracaoRecusada("ja_apurada")`; nenhuma auditoria nova; nenhuma chamada nova |
| A-14 | Concorrência | concorrência | AP-viável; X pago; Y sem pagamento | duas `iniciar_apuracao` em paralelo, com a primeira pausada depois de gravar a `ApuracaoFinal`, antes do commit ("Padrão das corridas", E09-01) | uma `ApuracaoFinal`; a outra recebe `ja_apurada`; Y cancelado uma vez; uma auditoria |
| A-15 | T-7, §8.3 | concorrência | AP-viável; X pago; a cobrança de Y aprovada no simulador em `T0 + 47h`, sem aviso entregue | (i) o aviso de Y processado antes da apuração; (ii) o aviso de Y pausado depois de travar a situação de Y, antes de quitar, e a apuração em paralelo, com a reconsulta de Y devolvendo "pendente" (dublê da consulta só na reconsulta da apuração) | (i) Y `pago`, 2 pagos. (ii) A apuração espera, na sincronização da reconsulta (trava do pagamento) ou na trava da situação de Y; depois do commit do aviso, Y `pago` e 2 pagos. Nos dois: um destino `quita` para Y, nenhuma devolução e Y nunca `cancelado`. **Red esperado em (ii):** a apuração cancela Y sem esperar a trava |
| A-16 | T-7, T-19, infra 4.4 | concorrência | AP-viável; X pago; a cobrança de Y aprovada no simulador em `T0 + 47h`, mas a reconsulta de Y devolvendo "pendente" (dublê da consulta só na reconsulta da apuração) | a apuração pausada depois de cancelar Y, antes do commit; o aviso de aprovação de Y processado em paralelo | o aviso espera a trava da situação de Y; depois do commit da apuração: Y continua `cancelado` por `inadimplencia`; destino `devolucao` com o motivo `pedido_cancelado`; obrigação integral de 106,15; alerta crítico `aprovado_no_prazo_depois_da_apuracao` aberto. **Red esperado:** Y quita, ou nenhum alerta |
| A-17 | T-19, cenário 51 | positivo | o A-5 feito; depois a cobrança de Y aprovada no simulador em `T0 + 47h59` (criada antes de `T0 + 24h`) e o aviso entregue em `T0 + 50h` | processar o aviso | Y continua `cancelado` por `inadimplencia`, sem `quitado_em`; destino `devolucao` com `pedido_cancelado`; uma obrigação integral do valor pago; alerta crítico `aprovado_no_prazo_depois_da_apuracao` com pedido, comprador, valor e horário; `Pedido` e itens inalterados. **Red esperado:** o pagamento quita Y |
| A-18 | T-19 | positivo | o A-17 | o aviso repetido 3 vezes | um destino, uma obrigação, um alerta |
| A-19 | Infra 4.4 | negativo | o A-5 feito; a cobrança de Y aprovada em `T0 + 49h` | processar o aviso | devolução com o motivo `aprovado_apos_a_margem` (a regra da E08-04 vem antes); nenhum alerta `aprovado_no_prazo_depois_da_apuracao` |
| A-20 | Herdado E08 | positivo | AP-viável; Y cancelado por suspensão em `T0 + 30h`; a cobrança de Y aprovada em `T0 + 29h` (antes do cancelamento); a apuração feita em `T0 + 48h`; o aviso entregue em `T0 + 50h` | processar o aviso | Y continua `cancelado` (suspensão); destino `devolucao` com `pedido_cancelado`; alerta crítico aberto. Sem a apuração, o mesmo aviso quitaria (E08-04). **Red esperado:** Y quita |
| A-21 | E09-06 | positivo | o A-17, com a devolução autorizada e o estorno concluído (E10-04) | — | a obrigação totalmente liquidada; o alerta `aprovado_no_prazo_depois_da_apuracao` resolvido |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-13 e A-17 a A-21 | `tests/tecnicos/test_apuracao_inicio.py` |
| A-14 a A-16 | `tests/tecnicos/test_apuracao_inicio.py`, com transações PostgreSQL reais (`transaction=True`) |

## Correção E11-R03 (2026-11-01)

Valem a seção "Correção E11-R03" do `spec.md` e as regras comuns da E11-08 (`spec.md`, "Correções da revisão da E11"). O A-8 original fica substituído pelo A-8 abaixo.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-8 | Infra 4.3, R03 | positivo | AP-viável; X pago; Y com uma tentativa `criada` e a cobrança pendente no simulador | `iniciar_apuracao` | antes da `ApuracaoFinal`, a cobrança de Y `cancelado` no simulador e no `PagamentoNoProvedor`. No registro de operações do simulador, a consulta vem antes do cancelamento. A chamada `cancelar_cobranca` de alvo `t<tentativa>:apuracao` `concluida`; Y cancelado por `inadimplencia`. **Red esperado:** a chamada só agendada (`pendente`) e a cobrança ainda `pendente` no provedor |
| A-22 | Infra 4.3, R03 | negativo | o arranjo do A-8; `falhar_proximas(1, operacao="cancelar_cobranca")` | `iniciar_apuracao` | `ConsultaAoProvedorFalhou` com o `id_externo` na mensagem; sem `ApuracaoFinal`; Y `aguardando_pagamento`; as parcelas iguais; a chamada `pendente` com o erro. **Red esperado:** a apuração termina |
| A-23 | Infra 4.3 (bloqueio ativo), P-6 | positivo | o arranjo do A-8, com o simulador aprovando a cobrança de Y na resposta do cancelamento, em `T0 + 47h` (`aprovacao_no_cancelamento`) | `iniciar_apuracao` em `T0 + 48h` | Y `pago`, com um destino `quita`; 2 pagos e 0 não pagos; nenhuma devolução |
| A-24 | Infra 4.3, R03 | positivo | AP-viável; X pago; uma cobrança pendente com a referência de Y no simulador, sem tentativa vinculada (órfã) | `iniciar_apuracao` | a cobrança órfã cancelada no provedor pela chamada de alvo `<id_externo>:apuracao`, antes da decisão; Y cancelado |
| A-25 | R03 | positivo | o arranjo do A-8, com o cancelamento recusado pelo simulador (`estado_invalido`) e a cobrança já `cancelado` na reconsulta | `iniciar_apuracao` | a reconsulta registra `cancelado`; a apuração prossegue; Y cancelado por `inadimplencia` |
| A-26 | R03 | negativo | o arranjo do A-8, com o cancelamento recusado e a cobrança ainda `pendente` na reconsulta | `iniciar_apuracao` | `ConsultaAoProvedorFalhou`; sem `ApuracaoFinal` |
| A-27 | R03 | negativo | o A-8 até o fim do passo 4-A; depois um dublê que deixa um `PagamentoNoProvedor` da abertura `pendente` antes da transação da decisão | a decisão | `ApuracaoRecusada("cobranca_aberta")`, sem escrita |
| A-28 | R03 | positivo | o arranjo do A-8, com a chamada do bloqueio de `T0 + 24h` (alvo do bloqueio) pendente com erro | `iniciar_apuracao` | a chamada de alvo `t<tentativa>:apuracao` executada e `concluida`; a do bloqueio continua como estava; a cobrança cancelada uma vez no provedor (o segundo cancelamento, quando o executor rodar, não muda nada) |
| A-29 | Auditoria | positivo | o A-8 | ler a auditoria `rodada.apuracao_final` | a cobrança de Y nas canceladas pelo passo 4-A, com a situação `cancelado` |

As provas `test_cancelamento_no_provedor_precede_apuracao` e `test_falha_do_cancelamento_bloqueia_apuracao` do parecer têm de passar como estão.

| Critério | Arquivo de teste |
|---|---|
| A-8 e A-22 a A-29 | `tests/tecnicos/test_apuracao_inicio.py` |
