# E11-01 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Comandos com o arquivo de teste inteiro, sem `-k`: `uv run pytest tests/tecnicos/test_apuracao_inicio.py`.

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-21 (arranjo AP em `tests/apoio/apuracao.py`) | `e092f5b` | **Red: 20 failed, 2 errors.** `ModuleNotFoundError: No module named 'apps.pedidos.apuracao'` (a função não existia), e `ImportError` nos testes que pausam o módulo |
| `ApuracaoFinal`, `MotivoDoCancelamento.INADIMPLENCIA` e o alerta (migrações `pedidos 0007`, `0008` e `financeiro 0015`); `iniciar_apuracao` sem as regras de destino do pagamento depois da apuração e com a situação lida sem trava | commit da fatia | **6 failed, 16 passed.** Red pelos motivos da spec: A-17, A-18, A-20 e A-21, Y `pago` (o pagamento quita depois da apuração); A-16, Y `pago`; A-15 (ii), `OperationalError: deadlock detected` na gravação da situação sem trava. A-19 passou (regressão: a regra do `aprovado_apos_a_margem` da E08-04 já vinha antes) |
| `_motivo_da_devolucao`: depois da apuração do ciclo, ou com o motivo `inadimplencia`, o cancelado é `pedido_cancelado`; alerta crítico `aprovado_no_prazo_depois_da_apuracao` (`teria_quitado_pela_p6`), resolvido na liquidação; trava das `SituacaoDoPedido` | idem | A-15 (ii) ainda com `deadlock detected` (ver decisão abaixo); os outros passam |
| Travas da decisão com `FOR NO KEY UPDATE` (fornecedor, rodada, produtos, estoques e parcelas) | idem | **22 passed** |

## Decisões técnicas

- **`FOR NO KEY UPDATE` nas travas da apuração.** O impasse do A-15 (ii) vinha de um pagamento que quita (ou devolve) e insere registros que apontam para a rodada e o fornecedor (contas do livro-razão, por exemplo): no `COMMIT` dele, a conferência da chave estrangeira pede `FOR KEY SHARE` sobre a rodada, e a apuração a tinha com `FOR UPDATE` enquanto esperava a situação do pedido que o próprio pagamento segurava. `FOR NO KEY UPDATE` continua excluindo as operações de interesse (`FOR UPDATE`) e outras apurações, e não conflita com `FOR KEY SHARE`. Ordem das travas da spec mantida.
- **Mais de uma condição do cancelado.** Além de "depois da apuração", o motivo `inadimplencia` sempre vira `pedido_cancelado` (o cancelamento por falta de pagamento nunca é desfeito).
- **Guarda de transação** compartilhada: `exigir_fora_de_transacao` em `apps/pagamentos/consulta.py` (bloco durável vazio, como na E10-04 P1).
- Apuração dos testes de aviso: o aviso do simulador é entregue e a tarefa de chamadas consulta o pagamento (`_receber_o_aviso`).

## Riscos remanescentes e limites de verificação

- O comportamento do provedor real na busca por referência continua o limite L-6.


## Parecer independente — agente 3 — 2026-10-31

Base auditada: `1a36495`, branch `e11-implementacao`, comparada à base E10 integrada `1b9bf07`. Leitura dos documentos-base (funcional v1.7 e infraestrutura v1.8), spec/acceptance das oito fatias, implementação, testes e registros de TDD. O conteúdo anterior deste arquivo foi preservado integralmente. Evidências e reproduções completas no [parecer consolidado da E11-08](../E11-08/review.md).

**BLOQUEADO POR DECISÃO no ponto R03; etapa E11 REPROVADA também por defeitos independentes.** A-1 a A-21 foram confrontados com código e testes: autorização, fronteira de 48h, releitura sob trava, pedido imutável, inadimplência, reconsulta, idempotência, destino/alerta de pagamento informado depois e sua liquidação estão cobertos pela suíte. A-8 confirma o agendamento implementado, mas esse critério não basta para comprovar a ordem exigida pela fonte superior.

**R03 — bloqueador — cancelamento no provedor adiado para depois da apuração.** Infraestrutura §4.3: reconsultar, cancelar no provedor tentativas não terminais, aplicar P-6 e seguir a apuração; indisponibilidade bloqueia a apuração. E11-01/spec.md, passo 5, e A-8 mandam somente agendar. `apps/pedidos/apuracao.py:282` chama `agendar_cancelamento`; `iniciar_apuracao` prossegue e grava o resultado antes da execução externa. Prova: X pago, cobrança de Y pendente, início em T0+48h; depois da conclusão da apuração o provedor ainda devolve `pendente`. Com falha programada de `cancelar_cobranca`, a apuração também termina sem bloqueio, pois nem tenta a operação.

