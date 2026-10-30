# E10-06 — Devolução excepcional confirmada pelo administrador

Fatia 6 de 7 da milestone **E10 — Devoluções**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E10-01.

## Contexto e objetivo

Quando a devolução pelo provedor é comprovadamente inviável (parcela `elegivel_excepcional`, E10-04), o administrador devolve o dinheiro direto ao comprador, por Pix ou transferência, **fora da integração**. A plataforma não executa essa devolução.

A única ação da plataforma é a **confirmação administrativa**, explícita e com nova autenticação. Ela:
- registra pedido, comprador, valor, justificativa, identificação da transferência e comprovante;
- dá baixa na obrigação;
- bloqueia qualquer nova tentativa pelo provedor.

A confirmação é recusada enquanto houver devolução em processamento no provedor, e uma segunda confirmação da mesma parcela também é recusada.

Esta fatia define também o **lançamento no livro-razão** da devolução excepcional, que a E09 deixou para a E10.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9.5 | Devolução excepcional por Pix ou transferência, só quando a via principal for comprovadamente inviável. A plataforma não executa a devolução e não exige que o dinheiro saia da conta do provedor. Confirmação administrativa explícita, com pedido, comprador, valor, justificativa, identificação da transferência e comprovante, e baixa da obrigação. A confirmação é recusada enquanto houver operação pendente para a mesma parcela, e não vale duas vezes. Depois dela, novas tentativas pela plataforma ficam bloqueadas. A obrigação continua integral até a liquidação. Só para devoluções. |
| Infraestrutura 4.7 | Confirmação explícita, com nova autenticação, e comprovante guardado no R2. Dá baixa na obrigação; até lá, a obrigação continua integral. É recusada enquanto houver devolução em processamento no provedor. Somadas, as devoluções concluídas nunca passam do valor pago. |
| Infraestrutura 4.2 | Consulta obrigatória antes da confirmação de devolução excepcional; se a consulta falhar, a ação fica bloqueada. |
| Infraestrutura 3.5 | Liquidada fora do provedor: a conciliação não espera saída e não a aponta como divergência. |
| Infraestrutura 3.1 e 3.3, A1 | A reserva contém os aportes do administrador, que são capital próprio e não receita. |
| Herdado da E09 | Definir o tratamento no livro da devolução excepcional: fora da conta do provedor, sem saída esperada na conciliação. |
| Cenários §16 | 35 e 36 |
| Testes técnicos | T-9 |

## Escopo

**Dentro:**
- O serviço `confirmar_devolucao_excepcional`.
- O registro `ConfirmacaoDeDevolucaoExcepcional` e o comprovante.
- O fluxo F16 no livro-razão e `liquidar_obrigacao_fora_do_provedor`.
- O bloqueio das tentativas depois da confirmação.

**Fora:**
- A tela e a rota (E10-07). Esta fatia entrega o serviço e o armazenamento.
- O armazenamento no R2 de produção (E16). Em desenvolvimento e teste, o armazenamento padrão do Django, como o avatar (E02-09).

## Regras

**`confirmar_devolucao_excepcional(parcela, *, autor, meio, identificacao, justificativa, comprovante)`:**
1. **Autor.** Administrador. Outro: `PermissionDenied`. A nova autenticação (passkey recente) é exigida pela rota (E10-07), como nas outras operações financeiras (`exige_reautenticacao_por_passkey`).
2. **Campos.** Todos obrigatórios. Faltando algum, `ValueError` e nenhuma escrita.
   - `meio`: `pix` ou `transferencia`.
   - `identificacao`: texto de 1 a 100 caracteres, sem o caractere nulo.
   - `justificativa`: texto não vazio, de até 1.000 caracteres.
   - `comprovante`: arquivo PDF, JPEG ou PNG, reconhecido pelo conteúdo (a assinatura dos primeiros bytes), e não só pela extensão, de até 10 MB.
3. **Situação.** Só uma parcela em `elegivel_excepcional`. Qualquer outra situação recusa com `DevolucaoRecusada`:
   - `solicitada`, `falha_temporaria`, `em_processamento` ou `falha_definitiva`, com a mensagem "há devolução pendente na plataforma";
   - `concluida`, com "já devolvida pela plataforma";
   - `concluida_fora_da_plataforma`, com "já confirmada";
   - sem parcela (obrigação `devida`), com "a devolução pela plataforma não foi tentada".
4. **Reconsulta**, antes da transação e sem travas:
   - `consultar_antes_de_decidir(pagamento.referencia_externa)`;
   - `consultar_estornos(pagamento.id_externo)`.

   Se alguma falhar, `ConsultaAoProvedorFalhou` e nada gravado. Se houver estorno não contabilizado (E10-04) `em_processamento` ou `concluido`: `DevolucaoRecusada("há devolução em processamento ou concluída no provedor")`, nada gravado, e `verificar_estornos` agendada para a parcela, que a adota pela regra da E10-05.
