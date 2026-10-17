# E04-06 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As telas do administrador usam a passkey simulada da E02-03. O simulador de WhatsApp é reiniciado pela fixture da E04-04.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §12 | positivo | compradores `A` (ativa, com consentimento de WhatsApp), `B` (ativa, sem consentimento), `S` (suspensa) e `R` (removida); uma conta de fornecedor `F`; o administrador | `publicar_comunicado(admin, titulo=" Feira ", mensagem="Sábado\nàs 9h", token=t)` | devolve `(c, True)`; `c.titulo="Feira"`, `c.mensagem="Sábado\nàs 9h"`, `c.destinatarios=3`; uma notificação `comunicado` para `A`, `B` e `S`, com link `/comunicados/`; nenhuma para `R`, `F` ou o administrador; três envios de e-mail e um de WhatsApp (só `A`); auditoria `comunicado.publicar` com `{"comunicado": c.id, "destinatarios": 3}` |
| A-2 | Spec da fatia | positivo | o comunicado do A-1 | `publicar_comunicado` com o mesmo `token` e, noutro teste, com o mesmo token e outro texto | devolve `(c, False)`; nenhuma notificação, envio ou auditoria nova; um único comunicado |
| A-3 | Spec da fatia | concorrência | os compradores do A-1 | duas threads publicam com o mesmo token; a primeira só confirma depois de ver a segunda esperando por trava (`pg_stat_activity`) | um comunicado; três notificações; a segunda thread recebe `(c, False)` sem exceção |
| A-4 | Spec da fatia | negativo | o administrador | título vazio, título com 151 caracteres, mensagem só com espaços e mensagem com 2001 caracteres | `ValidationError` no campo certo; nada gravado |
| A-5 | Spec §2 | negativo | um comprador e uma conta de fornecedor | chamo `publicar_comunicado` com cada um | `PermissionDenied`; nada gravado |
| A-6 | Spec §13 | positivo | o administrador com passkey; três compradores elegíveis | `GET /administracao/comunicados/`, depois `POST` com o token do formulário, depois o mesmo `POST` de novo | o `GET` mostra "Será enviado para 3 compradores." e um token oculto; o primeiro `POST` redireciona com "Comunicado publicado para 3 compradores."; o segundo, com "Este comunicado já tinha sido publicado."; um único comunicado |
| A-7 | Spec da fatia | negativo | o administrador | `POST` com título vazio e mensagem "texto" | 200; erro no campo título; "texto" de volta no formulário; nada gravado |
| A-8 | Spec §13, §14 | positivo | o comunicado do A-1, com o e-mail de `B` falhando três vezes e os outros enviados | abro o histórico | linha com data, título, autor, "3" destinatários e as contagens "e-mail: 2 aceitos, 1 com falha" e "WhatsApp: 1 aceito" |
| A-9 | Spec §13 | positivo | dois comunicados, um com mensagem `<b>x</b>` | o comprador `S` (suspenso) abre `/comunicados/` | 200; os dois, do mais recente para o mais antigo, com a mensagem escapada e as âncoras `c<id>`; sem autor e sem número de destinatários |
| A-10 | Spec da fatia | positivo | um comprador cadastrado depois do comunicado do A-1 | abre `/comunicados/` e `/notificacoes/` | o comunicado aparece em `/comunicados/`; nenhuma notificação dele na central |
| A-11 | E02-10 | negativo | uma conta de fornecedor, o administrador e um anônimo | abrem `/comunicados/` | 403, 403 e redirecionamento para `/entrar/` |
| A-12 | Spec da fatia | positivo | 1 e, noutro teste, 20 comunicados no histórico | conto as consultas do `GET /administracao/comunicados/` | o mesmo teto nos dois casos |
| A-13 | Infra 5 | negativo | um comunicado | `UPDATE` e `DELETE` pelo ORM e por SQL direto | `RegistroImutavel` no ORM; o banco recusa por SQL |
| A-14 | Spec §12 | positivo | nenhum comprador cadastrado | publico | `destinatarios=0`; o comunicado aparece em `/comunicados/` |
| A-15 | E02-10 | positivo | as rotas desta fatia | rodo a varredura de políticas | `administrador` na tela administrativa e `comprador` em `/comunicados/` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1, A-2, A-4, A-5, A-13, A-14 | `tests/tecnicos/test_comunicados_servico.py` |
| A-3 | `tests/tecnicos/test_notificacoes_concorrencia.py` (marcador `concorrencia`) |
| A-6 a A-12 | `tests/tecnicos/test_comunicados_telas.py` |
| A-15 | coberto pelo teste existente `tests/tecnicos/test_permissoes_politica_rotas.py` |
