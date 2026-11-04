# E13-05 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:** AF e AF-parcial (E13-01), aprovados em `T0 + 48h`. A previsão inicial é 11/11/2026, e o relógio fica em 2026-11-05 12:00 UTC (09:00 em Brasília), salvo indicação.
- **Chamada:** `ajustar_previsao_de_entrega(admin, rodada, date(...))`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §10 | positivo | AF | ajustar para 2026-11-14 | uma `PrevisaoDeEntrega` `ajuste` com o autor e `data = 2026-11-14`; `previsao_vigente(ciclo)` devolve ela; o `PedidoFormal` (inclusive `previsao_inicial` e o corpo) e as linhas iguais, campo a campo. **Red esperado:** a função não existe |
| A-2 | §12 | positivo | AF | ajustar para 2026-11-14 | A e B recebem um `previsao_de_entrega_alterada` cada, com o título `Previsão de entrega alterada: F`, o corpo `A previsão de entrega do seu pedido <pk> da rodada de F passou de 11/11/2026 para 14/11/2026.`, o link `/pedidos/<pk>/` do próprio pedido e a chave `previsao_de_entrega_alterada:<previsão>:<conta>`; e-mails na fila de envios da E04 |
| A-3 | Regra 6 | positivo | AF-parcial | ajustar | só A recebe o aviso (Y não é válido) |
| A-4 | Regra 6, §2 | positivo | AF; B suspensa; e, em outro teste, B removida | ajustar | B suspensa recebe o aviso; B removida não recebe; A recebe nos dois |
| A-5 | Privacidade | negativo | o A-2 | ler o corpo de A e o de B | nenhum com o nome, o pedido ou o e-mail do outro |
| A-6 | Regra 4 | negativo | AF | ajustar para 2026-11-04 (ontem em Brasília) | `PrevisaoRecusada("data_passada")`; sem escrita nem aviso |
| A-7 | Regra 4 | positivo | AF; relógio em 2026-11-05 02:30 UTC (23:30 de 04/11 em Brasília) | ajustar para 2026-11-04 | aceito (é hoje em Brasília) |
| A-8 | Regra 4 | negativo | AF | ajustar para 2026-11-11 (a vigente) | `PrevisaoRecusada("sem_alteracao")`; sem escrita nem aviso |
| A-9 | Regra 4 | negativo | AF cancelada (E12); e, em outro teste, uma rodada em `pagamento` | ajustar | `PrevisaoRecusada("fora_de_aguardando_fornecedor")`, sem escrita |
| A-10 | Regra 2 | negativo | AF | ajustar com `datetime(2026, 11, 14, 10, 0)` e com `"2026-11-14"` | `PrevisaoRecusada("data_invalida")` nos dois |
| A-11 | Regra 1 | negativo | AF | ajustar com um comprador, com a conta do fornecedor e com `None` | `PermissionDenied` nos três, sem escrita |
| A-12 | Regra 7 | positivo | o A-1 | ler a auditoria | `rodada.previsao_de_entrega` com o autor, 2026-11-11 → 2026-11-14 e 2 compradores avisados |
| A-13 | Regras 8 e 9 | positivo | AF | GET a página do pedido formal; POST `administracao/rodadas/<pk>/previsao/` com `data=2026-11-14` | o bloco com "11/11/2026", o histórico "Prazo padrão de 7 dias" e o formulário; depois do POST, o redirecionamento com "Previsão de entrega alterada para 14/11/2026." e o histórico com "Ajuste" e o nome do administrador |
| A-14 | Regra 9 | negativo | AF | POST sem `data`, com `data=14/11/2026` e com `data=2026-11-04` | 400 com "Informe uma data válida." nos dois primeiros; 409 com "A previsão não pode ser uma data passada." no terceiro |
| A-15 | Regra 9 | negativo | AF | GET na rota; POST como comprador e como fornecedor | 405; 403; 403 |
| A-16 | Regra 8 | negativo | AF cancelada | GET a página do pedido formal | o bloco com a previsão e o histórico, sem formulário |
| A-17 | Regra 10 | positivo | o A-1 | GET `pedidos/<X>/` como A | "Previsão de entrega: 14/11/2026." |
| A-18 | Regra 10 | negativo | AF-parcial; AF cancelada | GET `pedidos/<Y>/` como B no AF-parcial; `pedidos/<X>/` como A no cancelado | sem "Previsão de entrega" nos dois |
| A-19 | Concorrência | concorrência | AF | dois ajustes para 2026-11-14 em paralelo, o primeiro pausado antes do commit | o segundo espera a trava e recebe `sem_alteracao`; uma previsão `ajuste`; um aviso por comprador |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-12 | `tests/tecnicos/test_previsao_de_entrega.py` |
| A-13 a A-18 | `tests/tecnicos/test_previsao_de_entrega_telas.py` |
| A-19 | `tests/tecnicos/test_previsao_de_entrega.py`, com transações PostgreSQL reais |
