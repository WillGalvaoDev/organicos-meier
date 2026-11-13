# E13-02 — O ciclo automático de envio do pedido formal

Fatia 2 de 8 da milestone **E13 — Pedido formal, repasse e portal do fornecedor**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E13-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E13-01.

## Contexto e objetivo

Gerado o pedido formal (E13-01), a plataforma o envia automaticamente ao e-mail do fornecedor:
- até três tentativas no total, incluindo a primeira;
- o ciclo termina no primeiro sucesso ou na terceira falha;
- depois de três falhas, o administrador é avisado e o botão **Reenviar pedido** fica disponível (§10, 17.10, R-4);
- o estado do ciclo fica gravado e é lido sob a mesma trava dos envios, para que uma tentativa automática e um acionamento manual nunca corram juntos (infraestrutura 4.14, R-7).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §10 | Até três tentativas automáticas no total. Depois de três falhas, aviso ao administrador e botão **Reenviar pedido**. Todas as tentativas e resultados registrados e auditáveis. A aceitação pelo serviço de envio não comprova entrega (L-13). |
| Especificação §12 | Falha no envio do pedido formal: ao administrador, depois da terceira tentativa sem sucesso, com a rodada, as tentativas, os resultados e o acesso ao botão. Falha de mensagem não altera estado financeiro. |
| Infraestrutura 4.14 | No máximo três tentativas, pela tabela de chamadas pendentes, com intervalos crescentes definidos na implementação. "Falha" é a recusa ou o erro na chamada ao serviço de e-mail. Cada tentativa registra tipo, número, horário, resultado, resposta e, quando manual, o admin. O estado do ciclo (em andamento, concluído com sucesso, concluído com três falhas) é gravado no pedido formal e lido sob a mesma trava dos envios. |
| Infraestrutura 4.2 | Consulta obrigatória ao provedor antes do envio do pedido formal; se a consulta falhar, a ação fica bloqueada. |
| Infraestrutura 9.2, L-13 | A aceitação pela API do serviço de e-mail não garante a entrega; um pedido aceito e não entregue não aciona tentativas. |
| Herdado da E04 | O envio usa `enviar_email` (E04-03), com o ciclo próprio da infraestrutura 4.14 (e não a fila de envios da E04). O aviso `falha_no_pedido_formal` usa `emitir_evento_para_varios`, na transação do fato, com chave derivada do fato. |
| Herdado da E07 | O envio do pedido formal chama `consultar_antes_de_decidir` e fica bloqueado com `ConsultaAoProvedorFalhou`. |
| Herdado da E12 | A rodada `cancelada` não envia pedido formal. |
| Cenários §16 | 68, 69, 94, 118 |
| Testes técnicos | T-28, T-41 (parte automática), T-54 (estado), T-55 (trava) |

## Escopo

**Dentro:**
- O modelo `TentativaDeEnvioDoPedidoFormal`.
- O serviço `processar_pedidos_formais()` e a tarefa periódica.
- A consulta prévia, as transições do `EnvioDoPedidoFormal`, o aviso ao administrador e a interrupção pela rodada cancelada.

**Fora:**
- O reenvio manual (E13-03). Esta fatia cria as colunas manuais da tentativa (`autor`, `token`) e as restrições delas, que a E13-03 usa.
- As telas (E13-04).

## Modelo

**`TentativaDeEnvioDoPedidoFormal`** (só inserção):

| Campo | Conteúdo |
|---|---|
| `pedido_formal` | chave estrangeira |
| `numero` | ordem da tentativa no pedido formal (1, 2, ...), automática ou manual; único por pedido formal |
| `tipo` | `automatica` ou `manual` |
| `ordem_automatica` | 1, 2 ou 3 nas automáticas; nulo nas manuais |
| `iniciada_em`, `concluida_em` | instantes do envio |
| `resultado` | `sucesso` (aceito pelo serviço de e-mail) ou `falha` |
| `resposta` | até 100 caracteres: `aceito pelo serviço de e-mail` no sucesso; o nome da exceção na falha (como na E04-03) |
| `destino` | o e-mail do pedido do fornecedor usado na tentativa |
| `autor` | o administrador, nas manuais; nulo nas automáticas |
| `token` | UUID único, nas manuais; nulo nas automáticas |