O código segue o detalhamento local, mas há conflito com a fonte superior. Não se trata de mandar fazer rede sob travas: a solução deve preservar também o contrato da infraestrutura §4.2. Solicitei ao responsável identificar eventual decisão aprovada que permita postergar o cancelamento. Não foi localizada tal decisão nos documentos auditados. O ponto exige alinhamento pelo especificador: cumprir a ordem existente ou formalizar uma alteração autorizada, com tratamento da corrida e da indisponibilidade. Não presumi essa autorização.

TDD: conferidos `e092f5b → bbc9e7f` e o registro dos Reds intermediários de destino/concorrência; não reexecutei versões históricas nesta rodada. A solução `FOR NO KEY UPDATE` inicial é pertinente, mas o ramo de retorno a perde depois (R04, E11-05).

## Correção E11-R03 — agente 2 — 2026-11-01

Comando: `uv run pytest tests/tecnicos/test_apuracao_inicio.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-8 (substituído) e A-22 a A-29 | `ffcefc6` | **Red: 9 failed.** A-8: a chamada só agendada e a cobrança ainda `pendente` no provedor; A-22 e A-26: `DID NOT RAISE ConsultaAoProvedorFalhou`; A-23: Y `cancelado` em vez de `pago`; A-24 e A-28: chamada inexistente ou `pendente`; A-27: `_cancelar_no_provedor` inexistente; A-29: sem `cobrancas_canceladas` na auditoria. A-25 passou (a cobrança já estava cancelada na reconsulta: regressão) |
| Passo 4-A `_cancelar_no_provedor` (agenda numa transação curta e executa com `executar_chamada_agora`, fora de transação de negócio); `executar_chamada_agora` em `apps/pagamentos/chamadas.py`; `ConsultaAoProvedorFalhou` com mensagem própria; conferência `cobranca_aberta` sob as travas; o passo 5 deixa de agendar | `e510c4f` | **30 passed** |

**Decisões técnicas.** `executar_chamada_agora` espera a trava da chamada (sem `skip_locked`) e relê a situação; uma exceção inesperada deixa a chamada pendente, o que bloqueia a apuração. A mensagem de bloqueio é "O provedor não confirmou o cancelamento da cobrança {id_externo}.". A ordem do passo 4-A é pelo pedido e pelo `id_externo`.

**Testes que mudaram por consequência da correção (sem afrouxar o que afirmam):**
- **A-16:** a cobrança de Y aprovada no simulador antes da apuração, com a reconsulta "pendente" por dublê, deixou de ser um cenário coerente: o passo 4-A cancela, o provedor responde `aprovado` e Y quita antes da decisão. O teste passou a aprovar a cobrança, já cancelada, durante a pausa da decisão (L-3), que é o cenário "pagamento depois da apuração" que o critério quer: o aviso espera a trava da situação e vira devolução com alerta.
- **A-15 (ii):** continua com o dublê só na reconsulta; a espera passa a acontecer na sincronização do cancelamento, e o resultado (Y pago, um destino `quita`) é o mesmo. **Ponto para o especificador:** a redação do A-15 (ii) e do A-16 fala de "reconsulta devolvendo pendente"; vale ajustá-la ao passo 4-A.
- **A-27:** o instantâneo de "sem escrita" é tirado depois do passo 4-A, porque o efeito no provedor fica (regra 5).

Provas do parecer `test_cancelamento_no_provedor_precede_apuracao` e `test_falha_do_cancelamento_bloqueia_apuracao`: passam como estão (arquivo temporário, removido).


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `0af24ad`, branch `e11-implementacao`; correções desde o parecer `3aa8858` sobre `1a36495`. Requisitos corrigidos em `732b7bb`, código, testes e registros Red/Green confrontados. Conteúdo anterior preservado. Evidências e prova residual no [parecer consolidado E11-08](../E11-08/review.md).

**APROVADO nesta revalidação — R03 encerrado.** O cancelamento pendente é efetivado e sincronizado antes da decisão; indisponibilidade bloqueia. Conferidos A-8 e A-22 a A-29, cobranças órfãs, aprovação concorrente, recusa seguida de consulta e guarda sob trava. As duas provas independentes de R03 passam. O adendo alinha a especificação à infraestrutura §4.3, resolvendo o conflito anterior sem nova regra de negócio. A etapa E11 permanece REPROVADA por R02 residual.
