# E10-04 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:**
- O pedido X do comprador B (produtos 100,00, serviço 5,00, frete 20,00), pago pelo simulador com o pagamento P1 de 125,00 e com as entradas na custódia (E09-04).
- Um aporte de 1.000,00 no simulador e no livro, para haver saldo no provedor.
- O administrador ADM com passkey recente.
- **O1:** a obrigação do `reembolso_parcial` de um item de X, de 31,25, financiada pela custódia (E10-02).
- As chamadas são executadas por `processar_chamadas()`, com o relógio controlado avançando além de `proxima_em` quando o critério pede nova tentativa.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §9.2, Infra 4.7 | positivo | O1 | `autorizar_devolucao(O1, autor=ADM)` e depois `processar_chamadas()` | depois da autorização: parcela `solicitada`, com valor 31,25, chave gravada e uma `ChamadaAoProvedor` `estornar` pendente com a mesma chave; nenhum estorno no simulador ainda. Depois da tarefa: um estorno de 31,25 no simulador; parcela `concluida` com o `id_estorno`; um movimento F15 com a chave `devolucao:<id_estorno>`; a obrigação liquidada (`devido − liquidado = 0`); duas linhas no histórico |
| A-2 | Herdado E08, E09-04 | positivo | P2, um segundo pagamento de X aprovado (destino `devolucao`/`duplicidade`, obrigação `integral` de 125,00 e alerta `duplicidade` aberto) | autorizar e processar | estorno de 125,00 de **P2**; parcela `concluida`; o alerta `duplicidade` resolvido (E09-06) |
| A-3 | Herdado E08 | positivo | um pagamento `sem_pedido` de 40,00 (obrigação sem pedido nem comprador) | autorizar e processar | estorno de 40,00 desse pagamento; parcela `concluida`; nenhuma trava de `SituacaoDoPedido` exigida |
| A-4 | Infra 4.2, E07-06 | negativo | `indisponivel()` no simulador | `autorizar_devolucao(O1, autor=ADM)` | `ConsultaAoProvedorFalhou`; nenhuma parcela, chamada ou histórico |
| A-5 | Permissão | negativo | B (comprador) e uma conta de fornecedor | `autorizar_devolucao(O1, autor=...)` | `PermissionDenied`; nada gravado |
| A-6 | Idempotência | positivo | O1 autorizada | `autorizar_devolucao(O1, autor=ADM)` de novo | devolve a mesma parcela; uma chamada só |
| A-7 | Decisão técnica | negativo | uma obrigação de 30,00 depois da apuração com 10,00 sem cobertura (E09-06) | autorizar | `DevolucaoRecusada`, com a mensagem de cobrir antes; nada gravado. Depois de `designar_reserva` de 10,00: autoriza |
| A-8 | §9.2 | negativo | uma parcela de 125,00 de P1 já concluída (fábrica de obrigação de 125,00 sobre P1) e O1 sobre o mesmo P1 | autorizar O1 | `DevolucaoRecusada` (passaria do valor do pagamento) |
| A-9 | T-8 | positivo | `falhar_proximas(2, operacao="estornar", depois_de_executar=True)` | autorizar e processar três vezes, avançando o relógio | as duas primeiras execuções deixam `falha_temporaria`, com o código `indisponivel` e as tentativas 1 e 2; a terceira conclui. Um estorno só no simulador, a mesma chave nas três tentativas e um F15 só |
| A-10 | T-8 | positivo | `falhar_proximas(3, operacao="estornar")` | três execuções | `falha_temporaria` com 3 tentativas; o alerta `devolucao_com_falha` aberto (chave `parcela:<pk>`); a quarta conclui e resolve o alerta |
| A-11 | Infra 3.3, E10-03 | positivo | o saldo do simulador abaixo de 31,25 (o aporte retirado do arranjo) | autorizar e processar | `falha_temporaria` com `saldo_insuficiente` e o alerta `devolucao_com_falha` já na primeira tentativa; depois de `depositar` 100,00 e nova execução, `concluida` |
| A-12 | Infra 4.7, P-5 | positivo | `recusar_estornos(P1, "prazo_vencido")` | autorizar e processar até a chamada de verificação concluir | primeiro `falha_definitiva`, com o código na evidência, o alerta `devolucao_em_falha_definitiva` e a chamada `verificar_estornos` agendada; depois da verificação, `elegivel_excepcional`, com a evidência da reconsulta (nenhum estorno), o alerta `devolucao_elegivel_excepcional` aberto e o de falha definitiva resolvido; nenhum F15 |
| A-13 | Infra 4.7 | positivo | `recusar_mas_processar(P1, "meio_nao_permite_estorno")` e, antes da verificação, `concluir_estorno` no simulador | autorizar e processar | a verificação encontra o estorno não contabilizado de 31,25 e a parcela o adota: `concluida`, com F15 `devolucao:<id>`; nunca passa por `elegivel_excepcional` |
| A-14 | Infra 4.7 | negativo | o A-13 com o estorno invisível ainda em processamento na verificação | processar | a verificação não vê o estorno invisível, e a parcela passa de `falha_definitiva` a `elegivel_excepcional`. Este critério documenta o risco residual que a E10-05 detecta |
| A-15 | Infra 4.7 | negativo | um estorno não contabilizado de 10,00 do mesmo pagamento (criado direto no simulador) e `recusar_estornos(P1, "prazo_vencido")` | autorizar e processar | `falha_definitiva` com o código `verificacao_inconclusiva`; o alerta continua aberto; não fica elegível |
| A-16 | Referência §7 | positivo | `estornos_em_processamento(P1)` | autorizar e processar; depois `concluir_estorno` no simulador e processar de novo | `em_processamento` com o `id_estorno` e a chamada `acompanhar_estorno` pendente; a primeira repetição a mantém em processamento; depois da conclusão no simulador, `concluida` com F15 |
| A-17 | Referência §7 | positivo | o A-16 com `recusar_estorno` no simulador em vez de concluir | processar | `falha_definitiva`, depois a verificação e `elegivel_excepcional` |
| A-18 | §9.2 | positivo | o A-10 depois de três falhas | `tentar_devolucao_de_novo(parcela, autor=ADM)` | a chamada pendente com `proxima_em = agora` e a mesma chave; a execução seguinte conclui sem esperar o intervalo |
| A-19 | §9.2 | negativo | parcelas `solicitada` sem falha, `elegivel_excepcional` e `concluida` | `tentar_devolucao_de_novo` | `DevolucaoRecusada` nas três; nada muda |
| A-20 | §9.5 | negativo | uma parcela em `elegivel_excepcional` com a chamada `estornar` ainda pendente por fábrica | processar | `executar` levanta `FalhaDefinitiva("parcela_encerrada")` sem chamar o provedor; nenhum estorno no simulador; a parcela continua igual |
| A-21 | Decisão técnica | negativo | O1 coberta por designação da reserva (fábrica com obrigação depois da apuração) e a parcela `solicitada` | `desfazer_designacao` | `DevolucaoRecusada`; a designação continua ativa |
| A-22 | Transições | negativo | uma parcela `concluida` | aplicar no serviço uma transição para `falha_temporaria` | recusada; a parcela continua `concluida` |
| A-23 | Concorrência | concorrência | O1 | duas `autorizar_devolucao` em paralelo | uma parcela e uma chamada; sem `deadlock` |
| A-24 | Concorrência | concorrência | `estornos_em_processamento(P1)`; a parcela em `em_processamento` | `acompanhar_estorno` e `verificar_estornos` (agendado à mão) em paralelo, com o estorno concluído no simulador | um F15 só; a parcela `concluida`; a segunda operação não faz nada |
| A-25 | Auditoria | positivo | o A-1 | ler a auditoria e o histórico | a autorização com autor, instante e obrigação; o histórico com `solicitada` e `concluida`, cada linha com o instante e os dados |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-22 e A-25 | `tests/tecnicos/test_devolucoes_execucao.py` |
| A-23 e A-24 | `tests/tecnicos/test_devolucoes_concorrencia.py` |
| A-9 e A-10 | também `tests/tecnicos/test_t08_devolucao_idempotente.py` (T-8) |

