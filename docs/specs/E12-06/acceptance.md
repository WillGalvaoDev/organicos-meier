# E12-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:** AP (E12-02) e CI (E12-01).
- **Administrador:** com passkey e nova autenticação recente, como nos testes da E10-07 e da E11-07.
- **Páginas e rotas:** `PAGINA` é `administracao/rodadas/<pk>/estoque/`; `ROTA` é `administracao/rodadas/<pk>/cancelar/`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §13 | positivo | AP | GET `PAGINA` | o bloco "Cancelar rodada" com o aviso, as duas opções sem nenhuma marcada, o campo da mensagem e o botão; sem campo de motivo nem de compradores. **Red esperado:** sem o bloco |
| A-2 | Cenário 43 | positivo | AP; X pago | POST `ROTA` com `reembolso=sim` e uma mensagem | redireciona para `PAGINA` com "Rodada cancelada." e "As devoluções integrais foram geradas e autorizadas."; a página mostra o bloco "Rodada cancelada" com o nome do administrador, "com reembolso", a mensagem e a devolução de X (94,35) com o link do detalhe |
| A-3 | Cenário 44 | positivo | AP; X pago | POST `ROTA` com `reembolso=nao`, sem mensagem | redireciona com "Rodada cancelada."; a página com "sem reembolso" e sem lista de devoluções |
| A-4 | T-16 | negativo | AP | POST `ROTA` com `reembolso=sim` e `compradores=<A>`; depois com `motivo=x` | 400 com a mensagem da regra 2 nos dois; o serviço não é chamado; a rodada na etapa original |
| A-5 | T-16 | positivo | CI | POST `ROTA` só com `reembolso=nao` (sem motivo, sem mensagem) | aceito; a rodada `cancelada` |
| A-6 | Regra 2 | negativo | AP | POST `ROTA` sem `reembolso`; depois com `reembolso=talvez` | 400 com "Informe se existe reembolso devido."; nada cancelado |
| A-7 | T-16, cenário 42 | negativo | um comprador; um fornecedor | POST `ROTA` e GET `PAGINA` | a recusa de `somente_administrador`, sem escrita |
| A-8 | Infra 4.8 | negativo | o administrador sem nova autenticação recente | POST `ROTA` | o redirecionamento para a nova autenticação, sem chamar o serviço |
| A-9 | Método | negativo | o administrador | GET `ROTA` | 405 |
| A-10 | Recusa | negativo | o A-3 | POST `ROTA` de novo | 409 com "Esta rodada já foi cancelada." |
| A-11 | Infra 4.2 | negativo | AP; X pago; a próxima consulta ao provedor falha | POST `ROTA` com `reembolso=sim` | 503 com "Não foi possível consultar o provedor; nada foi cancelado. Tente de novo."; a rodada na etapa original |
| A-12 | Cenário 45 | positivo | o A-2 | GET `PAGINA` | sem os blocos de fechamento, pagamento e apuração; o estoque só para leitura; os pedidos e pagamentos anteriores consultáveis |
| A-13 | Regra 6 | positivo | o arranjo do E12-03 A-10 (obrigação sem cobertura) | GET a lista de devoluções e o detalhe da obrigação | "Autorizada pelo cancelamento da rodada" e "aguardando cobertura"; sem o botão "Autorizar"; as ações de cobertura presentes |
| A-14 | Regra 7 | positivo | o A-2 | GET `pedidos/<X>/` como A | "A rodada foi cancelada pelo administrador. O valor será devolvido integralmente."; a mensagem; o reembolso na seção de estornos com a situação real; sem "Pagar" |
| A-15 | Regra 7 | positivo | o A-2 | GET `pedidos/<Y>/` como B | "Cancelado (rodada cancelada)" e "Nada foi cobrado neste pedido."; sem "Pagar" |
| A-16 | Regra 7 | positivo | o A-3 | GET `pedidos/<X>/` como A | "A rodada foi cancelada pelo administrador." e "O cancelamento não inicia novas devoluções." |
| A-17 | §2, isolamento | negativo | o A-2 | GET `pedidos/<X>/` como B | recusado como hoje (pedido de outro comprador) |
| A-18 | Regra 8 | positivo | o A-2 | GET o painel dos pedidos da rodada | Y com "Cancelado (rodada cancelada)" |
| A-19 | Regra 9 | positivo | CI cancelada (E12-01 A-1) | GET `carrinho/` como D | sem a rodada ativa de F; o pendente de 3 em P1 visível, com a ação de remover |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-13 e A-18 | `tests/tecnicos/test_cancelamento_telas.py` |
| A-14 a A-17 e A-19 | `tests/tecnicos/test_cancelamento_do_comprador.py` |

## Correção da revisão: R01 (2026-11-01)

Arranjo AP-R: o da E12-02 (correção R03). X é o pedido pago de A no ciclo 1, com o retorno ao interesse e a devolução de mínimo pendente.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-20 | R01, regra 7-A | positivo | AP-R; `cancelar_rodada(..., com_reembolso=False)`; `total_reservado(P1) = 0` conferido | GET `pedidos/<X>/` como A | 200; "A rodada foi cancelada pelo administrador." e "O cancelamento não inicia novas devoluções." antes de "Antes do cancelamento, a apuração deste ciclo levou a rodada de volta para interesse, e o valor pago deste pedido será devolvido integralmente."; sem "seus interesses continuam reservados na rodada"; sem "A rodada voltou para interesse." no presente; a devolução de mínimo na seção de estornos com a situação real. **Red esperado:** a prova `test_cancelamento_nao_promete_reservas_do_retorno_anterior` do parecer falhando |
| A-21 | R01, regra 7-A | positivo | AP-R; `cancelar_rodada(..., com_reembolso=True)` | GET `pedidos/<X>/` como A | "A rodada foi cancelada pelo administrador." e "As devoluções já devidas deste pedido continuam em andamento."; sem "O valor será devolvido integralmente." na frase do cancelamento (não houve reembolso novo); a frase histórica do retorno; sem "seus interesses continuam reservados na rodada" |
| A-22 | R01, regressão E11-07 | positivo | AP-R sem cancelamento | GET `pedidos/<X>/` como A | o texto atual da E11-07, com "seus interesses continuam reservados na rodada" (A não impedida); sem a frase histórica |

A prova `test_cancelamento_nao_promete_reservas_do_retorno_anterior` do parecer tem de passar como está.

| Critério | Arquivo de teste |
|---|---|
| A-20 a A-22 | `tests/tecnicos/test_cancelamento_do_comprador.py` |

## Alinhamento com a E03 (2026-11-01)

A regra 4 manda mostrar o formulário de cancelamento em toda etapa cancelável, inclusive `fechamento`. Por isso a asserção da E03 A-25 (`test_rodadas_estoque.py::test_409_do_servico_e_pagina_so_de_leitura_com_a_etapa_relida`), de nenhum formulário na página só de leitura, passa a excluir apenas a ação com `/cancelar/`. As demais ações continuam proibidas nessa página.
