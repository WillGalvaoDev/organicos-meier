# E14-01 — O recebimento dos produtos do fornecedor

Fatia 1 de 8 da milestone **E14 — Recebimento, ocorrências, retirada e descarte**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7 (29/10/2026).
- Infraestrutura: v1.8 (29/10/2026), com base na especificação v1.7.
- A descrição da milestone 14 cita a base v1.6/v1.7. As seções usadas aqui (§2, §7, §7.1, §7.2, §9.2, §9.3, §10, §11, §12, §13, §14, §16 e 17.3 da especificação; 3.1, 3.2, 4.7, 4.9 e 5 da infraestrutura) não mudaram nas versões v1.7/v1.8. Essas versões só acrescentaram a Q-8 (contestação, §9.6), que não toca recebimento, ocorrência, retirada ou descarte. A base vigente é v1.7/v1.8, e a milestone é atualizada no fechamento.
- Gate de especificação: feito pelo especificador, por decisão do responsável (descrição da milestone).

## Decisão do responsável (2026-11-13)

**Rodada `disponivel_para_retirada` não pode ser cancelada** (opção (a) do herdado da E12). O cancelamento continua recusado com `rodada_encerrada`. O que restar a resolver depois da liberação (item faltante, incorreto ou não entregue) é registrado como ocorrência de entrega (§10), com reembolso pontual. As fatias E14-02 e E14-04 aplicam a decisão.

## Divisão da E14

| Fatia | Objetivo |
|---|---|
| E14-01 | O recebimento: o administrador registra, por produto do pedido formal, as quantidades recebidas do fornecedor, em uma ou mais entregas parciais |
| E14-02 | As ocorrências de entrega: faltante, incorreto ou não entregue, por item do pedido do comprador, com o reembolso pontual (§9.2), antes e depois da liberação |
| E14-03 | O endereço de retirada: o registro pelo administrador, o carrinho e a página de regras (herdado da E05) |
| E14-04 | A liberação da retirada: a conferência do recebimento, o encerramento da rodada, a liberação das reservas `em_pedido` (herdados da E08 e da E11), o aviso `retirada_liberada`, a nova rodada imediata e a recusa do cancelamento (decisão (a)) |
| E14-05 | A retirada por item e o descarte manual depois de sete dias |
| E14-06 | As telas do administrador: recebimento, ocorrências, liberação, retiradas e descartes |
| E14-07 | As telas do comprador (pedido, ocorrências, retirada e prazo), a ausência de rota de comprador para faltas e o portal do fornecedor inalterado |
| E14-08 | Ponta a ponta com o simulador: entrega parcial, ocorrências antes e depois do repasse e da liberação, nova rodada, retirada, prazo e descarte |

Ordem de implementação: E14-01 → E14-02 → E14-03 → E14-04 → E14-05 → E14-06 → E14-07 → E14-08. A E14-03 não depende das anteriores. As demais dependem das anteriores.

## Arranjos comuns da E14

Definidos em `docs/specs/E14-01/acceptance.md` e usados por todas as fatias.

## Contexto e objetivo

Na etapa `aguardando_fornecedor`, o administrador aguarda os produtos e os recebe em casa (§1, §7). A entrega pode ser parcial. O administrador então registra as ocorrências e autoriza o reembolso, ou aguarda o restante antes de liberar a retirada. Não existe liberação automática de retirada parcial (§10). A plataforma guarda as quantidades recebidas e as datas (§11, §14).