## Correções E10-R03 e R04 (2026-10-30)

Valem a seção das correções no `spec.md`, o "Padrão das corridas" (E09-01, `spec.md`) e a correção E10-R08 (E10-07, `spec.md`). As corridas usam os serviços reais, o provedor simulado real e transações PostgreSQL. Os critérios do R05 estão na E10-05.

**Arranjo D (designação):** o arranjo da E10-04, com a custódia de X esvaziada para outra obrigação (o "ralo" da prova do revisor), de modo que uma obrigação nova `Od` de 31,25 (um parcial de I1) fica sem financiamento; `designar_reserva(ADM, Od, 31.25, ...)` feita numa transação própria. O sem cobertura de `Od` é 0,00, todo pela designação.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-26 | R03 | concorrência | D | `autorizar_devolucao(Od)`, que pausa logo depois de ler `sem_cobertura_da_obrigacao`, em paralelo com `desfazer_designacao(ADM, d, ...)` | a autorização conclui, com uma parcela `solicitada` e uma chamada `estornar`; o desfazer levanta `DevolucaoRecusada("há devolução em curso para esta obrigação")`; a designação continua ativa; o sem cobertura de `Od` é 0,00. **Red esperado:** as duas concluem, e o sem cobertura fica 31,25 |
| A-27 | R03 | concorrência | D | `desfazer_designacao(ADM, d, ...)`, que pausa logo depois de conferir que não há devolução em curso, em paralelo com `autorizar_devolucao(Od)` | o desfazer conclui; a autorização levanta `DevolucaoRecusada` com a mensagem de cobrir antes; nenhuma parcela e nenhuma chamada. **Red esperado:** a autorização não espera a `reserva`, lê o sem cobertura de antes e cria a parcela; as duas concluem |
| A-28 | R03 | negativo | D com a parcela de `Od` levada a `falha_definitiva` (`recusar_estornos(P1, "prazo_vencido")` e `processar_chamadas(limite=1)`); depois, a mesma parcela levada a `elegivel_excepcional` | `desfazer_designacao(ADM, d, ...)` em cada um dos dois estados | `DevolucaoRecusada` nos dois; a designação continua ativa. **Red esperado:** o desfazer é aceito |
| A-29 | R04 | concorrência | a parcela de O1 em `falha_temporaria` (`falhar_proximas(1, operacao="estornar")`, autorizar e processar), com a chamada vencida (relógio + 2 minutos); o simulador sem falha planejada | `processar_chamadas(limite=1)`, que pausa logo antes de travar a cadeia da parcela, em paralelo com `tentar_devolucao_de_novo(parcela, autor=ADM)` | nenhum `OperationalError` (nem no log); a tarefa conclui o estorno: a parcela `concluida`, um `EstornoSimulado`, um F15 `devolucao:<id_estorno>`; a nova tentativa levanta `DevolucaoRecusada`; a chave da chamada é a da autorização. **Red esperado:** `OperationalError: deadlock detected` na trava de `pagamentos_chamadaaoprovedor` |
| A-30 | R04 | concorrência | o arranjo do A-29 | `tentar_devolucao_de_novo(parcela, autor=ADM)`, que pausa logo depois de travar a cadeia, em paralelo com `processar_chamadas(limite=1)`; depois das duas, `processar_chamadas()` | a nova tentativa conclui (`proxima_em = agora`); a execução paralela não tenta a chamada (`skip_locked`); a execução seguinte conclui o estorno com a mesma chave: um `EstornoSimulado` e um F15; nenhum `OperationalError`. **Red esperado:** a tarefa pega a chamada, que a nova tentativa ainda não travou, e as duas se travam mutuamente (`deadlock detected`) |

