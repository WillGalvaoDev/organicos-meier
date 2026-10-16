# E02-03 — Revisão

Estado atual: **REPROVADO** no commit `8f4dc36` (revisão independente ao final). A E02 global está **REPROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

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


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

### Matriz da fatia

A-1 a A-15: login por senha seguido de passkey, login direto, primeira passkey, autorização, recência e recuperação cobertos. A fronteira de 300 s exclusiva está registrada conforme autorização da spec para observar o allauth real. A-11/A-12 passam sequencialmente, mas a invariante da última passkey falha sob concorrência (E02-R02).

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

### E02-R02 — importante: duas remoções podem apagar a última passkey

Referência: spec E02-03, Gestão de passkeys e invariante de conservar ao menos uma fora do comando de recuperação; A-11/A-12; infraestrutura §2. Locais: `apps/contas/adaptadores.py:111` e `apps/contas/views.py:59`.

A consulta que permite excluir porque existe outra passkey e a exclusão não são serializadas. Com duas passkeys, duas sessões realmente autenticadas pelo fluxo de passkey e dois POSTs simultâneos, cada requisição vê a outra chave e ambas apagam. Resultado observado: **zero Authenticator**, fora do comando de recuperação. Não houve erro de infraestrutura nem exceção nas operações.

Reprodução: `test_duas_remocoes_preservam_ultima_passkey`. O monkeypatch apenas acrescenta uma barreira depois do resultado real de `can_delete_authenticator`; não altera a decisão. Views, sessões, banco e exclusões são reais. `executar_em_paralelo` executa os dois POSTs. Falha: `assert 0 >= 1`.

Devolução: tornar a verificação e a exclusão uma operação serializada por administrador, revalidando sob a mesma proteção; registrar Red → Green com duas exclusões concorrentes e conservar os testes de recência/permissão. A frase da spec sobre ausência de concorrência crítica não revoga a invariante explícita da última chave. Não é necessária decisão comercial.

## Correção E02-R02 conforme "Correção E02-R02" do spec.md (implementador)

**Causa confirmada.** `remover_passkey` consultava `can_delete_authenticator` (existe outra passkey?) e depois delegava a exclusão à view do allauth, sem serializar as duas etapas. Com duas passkeys e dois `POST` simultâneos de passkeys diferentes, cada requisição via a outra passkey, as duas apagavam e o administrador ficava com zero.

**Red** (código do commit `8f4dc36`, `uv run pytest tests/tecnicos/test_admin_passkeys_concorrencia.py`, três execuções seguidas):

```
3 failed   (execução 1)
3 failed   (execução 2)
3 failed   (execução 3)
E   assert 0 >= 1        test_duas_remocoes_preservam_ultima_passkey (teste do revisor, literal)
```

O teste do revisor falhou de forma determinística pela asserção (zero passkeys), porque a barreira dele força a intercalação logo depois de `can_delete_authenticator`. O A-16 (duas sessões, 10 repetições) e o A-17 (três sessões) também falharam nas três execuções do código antigo neste ambiente; como dependem da ordem real das threads, ficam como testes de regressão.

**Green** (`apps/contas/views.py`, `remover_passkey`): no `POST`, a consulta prévia por `can_delete_authenticator` continua como resposta rápida (sem trava, e é a que o teste do revisor pausa). Em seguida abre-se `transaction.atomic()` e trava-se a linha da **conta** da sessão (`Conta.objects.select_for_update().get(pk=...)`); sob a trava, a função própria `_ha_outra_passkey` (consulta nova) decide, e `can_delete_authenticator` nunca é chamado com a trava obtida. Sem outra passkey, a remoção é recusada com "A última passkey não pode ser removida." e redirecionamento para a lista; havendo, `remove_webauthn` roda dentro do mesmo bloco atômico (se o allauth pedir nova autenticação, a exceção desfaz o bloco e nada é removido). `GET`, A-11, A-12 e a exigência de nova autenticação ficaram como estavam. O comando `redefinir_passkeys_administrador` não mudou e segue como a única exceção à invariante.

**Verificação:**

```
test_admin_passkeys_concorrencia.py + test_admin_passkeys_gestao.py (5 execuções seguidas) -> 12 passed em todas
uv run pytest -q   -> 621 passed
```

**Defeito adicional encontrado no Green (corrigido, com teste).** Ao contar as mensagens da lista de passkeys, a página `/seguranca/webauthn/` falhou com `TemplateSyntaxError: 'humanize' is not a registered tag library`: os templates de passkeys do allauth carregam `django.contrib.humanize`, que não estava em `INSTALLED_APPS`, e nenhum teste anterior renderizava a listagem. Red: `test_paginas_de_gestao_de_passkeys_renderizam[lista]` (1 failed). Green: `django.contrib.humanize` adicionado a `config/settings/base.py`; as três páginas (índice, lista e cadastro) respondem 200.

**Matriz:** A-16 e A-17 em `tests/tecnicos/test_admin_passkeys_concorrencia.py`, com `test_duas_remocoes_preservam_ultima_passkey` do revisor (corpo literal, com `type: ignore` nas funções sem anotação e o formato de aspas do `ruff format`; nome original no comentário). Mais a regressão das páginas em `test_admin_passkeys_gestao.py`.

**Não feito (conforme "O que não fazer"):** não se travou só a linha do `Authenticator`; não se usou `count()` sem trava nem recriação posterior.
