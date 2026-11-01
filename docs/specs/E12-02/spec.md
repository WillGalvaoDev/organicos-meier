# E12-02 — Cancelamento com pedidos: pagamento e aguardando fornecedor

Fatia 2 de 7 da milestone **E12 — Cancelamento da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E12-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E12-01.

## Contexto e objetivo

A partir da abertura do pagamento (`T0`), a rodada tem pedidos congelados. O cancelamento precisa ainda:
- cancelar os pedidos não pagos;
- bloquear novas tentativas de pagamento e cancelar no provedor as cobranças pendentes;
- impedir que a apuração e a aprovação do resultado continuem.

Tudo isso sem tocar na composição dos pedidos nem nos registros financeiros (§7.1, §7.2). Esta fatia cobre o efeito comum às duas indicações e, por inteiro, o cancelamento **sem reembolso**. O reembolso é da E12-03.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7.1 | A composição do pedido congelado é definitiva. O cancelamento da rodada é uma mudança legítima de estado, registrada separadamente. |
| Especificação §7.2 | Sem reembolso: nenhuma devolução nova. Obrigações existentes não são apagadas nem liquidadas. Registros anteriores preservados. Ao cancelar, novas tentativas de pagamento ficam bloqueadas. |
| Infraestrutura 3.2 | Cancelamento sem reembolso: nenhum lançamento novo; obrigações mantidas; os valores continuam nas destinações em que estavam. |
| Infraestrutura 4.8 | Na transação: bloqueia novas tentativas. As chamadas ao provedor (cancelar tentativas pendentes [L-2]) entram na tabela de chamadas pendentes. Registros anteriores não são alterados. |
| Infraestrutura 7, fase 1 | O simulador reproduz o cancelamento da rodada durante a margem e depois do repasse. |
| Herdado da E08 | O cancelamento bloqueia novas tentativas (`pedir_pagamento` recusa com a rodada `cancelada`) e cancela as cobranças pendentes com `agendar_cancelamento` e um motivo próprio no alvo (`t<tentativa>:cancelamento_da_rodada`). |
| Cenários §16 | 41, 44, 45 |
| Testes técnicos | T-15 |

## Escopo

**Dentro:**
- O motivo `cancelamento_da_rodada` em `MotivoDoCancelamento`.
- O cancelamento dos pedidos não pagos do ciclo vigente.
- As parcelas `em_pedido`.
- O bloqueio de tentativas e o cancelamento das cobranças pendentes, inclusive as sem tentativa.
- A recusa da apuração, da aprovação e das tarefas da linha do tempo.
- O cancelamento sem reembolso.

**Fora:**
- O reembolso (E12-03).
- O destino de um pagamento aprovado depois (E12-04).
- O aviso (E12-05).
- As telas (E12-06).
- O pedido formal e o repasse (E13): ver "Dependências".

## Regras

Acréscimos a `cancelar_rodada` (E12-01), nas etapas `pagamento` e `aguardando_fornecedor`:

1. **Compradores e pedidos envolvidos:** os pedidos de todas as aberturas da rodada. Os compradores deles entram nas travas de conta da E12-01.
2. **Travas:** depois das travas da E12-01, as `SituacaoDoPedido` dos pedidos da abertura do ciclo vigente, por `pedido_id` (a mesma posição da E11-01). Os pedidos das aberturas anteriores só são lidos.
3. **Pedidos não pagos:** cada pedido da abertura vigente em `aguardando_pagamento` passa a `cancelado`:
   - `motivo_do_cancelamento = cancelamento_da_rodada`;
   - `cancelado_em` = o instante do cancelamento.

   Pedidos já `cancelado` (inadimplência, suspensão, remoção) não mudam, nem o motivo nem o instante. Pedidos `pago` continuam `pago`.
