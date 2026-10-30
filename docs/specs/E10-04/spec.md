# E10-04 — Devolução pela plataforma: parcela, autorização, estados, nova tentativa e liquidação

Fatia 4 de 7 da milestone **E10 — Devoluções**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E10-01.

## Contexto e objetivo

Uma obrigação com comprador (E09-06) é dinheiro devido e ainda não devolvido. Ela vem de duas origens:
- um reembolso da E10-02;
- um pagamento que não quitou, com destino `devolucao` ou `sem_pedido` (E09-04).

Esta fatia leva a obrigação até o dinheiro devolvido pela via principal, o provedor integrado:
1. o administrador autoriza;
2. o sistema registra a **parcela de devolução**, com a chave de idempotência gravada antes, e agenda o estorno (E07-04);
3. a tarefa chama o provedor (E10-03) e aplica cada resposta: concluída, em processamento, falha temporária com nova tentativa pela mesma chave, ou falha definitiva;
4. na falha definitiva, o sistema reconsulta o provedor antes de declarar a parcela **elegível para devolução excepcional** (E10-06);
5. na conclusão, a obrigação é liquidada no livro-razão (`liquidar_obrigacao`, E09-06).

Autorização não é dinheiro devolvido (§9.2). Cada estado fica visível e auditável.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9.2 | O administrador autoriza estornos manualmente no dashboard. A plataforma executa a devolução, que é a via principal. Exibir solicitados, pendentes, concluídos e falhos, com retentativa segura. Autorização não equivale a dinheiro devolvido. Estornos sucessivos não passam do valor pago nem devolvem duas vezes a mesma parcela. |
| Infraestrutura 4.7 | Estados por parcela: devida → solicitada → concluída; falha temporária → nova tentativa com a mesma chave; falha definitiva comprovada → elegível. "Comprovadamente inviável": resposta definitiva guardada como evidência, e reconsulta do pagamento e das devoluções antes de passar a elegível. Todas as origens usam os mesmos estados e a mesma proteção. |
| Infraestrutura 4.2 | Consulta obrigatória antes de autorizar ou repetir uma devolução; se falhar, a ação fica bloqueada. Chave de idempotência por parcela, gravada antes da chamada. Chamadas pendentes na mesma transação da mudança de estado. |
| Infraestrutura 3.6 | Alertas de devolução com falha ou em falha definitiva, e de devolução elegível para excepcional. |
| Herdado da E07 | Operação de `ChamadaAoProvedor` com a chave por parcela (E07-04); a autorização e a nova tentativa chamam `consultar_antes_de_decidir` (E07-06); correção E07-R01: agendar antes de travar o que o `concluir` trava, ou usar um alvo próprio. |
| Herdado da E08 | Os destinos `devolucao` e `sem_pedido` exigem tratamento definido na E10. |
| Herdado da E09 | A execução no provedor termina com `liquidar_obrigacao(obrigacao, valor, referencia=...)`, que consome as designações da reserva e resolve os alertas `aprovado_apos_a_margem` e `duplicidade`. Alertas com `abrir_alerta` (E09-03). |
| Testes técnicos | T-8 |

## Escopo

**Dentro:**
- O modelo `ParcelaDeDevolucao` e o histórico dela.
- Os serviços `autorizar_devolucao` e `tentar_devolucao_de_novo`.
- As operações `estornar`, `acompanhar_estorno` e `verificar_estornos`.
- O gancho de falha temporária em `Operacao` (E07-04).
- Os alertas novos de devolução.

**Fora:**
- A confirmação excepcional (E10-06).
- O par na conciliação e a conclusão tardia (E10-05).
- As telas, as rotas e os avisos ao comprador (E10-07).
- Quem cria as obrigações dos reembolsos (E11, E12 e E14).

## Modelo

**`ParcelaDeDevolucao`**, uma por obrigação. É um registro de estado, como a `TentativaDePagamento` da E08:

