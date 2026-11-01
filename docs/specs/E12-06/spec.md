# E12-06 — Telas do cancelamento: administrador e comprador

Fatia 6 de 7 da milestone **E12 — Cancelamento da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E12-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E12-01.

## Contexto e objetivo

O administrador cancela a rodada inteira pela página da rodada, indicando se há reembolso devido (§13). Depois do cancelamento:
- a página da rodada mostra o registro;
- a lista de devoluções (E10-07) mostra as devoluções já autorizadas pela indicação;
- o comprador vê no pedido o que aconteceu.

A rota recusa lista de compradores, aceita requisição sem motivo e recusa comprador e fornecedor (T-16).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, administrador | Início de etapas, definição de frete, prorrogação e cancelamento da rodada inteira, com indicação de reembolso devido. Sem edição de pedidos congelados. |
| Especificação §13, comprador | Histórico de pedidos, pagamentos, estornos e retirada por item. |
| Especificação §2 | Comprador suspenso consulta os pedidos pagos. Isolamento entre compradores. |
| Infraestrutura 4.8 | Só o admin, verificado no servidor, com nova autenticação (proteção de acesso, não etapa de aprovação). A ação recebe só a rodada e a indicação; mensagem opcional. |
| Infraestrutura 8, T-16 | A rota de cancelamento recusa lista de compradores e aceita requisição sem motivo. Comprador e fornecedor recebem recusa. |
| Cenários §16 | 42, 45 |

## Escopo

**Dentro:**
- A rota e o formulário de cancelamento.
- O bloco do cancelamento na página da rodada.
- A marcação das devoluções do cancelamento na lista de devoluções.
- O texto do pedido do comprador e o painel dos pedidos.

**Fora:** o painel administrativo geral (E15).

## Regras

**Rota:** `POST administracao/rodadas/<pk>/cancelar/` (nome `rodadas_cancelar`).

1. **Proteção:** `exige_reautenticacao_por_passkey`, como a apuração (E11-07). Sem nova autenticação recente, redireciona para ela sem chamar o serviço. Comprador e fornecedor: a recusa de `somente_administrador`, sem escrita. `GET`: 405.
2. **Campos aceitos:** `reembolso` (obrigatório, `sim` ou `nao`), `mensagem` (opcional) e o token CSRF. Qualquer outro campo, como `compradores`, `comprador`, `motivo` ou `fornecedor`, dá 400 com "O cancelamento vale para a rodada inteira e só recebe a indicação de reembolso e a mensagem opcional.", sem chamar o serviço. Sem `reembolso`, ou com outro valor: a página com 400 e "Informe se existe reembolso devido."
3. **Chamada:** `cancelar_rodada(request.user, rodada, com_reembolso=..., mensagem=...)`. Respostas:
   - sucesso: redireciona para a página da rodada com "Rodada cancelada." e, com reembolso, "As devoluções integrais foram geradas e autorizadas.";
   - `CancelamentoRecusado`: a página com 409 e a mensagem da recusa;
   - `ConsultaAoProvedorFalhou`: a página com 503 e "Não foi possível consultar o provedor; nada foi cancelado. Tente de novo.";
   - `PermissionDenied`: a recusa padrão.

**Página da rodada** (`administracao/rodadas/<pk>/estoque/`):

4. **Rodada cancelável** (etapas da tabela da E12-01): o bloco "Cancelar rodada" com:
   - o aviso "O cancelamento vale para todos os compradores da rodada e não pode ser desfeito.";
   - a escolha obrigatória, sem opção marcada: "Com reembolso integral para quem pagou" e "Sem reembolso (não inicia novas devoluções)";
   - o campo "Mensagem aos compradores (opcional)", até 1000 caracteres;
   - o botão "Cancelar rodada".

   O bloco não pede motivo nem lista de compradores.
5. **Rodada cancelada:**
   - o bloco "Rodada cancelada" com o momento em Brasília, o nome do administrador, a indicação ("com reembolso" ou "sem reembolso") e a mensagem, se houver;
   - com reembolso, a lista das devoluções geradas: pedido, comprador, valor e a situação da E10 (por exemplo "devida", "solicitada", "concluída"), com o link para `financeiro/devolucoes/<obrigacao>/`;
   - sem os blocos de ações das outras etapas (fechamento, pagamento, apuração);
   - o estoque e o progresso só para leitura;
   - os dados anteriores (pedidos, pagamentos, apuração, devoluções) continuam consultáveis (cenário 45).

**Lista e detalhe de devoluções (E10-07):**