4. **Composição intacta:** nenhum `Pedido`, `ItemDoPedido` ou `ParcelaNoPedido` muda ou é criado (§7.1).
5. **Parcelas `em_pedido`** (a parte congelada): seguem a regra 6 da E12-01. A reserva vai a zero e a parcela fica `removida`, ou `pendente` quando tem parte pendente. A parte congelada continua só no pedido.
6. **Cobranças pendentes no provedor:**
   - **com tentativa:** para cada tentativa `criada` de pedido da abertura vigente, `agendar_cancelamento(tentativa, "cancelamento_da_rodada")`. O alvo `t<tentativa>:cancelamento_da_rodada` é diferente dos da E08 e da E11, então o cancelamento não espera chamada em andamento (E07-R01). Vale também para as tentativas de pedidos que continuam `pago` (por exemplo, uma segunda cobrança aberta);
   - **sem tentativa vinculada:** cada `PagamentoNoProvedor` `pendente` com a referência de um pedido da abertura vigente e sem tentativa (cobrança órfã, E08-R03) recebe o agendamento `cancelar_cobranca` com o alvo `<id_externo>:cancelamento_da_rodada`;
   - os agendamentos acontecem na transação do cancelamento e só executam depois do commit (infraestrutura 4.8);
   - uma tentativa `solicitada`, ainda sem cobrança, não recebe agendamento: a execução da criação já recusa pedido cancelado (`pedido_cancelado`, E08-03) e procura a órfã.
7. **Novas tentativas:** `pedir_pagamento` recusa, depois das travas que já faz, com `PagamentoRecusado("rodada_cancelada")` quando a rodada do pedido está `cancelada`, antes das outras conferências de situação. A mensagem é "A rodada foi cancelada pelo administrador; não há pagamento a fazer."
8. **Apuração e aprovação:** com a rodada `cancelada`, `iniciar_apuracao` e `aprovar_resultado` recusam com `ApuracaoRecusada("fora_de_pagamento")` (a conferência de etapa que já existe), na conferência prévia e sob as travas.
9. **Tarefas da linha do tempo:** o bloqueio de `T0 + 24h` e a reconsulta da margem (E08-05) já filtram a etapa `pagamento` e passam a ignorar a rodada cancelada. Um critério confirma isso.
10. **Sem reembolso** (`com_reembolso = False`):
    - nenhum `Reembolso`, nenhuma `ObrigacaoComComprador` e nenhum `MovimentoFinanceiro` novo;
    - as obrigações existentes (de destino, de caixa invalidada, de mínimo) não mudam, não são liquidadas e continuam no seu fluxo: autorização, execução e devolução excepcional da E10;
    - os saldos das destinações continuam como estavam (infraestrutura 3.2).
11. **Auditoria `rodada.cancelar`:** acrescenta os pedidos cancelados agora (`pk` e situação anterior), os pedidos pagos (`pk`) e as cobranças com cancelamento agendado (alvo e `id_externo`).

**`aguardando_fornecedor`:**
- não há pedido não pago nem cobrança pendente esperada;
- as regras 4, 5, 10 e 11 valem;
- a apuração no livro (E11-06) não é desfeita: custódia, obrigação com o fornecedor, frete e receita continuam como estavam.

## Decisões técnicas

- **Pedido não pago de rodada cancelada é `cancelado`, com motivo próprio.** É a mudança de estado prevista no §7.1 para o cancelamento da rodada. Ela usa o mesmo registro de situação da E08 e deixa o destino de um pagamento tardio decidido pela E12-04.
- **O cancelamento no provedor é assíncrono.** A infraestrutura 4.8 manda as chamadas para a tabela de chamadas pendentes. Ao contrário da apuração (infraestrutura 4.3), o cancelamento não decide a partir da situação final das cobranças: qualquer aprovação que chegar depois é tratada pela E12-04.
- **Só a abertura do ciclo vigente tem situação travada.** Os ciclos anteriores já foram apurados (retorno ao interesse) e não têm pedido aguardando pagamento.

## Invariantes

- Depois do cancelamento, nenhum pedido da rodada fica `aguardando_pagamento`.
- Nenhum pedido `pago` muda de situação.
- Sem reembolso, o livro-razão não ganha movimento (contagem e saldos iguais antes e depois).

## Casos-limite e concorrência

- **Cancelamento e `pedir_pagamento` em paralelo:**
  - se o pedido do pagamento trava a situação antes, a tentativa nasce `solicitada` e a criação dela é recusada depois;
  - se o cancelamento trava antes, o pedido de pagamento espera e recebe `rodada_cancelada`.
- **Cancelamento e aviso de aprovação em paralelo:** o aviso trava o pagamento e depois a situação do pedido (E08-04).
  - Se o aviso vem antes, o pedido está `pago` quando o cancelamento o lê.
  - Se vem depois, o pedido está `cancelado` e o destino é da E12-04.
