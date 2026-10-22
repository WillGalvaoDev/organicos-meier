# Referência da API do Mercado Pago para o simulador de pagamentos

Este documento é de apoio, não uma fonte de regra de negócio (AGENTS.md §2).

Ele reúne o que a documentação pública do Mercado Pago diz sobre os pontos que o sistema usa. A finalidade é dupla:

- **Para o simulador** (`apps.simulador_pagamentos`): ele deve reproduzir os padrões de comportamento do provedor real, como idempotência, estados, avisos, atrasos, saldo e tarifas, sem copiar o formato dele.
- **Para a tradução da fase 2a:** é ela que transforma o Mercado Pago no vocabulário interno de `apps.pagamentos.provedor`.

**Limites.** A consulta foi feita em 2026-10-22, na referência pública, e algumas páginas vieram truncadas. Nada aqui substitui a prova de conceito no sandbox da fase 0. As limitações L-1 a L-13 da infraestrutura (seção 9.2) continuam abertas até essa prova. O que a documentação não confirmou aparece marcado como **a confirmar**.

**Precedência.** Se este documento divergir da especificação funcional, da infraestrutura ou de uma especificação aprovada, valem esses documentos. A divergência é levada ao especificador.

## 1. Como usar este documento

1. **Vocabulário interno.** O simulador fala o vocabulário interno: situações `pendente`, `aprovado`, `recusado`, `cancelado` e `expirado`, e os tipos `PagamentoConsultado`, `MovimentoNoProvedor` e outros. Ele não imita JSON, nomes de campo nem códigos do Mercado Pago. A tradução é papel da implementação real do protocolo.
2. **Comportamento.** O que o simulador deve reproduzir é o comportamento: o que pode falhar, o que se repete, o que chega atrasado, o que é idempotente e o que é definitivo. Toda especificação nova do simulador confere a seção correspondente daqui.
3. **Diferenças registradas.** Uma diferença de comportamento entre o simulador e o Mercado Pago fica registrada na seção 10, com o motivo, ou vira correção especificada. Diferença silenciosa não é aceita.
4. **Nada além do documentado.** O simulador não inventa comportamento do provedor que não esteja documentado aqui ou validado no sandbox. Quando precisar de um comportamento ainda não validado, ele é simulado como possibilidade (por exemplo, `atrasar_consistencia`), e não como garantia.

## 2. Visão geral da API

- **URL base:** `https://api.mercadopago.com`.
- **Autenticação:** `Authorization: Bearer <access token>` (OAuth do Mercado Pago). O token é segredo e fica fora do Git (`fly secrets`).
- **Idempotência:** o cabeçalho `X-Idempotency-Key` é **obrigatório** na criação do pagamento e no reembolso. Sem ele, a criação devolve o erro `4292` ("Header X-Idempotency-Key can't be null"). Repetir a requisição com a mesma chave não repete a ação.
- **Horários:** ISO 8601 com fuso (por exemplo, `2017-09-14T11:26:38.000Z` ou `...-04:00`). A tradução converte tudo para UTC (L-4).

**APIs de pagamento na referência atual:**

| API | Uso | Situação no projeto |
|---|---|---|
| Payments API (`/v1/payments`) | criação direta de pagamento, inclusive Pix (Checkout Transparente) | candidata para o Pix da fase 2a |
| Checkout Pro (Preferences) | página de pagamento do Mercado Pago, cartões e Pix | recomendada pela infraestrutura para cartões (fase 2b) |
| Orders API (Checkout Pro e Checkout Transparente) | integração nova que a referência passou a oferecer | **a avaliar** antes da fase 2a (milestone E16) |

## 3. Pagamento

`GET /v1/payments/{id}`. Os campos que interessam ao sistema:

