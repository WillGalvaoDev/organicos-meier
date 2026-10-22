# E09-01 — Livro-razão: destinações, movimentos e proibições

Fatia 1 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Divisão da E09

| Fatia | Entrega | Depende de |
|---|---|---|
| E09-01 | Livro-razão: destinações, movimentos e proibições (P-2) | E08 |
| E09-02 | Provedor: tarifa, liberação, saldo e movimentos da conta | E07, E09-01 |
| E09-03 | Alertas financeiros | E04, E09-01 |
| E09-04 | Entradas dos pagamentos e tarifas | E08-04, E09-01 a E09-03 |
| E09-05 | Reserva e aportes | E09-01, E09-03 |
| E09-06 | Apuração no livro, despesas, frete e financiamento das obrigações | E09-04, E09-05 |
| E09-07 | Liquidez, invariante, saídas e conciliação diária | E09-02, E09-06 |
| E09-08 | Telas financeiras do administrador | E09-01 a E09-07 |

**Fronteira com as etapas seguintes.** A E09 entrega o livro-razão e as operações que as etapas seguintes vão chamar:

- a apuração (E11) chama o movimento de apuração da E09-06;
- as devoluções (E10, E11, E12 e E14) usam a obrigação com comprador e a liquidação da E09-06;
- o repasse e o pagamento do frete (E13) usam as saídas da E09-07.

As regras de quando essas operações acontecem continuam nas etapas donas delas. Por isso os cenários 31, 33 e 34 são provados aqui no nível do livro-razão, com as operações chamadas diretamente. Cada etapa seguinte repete o cenário pelo seu fluxo real.

## Contexto e objetivo

O provedor tem um saldo único, mas o dinheiro tem donos diferentes: o fornecedor, o comprador que vai receber de volta, o frete, a plataforma e a reserva. Esta fatia cria o livro-razão, que separa esses valores por destinação. Todo movimento fica registrado de forma imutável e explicada. O servidor recusa qualquer movimento que use recursos de um fornecedor fora do que a P-2 permite.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9.3 | O livro-razão separa custódia, obrigações com fornecedores, receita de serviço, reserva, despesas, obrigações com compradores e frete. Recursos de um fornecedor são exclusivos dele, ressalvadas as devoluções devidas antes do repasse. Movimentação explícita, justificada, rastreável e auditável. A segregação vale com saldo único no provedor. |
| Especificação §14 | Livro-razão e destinações, com movimentações justificadas e auditáveis. |
| Infraestrutura 3.1 | Todo valor tem destinação. Todo movimento é um lançamento só de inserção, com autor, momento, justificativa e vínculo com a origem. Tabela de destinações e granularidade. |
| Infraestrutura 3.2 | Regras de movimentação e proibições (P-2). Lançamentos de regra fixa são do sistema e citam a regra. Os de escolha de origem exigem o administrador com nova autenticação. |
| Infraestrutura 5 | Dinheiro em decimal exato e registros auditáveis e imutáveis. |
| Cenários §16 | 32 |
| Testes técnicos | T-11, primeira metade (a recusa do lançamento entre fornecedores). A segunda metade, o repasse limitado à liquidez, fica na E09-07. |
| AGENTS.md §6 | Dinheiro: decimal exato, lançamentos imutáveis, idempotência e segregação por destinação. |

## Escopo

**Dentro:**

- O app `apps.financeiro`.
- As contas do livro-razão por destinação e chave.
- O movimento com as suas transferências, só de inserção e com trigger.
- O serviço `lancar`, com a lista fechada de fluxos permitidos, a recusa de saldo negativo e a idempotência.
- As consultas `saldo` e `extrato`.

**Fora:**

- Quem gera cada movimento: as fatias E09-04 a E09-07 e as etapas seguintes.
- Telas (E09-08).
- O saldo comprometido da reserva (E09-05).

## Decisões técnicas

