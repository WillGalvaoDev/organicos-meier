# E12-07 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_ponta_a_ponta.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-8 | `49b954c` | **8 passed; suíte completa 2900 passed**; `ruff`, `mypy`, `makemigrations --check` limpos |

## Sobre o Red
A fatia, pelo `spec.md`, não cria comportamento novo: os cenários exercitam o que as E12-01 a E12-06 entregaram. Não há Red de código de produção; os testes são de regressão ponta a ponta e passaram assim que os ajustes do próprio teste (abaixo) foram feitos. Isso é registrado como tal, e não como Red.

## Ajustes do próprio teste (antes de passar; nenhum afrouxa asserção de comportamento)
- **A-3:** a autorização acontece 3 dias depois: o pagamento aprovado depois da margem só fica liberado para estorno com o saldo do provedor depois disso (antes, `saldo_insuficiente`, `falha_temporaria` do simulador). **Ponto para o especificador:** o critério não fala do prazo de liberação.
- **A-4:** o aporte e o movimento de cobertura de despesa vão em transações separadas (regra de ordem das travas do livro); a falta de cobertura vem desse movimento, como na E12-03 A-10.
- **A-5:** o estorno da parcial é 2,50 (2,00 de produtos, 0,10 de serviço e 0,40 de frete), e o pedido de 7,99 + 0,40 + 1,60 vale 9,99; o critério fala de 2,00 do item e de "igual ao pago".
- O administrador entra de novo (`entrar_de_novo`) depois de cada avanço do relógio, como na E11-07.
