# E02-03 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** `allauth.mfa` instalado com as configurações (`MFA_SUPPORTED_TYPES = ["webauthn"]`, `MFA_PASSKEY_LOGIN_ENABLED`, `MFA_ADAPTER`, `ACCOUNT_REAUTHENTICATION_TIMEOUT = 300`; `MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN` só em `dev.py` e `test.py`); middlewares, `somente_administrador`/`exige_reautenticacao_por_passkey`/mixin como passagem direta; `painel_administracao` em `/administracao/`; rotas `/seguranca/` (MFA do allauth); comando e `AdaptadorMFA` vazios. Suíte antes do Red: `265 passed`.

**Apoio de teste:** `tests/apoio/webauthn_falso.py` (dublê), `tests/apoio/admin_fluxos.py` (passos), `tests/apoio/urls.py` (rota de teste protegida por `exige_reautenticacao_por_passkey`, usada com `pytest.mark.urls`).

**Red** (`uv run pytest` nos cinco arquivos novos mais `test_contas_login_senha.py`, com o andaime):

```
26 failed, 23 passed
```

As falhas são de asserção: `assert 200 == 302` (a área administrativa e as demais URLs respondiam em vez de redirecionar), `assert 200 == 403` (comprador/fornecedor em `/administracao/`), `assert False` em `autenticado(...)` depois do comando de recuperação. O teste A-8 da E02-02 foi atualizado **antes** da correção, conforme o A-14 desta fatia (ver "Teste da E02-02 atualizado"), e entrou no Red.

**Green:** `apps/contas/administracao.py`, `middleware.py`, `sessoes.py`, `adaptadores.py` (`AdaptadorMFA`, `metodo_do_login`, `conferir_login`), `views.py` (`painel_administracao`, `remover_passkey`), `config/urls.py`, `management/commands/redefinir_passkeys_administrador.py`, templates `administracao/painel.html`, `mfa/index.html` e `account/reauthenticate.html`.

**Refactor:** tipagem (`mypy` estrito) e ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 295 passed em 47 s
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 79 source files
```

## Matriz

| Critério | Teste |
|---|---|
| A-1, A-2, A-3, A-4, A-5, A-14 | `test_admin_passkey_login.py` |
| A-6, A-7, A-8 | `test_admin_area_restrita.py` |
| A-9, A-10 | `test_admin_reautenticacao.py` |
| A-11, A-12, A-15 | `test_admin_passkeys_gestao.py` |
| A-13 | `test_admin_redefinir_passkeys.py` |

## Pontos de integração com o allauth 65.19.7 (exigidos pelo spec)

- **Prova de passkey na sessão:** API pública `allauth.account.authentication.get_authentication_records(request)`; vale um registro com `method == "mfa"` e `type == "webauthn"`. Registros de senha nunca contam. É o mesmo registro que o allauth cria no login por passkey, na etapa de passkey depois da senha e na reautenticação por passkey.
- **Dublê de WebAuthn:** `monkeypatch` nas cinco funções de `allauth.mfa.webauthn.internal.auth` (`begin_registration`, `complete_registration`, `begin_authentication`, `complete_authentication`, `extract_user_from_response`). As credenciais enviadas aos formulários reais são estruturas WebAuthn válidas montadas com o `fido2` (o allauth ainda faz o `parse_*` real). Views, estágio `mfa_authenticate`, registro de autenticação na sessão e o modelo `Authenticator` são reais.
- **Fronteira de 300 s (observada, não a prevista no spec):** o allauth compara `agora - última_autenticação < ACCOUNT_REAUTHENTICATION_TIMEOUT`, ou seja, o limite é **exclusivo**: com 299,9 s ainda vale, e com exatamente 300 s já exige nova autenticação. O spec supunha limite inclusivo e mandava registrar o real; a função própria (`passkey_recente`) usa o mesmo critério para ficar coerente com as telas do allauth. O tempo vem de `agora()` e é controlável pela fixture `relogio` (o `time-machine` também controla o `time.time()` que o allauth grava).

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **`can_delete_authenticator` só é consultado pelo TOTP** no allauth 65.19.7. A regra "a última passkey não pode ser removida" está no `AdaptadorMFA.can_delete_authenticator` e **também** na view: `remover_passkey` (em `config/urls.py`, antes do `include`) consulta o adaptador e recusa; senão delega à view do allauth.
- **Reautenticação do allauth:** `did_recently_authenticate` aceita qualquer método (inclusive senha). Por isso `ProtegeRotasDeMfa` exige passkey recente para cadastrar/editar/remover passkeys **quando o administrador já tem passkey**; sem nenhuma passkey ainda, vale a regra do allauth (login recente), para permitir a primeira.
- **Sem opção de senha na nova autenticação:** `AdaptadorConta.get_reauthentication_methods` remove a reautenticação por senha quando o administrador tem passkey (o allauth listaria as duas). A rota `account_reauthenticate` existe (o allauth a reverte ao montar a lista) para o administrador que ainda não tem passkey.
- **Método do login em `pre_login`:** `metodo_do_login` lê o último registro de autenticação (passkey direta = `Metodo.PASSKEY`; senão `Metodo.SENHA`), de modo que o banimento vale para ambos (teste `test_login_por_passkey_direta_respeita_o_banimento_do_email`).
- **Rotas de MFA:** `ProtegeRotasDeMfa` devolve 403 a qualquer conta autenticada que não seja administrador em `/seguranca/*`. Anônimos passam (login por passkey direta e etapa de passkey são anônimos).
- **Sessões restritas:** `ExigePasskeyDoAdministrador` redireciona administrador sem passkey para `mfa_add_webauthn`, exceto `/seguranca/*`, `/sair/` e arquivos estáticos. É por requisição, então vale também para sessões criadas por `force_login`.
- **`encerrar_sessoes_da_conta`** (em `apps/contas/sessoes.py`) varre as sessões do banco por `_auth_user_id` e limpa `UserSession`, sem depender de a conta ter feito requisições; a E02-08 reaproveita.
- **`mfa/index.html`** é a tela de conclusão do cadastro: orienta entrar de novo com passkey ou confirmar identidade para abrir a administração.

## Teste da E02-02 atualizado (A-14 desta fatia)

`test_login_por_senha_do_administrador_e_recusado_nesta_fatia` foi substituído por `test_login_por_senha_do_administrador_sem_passkey_fica_restrito`: a recusa temporária acabou; a sessão existe e só alcança o cadastro da primeira passkey. A recusa temporária foi removida de `conferir_login` (antes `conferir_login_por_senha`).

## Limitações

- Nenhuma revisão independente feita ainda.
- A cerimônia criptográfica real do WebAuthn (navegador e autenticador) não é exercida nos testes; é a responsabilidade do allauth/`fido2`. Fica para verificação manual na homologação.
- Telas de negócio da administração e o uso concreto da nova autenticação em operações financeiras ficam para etapas seguintes (spec).
