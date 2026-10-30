# E10-07 — Avisos de estorno, telas do administrador e do comprador

Fatia 7 de 7 da milestone **E10 — Devoluções**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E10-01.

## Contexto e objetivo

As fatias E10-02 a E10-06 entregam o cálculo, a execução e a confirmação excepcional como serviços. Esta fatia os torna visíveis e operáveis:
- **O administrador** vê as devoluções por estado, autoriza, pede nova tentativa e confirma a devolução excepcional com o comprovante.
- **O comprador** vê os estornos dos seus pedidos, com o valor, o motivo e o estado real do processamento.
- **O aviso `estorno`** (E04) é emitido nos momentos em que o estado real muda para o comprador.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9.2 | O administrador autoriza estornos no dashboard. Exibir solicitados, pendentes, concluídos e falhos, com retentativa segura. Autorização não é dinheiro devolvido. |
| Especificação §9.5 | Confirmação administrativa com registro da transferência, comprovante e baixa da obrigação. |
| Especificação §12 | Evento "Estorno": valor, motivo (inclusive pagamento aprovado depois de `T0 + 48h` ou em duplicidade) e estado real do processamento, inclusive quando for devolução excepcional. |
| Especificação §13 | Comprador: histórico de pedidos, pagamentos e estornos. Administrador: autorização e acompanhamento de estornos; devolução excepcional com as parcelas elegíveis e a confirmação. |
| Infraestrutura 4.2 e 4.7 | Ações financeiras com nova autenticação. |
| Herdado da E04 | Emitir com `emitir_evento`, dentro da transação do fato, com a chave derivada do fato, e redigir título, corpo e link do aviso `estorno`. |
| Herdado da E08 | O aviso `estorno` ao comprador é emitido pela E10. |
| Cenários §16 | 35 e 36, pelo fluxo da tela |

## Escopo

**Dentro:**
- As rotas e telas do administrador em `/financeiro/devolucoes/`.
- A seção de estornos no detalhe do pedido do comprador.
- A emissão do aviso `estorno`.
- O download do comprovante.

**Fora:**
- O painel geral de alertas (E15).
- As telas de ocorrência, de caixa e de cancelamento, que criam reembolsos (E11, E12 e E14).

## Regras

**Telas do administrador** (só o administrador, `somente_administrador`; as ações com `exige_reautenticacao_por_passkey`):

| Rota | Método | Conteúdo ou efeito |
|---|---|---|
| `financeiro/devolucoes/` | GET | lista paginada das obrigações com comprador, nos grupos **pendentes de autorização** (devida), **solicitadas**, **em processamento**, **falhas** (`falha_temporaria`, `falha_definitiva`), **elegíveis para devolução excepcional** e **concluídas** (pela plataforma ou fora dela). Cada linha mostra o valor, o motivo, o pedido e o comprador (ou "pagamento sem pedido"), o pagamento, a situação e, nas falhas, o código, as tentativas e a próxima tentativa. O texto "Autorização não é dinheiro devolvido" aparece no topo |
| `financeiro/devolucoes/<obrigacao>/` | GET | o detalhe: a obrigação com componentes, o financiado e o sem cobertura, a parcela, o histórico, a evidência da falha definitiva e a confirmação excepcional |
| `financeiro/devolucoes/<obrigacao>/autorizar/` | POST, reautenticado | `autorizar_devolucao(obrigacao, autor=ADM)`. Recusa: a mensagem do serviço e o status 409; provedor fora do ar: "Não foi possível consultar o provedor; tente de novo", com o status 503. Sucesso: redireciona ao detalhe, com a mensagem "Devolução solicitada ao provedor" |
| `financeiro/devolucoes/<obrigacao>/tentar-de-novo/` | POST, reautenticado | `tentar_devolucao_de_novo`, com o mesmo tratamento de erro |
| `financeiro/devolucoes/<obrigacao>/excepcional/` | GET e POST, reautenticado | o formulário de confirmação, com meio, identificação, justificativa e comprovante (`multipart/form-data`), e `confirmar_devolucao_excepcional`. Só aparece para parcela `elegivel_excepcional`; para outra situação, o GET responde 409 com a mensagem da E10-06 |
| `financeiro/devolucoes/<obrigacao>/comprovante/` | GET | o arquivo do comprovante, com `Content-Disposition: attachment` e o tipo gravado. Só para o administrador; para qualquer outro perfil, 403 (ou o redirecionamento ao login, para quem não está autenticado) |

