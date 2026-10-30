# E10-03 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:** o simulador reiniciado, com o relógio controlado em `T`. Um pagamento Pix `P1` de 125,00, aprovado em `T`, com tarifa de 1,25 e liberação imediata. Um aporte simulado (`depositar`) de 1.000,00, liberado. O provedor é obtido por `obter_provedor()`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 7 | positivo | o arranjo | `estornar(NovoEstorno(P1, 125.00, "k1"))` | um `EstornoConsultado` `concluido`, com `id_estorno` `sim-est-<n>`; um movimento `devolucao` de −125,00 com o `id_externo` de P1 e o mesmo `id_estorno`; o saldo cai 125,00; a tarifa continua debitada |
| A-2 | Infra 7 | positivo | o arranjo | `estornar` de 25,00 com `"k1"` e depois de 100,00 com `"k2"` | dois estornos `concluido`; dois movimentos `devolucao`; `consultar_estornos(P1)` devolve os dois, em ordem |
| A-3 | Idempotência, T-8 | positivo | o arranjo | `estornar` de 25,00 com `"k1"` duas vezes | o mesmo `id_estorno`; um estorno e um movimento |
| A-4 | Idempotência | negativo | o A-3 | `estornar` de 30,00 com `"k1"` | `RecusaDoProvedor("chave_em_uso")`; nada novo |
| A-5 | T-8, E07 | positivo | `falhar_proximas(1, operacao="estornar", depois_de_executar=True)` | `estornar` de 25,00 com `"k1"`; depois de novo com `"k1"` | a primeira levanta `ProvedorIndisponivel`, com o estorno gravado no simulador; a segunda devolve esse mesmo estorno; um movimento só |
| A-6 | Infra 7 | negativo | `indisponivel()` | `estornar` e `consultar_estornos` | `ProvedorIndisponivel`; nada gravado |
| A-7 | Infra 7, 3.3 | negativo | o arranjo sem o aporte: o saldo liberado é 123,75 (o pagamento menos a tarifa) | `estornar` de 125,00 | `SaldoInsuficienteParaEstorno`; nada gravado. Depois de um `depositar` de 50,00, a mesma chamada conclui |
| A-8 | Infra 4.7 | negativo | o relógio em `T + 181 dias` | `estornar` de 10,00 | `RecusaDoProvedor("prazo_vencido")` |
| A-9 | Infra 7 | negativo | `recusar_estornos(P1, "meio_nao_permite_estorno")` | `estornar` | `RecusaDoProvedor("meio_nao_permite_estorno")`; nada gravado |
| A-10 | Referência §7 | negativo | `sem_estorno_parcial(P1)` | `estornar` de 25,00; depois de 125,00 com outra chave | o primeiro, `parcial_nao_suportado`; o segundo conclui |
| A-11 | Invariante | negativo | um estorno de 100,00 concluído | `estornar` de 30,00 com outra chave | `valor_acima_do_disponivel` |
| A-12 | Referência §7 | positivo | `estornos_em_processamento(P1)` | `estornar` de 25,00; `consultar_estornos(P1)`; `concluir_estorno(id)`; `consultar_estornos(P1)` | primeiro `em_processamento`, sem movimento, e visível na consulta; depois `concluido`, com o movimento no instante da conclusão |
| A-13 | Referência §7 | positivo | o A-12 antes de concluir | `recusar_estorno(id, "estado_invalido")` | `recusado`, com o código; nenhum movimento; o restante do pagamento volta a 125,00 |
| A-14 | Infra 4.7 | positivo | `recusar_mas_processar(P1, "meio_nao_permite_estorno")` | `estornar` de 25,00; `consultar_estornos(P1)`; `concluir_estorno(id)`; `consultar_estornos(P1)` | `RecusaDoProvedor("meio_nao_permite_estorno")`; a primeira consulta vazia; depois da conclusão, o estorno visível e `concluido`, com o movimento |
| A-15 | Infra 7 | negativo | pagamento pendente ou cancelado; `id_externo` inexistente | `estornar` | `estado_invalido`; `PagamentoNaoEncontrado` |
| A-16 | Q-8, Infra 7 | positivo | o arranjo | `contestar(P1)` e `contestar(P1, 10.00, descricao="med")` | dois movimentos `outro`, de −125,00 e −10,00, com as descrições `chargeback` e `med`; a situação de P1 continua aprovada; nenhum aviso simulado; nada no banco do sistema |
| A-17 | Interface | negativo | — | `NovoEstorno` com valor 0, −1, 1.001 ou chave vazia ou com 65 caracteres | `ValueError` |
| A-18 | Concorrência | concorrência | o arranjo | dois `estornar` de 25,00 com `"k1"` em paralelo | um estorno, um movimento; as duas respostas com o mesmo `id_estorno` |
| A-19 | Herdado E09 | positivo | o A-1 | `listar_movimentos` do dia | o movimento `devolucao` com `id_estorno` preenchido; os outros tipos com `id_estorno` `None` |
| A-20 | Controle | positivo | todos os controles novos aplicados | `reiniciar()` e um `estornar` comum | conclui normalmente |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-17, A-19 e A-20 | `tests/tecnicos/test_simulador_estornos.py` |
| A-18 | `tests/tecnicos/test_simulador_estornos.py`, com transações PostgreSQL reais |

## Correção E10-R02 (2026-10-30)