| Campo | Definição |
|---|---|
| `obrigacao` | `OneToOne` com `ObrigacaoComComprador` |
| `pagamento` | o `PagamentoNoProvedor` estornado (regra abaixo) |
| `valor` | o que faltava devolver na autorização: devido menos o liquidado. Não muda depois |
| `situacao` | tabela de estados abaixo |
| `chave_idempotencia` | texto único, gerado e gravado na autorização, antes de qualquer chamada |
| `id_estorno` | o do provedor, único quando preenchido |
| `codigo_da_falha` | o último código de falha, ou vazio |
| `evidencia` | JSON: a recusa definitiva (código e instante) e o resultado da reconsulta (os estornos vistos, com situação e valor) |
| `autorizada_por` | a conta, ou nula para `SISTEMA` |
| `autorizada_em` e `concluida_em` | instantes |

**`HistoricoDaDevolucao`**, só de inserção. Uma linha por mudança de situação, com a parcela, a situação nova, o instante, o autor e os dados (código, `id_estorno`, tentativas).

**Pagamento estornado:**

| Origem da obrigação | Pagamento |
|---|---|
| `Reembolso` (E10-02) | o `quitado_por` da `SituacaoDoPedido` do pedido |
| `DestinoDoPagamento` (E09-04, `devolucao` ou `sem_pedido`) | o pagamento do destino |
| outra | `ValueError`: não executável por esta etapa |

## Estados

| Situação | Significado | Grupo exibido (§9.2) |
|---|---|---|
| (sem parcela) | devida, aguardando autorização | pendente |
| `solicitada` | autorizada, com o estorno agendado ou em tentativa | solicitado |
| `falha_temporaria` | a última tentativa falhou de forma temporária; nova tentativa automática com a mesma chave | falho |
| `em_processamento` | o provedor aceitou e ainda não concluiu | pendente |
| `falha_definitiva` | o provedor recusou de forma definitiva; reconsulta em andamento | falho |
| `elegivel_excepcional` | falha definitiva comprovada pela reconsulta | falho |
| `concluida` | estornado pelo provedor e liquidado no livro | concluído |
| `concluida_fora_da_plataforma` | confirmada pelo administrador (E10-06) | concluído |

Transições permitidas:
- `solicitada` → `falha_temporaria`, `em_processamento`, `concluida` ou `falha_definitiva`;
- `falha_temporaria` → as mesmas, inclusive ela própria, quando o código muda;
- `em_processamento` → `concluida` ou `falha_definitiva`;
- `falha_definitiva` → `elegivel_excepcional`, `em_processamento` ou `concluida` (estorno encontrado pela reconsulta);
- `elegivel_excepcional` → `concluida_fora_da_plataforma` (E10-06).

`concluida` e `concluida_fora_da_plataforma` são finais. Qualquer outra transição é recusada no serviço.

## Regras

**`autorizar_devolucao(obrigacao, *, autor)`:**
1. **Autor.** Precisa ser uma conta com papel de administrador, ou `SISTEMA`, para as etapas que já trazem a autorização na própria ação, como o cancelamento com reembolso (infraestrutura 4.8, E12). Outro autor: `PermissionDenied`, sem escrita.
2. **Reconsulta.** Antes de abrir a transação e sem segurar travas, `consultar_antes_de_decidir(pagamento.referencia_externa)` (E07-06). Se ela falhar, `ConsultaAoProvedorFalhou` sobe e nada é gravado.
3. **Travas**, numa transação, na ordem global: `PagamentoNoProvedor` → `SituacaoDoPedido` do pedido, se houver. Depois, a releitura da parcela.
4. **Parcela já existente:** devolve a existente, sem nada novo (idempotente; duplo clique).
5. **Recusas**, todas com `DevolucaoRecusada` e a mensagem, sem escrita:
   - nada a devolver (devido menos o liquidado ≤ 0);
   - o pagamento não está aprovado na situação sincronizada;
   - a obrigação não está coberta: `sem_cobertura_da_obrigacao` maior que zero (E09-05). A mensagem diz para cobrir antes, por designação da reserva, receita ou aporte. Assim o livro sempre consegue liquidar o que o provedor devolver;
   - a soma dos `valor` de todas as parcelas do mesmo pagamento, com a nova, passaria do valor do pagamento.