- **Botões por situação:** "Autorizar devolução" só na devida, "Tentar de novo" só em `falha_temporaria` e "Confirmar devolução feita fora da plataforma" só em `elegivel_excepcional`. O servidor recusa a ação mesmo que o botão seja forjado.
- O link "Devoluções" entra no menu financeiro do administrador (E09-08).

**Seção "Estornos" no detalhe do pedido do comprador** (`pedidos/<pk>/`, só o dono, como já é a rota):
- uma linha por obrigação do pedido, inclusive as dos pagamentos que não quitaram, com o valor, o motivo em texto e o estado real;
- os estados mostrados ao comprador:

| Situação interna | Texto ao comprador |
|---|---|
| devida | "Estorno registrado, aguardando processamento" |
| `solicitada` ou `falha_temporaria` | "Estorno solicitado à plataforma de pagamento" |
| `em_processamento` | "Estorno em processamento na plataforma de pagamento" |
| `falha_definitiva` ou `elegivel_excepcional` | "A plataforma não conseguiu devolver; o administrador fará a devolução diretamente" |
| `concluida` | "Estorno concluído pela plataforma de pagamento" |
| `concluida_fora_da_plataforma` | "Devolução feita pelo administrador por Pix ou transferência" |

- O comprador não vê códigos de falha, evidências, comprovante, identificação da transferência nem dados de outros compradores.

**Textos dos motivos:**

| Motivo | Texto |
|---|---|
| `minimo_nao_atingido` | Mínimo não atingido |
| `caixa_invalidada` | Caixa incompleta |
| `ocorrencia_de_entrega` | Ocorrência na entrega |
| `cancelamento_da_rodada` | Cancelamento da rodada |
| `aprovado_apos_a_margem` | Pagamento aprovado depois do prazo |
| `duplicidade` | Pagamento em duplicidade |
| `iniciado_fora_do_prazo` | Pagamento iniciado fora do prazo |
| `pedido_cancelado` | Pedido cancelado |
| `valor_divergente` | Valor diferente do pedido |

**Aviso `estorno`**, emitido ao comprador da obrigação com `emitir_evento(Evento.ESTORNO, comprador, ...)`, dentro da transação que muda a situação, com a chave `estorno:<parcela.pk>:<situacao>:<conta.pk>`:

| Momento | Situação nova | Título | Corpo (sempre com o valor e o motivo) |
|---|---|---|---|
| autorização | `solicitada` | "Estorno solicitado" | "Solicitamos à plataforma de pagamento a devolução de R$ X (motivo)." |
| conclusão pelo provedor | `concluida` | "Estorno concluído" | "A plataforma de pagamento concluiu a devolução de R$ X (motivo)." |
| elegível | `elegivel_excepcional` | "Estorno em andamento" | "A plataforma de pagamento não conseguiu devolver R$ X (motivo). O administrador fará a devolução diretamente por Pix ou transferência." |
| confirmação excepcional | `concluida_fora_da_plataforma` | "Devolução realizada" | "O administrador devolveu R$ X (motivo) por <Pix/transferência>." |

- O link de todos os avisos é o detalhe do pedido.
- `falha_temporaria`, `em_processamento` e `falha_definitiva` não geram aviso, porque são estados intermediários. O comprador os vê na tela.
- Obrigação sem comprador (`sem_pedido`) não gera aviso.
- O aviso não leva código de falha, identificação da transferência nem dado bancário.

## Decisões técnicas

- **Os avisos ficam nos serviços das fatias E10-04 e E10-06.** A emissão é acrescentada dentro deles, na mesma transação do fato, e não em receptores à parte. Assim, uma transação desfeita não deixa aviso. A chave de idempotência evita a duplicação nas repetições.
- **A falha temporária não avisa o comprador.** Ela é resolvida pela própria plataforma e não muda o que ele precisa fazer. O administrador a vê no alerta (E10-04).

## Invariantes

