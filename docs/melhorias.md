# Melhorias não impeditivas

Registro central das melhorias apontadas nas revisões que **não impedem** a aprovação de uma entrega. Criado por decisão do responsável pelo projeto em 2026-10-20: essas melhorias ficam aqui e são revistas no fim da implantação do projeto (antes do encerramento da fase 1, E16).

## Regras de uso

- **Quem registra.** O revisor (agente 3), ao classificar um achado como melhoria, acrescenta uma linha na tabela de pendentes, além de citá-lo no `review.md`. O especificador e o implementador também podem registrar o que perceberem e não for do escopo da tarefa.
- **O que entra.** Só achados classificados como melhoria: sem bloqueador, sem impacto em regra de negócio, dinheiro, permissão, integridade ou segurança. Se um achado afetar algum desses pontos, ele não é melhoria e segue o fluxo normal de correção (AGENTS.md §4).
- **O que não fazer.** Uma melhoria registrada não é implementada por conta própria dentro de outra tarefa. Ela só entra numa entrega quando o responsável decidir, na revisão final ou antes, se pedir.
- **Como fechar.** Quando uma melhoria for tratada, a linha passa para a tabela de encerradas, com a entrega e o commit. Uma melhoria descartada também passa para lá, com o motivo.

## Pendentes

| ID | Origem | Onde | Descrição | Sugestão |
|---|---|---|---|---|
| M-1 | E07-R08, revisão de `162e9e1` | `tests/apoio/concorrencia.py` (mensagem de `TempoEsgotado`) | A mensagem de `TempoEsgotado` com a limpeza concluída cita só `índice:nome` das operações pendentes. A correção E07-R06 (E01-05, item 7) pede também o alias e a fase, como já faz `LimpezaIncompleta`. A limpeza e a guarda estão corretas; falta só a informação de diagnóstico. | Usar `execucao.descrever(pendentes)` também nesse caminho e acrescentar a asserção da mensagem no teste do A-22 da E01-05, com Red e Green. |
| M-2 | E08-04 (implementador) | `tests/tecnicos/test_pagamentos_fronteiras.py::test_so_a_sincronizacao_escreve_nos_registros_de_pagamento` | O teste acusa qualquer módulo que cite `PagamentoNoProvedor` ou `ConsultaDoPagamento` e contenha uma chamada de escrita, mesmo quando a escrita é de outro modelo. Os módulos de pedidos evitam citar as classes (constante, função de leitura e `Protocol`) só para passar nessa heurística. | Verificar a escrita nos próprios modelos de pagamento (por exemplo, pela árvore de sintaxe) em vez da coocorrência de texto, e então permitir a citação da classe nos tipos e nas chaves estrangeiras. |
| M-4 | E08-R06, revisão de `584b323` | `tests/tecnicos/test_pedidos_quitacao.py` / `decidir_destino` | A corrida do A-17 cobre a deduplicação pela sincronização, mas não detecta retirar a guarda interna de destino existente. O limite e o reforço foram declarados no tratamento autorizado de R06; controle independente de chamada direta repetida passa no código atual, sem defeito funcional demonstrado. | Na revisão das melhorias, acrescentar teste direto sob transação e trava do pagamento que chame a decisão duas vezes, exija o mesmo destino e confira a ausência de novos registros/avisos. Preservar o teste concorrente existente; não tratar mutação como Red histórico. |
| M-9 | E09-08 (implementador); registrada como M-5 nos pareceres da E09-08 | `apps/financeiro/views.py` (resumo) e `apps/financeiro/reserva.py` (`itens_sem_cobertura`) | O resumo e a lista de itens sem cobertura percorrem todas as contas, obrigações e despesas, calculando saldo e financiado conta a conta (várias consultas por obrigação). Com o tempo a tela e o `avaliar_reserva`, que roda no fim de cada operação, ficam lentos. | Agregar os saldos numa consulta só por destinação, paginar as obrigações do resumo e medir o tempo antes de otimizar. |
| M-7 | E09-04 (implementador) | `tests/tecnicos/test_financeiro_concorrencia.py` (A-12 da E09-04) | Retirar a trava do pagamento da sincronização não faz o teste do aviso concorrente com a reconsulta falhar, porque a trava da situação do pedido e a chave idempotente do movimento também contêm a corrida. | Um teste da trava do pagamento isolada, em E07-03, se a trava merecer prova própria. |
| M-11 | E13-08, revisão independente de `9af6251` | `tests/tecnicos/test_pedido_formal_ponta_a_ponta.py`, A-6/A-7 | O A-7 entregue aprova com `em=T0+47h` após cancelar em `T0+93h`: cobre descoberta atrasada de aprovação anterior. A prova independente com aprovação em `T0+94h`, valores exatos devidos no cancelamento e cobertura da devolução passou (código em E13-08/review.md). Sem defeito funcional demonstrado. | Incorporar ao conjunto permanente as asserções complementares de A-6/A-7 preservadas no parecer, incluindo aprovação realmente posterior ao cancelamento. |
| M-12 | E15-07 (implementador), ajuste do especificador | `apps/simulador_pagamentos/` (`controle.py`, `plano.py`) | O simulador não reproduz duas situações do provedor: a recusa definitiva de `cancelar_cobranca` e a consulta de pagamento com valor divergente. Os critérios E15-04 A-4/A-7 e E15-07 A-10 gravam esses estados direto no banco. A E15-07 A-8 usa a falha de consulta de pagamento desconhecido, que o simulador reproduz. Sem defeito funcional: a verificação dos alertas está coberta. | Acrescentar ao simulador controles como `recusar_cancelamento(id_externo, codigo)` e `divergir_consulta(id_externo, campo, valor)`, com testes próprios. Depois, trocar a gravação direta desses critérios pelo simulador. Validar antes, na homologação (E16), se o provedor real produz esses casos. |
| M-15 | E16-07, R05 (decisão do responsável de 2026-11-20, segunda opção da regra 2-I; registro do especificador) | `tests/rastreabilidade/auditoria.py` e `matriz.py` | A releitura semântica de todas as ligações da matriz com as perguntas (a) a (k) da regra 2-J não foi feita (R05-J1). A sétima amostra não demonstrou defeito de produção. A correção da regra 2-K trata os resíduos apontados e põe a existência e o alcance do `caminho` sob conferência automática, mas não relê as linhas que não alterou. Achados novos em linhas não alteradas, sem defeito de produção, entram aqui. | Na revisão final das melhorias, decidir se as linhas não alteradas pela regra 2-K são relidas com (a) a (k) antes da fase 2a, priorizando as afirmações financeiras e de concorrência. |
| M-14 | E16-03 (implementador) | `config/observabilidade.py` (`opcoes_do_sentry`) | O `sentry-sdk` 2.75 avisa que `send_default_pii` está obsoleto em favor de `data_collection`. A spec fixa `send_default_pii = False`, e o teste A-2 lê essa opção. | Migrar para `data_collection` quando o SDK removê-lo, com a spec ajustada. |

