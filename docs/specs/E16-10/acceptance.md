# E16-10 — Critérios de aceitação

Agente 1 (especificador). Fatia de documentação. Os critérios são conferidos pela leitura e pela execução dos testes existentes (spec, regra 2).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 1, M-3 | positivo | `docs/specs/E08-02/acceptance.md` | ler o A-12 e o A-21 | a redação nova da regra 1, com a marca "(redação corrigida na E16-10)", e o texto anterior preservado abaixo da tabela |
| A-2 | Regra 1, M-8 | positivo | `docs/specs/E09-08/acceptance.md` | ler o A-3 | o literal `1000,00`, a marca e o texto anterior preservado |
| A-3 | Regra 2 | positivo | os testes da regra 2, sem alteração | executar `pytest` com os três arquivos | todos passam. O `review.md` registra o comando, o resultado e a leitura que confirma que cada asserção corresponde à redação nova: 409 com a mensagem para A; recusa da política para o administrador; `preco_alterado` para A e B só quando o preço vem antes; `1000,00` aceito |
| A-4 | Invariantes | positivo | o diff da fatia | `git diff --stat` contra o commit anterior | só os dois `acceptance.md`, os documentos desta fatia, o teste da regra 2-A em `tests/tecnicos/test_pedidos_abertura_tela.py` (sem mudar os testes que já existem no arquivo) e, depois da aprovação, `docs/melhorias.md` |
| A-5 | Regra 3 | positivo | `docs/melhorias.md`, depois da aprovação | ler | M-3 e M-8 em "Encerradas", com a entrega E16-10 e o commit |
| A-6 | Regra 2-A (complemento E16-R08) | negativo | o arranjo do A-12 da E08-02, com os interesses do fornecedor bloqueados, e o administrador autenticado | `POST /interesses/` com `produto=<P1>` e `quantidade=7` | `status_code == 403`; `MENSAGEM_INTERESSES` ausente do corpo; pedidos, itens e parcelas de interesse iguais por conteúdo. Teste `test_administrador_e_recusado_pela_politica_sem_a_mensagem_da_etapa`, caracterização |
| A-7 | Regra 2-A | positivo | o `review.md` da fatia | ler | a primeira execução do A-6 (caracterização), a correspondência do A-12 refeita com esse teste e com os do A-3, sem a frase "lacuna registrada, sem devolução" para o ponto resolvido, e a execução dos testes da regra 2 junto com o novo |

| Critério | Onde |
|---|---|
| A-1, A-2, A-5 | leitura dos documentos |
| A-3, A-7 | `docs/specs/E16-10/review.md` |
| A-4 | `git diff --stat` |
| A-6 | `tests/tecnicos/test_pedidos_abertura_tela.py` |
