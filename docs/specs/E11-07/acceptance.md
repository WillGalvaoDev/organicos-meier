# E11-07 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Arranjo AP como na E11-01 (`acceptance.md`). O administrador com passkey e nova autenticação recente, como nos testes da E10-07. `PAGINA` é `administracao/rodadas/<pk>/estoque/`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §7, T-4 | positivo | AP-viável em `T0 + 47h` | GET `PAGINA` | o bloco "Apuração final" com "A apuração pode começar a partir de" e `T0 + 48h` em Brasília; sem o botão "Iniciar apuração". **Red esperado:** sem o bloco |
| A-2 | §7 | positivo | o A-1 em `T0 + 48h` | GET `PAGINA` | o botão "Iniciar apuração" e o aviso de que não pode ser desfeita |
| A-3 | Cenário 13, 14 | positivo | AP-viável; X pago, Y sem pagamento; `T0 + 48h` | POST `apuracao/iniciar/` | redireciona para `PAGINA` com "Apuração feita. Confira o resultado e aprove o avanço."; a página mostra X pago e Y "Cancelado (falta de pagamento)", as caixas P2 1 e 2, o valor válido 60,00, o mínimo 50,00, "Mínimo atendido", o estorno de A (caixa invalidada, 23,59, "pendente de autorização", com o link para `financeiro/devolucoes/<obrigacao>/`) e o botão "Aprovar resultado e avançar" |
| A-4 | Cenário 14 | positivo | o A-3 | POST `apuracao/aprovar/` | redireciona com "Resultado aprovado. A rodada aguarda o fornecedor."; a página mostra frete efetivo 22,00, arrecadado 7,76, déficit 14,24 e "Resultado aprovado em" com o nome do administrador; sem o botão de aprovar |
| A-5 | Cenário 15 | positivo | AP-insuficiente; X pago, Y sem pagamento | POST `apuracao/iniciar/` | a mensagem do retorno; a rodada em interesse; a página mostra "Mínimo não atendido: a rodada voltou para interesse" e o estorno integral de A (mínimo não atingido, 94,35); sem botão de aprovar |
| A-6 | Recusa | negativo | AP-viável em `T0 + 47h` | POST `apuracao/iniciar/` | 409 com a mensagem `antes_do_prazo`; nenhuma `ApuracaoFinal` |
| A-7 | Recusa | negativo | o A-3 | POST `apuracao/iniciar/` de novo | 409 com "A apuração deste ciclo já foi feita." |
| A-8 | E07-06 | negativo | AP-viável em `T0 + 48h`; a próxima consulta ao provedor falha | POST `apuracao/iniciar/` | 503 com "Não foi possível consultar o provedor; nada foi apurado. Tente de novo."; nenhuma `ApuracaoFinal` |
| A-9 | Infra 4.8 | negativo | o administrador sem nova autenticação recente | POST nas duas rotas | o redirecionamento para a nova autenticação, sem chamar o serviço |
| A-10 | Permissão | negativo | um comprador; um fornecedor | POST nas duas rotas e GET `PAGINA` | a recusa de `somente_administrador`, sem escrita |
| A-11 | Método | negativo | o administrador | GET nas rotas de ação | 405 |
| A-12 | E08-05 | positivo | o A-3 | GET `PAGINA` | no painel dos pedidos, Y com "Cancelado (falta de pagamento)" |
| A-13 | §13 comprador | positivo | o A-3 | GET `pedidos/<Y>/` como B | "Cancelado por falta de pagamento" e "Nada foi cobrado neste pedido" |
| A-14 | §13 comprador | positivo | o A-3 | GET `pedidos/<X>/` como A; GET `carrinho/` como A | no pedido: "4 un em caixa que ficou incompleta" e a frase do estorno e da fila; o estorno de 23,59 na seção de estornos; no carrinho, P2 com "pendente: 4" separado do reservado |
| A-15 | §13 comprador | positivo | o A-5 | GET `pedidos/<X>/` como A | "A rodada voltou para interesse. O valor pago será devolvido integralmente" |
| A-16 | §2, §6.2 | negativo | o A-3 | GET `pedidos/<X>/` como A; GET `pedidos/<Y>/` como A | no primeiro, nenhum nome de B nem o mínimo do fornecedor; o segundo recusado como hoje (pedido de outro comprador) |
| A-17 | Retorno | positivo | o A-5; depois um novo fechamento e a abertura de um novo pagamento | GET `PAGINA` | o bloco da apuração do ciclo 1 some; aparece o painel do pagamento novo |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-12 e A-17 | `tests/tecnicos/test_apuracao_telas.py` |
| A-13 a A-16 | `tests/tecnicos/test_pedidos_apuracao_do_comprador.py` |
