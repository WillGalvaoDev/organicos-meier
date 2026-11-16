# E14-04 — A liberação da retirada e o encerramento da rodada

Fatia 4 de 8 da milestone **E14 — Recebimento, ocorrências, retirada e descarte**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E14-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E14-01.

## Contexto e objetivo

Resolvidas as ocorrências ou recebido tudo, o administrador libera a retirada e encerra a rodada para novas compras do fornecedor (§10). A rodada passa a `disponivel_para_retirada`. O fornecedor pode ter uma rodada nova imediatamente, e as retiradas antigas continuam registráveis por item (§7, §11, cenário 22). A liberação gera o aviso com o endereço, a disponibilidade e o limite de sete dias (§12).

A fatia também resolve os herdados de encerramento:
- as parcelas `em_pedido` deixam de reservar estoque (E08 e E11);
- a rodada liberada não pode ser cancelada (decisão (a), E14-01).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | Disponível para retirada: o administrador confirma o recebimento e libera a retirada. A rodada é encerrada para permitir nova rodada do fornecedor. Os pedidos mantêm o acompanhamento individual de retirada e descarte. |
| Especificação §10 | Não existe liberação automática de retirada parcial. Depois de resolver as ocorrências ou receber tudo, o administrador libera a retirada. |
| Especificação §11 | A liberação gera avisos por e-mail, site e WhatsApp para quem optou. Prazo de sete dias a partir da liberação. A nova rodada não depende das retiradas anteriores. |
| Especificação §12 | Liberação de retirada: endereço, disponibilidade e limite de sete dias. |
| Especificação §7.2 | O cancelamento é distinto das ocorrências de entrega. |
| Decisão (a), 2026-11-13 | A rodada `disponivel_para_retirada` não pode ser cancelada; o que restar vira ocorrência. |
| Herdado da E04 | `retirada_liberada` por `emitir_evento`, na transação do fato, com chave derivada do fato. Os canais são os de `CANAIS_POR_EVENTO` (site, e-mail e WhatsApp com consentimento). |
| Herdado da E08 e da E11 | Ao encerrar a rodada, as parcelas `em_pedido` saem de `total_reservado`, para não consumir o estoque da rodada seguinte. |
| Herdado da E13 | A previsão de entrega só vale em `aguardando_fornecedor` (E13-05). O pedido formal continua consultável no portal (E13-07). O repasse continua limitado ao liberado (E13-06). |
| Cenários §16 | 22, 52 |

## Escopo

**Dentro:**
- O modelo `LiberacaoDaRetirada` e o serviço `liberar_retirada`.
- A liberação das parcelas `em_pedido`, o aviso `retirada_liberada` e a recusa do cancelamento.

**Fora:**
- A tela (E14-06).
- Retirada e descarte (E14-05).

## Modelo

**`LiberacaoDaRetirada`** (só inserção, app `pedidos`):
- `rodada`: um para um; `ciclo`; `pedido_formal`;
- `liberada_em`: o instante lido sob as travas;
- `prazo_final`: `liberada_em` + 7 dias (168 horas);
- `endereco`: o `EnderecoDeRetirada` vigente;
- `autor`.

## Regras

`liberar_retirada(autor, rodada) -> LiberacaoDaRetirada`:

1. **Permissão:** só o administrador ativo; senão `PermissionDenied`, sem escrita.
2. **Conferência prévia, sem trava:** a etapa e as condições da regra 4, com as mesmas recusas.
3. **Transação e travas:** as travas da apuração e do cancelamento, na mesma ordem e no mesmo modo (`_travar` da E11-01, como na E12-01):
   - as contas dos compradores dos pedidos válidos, por `pk`;
   - o fornecedor;
   - a rodada;
   - os produtos do fornecedor e os estoques da rodada;
   - as parcelas não removidas de cada produto, por sequência.

   A trava da rodada vem antes de qualquer trava de situação ou de conta do livro, então a liberação se serializa com o recebimento, as ocorrências, o cancelamento e as operações de interesse sem formar ciclo.
4. **Conferências sob as travas**, na ordem (a primeira que falha vale, sem escrita):

| Condição | Código | Mensagem |
|---|---|---|
| a rodada está em `disponivel_para_retirada` | `ja_liberada` | "A retirada desta rodada já foi liberada." |
| a rodada não está em `aguardando_fornecedor` | `etapa` | "A retirada só é liberada quando a rodada aguarda o fornecedor." |
| não há endereço de retirada vigente | `sem_endereco` | "Registre o endereço de retirada antes de liberar." |
| alguma linha do pedido formal tem `a_resolver > 0` (E14-01) | `recebimento_pendente` | "Ainda falta resolver: <produto> (<a resolver> <unidade>); ...", com cada linha pendente, na ordem do pedido formal |