As provas `test_autorizacao_versus_desfazer_cobertura` e `test_retentativa_manual_versus_worker` do parecer têm de passar como estão. Os critérios acima as estendem com a ordem inversa e com o estado final do livro.

| Critério | Arquivo de teste |
|---|---|
| A-26, A-27, A-29 e A-30 | `tests/tecnicos/test_devolucoes_concorrencia.py` |
| A-28 | `tests/tecnicos/test_devolucoes_execucao.py` |

## Complemento das correções: pontos do implementador (2026-10-30)

Valem a seção "Complemento das correções" do `spec.md` e a correção E10-R08 (E10-07, `spec.md`). O A-30 passa a rodar a nova tentativa com `a_atomica=False`, sem outra mudança.

**Dublê da recusa na reconsulta:** `consultar_estornos` do provedor simulado substituída por monkeypatch, para levantar `RecusaDoProvedor("estado_invalido")` enquanto o teste quiser. O dublê só troca a resposta do provedor, e não muda trava nem serviço.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-31 | P1, E07-06 | negativo | a parcela de O1 em `falha_temporaria` (arranjo do A-29), num teste com `transaction=True` | `tentar_devolucao_de_novo(parcela, autor=ADM)` dentro de `transaction.atomic()` aberto pelo teste | `RuntimeError`; nenhuma consulta ao provedor registrada no simulador; a chamada pendente com o mesmo `proxima_em`; nenhum histórico novo. **Red esperado:** a função consulta o provedor e antecipa a chamada |
| A-32 | P1 | positivo | o arranjo do A-29, num teste sem `transaction=True` (dentro da transação de teste do Django) | `tentar_devolucao_de_novo(parcela, autor=ADM)` | aceita, como no A-18. Regressão: esperado verde, sem Red |
| A-33 | P4 | positivo | `recusar_estornos(P1, "prazo_vencido")`; O1 autorizada e `processar_chamadas(limite=1)`: a parcela `falha_definitiva`, com a `verificar_estornos` pendente; o dublê da recusa ativo | `processar_chamadas()` | a `verificar_estornos` continua `pendente`, com `tentativas = 1`, `ultimo_erro = "estado_invalido"` e `proxima_em` 1 minuto depois; a parcela continua `falha_definitiva`. **Red esperado:** a chamada termina `falhou`, sem nenhuma pendente |
| A-34 | P4 | positivo | o A-33 | avançar o relógio e processar até a terceira tentativa; depois, retirar o dublê, avançar 60 minutos e processar | da terceira tentativa em diante, `devolucao_com_falha` aberto (chave `parcela:<pk>`, código `reconsulta:estado_invalido`, 3 tentativas), um só; sem o dublê, a parcela passa a `elegivel_excepcional` e o alerta é resolvido com "reconsulta concluída". **Red esperado:** nenhum alerta, e a parcela parada em `falha_definitiva` |
| A-35 | P4 | positivo | o arranjo do A-33 sem o dublê; o `consultar_pagamento` do simulador levantando `PagamentoNaoEncontrado` (dublê); o relógio 25 horas depois da criação da chamada | `processar_chamadas()` | a chamada continua `pendente`, com `ultimo_erro = "nao_encontrado"`. **Red esperado:** `falhou` com `nao_encontrado` |

