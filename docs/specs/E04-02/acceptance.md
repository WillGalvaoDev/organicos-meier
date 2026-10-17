# E04-02 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As contas são criadas pelas fábricas da E02. O relógio é congelado com `time_machine`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §12 | positivo | um comprador `ana@x.com`, `ORIGEM_PUBLICA="https://om.test"` | dentro de `transaction.atomic()`, `emitir_evento(estorno, conta, titulo="Estorno", corpo="R$ 10,00", link="/historico/", chave="estorno:1:7")` | uma notificação; um `Envio` `email`, `pendente`, com `destino="ana@x.com"`, `assunto="Orgânicos Méier: Estorno"`, `corpo` igual a `"R$ 10,00\n\nAcesse: https://om.test/historico/\n\n"` mais o rodapé, `tentativas=0`, `proxima_tentativa_em == criado_em` e `chave="estorno:1:7:email"` |
| A-2 | Spec da fatia | positivo | um comprador | `emitir_evento(preco_alterado, ...)` | uma notificação e nenhum `Envio` |
| A-3 | Spec da fatia | negativo | um comprador | chamo `emitir_evento` fora de transação | `TransactionManagementError`; nada gravado |
| A-4 | Spec da fatia | negativo | um comprador | `emitir_evento` dentro de uma transação que depois levanta uma exceção | nenhuma notificação e nenhum envio gravados |
| A-5 | Cenário 17 | positivo | a emissão do A-1 já confirmada | repito a mesma chamada, com o mesmo conteúdo, em nova transação | devolve a mesma notificação; continua uma notificação e um envio |
| A-6 | Spec da fatia | negativo | a emissão do A-1 já confirmada | repito a chave `"estorno:1:7"` com outro corpo e, noutro teste, com outra conta | `ChaveDeEventoReutilizada`; nada novo gravado |
| A-7 | Spec da fatia | concorrência | um comprador | duas threads chamam `emitir_evento` com a mesma chave; a primeira só confirma depois de ver a segunda esperando por trava (`pg_stat_activity`) | uma notificação e um envio; a segunda devolve a notificação da primeira, sem exceção |
| A-8 | Spec da fatia | negativo | um comprador e o administrador | `emitir_evento(falha_no_pedido_formal, comprador, ...)` e `emitir_evento(estorno, administrador, ...)` | `NotificacaoInvalida`; nada gravado |
| A-9 | Spec da fatia | positivo | compradores `A`, `B` e `C`, com `A` repetido na lista | `emitir_evento_para_varios(comunicado, [A, B, A, C], ..., chave_base="comunicado:5")` | devolve 3; chaves `comunicado:5:<pk>`; três envios de e-mail; repetir a chamada devolve 0 e não grava nada |
| A-10 | Spec da fatia | positivo | listas de 1 e de 30 compradores | conto as consultas de `emitir_evento_para_varios` (`django_assert_max_num_queries`) | o mesmo teto nos dois casos |
| A-11 | Spec da fatia | negativo | uma lista com dois compradores e o administrador, para `comunicado` | `emitir_evento_para_varios` | `NotificacaoInvalida`; nada gravado para nenhum dos três |
| A-12 | Infra 5 | negativo | um envio pendente e outro `enviado` | por SQL direto: `DELETE`; `UPDATE` de `corpo`, `destino` e `chave` no pendente; `UPDATE` de `situacao` no `enviado`; `tentativas = 4`; `situacao='enviado'` com `concluido_em` nulo | o banco recusa todos |
| A-13 | Spec da fatia | positivo | um envio pendente | por SQL direto, `UPDATE` de `tentativas`, `proxima_tentativa_em`, `situacao='falhou'` e `concluido_em` juntos | aceito |
| A-14 | Infra 5 | negativo | `caplog` em nível `DEBUG` | emito para `ana@x.com`, com título "Estorno" e corpo "R$ 10,00", e forço uma `NotificacaoInvalida` noutra emissão | nenhum registro de log contém `ana@x.com`, "Estorno" nem "R$ 10,00" |
| A-15 | E04-R01 | negativo | um comprador e um segundo comprador | dentro de `transaction.atomic()`, `emitir_evento` e `emitir_evento_para_varios` (com os dois compradores) com cada link recusado da lista de exemplos da correção E04-R01 (E04-01) | `NotificacaoInvalida` com `campo == "link"` em todos; nenhuma notificação e nenhum envio gravados; com o link `"/catalogo/1/?q=abc#x"`, as duas funções gravam normalmente |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-6, A-8 a A-11, A-14 | `tests/tecnicos/test_notificacoes_emissao.py` |
| A-5 | também marcado `acceptance`, com o comentário `cenário 17` |
| A-7 | `tests/tecnicos/test_notificacoes_concorrencia.py` (marcador `concorrencia`) |
| A-12, A-13 | `tests/tecnicos/test_notificacoes_modelo.py` |
| A-15 | `tests/tecnicos/test_notificacoes_link_interno.py` (o mesmo arquivo dos critérios A-15 a A-17 da E04-01) |