- **Cancelamento e apuração em paralelo** (relógio depois de `T0 + 48h`): a ordem das travas é a mesma.
  - Se a apuração confirma antes, o cancelamento vale sobre o resultado: pedidos já cancelados por inadimplência continuam com esse motivo.
  - Se o cancelamento confirma antes, a apuração recebe `fora_de_pagamento` sob as travas.
- **Cancelamento durante a margem**, com uma cobrança pendente: o pedido fica `cancelado` e a cobrança recebe o agendamento.
- **Cancelamento de rodada que voltou para interesse depois de uma apuração** (ciclo 2 em interesse): é o caso da E12-01, mais a leitura dos pedidos do ciclo 1 (pagos, com a devolução integral de mínimo já registrada). Nada muda neles.

## Dependências e decisões em aberto

- Depende da E12-01, da E08 (tentativas e cancelamento no provedor) e da E11 (apuração e aprovação). Nenhuma decisão em aberto.
- **Herdado para a E13:** uma rodada cancelada em `aguardando_fornecedor` não envia pedido formal nem permite reenviar (a E13 confere a etapa). O tratamento de um repasse posterior ao cancelamento segue as regras da E13 e de P-2.

## Correção da revisão: R03, a ordem das travas com os pedidos de ciclos anteriores (2026-11-01)

Origem: revisão independente sobre `8e236e5` (`docs/specs/E12-07/review.md`, "R03 — bloqueador").

Nenhuma regra comercial muda. A correção alinha esta fatia ao uso real da E12-03: o reembolso integral relê e trava a situação dos pedidos pagos de **todas** as aberturas. A ordem global do projeto vale também para o cancelamento:

| Fluxo | Ordem das travas |
|---|---|
| Sincronização (E08-04, E09-04) | o pagamento → a `SituacaoDoPedido` → as contas do livro |
| Apuração (E11-01, E11-06) | as travas da E11 → as situações → as contas do livro |

O defeito: o cancelamento travava as contas do livro antes da situação de um pedido de ciclo anterior. Uma sincronização concorrente de pagamento tardio desse pedido travava a situação e esperava as contas, e o banco acusava impasse.

**Regra 2, reescrita — travas:**
- **Alcance:** depois das travas da E12-01, as `SituacaoDoPedido` de **todos os pedidos de todas as aberturas da rodada**, numa única consulta `select_for_update` ordenada por `pedido_id` (a mesma posição da E11-01).
- **Etapas e indicações:**
  - vale nas duas indicações e em todas as etapas canceláveis;
  - nas etapas antes do pagamento, alcança os pedidos dos ciclos anteriores (rodada que voltou para interesse);
  - sem pedido, não trava nada.
- **Uso:**
  - só os pedidos da abertura vigente podem mudar de situação (regra 3);
  - os demais são travados para que a leitura deles (pago ou não, E12-03 regra 1; destinatários e texto do aviso, E12-05) seja estável e para que nenhuma trava de situação venha depois de uma conta do livro.
- **Contas do livro:** nenhuma trava de conta do livro (`travar_contas`, E09) acontece antes desta consulta.
- **Reembolso:** as travas de situação feitas depois, dentro de `reembolso_integral_do_pedido` (E10-02), alcançam linhas já travadas e não mudam a ordem.

**Invariantes da ordem** (conferidos por teste e registrados no `review.md` pelo implementador):
- a transação do cancelamento não trava nenhum `PagamentoNoProvedor` (sincronização) nem `DestinoDoPagamento`;
- toda trava de tentativa ou de chamada (`agendar_cancelamento`, `agendar_chamada`) acontece depois das situações, como na E08;
- as contas do livro são as últimas travas da transação.

O implementador confere no código das E08-04, E09-04 e E10-02 que a ordem acima é a de todos os fluxos que travam a situação e as contas. Uma divergência encontrada volta ao especificador com evidência.

**Decisão técnica substituída:** a decisão "Só a abertura do ciclo vigente tem situação travada" deixa de valer. Ela trocou leitura sem trava por trava de linha já necessária para o reembolso, e é essa inversão que gerou o impasse.

**Caso-limite reescrito — cancelamento de rodada que voltou para interesse:** as situações dos pedidos do ciclo 1 são travadas (regra 2) e nenhuma muda.

Critérios: A-17 e A-18 (`acceptance.md`) e E12-03 A-19 a A-21.