5. **Travas e releitura**, numa transação: `PagamentoNoProvedor` → `SituacaoDoPedido`, se houver → parcela. A situação é conferida de novo.
6. **Cobertura.** O valor da parcela precisa estar coberto: o saldo financiado da conta da obrigação mais as designações ativas. Senão, `DevolucaoRecusada` com a mensagem de cobrir antes, como na E10-04.
7. **Gravação**, na mesma transação:
   - a `ConfirmacaoDeDevolucaoExcepcional`, só de inserção e única por parcela, com:
     - a parcela, a obrigação, o pedido e o comprador (nulos em `sem_pedido`);
     - o valor (o da parcela), o meio, a identificação e a justificativa;
     - o comprovante (o arquivo gravado, o nome original, o tipo e o tamanho);
     - o autor e o instante;
   - `liquidar_obrigacao_fora_do_provedor(obrigacao, parcela.valor, referencia=f"excepcional:{parcela.pk}")`;
   - a parcela em `concluida_fora_da_plataforma`, com `concluida_em` e o histórico;
   - a resolução do alerta `devolucao_elegivel_excepcional` da parcela;
   - a auditoria (`EntradaAuditoria`).
8. **Arquivo do comprovante.** Gravado no armazenamento só depois de todas as validações, com nome gerado (sem o nome original no caminho). Se a transação for desfeita, o arquivo é apagado (`on_commit`/limpeza, como no avatar da E02-09). Ele nunca é servido publicamente: só a rota de download da E10-07, para o administrador.

**`liquidar_obrigacao_fora_do_provedor(obrigacao, valor, *, referencia)`** (E09-06, ao lado de `liquidar_obrigacao`):
- **Mesmo comportamento de `liquidar_obrigacao`:**
  - a chave `devolucao_excepcional:<referencia>`, idempotente;
  - a revalidação sob trava;
  - as recusas "passa do que falta devolver" e "passa do que está financiado";
  - o consumo das designações ativas da reserva, em ordem de criação;
  - a resolução dos alertas `aprovado_apos_a_margem` e `duplicidade` quando a obrigação fica liquidada;
  - `avaliar_reserva` no fim.
- **A diferença** é o último movimento: o tipo novo `devolucao_excepcional`, com a transferência **F16** de `obrigacao_comprador(o)` para `reserva`. A justificativa é "Devolução excepcional feita pelo administrador fora da integração (P-5): o recurso que ficou na conta do provedor passa a ser capital do administrador".
- **O liquidado da obrigação** (`_liquidado`, E09-06) passa a somar as saídas da conta da obrigação pelos dois tipos, `devolucao` (F15) e `devolucao_excepcional` (F16).

**F16 na lista fechada de fluxos (E09-01):**

| Fluxo | De | Para | Restrição |
|---|---|---|---|
| F16 | `obrigacao_comprador(o)` | `reserva` | só com o tipo `devolucao_excepcional`, e esse tipo só aceita F16. O único chamador é `liquidar_obrigacao_fora_do_provedor` |

**Bloqueio depois da confirmação:**
- `autorizar_devolucao` devolve a parcela existente, sem nova chamada;
- `tentar_devolucao_de_novo` recusa;
- uma chamada `estornar` ou `acompanhar_estorno` ainda pendente termina em `FalhaDefinitiva("parcela_encerrada")`, sem chamar o provedor (E10-04).

## Decisões técnicas

- **F16 para a reserva (derivado de A1, 3.3 e 3.5).** O administrador devolveu ao comprador com recursos próprios, fora do provedor. O dinheiro que estava destinado a essa obrigação continua na conta do provedor, mas já não é devido a ninguém. Ele passa a ser capital do administrador, que é o que a reserva representa ("aportes do admin, menos as utilizações"). Com isso:
  - a soma do livro-razão não muda, e a conta do provedor também não; a conciliação não precisa de exceção (3.5);
  - nenhum recurso de fornecedor é usado: a parte que veio da rodada já era devida ao comprador (P-2);
  - o invariante 3.4 continua valendo: a obrigação cai, e a reserva sobe pelo mesmo valor.

  Se a obrigação estava coberta por designação da reserva, o consumo da designação (F11) e o F16 se compensam. A reserva fica igual, e o administrador arcou com esse valor por fora, como acontece com o uso da reserva pela via principal.
- **Cobertura exigida.** É a mesma regra da via principal: o livro só baixa o que está financiado. O administrador cobre o que faltar (designação, receita ou aporte) antes de confirmar.
- **Valor da confirmação.** É sempre o valor inteiro da parcela. Uma confirmação parcial não aparece em nenhuma regra, e a obrigação "permanece integralmente registrada enquanto não for liquidada".
- **`sem_pedido`.** A confirmação registra pedido e comprador nulos. A identificação da transferência e a justificativa identificam o pagador.

