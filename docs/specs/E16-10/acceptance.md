# E16-10 — Critérios de aceitação

Agente 1 (especificador). Fatia de documentação. Os critérios são conferidos pela leitura e pela execução dos testes existentes (spec, regra 2).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 1, M-3 | positivo | `docs/specs/E08-02/acceptance.md` | ler o A-12 e o A-21 | a redação nova da regra 1, com a marca "(redação corrigida na E16-10)", e o texto anterior preservado abaixo da tabela |
| A-2 | Regra 1, M-8 | positivo | `docs/specs/E09-08/acceptance.md` | ler o A-3 | o literal `1000,00`, a marca e o texto anterior preservado |
| A-3 | Regra 2 | positivo | os testes da regra 2, sem alteração | executar `pytest` com os três arquivos | todos passam. O `review.md` registra o comando, o resultado e a leitura que confirma que cada asserção corresponde à redação nova: 409 com a mensagem para A; recusa da política para o administrador; `preco_alterado` para A e B só quando o preço vem antes; `1000,00` aceito |
| A-4 | Invariantes | positivo | o diff da fatia | `git diff --stat` contra o commit anterior | só os dois `acceptance.md`, os documentos desta fatia e, depois da aprovação, `docs/melhorias.md` |
| A-5 | Regra 3 | positivo | `docs/melhorias.md`, depois da aprovação | ler | M-3 e M-8 em "Encerradas", com a entrega E16-10 e o commit |
