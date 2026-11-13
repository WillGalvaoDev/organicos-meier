# E14-06 — As telas do administrador: recebimento, ocorrências, liberação, retiradas e descartes

Fatia 6 de 8 da milestone **E14 — Recebimento, ocorrências, retirada e descarte**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E14-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E14-01.

## Contexto e objetivo

O §13 pede ao administrador:
- o registro das ocorrências de entrega (faltantes, incorretos, não entregues) com reembolso pontual;
- a liberação da retirada;
- o controle de retirada por item, dos itens vencidos e do registro de descarte.

Esta fatia entrega as páginas e as rotas que chamam os serviços das E14-01, E14-02, E14-04 e E14-05, com as mesmas convenções da E13-04 e da E13-06.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, administrador | Ocorrências de entrega com reembolso pontual e liberação de retirada; controle de retirada por item, itens vencidos e registro de descarte. |
| Especificação §2 | Só o administrador; restrições no servidor, inclusive por acesso direto. |
| Especificação §10, §11 | As regras das fatias anteriores. |
| Cenários §16 | 22, 23, 48, 49, 50 (nenhuma rota de comprador), 52 |

## Escopo

**Dentro:**
- A página de recebimento, com a liberação.
- A página de ocorrências.
- A página de retiradas, com o descarte.
- As rotas `POST` e os links na página da rodada.

**Fora:**
- Os serviços (fatias anteriores).
- As telas do comprador (E14-07).
- O painel de alertas (E15).

## Convenções comuns

1. **Acesso:** todas as rotas usam `somente_administrador`. Comprador e fornecedor recebem 403; o anônimo vai para o login. Rodada inexistente ou sem pedido formal: 404.
2. **Rotas `POST`:** `GET` dá 405. O formulário tem o token CSRF e um campo oculto `acionamento` com um UUID novo gerado a cada carregamento da página, como o token do reenvio (E13-04).
   - Sem `acionamento`, ou com um valor que não é UUID: a página com 400 e "Recarregue a página e tente de novo.", sem chamar o serviço.
   - Campos fora do formulário são ignorados.
3. **Respostas dos serviços:**
   - **registro novo:** 302 para a página, com a mensagem de sucesso;
   - **acionamento repetido** (`novo`/`nova` falso): 302 com "Este registro já tinha sido feito.", sem registro novo;
   - **recusa do serviço:** a página com 409 e a mensagem da recusa, com o formulário preenchido;
   - **campo ausente ou malformado** (produto, item, tipo ou quantidade que não se converte em `Decimal`): 400 com "Preencha todos os campos.";
   - **`acionamento_invalido` do serviço:** 400 com "Recarregue a página e tente de novo.".
4. **Quantidades:** aceitas com vírgula ou ponto decimal (como os formulários de interesse da E05) e exibidas com `formatar_quantidade` e a unidade gravada.
5. **Datas:** em Brasília, `dd/mm/aaaa hh:mm`.

## Página de recebimento

`GET administracao/rodadas/<pk>/recebimento/` (nome `rodadas_recebimento`):

6. **Tabela por linha do pedido formal** (`situacao_do_recebimento`): produto, unidade, pedida, recebida, faltante, não entregue, incorreta e a resolver.
7. **Em `aguardando_fornecedor`:**
   - **formulário de recebimento:** produto (as linhas do pedido formal), quantidade, `acionamento`, botão "Registrar recebimento";
   - o link "Registrar ocorrência" para a página de ocorrências;
   - **liberação:**
     - com o recebimento resolvido e o endereço vigente: o formulário "Liberar retirada", com o texto "A rodada será encerrada e os compradores serão avisados. O prazo de retirada é de sete dias.";
     - sem uma das condições: o motivo da E14-04 (`recebimento_pendente` com a lista, ou `sem_endereco` com o link para `administracao/retirada/endereco/`), sem formulário.
8. **Em `disponivel_para_retirada`:** a tabela só para leitura, com "Retirada liberada em <data hora>, prazo até <data hora>, no endereço: <endereço da liberação>".
9. **Em `cancelada`:** a tabela só para leitura, com "Rodada cancelada."
10. **Histórico dos recebimentos:** data e hora, produto, quantidade e autor, do mais recente para o mais antigo.

`POST administracao/rodadas/<pk>/recebimento/registrar/` (nome `rodadas_recebimento_registrar`): campos `produto` (pk), `quantidade`, `acionamento`. Sucesso: "Recebimento registrado: <quantidade> <unidade> de <produto>.".

`POST administracao/rodadas/<pk>/retirada/liberar/` (nome `rodadas_retirada_liberar`): só `acionamento` e CSRF.
- Sucesso: 302 para a página de retiradas, com "Retirada liberada. Os compradores foram avisados.".
- `LiberacaoRecusada`: a página de recebimento com 409 e a mensagem.
- `ja_liberada`: 302 para a página de retiradas, com a mensagem da recusa.

## Página de ocorrências