| Critério | Arquivo de teste |
|---|---|
| A-31 e A-32 | `tests/tecnicos/test_devolucoes_execucao.py` |
| A-33 a A-35 | `tests/tecnicos/test_devolucoes_execucao.py` |

## Correção E10-R11 (2026-10-30)

Valem a seção "Correção E10-R11" do `spec.md` e a correção E10-R08 (E10-07, `spec.md`). O serviço e a tela andam juntos: o A-40 é escrito e visto falhar junto com o A-36, antes da correção.

**Arranjo I:**
- um estorno avulso de 10,00 do pagamento, aceito pelo provedor simulado e concluído, sem parcela (como na prova do parecer);
- `recusar_estornos(P1, "prazo_vencido")`;
- O1 autorizada;
- `processar_chamadas()` até a reconsulta rodar uma vez.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-36 | R11, P4 | negativo | o arranjo I | — | a parcela em `falha_definitiva`, com `codigo_da_falha = "verificacao_inconclusiva"` e a evidência da reconsulta (o avulso de 10,00); `devolucao_em_falha_definitiva` aberto; a **mesma** `verificar_estornos` (mesma chave) `pendente`, com `tentativas = 1`, `ultimo_erro = "verificacao_inconclusiva"` e `proxima_em` 1 minuto depois; nenhum `devolucao_com_falha` aberto. **Red esperado:** a chamada `concluida`, sem nenhuma pendente |
| A-37 | R11 | positivo | o A-36 | avançar o relógio e processar até a quinta reconsulta | todas inconclusivas; a mesma chamada pendente; os intervalos 1, 5, 15, 60 e 60 minutos; o código e a evidência mantidos; nenhum `devolucao_com_falha` aberto a partir da terceira; nenhum histórico de situação novo da parcela. **Red esperado:** nenhuma segunda reconsulta |
| A-38 | R11, infra 4.7, E10-05 | positivo | o arranjo I, com `recusar_mas_processar(P1, "meio_nao_permite_estorno")` no lugar de `recusar_estornos`: o estorno da parcela recusado na resposta e invisível em processamento | a primeira reconsulta (inconclusiva); depois `concluir_estorno` do estorno da parcela; avançar 1 minuto e processar | a parcela adota o próprio estorno e fica `concluida` pela via principal (F15); os alertas resolvidos como no E10-05; a chamada `concluida`. **Red esperado:** a parcela parada em `falha_definitiva` |
| A-39 | R11, P4 | positivo | a parcela em `falha_definitiva`, com o avulso de 10,00 **em processamento** (`estornos_em_processamento` antes dele) e o dublê da recusa do A-33 ativo até a terceira tentativa: `devolucao_com_falha` aberto | retirar o dublê, avançar 60 minutos e processar (inconclusiva); depois `recusar_estorno` do avulso, avançar e processar | na inconclusiva, o `devolucao_com_falha` é resolvido com "reconsulta concluída", e a chamada continua pendente; depois da recusa do avulso, a parcela passa a `elegivel_excepcional`, e a chamada termina. **Red esperado:** a chamada termina na inconclusiva, e a parcela não fica elegível |
| A-40 | R11, R10 | positivo | o A-36 e `montar_tela` | GET `financeiro/devolucoes/` e o detalhe da parcela | na linha da parcela: `verificacao_inconclusiva` e `reconsulta agendada`; no detalhe: o último erro `verificacao_inconclusiva` e as tentativas da reconsulta. **Red esperado:** `sem nova tentativa agendada` |
| A-41 | R11, E10-05 | positivo | uma parcela `elegivel_excepcional` e um estorno sem baixa de outro valor (arranjo do E10-05 para o passo 6) | a reconsulta | a parcela continua `elegivel_excepcional`, com o código `verificacao_inconclusiva`; a chamada termina. Regressão: esperado verde, sem Red |

A prova `test_inconclusiva_mantem_reconsulta_pendente` do parecer tem de passar como está.

| Critério | Arquivo de teste |
|---|---|
| A-36 a A-39 e A-41 | `tests/tecnicos/test_devolucoes_execucao.py` |
| A-40 | `tests/tecnicos/test_devolucoes_telas.py` |
