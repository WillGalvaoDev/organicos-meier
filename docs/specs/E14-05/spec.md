# E14-05 — A retirada por item e o descarte manual

Fatia 5 de 8 da milestone **E14 — Recebimento, ocorrências, retirada e descarte**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E14-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E14-01.

## Contexto e objetivo

Liberada a retirada, o administrador registra a retirada por item e quantidade, em momentos diferentes se for o caso (§11). O prazo de armazenamento é de sete dias a partir da liberação. Depois dele, os itens restantes aparecem como pendentes de decisão. Só uma ação do administrador registra o descarte: a passagem do tempo nunca marca nada como descartado (§11, cenário 23).

O histórico preserva as quantidades recebidas, estornadas, retiradas e descartadas (§11, §14).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §11 | Retirada por item e quantidade, em momentos diferentes. Prazo de sete dias a partir da liberação. Depois do prazo, descarte manual dos itens restantes; nunca automático. Histórico das quantidades recebidas, estornadas, retiradas e descartadas. A nova rodada não depende das retiradas anteriores. |
| Especificação §2 | Só o administrador registra retiradas e descarte. O comprador suspenso continua com os pedidos pagos disponíveis para retirada (cenário 19). |
| Especificação §7, §7.1 | Os pedidos mantêm o acompanhamento individual de retirada e descarte; retirada e descarte são estado operacional registrado à parte, sem alterar a composição. |
| Especificação §13, administrador | Controle de retirada por item, itens vencidos e registro de descarte. |
| Infraestrutura 4.9 | O estado operacional (retirado, descartado) fica em registros próprios, que referenciam o pedido sem alterá-lo. |
| Cenários §16 | 19 (retirada do suspenso), 22, 23 |

## Escopo

**Dentro:**
- Os modelos `RetiradaDeItem` e `DescarteDeItem`.
- Os serviços `registrar_retirada`, `registrar_descarte` e `situacao_da_retirada`.
- A extensão de `saldo_do_item` (E14-02).

**Fora:**
- As telas (E14-06 e E14-07).
- Alertas de itens vencidos no painel (E15).

## Modelos

**`RetiradaDeItem`** e **`DescarteDeItem`** (só inserção, app `pedidos`), com os mesmos campos:
- `item`: o `ItemDoPedido`;
- `quantidade`: maior que zero, com até três casas;
- `autor`: o administrador;
- `registrada_em`;
- `acionamento`: UUID único em cada tabela.

## Regras

`registrar_retirada(autor, item, quantidade, *, acionamento) -> RetiradaRegistrada` e `registrar_descarte(autor, item, quantidade, *, acionamento) -> DescarteRegistrado`:

1. **Permissão:** só o administrador ativo; senão `PermissionDenied`, sem escrita.
2. **Acionamento:** como na E14-01, regra 2. A repetição com o mesmo item e a mesma quantidade devolve o registro (`novo = False`). Outro conteúdo ou valor inválido: `RetiradaRecusada("acionamento_invalido")`.
3. **Transação e travas:** a `Rodada` do pedido (`select_for_update(no_key=True)`), depois a `SituacaoDoPedido` do pedido (`select_for_update()`). É a ordem da E14-02, que serializa a retirada e o descarte com as ocorrências do mesmo item, e com a leitura dos reembolsos acumulados.
4. **Conferências sob as travas**, na ordem (a primeira que falha vale, sem escrita). As duas operações usam `RetiradaRecusada`:

| Condição | Código | Mensagem |
|---|---|---|
| a rodada não está em `disponivel_para_retirada` | `etapa` | "A retirada só é registrada depois da liberação." |
| o item não é de um pedido válido do ciclo liberado | `item_fora_do_pedido_formal` | "Este item não está entre os pedidos válidos da rodada." |
| a quantidade não é `Decimal` finito maior que zero, com até três casas e múltipla do `incremento` do item | `quantidade_invalida` | "Informe uma quantidade maior que zero, no incremento do produto." |
| a quantidade passa do saldo do item | `passa_do_saldo_do_item` | "A quantidade passa do saldo deste item (<saldo> <unidade>)." |
| **só no descarte:** agora é anterior ao `prazo_final` da liberação | `antes_do_prazo` | "O descarte só pode ser registrado a partir de <dd/mm/aaaa hh:mm> (horário de Brasília)." |

5. **Saldo do item:** `saldo_do_item` (E14-02) passa a descontar a soma das retiradas e dos descartes do item.
6. **Retirada depois do prazo:** é aceita enquanto houver saldo (cenário 22: retiradas antigas continuam registráveis). O prazo só habilita o descarte.
7. **Situação do comprador:** a retirada e o descarte não dependem da situação da conta (ativa, suspensa ou removida). O pedido pago continua do comprador, e a retirada é um registro físico do administrador (cenário 19, §2).
8. **Sem efeito financeiro:** nenhum reembolso, obrigação ou movimento. O descarte de item não retirado não gera devolução: nenhuma regra prevê isso (§11).
9. **Auditoria:** `retirada.registrar` e `descarte.registrar`, com o autor, o pedido, o item, a quantidade, o saldo depois e o UUID sob `acionamento`. Sem nome nem e-mail do comprador.

`situacao_da_retirada(rodada) -> SituacaoDaRetirada`, sem trava:
- `liberacao` (instante, prazo final, endereço) e `prazo_encerrado` (agora ≥ `prazo_final`);
- por pedido válido, na ordem de `pk`, o comprador (nome) e, por item, na ordem de `pk`:
  - `pedida` (a quantidade do item);
  - `reembolsada_na_apuracao` (os reembolsos de motivo diferente de `ocorrencia_de_entrega`);
  - `em_ocorrencias`, `retirada`, `descartada` e `saldo`;
- `vencidos`: os itens com `saldo > 0` quando `prazo_encerrado`, que são os "pendentes de decisão/descarte" (cenário 23).

## Interface

- `registrar_retirada(...)`, `registrar_descarte(...)`, com `class RetiradaRecusada(Exception)` e `codigo`.
- `situacao_da_retirada(rodada)` e `saldo_do_item(item)` (estendida).

## Decisões técnicas

- **Fronteira do prazo:** "sete dias a partir da liberação" é o instante `liberada_em + 168 h`. O descarte é aceito a partir desse instante, inclusive. É a convenção das demais fronteiras (a partir de `T0 + 24h`, as tentativas são recusadas).
- **Descarte por item e quantidade.** A §11 fala em "itens restantes". O descarte parcial do saldo é permitido, e a soma nunca passa do saldo. O descarte de tudo é a quantidade do saldo.
- **Nenhum vencimento automático.** `vencidos` é calculado na leitura, e nada é gravado pela passagem do tempo (cenário 23).

## Invariantes

- Por item: reembolsado + retirado + descartado ≤ quantidade do item.
- Nenhum descarte antes do prazo final.
- Nenhuma retirada ou descarte fora de `disponivel_para_retirada`.

## Casos-limite e concorrência

- **Retirada e ocorrência em paralelo no mesmo item:** as duas travam a rodada; a segunda confere o saldo já reduzido.
- **Duas retiradas em paralelo** que somam mais que o saldo: a segunda recebe `passa_do_saldo_do_item`.
- **Descarte exatamente no prazo final:** aceito; um milissegundo antes, `antes_do_prazo`.
- **Produto por peso:** retirada de 0,5 kg de 1,5 kg com incremento de 0,5 é aceita; 0,3 kg é recusada.

## Dependências e decisões em aberto

- Depende das E14-02 e E14-04.
- Nenhuma decisão em aberto.
