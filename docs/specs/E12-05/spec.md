# E12-05 — Aviso `rodada_cancelada` aos compradores

Fatia 5 de 7 da milestone **E12 — Cancelamento da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E12-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E12-01.

## Contexto e objetivo

O cancelamento administrativo é avisado aos compradores (§12). O aviso diz:
- que a rodada foi cancelada;
- se há reembolso integral ou se não há novas devoluções;
- a mensagem do administrador, quando ele a escreveu.

O evento `rodada_cancelada` já existe na matriz de canais da E04-01 (site, e-mail e WhatsApp). Esta fatia escreve o título, o corpo, o link, os destinatários e a chave.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §12 | Cancelamento administrativo: rodada cancelada, indicação de reembolso integral ou de ausência de novas devoluções e, quando o administrador desejar, mensagem customizada. A mensagem é opcional e não é motivo obrigatório. Falha de mensagem não altera o estado financeiro. |
| Especificação §7.2 | O cancelamento afeta todos os compradores da rodada. |
| Herdado da E04 | Emitir com `emitir_evento` ou `emitir_evento_para_varios`, na mesma transação do fato, com chave derivada do fato (`<evento>:<id do fato>:<conta>`), e redigir título, corpo e link do `rodada_cancelada`. |
| E04-01 | `rodada_cancelada`: destinatário comprador; site, e-mail e WhatsApp (o WhatsApp é da fase 3). |
| Cenários §16 | 41, 43, 44 |

## Escopo

**Dentro:** os destinatários, o texto, o link e a chave do aviso, emitido por `cancelar_rodada`.

**Fora:**
- O aviso `estorno` de cada devolução: é o da E10, emitido quando a devolução é autorizada ou muda de estado.
- O envio por WhatsApp (fase 3).

## Regras

1. **Quando:** na transação do cancelamento, depois das regras das E12-01 a E12-03. Um aviso por destinatário, com a chave `rodada_cancelada:<cancelamento>:<conta>`. Repetir não duplica.
2. **Destinatários:** os compradores da rodada, cada um uma vez:
   - os donos das parcelas alteradas pelo cancelamento (E12-01, regra 6);
   - os compradores dos pedidos da abertura do ciclo vigente, qualquer que seja a situação do pedido;
   - os compradores com reembolso gerado pelo cancelamento (E12-03), inclusive de ciclo anterior.

   Quem só tem quantidades pendentes na fila do fornecedor, sem reserva nem pedido nesta rodada, não recebe o aviso: o cancelamento não muda nada dele.
3. **Título:** `Rodada cancelada: <fornecedor>`, até 150 caracteres.
4. **Corpo**, em frases, nesta ordem:
   1. "A rodada de <fornecedor> foi cancelada pelo administrador."
   2. A situação do comprador:
      - com reembolso gerado para ele: "O valor pago ainda não devolvido, <valor>, será devolvido integralmente pela plataforma de pagamentos." (o valor é a soma dos reembolsos do cancelamento do comprador);
      - com reembolso, para quem tem pedido pago sem saldo novo: "As devoluções já devidas do seu pedido continuam em andamento.";
      - sem reembolso, para quem tem pedido pago: "O cancelamento não inicia novas devoluções. As devoluções já devidas continuam em andamento.";
      - para quem não tinha pedido pago:
        - com o pedido cancelado agora: "Seu pedido foi cancelado e nada foi cobrado.";
        - sem pedido: "Seus interesses nesta rodada foram removidos.";
        - em seguida, a indicação: "Reembolso integral para quem pagou." ou "Sem novas devoluções.", conforme a indicação.
   3. Com quantidades pendentes do comprador na fila do fornecedor depois do cancelamento: "Suas quantidades pendentes continuam na fila do fornecedor para as próximas rodadas."
   4. Com mensagem: "Mensagem do administrador: <mensagem>".
5. **Link:** o pedido do comprador no ciclo vigente (`/pedidos/<pk>/`), ou o do pedido com reembolso; sem pedido, o carrinho (`/carrinho/`).
6. **Privacidade:** o corpo não traz nome de outro comprador, o mínimo do fornecedor nem valores de outros pedidos (§2, §6.2).
7. **Falha de canal:** a falha de e-mail não muda o cancelamento nem o estado financeiro (E04). O aviso no site é gravado na transação.

