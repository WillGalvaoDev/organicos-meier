# E10-01 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:**
- O provedor da conciliação é um dublê do protocolo de saldo e de movimentos, como nos critérios A-22 a A-27 da E09-07. Os alertas e os lançamentos são os reais.
- `D1` e `D2` são dias seguidos, já terminados no horário de Brasília.
- Cada conciliação roda à 01:00 do dia seguinte, com `referente_a` às 23:00 do próprio dia.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | 2A, E09-07 | positivo | um `ajuste` de +10,00 do provedor às 12:00 de `D1` e livro vazio; saldo do provedor de 10,00 em `D1` e em `D2`; nenhum movimento em `D2` | `conciliar_dia(D1)` e depois `conciliar_dia(D2)` | em `D1`: diferença 0,00, `sem_par = 1`, `divergente`, e o alerta do `ajuste` aberto. Em `D2`: diferença 0,00, `sem_par = 0`, resultado `ok`, nenhum alerta `saldo:<D2>`; o alerta do `ajuste` continua aberto. **Red esperado:** em `D2`, diferença +10,00 e o alerta `saldo:<D2>` aberto |
| A-2 | 2A | positivo | um aporte de 100,00 registrado às 12:00 de `D1` com a identificação `"sem-deposito"`, sem depósito no provedor; saldo do provedor 0,00 nos dois dias | as duas conciliações | em `D1`: diferença 0,00 e o alerta `livro:sem-deposito` aberto. Em `D2`: diferença 0,00 e `ok`. **Red esperado:** em `D2`, diferença −100,00 |
| A-3 | 2A | positivo | um pagamento de 125,00 no provedor às 12:00 de `D1`, sem entrada no livro (sem destino decidido); saldo do provedor 125,00 nos dois dias | as duas conciliações | em `D1`: o alerta `pagamento_sem_conciliacao` aberto e diferença 0,00. Em `D2`: diferença 0,00. **Red esperado:** em `D2`, diferença +125,00 |
| A-4 | 2A | positivo | o A-2; depois o depósito `"sem-deposito"` de 100,00 no provedor às 10:00 de `D2`, com o saldo do provedor de 100,00 em `D2` | `conciliar_dia(D2)` | diferença 0,00; o alerta `livro:sem-deposito` resolvido, com o motivo "par encontrado na conciliação de `<D2>`"; o depósito de `D2` sem alerta. **Red esperado:** o alerta `livro:` continua aberto |
| A-5 | 2A | negativo | o A-1; um segundo `ajuste` de −3,00 às 15:00 de `D2`, com o saldo do provedor de 7,00 em `D2` | `conciliar_dia(D2)` | diferença 0,00; `sem_par = 1` (só o ajuste novo); dois alertas de `ajuste` abertos; nenhum `saldo:<D2>` |
| A-6 | 2A | negativo | o A-1; o saldo do provedor de 15,00 em `D2`, ou seja, 5,00 a mais, sem movimento que explique | `conciliar_dia(D2)` | diferença +5,00, só a parte nova; alerta `saldo:<D2>` aberto, com `diferenca = 5.00` |
| A-7 | 2A | positivo | o A-3; a entrada do pagamento lançada às 23:30 de `D1`, depois de `t` de `D1` e antes da execução de `D2`; saldo de 125,00 em `D2` | `conciliar_dia(D2)` | diferença 0,00, porque a entrada já existe em `t` de `D2`; o alerta `pagamento_sem_conciliacao` já foi resolvido pelo `registrar_entrada` (E09-07) e não entra na soma |
| A-8 | 2A | positivo | um `ajuste` de +10,00 às 22:00 de `D1`, que a lista de `D2` também traz (a janela começa em `D2 − 3 dias`); saldo de 10,00 em `D2` | `conciliar_dia(D2)` | o ajuste não entra duas vezes: diferença 0,00 em `D2` |
| A-9 | Caso-limite | negativo | um alerta `divergencia_na_conciliacao` aberto, criado à mão, com `dados` sem `data` | `conciliar_dia(D2)` | a conciliação termina; o alerta não entra na soma; um log `warning` sem dados pessoais |
| A-10 | Invariante | positivo | o `ajuste` do A-1 conciliado em `D1`; os dias `D2`, `D3` e `D4` sem movimento, com o saldo de 10,00 em cada um | `conciliar_dias_pendentes_agora()` à 01:00 de `D5` | `D2`, `D3` e `D4` conciliados `ok`; nenhum alerta `saldo:*`; um só alerta do `ajuste` aberto |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-10 | `tests/tecnicos/test_financeiro_conciliacao.py` |
