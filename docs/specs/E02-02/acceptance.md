# E02-02 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Os testes usam o cliente de teste do Django contra as rotas reais e o Postgres real.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §3.2 | positivo | um comprador ativo com senha válida | envio o login com o e-mail exato | sessão autenticada, redirecionamento para `/inicio/` e a página mostra o nome |
| A-2 | Spec §2, R-3 | positivo | o mesmo comprador (`ana@x.com`) | envio o login com `"  ANA@x.com "` | sessão autenticada |
| A-3 | Spec §3.2 | negativo | o mesmo comprador | envio senha errada; envio um e-mail inexistente | nenhuma sessão; a mesma mensagem genérica nos dois casos |
| A-4 | Spec §2, §3.1, cenário 58, T-24 | negativo | um comprador com senha válida e `EmailBanido` do e-mail dele | envio o login com o e-mail exato, com maiúsculas e com espaços | nenhuma sessão nas três tentativas; mensagem genérica idêntica à do A-3 |
| A-5 | Spec §2 | negativo | uma conta removida com senha válida | envio o login | nenhuma sessão; mensagem genérica; a página de conta inativa do allauth não aparece |
| A-6 | Spec §2 | positivo | um comprador suspenso com senha válida | envio o login | sessão autenticada |
| A-7 | Cenário 59, T-24 | positivo | `EmailBanido` com `ana@x.com` e uma conta `ana+1@x.com` | envio o login da conta `ana+1@x.com` | sessão autenticada |
| A-8 | Infra 2 (admin com passkey) | negativo | o administrador com senha definida | envio o login por senha | nenhuma sessão nesta fatia |
| A-9 | `verificar_acesso` | unitário | combinações de banido ou não, conta inexistente, situações (ativa, suspensa, removida), papéis e métodos | chamo `verificar_acesso` | recusa exatamente nos casos 1 a 4 da spec, com o `codigo` correspondente; sem recusa nos demais, inclusive suspensa |
| A-10 | Spec §3.2 | positivo | um comprador ativo | peço recuperação de acesso com `" Ana@X.com"` | um e-mail na caixa de saída para `ana@x.com`, com link de redefinição |
| A-11 | Spec §3.2 | negativo | (a) e-mail inexistente; (b) e-mail banido com conta; (c) conta removida | peço recuperação de acesso | nenhum e-mail; resposta (status e texto) idêntica à do A-10 |
| A-12 | Spec §18 | negativo | a rota de cadastro do allauth, se existir no `urls.py` | envio `GET` e `POST` com dados completos | nenhuma conta criada; resposta de cadastro fechado ou 404 |
| A-13 | Spec §3.2 | positivo | o link de redefinição do A-10 | defino uma nova senha válida e depois entro com ela | a senha antiga deixa de funcionar e a nova funciona; usar o mesmo link de novo é recusado |
| A-14 | Spec §2, §3.1 | negativo | o link de redefinição de um comprador, enviado antes de o e-mail dele ser banido | tento definir a nova senha | recusado; a senha não muda |
| A-15 | Spec §3.2 | negativo | um link de redefinição | defino uma senha de 9 caracteres, uma só numérica e uma comum | recusa em cada caso, com mensagem de validação |
| A-16 | Spec da fatia | positivo | um comprador autenticado | envio `POST /sair/`; depois envio `GET /sair/` autenticado de novo | o `POST` encerra a sessão; o `GET` não encerra |
| A-17 | Spec da fatia | negativo | um visitante anônimo | acesso `/inicio/` | redirecionamento para `/entrar/` |
| A-18 | Spec da fatia | positivo | `config/settings/prod.py` carregado com as variáveis obrigatórias de ambiente | inspeciono as configurações | cookies de sessão e CSRF `Secure`, sessão `HttpOnly`, `SameSite=Lax` |
| A-19 | Spec da fatia | negativo | `config/settings/prod.py` sem `EMAIL_BACKEND` no ambiente | carrego as configurações em um subprocesso | o carregamento falha com erro de configuração |
| A-20 | Spec da fatia | positivo | um login bem-sucedido | consulto o `usersessions` | existe um registro de sessão para a conta |
| A-21 | E02-01 (comando) | positivo | nenhum administrador | rodo `criar_administrador` | existe `EmailAddress` verificado e primário com o e-mail normalizado do administrador |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-8, A-16, A-17, A-20 | `tests/tecnicos/test_contas_login_senha.py` |
| A-9 | `tests/tecnicos/test_contas_acesso.py` |
| A-10, A-11, A-13 a A-15 | `tests/tecnicos/test_contas_recuperacao.py` |
| A-12 | `tests/tecnicos/test_contas_login_senha.py::test_cadastro_aberto_inexistente` |
| A-18, A-19 | `tests/tecnicos/test_configuracao_producao.py` |
| A-21 | `tests/tecnicos/test_contas_criar_administrador.py` |
| A-4 e A-7 (T-24, senha) | também marcados com `tecnico` e o comentário `T-24` |
