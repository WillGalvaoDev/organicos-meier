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

## Correção E10-R05 e R09 — estorno sem baixa e adoção na reconsulta (2026-10-30)

Origem: parecer sobre `9ce04ad`, R05 e R09 (`docs/specs/E10-05/review.md`). Valem a correção E10-R04 (ordem das travas das chamadas, E10-04) e a correção E10-R08 (E10-07, `spec.md`). Nenhuma regra comercial muda: as duas correções aplicam a infraestrutura 4.7 (proteção contra devolução em dobro e risco residual) e a extensão de `verificar_estornos` que esta fatia já previa.

### Diagnóstico

- **R09.** A regra "estorno não contabilizado" (E10-04) tratava como já resolvido todo estorno cujo `id_estorno` estivesse associado a alguma parcela. Mas a parcela pode guardar o ID de um estorno que o provedor recusou e que depois concluiu (o risco residual da infraestrutura 4.7). Nessa parcela, em `falha_definitiva` ou `elegivel_excepcional`, o livro não tem baixa nenhuma desse estorno. Duas falhas resultam:
  1. com a conclusão antes da confirmação, `confirmar_devolucao_excepcional` não vê o estorno e **aceita**, e o comprador recebe duas vezes;
  2. com a confirmação antes da conclusão, a conciliação só abre a divergência comum, porque o alerta crítico exige parcela sem `id_estorno`.
- **R05.** Na `elegivel_excepcional`, a reconsulta adota só o estorno `concluido`. Um estorno reencontrado `em_processamento` fica sem acompanhamento (ver E10-04, "Correção E10-R05").

### Estorno sem baixa (substitui "estorno não contabilizado" na E10-04, nesta fatia e na E10-06)

Um estorno do provedor `em_processamento` ou `concluido` é **assumido pelo sistema** quando existe uma parcela com o mesmo `id_estorno` numa destas situações:
- `solicitada`, `falha_temporaria` ou `em_processamento`: o acompanhamento vai liquidá-lo;
- `concluida`: o F15 `devolucao:<id_estorno>` já o liquidou.

Qualquer outro estorno `em_processamento` ou `concluido` é **sem baixa**, inclusive o da própria parcela quando ela está em `falha_definitiva`, `elegivel_excepcional` ou `concluida_fora_da_plataforma`. Estornos recusados não entram.

### Regras

**`verificar_estornos`, em `falha_definitiva` e em `elegivel_excepcional`** (as mesmas regras nos dois estados):
1. Considera os estornos sem baixa do pagamento.
2. **Escolha do estorno a adotar:** entre os sem baixa com o valor da parcela, primeiro o que tem o `id_estorno` da própria parcela; depois, o mais antigo por `criado_em` e, no empate, pelo `id_estorno`.
3. **Adotado `concluido`:** a parcela passa a `concluida`, com o `id_estorno` e a liquidação F15 `devolucao:<id_estorno>`.
4. **Adotado `em_processamento`:** a parcela grava o `id_estorno`, passa a `em_processamento` e agenda `acompanhar_estorno`.
5. **Alertas na adoção:** são resolvidos o `devolucao_em_falha_definitiva` ou o `devolucao_elegivel_excepcional` da parcela e o `devolucao_concluida_tardiamente` do estorno. O motivo é "estorno encontrado no provedor e adotado".
6. **Só estornos sem baixa de outro valor:** a parcela fica na situação em que está, com o código `verificacao_inconclusiva` e a evidência da reconsulta, como já acontecia na `falha_definitiva`.
7. **Nenhum estorno sem baixa:** na `falha_definitiva`, a parcela passa a `elegivel_excepcional`, como hoje; na elegível, nada muda.

**Conciliação (`devolucao_concluida_tardiamente`).** Um movimento `devolucao` concluído e sem par, com `id_estorno`:
- Se existe parcela do pagamento que assume o estorno (a definição acima), nada muda: o `concluir` dela vai lançar o F15.
- Senão, a parcela relacionada é escolhida entre as do pagamento em `falha_definitiva`, `elegivel_excepcional` ou `concluida_fora_da_plataforma`: primeiro a que tem o mesmo `id_estorno`; depois, uma sem `id_estorno`. O filtro "sem `id_estorno`" deixa de ser exigido.
- O resto da regra não muda: o alerta crítico com os dados da parcela, `devolvida_em_dobro = true` em `concluida_fora_da_plataforma` (sem lançamento), e `verificar_estornos` agendada nos outros dois estados.

**Confirmação excepcional (E10-06, passo 4).** A recusa "há devolução em processamento ou concluída no provedor" vale para qualquer estorno sem baixa do pagamento, inclusive o que tem o ID da própria parcela.

### Invariantes acrescentados

- Um estorno concluído no provedor tem, no máximo, uma baixa no livro: um F15 com a sua chave, ou nenhum, quando a devolução já tinha sido feita fora (alerta crítico de devolução em dobro).
- Enquanto existe um estorno sem baixa do pagamento, nenhuma confirmação excepcional é aceita para as parcelas desse pagamento.
- Nenhuma parcela fica em `elegivel_excepcional` depois de uma reconsulta que viu um estorno sem baixa do valor dela.
