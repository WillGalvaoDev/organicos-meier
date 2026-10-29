# E10-06 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Andaime (`TipoDeMovimento.DEVOLUCAO_EXCEPCIONAL`, `ConfirmacaoDeDevolucaoExcepcional`, migração 0013 com a trava só-inserção, assinaturas com `NotImplementedError`) e testes A-1 a A-15 e A-17 | `E10-06: andaime` | `uv run pytest tests/tecnicos/test_devolucoes_excepcional.py` | **Red: 29 failed, 2 passed.** Passam o A-2 (a obrigação continua integral: já era verdade da E10-04) e o A-14 (o fluxo F16 ainda não era permitido, então o `MovimentoProibido` já acontecia; vira guarda de regressão da lista fechada) |
| F16 em `livro._permitido`, `_liquidar` compartilhada, `liquidar_obrigacao_fora_do_provedor`, `confirmar_devolucao_excepcional`, comprovante pelo conteúdo | `E10-06: confirmacao` | o mesmo arquivo, mais `test_financeiro_livro.py` e `test_financeiro_apuracao_e_obrigacoes.py` | 124 passed |
| A-16 (corrida), T-9, cenários 35 e 36 | `E10-06: corrida A-16...` | `test_devolucoes_concorrencia.py`, `test_t09_excepcional.py`, `test_cenarios_35_36_excepcional.py` | passam |

**Não conformidade de TDD declarada (A-16).** A confirmação confere a situação de novo **depois** da trava e só então grava o arquivo; a trava foi escrita com o código funcional, sem Red da corrida. Mutação não substitui Red. Tratamento igual ao da E10-04.

## Decisões técnicas

- **Ordem dos passos:** autor → campos (`ValueError`) → situação (sem trava) → reconsulta → trava e releitura → cobertura → gravação. O arquivo só é gravado depois da releitura, então a confirmação recusada nunca o grava; se a transação falhar depois, o `except BaseException` apaga o arquivo.
- **Cobertura:** `max(0, saldo da conta da obrigação) + restos das designações ativas ≥ valor da parcela`, a mesma conta da `liquidar_obrigacao`.
- **A-10:** a parcela é levada a `elegivel_excepcional` com a obrigação coberta por designação (a autorização exige cobertura); só então a designação é desfeita (permitido, porque `elegivel_excepcional` não está em `ABERTAS`), e a confirmação é recusada até haver nova designação.
- **A-6:** o estorno "visível em processamento" é montado com `EstornoSimulado.objects.update(visivel=True)` sobre o estorno que `recusar_mas_processar` deixou invisível.
- `liquidar_obrigacao` e `liquidar_obrigacao_fora_do_provedor` partilham `_liquidar`; `_liquidado` soma os dois tipos de saída da conta da obrigação.

## Revisão (agente 3)

| Achado | Classificação (bloqueador, importante, melhoria) | Evidência | Requisito |
|---|---|---|---|
| | | | |

**Decisão:** pendente

## Revalidação

—
