# E05-07 — Remoção dos interesses do comprador suspenso ou removido

Fatia 7 de 7 da milestone **E05 — Interesses, reservas e progresso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A suspensão de um comprador remove os interesses dele (§2, cenário 19). A E02-08 deixou o sinal `conta_suspensa`, enviado dentro da transação da suspensão, para que esse efeito seja atômico com ela.

Esta fatia conecta o receptor. Ele faz três coisas na mesma transação:

- remove as parcelas `ativa` e `pendente` do comprador;
- libera as reservas;
- atende a fila de pendentes dos produtos liberados.

A remoção da conta tem o mesmo efeito sobre os interesses, por decisão do responsável (D-1, de 2026-10-18). Um segundo receptor, ligado ao sinal `conta_removida` da E02-08, usa a mesma função.

O cancelamento de pedidos não pagos, do suspenso e do removido, é da E08.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Suspenso: não adiciona interesses; interesses e pedidos não pagos são removidos ou cancelados; suspensão reversível. |
| Especificação §5 | Remoção libera a reserva quando a rodada continua utilizável. |
| Especificação §5.2 | Sempre que estoque é liberado, as pendentes são atendidas primeiro. |
| Cenários §16 | 19 (parte dos interesses): a suspensão esvazia os interesses, e a reversão não os restaura. |
| Especificação §2, comprador removido | Acesso bloqueado definitivamente; histórico, inclusive financeiro, preservado; pedidos pagos não são apagados. Sobre interesses, a seção não diz nada. |
| D-1, decisão do responsável em 2026-10-18 | Os interesses da conta removida recebem o mesmo tratamento da suspensão (opção a). |
| E02-08 | `conta_suspensa` e `conta_removida`, ambos com o argumento `conta` e enviados dentro da transação de `suspender` e de `remover`, com a conta já travada. `reativar` não restaura nada. `remover` aceita comprador ou fornecedor, `ativa` ou `suspensa`. |
| Milestone E05, herdado da E02 | Remoção dos interesses do suspenso conectada a `conta_suspensa` na mesma transação. |
| E05-01, E05-02 | Ordem de travas e `_alocar_produto`. |

## Escopo

**Dentro:**

- Os receptores de `conta_suspensa` e `conta_removida` em `apps.interesses`, com a função `remover_interesses_do_comprador(conta, *, motivo)`.

**Fora:**

- Pedidos não pagos do suspenso e do removido (E08).

## Decisões técnicas

- **Remoção completa.** As parcelas `ativa` e `pendente` do comprador passam a `removida`, com reservado e pendente zero.
  - Isso inclui as pendentes da fila. A §2 manda remover os interesses, e pendente é interesse sem reserva.
  - As parcelas `em_pedido` não mudam: elas pertencem a pedidos (E08).
- **Em qualquer etapa.** A remoção não depende da etapa da rodada. Ela usa a ordem global de travas sem exigir etapa, como a remoção de pendentes (E05-03).
  - A conta já vem travada por `suspender`.
  - Os fornecedores são travados em ordem de id.
  - Para cada fornecedor: a rodada ativa, se houver; os produtos afetados, por id; o estoque de cada produto na rodada, se houver; e as parcelas, com `travar_parcelas(produto)` (E05-01).
- **Fila depois da liberação.** Para cada produto com reserva liberada, `_alocar_produto(rodada, produto)` roda quando a rodada aceita reservas (`interesse` ou `fechamento`). Nas outras etapas, a reserva só é liberada (§5, "quando a rodada continuar utilizável").
- **Auditoria:** a ação depende do motivo, `interesse.remover_por_suspensao` ou `interesse.remover_por_remocao_da_conta`. A entrada tem autor `SISTEMA`, a conta e `{"parcelas": [[id, reservado anterior, pendente anterior], ...]}`. Sem parcelas a remover, não há auditoria.
- **Remoção de conta já suspensa:** a suspensão já removeu os interesses, então a função não encontra parcelas, devolve 0 e não audita. O receptor não precisa distinguir esse caso.
- **Remoção de conta de fornecedor:** contas de fornecedor não têm parcelas (§2, fornecedor não compra). O receptor devolve sem fazer nada quando o papel não é `comprador` e não trava nada além do que `remover` já travou.

## Regras

```
remover_interesses_do_comprador(conta, *, motivo) -> int
```

Fica em `apps/interesses/servicos.py`. `motivo` vale `"suspensao"` ou `"remocao_da_conta"` e só escolhe a ação da auditoria. Qualquer outro valor levanta `ValueError`.

- Exige transação aberta. Fora dela, levanta `TransactionManagementError`.
- Executa as travas da decisão técnica e marca como `removida` cada parcela `ativa` ou `pendente` da conta.
- Executa `_alocar_produto` onde couber.
- Devolve o número de parcelas removidas.
- Não envia notificação ao comprador: a §12 não lista evento para a suspensão.

**Receptores** (conectados no `ready()` de `apps.interesses`):