6. **Gravação**, na mesma transação:
   - a parcela `solicitada`, com o valor, uma chave nova (UUID), o autor e o instante;
   - a linha do histórico;
   - uma entrada de auditoria (`EntradaAuditoria`);
   - `agendar_chamada("estornar", f"parcela:{pk}", chave_idempotencia=parcela.chave_idempotencia)`.

   O alvo é próprio da parcela, então a regra da E07-R01 está atendida.

**Operação `estornar`:**
- **`executar`** lê a parcela sem trava.
  - Em `concluida`, `concluida_fora_da_plataforma` ou `elegivel_excepcional`, levanta `FalhaDefinitiva("parcela_encerrada")`, sem chamar o provedor. É o bloqueio de novas tentativas depois da confirmação excepcional (§9.5).
  - Senão, chama `estornar(NovoEstorno(pagamento.id_externo, parcela.valor, chamada.chave_idempotencia))`.
  - `SaldoInsuficienteParaEstorno` vira `FalhaTemporaria("saldo_insuficiente")`. `PagamentoNaoEncontrado` segue `nao_encontrado(chamada)` (E07-04).
- **`concluir(chamada, estorno)`** trava `PagamentoNoProvedor` → `SituacaoDoPedido` → parcela e relê. Se a parcela já está final, não faz nada.
  - `concluido`:
    - `id_estorno`, `concluida` e `concluida_em`;
    - `liquidar_obrigacao(obrigacao, parcela.valor, referencia=estorno.id_estorno)`. A chave do movimento é `devolucao:<id_estorno>`, o par da E10-05;
    - resolve os alertas `devolucao_com_falha` e `devolucao_em_falha_definitiva` da parcela.
  - `em_processamento`: `id_estorno` e `em_processamento`, e `agendar_chamada("acompanhar_estorno", f"parcela:{pk}")`.
  - `recusado`: segue a falha definitiva abaixo.
- **`adiada(chamada, codigo)`** é o gancho novo, chamado na falha temporária (abaixo). Ele trava a parcela, que passa a `falha_temporaria` com o código, e grava o histórico. Abre `devolucao_com_falha` (chave `parcela:<pk>`), com o código e as tentativas, quando o código é `saldo_insuficiente` ou quando a chamada chega a 3 tentativas.
- **`falhou(chamada, erro)`**, na recusa definitiva:
  - com `parcela_encerrada`, não faz nada;
  - senão, trava `PagamentoNoProvedor` → `SituacaoDoPedido` → parcela. A parcela passa a `falha_definitiva`, com o código e a evidência da recusa. Abre `devolucao_em_falha_definitiva` (chave `parcela:<pk>`) e agenda `verificar_estornos` com o alvo da parcela.

**Operação `acompanhar_estorno`:**
- `executar` chama `consultar_estornos(pagamento.id_externo)` e procura o `id_estorno`.
  - Em processamento: `FalhaTemporaria("em_processamento")`. A repetição segue os intervalos da E07-04, sem limite.
  - Não encontrado: `nao_encontrado(chamada)`.
- `concluir` aplica `concluido` ou `recusado` como no `estornar`.

**Operação `verificar_estornos`** (a reconsulta da infraestrutura 4.7):
- `executar` chama `consultar_pagamento` e `consultar_estornos` do pagamento.
- `concluir` trava como acima. Ele só age se a parcela ainda está em `falha_definitiva`. Um estorno é **não contabilizado** quando nenhuma parcela do sistema tem o seu `id_estorno`.
  - **Um não contabilizado `em_processamento` ou `concluido`, com valor igual ao da parcela:** a parcela o adota (`id_estorno`). Segue para `em_processamento` ou para `concluida` com a liquidação. Resolve o alerta de falha definitiva.
  - **Algum não contabilizado `em_processamento` ou `concluido` com outro valor:** a parcela continua em `falha_definitiva`, com a evidência e o código `verificacao_inconclusiva`. O alerta continua aberto, para análise do administrador.
  - **Nenhum:** a parcela passa a `elegivel_excepcional`, com a evidência (a recusa e os estornos vistos). Abre `devolucao_elegivel_excepcional` (chave `parcela:<pk>`) e resolve `devolucao_em_falha_definitiva`.

