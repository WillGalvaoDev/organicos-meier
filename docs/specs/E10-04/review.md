# E10-04 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Andaime (`ParcelaDeDevolucao`, `HistoricoDaDevolucao`, migração 0012, três tipos de alerta, gancho `adiada` sem chamada) e testes A-1 a A-22 e A-25 | `E10-04: andaime` | `uv run pytest tests/tecnicos/test_devolucoes_execucao.py` | **Red: 25 failed** (`NotImplementedError`) |
| `devolucoes.py`, operações `estornar`, `acompanhar_estorno` e `verificar_estornos`, `adiada` em `_tentar`, recusa em `desfazer_designacao` | `E10-04: parcela de devolucao` | o mesmo arquivo | **25 passed** |
| Corridas A-23 e A-24 e T-8 | `E10-04: corridas A-23 e A-24 e T-8` | `test_devolucoes_concorrencia.py`, `test_t08_devolucao_idempotente.py` | 7 passed |

**Não conformidade de TDD declarada.** As travas (pagamento → situação do pedido → parcela) foram escritas junto com o código funcional, e não depois de um Red da corrida. A mutação que tira só `travar_pagamento` da autorização não derruba o A-23, porque a trava da `SituacaoDoPedido` e a unicidade da parcela por obrigação também serializam a autorização. Mutação não substitui Red; fica registrado como limite de verificação. O tratamento é o mesmo da E05-R04, da E06-R05 e da E08-R06.

## Desvios de arranjo nos testes (a especificação pede "depois da apuração")

- **A-7, A-21 e a variante do A-6 da E10-07:** em vez de apurar a rodada, a custódia do comprador é esvaziada antes do reembolso (`obrigacao_sem_cobertura`). O efeito é o mesmo: a obrigação nasce sem cobertura e só a designação da reserva a cobre.
- **A-11:** o saldo do simulador é reduzido com `registrar_saida(1.100,00)`, e não pela remoção do aporte.
- **A-8:** a parcela de 125,00 já concluída é uma fábrica (`ParcelaDeDevolucao` direta).
- **A-20:** a chamada `estornar` pendente é criada por fábrica, como a especificação pede.

## Decisões técnicas

- `autorizar_devolucao` lê a cobertura sob a trava da conta da obrigação, mas não trava a reserva: uma designação criada em paralelo só aumenta a cobertura, e o desfazer de designação com parcela aberta é recusado.
- `transicionar` é a única porta das mudanças de situação; a tabela cobre também `elegivel_excepcional → concluida` (E10-05).
- `verificar_estornos` que falha de forma definitiva não é reagendada: a parcela fica em `falha_definitiva` com o alerta aberto.
- `devolucao_concluida_tardiamente` (crítico) e a ampliação de `AlertaFinanceiro.tipo` para 40 caracteres entram já na migração 0012, para não haver duas migrações do mesmo campo; o uso do alerta é da E10-05.

## Revisão independente — agente 3 — 2026-10-30

Objeto: branch `e10-implementacao`, commit `9ce04adcdb1b6186ee5c932ef38170989e4d19cf`, comparado à especificação de `cd735c3`. Fontes: funcional v1.7, infraestrutura v1.8, `spec.md` e `acceptance.md` das sete fatias, AGENTS.md. Os registros do implementador acima foram preservados.

A suíte existente passou integralmente (**2600 passed in 270.31s**, execução independente iniciada em 2026-10-29). Isso não encerra os requisitos: os testes adicionais do revisor expõem os casos abaixo. Comandos, limitações, histórico TDD e reproduções estão no [parecer consolidado](../E10-07/review.md).

**Decisão da fatia: REPROVADO.**

| Critérios | Evidência | Resultado |
|---|---|---|
| A-1 a A-6, A-8 a A-17, A-19/A-20/A-22/A-25 | `test_devolucoes_execucao.py`, T-8 | Cenários existentes verdes; limites de estados conhecidos em R05/R09 |
| A-7 e A-21 | Cobertura e recusa sequencial de desfazer designação | Insuficientes em concorrência: R03 |
| A-18 | Antecipação manual com mesma chave | Funciona isoladamente; deadlock com worker, R04 |
| A-23 e A-24 | `test_devolucoes_concorrencia.py` | Verdes; não cobrem R03/R04; Red específico ausente, R08 |

### R03 — bloqueador — autorização concorre com a retirada da própria cobertura

Referências: E10-04/spec.md, autorização passo 5 e proteção de designações; A-7/A-21; funcional §§9.3/9.4; `apps/financeiro/devolucoes.py:210–224`, `apps/financeiro/reserva.py:319–344`.