- **Partidas como transferências.** Um movimento é um conjunto de transferências `(de, para, valor)`, com `valor > 0` e duas casas. `de` e `para` são contas do livro-razão ou o **exterior**, que é o dinheiro entrando na conta do provedor ou saindo dela. O saldo de uma conta é o que entrou nela menos o que saiu. O exterior não tem saldo.
  - Consequência: a soma dos saldos de todas as contas é o dinheiro que o livro-razão espera na conta do provedor. A E09-07 compara essa soma com o saldo real.
- **Contas por destinação.** A conta é identificada pela destinação e pela chave. Ela nasce no primeiro movimento, uma vez só (`UNIQUE` na destinação e na chave):

  | Destinação | Chave | Contém |
  |---|---|---|
  | `custodia` | rodada, ciclo, comprador, componente (`produtos`, `servico`, `frete`) | o que o comprador pagou antes da apuração |
  | `obrigacao_fornecedor` | fornecedor, rodada | produtos devidos ao fornecedor depois da apuração |
  | `frete` | rodada | frete arrecadado e coberturas de déficit, até o pagamento do frete |
  | `obrigacao_comprador` | obrigação (E09-04, E09-06) | o que já está financiado para uma devolução devida |
  | `receita_servico` | rodada | taxa de serviço dos pedidos válidos |
  | `reserva` | única | aportes menos utilizações |
  | `despesas_a_cobrir` | única | tarifas que o provedor já descontou e que ainda não foram cobertas |

- **O único saldo negativo** permitido é o de `despesas_a_cobrir`. A tarifa sai do saldo do provedor antes de ter uma fonte, e o saldo negativo mostra exatamente o que ainda falta cobrir. Qualquer movimento que deixe outra conta negativa é recusado inteiro.
- **Fluxos permitidos por lista fechada.** A P-2 fica garantida por uma lista do que é permitido, e não por uma lista do que é proibido. Um par (origem, destino) fora da lista é recusado com `MovimentoProibido`, mesmo que o código chamador esteja errado. A lista está em "Regras".
- **Ordem das travas.** O `lancar` trava as contas envolvidas em ordem crescente de `pk` e confere os saldos sob a trava. Ele roda dentro da transação de quem chama e vem depois das travas da E08: `PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento` → contas do livro-razão.
- **Idempotência.** Todo movimento tem uma `chave` única, derivada da origem (por exemplo, `entrada:<destino>`). Repetir com a mesma chave e o mesmo conteúdo devolve o movimento existente, sem gravar nada. Com a mesma chave e conteúdo diferente, levanta `MovimentoConflitante`. Uma repetição nunca vira um segundo lançamento.
- **Autor e justificativa.**
  - No movimento do sistema, o autor é `SISTEMA`, e a justificativa é o código da regra mais um texto fixo (por exemplo, `P-1`).
  - No movimento do administrador, o autor é a conta, a justificativa é um texto não vazio digitado por ele, e uma `EntradaAuditoria` é gravada na mesma transação.

## Regras

**Fluxos permitidos.** Na tabela, `r` é a rodada da conta de origem. "Obrigação da rodada `r`" é uma `obrigacao_comprador` cuja obrigação pertence à rodada `r`.