**`tentar_devolucao_de_novo(parcela, *, autor)`** (a retentativa segura do §9.2):
- **Autor:** administrador. Senão, `PermissionDenied`.
- **Situação:** só em `falha_temporaria`. Fora disso, `DevolucaoRecusada`.
- **Reconsulta:** antes, `consultar_antes_de_decidir`, como na autorização.
- **Efeito:** sob as travas, a chamada pendente da parcela passa a `proxima_em = agora`, com a **mesma chave**, e o histórico é gravado. Sem chamada pendente: `DevolucaoRecusada`.

Uma parcela em `falha_definitiva` ou `elegivel_excepcional` não volta ao provedor por esta função.

**Gancho em `apps.pagamentos.chamadas`.** `Operacao` ganha `adiada: Callable[[ChamadaAoProvedor, str], None] | None = None`. `_tentar` o chama na falha temporária, depois de gravar `tentativas`, `ultimo_erro` e `proxima_em`, na mesma transação. As operações existentes não mudam.

**Alertas novos** (`TipoDeAlerta` e gravidade, E09-03):

| Tipo | Gravidade | Resolução |
|---|---|---|
| `devolucao_com_falha` | aviso | na conclusão ou na falha definitiva |
| `devolucao_em_falha_definitiva` | aviso | na conclusão, na adoção ou ao passar a elegível |
| `devolucao_elegivel_excepcional` | aviso | na confirmação excepcional (E10-06) |

O `devolucao_concluida_tardiamente`, crítico, é da E10-05.

## Interfaces

- `autorizar_devolucao(obrigacao, *, autor) -> ParcelaDeDevolucao`
- `tentar_devolucao_de_novo(parcela, *, autor) -> ParcelaDeDevolucao`
- `pagamento_da_obrigacao(obrigacao) -> PagamentoNoProvedor`
- `situacao_da_devolucao(obrigacao) -> str`: `devida` sem parcela, ou a situação da parcela. Usada pelas telas.
- Exceção `DevolucaoRecusada`.
- As operações `estornar`, `acompanhar_estorno` e `verificar_estornos`, registradas com `registrar_operacao`.

## Decisões técnicas

- **Uma parcela por obrigação, pelo valor restante inteiro.** A obrigação já é a unidade da devolução (infraestrutura 3.1, "parcela de devolução"). Fracionar a mesma obrigação em vários estornos não aparece em nenhuma regra.
- **Falha temporária automática, sem limite de tentativas.** É o mesmo princípio da E07-04: desistir deixaria dinheiro devido sem devolução. O alerta avisa o administrador a partir da terceira tentativa, ou logo, quando falta saldo (que se resolve com aporte, §9.4).
- **Sem nova tentativa no provedor depois da falha definitiva.** Repetir com a mesma chave devolveria a mesma recusa. Uma chave nova para a mesma parcela abriria a porta a duas devoluções se a recusa fosse a do risco residual. O caminho seguinte é a excepcional (P-5).
- **Exigir cobertura antes de autorizar.** `liquidar_obrigacao` recusa liquidar além do financiado. Sem essa exigência, o provedor poderia devolver um dinheiro que o livro não consegue baixar.
- **`sem_pedido`:** a devolução vai ao pagamento do destino, sem pedido nem comprador. O pagador recebe pelo provedor. Não há aviso ao comprador (E10-07).

## Invariantes

- Cada obrigação tem no máximo uma parcela, e cada parcela no máximo um estorno no provedor (a mesma chave em todas as tentativas).
- Uma parcela `concluida` tem exatamente um movimento `devolucao:<id_estorno>` (F15) com o seu valor. A obrigação fica liquidada nesse valor.
- A soma das parcelas de um pagamento nunca passa do valor dele.
- Nenhuma parcela passa a `elegivel_excepcional` sem a recusa definitiva e a reconsulta registradas na evidência.

## Casos-limite e concorrência

