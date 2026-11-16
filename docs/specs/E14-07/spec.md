# E14-07 — O que o comprador e o fornecedor veem

Fatia 7 de 8 da milestone **E14 — Recebimento, ocorrências, retirada e descarte**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E14-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E14-01.

## Contexto e objetivo

O comprador consulta, no histórico dos pedidos, os estornos e a retirada por item (§13). Ele não pode modificar o pedido para informar faltas nem pedir substituição (§10, cenário 50). O fornecedor continua vendo só a lista fechada da E13-07 (§2, 17.9): nenhum dado de recebimento, ocorrência, retirada ou descarte, porque esses dados são por comprador.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, comprador | Histórico de pedidos, pagamentos, estornos e retirada por item. Regras e endereço. |
| Especificação §10, §7.1 | O comprador não modifica o pedido para informar faltas nem pede substituição. Nenhuma rota permite alterar pedido congelado (cenário 47). |
| Especificação §2, 17.9 | O comprador suspenso consulta os pedidos pagos. O fornecedor vê só os dados da lista; nada de compradores. |
| Especificação §11 | Prazo de sete dias a partir da liberação. |
| Infraestrutura 4.9, 4.13 | Nenhuma rota de comprador para ocorrências. Serializadores do fornecedor com lista fechada de campos. |
| Cenários §16 | 19, 21, 50, 67 |

## Escopo

**Dentro:**
- O bloco "Entrega e retirada" na página do pedido do comprador (`pedidos/<pk>/`).
- As recusas do comprador e do fornecedor nas rotas da E14.
- A confirmação de que o portal do fornecedor não muda.

**Fora:**
- As telas do administrador (E14-06).
- O aviso de liberação (E14-04).

## Regras

**Página do pedido** `pedidos/<pk>/` (E08, com a previsão da E13-05), para o dono do pedido, ativo ou suspenso:

1. **Ocorrências**, quando o pedido tem alguma: a seção "Ocorrências de entrega", com uma linha por ocorrência:
   - data, produto, tipo ("Faltante", "Incorreto" ou "Não entregue"), quantidade com a unidade;
   - o reembolso total da ocorrência ("Reembolso de R$ <total>") e a situação da devolução: "Devida" quando `situacao_da_devolucao` (E10) é `devida`, e senão o rótulo de `SituacaoDaParcela` ("Solicitada", "Concluída" etc.); "Sem valor a devolver" no valor zero.

   Sem o nome do administrador.
2. **Retirada**, quando a rodada está `disponivel_para_retirada` e o pedido é válido:
   - "Retirada liberada em <data hora>. Retire até <data hora> (horário de Brasília).";
   - "Endereço: <endereço da liberação>", com as quebras de linha;
   - por item, "Pedido", "Reembolsado", "Retirado", "Descartado" e "A retirar", os valores de `situacao_da_retirada` (reembolsado = na apuração + em ocorrências);
   - depois do prazo final, com saldo: "Prazo de retirada encerrado em <data hora>. Fale com o administrador sobre os itens não retirados." Não há rótulo de descartado sem `DescarteDeItem` (cenário 23).
3. **Antes da liberação** (pedido válido em `aguardando_fornecedor`): sem a seção de retirada; a previsão da E13-05 continua.
4. **Sem formulário:** a página não tem campo nem botão para informar falta, troca, substituição, retirada ou descarte.
5. **Pedido não válido** (cancelado, ou de rodada que voltou ao interesse): sem as seções desta fatia.
6. **Outro comprador:** a página do pedido de outro comprador continua recusada como na E08.

**Recusas por acesso direto** (cenário 50, infraestrutura 4.9):

7. **Comprador:** as rotas da E14-06 e `administracao/retirada/endereco/` recusam o comprador com 403, sem escrita, inclusive com o pk de um item do próprio pedido.
8. **Rotas do comprador existentes:** `POST` em `pedidos/<pk>/` e `pedidos/<pk>/pagar/` com campos de ocorrência (`item`, `tipo`, `quantidade`) não criam `OcorrenciaDeEntrega`, `Reembolso` nem `RetiradaDeItem`, e não mudam o pedido.

