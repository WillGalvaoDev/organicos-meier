# E02-07 — Revisão

Estado atual: **APROVADO** no commit `0178d62` (revalidação independente ao final). A E02 global está **APROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

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


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

### Matriz da fatia

A-1 a A-17: associação e recusas, convite, papel, consumo, recuperação e configuração cobertos para o payload email_verified. O payload verified_email do provedor real não conclui o cadastro (E02-R03), ampliando o cenário positivo A-9.

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

### E02-R03 — importante: cadastro Google recusa um retorno verificado aceito pelo próprio adaptador

Referência: spec E02-07, Dados aceitos do Google e Conclusão do cadastro; A-9; especificação funcional §3.2. Local: `apps/contas/views.py:205`, em contraste com `apps/contas/adaptadores.py:134`.

O allauth instalado admite dois formatos: ID token (`sub`, `email_verified`) e `/oauth2/v2/userinfo` (`id`, `verified_email`). O provedor e o adaptador do projeto aceitam ambos. A conclusão própria verifica somente `email_verified is True`, recusando o segundo formato mesmo com convite válido e e-mail verificado. Isso é observável sem rede: o retorno segue corretamente para `/entrar/google/concluir/`, mas seu POST redireciona para `/entrar/` e não cria a conta. Não se presume uma falha do Google; é divergência entre duas etapas do próprio projeto.

Reprodução: `test_google_userinfo_verificado_conclui_cadastro` passa `{"id":"google-revisor","email":"google@x.com","verified_email":true,"name":"Google"}` pela mesma rota de teste que chama `provider.sociallogin_from_response` e `complete_social_login`. Falha: `/entrar/ != /inicio/`. O suporte aos dois formatos foi conferido no código local de `allauth/socialaccount/providers/google/provider.py` e `views.py`, sem inferência sobre um provedor não consultado.

Devolução: usar a mesma interpretação segura de e-mail verificado no retorno e na conclusão, cobrindo ambos os formatos e conservando as recusas de e-mail ausente/não verificado, divergência com o convite, expiração e banimento. Não aceitar um e-mail não verificado para fazer o teste passar.

## Correção E02-R03 conforme "Correção E02-R03" do spec.md (implementador)

**Causa confirmada.** O adaptador aceitava o e-mail como verificado com `email_verified is True` **ou** `verified_email is True` (`adaptadores.py`), enquanto a conclusão do cadastro (`views.py`) aceitava só `email_verified is True`. No formato userinfo (`id`, `verified_email`) o retorno seguia, a conclusão recusava e a conta não era criada.

**Red** (código do commit `8f4dc36`, `uv run pytest tests/tecnicos/test_contas_google_cadastro.py`):

```
6 failed, 23 passed
FAILED test_google_userinfo_verificado_conclui_cadastro                      (teste do revisor, literal; A-18)
FAILED test_formato_userinfo_tem_o_mesmo_resultado_do_cadastro_com_id_token   (A-18)
FAILED test_email_nao_verificado_nao_cadastra_pelo_convite[conflito]          (A-19 c)
FAILED test_email_nao_verificado_nao_entra_em_conta_existente[conflito]       (A-19 c)
FAILED test_funcao_unica_interpreta_a_verificacao_do_google                   (A-20: a função não existia)
FAILED test_adaptador_e_conclusao_usam_a_mesma_funcao                         (A-20)
```

O teste do revisor falha em `assert resposta['Location'] == '/inicio/'` (a conclusão recusa e redireciona para `/entrar/`). O caso `email_verified: true` com `verified_email: false` (A-19 c) era aceito pelo `or` do adaptador. Os demais casos do A-19 (`false`, texto `"true"`, nenhuma chave) já eram recusados e ficam como cobertura.

**Green:** `email_verificado_do_google(extra_data) -> str | None` em `apps/contas/google.py`, a única função que interpreta a verificação: pelo menos uma das chaves `email_verified` e `verified_email` vale exatamente `True` e nenhuma presente tem outro valor; e-mail ausente, não textual ou recusado por `normalizar_email` devolve `None`. O adaptador (`_email_verificado`, usado no retorno, em `pre_social_login` e em `is_open_for_signup`) e a view de conclusão a chamam por `apps.contas.google.email_verificado_do_google` (referência de módulo, para o `monkeypatch` do A-20 alcançar os dois pontos). A view não interpreta mais nenhuma chave. As recusas por divergência com o convite, convite expirado, consumido ou banido e a ausência de convite pendente continuam.

