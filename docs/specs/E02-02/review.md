# E02-02 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** `allauth`, `allauth.account` e `allauth.usersessions` em `INSTALLED_APPS` com os dois middlewares; bloco de configuração `ACCOUNT_*` e `AUTH_PASSWORD_VALIDATORS` em `base.py` (sem ele o allauth acusa `Cannot resolve keyword 'email'` ao criar o banco de testes); `acesso.py` com `Metodo`, `AcessoRecusado` e `verificar_acesso` que nunca recusa; `AdaptadorConta` e os dois formulários como subclasses vazias; `ContaFactory` passa a criar o `EmailAddress` verificado e primário; fixture que limpa o cache entre testes (limites de requisição do allauth). Com isso a suíte anterior seguiu verde: `191 passed`.

**Red** (`uv run pytest` nos cinco arquivos de teste desta fatia, com o andaime):

```
55 failed, 26 passed
```

As falhas são de asserção: respostas `404` onde se esperava redirecionamento ou formulário (`/entrar/`, `/recuperar-acesso/`, `/inicio/` ainda sem rota), `assert 'Não foi possível entrar com esses dados.' in '<!doctype html>... Not Found'`, `DID NOT RAISE AcessoRecusado`, `ImproperlyConfigured` ausente na configuração de produção, e `EmailAddress.DoesNotExist` no comando. Os 26 que já passavam são cobertura (casos "não recusa", `is_open_for_signup`, etc.).

**Green:** `apps/contas/acesso.py`, `adaptadores.py`, `formularios.py`, `views.py`, `config/urls.py`, `templates/` (base, login, logout, recuperação em quatro páginas, início e e-mail de recuperação), `config/settings/{dev,test,prod}.py`, passo do `EmailAddress` em `criar_administrador`.

**Refactor:** `skip_postgeneration_save = True` na fábrica (acaba com o `DeprecationWarning`), tipagem do adaptador, ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 265 passed em 56 s
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 67 source files
```

## Matriz

| Critério | Teste |
|---|---|
| A-1, A-2, A-3, A-4, A-5, A-6, A-7, A-8 | `test_contas_login_senha.py` (A-4 e A-7 marcados `tecnico`, T-24) |
| A-9 | `test_contas_acesso.py` (todas as combinações método x situação x papel) |
| A-10, A-11, A-13, A-14, A-15 | `test_contas_recuperacao.py` |
| A-12 | `test_cadastro_aberto_inexistente` |
| A-16, A-17, A-20 | `test_contas_login_senha.py` |
| A-18, A-19 | `test_configuracao_producao.py` (subprocesso) |
| A-21 | `test_comando_cria_endereco_de_email_verificado_e_primario` |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **`ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]`**: o `LoginForm` do allauth remove o campo de senha se `password1` não consta nos campos de cadastro. Como o cadastro está fechado, isso não abre rota alguma.
- **`ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`**: sem isso o allauth envia um e-mail "conta desconhecida" a quem não tem conta, contra o A-11 (nenhum e-mail).
- **Onde a recusa de login acontece:** em `AdaptadorConta.authenticate` (depois do `authenticate` do allauth), para que banido, removido, administrador e e-mail não verificado saiam como "credencial inválida", com a mesma mensagem genérica do spec e sem tocar na sessão. `pre_login` repete a conferência por defesa e redireciona ao `/entrar/`. `respond_user_inactive` também redireciona ao `/entrar/`, para a página de conta inativa nunca aparecer.
- **E-mail não verificado:** com `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`, uma conta sem `EmailAddress` verificado faria o allauth tentar a verificação e quebrar (rota não exposta). Essa situação é tratada como recusa genérica. A fábrica e o comando `criar_administrador` criam o `EmailAddress` verificado.
- **Recusa do administrador por senha:** em `conferir_login_por_senha`, fora de `verificar_acesso` (spec), comentada como temporária até a E02-03.
- **Recuperação:** `FormularioRecuperacao` retira da lista de envio as contas que `verificar_acesso(..., senha)` recusa (banida; removida já sai do filtro `is_active` do allauth); a resposta continua igual. `FormularioNovaSenha` revalida no momento de definir a senha. O token é o padrão do Django/allauth (uso único, expira no prazo padrão).
- **Rotas:** só as rotas do allauth necessárias, com os nomes que o allauth usa internamente (`account_login`, `account_reset_password_from_key`, ...), em português. Cadastro, e-mails, troca de senha e demais ficam fora.
- **Configuração de e-mail:** `locmem` em teste, `console` em desenvolvimento e, em produção, `EMAIL_BACKEND` e `DEFAULT_FROM_EMAIL` obrigatórios via `env(...)` sem padrão. Como o teste da E01-02 (`test_app_de_testes_fora_da_producao`) importa `config.settings.prod` dentro do processo de teste, `config/settings/test.py` define essas duas variáveis com `setdefault`. Os testes A-18 e A-19 rodam em subprocesso com o ambiente montado explicitamente, sem essas variáveis herdadas.
- **Cache nos testes:** o limite de requisição do allauth usa o cache; uma fixture `autouse` o limpa entre testes.
- **mypy:** `disallow_subclassing_any = false` só para `apps.contas.adaptadores` e `apps.contas.formularios` (o allauth não tem tipos).

## Limitações

- Nenhuma revisão independente feita ainda.
- Login por link, Google, passkey e a invalidação de sessões no banimento ficam para E02-03, E02-06, E02-07 e E02-08 (spec).