| Nº | De | Para | Condição |
|---|---|---|---|
| F1 | exterior | `custodia(r, c, b, comp)` | tipo `entrada_de_pagamento` |
| F2 | exterior | `obrigacao_comprador(o)` | tipo `entrada_para_devolucao` |
| F3 | exterior | `reserva` | tipo `aporte` |
| F4 | `despesas_a_cobrir` | exterior | tipo `tarifa` |
| F5 | `custodia(r, c, b, produtos)` | `obrigacao_fornecedor(f, r)` | tipo `apuracao`; `f` é o fornecedor da rodada `r` |
| F6 | `custodia(r, c, b, servico)` | `receita_servico(r)` | tipo `apuracao` |
| F7 | `custodia(r, c, b, frete)` | `frete(r)` | tipo `apuracao` |
| F8 | `custodia(r, c, b, comp)` | `obrigacao_comprador(o)` | tipo `financiamento_de_obrigacao`; `o` é da rodada `r`, do ciclo `c` e do comprador `b` |
| F9 | `obrigacao_fornecedor(f, r)` | `obrigacao_comprador(o)` | tipo `financiamento_de_obrigacao`; `o` é da rodada `r` |
| F10 | `frete(r)` | `obrigacao_comprador(o)` | tipo `financiamento_de_obrigacao`; `o` é da rodada `r` |
| F11 | `receita_servico(qualquer)` ou `reserva` | `despesas_a_cobrir`, `frete(qualquer)` ou `obrigacao_comprador(qualquer)` | tipos `cobertura_de_despesa` ou `financiamento_de_obrigacao` |
| F12 | `obrigacao_fornecedor(f, r)` | exterior | tipo `repasse` |
| F13 | `receita_servico(r)` | exterior | tipo `retirada_de_receita` |
| F14 | `frete(r)` | exterior | tipo `pagamento_do_frete` |
| F15 | `obrigacao_comprador(o)` | exterior | tipo `devolucao` |

Qualquer outra combinação é recusada, inclusive:

- custódia ou obrigação de um fornecedor para destino de outra rodada ou de outro fornecedor;
- custódia ou obrigação de fornecedor para `despesas_a_cobrir`, `reserva` ou `receita_servico`;
- custódia de um comprador para a obrigação de outro comprador;
- um componente para outro, como produtos para receita.

**Recusas de `lancar`, sem nenhuma escrita:**

| Situação | Exceção e código |
|---|---|
| Fluxo fora da lista | `MovimentoProibido("fluxo_nao_permitido")`, com o número do primeiro par recusado e as destinações na mensagem, sem valores |
| Saldo final negativo em conta que não seja `despesas_a_cobrir` | `SaldoInsuficiente`, com a destinação e a chave |
| Valor zero, negativo, com mais de duas casas ou `float` | `MovimentoInvalido("valor")` |
| Movimento sem transferências, com `de == para`, ou com dois sentidos para o mesmo par | `MovimentoInvalido("transferencias")` |
| Autor administrador sem justificativa | `MovimentoInvalido("justificativa")` |
| Mesma chave com conteúdo diferente | `MovimentoConflitante` |
| Fora de transação | `TransactionManagementError` |

**Imutabilidade:** movimentos e transferências só aceitam inserção, pela base `RegistroSoInsercao` mais a trigger `instalar_protecao_so_insercao`. Uma correção é sempre um movimento novo que cita o anterior na justificativa.

## Interfaces

- `Destinacao` (`TextChoices`) e `Componente` (`produtos`, `servico`, `frete`).
- `conta(destinacao, **chave) -> ContaFinanceira`, que cria ou devolve a conta, e `EXTERIOR`, o marcador.
- `Transferencia(de, para, valor)`, uma *dataclass* congelada.
- `lancar(*, tipo, transferencias, autor, justificativa, origem, chave) -> MovimentoFinanceiro`. A `origem` é o objeto de origem: o tipo e a `pk` são gravados como texto, como na auditoria.
- `saldo(conta) -> Decimal`; `extrato(conta) -> list[...]`, em ordem de movimento; `saldo_total_esperado(ate=None) -> Decimal`, a soma de todas as contas, só com os movimentos de momento ≤ `ate` quando informado (E09-07).
- As exceções `MovimentoProibido`, `SaldoInsuficiente`, `MovimentoInvalido` e `MovimentoConflitante`.

## Invariantes

- A soma das transferências que entram e saem de cada conta é o saldo dela. Nenhum saldo fica guardado à parte de forma que possa divergir das transferências.
- Nenhuma conta, exceto `despesas_a_cobrir`, termina um movimento com saldo negativo.
- Nenhum movimento grava pela metade: ou todas as transferências, ou nenhuma.
- Nenhum dinheiro de fornecedor sai por um fluxo fora de F5, F8, F9 e F12, nem é trocado entre fornecedores ou rodadas.
- Nenhum `float` no app, o que a varredura estática da E08-01 já cobre (`apps/`).

