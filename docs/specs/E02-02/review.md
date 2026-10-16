# E02-02 — Revisão

Estado atual: **REPROVADO** no commit `8f4dc36` (revisão independente ao final). A E02 global está **REPROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

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


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

### Matriz da fatia

A-1 a A-21: login, recusas genéricas, recuperação, sessões e configuração cobertos na suíte. A-8 foi substituído explicitamente por E02-03/A-14. A política de semelhança de senha não é efetiva para os atributos personalizados, conforme E02-R04; a cobertura de A-15 não detecta esse caso.

### Verificação independente comum

SHA auditado: `8f4dc36e91833ad11e327bcfb99e34fa81ba6eb8`, main/PR #32. Documentos de referência: especificação funcional v1.6 (§§2, 3 e 15), infraestrutura v1.7 (§§2, 4.11 e 5), spec e acceptance de cada fatia. Nenhuma mudança de regra de negócio foi presumida.

- `uv run pytest -q`: **594 passed em 75,74 s**, banco Postgres real, incluindo E01 e todas as fatias E02.
- `uv run ruff check .`: limpo; `uv run ruff format --check .`: 156 arquivos.
- `uv run mypy .`: 120 arquivos, sem erros.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: sem mudanças.
- `uv run python manage.py check --settings=config.settings.test`: zero issues.
- `uv sync --locked`: lock resolvido (51 pacotes), ambiente conferido (50 pacotes).
- CI do SHA exato: [run 38914653756](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38914653756), sucesso.

A suíte verde não basta para aprovar E02: os probes adicionais do revisor terminaram em **6 failed, 1 passed em 2,65 s**, reproduzindo quatro achados distintos. Script, comando e matriz global estão em `../E02-10/review.md`, seção de revisão independente. O probe de PNG/EXIF passou e não gerou achado.

### Evidência TDD e limites

Conferidos os relatos de andaime, Red por asserção/comportamento, Green e refatoração de cada fatia, comparados com o diff e os testes. As alterações autorizadas de testes anteriores estão identificadas: fábrica de conta na auditoria E01; regra temporária de login administrativo substituída pela E02-03. Ajustes de instrumentação relatados pelo implementador não foram tratados como prova de defeito em produção. Limitação: a cronologia dos ciclos é documentada pelo implementador, sem logs brutos/commits intermediários para comprovar independentemente cada passo. A execução Green acima é independente; não foi apresentada como prova retrospectiva de toda a sequência TDD.

WebAuthn usa o dublê criptográfico expressamente previsto, com views, sessão e Authenticator reais. Google usa o fluxo real do allauth com resposta simulada, sem chamada ao provedor. Cerimônia física de passkey, OAuth/credenciais reais, SES, R2 e efeitos futuros sobre pedidos/interesses não foram validados nesta etapa; permanecem nos gates previstos pelos documentos. D-1 da E02-08 (suspensão de fornecedor) não foi implementado nem reaberto.

### E02-R04 — importante: validador de similaridade ignora os atributos da Conta

Referência: spec E02-02, regra Senhas; E02-05, validação do cadastro/A-10. Local: `config/settings/base.py:115`.

O `UserAttributeSimilarityValidator` usa por padrão `username`, `first_name`, `last_name` e `email`. O modelo tem `nome` e `email_normalizado`; atributos inexistentes são ignorados pelo validador. Com o formulário real de convite, nome e senha iguais a `NomeCompletoExclusivo9271` resultaram em 302 para `/inicio/` e conta criada, em vez de erro de validação. A mesma configuração é compartilhada com a recuperação.

Reprodução: `test_cadastro_recusa_senha_igual_ao_nome` no script preservado em E02-10: falha `assert 302 == 200`. O código da dependência instalada confirma os atributos padrão (`django/contrib/auth/password_validation.py`, `UserAttributeSimilarityValidator`).

Devolução: configurar o validador para os atributos efetivos do modelo e demonstrar Red → Green no cadastro e na recuperação, cobrindo nome e e-mail, além dos casos já existentes. Não mudar a política de senha para acomodar o teste. O E02-R01 também afeta a preservação de uma senha recém-alterada, mas a correção pertence ao salvamento de perfil.

## Correção E02-R04 conforme "Correção E02-R04" do spec.md (implementador)

**Causa confirmada.** `AUTH_PASSWORD_VALIDATORS` declarava o `UserAttributeSimilarityValidator` sem opções; o padrão do Django compara a senha com `username`, `first_name`, `last_name` e `email`, atributos que `Conta` não tem, então a semelhança com o nome e o e-mail nunca foi aplicada.

**Red** (código do commit `8f4dc36`, `uv run pytest` em `test_contas_recuperacao.py`, `test_configuracao_producao.py` e `test_convites_cadastro.py` com os testes novos):

```
8 failed, 47 passed
E   assert 302 == 200                  (senha igual ao nome aceita; redirecionou para /inicio/ ou concluiu)
E   KeyError: 'form'                   (a redefinição não devolveu o formulário com erro)
E   Failed: DID NOT RAISE ValidationError   (serviço consumir_convite aceitou a senha)
E   AssertionError: assert ('username', ...ame', 'email') == ('nome', 'email_normalizado')
E   KeyError: 'OPTIONS'               (produção sem opções no validador)
```

Testes que falharam: A-22 e A-23 (`test_redefinicao_recusa_senha_semelhante_ao_nome` e `..._ao_email`), o teste do revisor `test_cadastro_recusa_senha_igual_ao_nome` (literal, em `test_convites_cadastro.py`; só o formato de aspas foi ajustado pelo `ruff format` e um `noqa: S105` foi acrescentado ao literal do token), as variações do A-19 e A-20 e o A-24 em teste e em produção.

**Green** (`config/settings/base.py`): `"OPTIONS": {"user_attributes": ("nome", "email_normalizado")}`. O `max_similarity` continua o padrão (0,7), conferido por teste, e os outros três validadores não mudaram (mínimo de 10 caracteres). Nenhuma alteração em `apps/contas/forms.py` nem em `convites.py`: ambos já validavam com a conta provisória preenchida (nome e e-mail). Na redefinição, o campo de senha do allauth valida com a conta do link.

**Verificação:**

```
uv run pytest -q              -> 603 passed
uv run ruff check .           -> All checks passed
uv run mypy .                 -> Success: no issues found in 120 source files
```

**Matriz:** A-22 e A-23 em `test_contas_recuperacao.py` (os dois conferem o código `password_too_similar`, que a senha continua a antiga e a ausência da nova); A-24 em `test_configuracao_producao.py` (produção, em subprocesso, e `get_default_password_validators()` nas configurações de teste).
