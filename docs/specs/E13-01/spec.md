# E13-01 — Pedido formal: o registro único e congelado do ciclo aprovado

Fatia 1 de 8 da milestone **E13 — Pedido formal, repasse e portal do fornecedor**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7 (29/10/2026).
- Infraestrutura: v1.8 (29/10/2026), com base na especificação v1.7.
- A descrição da milestone 13 cita a base v1.6/v1.7. As seções usadas aqui não mudaram nas versões v1.7/v1.8: §2, §6.2, §10, §12, §13, §14, §16 e 17.9, 17.10, Q-3, R-4 e R-7 da especificação; 3.2, 3.4, 4.2, 4.13 e 4.14 da infraestrutura. As alterações dessas versões são a Q-8 (contestação, §9.6), que não muda o que o fornecedor recebe. A base vigente é v1.7/v1.8, e a milestone é atualizada no fechamento.
- Gate de especificação: feito pelo especificador, por decisão do responsável (descrição da milestone).

## Divisão da E13

| Fatia | Objetivo |
|---|---|
| E13-01 | O pedido formal: o registro único e congelado do ciclo aprovado (conteúdo, linhas e a previsão inicial de entrega), gerado pelo receptor de `resultado_aprovado` |
| E13-02 | O ciclo automático de envio: até três tentativas no total, com o estado do ciclo gravado, a consulta ao provedor, o aviso ao administrador depois da terceira falha e a interrupção pela rodada cancelada |
| E13-03 | O reenvio manual: uma tentativa por acionamento, o token único, a recusa durante o ciclo automático e as corridas |
| E13-04 | As telas do administrador: o pedido consolidado, as tentativas e o botão **Reenviar pedido** |
| E13-05 | A previsão de entrega: o ajuste pelo administrador, o aviso `previsao_de_entrega_alterada` e o que o comprador vê |
| E13-06 | O repasse ao fornecedor e o pagamento do frete: a consulta prévia, o limite pelo liberado e a tela |
| E13-07 | O portal do fornecedor: as consultas com lista fechada de campos, a exportação e as recusas por acesso direto |
| E13-08 | Ponta a ponta com o simulador e o envio de e-mail simulado, incluindo o cancelamento depois do repasse (herdado da E12) |

Ordem de implementação: E13-01 → E13-02 → E13-03 → E13-04 → E13-05 → E13-06 → E13-07 → E13-08. A E13-06 depende só da E13-01. A E13-07 depende das E13-01 e E13-05. As demais dependem das anteriores.

## Contexto e objetivo

Depois da aprovação do resultado válido (E11-06), a plataforma envia automaticamente o pedido formal ao e-mail do fornecedor (§10). O pedido é **único por ciclo aprovado**, tem identificador e conteúdo congelados, e todo envio, automático ou manual, usa esse mesmo conteúdo (infraestrutura 4.14, Q-3, R-4).