**Fornecedor** (E13-07):

9. **Recusas:** as rotas da E14-06 e `administracao/retirada/endereco/` recusam a conta de fornecedor com 403; `regras/` também (E14-03).
10. **Portal sem mudança:**
    - na rodada `disponivel_para_retirada`, `fornecedor/rodadas/<pk>/` mostra a etapa "Disponível para retirada" e o pedido formal (E13-07, regra 8), sem previsão;
    - a exportação CSV é a mesma;
    - as chaves dos serializadores continuam as listas da E13-07: nenhuma chave nova de recebimento, ocorrência, retirada, descarte ou endereço.

## Interface

Sem rota nova. A página `pedidos/<pk>/` ganha as seções, montadas a partir de `situacao_da_retirada`, das ocorrências do pedido e de `situacao_da_devolucao`.

## Decisões técnicas

- **Reembolsado em uma coluna só.** Para o comprador, o que importa é quanto foi devolvido e quanto falta retirar. A separação entre apuração e ocorrência aparece na lista de ocorrências.
- **O fornecedor não vê o recebimento.** Recebimento por produto até poderia ser agregado, mas a §2 e a 17.9 fecham a lista ("nada além disso"). Incluir campos exigiria decisão do responsável, e nada no §10 pede isso.

## Invariantes

- O comprador nunca alcança escrita da E14.
- O portal do fornecedor não expõe dado da E14.

## Dependências e decisões em aberto

- Depende das E14-02, E14-04 e E14-05, da E13-05 (página do pedido) e da E13-07 (portal).
- Nenhuma decisão em aberto.

## Correção da revisão: E14-R02, a página do pedido depois do cancelamento (2026-11-16)

Origem: revisão independente sobre `5b00c56` (`docs/specs/E14-07/review.md`, "E14-R02 — Importante").

**Defeito.** A regra 5 manda tirar as seções desta fatia do pedido não válido. A ocorrência só existe em pedido do pedido formal, mas a rodada ainda pode ser cancelada em `aguardando_fornecedor` (E12, cenário 52). Depois disso, a página continua mostrando "Ocorrências de entrega". A seção é montada sem olhar a validade atual do pedido.

**Regra corrigida.** A regra 5 passa a dizer:

5. **Pedido não válido:** sem as seções "Ocorrências de entrega" e "Retirada". A validade é conferida a cada carregamento, com o estado atual, e não com o estado do momento da ocorrência. O pedido é válido quando as duas condições valem:
   - está no pedido formal do ciclo (`PedidoApurado` da apuração do ciclo da rodada);
   - a rodada não tem `CancelamentoDaRodada`.

   Pedido cancelado por inadimplência, ou de rodada que voltou ao interesse, não está no pedido formal. A rodada cancelada (com ou sem reembolso) torna não válidos todos os pedidos dela, inclusive os que tinham ocorrência.

**O que não muda com a regra 5:**
- a `OcorrenciaDeEntrega`, o `Reembolso` e a obrigação com o comprador continuam gravados, sem nenhuma alteração;
- a devolução da ocorrência continua no fluxo da E10;
- a seção "Estornos" da página (E10) continua listando a obrigação da ocorrência, com o valor e o estado real. É por ela que o comprador acompanha esse dinheiro depois do cancelamento, ao lado das frases do cancelamento (E12).

Esconder a seção não autoriza apagar, anular nem recalcular nada.

**Decisão técnica.** O registro de cancelamento basta como critério, porque o cancelamento é a única saída de `aguardando_fornecedor` além da liberação, e a liberação não pode ser cancelada (decisão (a)). Não há caso de ocorrência em pedido que depois saia do pedido formal por outro caminho.

Os critérios novos são A-15 e A-16.