## Decisões técnicas

- **Destinatários pelo efeito.** "Todos os compradores da rodada" são os que têm reserva, pedido ou reembolso nela. A fila do fornecedor não é da rodada (§5.2) e não muda.
- **Uma frase por situação.** O §12 exige a indicação de reembolso integral ou de ausência de novas devoluções. O texto diz isso a cada um no que o afeta, sem prometer devolução a quem não pagou.

## Invariantes

- No máximo um aviso `rodada_cancelada` por cancelamento e comprador.
- Nenhum aviso com valor de outro comprador.

## Casos-limite

- **Comprador suspenso com pedido pago:** recebe o aviso (o suspenso consulta os pedidos pagos, §2).
- **Mensagem vazia:** sem a frase da mensagem.

## Dependências e decisões em aberto

Depende das E12-01 a E12-03 e da E04. Nenhuma decisão em aberto.

## Correção da revisão: R02, o pagante de ciclo anterior (2026-11-01)

Origem: revisão independente sobre `8e236e5` (`docs/specs/E12-07/review.md`, "R02 — importante").

Nenhuma regra comercial muda. A regra 4 já manda informar a quem tem pedido pago que "As devoluções já devidas continuam em andamento". O defeito está na fonte: o código só considerava pagante quem tinha pedido pago na abertura vigente, ou, com reembolso, um pedido sem saldo. Um comprador com pedido pago de ciclo anterior (rodada que voltou para interesse) e devolução de mínimo pendente recebia, sem reembolso, o texto de quem não pagou e o link do carrinho.

**Regra 2-A — quem pagou na rodada:**
- **Definição:** o comprador tem pedido pago na rodada quando algum pedido dele, de qualquer abertura da rodada, está `pago` na leitura feita sob as travas do cancelamento (E12-02, regra 2 reescrita).
- **Mesma fonte nas duas indicações:** a classificação não depende de `com_reembolso` nem de haver reembolso gerado.

**Regra 2, complemento — destinatários:**
- **Inclusão:** entram também os compradores com pedido pago na rodada (regra 2-A), em qualquer abertura e nas duas indicações. O cancelamento muda o estado da rodada desses pedidos e o que a página deles mostra (E12-06), e por isso os afeta.
- **Exclusão mantida:** quem só tem quantidades pendentes na fila do fornecedor, sem reserva alterada, sem pedido da abertura vigente e sem pedido pago na rodada, continua sem aviso.
- **Nenhum dado novo:** o aviso não cria, não autoriza e não altera devolução. O ramo sem reembolso continua sem movimento no livro (E12-02, regra 10).

**Regra 4, complemento — a situação do comprador:**
- **Pagante sem reembolso gerado:** "pedido pago" nas frases da regra 4 é o da regra 2-A.
  - Sem reembolso, ele recebe "O cancelamento não inicia novas devoluções. As devoluções já devidas continuam em andamento.";
  - com reembolso e sem saldo, ele recebe "As devoluções já devidas do seu pedido continuam em andamento.".
- **Quem não pagou:** as frases de "para quem não tinha pedido pago" só valem para quem não tem pedido pago na rodada.
- **Pagante de ciclo anterior com pedido cancelado agora:**
  - **caso:** o comprador tem pedido pago de ciclo anterior e o pedido dele da abertura vigente foi cancelado agora (estava aguardando pagamento);
  - **frases:** depois da frase 1, "Seu pedido do ciclo atual foi cancelado e nada foi cobrado nele." e, em seguida, a frase de pagante da indicação (com o valor, quando houver reembolso gerado).

**Regra 5, reescrita — link, na ordem:**
1. o pedido do comprador na abertura vigente;
2. senão, o pedido com reembolso do cancelamento de menor `pk`;
3. senão, o pedido pago na rodada de maior `pk` (o mais recente);
4. senão, `/carrinho/`.

Critérios: A-8 a A-11 (`acceptance.md`).
