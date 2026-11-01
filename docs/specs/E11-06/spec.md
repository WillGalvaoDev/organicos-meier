# E11-06 — Aprovação do resultado e avanço para aguardando fornecedor

Fatia 6 de 8 da milestone **E11 — Apuração final e fila de pendentes**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E11-01.

## Contexto e objetivo

Com o resultado `valida` (E11-03 e E11-04), a rodada espera em `pagamento` a decisão do administrador (§8.2, passo 3.6). Ao aprovar o resultado, a rodada passa a "aguardando fornecedor" (§7), e o livro-razão registra a apuração final aprovada (infraestrutura 3.2):
- a custódia dos pedidos válidos vai para a obrigação com o fornecedor, a receita de serviço e o frete;
- o frete atribuído aos inadimplentes vira déficit do administrador (§8.2, P-1).

Antes da aprovação, o sistema reconsulta o provedor (infraestrutura 4.4).

Esta fatia entrega o serviço `aprovar_resultado` e o sinal do avanço. A E13 usa esse sinal para enviar o pedido formal.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | Aguardando fornecedor: o resultado válido da cobrança é aprovado pelo administrador, e o pedido formal é enviado automaticamente. O encerramento automático dos prazos não autoriza uma nova etapa. Toda intervenção auditada. |
| Especificação §8.2, passo 3.6 e frete | Mínimo atendido: resultado ao administrador para avanço e autorizações financeiras necessárias. O administrador assume o frete dos inadimplentes como déficit, sem aumentar o frete de quem pagou. |
| P-1 | Déficit de frete do administrador, sem cobrança retroativa. |
| Infraestrutura 3.1 e 3.2 | "Apuração final aprovada": custódia → obrigações com fornecedores, frete arrecadado e receita de serviço. Déficit = frete efetivo − frete arrecadado líquido. |
| Infraestrutura 4.4 | A nova consulta antes da autorização de avanço é uma das mitigações do pagamento informado depois da apuração. |
| Herdado da E09 | A apuração autorizada chama `registrar_apuracao_no_livro(ciclo, pedidos_validos)` (E09-06), que move a custódia, registra o frete efetivo e o déficit e cobre as tarifas. |
| Herdado da E07 | Decisões financeiras chamam `consultar_antes_de_decidir` e ficam bloqueadas com `ConsultaAoProvedorFalhou`. |
| Cenários §16 | 14 |

## Escopo

**Dentro:**
- O registro `AprovacaoDoResultado`.
- O serviço `aprovar_resultado(autor, rodada)`.
- O sinal `resultado_aprovado`.

**Fora:**
- O pedido formal e o envio por e-mail (E13).
- O repasse (E13).
- As autorizações das devoluções, que são independentes do avanço (E10).

## Modelo

**`AprovacaoDoResultado`** (só inserção): `apuracao` (um para um, única), `autor`, `aprovada_em`.

## Regras

**`aprovar_resultado(autor, rodada) -> AprovacaoDoResultado`**

1. **Autor:** administrador. Senão, `PermissionDenied`.
2. **Só fora de transação,** pelo mesmo motivo e com a mesma guarda da `iniciar_apuracao` (E11-01): `RuntimeError` antes de qualquer consulta.
3. **Conferência prévia, sem travas:** a rodada está em `pagamento`, e o ciclo vigente tem `ApuracaoFinal` com `resultado = valida` e sem `AprovacaoDoResultado`. Senão, `ApuracaoRecusada`, sem consulta.
4. **Nova consulta:** `consultar_antes_de_decidir` para a referência de cada pedido da abertura, na ordem de `pk`. Uma `ConsultaAoProvedorFalhou` bloqueia o avanço, sem escrita. Um pagamento descoberto agora segue as regras da E11-01:
   - devolução integral;
   - alerta crítico quando teria quitado pela P-6;
   - nenhuma mudança no pedido apurado.

   O avanço continua, porque o resultado não é refeito (§7.1, §8.3).
5. **Decisão, numa transação:**
   - **travas:** o fornecedor e a rodada; depois, o que `registrar_apuracao_no_livro` trava (as contas, pela regra única da E09);
   - **releitura:** as conferências do passo 3, sob as travas;
   - **pedidos válidos:** os pedidos pagos do ciclo com ao menos uma unidade fora das caixas invalidadas, por `pk`. Um pedido pago com todas as unidades invalidadas não é válido: a custódia dele já financiou os reembolsos da E11-04 e está zerada;
   - `registrar_apuracao_no_livro(ciclo, pedidos_validos, autor=autor)` (E09-06), que:
     - move os saldos atuais da custódia (o pago menos o que financiou os reembolsos);
     - registra o frete efetivo (`abertura.frete`) e o arrecadado;
     - abre a despesa de déficit;
     - cobre as tarifas pendentes da rodada;
   - a etapa da rodada passa a `aguardando_fornecedor`;
   - grava a `AprovacaoDoResultado`;
   - grava a auditoria `rodada.aprovar_resultado` com a apuração, os pedidos válidos, o frete efetivo, o arrecadado e o déficit;
   - emite o sinal `resultado_aprovado(rodada, ciclo, apuracao)` na transação, sem receptor nesta etapa. Quem enviar o pedido formal (E13) agenda o envio a partir dele.

**Recusas (`ApuracaoRecusada`), além das da E11-01:**

| Código | Mensagem |
|---|---|
| `sem_apuracao` | "A apuração deste ciclo ainda não foi feita." |
| `resultado_nao_valido` | "Só um resultado válido pode ser aprovado." |
| `ja_aprovado` | "O resultado desta apuração já foi aprovado." |
| `fora_de_pagamento` | a da E11-01 (por exemplo, a rodada já voltou para interesse ou já avançou) |

## Decisões técnicas

- **O livro só recebe a apuração na aprovação, e não no início.** A infraestrutura 3.2 associa o lançamento à "apuração final aprovada".
  - Entre o início e a aprovação, os reembolsos de caixa invalidada são financiados pela custódia, como devolução antes da apuração (E09-06).
  - O que sobra na custódia vai para as destinações na aprovação.
- **A autorização das devoluções não condiciona o avanço.** O §8.2 fala em "avanço e autorizações financeiras necessárias", mas a E10 já separa a autorização de cada devolução. Uma devolução não autorizada continua pendente e financiada.

## Invariantes

- Uma `AprovacaoDoResultado` por apuração, e só para resultado `valida`.
- Depois da aprovação, a custódia dos pedidos válidos do ciclo fica zerada (E09-06).
- O déficit de frete é exatamente o frete efetivo menos o arrecadado líquido, e nenhum pedido pago é recalculado (P-1, cenário 14).

## Casos-limite e concorrência

- **Duas aprovações em paralelo:** uma aprova; a outra recebe `ja_aprovado` depois das travas, sem escrita.
- **Aprovação com uma devolução de caixa invalidada já autorizada e concluída:** a custódia já foi financiada na criação da obrigação. A liquidação não muda o saldo da custódia, e a aprovação move o mesmo valor.
- **Resultado válido com zero pedidos válidos** (mínimo zero): `registrar_apuracao_no_livro` com lista vazia. O frete efetivo inteiro vira déficit (E09-06).

## Dependências e decisões em aberto

Depende de E11-04 e E09-06. Nenhuma decisão em aberto. O pedido formal é da E13.