- Cada mudança de situação com aviso gera no máximo um aviso por comprador.
- Nenhuma rota de devolução aceita perfil que não seja administrador. As ações exigem passkey recente.
- O comprador só vê obrigações dos próprios pedidos.

## Casos-limite

- **Autorização com o provedor fora do ar:** a tela mostra o erro, e nada muda (E10-04 A-4).
- **Duplo envio do formulário de autorização:** uma parcela e um aviso.
- **Comprovante inválido:** o formulário volta com a mensagem e o status 400, sem gravar.
- **Formulário excepcional aberto e a parcela concluída pelo provedor antes do envio:** o POST recusa com 409 ("já devolvida pela plataforma").

## Dependências e decisões em aberto

Depende de E10-02 a E10-06, E04 (avisos), E09-08 (menu e padrões das telas financeiras) e E08 (detalhe do pedido). Nenhuma decisão em aberto.

## Correções da revisão da E10 (2026-10-30)

O parecer consolidado do agente 3 sobre `9ce04ad` está neste diretório, em `review.md`, e reprovou a E10. A E10-01 foi aprovada e não se reabre. As correções estão nas fatias afetadas:

| Achado | Classificação | Onde está a especificação | Critérios novos ou alterados |
|---|---|---|---|
| R01 — a integral aceita a chave de um parcial | importante | E10-02, "Correção E10-R01" | E10-02 A-16 (reescrito), A-18 a A-20 |
| R02 — estornos de pagamentos diferentes gastam o mesmo saldo | importante | E10-03, "Correção E10-R02" | E10-03 A-21 e A-22 |
| R03 — a autorização concorre com a retirada da cobertura | bloqueador | E10-04, "Correções E10-R03, R04 e R05" | E10-04 A-26 a A-28 |
| R04 — impasse entre a nova tentativa manual e a tarefa | bloqueador | E10-04, mesma seção | E10-04 A-29 e A-30 |
| R05 — o estorno reencontrado em processamento não é adotado | importante | E10-04 (transições) e E10-05, "Correção E10-R05 e R09" | E10-05 A-10 e A-11; E10-07 A-23 |
| R06 — a falha da consulta de estornos escapa do 503 | importante | E10-06, "Correções E10-R06 e R07" | E10-06 A-18; E10-07 A-22 |
| R07 — o comprovante órfão depois do rollback de quem chama | importante | E10-06, mesma seção | E10-06 A-19 a A-21 |
| R08 — evidência de TDD | não conformidade de processo; **tratamento decidido pelo responsável em 2026-10-30: o mesmo da E05-R04, E06-R05, E08-R06 e E09-R08** | esta fatia, "Correção E10-R08" (vale para toda a E10) | sem critério novo para os antigos; registro e mutação por critério |
| R09 — o estorno com ID conhecido escapa da proteção e do alerta crítico | bloqueador | E10-05, "Correção E10-R05 e R09" | E10-05 A-12 a A-16 |
| R10 — a lista omite as tentativas da falha definitiva | importante | esta fatia, "Correção E10-R10" | E10-07 A-21 |

Nenhuma correção muda regra de negócio nem decisão aprovada. As fontes continuam a especificação funcional v1.7 e a infraestrutura v1.8.

### Ordem e regras comuns

**Ordem sugerida:**
1. R04 e R03, porque mudam a ordem das travas de que as outras dependem.
2. R09 e depois R05, que usam a mesma definição de **estorno sem baixa**.
3. R06 e R07.
4. R01, R02 e R10, independentes entre si.
5. O registro da R08.

**Corridas.** Todos os critérios de concorrência novos seguem o "Padrão das corridas" da E09 (E09-01, `spec.md`), com `tests/apoio/corrida.py`:
- os serviços reais em transações PostgreSQL;
- a pausa só num ponto, sem retirar trava, validação ou efeito;
- a liberação da pausa quando a outra operação termina, espera trava ou chega ao seu ponto;
- o Red indicado no critério; tempo esgotado ou erro de infraestrutura não vale como Red.

**Provas do parecer.** Das dez provas reproduzidas no parecer:
- `test_saldo_compartilhado_em_estornos_concorrentes` fica substituída pelo E10-03 A-21. A barreira de duas threads dela esgota o tempo depois da correção.
- As outras nove têm de passar como estão. Cada critério novo indica a prova que ele estende.

