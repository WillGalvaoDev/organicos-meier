# E10-05 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Testes A-1 a A-6, A-8 e A-9 | `E10-05: testes A-1 a A-6, A-8 e A-9` | `uv run pytest tests/tecnicos/test_financeiro_conciliacao_estornos.py` | **Red: 7 failed, 1 passed.** O A-8 (`devolucao` sem `id_estorno`) já passava: o `devolucao` era sempre divergente (regressão). O A-1 falhava pela divergência; A-2 e A-3, pela ausência de `id_estorno` nos dados do alerta; os demais, pelo `devolucao` sem par |
| Par do `devolucao`, `_sinalizar_devolucao_tardia`, `id_estorno` nos dados do alerta e na pendência, adoção na `verificar_estornos` em `elegivel_excepcional` | `E10-05: par dos estornos` | o arquivo, mais `test_financeiro_conciliacao.py` e `test_devolucoes_execucao.py` | 62 passed |
| A-7 (devolução excepcional não aparece na conciliação) | `E10-06: corrida A-16, E10-05 A-7...` | o mesmo arquivo | passa. **Não houve Red:** o critério depende da confirmação excepcional (E10-06), que só existiu depois; é prova de ausência de efeito, e o código de produção não mudou por causa dele |

## Decisões técnicas

- Os dados do alerta de divergência ganharam `id_estorno`, e a pendência de dia anterior (E10-01) o usa para remontar o movimento `devolucao`: sem isso, a pendência do A-9 não se resolveria.
- Na parcela `elegivel_excepcional`, a verificação só adota um estorno **concluído** com o valor da parcela; um estorno em processamento não é adotado (a transição para `em_processamento` não existe a partir de `elegivel_excepcional`).
- O alerta `devolucao_concluida_tardiamente` tem a chave `id_estorno` e é resolvido na adoção, junto com o alerta de elegível.
- `conciliacao.py` importa `ABERTAS` de `devolucoes.py`; o inverso não existe (sem ciclo).

## Revisão independente — agente 3 — 2026-10-30

Objeto: branch `e10-implementacao`, commit `9ce04adcdb1b6186ee5c932ef38170989e4d19cf`, comparado à especificação de `cd735c3`. Fontes: funcional v1.7, infraestrutura v1.8, `spec.md` e `acceptance.md` das sete fatias, AGENTS.md. Os registros do implementador acima foram preservados.

A suíte existente passou integralmente (**2600 passed in 270.31s**, execução independente iniciada em 2026-10-29). Isso não encerra os requisitos: os testes adicionais do revisor expõem os casos abaixo. Comandos, limitações, histórico TDD e reproduções estão no [parecer consolidado](../E10-07/review.md).

**Decisão da fatia: REPROVADO.**

| Critérios | Evidência | Resultado |
|---|---|---|
| A-1/A-2/A-5/A-6/A-8/A-9 | `test_financeiro_conciliacao_estornos.py`; identidade, dois cortes temporais e resolução posterior | Cenários existentes verdes |
| A-3 | Adoção tardia de concluído com ID ainda não associado | Verde nesse arranjo; processamento reencontrado fica abandonado, R05 |
| A-4 | Alerta de duplicidade depois da excepcional | Verde apenas com ID nulo na parcela; falha para ID já conhecido, R09 |
| A-7 | F16 sem movimento exterior nem divergência | Verde; ausência de efeito corretamente declarada como regressão, não Red novo |

### R05 — importante — estorno reencontrado em processamento não é adotado nem acompanhado

Referências: E10-05/spec.md, extensão de `verificar_estornos` “com as mesmas regras de adoção”; E10-06, passo 4/A-6; funcional §9.2; `apps/financeiro/devolucoes.py:460–497`.

Reprodução: recusa com processamento invisível, parcela elegível; o estorno torna-se visível ainda em processamento; tentar confirmar a excepcional recusa e agenda verificação. Executar a verificação. Observado: parcela continua `elegivel_excepcional`, sem acompanhamento; o teste esperava `em_processamento`. `_adotar_estorno_tardio` só considera concluídos. A decisão do implementador de não adotar o processamento não atende à extensão da especificação e deixa o estado exibido incorreto. A tabela original de transições da E10-04 precisa refletir essa extensão técnica; não há nova regra comercial a decidir. A guarda no POST continua recusando enquanto o provedor mostra o estorno, mas o acompanhamento automático se perde.

