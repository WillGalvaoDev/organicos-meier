# E02-06 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). `T` é o instante do pedido, controlado pela fixture `relogio`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §3.2 | positivo | um comprador ativo `ana@x.com` | peço o link com `"  ANA@x.com"` | a página padrão; um `LinkDeAcesso` para a conta; um e-mail para `ana@x.com` com `/entrar/link/<token>/` |
| A-2 | Spec §3.2 | positivo | o link do A-1 | abro `GET` | 200 com o botão; a sessão continua anônima; `usado_em` continua nulo |
| A-3 | Spec §3.2 | positivo | o link do A-1 | envio `POST` | sessão autenticada na conta `ana@x.com`; redirecionamento para `/inicio/`; `usado_em` preenchido |
| A-4 | Spec §3.2 | negativo | o link já usado no A-3 | envio `POST` de novo, em outro cliente | 410 com a mensagem única; nenhuma sessão |
| A-5 | Spec da fatia | fronteira | um link criado em `T` | envio `POST` em `T + 15min − 1 ms`, `T + 15min` e `T + 15min + 1 ms` (um link por instante) | aceito; recusado; recusado |
| A-6 | Spec da fatia | negativo | e-mail sem conta | peço o link | a mesma página (status e corpo) do A-1; nenhum link e nenhum e-mail |
| A-7 | Spec §2, cenário 58, T-24 | negativo | um comprador com `EmailBanido` do seu e-mail, e uma conta removida | peço o link para cada um, com variações de maiúsculas e espaços | a página padrão; nenhum link e nenhum e-mail |
| A-8 | Infra 2 | negativo | o administrador | peço o link | a página padrão; nenhum link e nenhum e-mail |
| A-9 | Cenário 2, 58 | negativo | um link pendente de um comprador | o e-mail é banido e depois envio o `POST`; noutro caso, a conta é removida e depois envio o `POST` | 410 nos dois; nenhuma sessão |
| A-10 | Spec §2 | positivo | um link pendente de um comprador que é suspenso depois do pedido | envio o `POST` | sessão autenticada |
| A-11 | Cenário 59 | positivo | `EmailBanido` com `ana@x.com` e a conta `ana+1@x.com` | peço e uso o link de `ana+1@x.com` | sessão autenticada |
| A-12 | Spec da fatia | negativo | um comprador | peço 4 links em 15 minutos | 3 links e 3 e-mails; o 4º pedido mostra a página padrão sem link nem e-mail; com o relógio avançado 15 minutos depois do 1º pedido, um novo pedido gera link |
| A-13 | Spec da fatia | concorrência | um link válido | dois `usar_link` em paralelo (`executar_em_paralelo`), repetido 20 vezes com links novos | em todas: uma conta devolvida e um `LinkInvalido`; `usado_em` gravado uma vez |
| A-14 | Spec da fatia | negativo | um token alterado em um caractere | abro `GET` e envio `POST` | 410 nos dois |
| A-15 | Spec da fatia | positivo | o link do A-1 | consulto o banco | `token_hash == sha256(token)`; o token em texto não aparece em nenhuma coluna |
| A-16 | Spec da fatia | positivo | dois links pendentes da mesma conta | uso o primeiro e depois o segundo (em outro cliente) | os dois autenticam, cada um uma vez |
| A-17 | Spec da fatia | negativo | um e-mail mal formado (`"lixo"`) | peço o link | erro de formulário; nenhum link |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-12, A-14 a A-17 | `tests/tecnicos/test_contas_link_de_acesso.py` |
| A-13 | `tests/tecnicos/test_contas_link_de_acesso_concorrencia.py` (marcador `concorrencia`) |
| A-7, A-9 (cenários 2 e 58; T-24, link) | também marcados `acceptance` e `tecnico`, com os números no comentário |
