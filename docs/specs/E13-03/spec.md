# E13-03 — O reenvio manual do pedido formal

Fatia 3 de 8 da milestone **E13 — Pedido formal, repasse e portal do fornecedor**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E13-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E13-01.

## Contexto e objetivo

Concluído o ciclo automático, com sucesso ou com três falhas, o administrador pode reenviar o mesmo pedido formal pelo botão **Reenviar pedido** (§10, Q-3, R-4, R-7):
- cada acionamento faz exatamente uma tentativa e nunca inicia um novo ciclo automático;
- enquanto o ciclo automático está em andamento, o reenvio é recusado;
- acionamentos repetidos da mesma solicitação (duplo clique) geram um único envio, e um acionamento novo gera uma tentativa nova;
- duas tentativas do mesmo pedido formal nunca saem ao mesmo tempo.

Esta fatia entrega o serviço. A tela é da E13-04.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §10 | Depois de três falhas, o botão **Reenviar pedido**; também depois de um envio bem-sucedido. Cada acionamento executa uma única tentativa; tentativas manuais não iniciam outro ciclo automático. O reenvio usa o mesmo pedido formal, sem gerar outro nem alterar produtos, quantidades ou valores. Tudo registrado e auditável. Proteção contra duplicação por concorrência ou acionamentos repetidos, sem impedir reenvios legítimos. Durante o ciclo automático, sem reenvio manual. |
| Infraestrutura 4.14 | Durante o ciclo (tentativa agendada ou em execução), o reenvio manual é recusado no servidor; o estado é lido sob a mesma trava dos envios. Cada acionamento carrega um token único, gravado com `UNIQUE`: o mesmo token gera um único envio; um token novo, uma tentativa nova. Um envio em andamento fica sob trava. |
| Infraestrutura 4.2 | Consulta obrigatória antes do envio do pedido formal. |
| Infraestrutura 5 | `UNIQUE` no token de reenvio do pedido formal. |
| Herdado da E12 | A rodada `cancelada` não permite reenviar. |
| Cenários §16 | 69 (reenvio com o mesmo pedido), 70, 92, 93, 94, 95, 118, 119 |
| Testes técnicos | T-29, T-41, T-54, T-55 |

## Escopo

**Dentro:** o serviço `reenviar_pedido_formal`, a exceção `ReenvioRecusado`, a auditoria e as corridas.

**Fora:** a tela e o token do formulário (E13-04).

## Regras

`reenviar_pedido_formal(autor, pedido_formal, *, token) -> ReenvioRegistrado`:

1. **Permissão:** só o administrador ativo; senão `PermissionDenied`, sem escrita.
2. **Fora de transação:** a consulta ao provedor vem antes da transação (`exigir_fora_de_transacao`, E07-06); dentro de uma transação, `RuntimeError`.
3. **Token:** um UUID (texto na forma canônica ou `uuid.UUID`). Outro valor: `ReenvioRecusado("token_invalido")`, sem escrita.
4. **Mesmo token, mesmo resultado:**
   - se já existe uma tentativa com o token, para esse pedido formal, ela é devolvida, sem consulta, envio ou escrita;
   - se o token existe em outro pedido formal: `ReenvioRecusado("token_invalido")`.
5. **Conferências prévias, sem trava**, na ordem (a primeira que falha vale):
   - a rodada `cancelada`: `ReenvioRecusado("rodada_cancelada")`, com a mensagem "A rodada foi cancelada; o pedido formal não é reenviado.";
   - o envio `em_andamento`: `ReenvioRecusado("ciclo_em_andamento")`, com a mensagem "O envio automático ainda está em andamento; o reenvio fica disponível quando ele terminar.";
   - o envio `interrompido`: `ReenvioRecusado("rodada_cancelada")` (só existe por cancelamento).
6. **Consulta prévia:** `consultar_antes_de_decidir` para cada pedido da abertura do ciclo, por `pk`, como na E13-02. `ConsultaAoProvedorFalhou` sobe para quem chamou, sem escrita (a tela traduz, E13-04).
7. **Transação e travas:**
   - o `EnvioDoPedidoFormal`, com `select_for_update()`, **esperando**: dois reenvios do mesmo pedido formal se executam um depois do outro (cenário 119);
   - a `Rodada`, com `select_for_update(no_key=True)`, como na E13-02.
8. **Conferências sob as travas:**
   - o token de novo: se outra transação já gravou a tentativa com ele, ela é devolvida, sem envio (cenários 70 e 95);
   - as conferências da regra 5 de novo, relidas.
