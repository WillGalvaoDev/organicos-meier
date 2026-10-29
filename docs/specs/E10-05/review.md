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

## Revisão (agente 3)

| Achado | Classificação (bloqueador, importante, melhoria) | Evidência | Requisito |
|---|---|---|---|
| | | | |

**Decisão:** pendente

## Revalidação

—