`GET administracao/rodadas/<pk>/ocorrencias/` (nome `rodadas_ocorrencias`), em `aguardando_fornecedor`, `disponivel_para_retirada` e `cancelada` (nesta só para leitura):

11. **Por pedido válido** (ordem de `pk`): o nº do pedido, o nome do comprador e, por item, o produto, a pedida, a reembolsada, a retirada, a descartada e o saldo (`saldo_do_item`).
12. **Formulário**, fora de `cancelada`:
    - campos: item (os itens com saldo maior que zero, rotulados "Pedido <pk> — <comprador> — <produto>"), tipo (Faltante, Incorreto, Não entregue), quantidade, `acionamento`;
    - o texto: "A ocorrência gera o reembolso dos itens afetados, com serviço e frete proporcionais. A devolução é autorizada na página da devolução.".
13. **Lista das ocorrências**, da mais recente para a mais antiga:
    - data e hora, pedido, comprador, produto, tipo, quantidade, etapa ("antes da liberação" ou "depois da liberação") e autor;
    - o reembolso: produtos, serviço, frete e total;
    - o link "Ver devolução" para `financeiro_devolucao` da obrigação (E10); sem obrigação (valor zero), "Sem valor a devolver".

`POST administracao/rodadas/<pk>/ocorrencias/registrar/` (nome `rodadas_ocorrencias_registrar`): campos `item` (pk), `tipo`, `quantidade`, `acionamento`.
- O item precisa ser de um pedido da rodada da rota; senão 404.
- Sucesso: "Ocorrência registrada. Reembolso de <total> (produtos <p>, serviço <s>, frete <f>)." e, havendo parte sem cobertura, "Parte do reembolso ainda não tem cobertura: <valor>. Cubra antes de autorizar a devolução.".

## Página de retiradas

`GET administracao/rodadas/<pk>/retiradas/` (nome `rodadas_retiradas`), só com a rodada liberada (senão 404):

14. **Cabeçalho:** "Retirada liberada em <data hora>. Prazo até <data hora>." e o endereço da liberação.
15. **Por pedido válido e item** (`situacao_da_retirada`): pedida, reembolsada na apuração, em ocorrências, retirada, descartada e saldo. Em cada item com saldo, o formulário de retirada (quantidade, `acionamento`, botão "Registrar retirada").
16. **Itens vencidos** (cenário 23):
    - antes do prazo final: "O descarte fica disponível a partir de <data hora>.", sem formulário de descarte;
    - depois do prazo: a seção "Prazo encerrado — pendentes de decisão", com cada item vencido e o formulário de descarte (quantidade sugerida igual ao saldo, `acionamento`, botão "Registrar descarte").
17. **Histórico:** retiradas e descartes, com data e hora, pedido, comprador, produto, quantidade, tipo (Retirada ou Descarte) e autor.

`POST administracao/rodadas/<pk>/retiradas/registrar/` (nome `rodadas_retiradas_registrar`) e `POST administracao/rodadas/<pk>/descartes/registrar/` (nome `rodadas_descartes_registrar`): campos `item`, `quantidade`, `acionamento`.
- O item precisa ser de um pedido da rodada da rota; senão 404.
- Sucesso: "Retirada registrada: <quantidade> <unidade> de <produto>." ou "Descarte registrado: <quantidade> <unidade> de <produto>.".

## Página da rodada

18. **Bloco "Entrega e retirada"** na página da rodada (`administracao/rodadas/<pk>/estoque/`, como o bloco do pedido formal da E13-04), em `aguardando_fornecedor`, `disponivel_para_retirada` e `cancelada` com pedido formal:
    - a situação: "Aguardando o fornecedor: <n> produto(s) a resolver.", "Retirada liberada; prazo até <data hora>." ou "Rodada cancelada.";
    - os links "Recebimento", "Ocorrências" e, na rodada liberada, "Retiradas".

## Lista de rotas do teste da E08-02

19. **Nomes das rotas:** nenhum contém "pedido", "item", "t0" ou "frete", então a lista de permitidas de `tests/tecnicos/test_pedidos_abertura_tela.py` não muda. Nenhuma das rotas altera pedido congelado, item, `T0` ou frete cobrado.

## Decisões técnicas

- **Sem nova autenticação** nas rotas desta fatia, como no reenvio (E13-04). Nenhuma delas tira dinheiro nem escolhe origem de recursos (infraestrutura 3.2). A devolução da ocorrência é autorizada na página da E10, que exige a passkey.
- **O item vem da rodada da rota.** O pk do item fora dos pedidos da rodada dá 404, sem diferença entre "não existe" e "de outra rodada".
- **A liberação vai para a página de retiradas**, porque é onde o administrador passa a trabalhar.

## Invariantes

- Nenhuma página edita pedido, item, pedido formal ou registro já gravado.
- Toda escrita passa pelos serviços das fatias anteriores.

## Dependências e decisões em aberto

- Depende das E14-01 a E14-05, da E13-04 (convenções) e da E10 (página da devolução).
- Nenhuma decisão em aberto.