## Casos-limite e concorrência

- **Duas retiradas concorrentes da mesma conta,** cada uma menor que o saldo, mas juntas maiores: uma passa e a outra recebe `SaldoInsuficiente`, em qualquer ordem.
- **O mesmo movimento por duas transações** com a mesma chave: um registro só, e a outra devolve o existente.
- **Dois movimentos que travam as mesmas contas em ordens de chamada diferentes:** a trava ordenada por `pk` evita impasse.
- **Um movimento com várias transferências,** em que a última viola o saldo: nenhuma transferência é gravada.

## Dependências e decisões em aberto

- Depende de E08, pelos modelos `Rodada`, `Ciclo`, `Pedido` e `Fornecedor`. Nenhuma decisão em aberto.
- **Limite de verificação:** o comportamento do Mercado Pago não interfere nesta fatia.

## Correções da revisão da E09 (2026-10-22)

O parecer consolidado do agente 3 sobre `34f9547` está em `docs/specs/E09-08/review.md` e reprovou a E09. As correções estão nas fatias afetadas:

| Achado | Classificação | Onde está a especificação | Critérios novos ou alterados |
|---|---|---|---|
| R01 — cobertura duplicada da mesma despesa | bloqueador | esta fatia ("Regra única de travas") e E09-06, "Correção E09-R01" | E09-06 A-20 a A-22 |
| R02 — impasse entre designação e liquidação | bloqueador | esta fatia ("Regra única de travas") e E09-05, "Correção E09-R02" | E09-01 A-19 a A-21; E09-05 A-16 e A-17 |
| R03 — liquidação repetida em paralelo não idempotente | importante | E09-06, "Correção E09-R03" | E09-06 A-23 |
| R04 — relatório do frete sem a cobertura das obrigações | importante | E09-06, "Correção E09-R04" | E09-06 A-25 e A-26 |
| R05 — a tarefa periódica não avalia a reserva | importante | E09-07, "Correção E09-R05" | E09-07 A-24 |
| R06 — identificação de 64 caracteres aborta a conciliação | importante | E09-03 e E09-07, "Correção E09-R06" | E09-03 A-6 (reescrito) e A-13; E09-07 A-25 |
| R07 — janelas da conciliação | importante | E09-07, "Correção E09-R07" | E09-07 A-26 e A-27 |
| R08 — evidência de TDD | bloqueador de processo; **tratamento decidido pelo responsável em 2026-10-22: o mesmo da E05-R04, E06-R05 e E08-R06** | esta fatia, "Correção E09-R08" (vale para toda a E09) | sem critério novo para os antigos; registro e mutação por critério |
| R09 — fontes desatualizadas durante a apuração | bloqueador | esta fatia ("Regra única de travas") e E09-06, "Correção E09-R09" | E09-06 A-24 |
| M-8 — literal `1.000,00` no E09-08 A-3 | melhoria | `docs/melhorias.md`, M-8 | nenhum. Resposta ao implementador: a leitura dele está certa. O A-3 é o valor de R$ 1.000,00 digitado `1000,00`, e a regra de entrada (sem separador de milhar) prevalece. A redação fica para a revisão final das melhorias. |

**Ordem sugerida:**

1. A regra única de travas: primeiro a guarda (A-19 a A-21 desta fatia), porque ela faz a suíte acusar as inversões que ainda existem.
2. R02 e R01, que dependem da regra.
3. R09 e R03.
4. R04, R05, R06 e R07, que são independentes entre si.
5. O registro da R08.

Ao final, o implementador roda:
- a suíte completa, sem `--deselect`;
- o ruff, o mypy e o `makemigrations --check`;
- as nove provas do parecer.

As provas `test_cobertura_cruzada`, `test_ordem_designacao_liquidacao`, `test_mesma_referencia_concorrente` e `test_obrigacao_concorrente_apuracao` esperam a outra operação terminar ou passar por uma barreira enquanto seguram a primeira. Com a correção, a outra operação fica esperando a trava, e essas provas passam a esgotar o tempo em vez de passar. Por isso elas ficam substituídas pelos critérios novos, que liberam a pausa também quando a outra conexão está esperando trava ("Padrão das corridas desta correção", abaixo). As outras cinco provas têm de passar como estão.