### R09 — bloqueador — risco residual com ID conhecido escapa à proteção e ao alerta crítico

Referências: infraestrutura 4.7 (proteção contra duplicidade e risco residual); funcional §9.5; E10-05/A-4 e E10-06/A-6; `apps/financeiro/devolucoes.py:448–457`, `:669–676`; `apps/financeiro/conciliacao.py:366–388`.

Um estorno inicialmente em processamento recebe ID, depois é recusado e a parcela fica elegível mantendo esse ID. O dublê de risco residual faz o mesmo estorno concluir tardiamente. Foram executadas duas ordens:

1. Conclusão antes da confirmação: `confirmar_devolucao_excepcional` **aceita**, em vez de recusar. `_nao_contabilizados` confunde “ID associado a uma parcela” com devolução já liquidada e ignora o estorno relevante da própria parcela.
2. Confirmação antes da conclusão tardia: a conciliação abre somente divergência comum; **não** abre `devolucao_concluida_tardiamente`. O filtro `id_estorno__isnull=True` exclui a parcela excepcional cujo ID já era conhecido.

O dublê muda explicitamente o estado do registro simulado para representar a conclusão posterior à recusa e usa `concluir_estorno` para produzir o débito. Não afirma que essa reversão foi validada na API real: exercita o risco residual exigido pela infraestrutura, sem presumir que ID conhecido elimina esse risco. Tratar também o estorno associado ainda não liquidado; a regra técnica de “não contabilizado” não pode enfraquecer a fonte de verdade. Preservar uma única baixa e alerta crítico quando o dinheiro já foi devolvido fora.

Histórico funcional: `3aaf01e → fe06cbe`; A-7 acrescentado em `deccdce`, sem Red, como registrado.

## Correção E10-R05 e R09 — agente 2 — 2026-10-30

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Testes A-10 a A-16 | `44727d1` | `uv run pytest tests/tecnicos/test_financeiro_conciliacao_estornos.py` | **Red: 6 failed, 10 passed.** A-10, A-11, A-14: a parcela continua `elegivel_excepcional`/`falha_definitiva`; A-12: `DID NOT RAISE`; A-13 e A-15: nenhum alerta crítico. A-16 passa (regressão da definição) |
| `_estornos_sem_baixa`, `_escolher_o_estorno`, `_adotar_estorno` (mesmas regras em falha definitiva e elegível), transição `elegivel → em_processamento`, conciliação com parcela do mesmo ID | `1d3b9da` | o arquivo e `test_devolucoes_execucao.py`, `test_devolucoes_excepcional.py`, `test_devolucoes_telas.py`, `test_financeiro_conciliacao.py` | 120 passed |

O dublê da conclusão tardia (`update(situacao="em_processamento")` + `concluir_estorno`) exercita o risco residual da infraestrutura 4.7; não afirma que a API real reverte uma recusa (L-7).


## Nova revisão independente das correções — agente 3 — 2026-10-30

Base auditada: `74b38c0`, branch `e10-implementacao`. Os registros anteriores foram preservados integralmente. Este parecer prevalece sobre o anterior apenas quanto à revalidação descrita abaixo. Resultado consolidado e reproduções: [E10-07/review.md](../E10-07/review.md), seção com esta mesma data e título.

**APROVADO no escopo revalidado. R05 e R09 encerrados.** A adoção de estorno em processamento após elegibilidade agora agenda acompanhamento. Um identificador já conhecido em parcela recusada não equivale a baixa contabilizada: a conclusão tardia impede confirmação excepcional ou gera alerta de possível duplicidade quando ela já ocorreu. As reproduções anteriores correspondentes passaram; A-10 a A-16 integram a suíte reexecutada. A aprovação desta fatia não encerra a etapa, devido a R02 e R11.


## Revalidação final de R02 residual e R11 — agente 3 — 2026-10-30

Base auditada: `4b51242`, branch `e10-implementacao`. Revisão incremental sobre o parecer `74bfa95`, com reexecução da suíte completa e das provas independentes preservadas. Histórico anterior e registros do implementador mantidos integralmente.

**APROVADO.** Mantido o encerramento de R05/R09. As provas independentes de adoção após elegibilidade, conclusão tardia de identificador conhecido e alerta tardio passaram novamente. A-38/A-39 da E10-04 também exercitam a continuidade da reconsulta até adoção ou elegibilidade. Nenhum novo achado nesta rodada.
