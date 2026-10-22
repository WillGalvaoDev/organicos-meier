# E09-07 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum (L):**

- Os fornecedores A e B, com as rodadas `rA` e `rB`.
- Em `rA`, o pedido XA (produtos 100,00, serviço 5,00 e frete 0,00); em `rB`, o pedido XB (produtos 80,00, serviço 4,00 e frete 0,00).
- Os dois quitados e apurados (E09-06).
- Liberação Pix em 24h e tarifa zero.
- XA aprovado às `T0 + 1h`, XB às `T0 − 30h`. O relógio está em `T0 + 2h`: XB liberado, XA a liberar.
- Um administrador ADM com passkey recente.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 3.4 | positivo | L | `liquidez(obrigacao_fornecedor(A, rA))` e `liquidez(obrigacao_fornecedor(B, rB))` | A: liberado 0,00 e a liberar 100,00; B: liberado 80,00 e a liberar 0,00 |
| A-2 | T-11 | negativo | L | `registrar_saida(ADM, tipo="repasse", conta=obrigacao_fornecedor(A, rA), valor=50.00, identificacao="sim-mov-9", ...)` | `LiquidezInsuficiente`, mesmo com o saldo do provedor em 189,00; nada é gravado |
| A-3 | T-11, §16 nº 40 | positivo | L com o relógio em `T0 + 25h` | o mesmo repasse de 50,00 | aceito; F12 de 50,00; `obrigacao_fornecedor(A, rA)` 50,00; `obrigacao_fornecedor(B, rB)` intacta; auditoria |
| A-4 | Infra 3.4 | positivo | o A-3 com uma obrigação de comprador de `rA` financiada por F9 com 20,00 | `liquidez(obrigacao_fornecedor(A, rA))` | liberado 30,00 (100,00 liberados − 50,00 − 20,00) |
| A-5 | Infra 3.4 | positivo | L, com XA2 (produtos 60,00) também válido em `rA`, aprovado às `T0 + 1h` com liberação em 48h; relógio em `T0 + 25h` | `liquidez(obrigacao_fornecedor(A, rA))` | liberado 100,00 e a liberar 60,00 |
| A-6 | Infra 3.2 | negativo | L | saída `repasse` da `receita_servico(rA)`; saída `retirada_de_receita` da `obrigacao_fornecedor(A, rA)`; identificação repetida; justificativa vazia | `MovimentoProibido` nas duas primeiras; `SaidaRepetida`; recusa de validação; nada é gravado |
| A-7 | Infra 3.4 | positivo | o simulador com `depositar(1000.00)` e o aporte registrado (E09-05); L | `verificar_invariante_agora()` | saldo do provedor 1189,00; obrigações de terceiros 180,00 (custódias 0,00 + fornecedores 180,00 + frete 0,00 + obrigações com comprador 0,00); nenhum alerta |
| A-8 | Infra 3.4 | positivo | o A-7 com `ajustar_saldo(Decimal("-1100.00"))` | `verificar_invariante_agora()` | alerta `invariante_violado` aberto, com a diferença −91,00; depois `ajustar_saldo(1100.00)` e nova verificação: alerta resolvido |
| A-9 | Infra 3.4 | negativo | o alerta `invariante_violado` aberto | `registrar_saida` de `retirada_de_receita` dentro do liberado; e de `repasse` dentro do liberado | a retirada levanta `InvarianteViolado`; o repasse é aceito |
| A-10 | Infra 3.4 | negativo | `indisponivel()` | `verificar_invariante_agora()` | devolve `None`; um log `warning`; os alertas ficam como estavam |
| A-11 | Infra 3.5 | positivo | o dia `D` com: pagamentos e tarifas dos pedidos do arranjo sincronizados; o depósito e o aporte; e um repasse de 50,00 de B (liberado), feito por `registrar_saida` no simulador e registrado no livro com o `id_movimento` dele | `conciliar_dia(D)` no dia seguinte | `ConciliacaoDiaria` com resultado `ok`, todos os movimentos com par e diferença 0,00; nenhum alerta |
| A-12 | Infra 3.5, 3.6 | positivo | um pagamento aprovado no simulador no dia `D` e nunca sincronizado | `conciliar_dia(D)` | alerta `pagamento_sem_conciliacao` com a chave `id_externo`; uma chamada `consultar_pagamento` pendente para ele; resultado `divergente`; depois de `processar_chamadas()`, a entrada é feita e o alerta resolvido |
| A-13 | Infra 3.5 | positivo | um `depositar(200.00)` no simulador sem aporte registrado; e um aporte registrado com a identificação `"inexistente"` | `conciliar_dia(D)` | um alerta `divergencia_na_conciliacao` com a chave do `id_movimento` do depósito e outro com a chave `livro:inexistente`; depois `registrar_aporte` com a identificação do depósito resolve o primeiro |
| A-14 | Infra 3.5 | positivo | um `ajustar_saldo(-0.50)` no dia `D` | `conciliar_dia(D)` | alerta de divergência para o movimento `ajuste`; nenhum alerta `saldo:<D>` (a diferença está explicada) |
| A-15 | Infra 3.5 | positivo | (i) um movimento F1 de 10,00 lançado direto por `lancar` (fora dos serviços, sem pagamento no provedor) no dia `D`; (ii) outro arranjo, com um alerta `saldo:<D − 1>` aberto e o dia `D` sem diferença | `conciliar_dia(D)` | (i) alerta `saldo:<D>` com a diferença −10,00, porque nenhum movimento a explica; (ii) o alerta `saldo:<D − 1>` resolvido |
| A-16 | Decisão técnica | negativo | o A-11 | `conciliar_dia(D)` de novo; `conciliar_dia(hoje)`; e `conciliar_dia(D + 1)` com o provedor indisponível | o mesmo registro, sem consultar o provedor; `ValueError`; `ConsultaAoProvedorFalhou` e nenhum registro |
| A-17 | Decisão técnica | positivo | o último dia conciliado é `D − 3`; o relógio em `D + 1`, 01:00 no horário de Brasília | `conciliar_dias_pendentes_agora()` | concilia `D − 2`, `D − 1` e `D`, nessa ordem; com o provedor falhando em `D − 1`, para ali e deixa `D − 1` e `D` para a próxima |
| A-18 | Decisão técnica | positivo | o relógio em `D`, 23:59 no horário de Brasília | `conciliar_dias_pendentes_agora()` | não concilia `D` |
| A-19 | T-11 | concorrência | L com o relógio em `T0 + 25h` | dois repasses de 60,00 da `obrigacao_fornecedor(A, rA)` em paralelo | um aceito e o outro `LiquidezInsuficiente`; o saldo final é 40,00 |
| A-20 | Decisão técnica | concorrência | o arranjo do A-11 | duas `conciliar_dia(D)` em paralelo | um `ConciliacaoDiaria`; nenhum alerta duplicado |
| A-22 | Saldo de relatório (E09-02) | positivo | L; um provedor de teste (dublê do protocolo) cujo `consultar_saldo` devolve 189,00 com `referente_a = T0 + 2h`; depois disso, às `T0 + 3h`, o pedido XC (125,00) é quitado e entra na custódia | `verificar_invariante_agora()`; depois o dublê devolve 89,00 com o mesmo `referente_a` | na primeira, nenhum alerta: as obrigações até `T0 + 2h` são 180,00, e a entrada de XC, posterior, não entra (sem o recorte seriam 305,00, um falso alerta); na segunda, alerta `invariante_violado` com a diferença −91,00 |
| A-23 | Coerência com o Mercado Pago | positivo | um dublê do provedor que lista, no dia `D`, um movimento `outro` com `descricao_no_provedor = "chargeback"` | `conciliar_dia(D)` | alerta `divergencia_na_conciliacao` com a chave do `id_movimento` e o rótulo `chargeback` nos dados |
| A-21 | AGENTS.md §6 | positivo | o A-12 | os movimentos do livro-razão antes e depois da conciliação | a conciliação não criou nenhum movimento |

