# E13-04 — Telas do administrador: o pedido consolidado, as tentativas e o botão Reenviar pedido

Fatia 4 de 8 da milestone **E13 — Pedido formal, repasse e portal do fornecedor**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E13-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E13-01.

## Contexto e objetivo

O administrador vê:
- o pedido consolidado;
- o envio formal e as tentativas registradas, automáticas e manuais, com as falhas de comunicação;
- o botão **Reenviar pedido**, disponível depois de três falhas ou de um envio bem-sucedido (§13).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, administrador | Visualização do pedido consolidado, envio formal, tentativas registradas (automáticas e manuais), falhas de comunicação e botão **Reenviar pedido**, disponível depois de três falhas ou de um envio bem-sucedido. |
| Especificação §12 | O aviso de falha dá acesso ao botão **Reenviar pedido**. |
| Infraestrutura 4.14 | O reenvio é recusado no servidor durante o ciclo automático. Cada acionamento carrega um token de requisição único: duplo clique e reenvio do formulário geram um único envio. |
| Infraestrutura 9.2, L-13 | A aceitação pelo serviço de e-mail não comprova entrega. |
| Cenários §16 | 69, 70, 92, 93, 94, 95 |
| Testes técnicos | T-29, T-41, T-54 (pela rota) |

## Escopo

**Dentro:** a página do pedido formal, a rota de reenvio e o bloco do pedido formal na página da rodada.

**Fora:**
- O bloco da previsão (E13-05) e o das saídas (E13-06), que entram nesta mesma página.
- O painel geral do administrador (E15).

## Regras

**Página** `GET administracao/rodadas/<pk>/pedido-formal/` (nome `rodadas_pedido_formal`):

1. **Acesso:** `somente_administrador`. Comprador e fornecedor recebem a recusa padrão (403). Sem pedido formal na rodada: 404.
2. **Cabeçalho:** "Pedido formal nº <pk>", o fornecedor, a rodada, o ciclo e "Emitido em <data hora> (horário de Brasília)".
3. **Pedido consolidado:** uma tabela com as linhas do pedido formal (produto, quantidade com a unidade, caixas ou "—", preço unitário e valor total) e o total dos produtos. Os valores vêm do `PedidoFormal` e das linhas, nunca recalculados.
4. **Conteúdo enviado:** o assunto e o corpo gravados, num bloco pré-formatado.
5. **Envio:**
   - o destino atual (e-mail do pedido do fornecedor);
   - a situação do ciclo, com um destes textos:
     - `em_andamento`: "Envio automático em andamento: tentativa <automaticas + 1> de 3 prevista para <data hora>.";
     - `concluido_com_sucesso`: "Envio automático concluído: aceito pelo serviço de e-mail.";
     - `concluido_com_falhas`: "Envio automático concluído sem sucesso depois de 3 tentativas.";
     - `interrompido`: "Envio interrompido: a rodada foi cancelada.";
   - a nota "A aceitação pelo serviço de e-mail não comprova a entrega ao fornecedor." (L-13).
6. **Tentativas:** uma tabela de todas as tentativas, por `numero`:
   - nº;
   - tipo ("Automática <ordem>/3" ou "Manual");
   - início em Brasília;
   - resultado ("Aceito pelo serviço de e-mail" ou "Falha");
   - resposta;
   - destino;
   - o nome do administrador, nas manuais.

   Sem tentativa: "Nenhuma tentativa ainda.".
7. **Botão Reenviar pedido:**
   - **disponível** (`pode_reenviar`, E13-03): um formulário `POST` para a rota de reenvio, com o token CSRF, um campo oculto `token` com um UUID novo gerado a cada carregamento da página e o botão "Reenviar pedido". O texto ao lado diz "Cada acionamento faz uma única tentativa com o mesmo pedido formal.";
   - **indisponível:** sem formulário. Em seu lugar, a mensagem da recusa (E13-03, regra 5).

**Rota** `POST administracao/rodadas/<pk>/pedido-formal/reenviar/` (nome `rodadas_pedido_formal_reenviar`):

8. **Acesso:** `somente_administrador`; `GET`: 405. Sem pedido formal: 404.
9. **Campos:** só `token` e o token CSRF são lidos; os demais são ignorados (o reenvio não recebe conteúdo). Sem `token` ou com um token inválido: a página com 400 e "Recarregue a página e tente de novo.", sem chamar o envio.
10. **Chamada:** `reenviar_pedido_formal(request.user, pedido_formal, token=...)`. Respostas:
    - **tentativa nova com sucesso:** redireciona para a página com "Reenvio registrado: aceito pelo serviço de e-mail.";
    - **tentativa nova com falha:** redireciona com "Reenvio registrado: o serviço de e-mail recusou (<resposta>).";
    - **token já usado** (`nova` falso): redireciona com "Este reenvio já tinha sido registrado.", sem envio novo;
    - **`ReenvioRecusado`:** a página com 409 e a mensagem da recusa;
    - **`ConsultaAoProvedorFalhou`:** a página com 503 e "Não foi possível consultar o provedor; o pedido não foi reenviado. Tente de novo.";
    - **`PermissionDenied`:** a recusa padrão.

**Página da rodada** (`administracao/rodadas/<pk>/estoque/`, E03 e E12-06):

11. **Bloco "Pedido formal":** em qualquer etapa, quando a rodada tem pedido formal: o nº, o total dos produtos, a situação do envio (o texto da regra 5) e o link "Ver pedido formal" para a página da regra 1.

## Decisões técnicas

- **Token por carregamento da página.** Ele identifica a solicitação. O duplo clique e o reenvio do mesmo formulário mandam o mesmo token e geram um único envio. Depois do redirecionamento, a página traz um token novo, então um novo clique é um novo acionamento legítimo (cenário 70).
- **Sem nova autenticação.** A infraestrutura 4.14 não a exige, e o reenvio não move dinheiro nem escolhe origem de recursos (infraestrutura 3.2). A proteção é a do administrador (`somente_administrador`).
- **Campos extras ignorados.** Diferente do cancelamento (E12-06), o T-29 e o T-41 não pedem recusa de campo extra. Ignorá-los garante que nenhum dado da requisição mude o conteúdo.

## Invariantes

- A tela nunca edita o pedido formal, as linhas ou as tentativas.
- O conteúdo exibido é o gravado.

## Dependências e decisões em aberto

- Depende das E13-01 a E13-03 e da E12-06 (página da rodada).
- Nenhuma decisão em aberto.
