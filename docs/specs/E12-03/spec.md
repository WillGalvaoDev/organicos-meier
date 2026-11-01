# E12-03 — Cancelamento com reembolso: devolução integral, já autorizada

Fatia 3 de 7 da milestone **E12 — Cancelamento da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E12-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E12-01.

## Contexto e objetivo

Com a indicação "com reembolso", cada comprador que efetivamente pagou recebe a devolução integral (§7.2):
- o valor pago (produtos, serviço e frete);
- menos as devoluções já concluídas ou pendentes;
- de modo que o total devolvido nunca passe do pago.

A indicação já é a autorização administrativa das devoluções geradas, sem etapa adicional. A execução segue os mecanismos da E10: o provedor como via principal e a devolução excepcional quando ele for comprovadamente inviável.

Esta fatia acrescenta a `cancelar_rodada`:
- a consulta prévia ao provedor;
- os reembolsos integrais e as obrigações;
- a autorização automática das devoluções, com a nova tentativa periódica.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7.2 | Com reembolso: devolução integral para todos os que pagaram. "Integral" = produtos, serviço e frete, descontadas as devoluções concluídas ou pendentes. A indicação já é a autorização. Os reembolsos usam o provedor e, quando necessário, a devolução excepcional (§9.2, §9.5). |
| Especificação §9.1, §9.2 | Motivo de estorno: cancelamento administrativo com reembolso. A devolução integral soma exatamente os valores cobrados registrados. |
| Infraestrutura 3.2 | Uma obrigação de devolução integral por comprador que pagou, financiada como as demais devoluções (antes ou depois do repasse). |
| Infraestrutura 4.2 | Consulta obrigatória antes do cancelamento com reembolso; se a consulta falhar, a ação fica bloqueada. |
| Infraestrutura 4.8 | As obrigações são geradas na transação, já autorizadas pela indicação. As devoluções entram na tabela de chamadas pendentes. Chave por rodada e comprador: uma nova execução não duplica. "Integral" sem duplicar: o pago menos as devoluções concluídas e pendentes; as pendentes continuam no seu fluxo e não são substituídas. |
| Infraestrutura 4.12 | A devolução integral do cancelamento passa pelo mesmo acumulador por item e componente: o resultado é determinístico. |
| Herdado da E07 | O cancelamento com reembolso chama `consultar_antes_de_decidir` e fica bloqueado com `ConsultaAoProvedorFalhou`. |
| Herdado da E09 | Uma obrigação por comprador que pagou, pelo valor pago menos o já devolvido ou pendente, via `registrar_obrigacao_com_comprador`, financiada antes ou depois do repasse pela regra da rodada. |
| E10-02 | `reembolso_integral_do_pedido` devolve tudo o que ainda não foi devolvido, item por item e componente por componente; o motivo `cancelamento_da_rodada` já existe. |
| E10-04 | `autorizar_devolucao(obrigacao, autor=SISTEMA)` para etapas que já trazem a autorização na ação, como o cancelamento com reembolso. A consulta vem fora da transação da decisão. |
| Cenários §16 | 43, 46, 91, 114 |
| Testes técnicos | T-13, T-14 |

## Escopo

**Dentro:**
- A consulta prévia.
- O reembolso integral de cada pedido pago da rodada, com a obrigação financiada pela regra.
- A autorização automática depois do commit.
- A tarefa periódica que autoriza o que ficou sem autorizar.
- A auditoria.

**Fora:**
- A execução no provedor, a nova tentativa, a falha definitiva, a devolução excepcional e a conciliação: são as da E10, sem mudança.
- O aviso (E12-05) e as telas (E12-06).

## Regras

Acréscimos a `cancelar_rodada` quando `com_reembolso = True`, em qualquer etapa cancelável:

1. **Pedidos pagos da rodada:** os pedidos de todas as aberturas da rodada com a situação `pago`, por `pk`. Sem pedido pago (por exemplo, nas etapas antes do pagamento), as regras 3 a 6 não fazem nada.
2. **Consulta prévia, fora de transação e antes das travas:**
   - `consultar_antes_de_decidir(referencia)`, por `pk`, para cada pedido de todas as aberturas da rodada que está `pago`, ou `aguardando_pagamento` na abertura vigente;
   - uma `ConsultaAoProvedorFalhou` bloqueia o cancelamento inteiro, sem escrita (nem rodada, nem pedidos, nem chamadas);
   - um pagamento sincronizado agora segue as regras que já existem (E08-04): pode quitar um pedido ainda aguardando, que então entra na regra 1 sob as travas.
