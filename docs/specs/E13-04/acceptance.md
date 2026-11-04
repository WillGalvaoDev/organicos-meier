# E13-04 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:** AF, AF-sucesso, AF-falhas e AF-meio (E13-01 e E13-03).
- **Páginas e rotas:** `PAGINA` é `administracao/rodadas/<pk>/pedido-formal/`; `ROTA` é `administracao/rodadas/<pk>/pedido-formal/reenviar/`.
- **Acesso:** o administrador entra como nos testes da E11-07; o cliente HTTP é o do Django.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §13 | positivo | AF-sucesso | GET `PAGINA` | 200; "Pedido formal nº <pk>"; a tabela com P1 (11 unidade, —, R$ 10,00, R$ 110,00) e P2 (12 unidade, 2, R$ 5,00, R$ 60,00) e o total R$ 170,00; o assunto e o corpo gravados; "Envio automático concluído: aceito pelo serviço de e-mail."; a nota da L-13; a tentativa 1 "Automática 1/3", "Aceito pelo serviço de e-mail", destino `pedidos@f.example`; o formulário "Reenviar pedido" com um campo oculto `token`. **Red esperado:** 404 (rota inexistente) |
| A-2 | §13, cenário 69 | positivo | AF-falhas | GET `PAGINA` | "Envio automático concluído sem sucesso depois de 3 tentativas."; as três tentativas com "Falha" e `ConnectionError`; o formulário presente |
| A-3 | Cenário 94, R-7 | negativo | AF-meio | GET `PAGINA` | "Envio automático em andamento: tentativa 2 de 3 prevista para <data hora>."; sem formulário de reenvio; a mensagem "O envio automático ainda está em andamento; o reenvio fica disponível quando ele terminar." |
| A-4 | Herdado E12 | negativo | AF; a rodada cancelada e a tarefa executada (envio `interrompido`) | GET `PAGINA` | "Envio interrompido: a rodada foi cancelada."; sem formulário; a mensagem de `rodada_cancelada` |
| A-5 | Token | positivo | AF-sucesso | GET `PAGINA` duas vezes | os dois tokens são UUIDs válidos e diferentes |
| A-6 | Cenário 92 | positivo | AF-sucesso | POST `ROTA` com o token da página | redireciona para `PAGINA` com "Reenvio registrado: aceito pelo serviço de e-mail."; a página mostra a tentativa 2 "Manual" com o nome do administrador |
| A-7 | Cenário 70, T-29 | positivo | AF-falhas | POST `ROTA` duas vezes com o mesmo token; depois GET `PAGINA` e POST com o novo token | o primeiro POST registra a tentativa; o segundo redireciona com "Este reenvio já tinha sido registrado." e nenhum e-mail novo; o terceiro registra outra tentativa; ao todo, dois e-mails, idênticos ao gravado |
| A-8 | Cenário 93 | positivo | AF-falhas; `BackendQueFalha` | POST `ROTA` | redireciona com "Reenvio registrado: o serviço de e-mail recusou (ConnectionError)."; a página continua com o formulário |
| A-9 | Cenário 94, T-54 | negativo | AF-meio | POST `ROTA` com um token válido | 409 com a mensagem de `ciclo_em_andamento`; nenhuma tentativa |
| A-10 | Infra 4.2 | negativo | AF-falhas; a próxima busca por referência falha no simulador | POST `ROTA` | 503 com "Não foi possível consultar o provedor; o pedido não foi reenviado. Tente de novo."; nenhuma tentativa |
| A-11 | Regra 9 | negativo | AF-falhas | POST `ROTA` sem `token`; depois com `token=abc` | 400 com "Recarregue a página e tente de novo." nos dois; nenhuma consulta e nenhuma tentativa |
| A-12 | Regra 9 | positivo | AF-falhas | POST `ROTA` com o token e campos extras (`assunto=x`, `corpo=y`, `quantidade=1`) | aceito; o e-mail enviado com o assunto e o corpo gravados |
| A-13 | Acesso | negativo | AF-falhas | GET `PAGINA` e POST `ROTA` como comprador e como a conta do fornecedor F | 403 nos quatro; nenhuma tentativa |
| A-14 | Método | negativo | AF-falhas | GET `ROTA` | 405 |
| A-15 | Regra 1 | negativo | uma rodada em `pagamento`, sem pedido formal | GET `PAGINA` e POST `ROTA` como administrador | 404 nos dois |
| A-16 | Regra 11 | positivo | AF-sucesso | GET a página da rodada | o bloco "Pedido formal" com o nº, R$ 170,00, a situação e o link para `PAGINA` |
| A-17 | §12 | positivo | AF-falhas | seguir o link da notificação `falha_no_pedido_formal` | 200 em `PAGINA`, com o formulário de reenvio |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-17 | `tests/tecnicos/test_pedido_formal_telas.py` |
