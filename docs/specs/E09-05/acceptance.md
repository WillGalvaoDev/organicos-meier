# E09-05 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:**

- O administrador ADM.
- Uma `ObrigacaoComComprador` O1 de R$ 50,00 sem financiamento. Ela representa uma devolução depois do repasse. Como a operação que cria obrigações financiadas pela regra só vem na E09-06, aqui ela é criada por fábrica (o modelo é da E09-04), sem nenhum movimento de financiamento.
- Uma despesa de tarifa D1 de R$ 2,00 pendente.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §16 nº 29, A1 | positivo | livro-razão vazio | `registrar_aporte(ADM, Decimal("1000.00"), "sim-mov-1", "Aporte inicial")` | `reserva` com 1000,00; `situacao_da_reserva()` = (1000,00, 0,00, 1000,00); nenhuma conta de receita, custódia ou fornecedor tocada; movimento `aporte` com autor ADM e a identificação; `EntradaAuditoria` |
| A-2 | Decisão técnica | negativo | o A-1 | o mesmo aporte com `"sim-mov-1"`; valor `0`, `-1.00`, `1.001`, `1.0` (`float`); identificação vazia; justificativa vazia | `AporteRepetido` no primeiro; recusa de validação nos outros; nada é gravado |
| A-3 | P-3, Infra 3.3 | positivo | reserva com 1000,00 | `designar_reserva(ADM, O1, 50.00, "devolução depois do repasse")` | reserva com saldo 1000,00, comprometido 50,00 e livre 950,00; O1 sem cobertura 0,00; nenhum movimento financeiro |
| A-4 | T-10 | negativo | reserva com 30,00 e nenhuma designação | `designar_reserva(ADM, O1, 50.00, ...)`; e `utilizar_reserva(ADM, D1, 40.00, ...)` com D1 de 40,00 | `ReservaInsuficiente` nas duas; nenhuma escrita; O1 continua com 50,00 devidos e sem cobertura |
| A-5 | T-10, §16 nº 34 | positivo | reserva com 30,00 e O1 sem cobertura | `avaliar_reserva()` | alerta `reserva_insuficiente` aberto, com sem cobertura 52,00 (O1 + D1) e livre 30,00 |
| A-6 | §16 nº 34, P-4 | positivo | o A-5 | `registrar_aporte(ADM, 40.00, "sim-mov-2", ...)`; `designar_reserva(ADM, O1, 50.00, ...)`; `utilizar_reserva(ADM, D1, 2.00, ...)` | depois do aporte, o livre é 70,00 e o alerta é resolvido; a designação aceita; a utilização gera F11 de 2,00 para `despesas_a_cobrir`; o saldo da reserva fica 68,00, com comprometido 50,00 e livre 18,00 |
| A-7 | Infra 3.3 | negativo | O1 com 50,00 designados | `designar_reserva(ADM, O1, 0.01, ...)` | `CoberturaExcedente`; nada é gravado |
| A-8 | Infra 3.3 | positivo | a designação do A-3 | `desfazer_designacao(ADM, designacao, "outra fonte")`; depois desfazer de novo | o comprometido volta a 0,00 e O1 a 50,00 sem cobertura, com auditoria; o segundo levanta `DesignacaoEncerrada` |
| A-9 | P-4 | positivo | reserva com 10,00 e obrigações maiores | rodar todas as tarefas periódicas do projeto | nenhum aporte criado; o saldo da reserva continua 10,00 |
| A-10 | Infra 3.4 | negativo | um alerta `invariante_violado` aberto e reserva com 1000,00 | `designar_reserva` e `utilizar_reserva`; e `registrar_aporte` | as duas primeiras levantam `InvarianteViolado`, sem escrita; o aporte é aceito |
| A-11 | Decisão técnica | negativo | o arranjo | um comprador, um fornecedor e um usuário anônimo chamando os serviços como autores | recusados (`PermissionDenied`); nada é gravado |
| A-12 | T-10 | concorrência | reserva com 60,00; duas obrigações O1 e O2 de 50,00 sem cobertura | duas transações em paralelo designam 50,00, uma para cada | uma é aceita e a outra recebe `ReservaInsuficiente`; o comprometido fica 50,00; em qualquer ordem |
| A-13 | T-10 | concorrência | reserva com 60,00; O1 de 50,00; D1 de 40,00 | `designar_reserva` de O1 com 50,00 e `utilizar_reserva` de D1 com 40,00 em paralelo | só uma das duas passa; o livre nunca fica negativo |
| A-14 | Decisão técnica | concorrência | livro-razão vazio | dois `registrar_aporte` com a mesma identificação em paralelo | um aporte; a outra chamada levanta `AporteRepetido` |
| A-15 | Infra 3.3 | positivo | reserva com 100,00; O1 com designação de 50,00; D1 pendente | `itens_sem_cobertura()` | lista só D1, com 2,00; O1 não aparece, porque está totalmente designada |

## Mapeamento para testes

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-11 e A-15 | `tests/tecnicos/test_financeiro_reserva.py` |
| A-1 | também `tests/aceitacao/test_cenario_29_aporte.py` |
| A-4 a A-6 | também `tests/aceitacao/test_cenario_34_reserva_insuficiente.py` (nível do livro-razão) |
| A-12 a A-14 | `tests/tecnicos/test_financeiro_concorrencia.py` |

## Correção E09-R02 — travas da designação (2026-10-22)

Valem a seção da correção no `spec.md`, a "Regra única de travas" e o "Padrão das corridas desta correção" (E09-01, `spec.md`), e a correção E09-R08.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-16 | Correção R02 | concorrência | uma obrigação de 50,00 (fábrica), com a conta `obrigacao_comprador(o)` criada antes da `reserva` (`pk` menor) e semeada com 25,00 financiados; a reserva com 100,00 | `designar_reserva(ADM, o, 25.00, ...)` em paralelo com `liquidar_obrigacao(o, 25.00, referencia="dev-trava")`; cada uma pausa logo depois da sua primeira trava de conta | **Red esperado:** uma das duas falha com `OperationalError` (`deadlock detected`). **Depois da correção:** as duas terminam, em qualquer ordem; a conta da obrigação fica 0,00; uma F15 de 25,00; a designação de 25,00 continua ativa, sem consumo; a reserva fica com saldo 100,00, comprometido 25,00 e livre 75,00; o sem cobertura de `o` é 0,00 |
| A-17 | Correção R02 | concorrência | uma obrigação O1 de 50,00 (fábrica) **sem conta no livro-razão**; a reserva com 100,00; a `receita_servico(r2)` com 100,00 | `designar_reserva(ADM, O1, 50.00, ...)`, que pausa depois de ler o sem cobertura, em paralelo com `cobrir_obrigacao_com_receita(ADM, O1, r2, 50.00, ...)` | **Red esperado:** as duas aceitas, com financiado + designado = 100,00 para um devido de 50,00. **Depois da correção:** uma aceita e a outra levanta `CoberturaExcedente`, sem escrita; financiado + designado = 50,00; o sem cobertura é 0,00. Se a designação venceu, o comprometido é 50,00 e a receita fica 100,00; se venceu a receita, o comprometido é 0,00 e a receita fica 50,00 |

| Critério | Arquivo de teste |
|---|---|
| A-16 e A-17 | `tests/tecnicos/test_financeiro_concorrencia.py` |
