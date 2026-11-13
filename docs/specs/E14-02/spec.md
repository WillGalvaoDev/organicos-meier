# E14-02 — As ocorrências de entrega com reembolso pontual

Fatia 2 de 8 da milestone **E14 — Recebimento, ocorrências, retirada e descarte**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E14-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E14-01.

## Contexto e objetivo

Depois da entrega, o administrador registra, por produto e quantidade, os itens faltantes, incorretos ou não entregues (§10). Cada ocorrência:
- dá o reembolso pontual dos itens afetados, com serviço e frete proporcionais (§9.2);
- fica registrada à parte, sem alterar o pedido (§7.1);
- não cancela a rodada.

A soma das ocorrências de um item nunca passa da quantidade paga dele (cenário 49, T-18).

Pela decisão (a) do responsável (E14-01), a ocorrência vale também depois da liberação da retirada. É o caminho para o que restar a resolver numa rodada que não pode mais ser cancelada.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §10 | Ocorrências por produto e quantidade: faltantes, incorretos, não entregues. Reembolso pontual com serviço e frete proporcionais (§9.2). Registradas à parte, sem modificar o pedido. O comprador não registra faltas nem pede substituição. Ocorrências não cancelam a rodada. A soma das ocorrências de um item não passa da quantidade paga. |
| Especificação §9.2 | O cálculo do reembolso parcial, com controle acumulado por item e por componente (a rotina da E10-02). |
| Especificação §7.1, §14 | O pedido congelado não muda. Ocorrência: item do pedido, quantidade, tipo, autor, momento e reembolso associado. |
| Especificação §2 | Só o administrador registra ocorrências. |
| Infraestrutura 4.9 | Ocorrência só de inserção, com item, quantidade, tipo, autor e momento. A soma por item não passa da quantidade paga, conferida sob trava de linha. No máximo uma obrigação de reembolso por ocorrência, com chave de idempotência própria. Só o administrador; nenhuma rota de comprador. |
| Infraestrutura 3.2 | Ocorrência com reembolso pontual: obrigação de devolução financiada como as demais (antes ou depois do repasse). |
| Infraestrutura 4.7 | A devolução segue os estados e a autorização das demais origens (E10). |
| Herdado da E09 | `registrar_obrigacao_com_comprador` (E09-06) com os componentes do §9.2. |
| Herdado da E10 | `reembolso_parcial(item, quantidade, chave=..., motivo="ocorrencia_de_entrega", autor=...)`. O motivo já existe em `MotivoDoReembolso`. |
| Decisão (a), 2026-11-13 | Na rodada `disponivel_para_retirada`, o que restar é tratado como ocorrência. |
| Cenários §16 | 18, 48, 49, 52; 90 e 112 a 117 pelo cálculo da E10-02 |
| Testes técnicos | T-18 |

## Escopo

**Dentro:**
- O modelo `OcorrenciaDeEntrega`.
- O serviço `registrar_ocorrencia`, as somas e o saldo do item.
- A auditoria e a concorrência (T-18).

**Fora:**
- A autorização e a execução da devolução: continuam na tela e no fluxo da E10 (`autorizar_devolucao`), a partir da obrigação gerada aqui.
- As telas (E14-06 e E14-07).
- Retirada e descarte (E14-05), que entram no saldo do item pela mesma função.

## Modelo

**`OcorrenciaDeEntrega`** (só inserção, app `pedidos`):

| Campo | Conteúdo |
|---|---|
| `item` | o `ItemDoPedido` afetado |
| `tipo` | `faltante`, `incorreto` ou `nao_entregue`, com os rótulos "Faltante", "Incorreto" e "Não entregue" |
| `quantidade` | maior que zero, com até três casas |
| `etapa` | a etapa da rodada no registro: `aguardando_fornecedor` ou `disponivel_para_retirada` |
| `reembolso` | um para um com o `Reembolso` gerado (E10) |
| `autor` | o administrador |
| `registrada_em` | o instante do registro |
| `acionamento` | UUID único |

## Regras

`registrar_ocorrencia(autor, item, quantidade, tipo, *, acionamento) -> OcorrenciaRegistrada`:

1. **Permissão:** só o administrador ativo; senão `PermissionDenied`, sem escrita. Sem nova autenticação: a ocorrência não move dinheiro nem escolhe a origem dos recursos (o financiamento é fixado pela regra, infraestrutura 3.2), como o reenvio da E13-04. A passkey recente continua exigida na autorização da devolução (E10), que é o ato que tira dinheiro.
2. **Acionamento:** como na E14-01, regra 2.
   - A repetição com o mesmo item, tipo e quantidade devolve a ocorrência gravada (`nova = False`).
   - Com outro conteúdo, ou um valor que não é UUID: `OcorrenciaRecusada("acionamento_invalido")`.
3. **Transação e travas, nesta ordem:**
   - a `Rodada` do pedido, com `select_for_update(no_key=True)` (a mesma trava da E14-01);
   - a `SituacaoDoPedido` do pedido, com `select_for_update()`. É a trava dos reembolsos do pedido (E10-02), tomada antes de ler qualquer acumulado;
   - as contas do livro-razão, travadas por `reembolso_parcial` ao registrar a obrigação.

   Essa é a ordem do cancelamento (E12: rodada, situações, contas) e da sincronização do pagamento (situação, contas). O acionamento é conferido de novo sob as travas. O `IntegrityError` no acionamento é tratado como na E14-01.
4. **Conferências sob as travas**, na ordem (a primeira que falha vale, sem escrita):

| Condição | Código | Mensagem |
|---|---|---|
| a rodada não está em `aguardando_fornecedor` nem em `disponivel_para_retirada` | `etapa` | "Ocorrências só são registradas depois da aprovação do resultado e antes do cancelamento." |
| o item não é de um pedido válido do ciclo do pedido formal (`PedidoApurado`) | `item_fora_do_pedido_formal` | "Este item não está entre os pedidos válidos da rodada." |
| o tipo não é um dos três | `tipo_invalido` | "Escolha o tipo da ocorrência." |
| a quantidade não é `Decimal` finito maior que zero, com até três casas e múltipla do `incremento` do item | `quantidade_invalida` | "Informe uma quantidade maior que zero, no incremento do produto." |
| a quantidade passa do saldo do item (regra 5) | `passa_do_saldo_do_item` | "A quantidade passa do saldo deste item (<saldo> <unidade>)." |
| em `aguardando_fornecedor`, `faltante` ou `nao_entregue`: recebido + `faltante` + `nao_entregue` do produto + a quantidade passaria da linha do pedido formal | `passa_do_pedido_formal` | "A quantidade passa do que ainda não foi recebido deste produto (<a resolver> <unidade>)." |
| em `aguardando_fornecedor`, `incorreto`: `incorreto` do produto + a quantidade passaria do recebido | `passa_do_recebido` | "A quantidade passa do que já foi recebido deste produto (<recebido> <unidade>)." |

5. **Saldo do item:** `saldo_do_item(item)` = `item.quantidade` − a quantidade já reembolsada do item (toda `ItemReembolsado`, de qualquer motivo, inclusive as unidades da caixa invalidada) − a retirada − a descartada (E14-05; zero até lá).
   - Lido sob as travas da regra 3.
   - O saldo é o que o comprador ainda tem para receber ou retirar.
   - Garante o cenário 49 e o T-18: a soma das ocorrências nunca passa da quantidade paga, e nenhuma unidade é reembolsada duas vezes.
6. **Depois da liberação:** em `disponivel_para_retirada`, só valem as conferências de etapa, item, tipo, quantidade e saldo. As regras do pedido formal e do recebido só existem antes da liberação, porque o recebimento já foi conferido (E14-04).
7. **Gravação, na mesma transação:**
   - o reembolso pontual: `reembolso_parcial(item, quantidade, chave=f"ocorrencia:{acionamento}", motivo="ocorrencia_de_entrega", autor=autor)`, que calcula pela §9.2 e registra a obrigação com o comprador (E09-06);
   - a `OcorrenciaDeEntrega`, com o `Reembolso` gerado e a etapa lida sob a trava;
   - **valor zero:** o reembolso é gravado sem obrigação, como na E10-02 (cenário 115). A ocorrência existe do mesmo jeito;
   - **financiamento:** é o da E09-06. Antes do repasse, os produtos saem da obrigação com o fornecedor da rodada, o serviço da receita de serviço e o frete do frete da rodada, até o saldo de cada uma. O que faltar fica sem cobertura até o administrador escolher a fonte (infraestrutura 3.2).
