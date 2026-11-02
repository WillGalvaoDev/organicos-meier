# E12-01 — Cancelamento da rodada: o serviço e o efeito nos interesses

Fatia 1 de 7 da milestone **E12 — Cancelamento da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7 (29/10/2026).
- Infraestrutura: v1.8 (29/10/2026), com base na especificação v1.7.
- A descrição da milestone 12 cita a base v1.6/v1.7. As seções usadas aqui (§7, §7.1, §7.2, §12, §13, §16 e 17.2 da especificação; 3.2, 4.2, 4.7 e 4.8 da infraestrutura) não mudaram nas versões v1.7/v1.8: as alterações dessas versões são a Q-8 (contestação, §9.6). A base vigente é v1.7/v1.8, e a milestone é atualizada no fechamento.
- Gate de especificação: feito pelo especificador, por decisão do responsável (descrição da milestone).

## Divisão da E12

| Fatia | Objetivo |
|---|---|
| E12-01 | O registro do cancelamento, o serviço `cancelar_rodada`, as recusas, as travas e o efeito nos interesses, nas etapas antes do pagamento |
| E12-02 | O cancelamento com pedidos (etapa `pagamento` e `aguardando_fornecedor`): pedidos não pagos cancelados, novas tentativas bloqueadas, cobranças pendentes canceladas no provedor, apuração e aprovação recusadas; o caso "sem reembolso" |
| E12-03 | O cancelamento com reembolso: consulta prévia ao provedor, devolução integral de cada pedido pago (descontado o já devolvido ou pendente), já autorizada, e a autorização automática |
| E12-04 | O pagamento informado depois do cancelamento: devolução integral, alerta, nenhum pedido alterado |
| E12-05 | O aviso `rodada_cancelada` aos compradores |
| E12-06 | As telas: a ação do administrador com nova autenticação, a rota que recusa lista de compradores, e o que administrador e comprador veem depois |
| E12-07 | Ponta a ponta com o simulador: cancelamento durante a margem e depois da aprovação do resultado, corridas reais e os cenários da §16 |

Ordem de implementação: E12-01 → E12-02 → E12-03 → E12-04 → E12-05 → E12-06 → E12-07. Cada fatia depende das anteriores.

## Contexto e objetivo

O administrador pode cancelar a rodada inteira por decisão própria, sem motivo, indicando se existe reembolso devido (§7.2, 17.2). O cancelamento afeta todos os compradores da rodada, remove os interesses e nunca apaga registros financeiros.

Esta fatia entrega o núcleo comum: o registro `CancelamentoDaRodada`, o serviço `cancelar_rodada`, as recusas, a ordem de travas e o efeito nos interesses e nas reservas. Nas etapas antes do pagamento (`interesse`, `fechamento` e `fechamento_encerrado`) não há pedido nem dinheiro. Nelas, "com reembolso" e "sem reembolso" têm o mesmo efeito, porque ninguém pagou. As fatias seguintes acrescentam ao mesmo serviço o efeito nos pedidos (E12-02), o reembolso (E12-03) e o aviso (E12-05).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | "Cancelada: administrador cancela a rodada inteira por decisão própria, sem informar motivo, e indica se existe reembolso devido. Interesses são removidos. Valores pagos exigem tratamento financeiro, nunca simples exclusão." Toda intervenção auditada; nenhuma intervenção reescreve pagamentos, apaga histórico ou cobra valor adicional. |
| Especificação §7.2 | Só o administrador; afeta todos os compradores; sem motivo nem informação sobre o fornecedor; com ou sem reembolso; obrigações existentes preservadas; registros anteriores preservados; novas tentativas bloqueadas. |
| Especificação §5.2 | A remoção de pendentes vale em qualquer fase, porque as quantidades pendentes não fazem parte de nenhum ciclo. A fila de um fornecedor só é atendida pelas rodadas dele. |
| Especificação §14 | Rodada cancelada: autor, momento e indicação de reembolso devido. A auditoria do cancelamento não exige motivo. |
| Infraestrutura 4.8 | Uma ação, uma rodada; só a rodada e a indicação (sim ou não); sem lista de compradores, motivo ou informação do fornecedor; mensagem opcional. Admin verificado no servidor, com nova autenticação (proteção de acesso). Numa transação com a rodada travada: auditoria; remoção de interesses e liberação das reservas; bloqueio de tentativas; obrigações com reembolso. Cancelar rodada já cancelada é recusado. |
| Herdado da E05 | O cancelamento remove os interesses da rodada (parcelas `ativa` e as reservas). Os pendentes da fila do fornecedor, que não pertencem a nenhum ciclo, continuam na fila. |
| E03-02 | Rodada `cancelada` não é ativa: uma nova rodada do fornecedor pode ser aberta. |
| Cenários §16 | 41, 42, 45 |
| Testes técnicos | T-13 (parte da recusa da repetição), T-16 (parte do serviço) |

## Escopo