### Regra única de travas do financeiro (correção E09-R01, E09-R02 e E09-R09)

Origem: parecer sobre `34f9547`, R01, R02 e R09. Esta regra substitui:
- a "Ordem das travas" desta fatia;
- a regra de travas da E09-05 ("a conta `reserva` primeiro, depois o alvo");
- as travas que a E09-06 descreve operação por operação.

#### Diagnóstico

Os três defeitos têm a mesma causa: **a operação decide com um valor lido antes de travar todas as contas de que a decisão depende.**
- **R01:** a utilização da reserva lê o pendente da despesa travando só a `reserva`. A conta de destino da despesa, que as outras fontes também usam, fica sem trava.
- **R02:** a designação trava a `reserva` e depois a conta da obrigação, enquanto a liquidação trava as duas em ordem de `pk`. Quando a conta da obrigação tem `pk` menor, as ordens se invertem e o PostgreSQL detecta o impasse.
- **R09:** a obrigação lê se o ciclo está apurado e escolhe as fontes antes das travas.

Ordenar por `pk` dentro do `lancar` não resolve, porque as contas já travadas antes dele ficam fora dessa ordem.

#### Regras

1. **O conjunto de contas vem antes de qualquer leitura.** Cada operação do financeiro determina todas as contas que pode ler para decidir ou que pode movimentar. Isso inclui as contas das operações que ela chama na mesma transação, por exemplo:
   - a cobertura automática das tarifas dentro de `registrar_tarifa` e da apuração: `receita_servico(r)` e `despesas_a_cobrir`;
   - o consumo das designações dentro da liquidação: a `reserva`.

   As contas que ainda não existem são criadas antes, por `conta(...)`.
2. **Uma trava só, em ordem.** O conjunto inteiro é travado de uma vez, em ordem crescente de `pk`. Depois disso, a operação não trava nenhuma conta que não esteja no conjunto.
3. **A decisão vem depois da trava.** Tudo o que decide o resultado é lido depois da trava:
   - saldos;
   - pendente da despesa;
   - sem cobertura e financiado da obrigação;
   - liquidado;
   - designações ativas;
   - a existência da apuração do ciclo;
   - movimentos e referências idempotentes.

   Uma leitura feita antes da trava só pode encerrar a operação quando encontra um fato definitivo, como um movimento já gravado, que é imutável: devolver o existente ou recusar o conflitante. Quando a leitura não encontra nada, a busca é refeita depois da trava.
4. **A proteção compartilhada de cada alvo é uma conta.** Todas as fontes que cobrem o mesmo alvo travam a mesma conta antes de ler o que falta. As fontes são a reserva, a receita de uma rodada e a cobertura automática.
   - **Despesa:** a conta de destino dela. É `despesas_a_cobrir` para a tarifa e `frete(r)` para o déficit de frete.
   - **Obrigação com comprador:** a conta `obrigacao_comprador(o)`. Ela é criada se ainda não existir, inclusive na designação, que hoje só trava a conta quando ela já existe.
5. **Ordem geral.** As travas da E08 vêm primeiro (`PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento`). Depois vêm as contas do livro-razão, pela regra acima. Depois, os alertas e avisos.

Conjuntos de contas das operações existentes. O implementador confere e completa esta lista, e a guarda acusa o que faltar:

