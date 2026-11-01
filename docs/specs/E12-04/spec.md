# E12-04 — Pagamento informado depois do cancelamento

Fatia 4 de 7 da milestone **E12 — Cancelamento da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E12-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E12-01.

## Contexto e objetivo

Depois do cancelamento, uma cobrança que estava pendente pode ser aprovada no provedor, ou uma aprovação anterior pode só chegar agora. O cancelamento no provedor é assíncrono e o provedor pode atrasar a informação (E12-02, L-2, L-6).

Esse pagamento é registrado e tratado financeiramente com auditoria, como em §8.3, sem alterar pedidos (§7.2). A infraestrutura 4.8 acrescenta que ele gera alerta. Esta fatia estende a regra de destino da E08-04 e o registro no livro da E09-04 para esse caso.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7.2 | Um pagamento aprovado depois do cancelamento é registrado e tratado financeiramente com auditoria, como em 8.3, sem alterar pedidos. |
| Especificação §8.3 | Nunca ignorar dinheiro recebido. Cada pagamento é reconhecido uma única vez. Pagamentos tardios não editam pedidos e geram obrigação de devolução. |
| Infraestrutura 4.8 | Pagamento aprovado depois do cancelamento: registrado, gera alerta e recebe tratamento financeiro auditado pelos mecanismos existentes, sem alterar pedidos. |
| Infraestrutura 3.2 | Pagamento que não quita: obrigação de devolução integral financiada pelo próprio pagamento. |
| Herdado da E08 | Pagamento aprovado depois do cancelamento vai para devolução pela regra de destino da E08-04, que a E12 estende. A exceção "aprovado antes do cancelamento quita" vale só para `suspensao` e `remocao_da_conta`. |
| Cenários §16 | 51 |
| Testes técnicos | T-19 (parte do cancelamento) |

## Escopo

**Dentro:**
- O destino `devolucao` de todo pagamento de pedido de rodada cancelada que ainda não tem destino.
- O alerta `pagamento_depois_do_cancelamento`.
- A auditoria.

**Fora:**
- A devolução desse pagamento: segue o fluxo da E10 para obrigações de destino, com a autorização do administrador. Ela não é gerada pelo cancelamento e não é autorizada por ele.
- O aviso ao comprador: o `estorno` da E10, quando autorizado.

## Regras

1. **Destino** (`decidir_destino`, E08-04). Um pagamento aprovado de um pedido cuja rodada tem `CancelamentoDaRodada` e que ainda não tem destino nunca quita, qualquer que seja o horário de aprovação. O motivo é escolhido na ordem que já existe:
   - `valor_divergente`, `iniciado_fora_do_prazo` e `aprovado_apos_a_margem`: como hoje;
   - `duplicidade`, se o pedido está `pago`;
   - `pedido_cancelado` nos demais casos. Isso inclui o pedido cancelado com o motivo `cancelamento_da_rodada`, mesmo com a aprovação anterior a `cancelado_em`: esse motivo entra ao lado de `inadimplencia` entre os cancelamentos que nenhum pagamento desfaz.
2. **Sem alteração de pedido:** a situação, o motivo e o `cancelado_em` do pedido não mudam. Nenhum `Pedido`, item ou parcela muda.
3. **Livro:** a entrada para devolução da E09-04, com a obrigação integral do valor do pagamento, financiada pelo próprio pagamento. Os alertas que já existem continuam:
   - `aprovado_apos_a_margem` e `duplicidade`;
   - `aprovado_no_prazo_depois_da_apuracao`, quando o ciclo foi apurado e o pagamento teria quitado.
4. **Alerta `pagamento_depois_do_cancelamento`** (novo tipo, gravidade **crítica**). Abre quando a obrigação da entrada para devolução nasce para um pagamento de pedido de rodada cancelada.
   - **Chave:** o `id_externo` do pagamento. Abre uma vez por pagamento; repetir o registro não o reabre depois de resolvido.
   - **Dados:** pagamento, pedido, comprador, valor, `aprovado_em` e `cancelada_em`.
   - **Convivência:** vale ao lado dos alertas da regra 3, que registram outros fatos do mesmo pagamento.
5. **Auditoria:** a do destino (`pagamento.destino`, E08-04), com o motivo.

## Decisões técnicas

- **Nunca quita, mesmo aprovado antes do cancelamento.** Quitar agora mudaria a situação de um pedido de uma rodada cancelada. Com reembolso, ainda exigiria uma devolução que o cancelamento não gerou. A devolução integral pelo próprio pagamento devolve o mesmo valor e não altera o pedido (§7.2: "sem alterar pedidos"). Com "sem reembolso", o pedido estava não pago no cancelamento e foi cancelado; o dinheiro recebido depois não é ignorado (§8.3) e volta ao comprador.
- **Gravidade crítica.** É dinheiro recebido numa rodada encerrada administrativamente, que exige ação do administrador na devolução. É o mesmo nível do pagamento informado depois da apuração (infraestrutura 4.4).
- **A devolução não é autorizada pela indicação "com reembolso".** A indicação autoriza as devoluções geradas pelo cancelamento (§7.2). Esta nasce de um pagamento posterior, pelo fluxo de destino, e segue a autorização da E10, como as demais devoluções de destino.

## Invariantes

- Nenhum pagamento quita um pedido de rodada cancelada depois do cancelamento.
- Cada pagamento tem no máximo um destino (E08-04) e uma obrigação de destino (E09-04).

## Casos-limite e concorrência

- **Aviso processado em paralelo ao cancelamento:** como na E12-02.
  - Se o aviso trava a situação antes, o pagamento quita, e o pedido entra no cancelamento como pago.
  - Se o cancelamento trava antes, vale esta fatia.
- **Aviso repetido ou fora de ordem:** o destino existente é devolvido; nenhuma obrigação nem alerta novo.
- **Pagamento de pedido cancelado antes, por inadimplência ou suspensão, numa rodada depois cancelada:** a regra 1 vale (`pedido_cancelado`), e o alerta abre.

## Dependências e decisões em aberto

Depende da E12-02, da E08-04 e da E09-04. Nenhuma decisão em aberto.
