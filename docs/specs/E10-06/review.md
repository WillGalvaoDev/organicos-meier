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

## Revisão independente — agente 3 — 2026-10-30

Objeto: branch `e10-implementacao`, commit `9ce04adcdb1b6186ee5c932ef38170989e4d19cf`, comparado à especificação de `cd735c3`. Fontes: funcional v1.7, infraestrutura v1.8, `spec.md` e `acceptance.md` das sete fatias, AGENTS.md. Os registros do implementador acima foram preservados.

A suíte existente passou integralmente (**2600 passed in 270.31s**, execução independente iniciada em 2026-10-29). Isso não encerra os requisitos: os testes adicionais do revisor expõem os casos abaixo. Comandos, limitações, histórico TDD e reproduções estão no [parecer consolidado](../E10-07/review.md).

**Decisão da fatia: REPROVADO.**

| Critérios | Evidência | Resultado |
|---|---|---|
| A-1 a A-5, A-8 a A-15 e A-17 | `test_devolucoes_excepcional.py`, T-9, cenários 35/36 | Cenários existentes verdes; rollback externo não coberto, R07 |
| A-6 | Recusa de estorno novo visível | Verde nesse arranjo; ID conhecido permite confirmação, R09; acompanhamento ausente, R05 |
| A-7 | Provedor integralmente indisponível | Verde; falha só na segunda consulta não é traduzida, R06 |
| A-16 | Duas confirmações simultâneas | Verde; histórico sem Red específico, R08 |

### R06 — importante — falha da consulta de estornos escapa do contrato de erro

Referências: E10-06/spec.md, passo 4/A-7; E10-07, tratamento HTTP 503; `apps/financeiro/devolucoes.py:613`, `:672`; `apps/financeiro/devolucoes_views.py:205–206`.

Reprodução: parcela elegível; `falhar_proximas(1, operacao="consultar_estornos")`; confirmar com campos válidos. A consulta de pagamento passa, mas a segunda consulta propaga **`ProvedorIndisponivel`** em vez de `ConsultaAoProvedorFalhou`. A rota só captura esta última, portanto esse caminho não entrega o 503/mensagem definidos. Nada deve ser confirmado quando qualquer consulta falha; normalizar os erros das duas consultas e testar o caminho HTTP também.

### R07 — importante — rollback da transação externa deixa comprovante órfão

Referências: E10-06/spec.md, passo 8 (“se a transação for desfeita, o arquivo é apagado”); AGENTS §6; `apps/financeiro/devolucoes.py:616–667`.

Reprodução: chamar a confirmação dentro de `transaction.atomic()` do chamador e lançar `RuntimeError` depois de ela retornar. A confirmação e o F16 são desfeitos, mas sobra **um PDF** em `MEDIA_ROOT/comprovantes/`. O `except BaseException` só cobre falhas enquanto a função está ativa; a transação externa ainda não foi confirmada quando ela retorna. Fazer a persistência/limpeza respeitar a transação efetiva ou recusar explicitamente uma composição transacional que não possa garantir; testar também falha interna e preservação do arquivo após commit.

R09 (detalhado na E10-05) impede a aprovação da proteção contra duplicidade. R08 cobre o histórico TDD. F16 foi conferido: transferência interna obrigação → reserva, sem débito exterior, liquidado somando F15/F16; os testes de segregação existentes passaram.

## Correções E10-R06 e R07 — agente 2 — 2026-10-30

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Testes A-18 a A-21 | `0c09af9` | `uv run pytest tests/tecnicos/test_devolucoes_excepcional.py` | **Red: 2 failed.** A-18: `ProvedorIndisponivel` escapa; A-19: `DID NOT RAISE RuntimeError`. A-20 e A-21 passam (regressão, execução verde antes e depois da correção) |
| `traduzindo_falhas` (contexto em `consulta.py`, usado pelas duas consultas); `_exigir_fora_de_transacao` (bloco durável vazio no início) e `transaction.atomic(durable=True)` na confirmação | `ee375bd` | o arquivo, `test_pagamentos_consulta.py`, `test_devolucoes_telas.py`, `test_devolucoes_concorrencia.py`, `test_cenarios_35_36_excepcional.py`, `test_t09_excepcional.py` | 78 passed |

Nenhum teste existente chamava a confirmação dentro de `atomic` próprio. A leitura de cobertura com as duas contas travadas (R03) não tem critério dedicado na spec e não tem Red possível: a retirada da designação já é recusada na elegível.

## Não conformidade de TDD (R08) — E10-06 A-16

Registro anterior preservado: sem Red da corrida (trava escrita com o código). Busca de evidência: nada em `dabe910`/`deccdce` nem nos logs. **Sensibilidade (mutação), não Red** — `uv run pytest tests/tecnicos/test_devolucoes_concorrencia.py`, com `confirmar_devolucao_excepcional` lendo a parcela sem a trava da cadeia: 1 failed, `test_duas_confirmacoes_excepcionais_da_mesma_parcela` (`'já confirmada'` não está na mensagem recebida, que passa a ser a de cobertura); restaurado. O reforço da corrida verificação × confirmação (E10-04) também cobre essa trava.

## Complemento: arranjo do A-10 (P3) — agente 2 — 2026-10-30

Registro da troca aceita pelo especificador (`65e3698`, `acceptance.md`, "Complemento das correções: arranjo do A-10"). O arranjo original criava a falta de cobertura desfazendo a designação depois da elegibilidade; com a E10-R03 (commit `5940418`), `desfazer_designacao` recusa nesse estado. O A-10 usa agora uma parcela `elegivel_excepcional` criada por fábrica (`parcela_de_fabrica(a, "elegivel_excepcional", "10.00")`), que não chama `desfazer_designacao` nem contorna recusa de serviço. Asserções iguais às de antes: confirmação recusada com a mensagem de cobrir antes; depois de `designar_reserva` de 10,00, aceita; o consumo da designação (F11) e o F16 deixam a reserva com o saldo de antes. A conferência de cobertura na confirmação é guarda defensiva.