### Decisão do responsável na revisão das melhorias — 2026-11-18 (E16-08, regra 10)

O especificador apresentou cada pendente com uma recomendação. O responsável aceitou todas em 2026-11-18:

| ID | Decisão | Motivo da recomendação |
|---|---|---|
| M-3 | **Tratar antes do encerramento**, na fatia E16-10 (só documentação) | Critério aprovado com redação que contradiz regras superiores; o relatório final cita os critérios |
| M-8 | **Tratar antes do encerramento**, na fatia E16-10 (só documentação) | Mesmo motivo da M-3 |
| M-1 | Fase 2a | Só diagnóstico de teste; não afeta o comportamento |
| M-2 | Fase 2a | Heurística de teste; sem defeito |
| M-4 | Fase 2a, antes do Pix real | Reforço de prova de uma guarda financeira; sem defeito demonstrado |
| M-7 | Fase 2a, antes do Pix real | Reforço de prova de trava; sem defeito demonstrado |
| M-9 | Fase 2a | Desempenho: medir antes de otimizar, com volume real |
| M-11 | Fase 2a, antes do Pix real | Asserções complementares já provadas no parecer da E13-08 |
| M-12 | Fase 2a | Depende de validar com o provedor real se esses casos ocorrem |
| M-14 | Fase 2a | Migrar quando o `sentry-sdk` remover `send_default_pii` |
| M-5 | **Descartada** (ver "Encerradas") | O revisor já considerou a trava da rodada uma defesa redundante, sem defeito |

As adiadas continuam na tabela de pendentes, com a fase indicada aqui.

## Encerradas

Melhorias apontadas antes da criação deste registro e já tratadas, para rastreabilidade.

