# E04-01 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As notificações dos testes são criadas pela `NotificacaoFactory` ou por `criar_notificacao`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §12, decisão técnica | unitário | — | comparo `CANAIS_POR_EVENTO` e `DESTINATARIO_POR_EVENTO` com a matriz da spec, transcrita no teste | igualdade exata nos 13 eventos; `site` presente em todos; `whatsapp` só em `fechamento_iniciado`, `pagamento_aberto`, `retirada_liberada`, `rodada_cancelada` e `comunicado`; `email` ausente só em `preco_alterado` |
| A-2 | Spec da fatia | positivo | um comprador | `criar_notificacao` com `estorno`, título, corpo, link `/historico/` e chave `"t:1"` | uma notificação gravada com esses valores, `criada_em` igual ao `agora()` congelado e `lida_em` nulo |
| A-3 | Spec da fatia | negativo | um comprador e o administrador | `criar_notificacao` com: título vazio; título com 151 caracteres; corpo com 2001; link `https://x.com`; link `//x.com`; link `x/`; chave vazia; evento `"inexistente"`; `falha_no_pedido_formal` para o comprador; `estorno` para o administrador | `NotificacaoInvalida` em todos, com o campo correto; nada gravado |
| A-4 | Infra 5 | negativo | uma notificação lida e outra não lida | por SQL direto: `DELETE`; `UPDATE` do título; `UPDATE` de `lida_em` para nulo na lida; `UPDATE` de `lida_em` para outro instante na lida | o banco recusa todos; pelo ORM, `save()` com título alterado e `delete()` levantam `RegistroImutavel` |
| A-5 | Spec da fatia | positivo | a notificação não lida do A-4 | por SQL direto, `UPDATE` só de `lida_em` de nulo para um instante | aceito |
| A-6 | Spec §2, §12 | positivo | comprador `C1` com 35 notificações (uma com corpo `<b>x</b>` e quebra de linha) e comprador `C2` com 2 | `C1` abre `/notificacoes/` e `/notificacoes/?pagina=2` | página 1 com as 30 mais recentes em ordem decrescente; página 2 com as 5 restantes; nenhuma de `C2`; o corpo aparece escapado, com `<br>`; data no formato `dd/mm/aaaa HH:MM` no fuso da operação; "Nova" nas não lidas |
| A-7 | Spec da fatia | positivo | uma conta sem notificações; `?pagina=99` para `C1` | abro a central | "Você não tem notificações."; a página 99 mostra a última página |
| A-8 | Spec §2 | negativo | uma notificação de `C2` e um id inexistente | `C1` envia `POST /notificacoes/<id>/lida/` | 404 nos dois, com o mesmo corpo; `lida_em` de `C2` continua nulo |
| A-9 | Spec da fatia | positivo | uma notificação não lida de `C1` | `C1` marca como lida duas vezes, com instantes diferentes | `lida_em` igual ao instante da primeira; as duas respostas redirecionam para `/notificacoes/`; com `HX-Request: true`, 200 com o fragmento do item sem "Nova" |
| A-10 | Spec da fatia | positivo | `C1` com 3 não lidas e `C2` com 2 não lidas | `C1` envia `POST /notificacoes/lidas/` | as 3 de `C1` lidas; as de `C2` não lidas; redirecionamento para `/notificacoes/` |
| A-11 | Spec da fatia | positivo | `C1` com 3 não lidas; um visitante anônimo | abro `/inicio/` como `C1` e como anônimo; conto as consultas do processador | "Notificações (3)" para `C1`; depois de marcar todas, "Notificações" sem número; para o anônimo, nenhum link e nenhuma consulta do processador; para `C1`, uma consulta do processador |
| A-12 | E02-10 | positivo e negativo | um comprador suspenso, uma conta de fornecedor, o administrador (com passkey) e um anônimo | abro a central e marco uma notificação própria | 200 e redirecionamento para os três autenticados; o anônimo é redirecionado para `/entrar/`; `GET` em `/notificacoes/<id>/lida/` responde 405 |
| A-13 | Spec da fatia | concorrência | uma notificação não lida | duas marcações em threads, a primeira segurando a linha até ver a segunda esperando por trava (`pg_stat_activity`) | uma única gravação; `lida_em` igual ao da primeira; nenhuma exceção |
| A-14 | E02-10 | positivo | as rotas desta fatia | rodo a varredura de políticas | política `autenticada` declarada nas três |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 | `tests/tecnicos/test_notificacoes_eventos.py` |
| A-2 a A-5 | `tests/tecnicos/test_notificacoes_modelo.py` |
| A-6 a A-12 | `tests/tecnicos/test_notificacoes_central.py` |
| A-13 | `tests/tecnicos/test_notificacoes_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
| A-14 | coberto pelo teste existente `tests/tecnicos/test_permissoes_politica_rotas.py` |