Esta fatia cria o registro do recebimento e o resumo por produto, que a liberação (E14-04) confere.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | Aguardando fornecedor: aguarda o recebimento dos produtos. Disponível para retirada: o administrador confirma o recebimento e libera a retirada. |
| Especificação §10 | Se a entrega é parcial, o administrador registra as ocorrências e autoriza o reembolso, ou aguarda o restante antes de anunciar o recebimento. Não existe liberação automática de retirada parcial. Não há substituição de produtos. |
| Especificação §11, §14 | Preservar o histórico das quantidades recebidas, estornadas, retiradas e descartadas, com as datas. |
| Especificação §2 | Só o administrador registra o recebimento. |
| Infraestrutura 5 | Registros operacionais só de inserção; `select_for_update` nas operações concorrentes. |
| Herdado da E13 | O `PedidoFormal` e as linhas são só inserção. O recebimento é registro separado, comparado com `LinhaDoPedidoFormal`, sem alterar o pedido formal. |

## Escopo

**Dentro:**
- O modelo `RecebimentoDoFornecedor`.
- O serviço `registrar_recebimento` e a consulta `situacao_do_recebimento`.
- A auditoria.

**Fora:**
- As ocorrências (E14-02). Esta fatia lê as somas das ocorrências pela função que a E14-02 cria. Até lá, a soma é zero.
- A liberação (E14-04) e as telas (E14-06).

## Modelo

**`RecebimentoDoFornecedor`** (só inserção, app `pedidos`):

| Campo | Conteúdo |
|---|---|
| `pedido_formal` | chave estrangeira |
| `linha` | a `LinhaDoPedidoFormal` do produto |
| `quantidade` | quantidade recebida nesta entrega, maior que zero, com até três casas |
| `autor` | o administrador |
| `registrado_em` | o instante do registro |
| `acionamento` | UUID único, um por envio do formulário |

**Recebido** significa as unidades que chegaram fisicamente, inclusive as que depois se revelam incorretas. As unidades que não chegaram são ocorrências `faltante` ou `nao_entregue` (E14-02), e nunca entram no recebimento.

## Regras

`registrar_recebimento(autor, rodada, produto, quantidade, *, acionamento) -> RecebimentoRegistrado`:

1. **Permissão:** só o administrador ativo; senão `PermissionDenied`, sem escrita.
2. **Acionamento:** um UUID (texto canônico ou `uuid.UUID`); outro valor dá `RecebimentoRecusado("acionamento_invalido")`.
   - **Repetição:** um recebimento já gravado com o mesmo acionamento é devolvido (`novo = False`), sem escrita, se tiver a mesma rodada, o mesmo produto e a mesma quantidade. Com outro conteúdo: `acionamento_invalido`.
3. **Transação e travas:** numa transação, a `Rodada` com `select_for_update(no_key=True)`.
   - É a trava que serializa o recebimento com as ocorrências (E14-02), a liberação (E14-04), o cancelamento (E12) e outro recebimento da mesma rodada.
   - O acionamento é conferido de novo sob a trava.
   - **`IntegrityError` no acionamento:** a transação é desfeita e a regra 2 é aplicada sobre o registro relido. Não há efeito externo nesta operação, então desfazer basta.
4. **Conferências sob a trava**, na ordem (a primeira que falha vale, sem escrita):

| Condição | Código | Mensagem |
|---|---|---|
| a rodada não está em `aguardando_fornecedor` | `etapa` | "O recebimento só é registrado enquanto a rodada aguarda o fornecedor." |
| o produto não tem linha no pedido formal da rodada | `produto_fora_do_pedido_formal` | "Este produto não está no pedido formal da rodada." |
| a quantidade não é `Decimal` finito maior que zero, com até três casas e múltipla do incremento do produto no ciclo | `quantidade_invalida` | "Informe uma quantidade maior que zero, no incremento do produto." |
| recebido + `faltante` + `nao_entregue` + a quantidade passaria da quantidade da linha | `passa_do_pedido_formal` | "A quantidade passa do que falta receber deste produto (<a receber> <unidade>)." |

   - O incremento do produto no ciclo é o de `CondicaoDoProdutoNoCiclo` (o congelado no fechamento).
   - Na mensagem, `<a receber>` é a quantidade formatada por `formatar_quantidade` (sem zeros à direita) e `<unidade>` é o valor gravado na linha (`unidade`, `kg`, ...), como no e-mail do pedido formal.
   - A soma das ocorrências por tipo vem da E14-02 (`somas_das_ocorrencias(pedido_formal, produto)`). Só contam as ocorrências registradas em `aguardando_fornecedor`.