**Verificação final.** Ao final, o implementador roda:
- a suíte completa, sem `--deselect`;
- `uv run ruff check --no-cache .`, `uv run ruff format --check .` e `uv run mypy .`;
- `uv run python manage.py makemigrations --check --dry-run`; o R01 acrescenta uma migração;
- as nove provas do parecer, num arquivo temporário que não entra no commit.

Os resultados vão para o `review.md` de cada fatia corrigida.

### Correção E10-R10 — tentativas da falha definitiva na lista

**Diagnóstico.** A lista só procura a chamada **pendente** da parcela, e só nas situações `solicitada`, `falha_temporaria` e `em_processamento`. Na falha definitiva, a chamada `estornar` ou `acompanhar_estorno` já está encerrada (`falhou`), e a linha não mostra as tentativas. A especificação pedia "nas falhas, o código, as tentativas e a próxima tentativa", sem dizer de onde vêm as tentativas de uma chamada encerrada.

**Regras.** Nas linhas do grupo **falhas** (e no detalhe):
- **o código:** `codigo_da_falha` da parcela;
- **as tentativas:** o texto `tentativas N`, em que N é a soma de `tentativas` das chamadas `estornar` e `acompanhar_estorno` da parcela (`alvo = parcela:<pk>`), em qualquer situação;
- **o que vem depois:**
  - em `falha_temporaria`: `próxima <dd/mm/aaaa hh:mm>`, da chamada pendente;
  - em `falha_definitiva` com `verificar_estornos` pendente: `reconsulta agendada`;
  - sem chamada pendente da parcela: `sem nova tentativa agendada`.

A tela só lê; nada muda nos serviços.

### Efeitos das outras correções nesta fatia

- **R04:** a rota `tentar-de-novo/` pode esperar a execução em andamento da mesma chamada. Se a tarefa concluiu nesse meio-tempo, o serviço recusa, e a rota responde 409 com a mensagem, como no A-8.
- **R05:** a parcela adotada em processamento aparece no grupo **em processamento**, e o comprador vê "Estorno em processamento na plataforma de pagamento". Não há aviso novo.
- **R06:** a falha de qualquer das duas consultas da confirmação chega à rota como `ConsultaAoProvedorFalhou`, e a resposta é 503.

### Correção E10-R08 — evidência de TDD (2026-10-30)

Origem: parecer sobre `9ce04ad`, R08. Esta seção vale para toda a E10. As outras fatias só remetem a ela.

#### Diagnóstico

Estes critérios não têm Red válido comprovado antes do código de produção:

| Critério | O que o registro mostra |
|---|---|
| E10-03 A-17 | as validações de `NovoEstorno.__post_init__` entraram no commit de andaime (`ceb68d7`); os cinco casos já estavam verdes |
| E10-03 A-18 | o Red registrado foi a ausência da operação, e não uma corrida contra a operação funcional sem a trava |
| E10-04 A-23 e A-24 | os testes entraram depois da proteção, como declarado; a mutação não mostrou que o A-23 falha sem a trava |
| E10-06 A-16 | o teste entrou depois da trava, como declarado |

Os já verdes declarados como regressão (E10-01 A-7, E10-05 A-7 e A-8, E10-06 A-2 e A-14, E10-07 A-14) foram aceitos pelo revisor e não entram na lista.

#### Tratamento — decisão do responsável pelo projeto (2026-10-30)

É o mesmo tratamento das correções E05-R04, E06-R05, E08-R06 e E09-R08 (E09-01, `spec.md`, seção "Correção E09-R08"), escolhido de novo para a E10. Ele não vira dispensa automática para as próximas etapas.

1. **Procurar a evidência que existe.** Valem commits locais, logs guardados com data e saídas registradas no momento. Se o implementador encontrar a evidência, registra a referência exata, e o critério sai da lista. Não vale execução nova, andaime recriado ou inferência sobre a ordem.
2. **Registrar a não conformidade** numa seção "Não conformidade de TDD" no `review.md` de cada fatia afetada (E10-03, E10-04 e E10-06). A seção traz:
   - os critérios;
   - o que aconteceu;
   - o tratamento aplicado.

   O registro anterior é preservado sem edição, e nenhum texto pode dar a entender que houve Red nesses critérios.
