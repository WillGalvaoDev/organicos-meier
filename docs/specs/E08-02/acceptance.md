# E08-02 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05): Red com caminhos explícitos de arquivos inteiros, sem `-k`, e tabela de cobertura do Red antes do Green.

**Arranjo comum, salvo indicação:**

- relógio em 2026-11-02 13:00 UTC;
- fornecedor F com mínimo de R$ 100,00 e rodada em `fechamento_encerrado`;
- produto `P1` a R$ 10,00, sem múltiplo;
- produto `P2` a R$ 5,00, com múltiplo 6;
- comprador A com 6 unidades de `P1` e 4 de `P2`;
- comprador B com 5 de `P1` e 8 de `P2`, sendo 2 delas numa segunda parcela.

A ordem das parcelas de `P2` é: A com 4, B com 6 e B com 2. São 12 unidades e duas caixas, e o encerramento não removeu nada.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §8.1, §9 | positivo | o arranjo; frete 22,00 | `abrir_pagamento(admin, rodada, Decimal("22.00"))` | a rodada em `pagamento`; uma `AberturaDoPagamento` com `t0` 13:00, frete 22,00 e `total_produtos` 170,00; o pedido de A com produtos 80,00, serviço 4,00, frete 10,35, total 94,35; o de B com produtos 90,00, serviço 4,50, frete 11,65, total 106,15; os fretes somam 22,00; duas `SituacaoDoPedido` `aguardando_pagamento` |
| A-2 | Spec §6.3 | positivo | o A-1 | inspeciono as `ParcelaNoPedido` de `P2` | caixa 1: A com 4 e B com 2 (da primeira parcela de B); caixa 2: B com 4 (resto da primeira parcela) e B com 2 (segunda parcela); cada caixa soma 6; em `P1`, `caixa` nula |
| A-3 | Spec §7.1, Infra 4.12 | positivo | o A-1 | inspeciono os `ItemDoPedido` | nome, unidade, incremento, múltiplo, preço, quantidade e subtotal iguais aos do produto às 13:00; A em `P2`: 4 × 5,00 = 20,00 |
| A-4 | Herdado da E05 | positivo | o arranjo, com uma parcela de A em `P1` que tem 6 reservadas e 3 pendentes (atendida em parte pela fila) | a abertura; depois, A remove 2 pendentes pela rota de remoção de pendentes (E05-03) | o pedido de A tem 6 de `P1`; a parcela ficou `pendente`, com a mesma `sequencia`, reserva 0 e pendente 3; a remoção é aceita e deixa 1 pendente; o pedido não muda; o carrinho mostra 1 pendente e nada reservado em `P1` |
| A-5 | Herdado da E05 | positivo | o arranjo, sem pendências | a abertura | todas as parcelas congeladas ficam `em_pedido`, com a reserva inalterada |
| A-6 | Herdado da E06, Spec §8.1 | positivo | antes da abertura, B é suspenso, e `P2` fica com 4 unidades (só A) | a abertura | as 4 unidades de A em `P2` são removidas (não completam caixa), com o aviso "Na abertura do pagamento da rodada de F, 4 unidade de P2 não completaram caixa…" e a chave `excedentes_removidos:abertura:<ciclo>:<P2>:<A>`; como 60,00 < 100,00, a rodada volta para `interesse`; nenhum pedido; o aviso `retorno_para_interesse` com o texto da abertura para A; a auditoria com `resultado` `retorno_para_interesse`; `etapa_final` `interesse` |
| A-7 | Spec §5.1, herdado da E06 | positivo | antes da abertura, o preço de `P1` cai para R$ 1,00 | a abertura | valor elegível 71,00 < 100,00; a rodada volta para `interesse`; nenhum pedido |
| A-8 | Spec §5.1 | positivo | antes da abertura, o preço de `P1` sobe para R$ 12,00 | a abertura | os itens de `P1` com 12,00; `total_produtos` 192,00 |
| A-9 | Spec da fatia | negativo | rodada em `interesse`, `fechamento` ou `pagamento` | a abertura | `TransicaoRecusada` com a mensagem "Só uma rodada com o fechamento encerrado pode abrir o pagamento."; nada gravado |
| A-10 | Spec da fatia | negativo | — | `abrir_pagamento` com comprador ou `None` como autor; com frete `-1`, `22.001`, `float` 22.0 | `PermissionDenied` nos dois primeiros; `ValueError` nos outros; nada gravado; a rodada continua `fechamento_encerrado` |
| A-11 | Infra 4.9, T-17 | negativo | o A-1 | `save()`, `delete()`, `update()` em lote e SQL direto (`UPDATE` e `DELETE`) em `AberturaDoPagamento`, `Pedido`, `ItemDoPedido` e `ParcelaNoPedido` | todos recusados (`RegistroImutavel` ou erro do banco); pelo ORM, um log `warning` "Tentativa de alterar pedido congelado: <modelo> <id>"; nada mudou |
| A-12 | Cenário 47, T-17 | negativo | o A-1 | varro as rotas (`rotas_sem_politica` e a lista de `config/urls.py`); A e o administrador tentam `POST /interesses/` para `P1`, aumentando e reduzindo | nenhuma rota de edição de pedido, item, `T0` ou frete; os `POST` de interesse recebem 409 com a mensagem da etapa; os pedidos não mudam |
| A-13 | Cenário 11 | positivo | o A-1 | um comprador C tenta adicionar `P1`; o administrador muda o preço de `P1` para R$ 20,00 e o de `P2` para R$ 1,00 | C é recusado; os itens e valores dos pedidos não mudam; nenhum aviso `preco_alterado` para A nem para B |
| A-14 | Cenário 65 | positivo | um produto por peso, a R$ 12,99/kg, com incremento 0,05 e 0,35 kg de A | a abertura; depois, altero o preço | o item fica com 0,350 kg e subtotal 4,55, e não muda depois |
| A-15 | Spec §12, herdado da E04 | positivo | o A-1 | inspeciono as notificações | uma `pagamento_aberto` por comprador, com o título "Pagamento aberto: F", os quatro valores do pedido e "Pague até 03/11/2026 às 10:00 (horário de Brasília). Esse prazo de 24 horas não é prorrogado.", o link `/pedidos/<id>/` e a chave `pagamento_aberto:<pedido>:<comprador>` |
| A-16 | Cenário 24, herdado da E04 | positivo | A com WhatsApp consentido; WhatsApp simulado com `falhar_sempre()` | a abertura; depois, `processar_envios()` até esgotar as tentativas; A abre a central | a abertura e os pedidos continuam gravados; WhatsApp `falhou` com três tentativas; e-mail `enviado`; a central mostra o aviso |
| A-17 | Spec da fatia | positivo | o A-1 | inspeciono a auditoria | uma entrada `rodada.abrir_pagamento` do administrador, com `t0` `"2026-11-02T13:00:00+00:00"`, frete `"22.00"`, `total_produtos` `"170.00"`, `pedidos` 2 e `resultado` `pagamento` |
| A-18 | Tela | positivo | rodada em `fechamento_encerrado` | o administrador abre a página de estoque; envia o formulário com "22,00"; depois com "abc" e com "22,001"; depois abre a página de novo | o bloco tem "Frete total (R$)" e "Abrir pagamento"; o envio válido redireciona com "Pagamento aberto. Prazo: 03/11/2026 às 10:00 (horário de Brasília)."; os inválidos recebem 400 com a mensagem do campo e nada gravado; em `pagamento`, o bloco mostra o `T0`, o fim do prazo e o fim da margem, sem o formulário |
| A-19 | E02-10 | negativo | — | comprador, fornecedor e anônimo fazem `POST` na rota; o administrador faz `GET` | recusados pela política (redirecionamento ou 403); 405 no `GET`; nada gravado; a varredura acusa a rota com a política `administrador` |
| A-20 | Spec da fatia | concorrência | o arranjo | duas threads abrem o pagamento ao mesmo tempo, com a primeira segurando a transação até a segunda aparecer esperando (prazo de espera com falha por asserção) | uma abertura, dois pedidos; a segunda recebe `TransicaoRecusada` |
| A-21 | Spec da fatia | concorrência | o arranjo | uma thread abre o pagamento e outra altera o preço de `P1` para R$ 11,00; nas duas ordens, com a primeira segurando a trava do produto até a segunda aparecer esperando | quando o preço vem antes, os itens de `P1` têm 11,00; quando vem depois, têm 10,00, e o preço do produto é 11,00; nos dois casos, nenhum `preco_alterado` para A nem para B |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-11, A-13 a A-17 | `tests/tecnicos/test_pedidos_abertura.py` |
| A-12, A-18, A-19 | `tests/tecnicos/test_pedidos_abertura_tela.py` e `tests/tecnicos/test_permissoes_politica_rotas.py` (teste existente) |
| A-11 | também marcado `acceptance`, com o comentário `T-17` |
| A-12 | também marcado `acceptance`, com o comentário `cenário 47` |
| A-13 | também marcado `acceptance`, com o comentário `cenário 11` |
| A-14 | também marcado `acceptance`, com o comentário `cenário 65` |
| A-16 | `tests/tecnicos/test_notificacoes_falha_isolada.py` ou arquivo próprio, marcado `acceptance`, com o comentário `cenário 24 (abertura real)` |
| A-20, A-21 | `tests/tecnicos/test_pedidos_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
