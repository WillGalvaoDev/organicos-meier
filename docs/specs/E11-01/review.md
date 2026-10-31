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