Reprodução: obrigação de 31,25 coberta integralmente por designação. A autorização pausa depois de ler `sem_cobertura = 0`; outra transação desfaz a designação antes da criação da parcela; ambas concluem. Observado: parcela autorizada e obrigação com **31,25 sem cobertura**. A autorização trava a conta da obrigação, enquanto o desfazer trava a reserva e lê a parcela ainda inexistente. A observação de que novas designações só aumentam cobertura não protege a retirada concorrente. Usar uma proteção comum para revalidar cobertura e impedir seu desfazimento, respeitando a ordem global. A liquidação posterior pode recusar depois que o provedor já devolveu; isso não satisfaz a proteção preventiva exigida.

### R04 — bloqueador — retentativa manual inverte a ordem de travas do worker

Referências: E10-04/spec.md, retentativa segura, E07-R01; AGENTS §6; `apps/financeiro/devolucoes.py:255–286`; `apps/pagamentos/chamadas.py:198–223`.

Reprodução: parcela em `falha_temporaria`, chamada vencida. Worker segura a chamada e pausa antes de `_travar_cadeia`; a retentativa manual segura pagamento/pedido/parcela e espera a chamada. Liberar worker produz **`OperationalError: deadlock detected`**, na trava de `pagamentos_chamadaaoprovedor`. O teste apenas pausa operações reais. O alvo próprio evita a colisão inicial de autorização, mas não essa inversão na mesma parcela. Unificar ordem/protocolo e provar a corrida com uma liquidação e a mesma chave.

R05 e R09 (E10-05/06) também afetam as operações deste módulo. R08 registra a não conformidade TDD; os registros históricos do implementador não constituem autorização para repetir exceções de etapas anteriores.

## Correções E10-R03 e R04 — agente 2 — 2026-10-30

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Testes A-29 e A-30 | `b02d06b` | `uv run pytest tests/tecnicos/test_devolucoes_concorrencia.py` | **Red: 2 failed.** A-29: `OperationalError: deadlock detected ... pagamentos_chamadaaoprovedor`; A-30: `erro inesperado OperationalError` no log da tarefa. O verde funcional (nova tentativa isolada, A-18) já existia |
| Ajuste do arranjo `Corrida`: `rodar(..., b_atomica=False)` para B, como a rota (`ATOMIC_REQUESTS` falso) | `f6feaea` | idem | Red reconferido no código antigo com o teste final: 2 failed |
| `tentar_devolucao_de_novo`: chamada (sem `skip_locked`/`nowait`) → cadeia → escrita; `verificar_estornos` agendada antes da cadeia | `f6feaea` | `test_devolucoes_concorrencia.py`, `test_devolucoes_execucao.py`, `test_devolucoes_excepcional.py`, `test_financeiro_conciliacao_estornos.py`, `test_devolucoes_telas.py`, `test_devolucoes_avisos.py` | 97 passed |
| Testes A-26 a A-28 | `a058de3` | `test_devolucoes_concorrencia.py`, `test_devolucoes_execucao.py` | **Red: 3 failed.** A-26 e A-27: as duas operações concluem; A-28: `DID NOT RAISE DevolucaoRecusada` |
| Autorização trava conta da obrigação e reserva (`travar_contas`, pk crescente); `EM_CURSO` em `desfazer_designacao`; leitura de cobertura da confirmação excepcional com as duas contas travadas | `5940418` | os mesmos e `test_devolucoes_excepcional.py`, `test_financeiro_reserva.py` | 80 passed |

**Ponto para o revisor/especificador (prova `test_retentativa_manual_versus_worker`).** A prova do parecer roda B dentro de uma transação externa (`Corrida.operacao_b`). Com isso a consulta ao provedor da nova tentativa (`consultar_antes_de_decidir`, que trava o pagamento) mantém o lock até o fim da transação externa, e o impasse reaparece fora do código sob teste. Executada com B sem a transação externa (como a rota), a mesma prova passa (arquivo temporário, não commitado). Seguir a spec ao pé da letra (consulta antes da transação; chamada sem `nowait`) e passar a prova como está são incompatíveis; **decisão pedida**: ajustar o arranjo da prova (B sem transação externa) ou autorizar `nowait`/chamada antes da consulta.

**Ajuste de arranjo (E10-06 A-10).** Com a R03, a designação de obrigação com parcela não final não se desfaz; o A-10 da E10-06 usa agora uma parcela `elegivel_excepcional` de fábrica sem cobertura. As asserções não mudaram.