## Invariantes

- Uma parcela tem no máximo uma confirmação, e a confirmação só existe para parcela que estava em `elegivel_excepcional`.
- Uma obrigação confirmada fica liquidada exatamente pelo valor da parcela, com um F16, e não tem F15.
- Depois da confirmação, nenhuma chamada ao provedor pede estorno para a parcela.
- Somadas, as devoluções de um pagamento (F15 e F16) nunca passam do valor pago.

## Casos-limite e concorrência

- **Duas confirmações em paralelo da mesma parcela:** uma passa, e a outra recusa com "já confirmada". Há um comprovante só gravado, e o arquivo da recusada é apagado.
- **Confirmação e estorno tardio:** ver a E10-05.
- **O provedor fora do ar na reconsulta:** a confirmação fica bloqueada (§4.2).
- **Comprovante com extensão `.pdf` e conteúdo de outro tipo:** recusado.

## Dependências e decisões em aberto

Depende de E10-04, E10-05, E09-01 (lista de fluxos), E09-05 (designações) e E09-06 (liquidação). Nenhuma decisão em aberto. O armazenamento no R2 entra na E16.

## Correções E10-R06 e R07 (2026-10-30)

Origem: parecer sobre `9ce04ad`, R06 e R07 (`docs/specs/E10-06/review.md`). Também valem para esta fatia:
- a correção E10-R03 (E10-04): a cobertura é lida com a conta da obrigação e a `reserva` travadas;
- a correção E10-R09 (E10-05): a recusa do passo 4 vale para qualquer **estorno sem baixa**, inclusive o que tem o ID da própria parcela;
- a correção E10-R08 (E10-07, `spec.md`).

### R06 — a falha da consulta de estornos escapa do contrato de erro

**Diagnóstico.** O passo 4 faz duas consultas. A primeira, `consultar_antes_de_decidir`, traduz as falhas do provedor em `ConsultaAoProvedorFalhou`. A segunda, `consultar_estornos`, é chamada direto, e a falha dela propaga `ProvedorIndisponivel`. A rota da E10-07 só trata `ConsultaAoProvedorFalhou`, e esse caminho não chega ao 503.

**Regra.** As duas consultas do passo 4 passam pela mesma tradução de erros: `ProvedorIndisponivel`, `RecusaDoProvedor` e `PagamentoNaoEncontrado` viram `ConsultaAoProvedorFalhou`. É o mesmo conjunto de `consultar_antes_de_decidir` (E07). Se qualquer uma das duas falhar:
- nada é gravado e nenhum arquivo vai ao armazenamento;
- nenhuma chamada é agendada.

A rota não muda: `ConsultaAoProvedorFalhou` responde 503 com a mensagem de tentar de novo.

### R07 — rollback da transação de quem chama deixa o comprovante órfão

**Diagnóstico.** O arquivo é gravado dentro da transação da confirmação e apagado se ela levantar. Mas, quando a função é chamada dentro de uma transação de quem chama, a transação dela é só um ponto de salvamento. Ela retorna sem erro, a transação de fora é desfeita depois, e o arquivo fica no armazenamento sem confirmação no banco. O Django não tem gancho de rollback para apagar o arquivo nesse momento.

**Regra.**
- A confirmação abre a sua transação com `transaction.atomic(durable=True)`. Chamada dentro de outra transação, ela é recusada com o erro do Django para bloco durável aninhado (`RuntimeError`), antes de qualquer gravação, e sem arquivo.
  - O bloco durável é aceito diretamente dentro da transação de teste do Django (`TestCase` e testes `django_db` sem `transaction=True`). Um teste existente que chame a confirmação dentro de um `atomic` próprio passa a receber o erro. O implementador aponta esse teste no `review.md` e ajusta só o arranjo, sem afrouxar asserção.
  - A rota da E10-07 já chama fora de transação (`ATOMIC_REQUESTS = False`).
- A ordem atual continua: todas as validações e as consultas primeiro, o arquivo gravado dentro da transação durável, e o arquivo apagado se ela levantar.
- Depois do commit, o arquivo fica, e a rota de download o entrega.
- **Limite registrado:** se o processo cair entre a gravação do arquivo e o commit, pode sobrar um arquivo sem confirmação. O contrário nunca acontece: nenhuma confirmação fica sem arquivo. Não há regra de limpeza de órfãos nesta etapa.

**Alternativa descartada.** Gravar o arquivo só em `transaction.on_commit`. A confirmação ficaria gravada sem o arquivo se a gravação depois do commit falhasse, e o comprovante é parte obrigatória da confirmação (§9.5).