5. **Efeitos, na mesma transação:**
   - a etapa da rodada passa a `disponivel_para_retirada`;
   - grava a `LiberacaoDaRetirada`, com o endereço vigente lido sob as travas;
   - **parcelas `em_pedido`** de produtos do fornecedor: perdem a reserva (`quantidade_reservada = 0`) e passam a `removida`. Se tiverem parte pendente, passam a `pendente` (fila do fornecedor, §5.2), como a regra 6 da E12-01;
     - as parcelas `ativa` e `pendente` não mudam;
     - nenhuma parcela é criada e nenhuma sequência muda;
   - os avisos (regra 6);
   - auditoria `rodada.liberar_retirada`: o autor, a rodada, o instante, o prazo final, o endereço e as parcelas alteradas (parcela, comprador, situação anterior e nova, reserva anterior), como no cancelamento.
6. **Aviso `retirada_liberada`**, por `emitir_evento`, um por pedido válido do ciclo com algum item de saldo maior que zero (E14-02, `saldo_do_item`):
   - **destinatários:** o comprador do pedido, ativo ou suspenso. O removido não recebe (acesso bloqueado, §2, como na E13-05);
   - **título:** `Retirada liberada: <fornecedor>`;
   - **corpo:** `Os produtos do seu pedido <pk> da rodada de <fornecedor> estão disponíveis para retirada em <endereço>. Retire até <dd/mm/aaaa> às <hh:mm> (horário de Brasília). Restrições de dia ou horário são publicadas nos comunicados.`, com o prazo final em Brasília e o endereço com as quebras de linha trocadas por ", ";
   - **link:** `/pedidos/<pk>/`;
   - **chave:** `retirada_liberada:<liberação>:<conta>`.
7. **Nova rodada imediata (cenário 22):** a etapa `disponivel_para_retirada` está fora de `ETAPAS_ATIVAS`. Logo depois do commit, `abrir_rodada` do mesmo fornecedor é aceita. Na nova rodada, o estoque fica livre das reservas `em_pedido` da rodada liberada.
8. **O que não muda:**
   - o envio do pedido formal (E13-02/E13-03) segue suas regras;
   - o repasse e o pagamento do frete (E13-06) continuam permitidos e limitados ao liberado;
   - a previsão deixa de ser ajustável e de aparecer para o comprador, como a E13-05 já define fora de `aguardando_fornecedor`;
   - pedidos, itens, pagamentos e livro-razão não mudam (a liberação não é ato financeiro);
   - as ocorrências continuam registráveis (E14-02, regra 6).
9. **Cancelamento recusado (decisão (a)):** `cancelar_rodada` numa rodada `disponivel_para_retirada` continua recusado com `CancelamentoRecusado("rodada_encerrada")` e a mensagem atual, sem escrita, com ou sem reembolso. A regra deixa de ser guarda provisória e passa a ser regra aprovada. Nenhum código novo de cancelamento é necessário.

## Interface

- `liberar_retirada(autor, rodada) -> LiberacaoDaRetirada` e `class LiberacaoRecusada(Exception)` com `codigo` e a mensagem.
- `liberacao_da_rodada(rodada) -> LiberacaoDaRetirada | None`.

## Decisões técnicas

- **A conferência do recebimento é a "liberação sem parcial automática".** Cada unidade do pedido formal precisa estar recebida ou coberta por ocorrência `faltante`/`nao_entregue`. Assim o administrador só libera depois de receber tudo ou de resolver o que faltou (§10), sem decisão comercial nova.
- **Parcelas `em_pedido` passam a `removida`.** É a mesma transição do cancelamento (E12-01, regra 6), já aprovada: a parcela deixa de reservar e sai do carrinho. O que o comprador comprou continua no pedido congelado, que é o registro da compra. Não se cria uma situação nova de parcela.
- **O aviso vai só a quem tem o que retirar.** Um pedido todo reembolsado por ocorrências não tem retirada; avisar seria mensagem desnecessária (§12).
- **O endereço fica na liberação.** Trocar o endereço depois não reescreve o que foi avisado nem o prazo.

## Invariantes

- Toda rodada `disponivel_para_retirada` tem exatamente uma `LiberacaoDaRetirada`.
- Depois da liberação, nenhuma parcela `em_pedido` de produto do fornecedor tem reserva vinda dessa rodada.
- Rodada `disponivel_para_retirada` nunca vira `cancelada`.

## Casos-limite e concorrência

- **Duas liberações em paralelo:** a segunda espera as travas e recebe `ja_liberada`; uma liberação, um conjunto de avisos.
- **Liberação e recebimento em paralelo:** quem travar a rodada depois vê o estado do outro. O recebimento depois da liberação recebe `etapa`. A liberação com o recebimento que completa a linha ainda não commitado espera e depois libera.
- **Liberação e cancelamento em paralelo:** se o cancelamento trava antes, a liberação recebe `etapa`. Se a liberação trava antes, o cancelamento recebe `rodada_encerrada`.
- **Liberação e ocorrência em paralelo:** a ocorrência espera a trava da rodada e é conferida na etapa nova (regra 6 da E14-02).
- **Rodada nova antes da liberação:** recusada pela restrição de rodada ativa única (`aguardando_fornecedor` está em `ETAPAS_ATIVAS`), como hoje.

## Dependências e decisões em aberto

- Depende das E14-01, E14-02 e E14-03, da E11-01 (`_travar`), da E12-01 (regra 6) e da E04-02.
- Nenhuma decisão em aberto: a decisão (a) foi tomada pelo responsável em 2026-11-13.