3. **Provar a sensibilidade por mutação**, com o título "sensibilidade (mutação), não Red". Cada mutação registra o trecho mudado, o comando com os arquivos de teste inteiros e sem `-k`, a falha por asserção (não por tempo esgotado) e a restauração verde.

   | Critério | Mutação |
   |---|---|
   | E10-03 A-17 | uma mutação por regra de `NovoEstorno`: aceitar valor zero ou negativo; aceitar mais de duas casas decimais; aceitar chave vazia; aceitar chave com mais de 64 caracteres. Cada uma tem de fazer falhar o caso correspondente |
   | E10-03 A-18 | `estornar` sem a trava da cobrança |
   | E10-04 A-23 | `autorizar_devolucao` sem as travas do pagamento e da `SituacaoDoPedido` |
   | E10-04 A-24 | `_concluir_verificacao` e `_aplicar_estorno` sem a trava da cadeia (só a releitura) |
   | E10-06 A-16 | `confirmar_devolucao_excepcional` sem a trava da cadeia (só a releitura) |

   Se o teste existente não falhar com a mutação, ele é reforçado com o "Padrão das corridas": a primeira operação pausa logo depois da leitura que a trava protege. O reforço é mostrado falhando com a mutação e passando sem ela, e entra no mesmo registro de sensibilidade. A falta de sensibilidade não fica só registrada como limite.
4. **Correções com Red real.** Todos os critérios novos desta correção seguem Red → Green → Refactor, cada um com a falha esperada indicada.
   - Os de concorrência registram as duas linhas da prevenção do E08-R06: o verde funcional, que já existe, e o Red da corrida, observado no código atual.
   - Os declarados como regressão (E10-02 A-20, E10-03 A-22, E10-05 A-16, E10-06 A-20 e A-21) registram a execução verde antes da correção e depois dela, com a justificativa.

Os passos 2 e 3 são o tratamento definitivo dos critérios antigos. Mesmo com esse tratamento, R01 a R07, R09 e R10 só se encerram pelos critérios novos.

#### Prevenção (soma-se às anteriores)

- **Validação observável não é andaime.** Recusa de entrada, mensagem ou exceção que um teste pode observar é comportamento, mesmo quando fica na interface ou num `dataclass`. Ela só entra depois do Red.
- **A trava vem depois do Red da corrida.** Para cada proteção de concorrência, o registro mostra três passos: o verde funcional sem a trava, o Red da corrida e só então a trava.

## Complemento das correções: pontos do implementador (2026-10-30)

Origem: o relatório do implementador sobre as correções R01 a R10 (`60b2412`), com quatro pontos para decisão ou atenção antes da revisão. Os quatro se resolvem com regras técnicas derivadas. Nenhuma regra comercial muda, e não há decisão nova do responsável.

| Ponto | Decisão | Onde está a especificação | Critérios |
|---|---|---|---|
| P1 — a prova `test_retentativa_manual_versus_worker` falha quando a nova tentativa roda dentro de uma transação do arranjo | O arranjo da prova viola o contrato da consulta (fora de transação, sem travas). A nova tentativa passa a recusar ser chamada dentro de outra transação. Sem trava antes da consulta e sem `nowait`. A prova fica substituída pelo A-29 | E10-04, "Complemento das correções", P1 | E10-04 A-31 e A-32; A-30 com `a_atomica=False` |
| P2 — o Red tardio dos critérios E10-07 A-22 e A-23 | Não conformidade de TDD tratada pela correção E10-R08 (decisão do responsável de 2026-10-30), com uma causa da especificação. Detalhe abaixo | esta seção | nenhum novo |
| P3 — o arranjo do E10-06 A-10 trocado por uma parcela elegível de fábrica | Aceito. O estado não é alcançável pelos fluxos depois da R03, e a conferência é uma guarda defensiva | E10-06, `acceptance.md`, "Complemento das correções" | E10-06 A-10 (arranjo novo) |
| P4 — a reconsulta que falha de forma definitiva não é reagendada | A reconsulta não desiste: as falhas do provedor nela são temporárias. Alerta a partir da terceira tentativa | E10-04, "Complemento das correções", P4 | E10-04 A-33 a A-35 |