| Campo do Mercado Pago | Significado | No modelo interno |
|---|---|---|
| `id` | identificador numérico gerado pelo Mercado Pago | `id_externo` (texto) |
| `status` | situação (seção 3.1) | `situacao` |
| `status_detail` | detalhe da situação | não guardado; usado na tradução |
| `date_created` | criação do pagamento | `criado_em` |
| `date_approved` | aprovação; pode ser diferente da criação, porque o pagamento passa por estado intermediário | `aprovado_em` (P-6 decide por ele) |
| `date_last_updated` | último evento do pagamento | não usado |
| `date_of_expiration` | vencimento (seção 4) | `expira_em` |
| `external_reference` | referência do integrador | `referencia_externa` (`om-c<ciclo>-p<pedido>`) |
| `transaction_amount` | valor cobrado | `valor` |
| `transaction_details.net_received_amount` | líquido recebido | base para conferir a tarifa |
| `fee_details[]` (`type`, `amount`, `fee_payer`) | tarifas | `tarifa` = soma das tarifas pagas pelo recebedor; `fee_payer: payer` não entra (E09-02) |
| `money_release_date` | data de liberação do dinheiro (nula até haver data) | `liberado_em` (nulo = a liberar, L-10) |
| `transaction_amount_refunded` | total já reembolsado | conferência das devoluções (E10) |
| `payment_method_id` e `payment_type_id` | meio (`pix`, `visa`...) e tipo | `meio` |
| `point_of_interaction.transaction_data` | dados do Pix (seção 4) | `dados_para_pagar` |

### 3.1 Situações

As situações documentadas, com a tradução prevista:

| `status` | Detalhes documentados (`status_detail`) | Situação interna |
|---|---|---|
| `pending` | `pending_waiting_transfer` (Pix e transferência), `pending_waiting_payment`, `pending_challenge` | `pendente` |
| `in_process` | `offline_process`, `pending_contingency`, `pending_review_manual` | `pendente` |
| `authorized` | `pending_capture` (cartão) | `pendente` (fase 2b) |
| `approved` | `accredited`; `partially_refunded` (aprovado com reembolso parcial) | `aprovado` |
| `rejected` | `bank_error`, `rejected_by_bank`, `rejected_by_regulations`, `cc_rejected_*`... | `recusado` |
| `cancelled` | cancelado pela API ou vencido (o detalhe do vencimento do Pix está **a confirmar**) | `cancelado` ou `expirado`, pelo detalhe |
| `refunded` e `charged_back` | depois da aprovação: reembolsado ou contestado | **sem situação interna**: o pagamento continua `aprovado` no sistema, e a devolução ou a contestação são registros à parte (E10) |
| `in_mediation` | em disputa | **a confirmar**; contestação na E10 |

**Padrões que o simulador reproduz:**

- **Estados intermediários.** `in_process` e `authorized` existem. O simulador não precisa deles na fase 1, porque a tradução os junta em `pendente`. Uma aprovação pode vir depois de um tempo em `pending` ou `in_process`.
- **Situação terminal.** A situação terminal não volta para pendente. Uma leitura que mostre pendente depois de aprovado é atraso de consistência (E07-03), e não mudança real.
- **Mudança depois da aprovação.** Reembolso e contestação mudam o `status` do Mercado Pago depois da aprovação. No sistema, a aprovação continua sendo o fato que decide o destino (P-6), e o resto é registrado à parte.

## 4. Pix: criação

`POST /v1/payments` com `X-Idempotency-Key`.

- **Corpo:**
  - `transaction_amount`;
  - `payment_method_id: "pix"`;
  - `description`;
  - `payer.email` (obrigatório);
  - `payer.identification` (tipo e número, por exemplo, CPF);
  - opcionais: `date_of_expiration`, `external_reference` e `notification_url`.
- **Resposta:** `id`, `status: "pending"`, `status_detail: "pending_waiting_transfer"`, `point_of_interaction.type: "PIX"` e `point_of_interaction.transaction_data`, com:
  - `qr_code` (o "copia e cola");
  - `qr_code_base64` (a imagem);
  - `ticket_url` (a página com os dados do pagamento).

  O QR Code deve ser usado uma única vez.
- **Vencimento (`date_of_expiration`):**
  - o padrão é 24 horas;
  - o valor precisa estar **entre 30 minutos e 30 dias** a partir da emissão;
  - o formato é `yyyy-MM-dd'T'HH:mm:ssz` (erro `23` se inválido).