5. **Gravação:** o `RecebimentoDoFornecedor`, com `registrado_em` lido depois da trava.
6. **Auditoria `recebimento.registrar`**, na transação: o autor, a rodada, o produto, a quantidade, o recebido acumulado e o UUID do acionamento, sob a chave `acionamento`.
7. **Nada mais muda:** o pedido formal, as linhas, o envio, a previsão, os pedidos, os pagamentos e o livro-razão ficam iguais. O recebimento não é ato financeiro nem gera aviso.
8. **Sem correção:** não existe rota nem serviço para apagar ou alterar um recebimento (só inserção). O limite da regra 4 impede registrar mais do que o pedido formal.

`situacao_do_recebimento(rodada) -> list[LinhaDoRecebimento]`, sem trava, uma por linha do pedido formal, na ordem das linhas:
- `produto`, `nome`, `unidade`, `pedida` (a quantidade da linha), `recebida` (a soma dos recebimentos);
- `faltante`, `nao_entregue` e `incorreta` (as somas das ocorrências da E14-02 registradas em `aguardando_fornecedor`);
- `a_resolver` = `pedida − recebida − faltante − nao_entregue`.

`recebimento_resolvido(rodada) -> bool`: verdadeiro se toda linha tem `a_resolver == 0`. É a condição da liberação (E14-04).

## Interface

- `registrar_recebimento(autor, rodada, produto, quantidade, *, acionamento) -> RecebimentoRegistrado(recebimento, novo)`.
- `class RecebimentoRecusado(Exception)`, com `codigo` e a mensagem da tabela.
- `situacao_do_recebimento(rodada)` e `recebimento_resolvido(rodada)`.

## Decisões técnicas

- **Recebimento por produto, e não por comprador.** O fornecedor entrega o pedido formal, que é por produto e sem compradores (E13-01). A divisão entre compradores só aparece nas ocorrências e na retirada, por item.
- **Incorreto conta como recebido.** A unidade incorreta chegou e ocupa espaço. Ela é reembolsada pela ocorrência e sai do que o comprador tem a retirar (E14-02, E14-05). As faltantes e as não entregues não chegaram e completam, com o recebido, a quantidade do pedido formal.
- **Trava da rodada.** Todas as operações da E14 sobre a mesma rodada se serializam por ela, antes de qualquer outra trava. O volume é pequeno (uma rodada por fornecedor), e uma única trava evita impasse.
- **Acionamento por envio de formulário.** O duplo clique não duplica a quantidade recebida, como o token do reenvio (E13-03). A chave da auditoria é `acionamento`, porque a auditoria recusa o termo `token` (E13-03, regra 12).

## Invariantes

- Para cada linha: recebido + `faltante` + `nao_entregue` ≤ quantidade da linha.
- Nenhum recebimento fora de `aguardando_fornecedor`.
- O pedido formal e as linhas nunca mudam.

## Casos-limite e concorrência

- **Dois recebimentos em paralelo** do mesmo produto, que juntos passam da linha: o segundo espera a trava da rodada e recebe `passa_do_pedido_formal`.
- **O mesmo acionamento em paralelo:** um registro; as duas chamadas devolvem o mesmo.
- **Recebimento e cancelamento em paralelo:** o que travar a rodada depois vê a etapa do outro. Um recebimento depois do cancelamento é recusado com `etapa`.
- **Produto por peso:** 2,5 kg com incremento de 0,5 kg é aceito; 2,3 kg é recusado.

## Dependências e decisões em aberto

- Depende da E13-01 (pedido formal) e da E06 (`CondicaoDoProdutoNoCiclo`).
- Nenhuma decisão em aberto.
