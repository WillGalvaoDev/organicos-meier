# E14-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:** os da E14-01, com o endereço registrado. O cliente de teste entra como admin, salvo indicação.
- **Atalhos:** `REC = /administracao/rodadas/<pk>/recebimento/`, `OCO = .../ocorrencias/`, `RET = .../retiradas/`. O `acionamento` é lido do formulário da página carregada antes.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regras 6 e 7 | positivo | AE | GET `REC` | 200; as linhas P1 (pedida 11, a resolver 11) e P2 (12, 12); o formulário com o campo oculto `acionamento` (UUID); sem formulário de liberação, com "Ainda falta resolver: P1 (11 unidade); P2 (12 unidade).". **Red esperado:** a rota não existe |
| A-2 | Regra 2 | positivo | AE | dois GET `REC` | os dois acionamentos são UUIDs distintos |
| A-3 | Recebimento | positivo | AE | POST de recebimento de P1 com `quantidade=7` | 302 para `REC`, com "Recebimento registrado: 7 unidade de P1."; um registro |
| A-4 | Regra 3 | positivo | o A-3 | o mesmo POST de novo | 302 com "Este registro já tinha sido feito."; um registro |
| A-5 | Regra 3 | negativo | AE | POST de recebimento de P1 com 12 | 409 com a mensagem de `passa_do_pedido_formal`; nada gravado |
| A-6 | Regra 2 | negativo | AE | POST sem `acionamento`, com `acionamento=abc`, sem `quantidade`, com `quantidade=x` | 400 com "Recarregue a página e tente de novo." nos dois primeiros e "Preencha todos os campos." nos outros; nada gravado |
| A-7 | Regra 4 | positivo | AE com P1 por peso (incremento 0,5) | POST com `quantidade=2,5` | aceito como 2,5 |
| A-8 | Liberação | positivo | AE-recebido | GET `REC`; POST de liberação | o formulário "Liberar retirada" presente; o POST dá 302 para `RET`, com "Retirada liberada. Os compradores foram avisados."; a rodada liberada |
| A-9 | Liberação | negativo | AE-recebido sem endereço | GET `REC`; POST de liberação | sem formulário, com o link para `administracao/retirada/endereco/`; o POST dá 409 com "Registre o endereço de retirada antes de liberar." |
| A-10 | Liberação | positivo | AE-liberada | POST de liberação de novo; GET `REC` | 302 para `RET` com "A retirada desta rodada já foi liberada."; a página só para leitura, com "Retirada liberada em 05/11/2026 10:00, prazo até 12/11/2026 10:00" |
| A-11 | Regra 11 | positivo | AE | GET `OCO` | 200; os pedidos X (A) e Y (B) com os itens e os saldos 6, 4, 5, 8; o formulário com os três tipos |
| A-12 | Cenário 48, ocorrência | positivo | AE | POST de ocorrência `faltante` de 2 em X-P1 | 302 para `OCO`, com "Ocorrência registrada. Reembolso de R$ 23,59 (produtos R$ 20,00, serviço R$ 1,00, frete R$ 2,59)."; a lista com a ocorrência, a etapa "antes da liberação" e o link "Ver devolução" para `/administracao/financeiro/devolucoes/<obrigação>/` |
| A-13 | Cenário 49 | negativo | o A-12 | POST de `nao_entregue` de 5 em X-P1 | 409 com a mensagem de `passa_do_saldo_do_item` ("(4 unidade)."); nada gravado |
| A-14 | Ocorrência depois do repasse | positivo | AE com repasse total a F | POST de `faltante` de 2 em X-P1 | 302, com a segunda frase "Parte do reembolso ainda não tem cobertura: R$ 20,00. Cubra antes de autorizar a devolução." |
| A-15 | Rota | negativo | duas rodadas AE de fornecedores distintos | POST de ocorrência na rota da primeira com um item da segunda | 404; nada gravado |
| A-16 | Regra 12 | positivo | AE cancelada | GET `OCO` | 200, só para leitura, sem formulário; o POST dá 409 com a mensagem de `etapa` |
| A-17 | Regras 14 e 15 | positivo | AE-liberada; relógio em `L + 1 dia` | GET `RET`; POST de retirada de 4 em X-P1 | o cabeçalho com a liberação, o prazo e o endereço; "O descarte fica disponível a partir de 12/11/2026 10:00."; o POST dá 302 com "Retirada registrada: 4 unidade de P1."; X-P1 com saldo 2 |
| A-18 | Cenário 23, regra 16 | positivo | o A-17; relógio em `L + 8 dias` | GET `RET`; POST de descarte de 2 em X-P1 | a seção "Prazo encerrado — pendentes de decisão" com X-P1 (2), X-P2, Y-P1 e Y-P2; o POST dá 302 com "Descarte registrado: 2 unidade de P1."; o histórico com a retirada e o descarte |
| A-19 | Regra 16 | negativo | AE-liberada; relógio em `L + 1 dia` | POST de descarte direto | 409 com a mensagem de `antes_do_prazo`; nada gravado |
| A-20 | Regra 14 | negativo | AE (não liberada) | GET `RET` | 404 |
| A-21 | Regra 18 | positivo | AE; AE-liberada; AE cancelada | GET da página da rodada | os blocos com "Aguardando o fornecedor: 2 produto(s) a resolver.", "Retirada liberada; prazo até 12/11/2026 10:00." e "Rodada cancelada.", com os links da regra 18 |
| A-22 | Cenário 50, §2 | negativo | AE e AE-liberada | GET de `REC`, `OCO` e `RET` e POST de cada rota desta fatia, como o comprador A, como a conta de fornecedor de F e como anônimo | 403, 403 e login em todos; nada gravado |
| A-23 | Regra 2 | negativo | AE | GET nas cinco rotas `POST` | 405 |
| A-24 | Regra 19 | positivo | — | rodar `tests/tecnicos/test_pedidos_abertura_tela.py` | verde, sem mudar a lista de rotas permitidas |
| A-25 | Regra 3 | positivo | AE | POST de recebimento com campos extras (`linha=1`, `pedido_formal=2`) | aceito, com os campos extras ignorados |
| A-26 | E14-R01, convenção 3 | concorrência | AE-liberada; com transações reais; a retirada de 4 em X-P1 com o acionamento a1 pausada depois da auditoria, com as travas retidas | um segundo POST de `rodadas_retiradas_registrar` com a1, X-P1 e 4, confirmado esperando; depois a primeira retomada | os dois 302; uma resposta seguida com "Retirada registrada: 4 unidade de P1." e a outra com "Este registro já tinha sido feito."; um `RetiradaDeItem`; X-P1 com saldo 2. **Red esperado:** as duas com "Retirada registrada" |
| A-27 | E14-R03, regra 15-A | negativo | AE-liberada; relógio em `L + 1 dia`; X-P1 com saldo 6 | POST de retirada com X-P1 e quantidade `7` | 409 com a mensagem de `passa_do_saldo_do_item`; no formulário de retirada de X-P1, `quantidade` igual a `7`; nos formulários de retirada de X-P2, Y-P1 e Y-P2, `quantidade` vazia; o `acionamento` de cada formulário um UUID diferente do enviado; nenhum `RetiradaDeItem`. **Red esperado:** a quantidade de X-P1 vazia |
| A-28 | E14-R03, regra 15-A | negativo | AE-liberada; relógio no prazo final; X-P1 com saldo 6 | POST de descarte com X-P1 e quantidade `7` | 409 com a mensagem de `passa_do_saldo_do_item`; no formulário de descarte de X-P1, `quantidade` igual a `7` (e não `6`); nos formulários de descarte de X-P2, Y-P1 e Y-P2, a quantidade sugerida igual ao saldo de cada um (4, 5 e 8); nos formulários de retirada, `quantidade` vazia; nenhum `DescarteDeItem`. **Red esperado:** a quantidade de X-P1 igual a `6` |
| A-29 | E14-R03, regra 15-A | negativo | AE-liberada; relógio em `L + 1 dia` | POST de retirada com X-P1 e quantidade `6,5` (P1 vendido por unidade) | 409 com a mensagem de `quantidade_invalida`; no formulário de retirada de X-P1, `quantidade` igual a `6,5`, sem conversão; nenhum `RetiradaDeItem` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-23, A-25 e A-27 a A-29 | `tests/tecnicos/test_recebimento_e_retirada_telas.py` |
| A-26 | `tests/tecnicos/test_recebimento_e_retirada_telas.py`, com transações PostgreSQL reais |
| A-24 | `tests/tecnicos/test_pedidos_abertura_tela.py` (existente, sem alteração) |