- **Consequência para a cobrança perto de `T0 + 24h`** (L-1, infraestrutura 4.5). Uma tentativa criada a menos de 30 minutos do prazo não pode vencer exatamente em `T0 + 24h`. A tradução da fase 2a usa `max(T0 + 24h, emissão + 30 min)`. Quem garante o fim em `T0 + 24h` é a recusa no servidor (E08-03) mais o cancelamento ativo pelo bloqueio (E08-05). Um pagamento criado antes de `T0 + 24h` e aprovado na margem é aceito (P-6). **O simulador hoje aceita qualquer vencimento** (seção 10).
- **Repetição com a mesma chave:** a criação não é repetida. O simulador reproduz isso devolvendo a cobrança existente (E07-01).

## 5. Busca por referência

`GET /v1/payments/search`, com os parâmetros:

- `external_reference`;
- `sort` (`date_created`, `date_last_updated`, `date_approved`, `money_release_date` ou `id`);
- `criteria` (`asc` ou `desc`);
- `range` (`date_created`, `date_last_updated`, `date_approved` ou `money_release_date`);
- `begin_date` e `end_date` (por exemplo, `NOW-30DAYS` e `NOW`).

A resposta vem paginada (`paging`).

**Padrões que o simulador reproduz:**

- A busca devolve todos os pagamentos da referência, inclusive os que o sistema não conhece. É assim que se recupera uma resposta perdida (E08-R03).
- A busca pode atrasar em relação à criação (L-6). O simulador reproduz isso com `atrasar_consistencia`.
- A paginação é responsabilidade da tradução. A interface interna devolve a lista completa.

## 6. Cancelamento

`PUT /v1/payments/{id}` com `{"status": "cancelled"}`. O campo só aceita `cancelled`.

- Só funciona para `pending`, `in_process` ou `authorized`. Em qualquer outro estado, devolve o **erro `2018`**.
- A tradução da fase 2a transforma o `2018` numa consulta do pagamento e devolve o estado atual. É o contrato da interface, que o simulador já cumpre (E07-01).
- **A confirmar (L-2):** o que acontece quando o pagador conclui o Pix no mesmo instante do cancelamento. O simulador reproduz a possibilidade com `aprovar_no_cancelamento`.

## 7. Reembolso (E10)

`POST /v1/payments/{id}/refunds`, com `X-Idempotency-Key` obrigatório.

- **Com `amount`:** reembolso parcial.
- **Sem `amount`:** reembolso total.
- **Resposta:** inclui `status` (exemplo: `approved`) e `refund_mode` (exemplo: `standard`).
- **Recusas documentadas** (candidatas a "comprovadamente inviável", P-5, **a confirmar** no sandbox, L-7):

  | Código | Mensagem |
  |---|---|
  | `3024` | "Partial refund unsupported for this transaction" |
  | `2024` e `15016` | "Payment-too-old-to-be-refunded" |
  | `4293` | "Invalid-payment-status-to-refund-charges" |

- **A confirmar (L-7):** se o reembolso exige saldo disponível, o prazo máximo, se a tarifa é devolvida e os estados intermediários do reembolso.
- **No relatório de liberações,** o reembolso aparece como `refund`, e a interface o traduz como movimento `devolucao` (E09-02).

## 8. Avisos (webhooks)

**Corpo de um aviso de pagamento:**

```json
{
  "id": 12345,
  "live_mode": true,
  "type": "payment",
  "date_created": "2015-03-25T10:04:58.396-04:00",
  "user_id": 44444,
  "api_version": "v1",
  "action": "payment.created",
  "data": { "id": "999999999" }
}
```

- **Na URL:** o `data.id` vem também na query string, e é dela que a assinatura usa o valor.
- **Cabeçalhos:**
  - `x-signature`, no formato `ts=<timestamp>,v1=<assinatura>`;
  - `x-request-id`.
- **Assinatura:**
  - o modelo de texto é `id:[data.id da URL];request-id:[x-request-id];ts:[ts];`;
  - a assinatura é um HMAC com SHA256, em hexadecimal, com o segredo da aplicação (painel, seção Webhooks);
  - a comparação com o `v1` precisa ser exata e em tempo constante;
  - se um dos valores do modelo não vier, ele é retirado do texto;
  - o `ts` permite uma tolerância de atraso, contra reenvio malicioso.

  O texto exato, com o `;` final e a origem do id, está **a confirmar** no sandbox (L-11).