6. **Devoluções do cancelamento:** uma obrigação de motivo `cancelamento_da_rodada` sem parcela não oferece o botão "Autorizar". Ela mostra "Autorizada pelo cancelamento da rodada".
   - Com falta de cobertura, acrescenta: "aguardando cobertura".
   - Coberta, mostra: "aguardando o envio ao provedor".

   As ações de cobertura da E09/E10 continuam disponíveis.

**Comprador:**

7. **Pedido de rodada cancelada** (`pedidos/<pk>/`):
   - pedido pago, com reembolso do cancelamento: "A rodada foi cancelada pelo administrador. O valor será devolvido integralmente." A seção de estornos (E10-07) mostra o reembolso e a situação real;
   - pedido pago, sem reembolso novo: "A rodada foi cancelada pelo administrador." e, sem reembolso, "O cancelamento não inicia novas devoluções."; as devoluções já devidas aparecem na seção de estornos;
   - pedido cancelado pelo cancelamento: "Cancelado (rodada cancelada)" e "Nada foi cobrado neste pedido.";
   - a mensagem do administrador, se houver;
   - sem o botão "Pagar".

   A fonte é o `CancelamentoDaRodada` e os reembolsos dele, nunca outro comprador.
8. **Painel dos pedidos do administrador** (E08-05/E11-07): o pedido cancelado mostra "Cancelado (rodada cancelada)".
9. **Carrinho:** a rodada cancelada não aparece como rodada ativa. As quantidades pendentes do comprador no fornecedor continuam visíveis e removíveis (E05-05).

## Decisões técnicas

- **A recusa de campo extra é explícita.** O T-16 pede que a rota recuse lista de compradores. Ignorar o campo em silêncio seria aceitar a requisição. Por isso a rota recusa qualquer campo fora dos três aceitos.
- **Nenhuma opção marcada.** A indicação é decisão do administrador a cada cancelamento (§7.2), e o servidor exige o valor (E12-01).

## Invariantes

- Nenhuma tela edita pedido congelado.
- Nenhuma tela mostra dado de outro comprador ao comprador.

## Dependências e decisões em aberto

Depende das E12-01 a E12-05, da E10-07 e da E11-07. Nenhuma decisão em aberto.

## Correção da revisão: R01, a página do pedido depois de um retorno ao interesse (2026-11-01)

Origem: revisão independente sobre `8e236e5` (`docs/specs/E12-07/review.md`, "R01 — importante").

Nenhuma regra comercial muda. Pela E12-01 (regra 6), o cancelamento zera as reservas da rodada. A página de um pedido pago de ciclo anterior, porém, ainda mostrava o efeito da apuração de retorno como atual: "seus interesses continuam reservados na rodada" (E11-05/E11-07). O registro histórico da apuração está certo. O defeito é apresentar como vigente um efeito que o cancelamento superou.

**Regra 7-A — pedido de rodada cancelada com apuração anterior:**
- **Estado vigente primeiro:** quando a rodada do pedido tem `CancelamentoDaRodada`, o bloco do cancelamento (regra 7) vem antes de qualquer efeito da apuração e é o estado vigente da página.
- **Retorno ao interesse como histórico:** o efeito de retorno ao interesse da apuração do pedido (E11-07) aparece como fato anterior, com o texto "Antes do cancelamento, a apuração deste ciclo levou a rodada de volta para interesse, e o valor pago deste pedido será devolvido integralmente."
  - Sem nenhuma promessa de reserva atual: a frase "seus interesses continuam reservados na rodada" não aparece em nenhuma indicação.
  - O que vale depois do cancelamento é a regra 9 (carrinho) e a fila de pendentes.
- **Fonte:** a existência do `CancelamentoDaRodada` da rodada do pedido, lida na montagem da página.
  - A informação de contas impedidas da apuração (`retorno.contas_impedidas`, E11-05 regra 2-A) continua registrada e não muda.
  - Não se apaga nem se reescreve nenhum registro da apuração.
- **Demais efeitos da apuração:** o cancelamento por falta de pagamento e as caixas incompletas com o estorno proporcional continuam como na E11-07. A fila de pendentes não é afetada pelo cancelamento (E12-01, regra 6).
- **Pago com reembolso, sem saldo novo:** o pedido pago sem reembolso do cancelamento numa rodada cancelada com reembolso (por exemplo, já coberto pela devolução de mínimo) mostra, depois de "A rodada foi cancelada pelo administrador.", a frase "As devoluções já devidas deste pedido continuam em andamento.". É o mesmo fato do aviso (E12-05, regra 4).
- **Fora do pedido:** pedidos, apuração, reembolsos e devoluções anteriores continuam consultáveis (cenário 45). A seção de estornos mostra a devolução de mínimo com a situação real.

Critérios: A-20 a A-22 (`acceptance.md`).
