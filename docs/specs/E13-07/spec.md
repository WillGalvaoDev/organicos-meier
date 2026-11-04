# E13-07 — O portal do fornecedor: consultas com lista fechada de campos

Fatia 7 de 8 da milestone **E13 — Pedido formal, repasse e portal do fornecedor**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E13-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E13-01.

## Contexto e objetivo

A conta de fornecedor consulta somente o fornecedor vinculado a ela (§2, 17.9):
- os produtos, as quantidades agregadas, os preços unitários e os valores totais dos produtos;
- o andamento da rodada, o pedido formal e a previsão de entrega.

Ela não vê pagamentos individuais, dados de compradores, taxa de serviço, reserva nem dados de outro fornecedor. Não altera nada e não compra.

As consultas usam uma **lista fechada de campos**. O filtro pelo fornecedor vinculado fica no conjunto de consulta, inclusive na exportação (infraestrutura 4.13).

Até aqui a conta de fornecedor existe (E02), mas não tem nenhuma tela.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Fornecedor: consulta só o fornecedor vinculado; seus produtos, quantidades, preços unitários, valores totais dos produtos, andamento, pedido formal e previsão. Não vê pagamentos individuais, dados pessoais de compradores, taxa de serviço, reserva nem outros fornecedores. Não altera nada nem compra. Restrições no servidor, inclusive em chamadas diretas e exportações. |
| Especificação §6.2 | O fornecedor vê quantidades agregadas, caixas completas, excedentes, preços unitários, valores totais dos produtos e andamento, sem identidades. |
| Especificação §13, fornecedor | Consulta dos produtos e rodadas com quantidades agregadas, caixas, excedentes, preços unitários, valores totais dos produtos, progresso e etapa; do pedido formal e da previsão. Sem acesso a compras. |
| Infraestrutura 4.13 | Serializadores próprios com lista de campos permitidos; nenhum campo fora dela. Filtro pelo fornecedor vinculado no conjunto de consulta, inclusive em exportações e downloads. Testes de acesso direto por identificador a pagamentos, compradores, taxa de serviço, reserva e outro fornecedor. |
| Herdado da E05 | A consulta usa `progresso_da_rodada(rodada)` sem comprador: quantidades agregadas, caixas, excedentes, preços unitários e valores totais, sem identidades. |
| E02-10 | Política `FORNECEDOR`: o papel de fornecedor com o fornecedor vinculado (`request.fornecedor_vinculado`). |
| Cenários §16 | 21, 67 |
| Testes técnicos | T-25 (lado do fornecedor e do comprador), T-27 |

## Escopo

**Dentro:**
- As três rotas do fornecedor e os serializadores com lista fechada.
- A exportação do pedido formal.
- O link na página inicial.
- Os testes de recusa por acesso direto.

**Fora:**
- Qualquer escrita pelo fornecedor (não existe).
- A retirada e as ocorrências (E14).

## Regras

1. **Política:** as rotas usam `exige_fornecedor` (E02-10). Comprador, administrador e anônimo são recusados como a política define (403, ou o login para o anônimo).
2. **Filtro no conjunto de consulta:**
   - toda consulta parte de `Rodada.objects.filter(fornecedor=request.fornecedor_vinculado)` ou `Produto.objects.filter(fornecedor=request.fornecedor_vinculado)`;
   - uma rodada de outro fornecedor, ou inexistente, dá 404, sem diferença entre os dois casos;
   - o identificador da rota nunca é usado fora desse filtro.
3. **Serializadores com lista fechada:** cada consulta é montada por uma função que devolve dicionários só com as chaves listadas abaixo, e a página só usa o que essa função devolve. Um teste compara o conjunto de chaves com a lista. Nenhum objeto de modelo chega ao template.

**Painel** `GET fornecedor/` (nome `fornecedor_painel`):

4. **Campos:**

| Bloco | Chaves |
|---|---|
| Fornecedor | `nome` |
| Produto (do fornecedor vinculado, por nome) | `nome`, `unidade`, `preco_unitario`, `multiplo` |
| Rodada (do fornecedor vinculado, da mais recente para a mais antiga) | `numero` (o `pk`), `etapa` (o rótulo), `aberta_em` (data em Brasília) |

**Rodada** `GET fornecedor/rodadas/<pk>/` (nome `fornecedor_rodada`):

5. **Andamento:** `etapa` (o rótulo) em todas as etapas.
6. **Em `interesse`, `fechamento` e `fechamento_encerrado`:** o progresso agregado de `progresso_da_rodada(rodada)` sem comprador.

