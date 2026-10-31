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