- **Duas autorizações em paralelo da mesma obrigação:** uma parcela e uma chamada, pela trava e pela unicidade.
- **Falha temporária repetida com a resposta perdida depois de executar** (T-8): o provedor devolve o mesmo estorno pela chave, com uma liquidação só.
- **O provedor fica fora do ar na autorização:** a autorização fica bloqueada, sem parcela.
- **A liquidação recusa** (a cobertura foi desfeita depois da autorização): o `concluir` levanta, a transação dele se desfaz, e a chamada continua pendente para a próxima execução (E07-04). Para isso não acontecer, a designação ativa da obrigação não pode ser desfeita com uma parcela `solicitada`, `falha_temporaria` ou `em_processamento`: `desfazer_designacao` (E09-05) passa a recusar com `DevolucaoRecusada` nesse caso.
- **Conclusão e verificação em paralelo** (o estorno conclui enquanto a reconsulta roda): a trava da parcela as serializa. A segunda vê a parcela final e não faz nada.

## Dependências e decisões em aberto

Depende de E10-02, E10-03, E09-03, E09-05, E09-06, E07-04 e E07-06. Nenhuma decisão em aberto.

## Correções E10-R03, R04 e R05 (2026-10-30)

Origem: parecer sobre `9ce04ad` (`docs/specs/E10-04/review.md` e `docs/specs/E10-05/review.md`). Valem a "Regra única de travas" e o "Padrão das corridas" (E09-01, `spec.md`) e a correção E10-R08 (E10-07, `spec.md`).

### R03 — a autorização concorre com a retirada da própria cobertura

**Diagnóstico.** A autorização lê `sem_cobertura_da_obrigacao` travando a conta da obrigação, mas não a `reserva`. As designações, que entram nessa cobertura, são protegidas pela trava da `reserva` (E09-R02). `desfazer_designacao` trava a `reserva` e procura uma parcela que, na corrida, ainda não foi criada. As duas transações decidem com leituras que a outra muda, e as duas concluem: a parcela fica autorizada sobre uma obrigação com 31,25 sem cobertura. Recusar depois, na liquidação, não basta, porque o provedor já terá devolvido o dinheiro.

A especificação original também deixou de fora dois estados: `desfazer_designacao` só recusava com parcela `solicitada`, `falha_temporaria` ou `em_processamento`. Em `falha_definitiva` e `elegivel_excepcional`, um estorno do provedor ainda pode ser adotado (E10-05), e a liquidação dele precisa da cobertura.

**Regras.**

- **Autorização:** depois das travas do pagamento e da `SituacaoDoPedido` e da conferência da parcela existente, `autorizar_devolucao` trava **juntas** a conta `obrigacao_comprador(o)` e a `reserva`, com `travar_contas` (ordem crescente de `pk`). Só depois lê o liquidado, o sem cobertura e as parcelas do pagamento.
- **Confirmação excepcional (E10-06):** a leitura da cobertura também passa a ser feita com essas duas contas travadas, depois da cadeia.
- **`desfazer_designacao`** recusa com `DevolucaoRecusada("há devolução em curso para esta obrigação")` sempre que a obrigação tem parcela **não final**: `solicitada`, `falha_temporaria`, `em_processamento`, `falha_definitiva` ou `elegivel_excepcional`. A leitura continua depois da trava da `reserva`.
- **Resultado em qualquer ordem:** se a autorização trava primeiro, o desfazer espera, vê a parcela e recusa. Se o desfazer trava primeiro, a autorização espera, lê o sem cobertura de 31,25 e recusa com a mensagem de cobrir antes.

### R04 — a nova tentativa manual inverte a ordem de travas da tarefa

**Diagnóstico.** `processar_chamadas` trava a `ChamadaAoProvedor` primeiro e, dentro de `concluir` ou do gancho `adiada`, a cadeia da parcela (pagamento → `SituacaoDoPedido` → parcela). `tentar_devolucao_de_novo` faz o inverso: trava a cadeia e depois a chamada. Com a mesma parcela nas duas, o PostgreSQL detecta o impasse. A correção E07-R01 (E07-04, `spec.md`) já pedia que as operações da E10 evitassem essa inversão; a especificação desta fatia não a aplicou.

