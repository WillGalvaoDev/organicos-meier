# E06-07 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As requisições usam o cliente HTTP do Django. Salvo indicação, o fornecedor `F` ("Sítio Boa Terra") tem mínimo R$ 100,00 e rodada em `interesse` com `P` (R$ 10,00, sem limite), e o relógio está em 2026-11-02 13:30 UTC.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §13 | positivo | A com 10 reservados | o administrador abre `/administracao/rodadas/<id>/estoque/` | o botão "Iniciar fechamento" com o `action` da rota; o texto "O prazo será de 24 horas a partir do início." |
| A-2 | Spec §13 | negativo | A com 9 reservados | o administrador abre a página | "O fechamento pode ser iniciado quando o mínimo elegível for atingido."; nenhum botão "Iniciar fechamento" |
| A-3 | Spec da fatia | positivo | A com 10 | `POST /administracao/rodadas/<id>/fechamento/iniciar/` | 302 para a página de estoque; "Fechamento iniciado. Prazo: 03/11/2026 às 10:30 (horário de Brasília)." na página seguinte; a rodada em `fechamento` |
| A-4 | Spec da fatia | negativo | A com 9; noutro caso, a rodada já em `fechamento` | o mesmo `POST` | 409 com "O fechamento só pode começar com o mínimo elegível atingido." e, no segundo caso, "O fechamento só pode começar com a rodada em interesse." no topo; nenhum ciclo novo |
| A-5 | Spec da fatia | positivo | o fechamento iniciado no A-3 | o administrador abre a página | "Prazo do fechamento: 03/11/2026 10:30 (horário de Brasília)"; o formulário "Prorrogar fechamento" com `termino` igual a `2026-11-03T10:30`; o histórico com a linha "Início" |
| A-6 | Spec da fatia | positivo | o estado do A-5 | `POST .../fechamento/prorrogar/` com `termino=2026-11-04T01:30` | 302; "Prazo do fechamento prorrogado para 04/11/2026 às 01:30 (horário de Brasília)."; `prazo_do_fechamento` igual a 2026-11-04 04:30 UTC; o histórico com "Início" e "Prorrogação" |
| A-7 | Spec da fatia | negativo | o estado do A-5 | `POST .../prorrogar/` com `termino` vazio, `abc` e `"><b>x</b>`; depois com `2026-11-03T09:00` | 200 com "Informe a data e a hora do novo prazo." nos três primeiros, com o texto escapado e sem gravar; 409 com "O novo prazo precisa ser posterior ao prazo atual, 03/11/2026 às 10:30." no último |
| A-8 | Spec da fatia | negativo | o estado do A-5; o relógio em 2026-11-03 13:31 UTC, sem a tarefa rodar | o administrador abre a página; depois faz `POST .../prorrogar/` com `termino=2026-11-05T10:00` | a página mostra "Prazo do fechamento encerrado em 03/11/2026 10:30. O encerramento será processado automaticamente." e nenhum formulário; o `POST` responde 409 com a mensagem de prazo encerrado |
| A-9 | Spec da fatia | positivo | a rodada em `fechamento_encerrado` pelo serviço da E06-05, com o mínimo atingido | o administrador abre a página e o detalhe do fornecedor | "Fechamento encerrado em 03/11/2026 10:30. Aguardando a autorização do pagamento."; no detalhe, "Prazo do fechamento: 03/11/2026 10:30" e "Prazo encerrado." |
| A-10 | Spec §13, §5 | positivo | o estado do A-5; A comprador | A abre `/carrinho/` e `/catalogo/<F>/` | "Prazo do fechamento: 03/11/2026 às 10:30 (horário de Brasília)" nas duas páginas; os formulários de quantidade presentes; nenhum "100,00" |
| A-11 | E06-03 | negativo | o estado do A-8 | A abre `/carrinho/` e `/catalogo/<F>/` | "Prazo do fechamento encerrado em 03/11/2026 às 10:30." nas duas; nenhum formulário de quantidade para `P` |
| A-12 | E02-10, T-25 | negativo | um comprador, uma conta de fornecedor e um anônimo | `POST` nas duas rotas; `GET` nas duas rotas como administrador | comprador e fornecedor: recusa da política; anônimo: redirecionamento para `/entrar/`; `GET`: 405; nada gravado; a varredura de políticas encontra `somente_administrador` nas duas |
| A-13 | E05-05 A-16 | positivo | carrinho de A com 3 fornecedores em `fechamento`, com 1 e com 10 produtos | conto as consultas de `GET /carrinho/` | o mesmo teto com 1 e com 10 produtos; o acréscimo em relação ao teto da E05-05 é no máximo uma constante por fornecedor |
| A-14 | Spec da fatia | negativo | uma rodada inexistente | `POST` nas duas rotas como administrador | 404 |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-9, A-14 | `tests/tecnicos/test_rodadas_fechamento_telas.py` |
| A-10, A-11, A-13 | `tests/tecnicos/test_interesses_carrinho.py` (acréscimos) |
| A-12 | `tests/tecnicos/test_permissoes_politica_rotas.py` (teste existente), mais o 405 e as recusas em `test_rodadas_fechamento_telas.py` |