**Agendamentos feitos sob a cadeia.**
- `verificar_estornos` (de `_declarar_falha_definitiva`): não se demonstra a ausência de um `verificar_estornos` pendente em execução (ex.: reconsulta velha agendada por uma recusa que leu a parcela como elegível); por isso passou para **antes** da cadeia (`_estorno_falhou` e `_aplicar_estorno`). Se a parcela não chegar à falha definitiva, a reconsulta agendada não encontra nada a fazer.
- `acompanhar_estorno` (de `_aplicar_estorno` e `_adotar_estorno`): a parcela só sai de `em_processamento` dentro da própria chamada `acompanhar_estorno`, que se encerra na mesma transação; logo, nas situações de onde se entra em `em_processamento` (solicitada, falha temporária, falha definitiva, elegível) não há `acompanhar_estorno` pendente nem em execução. Permanece sob a cadeia.
- `estornar` (autorização): a parcela é nova; não há chamada anterior.

## Não conformidade de TDD (R08) — E10-04 A-23 e A-24

Registro anterior preservado: não houve Red das corridas (travas escritas com o código funcional). Busca de evidência (passo 1): nada nos commits `ddf8016`/`77fca2e` nem nos logs de 2026-10-29. **Sensibilidade (mutação), não Red** — `uv run pytest tests/tecnicos/test_devolucoes_concorrencia.py`:

| Mutação | Resultado |
|---|---|
| A-23: `autorizar_devolucao` sem `travar_pagamento` e sem a trava da `SituacaoDoPedido` | 1 failed, `test_duas_autorizacoes_da_mesma_obrigacao_geram_uma_parcela` (`IntegrityError` no lugar de `None`) |
| A-24: `_concluir_verificacao` e `_aplicar_estorno` com só a releitura | o teste existente **não falhou** (11 passed). Reforçado (`20695e8`, `8eac7e0`) com duas corridas: `test_verificacao_contra_confirmacao_excepcional_nunca_devolve_duas_vezes` e `test_conclusao_contra_recusa_da_mesma_parcela_fica_concluida_sem_falha_no_historico`. Com a mutação: 2 failed (`LiquidacaoRecusada` e histórico com `falha_definitiva`); sem ela: 13 passed |

## Complemento das correções (P1 e P4) — agente 2 — 2026-10-30

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Testes A-31 e A-32; `Corrida.rodar(a_atomica=...)`; A-30 com `a_atomica=False` | `7998530` | `uv run pytest tests/tecnicos/test_devolucoes_execucao.py tests/tecnicos/test_devolucoes_concorrencia.py` | **Red: 1 failed.** A-31: `DID NOT RAISE RuntimeError` (a função consultava o provedor e antecipava a chamada). A-32 passou (regressão, sem Red, como a spec prevê) |
| `tentar_devolucao_de_novo`: `_exigir_fora_de_transacao()` logo depois da conferência do autor, antes da consulta ao provedor | `7998530` | os mesmos e `test_devolucoes_telas.py` | 61 passed |
| Testes A-33, A-34, A-35 (dublê na classe `ProvedorSimulado`, com `RecusaDoProvedor("estado_invalido")` e `PagamentoNaoEncontrado`) | `1634081` | `uv run pytest tests/tecnicos/test_devolucoes_execucao.py` | **Red: 3 failed.** Nos três a chamada `verificar_estornos` terminou `falhou` em vez de `pendente` (`'falhou' != 'pendente'`; no A-34, `tentativas` 1 e nenhum alerta; no A-35, `nao_encontrado` depois de 25 horas) |
| `_executar_verificacao` traduz `PagamentoNaoEncontrado` e `RecusaDoProvedor` em `FalhaTemporaria`; gancho `adiada` (`_verificacao_adiada`: alerta `devolucao_com_falha`, código `reconsulta:<codigo>`, a partir da 3ª tentativa); `_concluir_verificacao` resolve o alerta com "reconsulta concluída" | `1634081` | o mesmo arquivo | 31 passed |

**Decisão técnica.** O dublê da recusa usa `monkeypatch.setattr(ProvedorSimulado, ...)` (a classe), e não a instância `SIMULADO`: na instância, o `undo` deixava um atributo de instância residual e os espiões de `test_pagamentos_concorrencia.py` falhavam em suíte completa (2 failed em duas execuções; corrigido em `45a91e5`).

**Ponto de atenção para o revisor (invariante "toda parcela em `falha_definitiva` tem uma `verificar_estornos` pendente").** O caminho `verificacao_inconclusiva` (A-15: só estornos de outro valor) conclui a chamada e deixa a parcela em `falha_definitiva` sem reconsulta pendente. A spec do P4 não trata esse caso, e o A-15 existente exige que a parcela fique como está. Não alterei o comportamento; fica para decisão do especificador.

**Prova do parecer `test_retentativa_manual_versus_worker`:** substituída pelo A-29, como manda o complemento; executada como está, a operação B recebe `RuntimeError` (a guarda do A-31).
