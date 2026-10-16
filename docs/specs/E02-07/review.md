# E02-07 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento próprio, exceção técnica registrada):** `django.contrib.sites` (exigido pelo modelo `SocialApp` do allauth, `SITE_ID = 1`, sem uso em links), `allauth.socialaccount` e o provedor `google` em `INSTALLED_APPS`; configuração `SOCIALACCOUNT_*` e `SOCIALACCOUNT_PROVIDERS` (credenciais do ambiente: opcionais em `base`/`dev`, fictícias em `test`, obrigatórias em `prod` via `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`); `AdaptadorContaSocial` herdando o padrão do allauth; `MetodoCadastro.GOOGLE`; processador de contexto `google_habilitado`; views e rotas vazias; rota de teste que simula o retorno do Google (`tests/apoio/urls.py`). A suíte antes do Red: `408 passed`.

**Red** (`uv run pytest` nos dois arquivos de teste novos e em `test_configuracao_producao.py`, com o andaime):

```
31 failed, 6 passed
```

Falhas de asserção: `assert 200 == 302` (com o adaptador padrão o allauth não redireciona para a recusa), `assert 200 == 410`, `KeyError: 'location'`, `'NoneType' object is not subscriptable` (sem formulário de conclusão), `assert False` em `_autenticado`. O A-17 (produção sem credenciais) já passava por a configuração de produção fazer parte do andaime, e fica como cobertura.

**Green:** `AdaptadorContaSocial`, `apps/contas/google.py`, `FormularioConclusaoGoogle`, views `cadastrar_com_google`, `concluir_cadastro_google` e `google_recusado`, templates `convites/google_concluir.html` e os botões. 37 passed na primeira execução do Green.

**Refactor:** tipagem e formatação.

## Verificações (final)

```
uv run pytest -q                                  -> 442 passed em 70 s
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 97 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
manage.py check (test)                            -> 0 issues
```

## Matriz

| Critério | Teste |
|---|---|
| A-1, A-2 | `test_conta_existente_entra_pelo_email_e_vincula_a_conta_social`, `test_segundo_login_com_o_mesmo_uid_entra_na_mesma_conta` (cenário 82, T-35) |
| A-3 | `test_email_do_google_diferente_do_da_conta_vinculada_e_recusado` |
| A-4 | `test_sem_conta_e_sem_convite_nao_cria_nada` |
| A-5 | `test_email_nao_verificado_pelo_google_e_recusado`, `test_google_sem_email_e_recusado` |
| A-6 | `test_banido_ou_removido_nao_entra_pelo_google` (cenários 2 e 58, T-24 Google) |
| A-7, A-8, A-16 | `test_administrador_nao_entra_pelo_google`, `test_conta_suspensa_entra_pelo_google`, `test_alias_de_email_banido_entra_normalmente` |
| A-9 | `test_cadastro_com_google_cria_conta_vinculada_e_consome_o_convite` |
| A-10 | `test_google_com_outro_email_nao_cadastra_pelo_convite` (cenário 1) |
| A-11, A-12 | `test_post_adulterado_na_conclusao_e_ignorado`, `test_convite_que_expira_antes_da_conclusao_e_recusado`, `test_convite_consumido_por_senha_antes_da_conclusao_e_recusado` |
| A-13, A-14 | `test_convite_invalido_nao_inicia_o_fluxo_do_google`, `test_conclusao_aberta_diretamente_sem_convite_pendente_e_recusada` |
| A-15 | `test_conta_criada_pelo_google_define_senha_pela_recuperacao` |
| A-17 | `test_producao_sem_credenciais_do_google_falha_ao_carregar` |

## API do allauth usada no teste sem rede (versão 65.19.7)

A rota de teste (`/teste/retorno-google/`, em `tests/apoio/urls.py`, usada com `pytest.mark.urls`) monta o `SocialLogin` com `provider.sociallogin_from_response(request, extra_data)`, exatamente como o callback real do OAuth2, e o entrega a **`allauth.socialaccount.helpers.complete_social_login(request, sociallogin)`**. Nenhuma chamada HTTP ao Google é feita e o `AdaptadorContaSocial` do projeto não é substituído. `GOOGLE_CLIENT_ID` de teste só habilita o botão e o início do fluxo (que redireciona para `accounts.google.com`, sem rede).

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Onde a decisão acontece:** `AdaptadorContaSocial.pre_social_login`. A recusa é um `ImmediateHttpResponse` (redirecionamento para `/entrar/` com a mensagem única, via `recusar_login_google`), o que o `complete_login` do allauth trata antes de qualquer gravação; por isso nada é criado.
- **Vínculo e entrada:** na decisão 2 (conta com o mesmo e-mail normalizado), `sociallogin.connect(request, conta)` grava só a `SocialAccount`; `sociallogin.is_existing` passa a verdadeiro e o allauth segue o login normal (passando por `pre_login`, que usa `Metodo.GOOGLE` pelo último registro `socialaccount` da sessão).
- **E-mail verificado:** exige `extra_data["email_verified"] is True` (ou `verified_email is True`, formato do endpoint v2); qualquer outra coisa é recusa.
- **`SOCIALACCOUNT_EMAIL_VERIFICATION = "none"`:** a verificação do e-mail vem do próprio Google (exigida acima) e do `EmailAddress` verificado da conta; evita que o allauth tente enviar confirmação.
- **Conclusão do cadastro (`socialaccount_signup`):** a rota do allauth foi substituída por `/entrar/google/concluir/` com o mesmo nome, porque `redirect_to_signup` a usa. A view revalida o convite pendente e o e-mail do login social pendente, e só então chama `consumir_convite(..., metodo=MetodoCadastro.GOOGLE)` e `connect` numa única transação; o login vem depois do commit (`perform_login`).
- **Rotas do allauth expostas:** só o início e o callback do Google (`default_urlpatterns(GoogleProvider)`), e as duas rotas de erro/cancelamento (`socialaccount_login_error` e `_cancelled`), ambas apontando para a recusa única. A rota `google/login/token/` (login por token) não foi exposta. `on_authentication_error` também devolve a recusa única.
- **Convite pendente:** guardado em `request.session["convite_pendente"]` pela view `cadastrar_com_google` (somente `POST`, valida com `validar_convite`, inicia o login chamando a view `oauth2_login` do provedor). Sai da sessão no fim do cadastro, em qualquer recusa e em qualquer login de conta existente (decisões 1 e 2).
- **Botões:** "Entrar com Google" em `/entrar/` e "Cadastrar com Google" na página do convite aparecem só quando `GOOGLE_CLIENT_ID` está configurado (teste cobre os dois estados).
- **Dev:** sem credenciais, o botão some (spec). Em produção as duas variáveis são obrigatórias; `test_configuracao_producao.py` passou a incluí-las no ambiente mínimo.

## Limitações

- Nenhuma revisão independente feita ainda.
- O fluxo OAuth real com o Google (autorização, troca de código, `userinfo`) não é exercitado; é responsabilidade do allauth e fica para verificação na homologação, junto com a configuração do projeto no Google Cloud (fora do escopo).