**Regra das travas das chamadas da E10.** A ordem é: **a chamada → a cadeia da parcela → as contas do livro → os alertas.**

- `tentar_devolucao_de_novo`, depois da leitura sem trava e da consulta ao provedor, abre a transação e:
  1. trava a chamada `estornar` pendente da parcela com `select_for_update()`, **sem** `skip_locked` e sem `nowait`. Se a tarefa está executando essa chamada, a nova tentativa espera a tarefa terminar. Depois da espera, a condição `situacao = 'pendente'` é conferida na versão nova da linha (PostgreSQL em `READ COMMITTED`). Sem chamada pendente: `DevolucaoRecusada("não há tentativa pendente para esta devolução")`;
  2. trava a cadeia e relê a parcela. Fora de `falha_temporaria`: `DevolucaoRecusada` com a mensagem atual;
  3. grava `proxima_em = agora`, com a mesma chave, e o histórico.
- Com a trava da chamada retida pela nova tentativa, `processar_chamadas` pula a chamada (`skip_locked`) e a executa numa execução seguinte, com a mesma chave.
- **Agendamentos feitos sob a cadeia.** `_declarar_falha_definitiva`, `_aplicar_estorno` e `_concluir_verificacao` agendam outra operação da mesma parcela enquanto seguram a cadeia. `agendar_chamada` espera a trava de uma pendente do mesmo par (E07-R01). Para cada um desses agendamentos, o implementador registra no `review.md` por que, pelos estados da parcela, não pode haver uma execução da mesma operação e do mesmo alvo segurando essa pendente; onde isso não puder ser demonstrado, o agendamento passa para antes da cadeia.

**Invariante acrescentado.** Nenhuma transação da E10 trava uma `ChamadaAoProvedor` de uma parcela depois de travar a cadeia dessa parcela.

### R05 — a reconsulta na elegível adota só o estorno concluído

**Diagnóstico.** A E10-05 estendeu `verificar_estornos` à parcela `elegivel_excepcional` "com as mesmas regras de adoção". Na `falha_definitiva`, essas regras adotam o estorno do mesmo valor nos dois estados, `concluido` e `em_processamento`. Na elegível, o código só adota o concluído. Um estorno reencontrado em processamento fica sem acompanhamento, e a tela continua mostrando a parcela como elegível. A tabela de transições desta fatia não tinha as saídas da elegível para a adoção.

**Transições (substituem a linha da elegível em "Transições permitidas"):**
- `elegivel_excepcional` → `em_processamento` ou `concluida` (estorno adotado pela reconsulta, E10-05), ou `concluida_fora_da_plataforma` (E10-06).

As regras da adoção na elegível estão na E10-05, "Correção E10-R05 e R09". A adoção na elegível não gera aviso ao comprador, porque `em_processamento` é estado intermediário; a conclusão gera o aviso "Estorno concluído" da E10-07.

## Complemento das correções: pontos do implementador (2026-10-30)

Origem: o relatório do implementador sobre as correções R01 a R10 (commit `60b2412`), antes da revisão. Vale o resumo na E10-07 (`spec.md`, "Complemento das correções"). Nenhuma regra comercial muda.

### P1 — a nova tentativa manual chamada dentro de uma transação de quem chama

**Diagnóstico.** A prova `test_retentativa_manual_versus_worker` do parecer roda a nova tentativa pela `Corrida` sem `b_atomica=False`, e por isso dentro de uma transação aberta pelo arranjo. Nessa transação, a sincronização feita pela consulta ao provedor (`consultar_antes_de_decidir`) trava o `PagamentoNoProvedor` e mantém essa trava até o fim da transação de fora. A nova tentativa chega então à trava da chamada já segurando o pagamento, e a ordem "chamada → cadeia" fica invertida de novo.

A rota não abre transação de fora (`ATOMIC_REQUESTS = False`). Nela, a trava da consulta acaba com a transação curta da sincronização, e a mesma corrida passa (E10-04 A-29).

O contrato da consulta (E07-06, infraestrutura 4.2) já diz que ela é feita **antes** da transação da decisão e **sem segurar travas**. O arranjo da prova viola esse contrato. A correção é tornar o contrato explícito e verificável, e não mudar a ordem das travas.

