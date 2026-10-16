# E02-07 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). O retorno do Google é simulado montando o `SocialLogin`, sem rede (ver spec). "Nada criado" significa que as contagens de `Conta`, `SocialAccount` e `EmailAddress` não mudam.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 82, T-35 | positivo | uma conta comprador `ana@x.com` sem vínculo social | retorno do Google com `email="Ana@X.com"` verificado | sessão autenticada nessa conta; uma `SocialAccount` vinculada a ela; nenhuma conta nova |
| A-2 | Cenário 82 | positivo | o vínculo do A-1 | novo retorno do Google com o mesmo `uid` e e-mail | entra na mesma conta; nenhuma `SocialAccount` nova |
| A-3 | Spec §3.2 | negativo | o vínculo do A-1 | retorno do Google com o mesmo `uid` e `email="outra@x.com"` | recusado; nada criado; o vínculo continua apontando para a conta original |
| A-4 | Cenário 82, T-35 | negativo | nenhuma conta e nenhum convite pendente na sessão | retorno do Google com `nova@x.com` verificado | recusado; nada criado |
| A-5 | Spec §3.2 | negativo | uma conta `ana@x.com` | retorno do Google com `email_verified=false` e, noutro caso, sem e-mail | recusado nos dois; nada criado |
| A-6 | Cenário 2, 58, T-24 | negativo | uma conta `ana@x.com` com `EmailBanido` e uma conta removida `rem@x.com` | retorno do Google com `" ANA@x.com"` e com `rem@x.com` | recusado nos dois; nada criado |
| A-7 | Infra 2 | negativo | o administrador | retorno do Google com o e-mail dele | recusado; nada criado |
| A-8 | Spec §2 | positivo | um comprador suspenso | retorno do Google com o e-mail dele | sessão autenticada |
| A-9 | Spec §3.1, §3.2 | positivo | um convite de comprador pendente para `bia@x.com` | envio `POST /convite/<token>/google/`, retorno do Google com `Bia@x.com` e `name="Bia G"`, e envio o formulário com `nome="Bia"` | uma conta comprador `bia@x.com` com nome "Bia", senha inutilizável e `EmailAddress` verificado; `SocialAccount` vinculada; convite consumido; sessão autenticada; auditoria `convite.consumir` |
| A-10 | Cenário 1 ("outro e-mail") | negativo | um convite pendente para `bia@x.com` | inicio pelo convite e o Google retorna `outra@x.com` | recusado; nada criado; convite pendente; `convite_pendente` removido da sessão |
| A-11 | Spec §3.1 | negativo | um convite de fornecedor vinculado a `F1` | conclusão com Google com `POST` adulterado (`papel=comprador`, `fornecedor=<F2>`) | a conta criada é de fornecedor vinculada a `F1` |
| A-12 | Spec §3.1 | negativo | um convite que expira (relógio avançado) ou é consumido por senha entre o início no Google e o envio do formulário | envio o formulário de conclusão | recusado; nada criado pelo Google; no caso de consumo por senha, existe só a conta criada por senha |
| A-13 | Spec §3.1 | negativo | um convite inválido (consumido, expirado ou banido) | envio `POST /convite/<token>/google/` | 410 com a mensagem única da E02-05; não inicia o fluxo do Google |
| A-14 | Spec §3.2 | negativo | um retorno do Google para um e-mail sem conta, com o formulário de conclusão aberto diretamente sem convite pendente | envio o formulário | recusado; nada criado |
| A-15 | Spec §3.2 | positivo | a conta criada no A-9 | peço recuperação de acesso e defino uma senha | o login por senha passa a funcionar |
| A-16 | Cenário 59 | positivo | `EmailBanido` com `ana@x.com` e uma conta `ana+1@x.com` | retorno do Google com `ana+1@x.com` | sessão autenticada |
| A-17 | Spec da fatia | positivo | `config/settings/prod.py` sem `GOOGLE_CLIENT_ID` no ambiente | carrego as configurações em subprocesso | falha de configuração |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-8, A-16 | `tests/tecnicos/test_contas_google_login.py` |
| A-9 a A-15 | `tests/tecnicos/test_contas_google_cadastro.py` |
| A-17 | `tests/tecnicos/test_configuracao_producao.py` |
| A-1, A-2, A-4 (cenário 82, T-35); A-6 (cenários 2 e 58, T-24); A-10 (cenário 1) | também marcados `acceptance` e `tecnico`, com os números no comentário |
