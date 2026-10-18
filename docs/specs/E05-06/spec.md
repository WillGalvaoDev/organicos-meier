# E05-06 — Aviso de alteração de preço

Fatia 6 de 7 da milestone **E05 — Interesses, reservas e progresso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O administrador pode alterar o preço de um produto em qualquer etapa (E03-03). Durante interesse e fechamento, o preço novo atinge os interesses existentes, e os compradores afetados recebem aviso no perfil do site (§5.1).

Esta fatia entrega:

- o receptor do sinal `preco_alterado`, que emite o evento `preco_alterado` (E04-01, canal só site) para cada comprador afetado, na mesma transação da alteração;
- o texto do aviso.

Os totais e o progresso não precisam de recálculo gravado, porque já são calculados na leitura com o preço vigente (E05-04 e E05-05).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §5.1 | Atualizações do administrador atingem interesses existentes durante interesse e fechamento. Compradores afetados recebem notificação no perfil do site. Recalcular totais e progresso. Pedidos em pagamento preservam o preço congelado. |
| Especificação §12 | Alteração de preço de item no carrinho: produto afetado, preço atualizado e impacto no interesse. Notificação no site obrigatória. |
| Especificação §4.4 | O congelamento das condições não se aplica a preços. |
| Cenários §16 | 72 (preço alterado no fechamento atinge os interesses). |
| E03-03 | `editar_produto` envia `preco_alterado` dentro da transação, com `produto`, `anterior` e `novo`. Um receptor que falha desfaz a edição. |
| E04-01, E04-02 | Evento `preco_alterado` só no site; `emitir_evento` na mesma transação do fato, com chave derivada do fato. |
| Milestone E05, herdado da E04 | Redigir título, corpo e link do aviso, com produto, preço novo e impacto no interesse. |

## Escopo

**Dentro:**

- O receptor de `preco_alterado` em `apps.interesses`.
- O argumento `alteracao` no envio do sinal.
- O texto do aviso.

**Fora:**

- Pedidos congelados (E08). As parcelas `em_pedido` não recebem aviso, porque o preço delas está no pedido.
- Outros canais: `preco_alterado` é só site na matriz da E04-01.

## Decisões técnicas

- **Chave do fato.** A alteração de preço já grava uma entrada de auditoria `produto.alterar_preco` (E03-03).
  - `editar_produto` passa essa entrada no sinal, com o argumento novo `alteracao`.
  - A chave de cada aviso é `f"preco_alterado:{alteracao.pk}:{conta.pk}"`.
  - Duas alterações seguidas geram avisos separados. Uma reexecução do mesmo fato não duplica.
- **Afetados:** os compradores com pelo menos uma parcela `ativa` do produto, com reserva maior que zero.
  - Só essas parcelas têm valor no carrinho e no progresso (E05-04), e elas só existem enquanto a rodada está em interesse ou fechamento.
  - Pendentes sem reserva não têm valor no carrinho e não recebem aviso. Elas usam o preço vigente quando forem reservadas.
  - Parcelas `em_pedido` mantêm o preço congelado (§5.1).
- **Um aviso por comprador,** com o impacto calculado para ele. Por isso, a emissão usa `emitir_evento` uma vez por comprador, e não `emitir_evento_para_varios`, que exige o mesmo conteúdo para todos (E04-02). O número de compradores é pequeno (§1).
- **Preço igual:** `editar_produto` já não envia o sinal quando o preço não muda (E03-03). Nenhum aviso é emitido.

## Regras

**Sinal** (`apps/catalogo/sinais.py` e `editar_produto`):

- O envio passa a ser `preco_alterado.send(sender=Produto, produto=..., anterior=..., novo=..., alteracao=<EntradaAuditoria>)`, em que `alteracao` é a entrada de `produto.alterar_preco` já gravada na mesma transação.
- O comentário do sinal documenta o argumento novo.

**Receptor** (`apps/interesses/avisos.py`, conectado no `ready()` de `apps.interesses`):

1. Lê os compradores distintos com parcela `ativa` e `quantidade_reservada > 0` do produto, cada um com o reservado total no produto. Usa uma consulta agregada, ordenada por id da conta.
2. Para cada comprador, chama `emitir_evento(Evento.PRECO_ALTERADO, conta, titulo=..., corpo=..., link="/carrinho/", chave=...)`.
3. Roda dentro da transação de `editar_produto`. Uma falha na emissão desfaz a alteração de preço, como já acontece com os receptores da E03-03.

**Texto do aviso.** Os valores usam o filtro `reais`, e `R$ <valor>` é o resultado dele, já com o prefixo e sem repeti-lo (E05-04). As quantidades usam `formatar_quantidade`.

- `titulo`: `"Preço alterado: " + produto.nome`, cortado em 150 caracteres.
- `corpo`, em uma linha:

  ```
  O preço de <nome> mudou de R$ <anterior> para R$ <novo> por <unidade>. Seu interesse reservado de <q> <unidade> passa de R$ <subtotal anterior> para R$ <subtotal novo>.
  ```

  - `<unidade>` é o rótulo de `Unidade`.
  - Cada subtotal é `calcular_subtotal(preco, q)`.
  - O corpo cabe em 2000 caracteres, porque o nome tem no máximo 150 (E03-03).
- `link`: `"/carrinho/"`, que é um link interno válido (E04-R01).

**Recálculo:** nenhum valor é gravado. Depois da alteração, o carrinho, o catálogo e o progresso mostram os subtotais e o valor elegível com o preço novo. Um valor elegível que cai abaixo do mínimo durante o fechamento não muda a etapa nem o prazo (§7). O retorno ao interesse no fim do fechamento é da E06.

## Interfaces

- `apps/catalogo/servicos.py` (`editar_produto`) e `apps/catalogo/sinais.py`: o argumento `alteracao`.
- `apps/interesses/avisos.py`: o receptor.

## Invariantes

- Cada alteração de preço gera no máximo um aviso por comprador afetado.
- Nenhum aviso para quem não tem reserva do produto.
- O aviso nasce e morre com a alteração de preço: a mesma transação.

## Casos-limite e concorrência

- **Comprador com várias parcelas do produto:** recebe um aviso, com o reservado somado.
- **Alteração no fechamento** (cenário 72): o preço muda, o aviso é emitido e o carrinho mostra o subtotal novo.
- **Alteração com a rodada em `pagamento`:** as parcelas estão `em_pedido`, e nenhum aviso é emitido.
- **Produto sem nenhum interesse:** o preço muda e nenhum aviso é emitido.
- **Comprador com reserva e pendência:** o aviso só cita a quantidade reservada.

## Correção E05-R03 — travas implícitas dos avisos (2026-10-18)

- Cada aviso grava uma notificação com chave estrangeira para a conta, e o Postgres confere essa chave com `FOR KEY SHARE` na conta, enquanto a edição ainda segura a trava do produto.
- Com a conta travada em `FOR UPDATE` por uma operação do comprador ou pela moderação, isso fechava um ciclo de travas. O revisor reproduziu `deadlock detected`.
- A correção fica nas travas de conta (correção E05-R03 da E05-01) e não muda esta fatia:
  - o receptor e a emissão continuam na mesma transação da alteração de preço;
  - nenhum aviso vai para `on_commit`;
  - a edição de preço não ganha trava de conta.
- Os critérios de concorrência são o A-21 da E05-01 e os A-15 e A-16 da E05-07. Os critérios A-1 a A-9 desta fatia continuam valendo sem mudança.

## Dependências e decisões em aberto

- Depende de E03-03, E04-01, E04-02 e E05-01.
- Sem decisões em aberto.
