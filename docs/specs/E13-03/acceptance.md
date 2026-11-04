# E13-03 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos**, a partir do AF (E13-01) e da tarefa da E13-02:
  - **AF-sucesso:** a primeira tentativa automática aceita (E13-02 A-1);
  - **AF-falhas:** três falhas automáticas (E13-02 A-3);
  - **AF-meio:** uma falha automática, com a segunda agendada (`em_andamento`).
- **Tokens:** gerados no teste com `uuid.uuid4()`.
- **Chamada:** `reenviar_pedido_formal(admin, pedido_formal, token=...)`, fora de transação.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 69, T-41 | positivo | AF-falhas; e-mail aceito agora | reenviar com o token t1 | uma tentativa `manual` nº 4, `sucesso`, com o autor, o token t1 e o destino; um e-mail com o assunto e o corpo iguais aos gravados; o envio continua `concluido_com_falhas`, `automaticas = 3` e sem próxima; o `PedidoFormal` e as linhas iguais, campo a campo; nenhum `PedidoFormal` novo. **Red esperado:** a função não existe |
| A-2 | Cenário 92, Q-3 | positivo | AF-sucesso | reenviar com t1; depois rodar a tarefa da E13-02 em `+1 dia` | uma tentativa manual nº 2 com `sucesso`; o envio continua `concluido_com_sucesso`; a tarefa não faz nenhuma tentativa |
| A-3 | Cenário 93 | positivo | AF-falhas; `BackendQueFalha` | reenviar com t1; depois rodar a tarefa | a tentativa manual com `falha` e a resposta; nenhuma exceção; nenhuma tentativa automática nova; nenhuma notificação `falha_no_pedido_formal` além da do ciclo; `pode_reenviar` continua verdadeiro |
| A-4 | Cenário 94, T-54 | negativo | AF-meio | reenviar com t1 | `ReenvioRecusado("ciclo_em_andamento")`, com a mensagem da regra 5; nenhuma consulta ao provedor, nenhuma tentativa e nenhum e-mail |
| A-5 | T-54 | negativo | AF antes da primeira tentativa automática (`automaticas = 0`) | reenviar | `ciclo_em_andamento`, sem escrita |
| A-6 | Cenário 70, T-29 | positivo | AF-falhas | reenviar com t1; reenviar de novo com t1 | as duas chamadas devolvem a mesma tentativa; um e-mail; uma tentativa manual |
| A-7 | Cenário 70, T-29 | positivo | o A-6 | reenviar com t2 | uma segunda tentativa manual (nº 5) e um segundo e-mail, com o conteúdo idêntico ao primeiro e ao gravado |
| A-8 | Regra 3 | negativo | AF-falhas | reenviar com `"abc"`, com `""` e com `None` | `ReenvioRecusado("token_invalido")` nos três, sem escrita |
| A-9 | Regra 4 | negativo | dois pedidos formais (duas rodadas AF de fornecedores distintos, os dois com o ciclo concluído); um reenvio do primeiro com t1 | reenviar o segundo com t1 | `token_invalido`; nenhuma tentativa no segundo |
| A-10 | Herdado E12 | negativo | AF-sucesso; a rodada cancelada depois | reenviar | `ReenvioRecusado("rodada_cancelada")`, sem escrita nem consulta |
| A-11 | Regra 1 | negativo | AF-falhas | reenviar com um comprador, com o fornecedor (conta vinculada a F) e com `None` | `PermissionDenied` nos três, sem escrita |
| A-12 | Regra 2 | negativo | AF-falhas | reenviar dentro de `transaction.atomic()` aberto pelo teste | `RuntimeError`, sem escrita |
| A-13 | Infra 4.2 | negativo | AF-falhas; `falhar_proximas(1, operacao="buscar_por_referencia")` | reenviar com t1 | `ConsultaAoProvedorFalhou`; nenhuma tentativa; nenhum e-mail; reenviar de novo com t1, com o provedor normal, faz a tentativa |
| A-14 | Auditoria | positivo | o A-1 | ler a auditoria | `pedido_formal.reenviar`, com o administrador, o pedido formal, o número 4, `sucesso` e o token |
| A-15 | Cenário 95, T-29 | concorrência | AF-falhas; a primeira chamada com t1 pausada dentro de `enviar_email`, com a trava retida | uma segunda chamada com t1 numa segunda conexão; depois a primeira retomada | a segunda espera a trava e devolve a tentativa gravada pela primeira; um e-mail; uma tentativa |
| A-16 | Cenário 119, T-55 | concorrência | AF-falhas; a primeira chamada com t1 pausada dentro de `enviar_email` | a segunda chamada com t2 numa segunda conexão (confirmada esperando com `esperar_outra_conexao_na_trava()`); depois a primeira retomada | duas tentativas manuais (nº 4 e 5); a `iniciada_em` da 5 não é anterior à `concluida_em` da 4 (os envios não se sobrepõem); dois e-mails idênticos ao gravado |
| A-17 | Cenário 118, T-55 | concorrência | AF com `BackendQueFalha` até a terceira tentativa; a terceira tentativa automática pausada dentro de `enviar_email`, com as travas retidas | `reenviar_pedido_formal` com t1 numa segunda conexão | a chamada é recusada com `ciclo_em_andamento` **sem esperar** a trava (termina com a tentativa automática ainda pausada); depois, retomada a automática: três tentativas automáticas e nenhuma manual |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-14 | `tests/tecnicos/test_pedido_formal_reenvio.py` |
| A-15 a A-17 | `tests/tecnicos/test_pedido_formal_reenvio.py`, com transações PostgreSQL reais |