8. **A devolução não é automática:** a obrigação segue o fluxo da E10. O administrador autoriza a devolução pela tela da E10 (§9.2: "O administrador autoriza estornos manualmente"), com a consulta ao provedor e a cobertura exigidas lá. O aviso `estorno` sai na autorização (E10).
9. **Nada mais muda:**
   - o `Pedido`, os `ItemDoPedido` e as parcelas não mudam (cenário 48, §7.1);
   - a rodada não muda de etapa (cenário 52);
   - o pedido formal, as linhas e os recebimentos não mudam.
10. **Auditoria `ocorrencia.registrar`**, na transação: o autor, o pedido, o item, o tipo, a quantidade, a etapa, o reembolso (produtos, serviço, frete), a obrigação (ou nenhuma) e o UUID sob a chave `acionamento`. Sem e-mail nem nome do comprador.

**Somas para as outras fatias:**
- `somas_das_ocorrencias(pedido_formal, produto) -> dict[str, Decimal]`: por tipo, só das ocorrências em `aguardando_fornecedor` dos itens dos pedidos válidos do ciclo (E14-01);
- `saldo_do_item(item) -> Decimal`: sem trava, para as telas.

## Interface

- `registrar_ocorrencia(autor, item, quantidade, tipo, *, acionamento) -> OcorrenciaRegistrada(ocorrencia, reembolso, nova)`, com `reembolso` igual ao `ReembolsoRegistrado` da E10 (inclui `obrigacao` e `sem_cobertura`).
- `class OcorrenciaRecusada(Exception)`, com `codigo` e a mensagem.
- `class TipoDeOcorrencia(TextChoices)`.
- `somas_das_ocorrencias` e `saldo_do_item`.

## Decisões técnicas

- **A ocorrência é o ato que cria o reembolso; a devolução é autorizada à parte.**
  - O §10 diz que o administrador "registra as ocorrências e autoriza o reembolso", e o §9.2 diz que o administrador autoriza os estornos no dashboard.
  - Diferente do cancelamento com reembolso, nenhuma regra torna a ocorrência a própria autorização. Por isso a obrigação nasce na ocorrência e a devolução passa pela autorização da E10, como as demais.
  - "No máximo uma obrigação" (infraestrutura 4.9) cobre o reembolso de valor zero.
- **A chave do reembolso deriva do acionamento:** `ocorrencia:<uuid>` (47 caracteres, dentro dos 64 da E10). Uma repetição chega ao mesmo `Reembolso`.
- **O saldo inclui todos os reembolsos do item.** A quantidade paga da §10 é a do item no pedido. As unidades de caixa invalidada já foram reembolsadas e não estão com o comprador; contá-las no limite permitiria reembolsá-las de novo.
- **Incorreto antes da liberação limitado ao recebido:** só uma unidade que chegou pode estar incorreta. Faltante e não entregue completam o que não chegou (E14-01).

## Invariantes

- Por item: reembolsado (todos os motivos) + retirado + descartado ≤ quantidade do item.
- Em `aguardando_fornecedor`, por produto: recebido + `faltante` + `nao_entregue` ≤ linha do pedido formal, e `incorreto` ≤ recebido.
- Uma ocorrência gera exatamente um `Reembolso` e no máximo uma obrigação.
- Nenhuma ocorrência em rodada cancelada.

## Casos-limite e concorrência

- **Ocorrências concorrentes no mesmo item (T-18):** a segunda espera a trava da rodada e confere o saldo já reduzido.
- **Ocorrência e cancelamento:** a ocorrência registrada antes continua, e o cancelamento com reembolso devolve só o saldo restante (cenário 114, E10). Depois do cancelamento, a ocorrência é recusada com `etapa`.
- **Ocorrência depois do repasse:** a parte de produtos fica sem cobertura (a obrigação com o fornecedor já foi baixada). O administrador cobre pela reserva, pela receita de serviço ou por aporte (E09-06), antes de autorizar a devolução.
- **Comprador suspenso ou removido:** a ocorrência é registrada do mesmo jeito; a obrigação é dele.

## Dependências e decisões em aberto

- Depende da E14-01, da E10-02 (`reembolso_parcial`) e da E09-06.
- Nenhuma decisão em aberto.
