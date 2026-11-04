# E13-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjos:** AF e AF-parcial (E13-01), com a liberação do Pix configurada no simulador (`definir_liberacao("pix", horas=72)`). X é pago em `T0 + 2h` (liberado em `T0 + 74h`) e Y em `T0 + 20h` (liberado em `T0 + 92h`). Salvo indicação, o relógio fica em `T0 + 80h`: X liberado, Y a liberar.

**Valores de partida no AF:**

| Conta | Saldo | Liberado | A liberar |
|---|---|---|---|
| Obrigação com F | 170,00 | 80,00 (produtos de X) | 90,00 |
| Frete | 22,00 | 10,35 (frete de X) | 11,65 |

**Chamadas:** `registrar_repasse(admin, rodada, valor=..., identificacao=..., justificativa=...)` e `registrar_pagamento_do_frete(...)`, fora de transação.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 40, §10 | positivo | AF | repasse de 80,00, identificação `pix-001` | um movimento `repasse` que só baixa `obrigacao_fornecedor(F, rodada)` (saldo 90,00); custódia, receita de serviço, frete, reserva e as contas de outro fornecedor iguais; a auditoria `rodada.repasse` com o liberado 80,00 e o a liberar 90,00. **Red esperado:** a função não existe |
| A-2 | Infra 3.4, T-11 | negativo | AF | repasse de 80,01 | `LiquidezInsuficiente`, com "R$ 80,00" e "R$ 90,00" na mensagem; nenhum movimento |
| A-3 | Infra 3.4 | positivo | AF; relógio em `T0 + 92h` | repasse de 170,00 | aceito; a obrigação com F com saldo 0,00 |
| A-4 | T-11 | negativo | AF e uma rodada de outro fornecedor G, montada como o AF com o `T0` cinco dias antes, aprovada e com os pagamentos já liberados | repasse de F de 80,01 | `LiquidezInsuficiente`, mesmo com o saldo do provedor maior que 80,01 (o liberado de G não conta para F); nenhuma conta de G muda |
| A-5 | Infra 4.2, herdado E07 | negativo | AF; `falhar_proximas(1, operacao="buscar_por_referencia")` | repasse de 10,00 | `ConsultaAoProvedorFalhou`; nenhum movimento nem auditoria |
| A-6 | Infra 4.2 | positivo | AF | repasse de 10,00 com o simulador registrando as consultas | uma busca por referência de X e uma de Y antes do movimento |
| A-7 | Regra 2 | negativo | uma rodada em `pagamento` (sem apuração no livro) | repasse e pagamento do frete | `RepasseRecusado("sem_obrigacao")` nos dois, sem consulta |
| A-8 | E09-07 | negativo | o A-1 | repasse de 1,00 com a identificação `pix-001` de novo | `SaidaRepetida`; nenhum movimento |
| A-9 | Regra 1 | negativo | AF | repasse com um comprador, com a conta do fornecedor F e com `None`; e dentro de `transaction.atomic()` | `PermissionDenied` nos três; `RuntimeError` no último; sem escrita |
| A-10 | Regra 5, §7.2 | positivo | AF; a rodada cancelada sem reembolso depois da aprovação | repasse de 80,00 | aceito; a obrigação com F com 90,00 |
| A-11 | Regra 5, E12-03 | negativo | AF; relógio em `T0 + 92h`; a rodada cancelada com reembolso depois da aprovação | repasse de 0,01 | `LiquidezInsuficiente` (a obrigação foi consumida pelas devoluções) |
| A-12 | Regra 8 | negativo | AF | pagamento do frete de 22,00 | `LiquidezInsuficiente`, com "R$ 10,35" e "R$ 11,65". **Red esperado:** aceito (hoje o limite é o saldo) |
| A-13 | Regra 8 | positivo | AF | pagamento do frete de 10,35 | aceito; o frete com saldo 11,65; nenhuma outra conta muda |
| A-14 | Regra 8 | positivo | AF-parcial: o frete arrecadado é o de X depois do estorno proporcional da caixa invalidada (10,35 − 2,59 = 7,76), e o déficit é 22,00 − 7,76 = 14,24; o déficit coberto pela reserva (E09-05) | `liquidez(frete(rodada))`; pagamento do frete de 22,00 | antes da cobertura, liberado 7,76; depois, 22,00 (7,76 + 14,24); o pagamento aceito |
| A-15 | Regra 8 | positivo | AF-parcial; o déficit coberto pela receita de serviço de outra rodada (E09-06, `cobrir_despesa`) | `liquidez(frete(rodada))` | liberado 22,00, como no A-14 |
| A-16 | Regra 8 | positivo | AF; uma devolução de X depois da apuração (ocorrência simulada por `registrar_obrigacao_com_comprador` com frete 2,00) | `liquidez(frete(rodada))` | o liberado reduzido em 2,00 (8,35), pela saída do frete |
| A-17 | Concorrência | concorrência | AF | dois repasses de 50,00 em paralelo, com transações reais | um aceito e o outro `LiquidezInsuficiente`; o liberado nunca fica negativo |
| A-18 | Regras 11 e 12 | positivo | AF | GET `administracao/rodadas/<pk>/saidas/` | 200; a obrigação com F: saldo R$ 170,00, liberado R$ 80,00, a liberar R$ 90,00; o frete: efetivo R$ 22,00, arrecadado R$ 22,00, déficit R$ 0,00, saldo R$ 22,00, liberado R$ 10,35; os dois formulários |
| A-19 | Regra 13 | positivo | AF; o administrador com nova autenticação recente | POST `.../saidas/repasse/` com `valor=80,00`, a identificação e a justificativa | redireciona com "Repasse de R$ 80,00 registrado."; a página mostra o repasse no histórico com o nome do administrador |
| A-20 | Regra 13 | negativo | AF | POST `.../saidas/repasse/` com `valor=80,01`; com a identificação repetida; sem justificativa; com `valor=abc`; e com o provedor falhando | 409 com "Só R$ 80,00 estão liberados no provedor (R$ 90,00 a liberar)."; 409 com "Esta identificação de saída já foi registrada."; 400 com "Informe a justificativa."; 400; 503 com a mensagem da regra 13 |
| A-21 | Regra 13 | negativo | AF | POST `.../saidas/frete/` sem nova autenticação recente; GET nas duas rotas; POST como comprador e como fornecedor | o redirecionamento para a nova autenticação, sem chamar o serviço; 405; 403; 403 |
| A-22 | Regra 14 | positivo | AF | GET a página do pedido formal e a da rodada | o link "Saídas da rodada" nas duas |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-16 | `tests/tecnicos/test_repasse.py` |
| A-17 | `tests/tecnicos/test_repasse.py`, com transações PostgreSQL reais |
| A-18 a A-22 | `tests/tecnicos/test_repasse_telas.py` |