- **`conta_suspensa`:** chama `remover_interesses_do_comprador(conta, motivo="suspensao")` dentro da transação de `suspender`.
- **`conta_removida`:** quando o papel da conta é `comprador`, chama `remover_interesses_do_comprador(conta, motivo="remocao_da_conta")` dentro da transação de `remover`.
- **Falha:** uma falha no receptor desfaz a suspensão ou a remoção inteira, inclusive o banimento do e-mail e o encerramento das sessões. É o comportamento definido pela E02-08.

**Reversão:** `reativar` não restaura parcelas (cenário 19). Depois da reativação, o comprador pode adicionar interesses novos, que recebem sequências novas.

## D-1 — Conta removida (decidida em 2026-10-18)

| Item | Conteúdo |
|---|---|
| Referência | Especificação §2 (comprador removido) e cenário 20; E02-08, sinal `conta_removida` |
| Ambiguidade | A §2 manda remover os interesses do **suspenso**, mas não diz o que acontece com os interesses do **removido**. O removido não entra mais no sistema, então não pode reduzir interesses nem pagar. |
| Impacto da alternativa recusada | Se os interesses ficassem, as reservas seguiriam segurando estoque, contariam para o mínimo e entrariam no pedido da abertura do pagamento. Lá, o removido ficaria inadimplente com certeza e poderia invalidar caixas de compradores adimplentes (§8.2). |
| Decisão | **Opção (a):** os interesses da conta removida recebem o mesmo tratamento da suspensão, pelo receptor de `conta_removida` desta fatia. A opção (b), que mantinha os interesses até a apuração, foi recusada. |
| O que não muda | Parcelas `em_pedido`, pedidos pagos e histórico, inclusive financeiro, ficam preservados (§2, cenário 20). As parcelas removidas continuam gravadas, com a auditoria do que foi removido. |
| Ponto relacionado, fora desta fatia | O destino de um pedido **não pago** de conta removida, durante o prazo de pagamento, é da E08. A D-1 decide só os interesses. A E08 deve tratar esse pedido explicitamente e levar a pergunta ao responsável se ela não puder ser deduzida. |

## Interfaces

- `apps/interesses/servicos.py`: `remover_interesses_do_comprador`.
- `apps/interesses/apps.py`: a conexão do receptor.

## Invariantes

- Depois da suspensão ou da remoção confirmada, o comprador não tem parcela `ativa` nem `pendente`.
- A suspensão ou a remoção da conta e a remoção dos interesses são atômicas.
- Reserva liberada é oferecida primeiro à fila de pendentes, quando a rodada aceita reservas.

## Casos-limite e concorrência

- **Cenário 19 (interesses):** A tem interesses em dois fornecedores. Depois da suspensão, nenhum interesse de A continua ativo, e o estoque fica livre. A reativação não restaura nada.
- **Pendente de outro comprador:** C tem 3 pendentes no produto que A liberou. C recebe 3, na mesma transação da suspensão.
- **Rodada em `fechamento_encerrado`:** a parcela de A é removida e a reserva liberada, sem atendimento da fila.
- **Adição em paralelo com a suspensão:** se a adição confirma antes, a suspensão remove a parcela nova. Se a suspensão confirma antes, a adição é recusada, porque as duas travam a conta primeiro (E05-01, A-15).
- **Atendimento da fila em paralelo com a suspensão de quem tem pendente:** os dois se serializam pela trava do fornecedor.
  - Se o atendimento vem antes, a parcela atendida é removida pela suspensão, e a reserva volta para a fila.
  - Se a suspensão vem antes, a parcela já está `removida` e não é atendida.
- **Conta removida:** as mesmas regras e os mesmos casos da suspensão. A diferença é que não há reversão, porque a remoção é definitiva.
- **Remoção de conta suspensa:** nada a remover. Os interesses já saíram na suspensão.

## Correção E05-R03 — suspensão e remoção em paralelo com alteração de preço (2026-10-18)

O diagnóstico e a regra estão na correção E05-R03 da E05-01. Nesta fatia, a mudança é esta:

- `_travar` em `apps/contas/moderacao.py` passa a travar a conta com `select_for_update(no_key=True)`. Isso vale para `suspender`, `reativar` e `remover`.
- O `UPDATE` da situação continua restrito a `situacao` (`update_fields`).
- O resto da moderação não muda: a revalidação depois da trava, a auditoria, o banimento do e-mail, o encerramento das sessões e os sinais na mesma transação.
- A serialização entre moderação e operações de interesse continua pela conta, porque `FOR NO KEY UPDATE` conflita com `FOR NO KEY UPDATE`. A-8 e A-14 continuam valendo sem mudança.
- A alteração de preço que avisa o comprador durante a suspensão ou a remoção dele termina normalmente. O aviso fica gravado, mesmo que a conta acabe suspensa ou removida: a notificação é histórico da conta (E04-01).

## Dependências e decisões em aberto

- Depende de E02-08, E05-01 e E05-02.
- Sem decisões em aberto. A D-1 foi decidida em 2026-10-18 (opção a).