**Dentro:**
- O modelo `CancelamentoDaRodada`.
- O serviço `cancelar_rodada(autor, rodada, *, com_reembolso, mensagem="")` e a exceção `CancelamentoRecusado`.
- As recusas, a ordem de travas e a auditoria `rodada.cancelar`.
- O efeito nos interesses: reservas zeradas, parcelas removidas, pendentes preservados.
- A etapa `cancelada` e o fim do ciclo vigente para as operações de interesse e de fechamento.

**Fora:**
- Pedidos, tentativas e cobranças (E12-02).
- O reembolso (E12-03).
- O aviso aos compradores (E12-05; nesta fatia nenhum aviso é emitido).
- As telas e a nova autenticação (E12-06).
- O cancelamento de uma rodada `disponivel_para_retirada` (ver "Dependências e decisões em aberto").

## Modelo

**`CancelamentoDaRodada`** (só inserção, `RegistroSoInsercao`), no app de pedidos, ao lado de `ApuracaoFinal`:
- `rodada`: um para um, único;
- `autor`: a conta do administrador;
- `cancelada_em`: o instante lido depois das travas;
- `com_reembolso`: booleano, sem valor padrão;
- `mensagem`: texto opcional, até 1000 caracteres, vazio por padrão;
- `etapa_anterior`: a etapa da rodada no instante do cancelamento.

## Regras

**`cancelar_rodada(autor, rodada, *, com_reembolso, mensagem="") -> CancelamentoDaRodada`**

1. **Autor:** conta com papel de administrador. Comprador, fornecedor, conta inativa ou `None`: `PermissionDenied`, sem escrita.
2. **Só fora de transação:** a guarda `exigir_fora_de_transacao` (E07-06). Dentro de uma transação aberta: `RuntimeError`, sem escrita. O motivo é a consulta prévia ao provedor e a autorização das devoluções depois do commit (E12-03), que valem para as duas indicações pelo mesmo contrato.
3. **Entrada:**
   - `com_reembolso` precisa ser exatamente `True` ou `False`; qualquer outro valor, inclusive `None`: `CancelamentoRecusado("indicacao_obrigatoria")`;
   - `mensagem`: aparada nas pontas; acima de 1000 caracteres: `CancelamentoRecusado("mensagem_longa")`;
   - o serviço não recebe lista de compradores, motivo nem informação sobre o fornecedor; a assinatura não tem esses parâmetros (T-16).
4. **Conferência prévia, sem travas:** a rodada existe e está numa etapa cancelável. Senão, a recusa da tabela abaixo, sem escrita.
5. **Decisão, numa única transação:**
   - **travas,** na ordem e no modo da apuração (`_travar` da E11-01, com a correção E11-R04: `FOR NO KEY UPDATE`):
     - as contas dos compradores envolvidos, por `pk` (os donos das parcelas não removidas dos produtos do fornecedor e, a partir da E12-02, os compradores dos pedidos da rodada);
     - o fornecedor; a rodada; os produtos do fornecedor, por `pk`; os estoques da rodada; as parcelas não removidas de cada produto, por sequência;
   - **releitura:** o instante (`agora()`) é lido depois das travas; a etapa é conferida de novo sob a trava, com as mesmas recusas;
   - **interesses** (regra 6);
   - a etapa da rodada passa a `cancelada`;
   - grava o `CancelamentoDaRodada`;
   - grava a auditoria `rodada.cancelar` (regra 7).
6. **Efeito nos interesses.** Para cada parcela `ativa` ou `em_pedido` de produto do fornecedor, com ou sem reserva:
   - a reserva vai a zero;
   - a parte pendente, se houver, continua: a parcela passa a `pendente`, com a mesma sequência, a mesma pendência e a mesma quantidade original;
   - sem parte pendente, a parcela passa a `removida`;
   - as parcelas já `pendente` não mudam. Elas são a fila do fornecedor e não pertencem a nenhum ciclo (§5.2, herdado da E05). Esperam a próxima rodada do fornecedor em interesse;
   - nenhuma parcela é criada, e a sequência de nenhuma muda;
   - nenhum atendimento da fila acontece agora: sem rodada ativa, não há estoque a alocar.
7. **Auditoria `rodada.cancelar`,** com o autor e, nos dados:
   - a rodada, a etapa anterior, o instante, a indicação de reembolso e se houve mensagem;
   - por parcela alterada: a parcela, o comprador, a situação anterior e a nova, a reserva anterior e a pendência mantida;
   - as listas das fatias seguintes (pedidos cancelados, cobranças, reembolsos), vazias aqui.

   A mensagem fica no `CancelamentoDaRodada`, e não na auditoria. A auditoria não tem campo de motivo (§14).

**Etapas e recusas (`CancelamentoRecusado(codigo)`, com a mensagem):**