3. **Travas do livro:** depois das travas da E12-01 e da E12-02, as contas financeiras de todas as obrigações a criar são travadas de uma vez, em ordem de `pk`, antes da primeira. É a regra única da E09 (`contas_das_obrigacoes`), com os compradores dos pedidos pagos, agrupados por ciclo, numa única chamada a `travar_contas`.
4. **Reembolso integral:** na transação do cancelamento, para cada pedido pago da regra 1, relido sob as travas:
   - `reembolso_integral_do_pedido(pedido, chave=f"cancelamento:{rodada}:{comprador}:{pedido}", motivo=cancelamento_da_rodada, autor=administrador)`;
   - o valor é o que ainda não foi devolvido do pedido, por item e por componente, considerando todos os `Reembolso` anteriores (concluídos ou pendentes, autorizados ou não). A soma nunca passa do pago;
   - sem nada restante (pedido já devolvido por inteiro, por exemplo pelo mínimo não atingido de um ciclo anterior): nada é gravado para ele;
   - a obrigação nasce financiada pela regra da E09-06:
     - antes da apuração no livro, pela custódia do ciclo;
     - depois dela, pela obrigação com o fornecedor (produtos), pela receita de serviço e pelo frete da rodada;
     - o que faltar fica sem cobertura;
   - as obrigações que já existem (de caixa invalidada, de mínimo, de ocorrência, de destino de pagamento) não mudam e continuam no seu fluxo, inclusive as ainda não autorizadas.
5. **Autorização automática, depois do commit:**
   - **quando:** com a transação confirmada, `cancelar_rodada` chama `autorizar_devolucao(obrigacao, autor=SISTEMA)` para cada obrigação criada na regra 4, por `pk`;
   - **contrato:** cada chamada faz a própria consulta fora da transação (E10-04);
   - **falhas** (`ConsultaAoProvedorFalhou`; `DevolucaoRecusada` por falta de cobertura ou pagamento não aprovado no provedor):
     - não desfazem o cancelamento e não são relançadas;
     - ficam no log com a obrigação e o motivo;
     - a obrigação continua devida e autorizada pela indicação, à espera da regra 6.
6. **Nova autorização periódica:**
   - **a tarefa:** `autorizar_devolucoes_do_cancelamento_agora()`, a cada 10 minutos (Procrastinate, como as tarefas da E09);
   - **alcance:** procura as obrigações com o motivo `cancelamento_da_rodada`, sem `ParcelaDeDevolucao` e sem falta de cobertura (`sem_cobertura_da_obrigacao = 0`), e chama `autorizar_devolucao(obrigacao, autor=SISTEMA)` para cada uma;
   - **falhas:** são registradas e esperam a próxima execução;
   - **cobertura:** uma obrigação sem cobertura espera que o administrador escolha a fonte (receita de serviço, reserva ou aporte; P-2 e P-3, E09). Essa escolha é de financiamento, e não uma nova autorização da devolução. Coberta, a próxima execução autoriza;
   - **repetição:** a tarefa nunca cria uma segunda parcela, porque `autorizar_devolucao` devolve a existente.
7. **Auditoria `rodada.cancelar`:** acrescenta os reembolsos gerados (a chave, o pedido, o comprador e os componentes) e, sem nada restante, os pedidos pagos sem reembolso novo.

**Recusas:** as da E12-01 e da E12-02, mais a `ConsultaAoProvedorFalhou` da regra 2, que a tela traduz (E12-06).

## Decisões técnicas

- **Um reembolso por pedido pago, com a chave por rodada e comprador.** A infraestrutura 4.8 pede uma chave por rodada e comprador. O `Reembolso` é por pedido, e um comprador pode ter pedidos pagos em dois ciclos da mesma rodada (retorno ao interesse). A chave `cancelamento:<rodada>:<comprador>:<pedido>` contém a rodada e o comprador e continua única por pedido. Quando o pedido do ciclo anterior já foi devolvido por inteiro, só o do ciclo vigente gera reembolso.
- **O autor do reembolso é o administrador, e o da autorização é `SISTEMA`.** O reembolso registra quem decidiu (a indicação). A parcela de devolução nasce pela regra, como a E10-04 prevê para o cancelamento. A auditoria do cancelamento liga as duas.
- **A autorização acontece depois do commit, e não na transação.** `autorizar_devolucao` precisa consultar o provedor fora de transação (E07-06, E10-04). Por isso o cancelamento confirma primeiro as obrigações, que já são a dívida registrada, e autoriza em seguida. A tarefa periódica garante que nenhuma obrigação do cancelamento fique sem autorização por uma falha passageira.
- **A falta de cobertura não bloqueia o cancelamento.** Depois do repasse (E13), ou com a receita de serviço consumida por tarifas, parte da obrigação fica sem cobertura. Escolher a fonte exige o administrador (infraestrutura 3.2, P-2). O cancelamento registra a dívida, e a execução espera a cobertura.