Restrições no banco:
- `UNIQUE (pedido_formal, numero)` e `UNIQUE (pedido_formal, ordem_automatica)`;
- `ordem_automatica` entre 1 e 3;
- `UNIQUE (token)`;
- automática ⇔ `ordem_automatica` não nulo, com `autor` e `token` nulos;
- manual ⇔ `ordem_automatica` nulo, com `autor` e `token` não nulos.

Com isso, o banco recusa uma quarta tentativa automática e um token repetido.

## Regras

1. **Tarefa:** `processar_pedidos_formais()` roda a cada minuto (Procrastinate, `* * * * *`, com `queueing_lock`, como as tarefas da E04 e da E07).
   - **Alcance:** os `EnvioDoPedidoFormal` `em_andamento` com `proxima_tentativa_em` até agora, por `proxima_tentativa_em` e `pk`.
   - **Repetição:** a tarefa nunca decide regra comercial; ela só aplica as transições abaixo.
2. **Rodada cancelada (herdado da E12):** se a rodada do pedido formal está `cancelada`, a tentativa não acontece.
   - Sob a trava da regra 4, o envio passa a `interrompido`, com `motivo_da_interrupcao = rodada_cancelada`, `concluido_em` igual a agora e `proxima_tentativa_em` nulo.
   - Auditoria `pedido_formal.interromper`. Nenhum e-mail e nenhuma tentativa registrada.
3. **Consulta prévia (infraestrutura 4.2):**
   - **Quando:** antes de cada tentativa automática, fora de transação e sem trava.
   - **Como:** `consultar_antes_de_decidir(referencia)` para cada pedido da abertura do ciclo, por `pk` (os mesmos da aprovação, E11-06).
   - **Falha (`ConsultaAoProvedorFalhou`):** a tentativa não acontece e não conta.
     - Sob a trava, `proxima_tentativa_em` passa a agora + 5 minutos.
     - A falha fica no log, sem dado pessoal, com o pedido formal.
     - Nenhuma tentativa é registrada, porque nada foi entregue ao serviço de e-mail.
   - Um pagamento sincronizado nessa consulta segue as regras que já existem (E08-04, E11) e não muda o pedido formal.
4. **Tentativa, sob trava:**
   - **Travas, nesta ordem, numa transação:**
     - o `EnvioDoPedidoFormal`, com `select_for_update(skip_locked=True)`: outra execução da tarefa pula o registro;
     - a `Rodada`, com `select_for_update(no_key=True)`, relida. É a trava que serializa o envio com o cancelamento (E12), que trava a mesma linha do mesmo modo.
   - **Conferências sob as travas:** ainda `em_andamento`, já vencido e a rodada não cancelada (senão, a regra 2).
   - **Envio:** `enviar_email(fornecedor.email_pedido, pedido_formal.assunto, pedido_formal.corpo)`, com o e-mail lido do cadastro agora. O assunto e o corpo são exatamente os gravados.
   - **Registro:** a `TentativaDeEnvioDoPedidoFormal` automática, com `ordem_automatica = automaticas + 1`, o próximo `numero`, o destino e a resposta.
   - **Trava durante o envio:** o envio acontece com a trava retida, para que duas tentativas do mesmo pedido formal nunca saiam ao mesmo tempo (infraestrutura 4.14).
5. **Transições do envio** (na mesma transação da tentativa):

| Resultado | `ordem_automatica` | Novo estado |
|---|---|---|
| sucesso | 1, 2 ou 3 | `concluido_com_sucesso`, `concluido_em`, `proxima_tentativa_em` nulo |
| falha | 1 | continua `em_andamento`; `proxima_tentativa_em` = conclusão + 5 minutos |
| falha | 2 | continua `em_andamento`; `proxima_tentativa_em` = conclusão + 30 minutos |
| falha | 3 | `concluido_com_falhas`, `concluido_em`, `proxima_tentativa_em` nulo; aviso da regra 6 |

   Em todos os casos, `automaticas` passa a `ordem_automatica`. Não existe quarta tentativa automática (cenário 69, T-28).