| Etapa ou situação | Resultado |
|---|---|
| `interesse`, `fechamento`, `fechamento_encerrado` | cancela (esta fatia) |
| `pagamento`, em qualquer instante (antes de `T0 + 24h`, na margem, apta para apuração, apurada e não aprovada) | cancela (E12-02 acrescenta os pedidos) |
| `aguardando_fornecedor` | cancela (E12-02) |
| `cancelada` | `ja_cancelada`: "Esta rodada já foi cancelada." |
| `disponivel_para_retirada` | `rodada_encerrada`: "A rodada já foi encerrada e não pode ser cancelada." Ver "Dependências e decisões em aberto" |
| `com_reembolso` inválido | `indicacao_obrigatoria`: "Informe se existe reembolso devido." |
| mensagem acima de 1000 caracteres | `mensagem_longa`: "A mensagem passa de 1000 caracteres." |

**Depois do cancelamento:**
- **Interesses:** a rodada não é ativa. `adicionar_interesse`, `reduzir_interesse` e `definir_interesse` para produtos do fornecedor recebem a recusa que já existe sem rodada ativa (E05).
- **Remoção de pendentes:** `remover_pendente` continua aceita (E05-03, "sem rodada ativa").
- **Fechamento:** `iniciar_fechamento`, `prorrogar_fechamento` e `encerrar_fechamento` recusam ou ignoram a rodada, pela conferência de etapa que já existe (E06). A tarefa de encerramento dos prazos não toca uma rodada cancelada.
- **Condições:** a alteração de mínimo, múltiplo, incremento e estoque é recusada como sem rodada ativa (E03-07).
- **Nova rodada:** `abrir_rodada` para o fornecedor é aceita (E03-02). A rodada nova atende a fila pela regra da E05.
- **Registros:** ciclos, condições, prazos e auditorias anteriores ficam como estavam (§7.2, cenário 45).

## Decisões técnicas

- **Pendentes ficam; a parte reservada sai.** O §7 manda remover os interesses. O §5.2 e o herdado da E05 tiram da regra as quantidades pendentes, que não pertencem a ciclo nenhum. Uma parcela `ativa` com reserva e pendência (E08-02, E11-05) perde só a reserva e vira `pendente`: a parte pendente era fila e continua fila.
- **As mesmas travas da apuração.** O cancelamento concorre com a apuração, a aprovação, as operações de interesse, a moderação e o encerramento do fechamento. Usar a ordem e o modo da E11 (correção E11-R04) evita impasse com eles e com os pagamentos que inserem registros apontando para a rodada.
- **Fora de transação nas duas indicações.** Com reembolso é obrigatório (infraestrutura 4.2). Sem reembolso, a mesma guarda deixa um único contrato para a tela e para os testes.
- **A mensagem é dado do cancelamento, e não motivo.** Ela serve ao aviso (E12-05) e às telas. A auditoria registra só que ela existe.

## Invariantes

- No máximo um `CancelamentoDaRodada` por rodada (restrição única).
- Depois do cancelamento, nenhuma parcela de produto do fornecedor tem reserva: `total_reservado` é zero em todos os produtos da rodada.
- Nenhuma pendência é criada, aumentada ou apagada pelo cancelamento; as sequências não mudam.
- Uma rodada `cancelada` nunca volta a outra etapa.

## Casos-limite e concorrência

- **Dois cancelamentos em paralelo:** o segundo espera a trava da rodada e recebe `ja_cancelada` na releitura; um registro e uma auditoria (T-13).
- **Cancelamento e `adicionar_interesse` em paralelo:**
  - se o interesse trava antes, o cancelamento espera e depois zera a reserva nova;
  - se o cancelamento trava antes, a adição espera e depois recebe a recusa sem rodada ativa.

  Nos dois casos não sobra reserva.
- **Cancelamento e encerramento do fechamento em paralelo:**
  - se o encerramento vem antes, o cancelamento vale sobre `fechamento_encerrado`;
  - se o cancelamento vem antes, o encerramento não faz nada.
- **Cancelamento e suspensão de um comprador em paralelo:** as duas travam a conta primeiro; a segunda encontra a parcela já sem reserva e não falha.
- **Rodada sem nenhuma parcela:** cancela; auditoria com a lista vazia.

## Dependências e decisões em aberto

- Depende de E05, E06 e E11 (ordem das travas). Nenhuma decisão em aberto para esta fatia.
- **Cancelamento de rodada `disponivel_para_retirada` (encerrada)** — referência: §7 (a rodada é encerrada ao liberar a retirada) e §7.2 (o administrador cancela "por decisão própria", sem restrição de etapa). Ambiguidade: os documentos não dizem se uma rodada já encerrada, com produtos recebidos e retirada liberada, ainda pode ser cancelada com reembolso integral. Impacto: só a partir da E14, porque nenhuma rodada chega hoje a `disponivel_para_retirada`. Opções:
  - (a) recusar, porque a rodada está encerrada e o que restar se resolve por ocorrência de entrega (§10);
  - (b) permitir, com as mesmas regras.

  A E12 implementa (a) como guarda, sem efeito prático hoje. A decisão do responsável é necessária antes da E14 e fica registrada na milestone 14.
