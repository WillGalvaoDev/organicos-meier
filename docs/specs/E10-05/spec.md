# E10-05 — Conciliação dos estornos e conclusão tardia

Fatia 5 de 7 da milestone **E10 — Devoluções**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E10-01.

## Contexto e objetivo

Desde a E10-03, o provedor mostra cada estorno concluído como um movimento `devolucao`, com o `id_estorno`. Desde a E10-04, cada parcela concluída tem no livro o movimento `devolucao:<id_estorno>`. A conciliação diária (E09-07) ainda trata todo `devolucao` como divergente. Esta fatia faz três coisas:

1. **Pareia** o movimento `devolucao` do provedor com o lançamento do livro, nos dois recortes da E09-07: o do dia e o do instante `t`.
2. **Detecta o risco residual da infraestrutura 4.7:** o provedor conclui tarde um estorno que o sistema já tinha como falha definitiva, elegível ou devolvido de forma excepcional. Isso abre um alerta **crítico**. Quando ainda não houve devolução excepcional, a parcela adota o estorno e é liquidada pela via principal.
3. **Confirma** que a devolução excepcional (E10-06) não gera nada na conciliação. Ela não tem saída da conta do provedor e não é divergência (infraestrutura 3.5).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.5 | Toda saída da conta do provedor é registrada no livro, inclusive a devolução pela plataforma. A devolução excepcional é liquidada fora do provedor e não é divergência. |
| Infraestrutura 4.7 | Risco residual: o provedor conclui tardiamente uma devolução declarada como falha definitiva. A conciliação o detecta e gera alerta crítico. |
| Infraestrutura 3.6 | Divergência na conciliação diária. |
| Herdado da E09 | O par dos movimentos `devolucao` na conciliação (E09-07); E09-07: "A E10 acrescenta o par dos movimentos `devolucao` e exclui as devoluções excepcionais da conciliação." |

## Escopo

**Dentro:**
- O par do tipo `devolucao`.
- O alerta `devolucao_concluida_tardiamente`.
- A adoção tardia pela parcela.
- A prova de que a excepcional não aparece na conciliação.

**Fora:**
- O que fazer depois de uma devolução em dobro, isto é, excepcional mais estorno tardio: a recuperação do valor junto ao comprador é operação do administrador, fora do sistema nesta etapa.
- Telas (E10-07 e E15).

## Regras

**Par do `devolucao`** (a linha nova da tabela de classificação da E09-07):

| Movimento do provedor | Par esperado | Sem par |
|---|---|---|
| `devolucao` | o movimento do livro com a chave `devolucao:<id_estorno>` e total igual ao valor, em módulo. No recorte até `t`, só vale com `momento ≤ t` | `divergencia_na_conciliacao` (chave `id_movimento`) e, conforme a tabela abaixo, o alerta crítico |

Um movimento `devolucao` sem `id_estorno` não tem par: é divergência, com o alerta comum.

**Sem par: o que mais acontece**, olhando a parcela que tem esse `id_estorno` ou, se nenhuma tem, as parcelas do mesmo pagamento (`id_externo` do movimento):

| Situação encontrada | Efeito |
|---|---|
| uma parcela com esse `id_estorno` em `solicitada`, `falha_temporaria` ou `em_processamento` | só a divergência comum. O `concluir` da parcela ainda vai lançar o F15, e a pendência se resolve na conciliação seguinte (E10-01) |
| uma parcela do pagamento em `falha_definitiva` ou `elegivel_excepcional`, sem `id_estorno` | `devolucao_concluida_tardiamente` (crítico, chave `id_estorno`), com a parcela, a situação, o valor e o pagamento. A conciliação agenda `verificar_estornos` para a parcela |
| uma parcela do pagamento em `concluida_fora_da_plataforma` | `devolucao_concluida_tardiamente` (crítico), com os mesmos dados e `devolvida_em_dobro = true`. Não há lançamento automático |
| nenhuma parcela relacionada | só a divergência comum |

**Extensão de `verificar_estornos` (E10-04).** Ela passa a agir também em `elegivel_excepcional`, com as mesmas regras de adoção. Um estorno não contabilizado `concluido`, com o valor da parcela, é adotado: a parcela passa a `concluida`, com a liquidação F15 `devolucao:<id_estorno>`. Os alertas `devolucao_elegivel_excepcional` e `devolucao_concluida_tardiamente` desse estorno são resolvidos, com o motivo "estorno concluído tardiamente pelo provedor e adotado".

Em `concluida_fora_da_plataforma`, a parcela não muda.

**Devolução excepcional.** O movimento da E10-06 não tem transferência de ou para o exterior. Por isso não muda `saldo_total_esperado`, não é aporte nem saída, e não entra em nenhum recorte. A conciliação não precisa de regra para ele. Os critérios provam isso.

## Interfaces

- `conciliar_dia(data)`, com a mesma assinatura.
- O tipo de alerta `devolucao_concluida_tardiamente`, com gravidade crítica.
- `verificar_estornos`, com a extensão acima.

## Invariantes

- Um movimento `devolucao` do provedor tem par exatamente quando a parcela do seu `id_estorno` está `concluida` com o F15 de mesmo valor.
- Nenhum estorno concluído no provedor fica sem alerta enquanto não tiver par.
- A conciliação nunca lança dinheiro no livro.

## Casos-limite

- **Estorno concluído às 23:50 de `D` e `concluir` da parcela às 00:10 de `D + 1`, com `t` às 23:55:**
  - no recorte do dia, há par na execução (classificação sem `ate`);
  - no recorte até `t`, o F15 ainda não existe, e o movimento entra como sem par. A diferença fica zero, como no caso da tarifa da E09-07.
- **Dois estornos de mesmo valor do mesmo pagamento:** cada um pareia pelo seu `id_estorno`, e nunca pelo valor.
- **Estorno tardio e excepcional confirmados em paralelo:** a E10-06 recusa a confirmação se a reconsulta mostrar o estorno. Se o estorno só aparecer depois da confirmação, vale a linha `concluida_fora_da_plataforma` acima.

## Dependências e decisões em aberto

Depende de E10-03, E10-04, E10-01 e E09-07. Fica fora do sistema nesta etapa a recuperação de uma devolução em dobro. Não há regra comercial sobre ela. A E15 trata o alerta crítico no painel. Nenhuma decisão em aberto para esta fatia.