**Verificação:** `uv run pytest -q` -> 615 passed; ruff e mypy limpos.

**Matriz:** A-18 (`test_google_userinfo_verificado_conclui_cadastro` literal, com `noqa: S105` no token e o formato de aspas do `ruff format`, e `test_formato_userinfo_tem_o_mesmo_resultado_do_cadastro_com_id_token`), A-19 (parametrizado nos quatro casos, para convite pendente e para conta existente), A-20 (`test_funcao_unica_interpreta_a_verificacao_do_google` com ID token, userinfo e dez negativos, e `test_adaptador_e_conclusao_usam_a_mesma_funcao`). Não foi aceito e-mail sem marcação de verificado, e a interpretação não foi duplicada.

## Correção E02-R01 (vínculo Google) conforme o spec.md (implementador)

**Causa confirmada.** No caso 2 da decisão no retorno do Google, o adaptador lia a conta por e-mail sem trava e `sociallogin.connect(request, conta)` chamava `SocialLogin.save` -> `user.save()` sem `update_fields` (`allauth/socialaccount/models.py`), de modo que uma suspensão ou remoção feita entre a leitura e o vínculo era desfeita.

**Red** (código do commit `8f4dc36`): `test_vinculo_do_google_nao_desfaz_suspensao_nem_remocao[suspender]` e `[remover]` (A-21) falharam na asserção (`situacao` final `ativa`). O teste usa duas threads reais: uma trava a linha da conta e a suspende (ou remove) e só confirma depois de ver, em `pg_stat_activity` (`wait_event_type = 'Lock'`), a outra esperando por trava; a outra é o retorno do Google. No código antigo a espera acontece no `UPDATE` do `connect`, que então sobrescrevia a situação.

**Green** (`AdaptadorContaSocial.pre_social_login`, caso 2): a leitura (`Conta.objects.select_for_update().filter(email_normalizado=e).first()`), `verificar_acesso` e `sociallogin.connect` ficam no mesmo `transaction.atomic()`. Depois de uma suspensão concluída antes, o retorno espera a trava, lê `suspensa`, `verificar_acesso` aceita (a suspensa entra), o `connect` grava o estado atual e o login acontece. Depois de uma remoção, `verificar_acesso` recusa (a transação é desfeita, sem `SocialAccount`) e o login é recusado.

**Caso 1 (conta social já vinculada), conferido no allauth 65.19.7:** o caminho `_lookup_by_socialaccount` grava só a `SocialAccount` e o login só atualiza `last_login` (`update_fields`); não chama `user.save()` sem `update_fields`. O teste `test_login_com_conta_social_ja_vinculada_nao_regrava_a_conta` confere pelas consultas que a única atualização de `contas_conta` é a de `last_login`.

Testes: A-21 em `tests/tecnicos/test_contas_google_concorrencia.py` (`concorrencia`, `django_db(transaction=True)`). O inventário das gravações está em `docs/specs/E02-09/review.md`.

**Verificação (após as três correções do E02-R01):**

```
test_perfil_concorrencia.py + test_contas_google_concorrencia.py (3 execuções seguidas) -> 11 passed em todas
uv run pytest -q     -> 634 passed
uv run ruff check .  -> All checks passed
uv run mypy .        -> Success: no issues found in 123 source files
```


## Revalidação independente — 0178d62 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

R03 encerrado: interpretação única e estrita dos dois formatos de verificação, no retorno e na conclusão (A-18 a A-20); negativos e probe original verdes. R01 encerrado no vínculo existente: leitura, autorização e connect sob trava da Conta (A-21), inclusive espera real no Postgres e recusa após remoção.

Evidências comuns: `uv run pytest -q` — **634 passed em 70,20 s**; probes independentes — **7 passed em 2,20 s**; lint, formatação, tipos e checks Django sem erros. Comandos, encerramento dos quatro achados, evidência TDD e limites em [E02-10/review.md](../E02-10/review.md), seção de revalidação do commit `0178d62`. Os pareceres anteriores acima são históricos.