**Regras.**
- `tentar_devolucao_de_novo` só aceita ser chamada **fora de transação**. A conferência vem no início da função, antes da consulta ao provedor. Ela usa a mesma condição do bloco durável do Django: nenhum bloco atômico aberto além do da transação de teste. Dentro de outra transação, a função levanta `RuntimeError`, sem consultar o provedor e sem gravar nada. A forma é escolha do implementador; o caminho mais simples é abrir a transação da função com `transaction.atomic(durable=True)` e fazer a mesma conferência antes da consulta.
- A ordem das travas da correção E10-R04 não muda: consulta fora de transação, depois chamada → cadeia.
- **Alternativas descartadas:**
  - **Travar a chamada antes da consulta:** manteria uma trava do banco durante a chamada ao provedor, contra a infraestrutura 4.2. Na fase 2a, isso seria uma chamada de rede.
  - **`nowait` na trava da chamada:** troca a espera por uma recusa. Esconde a violação do contrato em vez de impedi-la, e muda o comportamento da rota sem necessidade.
- **`autorizar_devolucao` não recebe a guarda.** Ela agenda a chamada de uma parcela nova, cujo alvo nenhuma execução pode estar segurando. Por isso não há espera de trava de chamada dentro dela. Quem a chamar com `SISTEMA` nas etapas seguintes (E11, E12 e E14) segue o mesmo contrato da consulta: consulta fora da transação da decisão. Essas especificações devem dizer isso.
- **Apoio das corridas:** `Corrida.rodar` ganha `a_atomica`, simétrico ao `b_atomica`, para rodar a operação A sem a transação de fora. O E10-04 A-30, em que a nova tentativa é a operação A, passa a usar `a_atomica=False`. O A-29 já usa `b_atomica=False`. Nenhuma asserção muda.
- **A prova do parecer fica substituída** pelo E10-04 A-29: é a mesma corrida, com a nova tentativa no contexto da rota. Com a guarda, a prova como está recebe `RuntimeError` na operação B. A substituição se justifica porque o arranjo dela chama a função num contexto que o contrato proíbe, e esse contexto passa a ser recusado e testado (A-31).

### P4 — a reconsulta que falha de forma definitiva não é reagendada

**Diagnóstico.** A operação `verificar_estornos` não tem `falhou`. Uma `RecusaDoProvedor` na consulta, ou o `nao_encontrado` depois de 24 horas (`nao_encontrado`, E07), encerra a chamada como `falhou`. A parcela fica em `falha_definitiva` sem reconsulta pendente. Ela nunca chega a `elegivel_excepcional`, e a devolução fica parada sem caminho, nem pelo provedor nem fora dele.

A parcela não pode passar a elegível sem uma reconsulta que responda, porque a via excepcional exige a inviabilidade comprovada (§9.5, infraestrutura 4.7) e a decisão fica bloqueada quando a consulta falha (infraestrutura 4.2). O risco estava registrado pelo implementador desde a primeira entrega.

**Regras.**
- **A reconsulta não desiste.** Em `verificar_estornos`, `executar` traduz em `FalhaTemporaria` toda falha do provedor nas duas consultas:
  - `PagamentoNaoEncontrado`, com o código `nao_encontrado`, sem o limite de 24 horas;
  - `RecusaDoProvedor`, com o código da recusa.

  `ProvedorIndisponivel` já é temporária. A chamada continua pendente, com os intervalos de `processar_chamadas`; o último intervalo, de 60 minutos, se repete.
- **Gancho `adiada` de `verificar_estornos`:** a partir da terceira tentativa, abre `devolucao_com_falha` (chave `parcela:<pk>`) com o código `reconsulta:<codigo>` e as tentativas. O alerta é resolvido quando a reconsulta conclui, qualquer que seja o resultado (adoção, elegível ou inconclusiva), com o motivo "reconsulta concluída".
- A parcela não muda de situação por causa da falha da reconsulta. Na `elegivel_excepcional`, a confirmação continua com as próprias consultas (E10-06, passo 4), que bloqueiam se o provedor falhar.
- **Na tela (R10):** a falha definitiva com a reconsulta pendente continua com "reconsulta agendada". O detalhe mostra também o último erro e as tentativas da reconsulta.