## Invariantes

- Para cada pedido pago: a soma dos reembolsos (o do cancelamento mais os anteriores) é igual ao pago, por item e por componente, e nunca maior.
- No máximo um reembolso do cancelamento por pedido (chave única) e uma parcela de devolução por obrigação (E10).
- Quem não pagou não tem reembolso do cancelamento.
- Nenhuma obrigação anterior muda.

## Casos-limite e concorrência

- **Dois cancelamentos com reembolso em paralelo** (T-13): os dois consultam, e um trava primeiro.
  - O segundo recebe `ja_cancelada` sob a trava, sem gravar nada.
  - Um reembolso por pedido; nenhuma parcela duplicada.
- **Reembolso parcial anterior pendente** (T-14), por exemplo o estorno de caixa invalidada ainda não autorizado:
  - a nova obrigação cobre só o saldo restante;
  - a anterior continua pendente de autorização no fluxo dela.
- **Reembolso de mínimo não atingido do ciclo 1, ainda pendente,** e a rodada cancelada no ciclo 2: o pedido do ciclo 1 não tem saldo e não gera reembolso novo.
- **Falha do provedor na autorização automática:** o cancelamento confirma, e a obrigação espera a tarefa.
- **Pagamento sincronizado na consulta prévia, com o pedido ainda aguardando:** ele quita, e o pedido passa a pago antes das travas. Entra no reembolso integral.
- **Falha definitiva da devolução:** a parcela segue para "elegível para devolução excepcional" (E10-04/E10-06), sem duplicar (cenário 46).

## Dependências e decisões em aberto

Depende das E12-01 e E12-02 e das E09-06, E10-02, E10-04 e E10-06. Nenhuma decisão em aberto.

## Correção da revisão: R03, impasse com pagamento tardio de ciclo anterior (2026-11-01)

Origem: revisão independente sobre `8e236e5` (`docs/specs/E12-07/review.md`, "R03 — bloqueador"). Nenhuma regra comercial muda.

**Regra 3, complemento:**
- **"Depois das travas da E12-02":** inclui as situações de todos os pedidos de todas as aberturas (E12-02, regra 2 reescrita).
- **Lista dos pagos (regra 1):** é lida depois dessas travas. As contas de `contas_das_obrigacoes` são calculadas a partir dela e travadas por último.
- **Pedido sem saldo:** um pedido pago sem nada a devolver (por exemplo, o do ciclo 1 já coberto pela devolução de mínimo) não acrescenta trava nova ao chamar `reembolso_integral_do_pedido`.

**Caso-limite novo — pagamento tardio de ciclo anterior durante o cancelamento:**
- **Situação:** rodada que voltou para interesse (AP-R, E12-02). Uma segunda cobrança de X, criada antes do prazo, é aprovada no provedor e sincronizada enquanto o cancelamento com reembolso está entre a consulta prévia e o commit.
- **Ordem igual nos dois fluxos:** a situação de X e depois as contas do livro. Um espera o outro, sem impasse.
- **Sincronização antes:** ela decide o destino `devolucao` por `duplicidade` (X já está pago). A obrigação integral do pagamento é financiada por ele mesmo (E09-04), sem o alerta `pagamento_depois_do_cancelamento`, porque o cancelamento ainda não existe.
- **Cancelamento antes:** a sincronização decide depois, também por `duplicidade` (a ordem dos motivos da E12-04 não muda), e o alerta `pagamento_depois_do_cancelamento` abre (E12-04, regra 4).
- **Nos dois casos:**
  - o cancelamento conclui;
  - X não ganha reembolso do cancelamento (sem saldo);
  - a obrigação da duplicidade não é autorizada pela indicação (E12-04);
  - nenhuma devolução é duplicada.

Critérios: A-19 a A-21 (`acceptance.md`).