## Mapeamento para testes

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-6 | `tests/tecnicos/test_financeiro_liquidez_e_saidas.py` |
| A-2 e A-3 | também `tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py` (T-11) e `tests/aceitacao/test_cenario_40_repasse.py` (nível do livro-razão) |
| A-7 a A-10 e A-22 | `tests/tecnicos/test_financeiro_invariante.py` |
| A-11 a A-18, A-21 e A-23 | `tests/tecnicos/test_financeiro_conciliacao.py` |
| A-19 e A-20 | `tests/tecnicos/test_financeiro_concorrencia.py` |

## Correções da revisão da E09 (2026-10-22)

Valem as seções das correções no `spec.md` e a correção E09-R08 (E09-01). Nos A-26 e A-27, o provedor é um dublê do protocolo, como no A-22. O dia `D` é um dia já terminado no horário de Brasília.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-24 | Correção R05, E09-05 | positivo | (i) o provedor responde, sem violação do invariante; uma despesa de tarifa de 10,00 pendente; a reserva com 0,00; nenhum alerta `reserva_insuficiente`. (ii) o (i) depois da verificação, com a tarifa coberta por `cobrir_tarifas_pendentes_da_rodada(r)` (a receita de `r` com 10,00). (iii) o arranjo do (i) com `indisponivel()` | `verificar_invariante_agora()` em cada caso | (i) devolve o resultado do invariante, sem alerta `invariante_violado`; o alerta `reserva_insuficiente` fica aberto, com sem cobertura 10,00 e livre 0,00. (ii) o alerta é resolvido. (iii) devolve `None`, com o log `warning`; os alertas do invariante ficam como estavam; o alerta `reserva_insuficiente` fica aberto. **Red esperado:** em (i), nenhum alerta `reserva_insuficiente` |
| A-25 | Correção R06 | positivo | um aporte registrado em `D` com a identificação `"a" * 64` e uma saída registrada em `D` com a identificação `"s" * 64`, sem movimento correspondente no provedor | `conciliar_dia(D)`; depois, com o relógio em `D + 2`, `conciliar_dias_pendentes_agora()` | um `ConciliacaoDiaria` de `D`, `divergente`; dois alertas `divergencia_na_conciliacao` com as chaves `livro:` + 64 caracteres (70 no total), com a identificação inteira nos dados; a tarefa concilia `D + 1` em seguida. **Red esperado:** `ValueError` da chave e nenhum registro do dia |
| A-26 | Correção R07 | positivo | (i) o saldo do provedor 0,00 com `referente_a` às 10:00 de `D`, e um movimento `ajuste` de +10,00 às 12:00 de `D`; o livro-razão vazio. (ii) um pagamento de 125,00 no provedor às 23:00 de `D`, com a entrada no livro-razão às 00:30 de `D + 1`; o saldo do provedor 125,00 com `referente_a` às 23:30 de `D` | `conciliar_dia(D)` à 01:00 de `D + 1` | (i) diferença 0,00; nenhum alerta `saldo:<D>`; o alerta de divergência do `ajuste` aberto (é um movimento do dia). (ii) diferença 0,00; nenhum alerta `saldo:<D>` nem `pagamento_sem_conciliacao` (a entrada existe na execução). **Red esperado:** em (i), diferença −10,00; em (ii), diferença +125,00 |
| A-27 | Correção R07 | negativo | um aporte de 100,00 registrado às 12:00 de `D` com a identificação `"futuro"`; um depósito `"futuro"` de 100,00 no provedor só à 01:00 de `D + 1`; o saldo do provedor 100,00 com `referente_a` às 02:00 de `D + 1` | `conciliar_dia(D)` às 02:00 de `D + 1` | o resultado é `divergente`, com `sem_par = 1`; o alerta `livro:futuro` aberto; a diferença é 0,00 e não há alerta `saldo:<D>` (no instante `t`, o depósito e o aporte se pareiam). **Red esperado:** `ok` com `sem_par = 0` |

| Critério | Arquivo de teste |
|---|---|
| A-24 | `tests/tecnicos/test_financeiro_invariante.py` |
| A-25 a A-27 | `tests/tecnicos/test_financeiro_conciliacao.py` |