| ID | Origem | Descrição | Tratamento |
|---|---|---|---|
| E03-R02 | revisão da E03 (`0ceb171`) | Pré-condição do A-3 da E03-06 não isolava o código `multiplo`. | Critério e spec ajustados pelo especificador (2026-10-16). |
| E04-R03 | revisão da E04 (`0b52010`) | Cenário 24 citava WhatsApp em `pagamento_confirmado`, que não tem esse canal. | Spec, critério e teste alinhados a `pagamento_aberto` (correção E04-R03). |
| E06-R03 | revisão da E06 (`2fbf143`) | Campo `novo` da auditoria de prorrogação fora de UTC. | Corrigido na correção da E06 (E06-04 A-12). |
| E07-R04 | revisão da E07 (`d6e4d20`) | Respostas imediatas do simulador sem normalização UTC. | Corrigido na correção da E07 (E07-01 A-21). |
| E07-R07 | revisão da E07 (`636a94c`) | Red da R03 registrado com `-k`. | Divergência reconhecida no registro; comandos com arquivos inteiros desde então. |
| M-6 | E09-06 (implementador) | O A-19 não detectava a retirada da trava das contas da apuração. | Encerrada na correção E09-R08 (2026-10-22): a trava da apuração é provada pelo E09-06 A-24 (ii); retirá-la o faz falhar (registro em `docs/specs/E09-06/review.md`). Não existe Red real possível para o A-19. |
| M-10 | E13 (implementador) | O teste `test_devolucoes_reembolso.py::test_o_reembolso_gera_a_obrigacao_financiada_pela_custodia` não congelava o relógio e falhava desde 03/11/2026 (prazo de pagamento de `T0` vencido pelo relógio real). | Encerrada no PR #86 da E13 (2026-11-13), por decisão do responsável pelo projeto, porque bloqueava o CI da `main`: o teste congela o relógio em `T0 + 1h`, sem mudar as asserções (correção já provada pelo revisor no parecer da E13-08). |
| M-5 | E08-R06, registro do implementador (E08-02) e revisão de `584b323` | Na corrida do A-20 (E08-02), retirar só a trava da rodada não é detectado, porque a trava do fornecedor já serializa as aberturas. | **Descartada** por decisão do responsável de 2026-11-18 (E16-08, regra 10): o revisor considerou a trava da rodada uma defesa redundante nesse cenário, sem defeito funcional. Registro original na revisão da E08-02. |

### Reclassificação pelo revisor — 2026-11-17

M-13 deixa a lista de melhorias não impeditivas e passa a **bloqueador E16-R02**,
conforme [parecer da E16-03](specs/E16-03/review.md). A reprodução independente
confirmou token no envelope do Sentry. Não foi corrigido nem descartado; permanece
aberto no fluxo de correção. Registro original preservado abaixo:

| ID | Origem | Onde | Descrição | Sugestão original |
|---|---|---|---|---|
| M-13 | E16-03 (implementador) | `config/observabilidade.py` (`limpar_evento`) | A regra 3 manda manter o caminho da URL no evento do Sentry. Rotas com segredo no caminho (`/convite/<token>/`, `/entrar/link/<token>/`) mandariam o token ao Sentry quando uma delas falhar. Não é dado pessoal de comprador, mas é credencial de uso único. | Trocar o segmento do token por `[removido]` nessas rotas antes do envio (decisão do especificador). |

**Encerrada pela correção (implementador, 2026-11-17):** o achado E16-R02 foi corrigido no commit `d254321` (regras 3-A a 3-C da E16-03: troca do token nas rotas `entrar/link/<token>/`, `convite/<token>/` e `convite/<token>/google/` em todo o envelope, chaves de identificação pessoal e `transaction_style="url"`), com os testes A-14 a A-20 em `tests/tecnicos/test_observabilidade.py`. A M-13 não volta à lista de pendentes. A M-14 continua melhoria.
| M-3 | E08-R07, revisão de `2714a6a` | A-12 pede 409 para administrador em rota de comprador ativo, embora a política o recuse antes; A-21 pede ausência de aviso também quando o preço muda antes do congelamento, contrariando §5.1/E05-06. A implementação/testes respeitam as regras superiores; a inconsistência é na redação dos critérios. | Encerrada na E16-10, implementação `8e35589`, aprovada na revisão independente de 2026-11-19. Critérios corrigidos e evidências complementares conferidos; comportamento de produção preservado. |
| M-8 | E09-08, revisão de `34f9547` | O literal `1.000,00` conflita com a spec que recusa separador de milhar; teste e formulário usam/aceitam `1000,00`. Sem proposta de alterar comportamento financeiro. | Encerrada na E16-10, implementação `8e35589`, aprovada na revisão independente de 2026-11-19. Critérios corrigidos e evidências complementares conferidos; comportamento de produção preservado. |
