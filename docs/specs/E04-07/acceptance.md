# E04-07 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As telas usam o administrador autenticado com a passkey simulada da E02-03. Os envios são criados pela `EnvioFactory` e por `TentativaDeEnvio`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §12, §13 | positivo | 55 envios: de e-mail `enviado`, `falhou` e `pendente`; de WhatsApp `cancelado` e `enviado`; e um `acesso:convite` | abro `/administracao/envios/` e `?pagina=2` | 50 na primeira página e 5 na segunda, do mais recente para o mais antigo; colunas com rótulos legíveis; "Aceito pelo serviço" nos enviados; no convite, o e-mail de destino como destinatário; nas outras linhas, o nome da conta |
| A-2 | Spec da fatia | positivo | os envios do A-1 | filtro `situacao=falhou`; `canal=whatsapp`; `tipo=acesso:convite`; `situacao=falhou&canal=email`; `situacao=xyz` | só os envios correspondentes em cada caso; com `situacao=xyz`, a lista sem filtro e sem erro |
| A-3 | Spec da fatia | positivo | um envio de e-mail `falhou` com três tentativas, ligado a uma notificação lida | abro o detalhe | assunto, corpo, título e evento da notificação, "lida", e as três tentativas em ordem, com início, fim, resultado e `ConnectionError` |
| A-4 | E04-05 | positivo | um envio `acesso:link_de_acesso` | abro o detalhe | o corpo aparece como "(não armazenado: contém link de acesso)" |
| A-5 | Spec da fatia | positivo | 2 envios `falhou` | abro a página inicial da área administrativa; depois, sem envios com falha | "Envios com falha: 2", com link para `/administracao/envios/?situacao=falhou`; sem falhas, o indicador não aparece |
| A-6 | Spec da fatia | positivo | 1 e, noutro teste, 50 envios de tipos e canais variados | conto as consultas da lista (`django_assert_max_num_queries`) | o mesmo teto nos dois casos |
| A-7 | E02-03, E02-10 | negativo | um comprador, uma conta de fornecedor e um anônimo | abrem a lista e o detalhe | 403, 403 e redirecionamento para `/entrar/` |
| A-8 | Spec da fatia | negativo | o administrador | `POST` na lista e no detalhe; detalhe com id inexistente | 405 nos `POST`; 404 no id inexistente |
| A-9 | Spec da fatia | positivo | nenhum envio; depois, envios sem nenhum correspondente ao filtro | abro a lista | "Nenhum envio registrado."; "Nenhum envio com estes filtros.", com o filtro mantido no formulário |
| A-10 | E02-10 | positivo | as rotas desta fatia | rodo a varredura de políticas | política `administrador` declarada nas duas |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-9 | `tests/tecnicos/test_notificacoes_administracao.py` |
| A-10 | coberto pelo teste existente `tests/tecnicos/test_permissoes_politica_rotas.py` |