Esta fatia cria o registro e o gera na transação da aprovação, sem enviar nada. O envio é da E13-02, o reenvio da E13-03.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §10 | O pedido identifica a rodada, os produtos, as medidas, as quantidades finais, as caixas/múltiplos quando aplicáveis e as condições de entrega pertinentes, sem dados pessoais de compradores. Não envia unidades inadimplentes, caixas inválidas nem quantidades ainda sujeitas à apuração. O prazo padrão de entrega vem do fornecedor. |
| Especificação §7 | Aguardando fornecedor: resultado válido aprovado; pedido formal enviado automaticamente por e-mail. |
| Especificação §14 | Pedido ao fornecedor e repasse: quantidades finais, pedido formal único por ciclo, tentativas de envio com resultados. |
| Especificação §4.1, §4.3 | Dados do fornecedor: e-mail para o pedido formal, prazo padrão de entrega e informações de frete. A previsão pode ser ajustada depois dos pagamentos. |
| Infraestrutura 4.14 | Pedido formal único, gerado uma vez por ciclo aprovado, com identificador e conteúdo congelados (snapshot). Todo envio usa esse mesmo snapshot. |
| Infraestrutura 4.2 | Consulta obrigatória antes do envio do pedido formal (a consulta da aprovação, E11-06, e a de cada envio, E13-02/E13-03). |
| Infraestrutura 8, T-47 | O pedido formal ignora quantidade pendente. |
| Herdado da E08 | O pedido formal parte dos `ItemDoPedido` e `ParcelaNoPedido` (quantidades, caixas e preços congelados), sem dados pessoais. |
| Herdado da E11 | `aprovar_resultado` envia `resultado_aprovado` (`rodada`, `ciclo`, `apuracao`) na transação do avanço. A E13 cria o receptor. Os pedidos válidos e o frete efetivo já estão no livro (`PedidoApurado`, `ApuracaoNoLivro`). |
| Herdado da E12 | Uma rodada `cancelada` não envia pedido formal nem permite reenviá-lo (E13-02 e E13-03). |
| Cenários §16 | 69 (o mesmo pedido em todos os envios), 92, 95 (nenhum segundo pedido formal) |
| Testes técnicos | T-29 (snapshot), T-41 (identificador inalterado), T-47 (pedido formal sem pendentes) |

## Escopo

**Dentro:**
- Os modelos `PedidoFormal`, `LinhaDoPedidoFormal` e `PrevisaoDeEntrega` (só inserção) e `EnvioDoPedidoFormal` (o estado do ciclo, criado aqui e usado pela E13-02).
- O serviço `gerar_pedido_formal(aprovacao)` e o receptor de `resultado_aprovado`.
- A previsão inicial de entrega.

**Fora:**
- O envio e as tentativas (E13-02 e E13-03).
- As telas (E13-04, E13-07).
- O ajuste da previsão (E13-05).

## Modelos

Todos no app `pedidos`. Os registros só de inserção usam a proteção da E01-04 (aplicação e trigger).

**`PedidoFormal`** (só inserção):
- `aprovacao`: um para um com `AprovacaoDoResultado`;
- `ciclo`: um para um com `Ciclo`;
- `rodada` e `fornecedor`, por chave estrangeira;
- `emitido_em`: o instante da aprovação (`AprovacaoDoResultado.aprovada_em`);
- `prazo_entrega_dias`: o prazo padrão do fornecedor no instante da geração;
- `previsao_inicial`: a data da previsão de entrega inicial (regra 5);
- `total_produtos`: a soma dos `valor_total` das linhas;
- `assunto` (até 200 caracteres) e `corpo` (texto): o conteúdo do e-mail, congelado (regra 6).

**`LinhaDoPedidoFormal`** (só inserção), uma por produto com quantidade final maior que zero:
- `pedido_formal`, `produto`;
- `nome`, `unidade`, `preco_unitario`, `multiplo` (nulo sem múltiplo): copiados do `ItemDoPedido` congelado;
- `quantidade`: a quantidade final (regra 3);
- `caixas`: o número de caixas válidas (nulo sem múltiplo);
- `valor_total`: o valor dos produtos dessa linha (regra 4);
- única por `(pedido_formal, produto)`.

**`PrevisaoDeEntrega`** (só inserção):
- `rodada` e `ciclo`;
- `data`: a data prevista, sem hora, no calendário de Brasília;
- `origem`: `padrao` (a inicial) ou `ajuste` (E13-05);
- `autor`: nulo na `padrao`; o administrador no `ajuste`;
- `registrada_em`.

A previsão vigente do ciclo é a de maior `pk`.

**`EnvioDoPedidoFormal`** (o estado do ciclo de envio; único registro desta fatia que muda):
- `pedido_formal`: um para um;
- `situacao`: `em_andamento`, `concluido_com_sucesso`, `concluido_com_falhas` ou `interrompido`;
- `automaticas`: quantas tentativas automáticas foram feitas, de 0 a 3;
- `proxima_tentativa_em`: o instante da próxima tentativa automática; nulo fora de `em_andamento`;
- `concluido_em` e `motivo_da_interrupcao` (vazio, ou `rodada_cancelada`).