| Operação | Contas travadas juntas |
|---|---|
| `registrar_aporte`, `desfazer_designacao` | `reserva` |
| `designar_reserva` | `reserva`, `obrigacao_comprador(o)` |
| `utilizar_reserva` | `reserva`, o destino da despesa |
| `cobrir_despesa` pela receita | `receita_servico(rodada_fonte)`, o destino da despesa |
| `cobrir_tarifas_pendentes_da_rodada` | `receita_servico(r)`, `despesas_a_cobrir` |
| `registrar_tarifa` | `despesas_a_cobrir`; com a rodada apurada, também `receita_servico(r)` |
| `registrar_obrigacao_com_comprador` | `obrigacao_comprador(o)`; as três custódias do comprador no ciclo; `obrigacao_fornecedor(f, r)`, `receita_servico(r)` e `frete(r)` (as fontes antes e depois da apuração, porque o estado só é lido depois da trava) |
| `cobrir_obrigacao_com_receita` | `obrigacao_comprador(o)`, `receita_servico(rodada_fonte)` |
| `liquidar_obrigacao` | `obrigacao_comprador(o)`, `reserva` |
| `registrar_apuracao_no_livro` | as custódias dos pedidos válidos, `obrigacao_fornecedor(f, r)`, `receita_servico(r)`, `frete(r)`, `despesas_a_cobrir` |
| `registrar_saida` | a conta da saída |
| entradas da E09-04 | a custódia ou a conta da obrigação de destino, mais as contas da obrigação que a entrada cria |

#### Guarda da ordem (decisão técnica)

A função que trava uma conta do livro-razão (hoje `_travar_conta`) é o único caminho de trava das contas. Ela passa a guardar quais contas a transação mais externa já travou.
- Se a conta pedida ainda não está travada e tem `pk` menor que a maior já travada, a função levanta `OrdemDeTravasViolada` antes de travar. Como a exceção desfaz a transação de quem chamou, nada é gravado.
- Travar de novo uma conta já travada é permitido, em qualquer ordem.
- O registro começa vazio em cada transação mais externa, tanto depois de um commit quanto depois de um rollback.
- A guarda fica ativa sempre, não só nos testes. Ela é uma asserção de programação: no código correto nunca dispara. Num caminho com inversão, ela troca um impasse que só aparece às vezes por um erro determinístico, sem escrita.
- O `lancar` continua travando as contas das transferências em ordem crescente. Com a guarda, um `lancar` que precisaria de uma conta de `pk` menor que a maior já travada falha. Isso obriga quem chama a incluir essa conta no conjunto inicial.

#### Padrão das corridas desta correção

Os critérios de concorrência novos da E09 (E09-05 A-16 e A-17; E09-06 A-20 a A-24) seguem este padrão:

- O teste usa os serviços reais, em transações PostgreSQL, como as provas do parecer. O monkeypatch só pausa a execução num ponto: não retira trava, validação nem efeito.
- A operação A pausa no ponto indicado no critério, e a operação B começa. O teste libera A quando acontecer a primeira destas três coisas:
  - B terminou;
  - B está esperando trava (`tests/apoio/trava.py::outra_conexao_esperando`);
  - B chegou ao seu próprio ponto de pausa.

  O tempo limite é de 15 s. O teste nunca espera só pelo fim de B, porque depois da correção B espera a trava de A e o teste travaria.
- O critério indica a falha esperada no código atual (o Red). Uma falha por tempo esgotado ou por erro de infraestrutura não vale como Red.
- O resultado vale em qualquer ordem: o critério dá o estado final, que é o mesmo de uma das ordens seriais.

#### Invariantes acrescentados

- Nenhuma transação do financeiro trava uma conta de `pk` menor depois de uma de `pk` maior.
- Toda decisão sobre saldo, pendente, cobertura, liquidação ou estado da apuração é tomada com as contas de que ela depende já travadas.

### Correção E09-R08 — evidência de TDD (2026-10-22)

Origem: parecer sobre `34f9547`, R08. Esta seção vale para toda a E09. As outras fatias só remetem a ela.

#### Diagnóstico

Estes critérios não têm Red válido comprovado antes do código de produção:

| Critério | O que o registro mostra |
|---|---|
| E09-01, `extrato` (sem critério próprio na lista) | escrito junto com `saldo`; o teste veio depois, com prova por mutação |
| E09-01 A-2 | o Red falhou porque a conta do andaime não existia, e não porque a mutação fosse permitida; a cronologia das proteções do ORM e do SQL não está registrada |
| E09-06 A-17 a A-19 | as travas foram escritas junto com as operações, sem a sequência "verde funcional sem a trava → Red da corrida → trava"; a mutação detecta A-17 e A-18, mas não A-19 |
| E09-07 A-20 | o `UNIQUE` e o tratamento do conflito vieram antes do Red específico; prova por mutação registrada |

#### Tratamento — decisão do responsável pelo projeto (2026-10-22)

É o mesmo tratamento das correções E05-R04, E06-R05 e E08-R06 (E08-02, `spec.md`, seção "Correção E08-R06"), escolhido de novo para a E09. Ele não vira dispensa automática para as próximas etapas.

1. **Procurar a evidência que existe.** Valem commits locais, logs guardados com data e saídas registradas no momento. Se o implementador encontrar a evidência, registra a referência exata e o critério sai da lista. Não vale execução nova, andaime recriado ou inferência sobre a ordem.
2. **Registrar a não conformidade** numa seção "Não conformidade de TDD" no `review.md` de cada fatia afetada (E09-01, E09-06 e E09-07). A seção traz:
   - os critérios;
   - o que aconteceu;
   - o tratamento aplicado.

   O registro anterior é preservado sem edição, e nenhum texto pode dar a entender que houve Red nesses critérios.
3. **Provar a sensibilidade por mutação**, com o título "sensibilidade (mutação), não Red". Valem as mutações já registradas que cumpram as exigências do E08-R06: o trecho mudado, o comando com os arquivos inteiros e sem `-k`, a falha por asserção e a restauração verde.

   | Critério | Mutação |
   |---|---|
   | E09-01 `extrato` | já registrada (`extrato` devolvendo `[]`); acrescentar uma segunda, que inverte a ordem dos movimentos |
   | E09-01 A-2 | duas mutações, uma por caminho: retirar a recusa do ORM de um dos modelos; retirar a trigger de uma das tabelas |
   | E09-06 A-17 | já registrada (`registrar_obrigacao_com_comprador` sem travas); refazer depois da regra única de travas, sobre o código novo |
   | E09-06 A-18 | já registrada (`liquidar_obrigacao` sem travas); refazer sobre o código novo |
   | E09-06 A-19 | a mutação "apuração sem travas" não é detectada pelo A-19, e o limite fica registrado. A trava das contas da apuração passa a ser provada pelo E09-06 A-24 (ii), em que uma obrigação disputa a custódia com a apuração pausada. Retirar a trava da apuração tem de fazer o A-24 (ii) falhar. Não existe Red real possível para o A-19: a proteção já existe e a entrada concorrente na custódia de um pedido já quitado não acontece pelas regras. Com esse registro, a M-6 é encerrada no `docs/melhorias.md`. |
   | E09-07 A-20 | já registrada (sem o tratamento do `IntegrityError`) |

4. **Correções com Red real.** Todos os critérios novos desta correção (E09-01 A-19 a A-21; E09-03 A-13; E09-05 A-16 e A-17; E09-06 A-20 a A-26; E09-07 A-24 a A-27) seguem Red → Green → Refactor.
   - Os de concorrência registram as duas linhas da prevenção do E08-R06:
     - o verde funcional, que já existe;
     - o Red da corrida, observado no código atual.
   - Cada critério novo indica a falha esperada.
   - O E09-03 A-6 reescrito também precisa de Red: o teste com 81 caracteres passa no código atual, então o Red do par vem do A-13 (80 caracteres aceitos).

Os passos 2 e 3 são o tratamento definitivo dos critérios antigos. Mesmo com esse tratamento, R01 a R07 e R09 só se encerram pelos critérios novos.

#### Prevenção (soma-se às anteriores)

- **Mutação não substitui o Red.** A frase "provei por mutação" só aparece em critério já declarado como não conformidade. Comportamento novo só ganha código de produção depois de um Red observado.
- **A ordem do registro segue a ordem dos fatos.** O registro de cada critério novo mostra o commit ou a saída do Red antes do commit da produção.