- **Resposta esperada:** HTTP `200` ou `201`, em até **22 segundos**.
- **Reenvio:**
  - sem confirmação, o Mercado Pago reenvia a cada **15 minutos** até receber resposta;
  - depois da terceira tentativa, o intervalo aumenta;
  - não há limite documentado de tentativas.

**Padrões que o simulador reproduz** (E07-05):

- O aviso só avisa. O estado vem da consulta (infraestrutura 4.2).
- Avisos repetidos, atrasados, fora de ordem e perdidos.
- Assinatura conferida antes de qualquer gravação: 401 sem gravar.
- Resposta rápida. O recebimento só grava o evento e agenda a consulta, e nunca consulta o provedor dentro da requisição, para caber nos 22 segundos.
- Desde a E09-02, `verificar_aviso` recebe também os parâmetros da URL, necessários para o texto assinado.

## 9. Saldo, movimentos e relatórios

**Não há endpoint de saldo em tempo real** na referência pública. O saldo e os movimentos vêm de relatórios gerados de forma assíncrona: a criação devolve uma tarefa, que se consulta até ficar pronta, e o arquivo sai em CSV ou XLSX. A geração pode ser programada.

| Relatório | Caminho | Conteúdo |
|---|---|---|
| Liberações (*release report*) | `/v1/account/release_report` | dinheiro liberado e saldo disponível, linha a linha |
| Dinheiro em conta (*settlement report*) | `/v1/account/settlement_report` (caminho **a confirmar**) | as transações, inclusive o dinheiro ainda não liberado |

**Colunas do relatório de liberações:**

| Coluna | Significado | Uso na tradução |
|---|---|---|
| `DATE` | liberação, quando afeta o saldo disponível | `liberado_em` |
| `SOURCE_ID` | identificador da transação (por exemplo, o pagamento) | `id_externo` ou `id_movimento` |
| `EXTERNAL_REFERENCE` | referência do integrador (pode vir vazia em transferências) | conferência |
| `RECORD_TYPE` | `initial_available_balance`, `release`, `total` ou `available_balance` | saldo de abertura e fechamento |
| `DESCRIPTION` | `payment`, `refund`, `payout` (saque ou transferência), `chargeback`, `dispute`, `shipping`, `shipping_cancel`, `fee_release_in_advance`, `pre_payout_<id>`, `pos_payout_<id>`, `tax_withdholding` (grafia da página, **a confirmar**) | tipo do movimento |
| `NET_CREDIT_AMOUNT` e `NET_DEBIT_AMOUNT` | crédito e débito no saldo disponível | `valor` com sinal |
| `GROSS_AMOUNT` | valor bruto | conferência |
| `MP_FEE_AMOUNT` | comissão do Mercado Pago, com impostos | movimento `tarifa` |
| `BALANCE_AMOUNT` | saldo depois da transação | `SaldoNoProvedor` |
| `TRANSACTION_DATE` e `TRANSACTION_APPROVAL_DATE` | criação e aprovação | `ocorrido_em` |
| `TAXES_AMOUNT` e `TAX_DETAIL` | impostos retidos | movimento `outro` (decisão pendente, E16) |

**No relatório "Dinheiro em conta"**, os tipos de transação documentados incluem `SETTLEMENT` (aprovado), `REFUND`, `CHARGEBACK`, `DISPUTE`, `WITHDRAWAL`, `CASHBACK` e variantes de `SHIPPING`.

**Tradução para o modelo interno** (E09-02):

| Mercado Pago | Movimento interno |
|---|---|
| `payment` / `SETTLEMENT` | `pagamento` (bruto) mais `tarifa` (`MP_FEE_AMOUNT`), com o mesmo `liberado_em` |
| `refund` / `REFUND` | `devolucao` |
| `payout` / `WITHDRAWAL` | `saida`; o `SOURCE_ID` é a identificação que o administrador registra |
| depósito de recursos próprios (aporte) | `deposito`; o rótulo está **a confirmar** (L-9) |
| `chargeback`, `dispute`, `shipping`, `tax_withdholding` e outros | `outro`, com o rótulo em `descricao_no_provedor` |

**Padrões que o simulador reproduz** (E09-02):