**Invariante acrescentado.** Toda parcela em `falha_definitiva` tem uma `verificar_estornos` pendente, até sair desse estado.

## Correção E10-R11 — a reconsulta inconclusiva encerra a verificação (2026-10-30)

Origem: nova revisão sobre `74b38c0`, R11 (`docs/specs/E10-04/review.md` e `docs/specs/E10-07/review.md`, "Nova revisão independente das correções"). Vale a correção E10-R08 (E10-07, `spec.md`). Nenhuma regra comercial muda.

### Diagnóstico

Quando a reconsulta só encontra estornos sem baixa de outro valor, `_concluir_verificacao` grava `verificacao_inconclusiva` e retorna. A chamada termina `concluida`. A parcela fica em `falha_definitiva` sem `verificar_estornos` pendente, contra o invariante do P4. Basta um estorno avulso de outro valor, sem nenhuma falha de rede.

A regra da linha 150 (a parcela fica como está, com o alerta aberto para análise) e o invariante do P4 são compatíveis. A situação, o código e o alerta ficam, e a reconsulta continua. A reconsulta continuar tem motivo concreto: o próprio estorno recusado pode concluir depois no provedor (o risco residual da infraestrutura 4.7, E10-05), e só a reconsulta seguinte o adota. Também o estorno de outro valor pode ser recusado ou ganhar baixa, e então a parcela fica elegível. Não há exceção ao P4.

### Regras

- **Inconclusiva em `falha_definitiva`:** a parcela fica em `falha_definitiva`, com o código `verificacao_inconclusiva` e a evidência da reconsulta gravados, e o alerta `devolucao_em_falha_definitiva` continua aberto. A **mesma** chamada `verificar_estornos` (mesma chave) continua `pendente`:
  - `tentativas` sobe um;
  - `ultimo_erro = "verificacao_inconclusiva"`;
  - `proxima_em` segue os intervalos de `processar_chamadas` (1, 5, 15 e 60 minutos, com o último repetido).
- **O que a conclusão grava não se desfaz.** O código, a evidência e a resolução do `devolucao_com_falha` ficam gravados mesmo com a chamada reagendada. Uma `FalhaTemporaria` levantada de dentro de `concluir` não serve, porque desfaz a transação de `concluir`.
  - A forma é escolha do implementador, registrada no `review.md`.
  - Um caminho é `concluir` devolver um sinal de reagendamento com o código, que `_tentar` aplica depois de `concluir` terminar, pelo mesmo caminho da falha temporária: tentativas, último erro e próxima tentativa.
  - As outras operações não mudam de comportamento.
- **A resposta inconclusiva é uma resposta do provedor.** O `devolucao_com_falha` aberto por falhas anteriores da reconsulta (P4) é resolvido com "reconsulta concluída", como nos outros resultados. O gancho `adiada` **não** abre `devolucao_com_falha` pelo código `verificacao_inconclusiva`: o alerta em vigor é o de falha definitiva, que já pede a análise do administrador.
- **Inconclusiva em `elegivel_excepcional`** (E10-05, passo 6): sem mudança. A parcela fica elegível, e a chamada termina. O invariante do P4 é só da `falha_definitiva`, e a confirmação faz as próprias consultas e recusa diante de qualquer estorno sem baixa (E10-06, passo 4, e E10-R09).
- **Na tela (R10):** a falha definitiva inconclusiva mostra `verificacao_inconclusiva` e "reconsulta agendada"; o detalhe mostra o último erro e as tentativas da reconsulta (regra do P4).
- **A regra do P4 fica mais precisa.** Onde ela diz que o alerta é resolvido "quando a reconsulta conclui", leia-se "quando o provedor responde à reconsulta": adoção, elegível ou inconclusiva.

### Invariante

Sem mudança: toda parcela em `falha_definitiva` tem uma `verificar_estornos` pendente, até sair desse estado. Agora vale também para a inconclusiva.
