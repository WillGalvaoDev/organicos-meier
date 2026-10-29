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
