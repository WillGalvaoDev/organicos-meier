# E09-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum (Ap):** a rodada `r` do fornecedor A, o ciclo `c` e a abertura com frete `F = 30,00`.

| Pedido | Comprador | Produtos | Serviço | Frete | Total |
|---|---|---|---|---|---|
| X | B | 100,00 | 5,00 | 20,00 | 125,00 |
| Y | D | 50,00 | 2,50 | 10,00 | 62,50 |

X é quitado pela entrada da E09-04, com a tarifa 1,25. Y fica sem pagamento (inadimplente). A reserva tem 1000,00 por aporte, e há um administrador ADM.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 3.2 | positivo | Ap | `registrar_apuracao_no_livro(c, [X], autor=SISTEMA)` | um movimento `apuracao`; `obrigacao_fornecedor(A, r)` 100,00, `receita_servico(r)` 5,00 − 1,25 = 3,75 e `frete(r)` 20,00; as custódias de X zeradas; `ApuracaoNoLivro` com efetivo 30,00 e arrecadado 20,00 |
| A-2 | §16 nº 30, P-1 | positivo | Ap; a tarifa de 1,25 pendente | a apuração do A-1 | um movimento F11 de 1,25 de `receita_servico(r)` para `despesas_a_cobrir`, com autor `SISTEMA` e justificativa citando P-1; a despesa coberta; `obrigacao_fornecedor(A, r)` intacta em 100,00; `Pedido` e valores cobrados iguais |
| A-3 | §16 nº 31 | positivo | o A-1 | `frete_do_ciclo(c)` | efetivo 30,00, arrecadado 20,00, devolvido 0,00, déficit 10,00 e déficit coberto 0,00; uma `Despesa(deficit_frete)` de 10,00 pendente |
| A-4 | §16 nº 31 | positivo | o A-3 | `cobrir_despesa(ADM, deficit, fonte=("receita", r), valor=3.75, ...)` e `cobrir_despesa(ADM, deficit, fonte="reserva", valor=6.25, ...)` | `frete(r)` 30,00; receita de `r` 0,00; reserva 993,75; `frete_do_ciclo(c)` com déficit coberto 10,00; nenhum valor novo de comprador; auditoria nas duas |
| A-5 | Infra 3.2 | negativo | a receita de `r` em 0,00 e uma tarifa nova de 0,80 da rodada `r` depois da apuração | `registrar_tarifa` | a tarifa fica pendente (não cabe na receita da rodada); `itens_sem_cobertura()` a lista |
| A-6 | §16 nº 33 | positivo | Ap, antes da apuração | `registrar_obrigacao_com_comprador` de B com produtos 25,00, serviço 1,25 e frete 5,00 | financiada por F8 das três custódias de B; sem cobertura 0,00; as custódias de B ficam 75,00 / 3,75 / 15,00 |
| A-7 | §16 nº 33, P-2 | positivo | o A-1 (apurado), antes do repasse | a mesma obrigação do A-6 | produtos por F9 de `obrigacao_fornecedor(A, r)` (fica 75,00), serviço por F11 de `receita_servico(r)` e frete por F10 de `frete(r)`; uma `Despesa(deficit_frete)` de 5,00 pendente; `frete_do_ciclo(c).devolvido = 5,00` |
| A-8 | §16 nº 33 | positivo | o A-1 com um repasse de 100,00 lançado por F12 | a obrigação de produtos 25,00 | nenhum financiamento de produtos (sem saldo); sem cobertura 25,00; `avaliar_reserva` roda e não abre alerta (livre 1000,00 > 25,00); devido integral mantido |
| A-9 | §16 nº 33 | positivo | o A-8 | `cobrir_obrigacao_com_receita(ADM, obrigacao, rodada_fonte=r2, valor=10.00, ...)` com a receita de outra rodada `r2` em 10,00; e `designar_reserva(ADM, obrigacao, 15.00, ...)` | sem cobertura 0,00; F11 de `receita_servico(r2)`; comprometido 15,00 |
| A-10 | §16 nº 34 | positivo | o A-9 | `liquidar_obrigacao(obrigacao, 25.00, referencia="dev-1")`; depois de novo com `"dev-1"`; depois com `"dev-2"` e 0,01 | na primeira: o saldo financiado da conta (10,00) e a designação (15,00) consumidos, com um movimento F11 da reserva que cita a designação; F15 de 25,00; comprometido 0,00; na segunda: o mesmo movimento, nada novo; na terceira: `LiquidacaoRecusada` |
| A-11 | Infra 3.6 | positivo | uma obrigação de 125,00 vinda de destino `duplicidade` (E09-04 A-3), com o alerta aberto | `liquidar_obrigacao` de 125,00 | o alerta `duplicidade` resolvido; com liquidação parcial de 100,00, o alerta continua aberto |
| A-12 | Idempotência | positivo e negativo | o A-1 | a apuração de novo com `[X]`; depois com `[]` | a primeira devolve a existente, sem movimento novo; a segunda levanta `MovimentoConflitante` |
| A-13 | Pré-condições | negativo | Ap | apuração com Y (sem destino `quita`); com um pedido de outro ciclo; com X repetido | `ValueError` nos três; nada é gravado |
| A-14 | Infra 3.1 | positivo | Ap, sem apuração | `frete_do_ciclo(c)` | todos os campos `None` |
| A-15 | Infra 3.2 | negativo | o arranjo | `registrar_obrigacao_com_comprador` com componente negativo, com soma zero, com comprador de outra rodada, com origem já usada | recusados; nada é gravado |
| A-16 | P-2 | negativo | o A-1 | `cobrir_despesa(ADM, deficit, fonte="reserva", valor=10.01, ...)` e `cobrir_obrigacao_com_receita` acima do sem cobertura | recusados (`CoberturaExcedente` ou valor acima do pendente); nada é gravado |
| A-17 | Concorrência | concorrência | Ap antes da apuração | duas obrigações de B em paralelo, cada uma com produtos 60,00 | em qualquer ordem: a primeira totalmente financiada pela custódia; a segunda com 40,00 financiados e 20,00 sem cobertura; a custódia de produtos de B em 0,00 |
| A-18 | Concorrência | concorrência | uma obrigação de 25,00 totalmente financiada | duas liquidações em paralelo, `"dev-a"` e `"dev-b"`, de 25,00 cada | uma passa e a outra levanta `LiquidacaoRecusada`; uma saída F15 só |
| A-19 | Concorrência | concorrência | Ap com a entrada de X ainda não feita | a apuração com `[X]` em paralelo com a sincronização que quita X | em qualquer ordem, ou a apuração é recusada por X ainda não ter destino (`ValueError`) ou move os saldos completos; nunca move só parte das custódias de X |

## Mapeamento para testes

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-16 | `tests/tecnicos/test_financeiro_apuracao_e_obrigacoes.py` |
| A-2 | também `tests/aceitacao/test_cenario_30_tarifa.py` |
| A-3 e A-4 | também `tests/aceitacao/test_cenario_31_deficit_de_frete.py` |
| A-6 a A-9 | também `tests/aceitacao/test_cenario_33_devolucao_e_repasse.py` |
| A-10 | também `tests/aceitacao/test_cenario_34_reserva_insuficiente.py` |
| A-17 a A-19 | `tests/tecnicos/test_financeiro_concorrencia.py` |