6. **Aviso ao administrador** (`falha_no_pedido_formal`), na transação da terceira falha:
   - **destinatários:** todos os administradores ativos, por `emitir_evento_para_varios`, como os alertas financeiros (E09-08);
   - **chave base:** `falha_no_pedido_formal:<pedido formal>`, então um aviso por pedido formal e administrador;
   - **título:** `Falha no envio do pedido formal: <fornecedor>`;
   - **corpo:** `O pedido formal nº <pk> da rodada <rodada> de <fornecedor> não foi aceito pelo serviço de e-mail depois de 3 tentativas automáticas.`, seguido de uma frase por tentativa: `Tentativa <n> em <dd/mm/aaaa hh:mm>: <resposta>.`, e de `Use Reenviar pedido na página do pedido formal.`;
   - **link:** a página do pedido formal (E13-04, `administracao/rodadas/<pk>/pedido-formal/`);
   - **sem administrador ativo:** nenhum aviso, com o registro no log (como a E09-08).
7. **Falha do canal não muda dinheiro nem pedido:** nenhuma regra desta fatia escreve no livro-razão, no pedido, na rodada ou nos pagamentos (§12).
8. **Exceção inesperada no envio:** qualquer exceção de `enviar_email` é falha da tentativa, registrada com o nome da exceção. Ela não sai da tarefa e não desfaz o registro da tentativa.
9. **Queda do processo:** se o processo cair depois de o serviço aceitar a mensagem e antes do commit, a transação é desfeita e a tentativa se repete na próxima execução, com o mesmo número. É o mesmo "pelo menos uma vez" da E04-03, porque o serviço de e-mail não tem chave de idempotência (L-13).
10. **Auditoria:** cada conclusão do ciclo (`concluido_com_sucesso`, `concluido_com_falhas` ou `interrompido`) registra `pedido_formal.ciclo_concluido`, com autor `SISTEMA`, o estado e as tentativas (número, resultado e resposta).

## Interface

- `processar_pedidos_formais(*, limite: int = 50) -> int`: devolve quantas tentativas fez.
- `estado_do_envio(pedido_formal) -> str`: a situação gravada, sem trava, para as telas.

## Decisões técnicas

- **"Tabela de chamadas pendentes" é o próprio estado do envio.** A infraestrutura 4.14 pede que as tentativas saiam de uma tabela e não da requisição. A `ChamadaAoProvedor` (E07-04) é do provedor de pagamentos e repete sem limite. O pedido formal precisa de limite de três e de estado lido sob a trava dos envios. Por isso o `EnvioDoPedidoFormal` guarda a próxima tentativa, e a tarefa periódica a executa: é a mesma garantia (registro na transação do fato, execução por tarefa, nada perdido se o processo cair).
- **Intervalos de 5 e 30 minutos.** São crescentes, como pede a infraestrutura 4.14, e curtos o bastante para o administrador ser avisado no mesmo período do dia.
- **Falha de consulta não é tentativa.** A 4.14 define falha como a recusa ou o erro do serviço de e-mail. Uma consulta ao provedor que não responde bloqueia a ação (4.2), então nada é entregue ao serviço e não há tentativa a registrar. Contar essa falha anteciparia o fim do ciclo sem nenhum envio.
- **Trava da rodada no envio.** Ela não bloqueia leituras. Ela faz o cancelamento esperar o envio em curso, e um envio começado depois do cancelamento ver a rodada cancelada. Depois da aprovação, os únicos fluxos que travam a rodada são o cancelamento (E12), o ajuste da previsão (E13-05) e os envios. Nenhum deles trava o `EnvioDoPedidoFormal` depois da rodada, então a ordem envio → rodada não forma ciclo com o cancelamento (contas → fornecedor → rodada → ...).

## Invariantes

