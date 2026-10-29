# E09-08 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:**

- O administrador ADM com passkey recente (`tests/apoio/webauthn_falso.py`), um comprador e um fornecedor.
- O estado do A-1 da E09-06: a rodada apurada, a tarifa coberta e o déficit de 10,00 pendente.
- A reserva com 1000,00 e uma obrigação O1 de 25,00 sem cobertura.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §13 | positivo | o arranjo | ADM abre `financeiro_resumo` | 200; mostra `obrigacao_fornecedor` de A com 100,00 e o liberado e a liberar; frete com efetivo 30,00, arrecadado 20,00 e déficit 10,00; reserva 1000,00 / 0,00 / 1000,00; o déficit e O1 nas pendências |
| A-2 | §13, Infra 3.1 | positivo | o arranjo | ADM abre `financeiro_movimentos` e depois filtra por `destinacao=receita_servico` e pela rodada | os movimentos com tipo, momento no horário de Brasília, autor "Sistema", justificativa e transferências; o filtro mostra só a apuração e a cobertura da tarifa |
| A-3 | §16 nº 29, Infra 2 | positivo | ADM com passkey recente | `POST financeiro_aporte` com `1.000,00`, `sim-mov-1` e "Aporte inicial" | redireciona com a confirmação; reserva 2000,00; o histórico em `financeiro_reserva` mostra o aporte com autor e identificação |
| A-4 | Infra 2 | negativo | ADM sem passkey recente | `POST financeiro_aporte` e as outras rotas de ação | redireciona para `mfa_reauthenticate_webauthn` com `next`; nada é gravado |
| A-5 | §2, 17.9, E02-10 | negativo | o arranjo | comprador e fornecedor em todas as rotas `financeiro_*`, GET e POST | 403 sem dados; anônimo vai para o login; nada é gravado |
| A-6 | T-10 | negativo | reserva com 20,00 livres | `POST financeiro_designar` de O1 com 25,00 | 409; a mensagem "O valor passa do saldo livre da reserva (R$ 20,00)."; nenhuma designação |
| A-7 | §16 nº 31 | positivo | o arranjo | `POST financeiro_cobrir_despesa` do déficit com a fonte reserva e 10,00 | redireciona; o déficit coberto; `frete(r)` 30,00; reserva 990,00 |
| A-8 | Infra 3.4 | negativo | a receita da rodada com 3,75, dos quais 0,00 liberados | `POST financeiro_retirada` de 1,00 | 409, com a mensagem do liberado; nenhum movimento |
| A-9 | Infra 3.3 | positivo | o alerta `reserva_insuficiente` aberto | ADM abre `financeiro_resumo` e `financeiro_reserva` | o aviso "Reserva insuficiente: obrigações sem cobertura de R$ X para um saldo livre de R$ Y." com os valores do alerta |
| A-10 | Formulários | negativo | ADM com passkey recente | o aporte com `1.000`, `10,001`, `-5` e identificação vazia | 400 com a mensagem do campo; nada é gravado |
| A-11 | Formulários | negativo | o arranjo | `financeiro_designar` e `financeiro_cobrir_obrigacao` com id inexistente | 404 |
| A-12 | Infra 3.3 | positivo | uma designação de O1 | `POST financeiro_desfazer_designacao` com justificativa; e de novo | o primeiro redireciona e o comprometido volta; o segundo responde 409 com a mensagem da designação encerrada |
| A-13 | E09-03 | positivo | um alerta aberto | a notificação `alerta_financeiro` de ADM | o link aponta para `financeiro_resumo` |
| A-14 | E02-10 | positivo | as rotas do projeto | o teste que varre as políticas | todas as `financeiro_*` declaram a política da tabela |
| A-15 | Formulários | negativo | ADM com passkey recente | dois `POST financeiro_aporte` com a mesma identificação, um após o outro | o segundo responde 409 com "Este depósito já foi registrado como aporte."; um aporte só |

## Mapeamento para testes

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-13 e A-15 | `tests/tecnicos/test_financeiro_telas.py` |
| A-14 | `tests/tecnicos/test_permissoes_politica_rotas.py` (o teste existente, que passa a cobrir as rotas novas) |