Valem a seção da correção no `spec.md`, o "Padrão das corridas" (E09-01, `spec.md`) e a correção E10-R08 (E10-07, `spec.md`). As duas corridas usam transações PostgreSQL reais e o provedor simulado real.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-21 | R02, AGENTS §6 | concorrência | duas cobranças aprovadas de 80,00, `Pa` e `Pb`, liberadas; uma saída de 60,00 registrada; o saldo liberado em 100,00 | `estornar(Pa, 80.00, "k0")`, que pausa logo depois de ler o saldo liberado, em paralelo com `estornar(Pb, 80.00, "k1")` | um estorno concluído e o outro levanta `SaldoInsuficienteParaEstorno` (e não `RecusaDoProvedor`); um `EstornoSimulado` só; o saldo liberado fica 20,00. **Red esperado:** os dois concluem, e o saldo fica −60,00 |
| A-22 | R02 | concorrência | duas cobranças aprovadas de 80,00, liberadas; o saldo liberado em 200,00 | os dois estornos de 80,00 em paralelo, com a mesma pausa | os dois concluem, sem `deadlock`; o saldo liberado fica 40,00. Regressão da ordem das travas: esperado verde, sem Red |

A prova `test_saldo_compartilhado_em_estornos_concorrentes` do parecer pausa com uma barreira de duas threads. Com a correção, a segunda thread espera a trava do saldo antes da barreira, e a prova esgota o tempo. Ela fica substituída pelo A-21, que libera a pausa também quando a outra conexão está esperando trava.

| Critério | Arquivo de teste |
|---|---|
| A-21 e A-22 | `tests/tecnicos/test_simulador_estornos.py`, com transações PostgreSQL reais |

## Correção E10-R02 residual (2026-10-30)

Valem a seção "Correção E10-R02 residual" do `spec.md`, o "Padrão das corridas" (E09-01, `spec.md`) e a correção E10-R08 (E10-07, `spec.md`).

**Arranjo S:**
- duas cobranças aprovadas de 80,00, `Pa` e `Pb`, liberadas;
- `estornos_em_processamento` nas duas;
- uma saída de 60,00 registrada;
- `consultar_saldo().liberado` em 100,00.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-23 | R02 residual | negativo | o arranjo S | `estornar(Pa, 80.00, "k0")`; depois `estornar(Pb, 80.00, "k1")`; depois `concluir_estorno` do primeiro | o primeiro aceito `em_processamento`; o segundo levanta `SaldoInsuficienteParaEstorno` (e não `RecusaDoProvedor`), sem `EstornoSimulado` novo; depois da conclusão, o saldo liberado fica 20,00. **Red esperado:** o segundo é aceito, e a conclusão dos dois leva o saldo a −60,00 |
| A-24 | R02 residual | positivo | o arranjo S; o estorno de `Pa` aceito em processamento | `recusar_estorno` do estorno de `Pa`; depois `estornar(Pb, 80.00, "k1")` e `concluir_estorno` dele | o de `Pb` aceito; depois da conclusão, o saldo liberado fica 20,00. Regressão da liberação do comprometido: esperado verde depois do A-23 |
| A-25 | R02 residual | negativo | o arranjo S sem `estornos_em_processamento` em `Pa`; `recusar_mas_processar(Pa, "meio_nao_permite_estorno")` | `estornar(Pa, 80.00, "k0")`, que levanta `RecusaDoProvedor`; depois `estornar(Pb, 80.00, "k1")` | o de `Pb` levanta `SaldoInsuficienteParaEstorno`: o invisível em processamento compromete o saldo. **Red esperado:** o de `Pb` é aceito |
| A-26 | R02 residual, concorrência | concorrência | o arranjo S; o estorno de `Pa` aceito em processamento (o disponível é 20,00) | A: `concluir_estorno` do estorno de `Pa`, pausada depois da mudança e do movimento, antes do commit; B: `estornar(Pb, 80.00, "k1")` | B espera a trava do saldo enquanto A está pausada (a espera é vista em `pg_stat_activity` do banco do simulador; o apoio `outra_conexao_esperando` pode ganhar o alias como parâmetro); depois do commit de A, B levanta `SaldoInsuficienteParaEstorno`; o saldo liberado fica 20,00. **Red esperado:** B termina sem esperar a trava |
| A-27 | R02 residual, débito externo | positivo | o arranjo S; o estorno de `Pa` aceito em processamento | `registrar_saida(60.00)`; `concluir_estorno` do estorno de `Pa`; depois `estornar(Pb, 10.00, "k1")` | a conclusão é aceita, e o saldo liberado fica −40,00; o estorno de `Pb` levanta `SaldoInsuficienteParaEstorno`. Regressão do limite dos débitos externos: esperado verde, sem Red |

A prova `test_saldo_nao_negativo_depois_de_processamentos` do parecer chama o segundo `estornar` sem esperar a recusa. Com a correção, ela termina com `SaldoInsuficienteParaEstorno` nessa linha, que é o comportamento especificado. Ela fica substituída pelo A-23, que tem o mesmo arranjo e afirma a recusa e o saldo final não negativo.

| Critério | Arquivo de teste |
|---|---|
| A-23 a A-25 e A-27 | `tests/tecnicos/test_simulador_estornos.py` |
| A-26 | `tests/tecnicos/test_simulador_estornos.py`, com transações PostgreSQL reais |