- No máximo três tentativas automáticas por pedido formal (restrição no banco).
- Nenhuma tentativa automática com o envio fora de `em_andamento`.
- Nenhum e-mail do pedido formal de rodada cancelada depois do commit do cancelamento.
- O conteúdo enviado é sempre o `assunto` e o `corpo` gravados.

## Casos-limite e concorrência

- **Duas execuções da tarefa ao mesmo tempo:** a segunda pula o envio travado (`skip_locked`); uma tentativa só.
- **Cancelamento durante uma tentativa:** o cancelamento espera a trava da rodada. A tentativa em curso conclui e, depois do commit do cancelamento, a próxima execução interrompe o ciclo.
- **Sucesso depois de falha:** duas tentativas registradas, ciclo `concluido_com_sucesso`, nenhum aviso (cenário 68).
- **E-mail do fornecedor alterado entre tentativas:** cada tentativa registra o destino usado.

## Dependências e decisões em aberto

- Depende da E13-01, da E04-03 (`enviar_email`) e da E07-06 (consulta).
- Nenhuma decisão em aberto.

## Correção da revisão: E13-R02, a consulta vale só para a tentativa que a motivou (2026-11-13)

Origem: revisão independente sobre `9af6251` (`docs/specs/E13-02/review.md`, "E13-R02 — Importante").

**Defeito.** A consulta da regra 3 acontece fora de transação e sem trava. Por isso ela pode terminar depois de outra execução ter feito a tentativa que essa consulta precedia. No caminho de falha, a execução atrasada só confere `em_andamento` e grava agora + 5 minutos. Com isso, o intervalo de 30 minutos da segunda falha vira 5 (regra 5), contra os intervalos crescentes da infraestrutura 4.14. A trava impede escritas simultâneas, mas não uma escrita obsoleta feita depois do commit da outra execução.

O mesmo vale para o caminho de sucesso. Uma consulta bem-sucedida, mas atrasada, ainda permitiria a próxima tentativa, se o relógio já tivesse passado do novo agendamento. Essa tentativa sairia sem consulta posterior à tentativa anterior, contra a regra 3 ("antes de cada tentativa").

**Regra nova 3-A, o retrato da seleção:**
- **O retrato:** ao começar a tratar um envio, antes da consulta, a execução lê `automaticas` e `proxima_tentativa_em`. A consulta que vem a seguir pertence a esse retrato.
- **Falha da consulta:** sob a trava do envio (`skip_locked`, como hoje), o reagendamento para agora + 5 minutos só acontece se o envio continua `em_andamento` e com `automaticas` e `proxima_tentativa_em` iguais ao retrato. Se algum deles mudou, a execução não escreve nada e devolve 0; o registro no log da regra 3 continua.
- **Sucesso da consulta:** às conferências sob as travas da regra 4 (ainda `em_andamento`, vencido, rodada não cancelada), acrescenta-se: `automaticas` e `proxima_tentativa_em` iguais ao retrato.
  - Se algum deles mudou, a execução não tenta, não escreve e devolve 0.
  - A próxima execução que encontrar o envio vencido faz uma consulta nova.
- **Rodada cancelada:** a interrupção da regra 2 não depende do retrato, porque ela não usa a consulta.

**O que não muda:**
- a falha de consulta do trabalho vigente continua reagendando em 5 minutos, sem contar tentativa (A-7);
- a segunda execução simultânea continua pulando o envio travado (A-11);
- os intervalos de 5 e 30 minutos, o limite de três tentativas e o aviso aos administradores.

**Decisão técnica.** O retrato compara os dois campos que toda transição da regra 5 e todo reagendamento da regra 3 mudam. Uma mudança em qualquer um deles mostra que outra execução já agiu depois da consulta. Comparar só `automaticas` não bastaria: um reagendamento por falha de consulta muda apenas `proxima_tentativa_em`.

**Invariante novo:** toda tentativa automática tem uma consulta prévia, feita depois da tentativa anterior do mesmo pedido formal. Nenhum reagendamento por falha de consulta substitui o agendamento gravado por uma tentativa posterior a essa consulta.