9. **Tentativa:**
   - `enviar_email(fornecedor.email_pedido, assunto, corpo)`, com o conteúdo gravado e a trava retida;
   - a `TentativaDeEnvioDoPedidoFormal` `manual`, com o próximo `numero`, `ordem_automatica` nulo, o `autor`, o `token`, o destino e a resposta;
   - uma falha do serviço é registrada (`falha`) e devolvida como a tentativa, sem exceção (cenário 93).
10. **Nada mais muda:**
    - o `EnvioDoPedidoFormal` não muda: o estado, `automaticas` e a próxima tentativa continuam os mesmos, então nenhuma tentativa automática é agendada (cenários 92 e 93, T-41);
    - o `PedidoFormal`, as linhas e o conteúdo não mudam, e nenhum pedido formal novo é criado.
11. **`IntegrityError` no token:** se, apesar da regra 8, a gravação colidir com o `UNIQUE` do token, a transação é desfeita e a tentativa existente é relida e devolvida. O `UNIQUE` garante uma tentativa registrada por token; a garantia de um único envio é a releitura do token sob a trava (regra 8), porque o serviço de e-mail não tem chave de idempotência.
12. **Auditoria `pedido_formal.reenviar`**, na transação da tentativa: o autor, o pedido formal, o número e o resultado da tentativa e o UUID do acionamento, sob a chave `acionamento`. A auditoria recusa chaves com o termo `token`, que é reservado a segredos (`TERMOS_DE_SEGREDO`, E01). O UUID não é segredo: ele só identifica a solicitação para a idempotência. Por isso o valor é gravado, com outro nome de chave.
13. **Sem aviso:** a falha de um reenvio manual não emite `falha_no_pedido_formal` (§12 avisa só depois da terceira automática). O botão continua disponível (cenário 93).

## Interface

- `reenviar_pedido_formal(autor, pedido_formal, *, token) -> ReenvioRegistrado`, com `tentativa` (a `TentativaDeEnvioDoPedidoFormal`) e `nova` (falso quando o token já tinha gerado a tentativa, regras 4, 8 e 11). "Devolver a tentativa", nas regras, é devolver esse resultado.
- `class ReenvioRecusado(Exception)`, com `codigo` (`token_invalido`, `rodada_cancelada`, `ciclo_em_andamento`) e a mensagem da tela.
- `pode_reenviar(pedido_formal) -> tuple[bool, str]`: a conferência da regra 5, sem trava, para a tela mostrar ou explicar o botão.

## Decisões técnicas

- **Recusar sem esperar durante o ciclo, e esperar entre reenvios.**
  - **Contra a tentativa automática:** a conferência prévia lê o estado gravado. Uma tentativa automática só existe com o envio `em_andamento`, então um reenvio simultâneo a ela é recusado sem esperar a trava (cenário 118). A conferência sob a trava repete a leitura.
  - **Entre reenvios:** o ciclo já terminou e a trava é esperada, então os dois se executam em sequência (cenário 119).
- **O token vem da tela.** Cada carregamento do formulário gera um token. O duplo clique reenvia o mesmo token; um novo acionamento, depois de recarregar a página, traz outro (E13-04).
- **A consulta no reenvio.** É a mesma regra do envio automático (infraestrutura 4.2). Uma falha do provedor bloqueia o reenvio sem registrar tentativa, porque nada foi entregue ao serviço de e-mail.

## Invariantes

- Uma tentativa por token; um token por tentativa manual.
- Nenhuma tentativa manual com o envio `em_andamento` ou a rodada cancelada.
- Nenhuma tentativa manual muda o estado do ciclo automático.
- O conteúdo enviado é sempre o gravado no `PedidoFormal`.

## Casos-limite e concorrência

- **Reenvio logo depois da terceira falha:** aceito (cenário 69).
- **Reenvio depois do sucesso automático:** aceito, com uma tentativa (cenário 92).
- **Reenvio que falha:** registrado, botão disponível, nenhum ciclo novo (cenário 93).
- **Reenvio entre a primeira e a terceira falha:** recusado com `ciclo_em_andamento` (cenário 94).
- **Mesmo token em paralelo:** um envio; as duas chamadas devolvem a mesma tentativa (cenário 95).
- **Tokens distintos em paralelo:** duas tentativas, em sequência, com intervalos de envio que não se sobrepõem (cenário 119, T-55).
- **Tentativa automática em execução e reenvio:** recusado; nenhuma tentativa a mais (cenário 118).
- **Cancelamento da rodada depois do fim do ciclo:** o reenvio seguinte é recusado com `rodada_cancelada`.

## Dependências e decisões em aberto

- Depende das E13-01 e E13-02.
- Nenhuma decisão em aberto.

## Esclarecimento da implementação (2026-11-09)

A regra 12 foi reescrita para nomear a chave da auditoria (`acionamento`). A implementação que já grava o UUID sob essa chave está de acordo com a regra.