- O saldo tem `referente_a`: o instante a que se refere. No Mercado Pago, é o fim do período do relatório. No simulador, é agora.
- Um relatório ainda não pronto conta como indisponível (`ProvedorIndisponivel`), e quem chama tenta de novo depois.
- A tarifa sai do valor do pagamento e é liberada junto com ele.
- A liberação varia por meio de pagamento.

## 10. Diferenças conhecidas entre o simulador e o Mercado Pago

| Ponto | Mercado Pago | Simulador | Por que fica assim |
|---|---|---|---|
| Identificador do pagamento | número (`5466310457`) | `sim-<n>` | a interface trata o id como texto opaco; nenhum código pode depender do formato |
| Corpo e assinatura do aviso | JSON do Mercado Pago; HMAC sobre `id;request-id;ts` com `x-signature` | JSON próprio (`id_evento`, `tipo`, `id_externo`); HMAC SHA256 sobre o corpo, num cabeçalho próprio | a verificação é da implementação do protocolo (`verificar_aviso`); o resto do sistema só vê `AvisoDoProvedor` |
| Cancelar pagamento terminal | erro `2018` | devolve o estado atual | o contrato interno é devolver o estado; a tradução converte o `2018` |
| Vencimento do Pix | de 30 minutos a 30 dias | qualquer instante futuro | **possível alinhamento**: o simulador poderia recusar vencimento fora da faixa, e a criação perto do prazo usaria `max(T0 + 24h, emissão + 30 min)`; mudaria a E08-03, por isso só com especificação |
| Estados intermediários | `in_process` e `authorized` | não existem | a tradução os junta em `pendente` |
| Reembolso e contestação no `status` | `refunded` e `charged_back` | não existem | o sistema mantém `aprovado` e registra à parte (E10) |
| Saldo | por relatório assíncrono | instantâneo, com `referente_a = agora` | o sistema já compara pelo `referente_a` (E09-07) |
| Paginação da busca | `paging` | lista inteira | é responsabilidade da tradução |
| Reenvio do aviso | a cada 15 minutos, sem limite documentado | os testes decidem quando e quantas vezes | o simulador cobre repetido, atrasado e perdido |

## 11. Pontos a validar no sandbox (fase 0)

| Ponto | Limitação |
|---|---|
| Vencimento do Pix perto de `T0 + 24h` e a faixa de 30 minutos a 30 dias | L-1 |
| Cancelamento concorrente com o pagamento e o erro `2018` | L-2 |
| Pix aprovado depois do vencimento, e como aparece | L-3 |
| Precisão e fuso de `date_approved` | L-4 |
| Busca por `external_reference` e atraso de consistência | L-6 |
| Reembolso: parcial, prazo, saldo, tarifa e códigos definitivos | L-7 |
| Saídas da conta nos relatórios | L-8 |
| Saldo e movimentos por relatório; rótulo do depósito de recursos próprios | L-9 |
| `money_release_date` por meio | L-10 |
| Texto assinado do `x-signature` e política de reenvio | L-11 |
| Retenção de imposto, devolução forçada do Pix (MED) e escolha entre Payments, Preferences e Orders API | milestone E16 |

## Fontes

- [Referência da API](https://www.mercadopago.com.br/developers/pt/reference)
- [Obter pagamento](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/get-payment/get)
- [Buscar pagamentos](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/search-payments/get)
- [Criar pagamento](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/create-payment/post)
- [Cancelamento](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/create-cancellation/put)
- [Reembolso](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/create-refund/post)
- [Integrar Pix](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/integration-configuration/integrate-pix)
- [Situações do pagamento](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/response-handling/collection-results)
- [Webhooks](https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks)
- [Webhooks, versão em espanhol, com o modelo de assinatura](https://www.mercadopago.com/developers/es/docs/your-integrations/notifications/webhooks)
- [Relatórios](https://www.mercadopago.com.br/developers/pt/reference/reports/overview)
- [Campos do relatório de liberações](https://www.mercadopago.com.br/developers/en/docs/reports/released-money/report-fields)
- [Relatório Dinheiro em conta](https://www.mercadopago.com.br/developers/pt/docs/reports/account-money/how-to-use.md)