## Correções da revalidação da E09 sobre 2930ffd (2026-10-22)

Origem: a revalidação em `docs/specs/E09-08/review.md`, com dois achados:
- o R10, desta fatia;
- o R07 residual, da E09-07, na seção de mesmo título.

Os demais achados foram encerrados e não se reabrem. Valem a "Regra única de travas", o "Padrão das corridas desta correção" e a correção E09-R08. Não há decisão comercial nova.

| Achado | Onde | Critérios novos |
|---|---|---|
| R10: a guarda não acompanha a vida real das travas | E09-01 | A-22 a A-27 |
| R07 residual: a tarifa pareada pela data da despesa | E09-07 | A-28 e A-29 |

Ordem sugerida: o R10 primeiro, porque a guarda sustenta as correções já aprovadas; depois o R07 residual. A suíte inteira roda ao fim (A-21).

### Correção E09-R10: o registro da guarda segue as travas retidas

**Diagnóstico.** O registro das contas travadas é identificado pelo objeto `Atomic` mais externo. Esse objeto não identifica uma execução de transação, porque o mesmo `Atomic` pode ser usado várias vezes. Isso acontece no uso como decorador e no `with` repetido sobre o mesmo objeto.

Além disso, o rollback de um savepoint libera as travas pedidas dentro dele, mas o registro não as retira. O resultado, mostrado pelas provas do parecer, é que a guarda recusa um uso válido e aceita a inversão que deveria recusar.

**Regra (substitui o terceiro item da "Guarda da ordem").** O registro da guarda é, a todo momento, o conjunto das contas cuja trava a transação corrente ainda retém no PostgreSQL:

| Evento | Efeito no registro |
|---|---|
| início de uma execução da transação mais externa: cada `with` e cada chamada de função decorada, mesmo com o mesmo objeto `Atomic` | começa vazio |
| commit ou rollback dessa transação | é descartado; nada passa para a execução seguinte |
| trava pedida dentro de um savepoint que é desfeito (rollback do `atomic` interno) | a conta sai do registro, a menos que já estivesse travada antes desse savepoint |
| trava pedida dentro de um savepoint que é liberado (o `atomic` interno termina sem erro) | a conta continua no registro, porque a trava passa para o bloco de fora |
| savepoints aninhados | o mesmo, nível a nível: desfazer um nível retira as travas pedidas nele e nos níveis internos a ele |

- **Recusa.** Continua igual: pedir uma conta ainda não registrada com `pk` menor que a maior registrada levanta `OrdemDeTravasViolada` antes de travar.
- **Trava repetida.** Travar de novo uma conta registrada continua permitido.
- **Conta liberada pelo savepoint.** A conta que saiu do registro pelo rollback de um savepoint é tratada como não travada: pedi-la de novo segue a regra da ordem.
- **No `TestCase` do Django.** Os blocos do próprio caso de teste continuam fora da guarda. A transação da guarda é cada execução do bloco `atomic` mais externo que não pertence ao caso de teste. Esse bloco é um savepoint. O registro começa vazio a cada execução e é descartado ao fim dela, liberada ou desfeita.
- **Fora de transação.** Não há registro; o `select_for_update` já é recusado pelo Django.

**Restrições técnicas (decisão técnica).**
- A identidade do objeto `Atomic`, sozinha, não identifica a execução.
- Não valem:
  - monkeypatch do Django;
  - subclasse de `Atomic` em uso pela aplicação;
  - recusar formas válidas de `transaction.atomic` (decorador, objeto reutilizado, savepoints, `savepoint=False`);
  - desligar a guarda ou afrouxar os A-19 a A-21.
- **Mecanismo sugerido, não obrigatório:** o modelo que o próprio Django documenta para `transaction.on_commit`. Os callbacks são descartados no rollback do savepoint em que foram registrados e somem ao fim da transação. O mecanismo escolhido e a justificativa ficam no `review.md` desta fatia.
- O custo por trava continua sem consulta extra ao banco além do `select_for_update`, salvo justificativa registrada.