Restrições no banco: `automaticas` entre 0 e 3; `proxima_tentativa_em` não nulo se e só se `em_andamento`.

## Regras

1. **Quando:** o receptor de `resultado_aprovado` chama `gerar_pedido_formal(apuracao.aprovacao)` na transação da aprovação. Uma exceção desfaz a aprovação inteira (E11-06), então a geração só levanta exceção por violação de invariante (regra 7).
2. **Quais pedidos:** só os pedidos válidos da apuração no livro (`PedidoApurado` da `ApuracaoNoLivro` do ciclo). Pedidos não pagos, cancelados ou só com unidades invalidadas não entram (§10).
3. **Quantidade final por produto:**
   - é a soma das `ParcelaNoPedido.quantidade` dos itens dos pedidos válidos, menos as que estão em caixa invalidada (`CaixaInvalidada` da `ApuracaoFinal` do ciclo, pelo par produto e caixa);
   - as quantidades pendentes nunca entram, porque não estão em nenhum pedido (R-6, T-47);
   - um produto com quantidade final zero não tem linha;
   - **com múltiplo:** `caixas` é o número de caixas distintas do produto com parcela válida. Toda caixa válida está completa, então `quantidade = caixas × multiplo` (regra 7).
4. **Valor por produto:**
   - é a soma, sobre os itens do produto nos pedidos válidos, de `subtotal − desconto`;
   - o desconto é o valor de produtos das unidades em caixa invalidada, calculado como na E11-03 (`CalculoDoResultado.descontos`, o mesmo valor do estorno proporcional da E11-04);
   - o total do pedido formal é a soma das linhas. Ele é igual ao valor de produtos que a apuração no livro transferiu para a obrigação com o fornecedor (regra 7).
5. **Previsão inicial:**
   - a data de `emitido_em` no calendário de Brasília mais `prazo_entrega_dias` do fornecedor, em dias corridos;
   - gravada como `PrevisaoDeEntrega` de origem `padrao` e em `PedidoFormal.previsao_inicial`.
6. **Conteúdo do e-mail**, gerado uma vez e gravado:
   - **assunto:** `Pedido formal nº <pk> — Orgânicos Méier — <fornecedor>`, cortado em 200 caracteres;
   - **corpo**, nesta ordem, uma informação por linha:
     1. `Pedido formal nº <pk>`
     2. `Fornecedor: <nome>`
     3. `Rodada <pk da rodada>, ciclo <número do ciclo>`
     4. `Emitido em <dd/mm/aaaa hh:mm> (horário de Brasília)`
     5. uma linha em branco e `Produtos:`
     6. uma linha por produto, em ordem de nome e depois de `produto_id`:
        - **sem múltiplo:** `- <nome>: <quantidade> <unidade> × <preço unitário> = <valor total>`;
        - **com múltiplo:** `- <nome>: <quantidade> <unidade> em <caixas> caixa(s) de <múltiplo> <unidade> × <preço unitário> = <valor total>`;
     7. `Total dos produtos: <total>`
     8. uma linha em branco e `Condições de entrega:`
     9. `Previsão de entrega: <dd/mm/aaaa> (prazo padrão de <n> dias)`
     10. `Informações de frete: <informacoes_frete>`, só quando o cadastro tem esse texto.
   - **Formatos:** as quantidades e os valores usam os formatos do projeto (`quantidade_br`, `reais`) e o rótulo da unidade.
   - **Fica de fora:** nome, e-mail ou identificador de comprador, número de pedidos, valores pagos, taxa de serviço, frete cobrado dos compradores, reserva ou outro fornecedor (§2, §10).