| Bloco | Chaves |
|---|---|
| Rodada | `progresso_percentual` |
| Produto | `nome`, `unidade`, `preco_unitario`, `total_em_interesse` (o total reservado), `caixas_completas`, `faltam_para_proxima_caixa`, `excedente`, `valor_total` (o valor bruto) |

   Sem o mínimo em valor, sem a participação de nenhum comprador.
7. **Em `pagamento`:** só o andamento e a frase "As quantidades finais serão informadas no pedido formal, depois da apuração." Nada sobre pedidos, pagamentos ou compradores.
8. **Com pedido formal** (em `aguardando_fornecedor`, `disponivel_para_retirada` ou `cancelada`):

| Bloco | Chaves |
|---|---|
| Pedido formal | `numero`, `emitido_em`, `total_produtos` |
| Linha | `nome`, `unidade`, `quantidade`, `multiplo`, `caixas`, `preco_unitario`, `valor_total` |
| Previsão (só em `aguardando_fornecedor`) | `previsao_de_entrega` (a vigente, E13-05) |

   - O fornecedor não vê as tentativas de envio, o destino, o estado do ciclo, o frete, os repasses nem o corpo do e-mail.
   - Na rodada cancelada sem pedido formal: só o andamento.
9. **Link da exportação:** "Baixar pedido formal (CSV)", só com pedido formal.

**Exportação** `GET fornecedor/rodadas/<pk>/pedido-formal.csv` (nome `fornecedor_pedido_formal_csv`):

10. **Arquivo:**
    - **filtro:** o mesmo da regra 2; sem pedido formal na rodada do próprio fornecedor: 404;
    - **resposta:** `text/csv; charset=utf-8`, como anexo `pedido-formal-<pk>.csv`, separador `;`, vírgula decimal;
    - **cabeçalho:** `produto;unidade;quantidade;multiplo;caixas;preco_unitario;valor_total`;
    - **conteúdo:** uma linha por `LinhaDoPedidoFormal`, na ordem do pedido formal, e nenhuma outra coluna nem linha de total.

**Página inicial:**

11. **Link:** a conta de fornecedor vê "Minhas rodadas" (para `fornecedor/`) em `inicio/`.

**Recusas por acesso direto** (cenário 21, T-25, T-27). As rotas existentes já recusam pela política. Esta fatia as confirma com a conta de fornecedor:
12. **Recusas** (403 pela política, sem dados da rota):
    - pedido de comprador (`pedidos/<pk>/`) e o pagamento dele (`pedidos/<pk>/pagar/`);
    - carrinho e interesses (`carrinho/`, `interesses/`);
    - financeiro (`administracao/financeiro/`, `administracao/financeiro/reserva/`, `administracao/financeiro/movimentos/`, `administracao/financeiro/devolucoes/<pk>/`), que mostram taxa de serviço, reserva e devoluções;
    - administração (`administracao/usuarios/` e as páginas da rodada, do pedido formal e das saídas);
    - catálogo do comprador (`catalogo/` e `catalogo/<pk>/`).
13. **Outro fornecedor:** a rodada e a exportação de outro fornecedor dão 404 (regra 2).
14. **Comprador nas rotas do fornecedor:** 403 (T-25).

## Decisões técnicas

- **O progresso em percentual, sem o mínimo em valor.** O §13 lista "progresso" para o fornecedor, e a infraestrutura 4.13 fecha a lista em produtos, quantidades, preços, totais, andamento, pedido formal e previsão. O percentual é o andamento do progresso; o valor do mínimo não está na lista.
- **Nada de quantidades durante o pagamento.** As quantidades congeladas ainda estão sujeitas à apuração (§10). As finais chegam no pedido formal.
- **404 para outro fornecedor.** Responder igual para "não existe" e "não é seu" não revela a existência de rodadas de outros fornecedores (§2).
- **O pedido formal na rodada cancelada.** O registro continua consultável (§7.2: registros preservados), com a etapa "Cancelada". A previsão não aparece, porque não há entrega a prever.

## Invariantes

- Nenhuma resposta do fornecedor tem campo fora das listas desta fatia.
- Nenhuma consulta do fornecedor alcança dados de outro fornecedor.
- O fornecedor não tem nenhuma rota de escrita.

## Dependências e decisões em aberto

- Depende das E13-01 e E13-05, da E05-04 (`progresso_da_rodada`) e da E02-10 (políticas).
- Nenhuma decisão em aberto.