Com isso, das dez provas do parecer:
- duas ficam substituídas: a do saldo compartilhado pelo E10-03 A-21, e a da nova tentativa contra a tarefa pelo E10-04 A-29;
- as outras oito têm de passar como estão.

### P2 — Red tardio do E10-07 A-22 e A-23

**Diagnóstico.** Os testes do A-22 (R06 pela rota) e do A-23 (R05 pela tela) foram escritos no commit `085ccd8`, depois das correções de serviço que os fazem passar (`ee375bd` e a do R05). O Red foi conferido executando os testes contra o código de produção anterior (`44727d1`).

Parte da causa é da especificação. A ordem sugerida punha R05 e R06 antes, e os critérios de tela desses achados ficaram na E10-07, separados dos critérios de serviço. Seguir a ordem levava a escrever o teste de tela depois da correção do serviço.

**Tratamento** (o da correção E10-R08, sem decisão nova):
1. Registrar no `review.md` da E10-07, na seção "Não conformidade de TDD":
   - os dois critérios;
   - a sequência real dos commits;
   - o tratamento aplicado.
2. A execução contra `44727d1` é registrada com o título "sensibilidade (execução contra o código anterior), não Red". O registro traz:
   - o comando com o arquivo de teste inteiro, sem `-k`;
   - o commit de produção usado;
   - a falha por asserção ou exceção esperada (`ProvedorIndisponivel` no A-22; `'elegivel_excepcional' == 'em_processamento'` no A-23);
   - a execução verde no código atual.

   O registro já feito em `review.md` é preservado e completado; ele não pode dar a entender que houve Red antes do código.
3. Nenhum código de produção é revertido para refazer o ciclo.

**Prevenção (especificador).** Quando um achado tiver critérios de serviço e de tela, a ordem sugerida põe os dois juntos, e o teste de tela é escrito e visto falhar antes da correção do serviço.

### Verificação final

O implementador repete a verificação final da seção "Ordem e regras comuns". As provas do parecer passam a ser as oito indicadas acima.

## Correções da nova revisão: R02 residual e R11 (2026-10-30)

Origem: a nova revisão independente sobre `74b38c0` (`review.md`, "Nova revisão independente das correções"). Os dois achados se resolvem com regras técnicas derivadas, sem regra comercial nova e sem decisão do responsável.

| Achado | Decisão | Onde está a especificação | Critérios |
|---|---|---|---|
| R02 residual — estornos em processamento não comprometem o saldo do simulador | O estorno aceito compromete o saldo na aceitação: o disponível é o liberado menos os estornos em processamento. A conclusão não confere de novo. A conclusão e a recusa tomam a trava do saldo. `consultar_saldo` não muda | E10-03, "Correção E10-R02 residual" | E10-03 A-23 a A-27 |
| R11 — a reconsulta inconclusiva deixa a falha definitiva sem reconsulta pendente | A mesma chamada continua pendente, com os intervalos de sempre, sem desfazer o que a conclusão gravou. Sem novo alerta pela inconclusiva. A elegível inconclusiva não muda | E10-04, "Correção E10-R11" | E10-04 A-36 a A-41 |

### Ordem e regras comuns

1. **R11:** A-36 e A-40 juntos (serviço e tela), depois o restante.
2. **R02 residual:** A-23, A-25 e A-26 antes da correção; A-24 e A-27 como regressão.

Cada critério novo com Red real, antes do código de produção, registrado como na correção E10-R08. Commits separados por achado.

### Provas da nova revisão

- **`test_inconclusiva_mantem_reconsulta_pendente`:** tem de passar como está.
- **`test_saldo_nao_negativo_depois_de_processamentos`:** fica substituída pelo E10-03 A-23. Ela não espera a recusa do segundo estorno, que é o comportamento especificado, e o A-23 afirma a recusa e o saldo final de 20,00 com o mesmo arranjo.
- As oito provas anteriores continuam valendo como na seção "Complemento das correções".

### Verificação final

O implementador repete a verificação final da seção "Ordem e regras comuns" das correções R01 a R10: a suíte completa, ruff, formatação, mypy e `makemigrations --check`. Registra os resultados no `review.md` desta fatia.
