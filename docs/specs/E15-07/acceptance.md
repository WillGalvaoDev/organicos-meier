# E15-07 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Como na E14-08, não há Red próprio: a fatia verifica comportamentos que as E15-01 a E15-06 construíram por TDD.

- **Execução:**
  - o administrador ADM1 (o banco admite um único administrador, sempre ativo (especificação §1, "Há um único administrador"; `conta_administrador_unico` e `conta_administrador_ativo`));
  - o painel lido com `GET /administracao/` como ADM1, autenticado com passkey e com `entrar_de_novo` depois de cada avanço do relógio;
  - as tarefas chamadas diretamente;
  - `verificar_operacao(timestamp=0)` sempre que o critério diz "verificar".
- **Arranjo da rodada:** AP-I2 da E15-05 para o começo. A partir da aprovação, o AE da E14-01, com `simulador_pagamentos.definir_liberacao("pix", horas=0)`.
- **Invariante financeiro:** conferido sem violação no fim de cada critério, como o `_invariante_ok()` das E13-08 e E14-08.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 1 | positivo | AP-I2 | GET; iniciar o fechamento pela tela; GET; avançar até o prazo + 1min e chamar `encerrar_fechamentos_vencidos`; GET | as ações "Mínimo atingido...", depois nenhuma de G em `fechamento` (com "Fecha em..." na tabela), depois "Fechamento encerrado: aguarda a abertura do pagamento." |
| A-2 | Cenário 1 | positivo | o A-1 | abrir o pagamento pela tela; GET em `T0 + 1h` e em `T0 + 48h`; apurar pela tela; GET; aprovar pela tela; GET | "Pagamento até...; margem até..."; depois "Apta para a apuração final desde..."; depois "Apuração feita: aguarda a aprovação do resultado."; depois a etapa "Aguardando fornecedor", com a ação "Recebimento: ..." |
| A-3 | Cenário 1 | positivo | AE (aprovada) | `enviar_pedidos_formais` com o e-mail falhando três vezes (E13-02); GET; reenviar pela tela; GET | a ação "O pedido formal não foi enviado depois das três tentativas: reenvie."; depois do reenvio aceito, a ação some |
| A-4 | Cenário 1 | positivo | o A-3 | GET; repasse de R$ 170,00 e frete de R$ 22,00 pela tela da E13-06; GET | as duas ações de saída; depois, nenhuma |
| A-5 | Cenário 1 | positivo | o A-4 | recebimento total pela tela da E14-06; GET; registrar o endereço; GET; liberar pela tela; GET em `L + 8 dias`; descartar todos os saldos pela tela; GET | "Recebimento resolvido... Registre antes o endereço de retirada."; depois sem a segunda frase; depois "Retirada até..." na tabela e, em `L + 8 dias`, "Prazo de retirada encerrado: 4 item(ns)..." e a linha em "Prazos encerrados"; por fim, a rodada fora do painel, sem ações |
| A-6 | Cenário 2 | positivo | todas as tarefas concluídas em `I` | avançar para `I + 6min`, sem chamar as tarefas de 1 minuto; verificar; GET | `tarefa_atrasada` para as cinco tarefas de 1 minuto; uma notificação no site e um `Envio` de e-mail para ADM1 por alerta; o painel com os cinco alertas e "Atrasada desde..." nas cinco linhas |
| A-7 | Cenário 2 | positivo | o A-6 | chamar as cinco tarefas; verificar; `processar_envios()` | os cinco alertas resolvidos; os e-mails dos alertas enviados ao simulador de e-mail; o painel com "Nenhum alerta aberto." e "Em dia" |
| A-8 | Cenário 3 | positivo | `consultar_pagamento` agendada para um pagamento que o simulador não conhece (E07-04 A-9) | `processar_chamadas()` nos instantes da tabela de intervalos até passar de 24 horas; verificar; GET | `chamada_ao_provedor_falhou` aberto, com o formulário "Dar ciência" no painel |
| A-9 | Cenário 3 | positivo | o A-8 | POST "Dar ciência" pelo painel; GET; GET no histórico com `?acao=alerta.ciencia` | 302 com "Ciência registrada."; o alerta fora do painel; a entrada de ADM1 no histórico |
| A-10 | Cenário 3 | positivo | uma `ConsultaDoPagamento` com divergência `valor`, gravada diretamente (o simulador não devolve valor divergente) | verificar; outra consulta igual gravada; verificar | `consulta_com_divergencia` aberto; uma reconsulta igual não abre outro |
| A-11 | Cenário 3 | positivo | — | 5 POST em `/pagamentos/avisos/` com assinatura errada; verificar; 1 aviso válido do simulador; verificar | 401 nos cinco; `avisos_recusados_em_sequencia` aberto; depois, resolvido |
| A-12 | Cenário 4 | positivo | o e-mail do comprador falhando em todas as tentativas (apoio `email_falho`) | um evento para o comprador; `processar_envios()` até o envio ficar `falhou`; verificar; GET da central de notificações do comprador | `falha_de_mensagem` aberto; a notificação no site do comprador presente e correta; nenhum registro financeiro alterado |
| A-13 | Cenário 5 | positivo | os A-1 a A-5 | GET no histórico com `?autor=<ADM1>` | exatamente as `EntradaAuditoria` com autor ADM1 gravadas nos critérios, da mais nova para a mais antiga (a lista esperada é lida do banco); entre elas, `recebimento.registrar` e `descarte.registrar` da E14; nenhuma de outro autor |
| A-14 | Cenário 6 | negativo | os estados dos A-5, A-6 e A-8 | o comprador A e a conta do fornecedor F: GET no painel e no histórico; POST de ciência | 403 em todos; nenhuma notificação `alerta_operacional` para eles |
| A-16 | Cenário 2 (E15-R01) | positivo | todas as tarefas concluídas em `I` | avançar para `I + 20min` sem chamar nenhuma tarefa, nem a verificação; GET; chamar as dez tarefas e, por último, `verificar_operacao(timestamp=0)`; `processar_envios()`; GET | no primeiro GET, "Atrasada desde..." em Verificação operacional e nas demais; depois da retomada, nenhum `tarefa_atrasada` aberto, nenhum com a chave `verificar_operacao` em momento algum e nenhuma notificação `alerta_operacional`; o painel com "Em dia" nas onze linhas |
| A-15 | Invariantes | positivo | todos os critérios acima | no fim de cada um | as verificações sem escrita de domínio (rodada, pedido, pagamento, chamada, envio, movimentos iguais antes e depois de `verificar`); o invariante financeiro sem violação; no máximo um alerta aberto por par |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-16 | `tests/tecnicos/test_painel_ponta_a_ponta.py` |