7. **Invariantes conferidos na geração.** Uma violação levanta `PedidoFormalIncoerente` e desfaz a aprovação. Isso nunca deve acontecer, e serve de rede contra regressão:
   - `quantidade = caixas × multiplo` em toda linha com múltiplo;
   - o mesmo `preco_unitario` em todos os itens do produto no ciclo;
   - `total_produtos` igual à soma do componente de produtos transferido para a obrigação com o fornecedor pelo movimento da `ApuracaoNoLivro` do ciclo.
8. **Unicidade e repetição:**
   - um pedido formal por aprovação e por ciclo, pelas restrições um para um;
   - chamar `gerar_pedido_formal` de novo para a mesma aprovação devolve o existente, sem escrita.
9. **Estado inicial do envio:** na mesma transação, um `EnvioDoPedidoFormal` com `situacao = em_andamento`, `automaticas = 0` e `proxima_tentativa_em = emitido_em`. A primeira tentativa automática é feita pela tarefa da E13-02.
10. **Auditoria `pedido_formal.gerar`** (autor `SISTEMA`), com o pedido formal, o ciclo, as linhas (produto, quantidade, caixas e valor), o total e a previsão inicial. Sem dado de comprador.
11. **Sem aprovação, sem pedido formal:** `gerar_pedido_formal` exige uma `AprovacaoDoResultado` com resultado `valida`. Um ciclo em pagamento, apurado e não aprovado ou com retorno ao interesse nunca gera pedido formal (§10: nada sujeito à apuração).

## Interface

- `gerar_pedido_formal(aprovacao: AprovacaoDoResultado) -> PedidoFormal`: exige transação aberta (`TransactionManagementError`); idempotente pela regra 8.
- `previsao_vigente(ciclo) -> PrevisaoDeEntrega | None`.
- `class PedidoFormalIncoerente(Exception)`.

## Decisões técnicas

- **A geração na transação da aprovação, e o envio depois.** O snapshot é a decisão irreversível, e a aprovação já consulta o provedor fora da transação (E11-06). Ele nasce com o avanço da rodada, então não existe rodada `aguardando_fornecedor` sem pedido formal. O envio, que fala com um serviço externo, fica na tarefa da E13-02.
- **O valor por linha vem do mesmo cálculo da apuração.** Recalcular o desconto pela E11-03 dá o mesmo valor determinístico do estorno proporcional. A conferência com o livro (regra 7) garante que o fornecedor vê exatamente o que lhe é devido.
- **O prazo padrão conta a partir da emissão.** O prazo é do fornecedor (§4.1, §10), e o pedido formal é o pedido feito a ele, então a contagem começa na emissão do pedido. O ajuste é do administrador (E13-05).
- **O destino do e-mail não faz parte do snapshot.** O conteúdo é congelado; o endereço é lido do cadastro a cada tentativa e registrado nela (E13-02). Assim, o reenvio depois de corrigir o e-mail do fornecedor continua usando o mesmo pedido formal.
- **O frete não aparece no pedido.** O fornecedor vê produtos, quantidades, preços unitários e totais de produtos (§2, 17.9). O frete efetivo é um valor da plataforma.

## Invariantes

- No máximo um pedido formal por ciclo; nenhum pedido formal sem aprovação válida.
- O conteúdo e as linhas nunca mudam depois de gravados.
- `total_produtos` = soma das linhas = produtos transferidos para a obrigação com o fornecedor na apuração.
- Nenhum campo do pedido formal identifica um comprador.

## Casos-limite e concorrência

- **Aprovações concorrentes:** a E11-06 já recusa a segunda (`ja_aprovado`, sob a trava da rodada). Por isso só uma transação gera o pedido formal, e as restrições um para um são a última defesa.
- **Produto com todas as unidades invalidadas:** sem linha.
- **Produto fracionário** (por exemplo, kg com incremento 0,25): a quantidade aparece com até três casas, no formato do projeto.
- **Fornecedor sem informações de frete:** sem a linha 10 do corpo.

## Dependências e decisões em aberto

- Depende da E11 (aprovação, caixas invalidadas e apuração no livro) e da E01-04 (só inserção).
- Nenhuma decisão em aberto.
