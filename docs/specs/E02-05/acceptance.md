# E02-05 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Os convites são criados pelo serviço da E02-04 ou por fábrica, com o token conhecido pelo teste. `T` é o instante de emissão, controlado pela fixture `relogio`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §3.1 | positivo | um convite de comprador pendente para `bia@x.com` | abro `GET /convite/<token>/` | 200, com o e-mail só para leitura, a finalidade e os campos nome, senha e confirmação |
| A-2 | Spec §3.1, §3.2 | positivo | o mesmo convite | envio `nome="Bia"` e uma senha válida | uma conta comprador ativa com `bia@x.com`; `EmailAddress` verificado e primário; convite com `consumido_em` e `conta_criada`; sessão autenticada e redirecionamento para `/inicio/` |
| A-3 | Spec §3.1, cenário 1 | negativo | o convite do A-2 já consumido | abro o link e envio o formulário de novo | 410 com a mensagem única nos dois; uma única conta continua existindo |
| A-4 | Spec §3.1, cenário 1, Infra 4.3 | fronteira | um convite emitido em `T` | envio o cadastro em `T + 24h − 1 ms`, `T + 24h` e `T + 24h + 1 ms` (um convite novo para cada instante) | conta criada no primeiro; 410 e nada criado nos outros dois |
| A-5 | Spec §3.1 | negativo | um convite válido em `T + 23h` no `GET` | envio o `POST` em `T + 24h` | 410; nada criado |
| A-6 | Cenário 1 ("outro e-mail"), 62 | negativo | um convite de comprador para `bia@x.com` | envio o `POST` com campos extras `email=outra@x.com`, `papel=fornecedor` e `fornecedor=<id>` | conta criada com `bia@x.com`, papel comprador e sem fornecedor |
| A-7 | Spec §3.1, cenário 1 | negativo | um convite de fornecedor vinculado a `F1` e outro fornecedor `F2` | envio o `POST` com `fornecedor=<id de F2>` | conta de fornecedor vinculada a `F1` |
| A-8 | Spec §3.1 | negativo | um convite pendente para `ana@x.com` e, depois da emissão, `EmailBanido` de `ana@x.com` | abro o link e envio o cadastro | 410 nos dois; nada criado; convite não consumido |
| A-9 | Spec §3.1, cenário 80 | negativo | um convite pendente para `ana@x.com` e, depois da emissão, uma conta criada com `ana@x.com` (outro convite consumido) | envio o cadastro com o primeiro convite | 410; nenhuma segunda conta |
| A-10 | Spec §3.2 | negativo | um convite válido | envio nome vazio, nome só com espaços, nome com 151 caracteres, senha fraca e confirmação diferente (um caso por vez) | formulário com mensagem; nada criado; convite continua pendente |
| A-11 | Spec §3.1 | negativo | um token alterado em um caractere e um token aleatório | abro `GET` e envio `POST` | 410 com a mensagem única; nada criado |
| A-12 | Spec §2 | negativo | um comprador autenticado e um convite válido para outro e-mail | abro o link e envio o `POST` | a página pede para sair da conta atual; nada criado; convite pendente |
| A-13 | Spec §3.1 (consumo único) | concorrência | um convite válido | dois `consumir_convite` em paralelo (`executar_em_paralelo`), repetido 20 vezes com convites novos | em todas as repetições: exatamente uma conta, convite consumido uma vez, e a outra operação com `ConviteInvalido` (consumido) |
| A-14 | T-34, Q-2, R-3 | concorrência | um convite de comprador emitido para `Ana@x.com` e um de fornecedor para ` ana@x.com ` (normalizados iguais) | consumo os dois em paralelo, repetido 10 vezes com dados novos | em todas: exatamente uma conta com `ana@x.com`; a outra operação recusada, por `ConviteInvalido(email_em_uso)` ou pela restrição de unicidade, com a transação desfeita; o convite recusado continua não consumido |
| A-15 | Spec §14 | positivo | o cadastro do A-2 | consulto a auditoria | uma entrada `convite.consumir`, com autor igual à conta criada e alterações com convite, conta e papel, sem e-mail, senha ou token |
| A-16 | Spec §3.1 | positivo | a conta do A-2, depois de sair | entro por senha (E02-02) | login aceito, sem novo convite |
| A-17 | Cenário 81 | positivo | uma conta comprador `ana@exemplo.com` | um convite de fornecedor para `ana.fornecedor@exemplo.com` é usado | duas contas independentes; cada login (senha) mostra em `/inicio/` só o próprio nome e papel |
| A-18 | Spec da fatia | negativo | um convite inválido de cada tipo (inexistente, consumido, expirado, banido, em uso) | abro o link | o corpo da resposta é idêntico nos cinco; o `codigo` interno de `ConviteInvalido` corresponde a cada causa (teste de serviço) |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-12, A-15 a A-18 | `tests/tecnicos/test_convites_cadastro.py` |
| A-13, A-14 | `tests/tecnicos/test_convites_cadastro_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
| A-3, A-4, A-6, A-7 (cenário 1); A-6 (cenário 62); A-9 (cenário 80); A-17 (cenário 81) | também marcados `acceptance`, com o número do cenário no comentário |
| A-14 (T-34) | também marcado `tecnico`, com o comentário `T-34` |
