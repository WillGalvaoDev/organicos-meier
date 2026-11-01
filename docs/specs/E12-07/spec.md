# E12-07 — Cancelamento de ponta a ponta com o simulador

Fatia 7 de 7 da milestone **E12 — Cancelamento da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E12-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E12-01.

## Contexto e objetivo

A fase 1 exige que o simulador reproduza o cancelamento da rodada durante a margem e depois do repasse, com pagamento chegando depois do cancelamento (infraestrutura 7). O repasse é da E13. Aqui, "depois do repasse" é coberto até onde o projeto chega hoje: depois da aprovação do resultado, com a custódia já movida para a obrigação com o fornecedor. O caso com repasse registrado fica herdado para a E13.

Esta fatia não cria comportamento novo. Ela exercita, pelo caminho real (telas, serviço, chamadas ao provedor, simulador e tarefas), os cenários 41 a 46, 51, 91 e 114 e os testes técnicos T-13 a T-16 e T-19. Também confere os invariantes financeiros de ponta a ponta.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 7, fase 1 | O simulador reproduz o cancelamento da rodada durante a margem e depois do repasse, com pagamento chegando depois do cancelamento. Critério de saída: os cenários 1 a 119 e T-1 a T-55 contra o simulador. |
| Infraestrutura 8 | T-13, T-14, T-15, T-16 e T-19. |
| Especificação §16 | Cenários 41 a 46, 51, 91 e 114. |
| Infraestrutura 3.1 | Invariante financeiro verificado periodicamente (E09-03). |

## Escopo

**Dentro:** os cenários de ponta a ponta abaixo, com o simulador, as chamadas pendentes processadas pelo executor real e a verificação do invariante (`verificar_invariante_agora`) ao fim de cada um.

**Fora:**
- O cancelamento com repasse registrado: herdado para a E13, que acrescenta o cenário quando o repasse existir.
- O cancelamento em `disponivel_para_retirada` (decisão em aberto da E12-01).

## Cenários de ponta a ponta

1. **Cancelamento com reembolso durante a margem** (cenários 41, 43, 46, 51; T-19):
   - **arranjo:** AP com X pago e Y com uma cobrança pendente, relógio em `T0 + 30h`;
   - **ação:** o administrador cancela pela tela, com reembolso;
   - **esperado:** X devolvido de ponta a ponta, com o estorno concluído no simulador; a cobrança de Y cancelada pela chamada; o invariante sem violação;
   - **depois:** a cobrança de Y aprovada no simulador antes de o cancelamento ser processado (cancelamento coincidindo com o pagamento) gera a devolução de destino e o alerta crítico, sem alterar Y.
2. **Cancelamento sem reembolso com obrigação existente** (cenário 44; T-15):
   - **arranjo:** AP-viável apurada, com um pagamento de Y aprovado depois de `T0 + 48h` (obrigação de destino pendente);
   - **ação:** o cancelamento sem reembolso;
   - **esperado:** a obrigação continua pendente; depois, autorizada pelo administrador na tela da E10, é executada normalmente.
3. **Cancelamento depois da aprovação do resultado** (cenários 43, 45, 91):
   - **arranjo:** AP-viável apurada e aprovada (`aguardando_fornecedor`), com a tarifa de X registrada;
   - **ação:** o cancelamento com reembolso;
   - **esperado:**
     - a obrigação financiada pelas destinações da rodada depois da apuração;
     - o que faltar fica sem cobertura e é coberto pelo administrador;
     - a tarefa autoriza, o estorno conclui e a conciliação do dia não aponta divergência;
     - a `ApuracaoNoLivro` e os registros anteriores ficam intactos.
4. **Reembolso parcial anterior** (cenários 114, 91; T-14):
   - **arranjo:** um pedido pago com o item de 7,99/kg × 1 kg, com uma devolução parcial de 0,25 kg (2,00) já concluída no simulador;
   - **ação:** o cancelamento com reembolso;
   - **esperado:** o item devolve 5,99 e o total devolvido do pedido é exatamente o pago.
5. **Dois cancelamentos em paralelo** (T-13), com transações reais:
   - **ação:** os dois POST da tela, ou os dois serviços, ao mesmo tempo;
   - **esperado:** um cancela e o outro recebe `ja_cancelada`; uma parcela de devolução por pedido no simulador.
6. **Rota e permissões** (T-16, cenário 42): pelo cliente HTTP, a lista de compradores recusada, a requisição sem motivo aceita, comprador e fornecedor recusados.
7. **Nova rodada depois do cancelamento** (cenários 41, 45):
   - **ação:** abrir uma rodada nova do fornecedor;
   - **esperado:** a fila atendida pela E05; os pedidos e reembolsos da rodada cancelada consultáveis e inalterados.

## Regras

- Cada cenário roda contra o simulador, sem dublê do provedor, salvo o controle explícito de falhas dele (`falhar_proximas`).
- Ao fim de cada cenário: `verificar_invariante_agora()` sem alerta `invariante_violado`. Para cada pedido pago: a soma dos estornos concluídos no simulador é igual à soma dos reembolsos liquidados e nunca maior que o pago.

## Dependências e decisões em aberto

- Depende das E12-01 a E12-06. Nenhuma decisão em aberto.
- **Herdado para a E13:** o cenário "cancelamento depois do repasse", com a obrigação de devolução financiada depois do repasse (receita de serviço, reserva ou aporte; infraestrutura 3.2), e a recusa do pedido formal numa rodada cancelada.
