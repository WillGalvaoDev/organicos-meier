# E02-09 — Revisão

Estado atual: **APROVADO** no commit `0178d62` (revalidação independente ao final). A E02 global está **APROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

## Dependência nova: Pillow (A-19)

Pillow é a única dependência acrescentada, como prevê o spec: sem ela não há como verificar com segurança que o arquivo é uma imagem nem regravá-la sem metadados. `uv add pillow` registrou `pillow>=12.3.0` em `pyproject.toml` (grupo de dependências do projeto) e travou **12.3.0** em `uv.lock`. `uv sync --locked` passa (`Checked 50 packages`), e o CI roda o mesmo comando.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** campos `telefone`, `avatar` e `whatsapp_consentido_em` em `Conta` (sem restrições; migração provisória), `apps/contas/perfil.py` com as exceções e funções que devolvem a entrada como veio, `FormularioPerfil` mínimo, views `perfil` e `avatar` vazias com as rotas `/perfil/` e `/perfil/avatar/<id>/`, `MEDIA_ROOT` e `media/` no `.gitignore`. Suíte antes do Red: `479 passed`.

**Red** (`uv run pytest` nos quatro arquivos de teste desta fatia, com o andaime):

```
62 failed, 7 passed
```

Falhas de asserção: `DID NOT RAISE TelefoneInvalido`, `DID NOT RAISE IntegrityError` (sem as restrições do banco), `assert 200 == 302` (perfil vazio), `'NoneType' object is not subscriptable` (sem formulário no contexto), resultados de normalização diferentes dos esperados (`- +5521999998888`).

**Green:** `perfil.py` (`normalizar_telefone`, `processar_avatar`, `atualizar_perfil`), `FormularioPerfil`, views `perfil` e `avatar`, restrições `conta_whatsapp_exige_telefone` e `conta_telefone_e164` (migração `0004_perfil` regerada), template `contas/perfil.html`.

**Refactor:** tipagem e ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 548 passed em 74 s
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 109 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
uv sync --locked                                  -> Checked 50 packages
```

## Matriz

| Critério | Teste |
|---|---|
| A-1 a A-3, A-16 a A-18 | `test_perfil_tela.py` |
| A-4, A-5 | `test_perfil_telefone.py` (todos os exemplos do spec e mais casos-limite) |
| A-6 a A-9 | `test_perfil_whatsapp.py` |
| A-10 a A-15 | `test_perfil_avatar.py` (imagens geradas em memória; `MEDIA_ROOT` temporário; `django_db(transaction=True)` para a exclusão depois do commit) |
| A-19 | seção "Dependência nova" acima |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Telefone:** ao normalizar, `+` só é aceito no início e só como `+55`; sem `+`, o prefixo `55` só é descartado quando a entrada tem 12 ou 13 dígitos (assim o DDD 55 do Rio Grande do Sul, como em `(55) 99999-8888`, não é confundido com o país). Restam 10 ou 11 dígitos, com DDD que não começa com 0. A mensagem do erro não repete o número.
- **Restrição extra no banco:** `conta_telefone_e164` (`telefone IS NULL OR telefone ~ '^\+55[1-9][0-9][0-9]{8,9}$'`) garante a invariante "o telefone gravado é sempre E.164 brasileiro ou nulo" mesmo por SQL, além do `conta_whatsapp_exige_telefone` pedido.
- **Consentimento (regra completa em `atualizar_perfil`):** marcar com telefone grava `agora()` e audita `perfil.whatsapp_consentir`; desmarcar, remover o telefone ou trocar o número (com consentimento ativo) grava nulo e audita `perfil.whatsapp_revogar`. Na gravação em que o número muda, a caixa marcada é ignorada: é preciso aceitar de novo, numa gravação seguinte (teste `test_aceitar_de_novo_depois_de_trocar_o_numero`). Marcar sem telefone é erro de formulário, a menos que o consentimento já estivesse ativo e o usuário esteja removendo o número (nesse caso revoga). Manter o consentimento ativo não muda o instante nem gera auditoria. A auditoria nunca traz o número.
- **Avatar:** limite de 2 MB conferido antes de abrir; `Image.open` lê só o cabeçalho, então formato e dimensões (4096 × 4096) são validados antes de decodificar; `verify()` e reabertura para regravar; `ImageOps.exif_transpose` aplica a orientação antes de descartar o EXIF; a regravação não repassa `exif`, `pnginfo` nem perfis, então EXIF/GPS e textos de PNG saem (testados nos bytes do arquivo gravado). Extensão e nome vêm do formato verificado e de um UUID, nunca do nome enviado. A imagem de um tipo não aceito (GIF, texto com extensão `.png`) é recusada.
- **Armazenamento:** `ImageField` com `upload_to="avatares/"` no storage padrão (`MEDIA_ROOT`); o arquivo novo é gravado dentro da transação e removido se ela falhar; o antigo é apagado em `transaction.on_commit`.
- **Acesso ao avatar:** `/perfil/avatar/<id>/` exige login (anônimo vai ao `/entrar/`), serve à própria conta e ao administrador **com prova de passkey na sessão**; qualquer outro caso, inclusive conta sem avatar, dá 404. Resposta com `Cache-Control: private, no-store`.
- **Perfil:** a view carrega a conta da sessão e não aceita identificador de conta; o formulário só tem `nome`, `telefone`, `avatar`, `remover_avatar` e `whatsapp`, então `email`, `papel`, `fornecedor` e `situacao` enviados no `POST` são ignorados.

## Limitações

- Nenhuma revisão independente feita ainda.
- O storage do R2 em produção entra com a homologação (E16); aqui vale o storage padrão (spec).
- Envio de WhatsApp e templates ficam para a fase 3.


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

### Matriz da fatia

A-1 a A-19: perfil, telefone, consentimento/auditoria, validação e limpeza de avatares, acesso e dependência cobertos. Um probe adicional de PNG com EXIF/GPS também passou. A gravação integral da conta sobrescreve campos fora do perfil sob intercalação (E02-R01), contra o isolamento de A-16 e das regras de moderação/credenciais.

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

### E02-R01 — bloqueador: salvar perfil restaura estado de acesso e credenciais antigos

Referências: especificação funcional §§2 e 15; E02-09 Campos editáveis/A-16; E02-08 moderação/invariantes; E02-02 recuperação de acesso. Local: `apps/contas/perfil.py:124` (`conta.save()`), com a conta lida em `apps/contas/views.py` antes da gravação.

O perfil grava todas as colunas de uma instância já lida, incluindo `situacao` e `password`, embora só deva editar dados de perfil. Se outra operação suspender/remover a conta ou alterar a senha entre a leitura e a gravação, o POST de perfil restaura os valores antigos. Em três reproduções determinísticas pela rota real, a situação voltou a `ativa` após suspensão e após remoção, e a senha nova deixou de conferir após o perfil ser salvo.

No caso de remoção, o registro EmailBanido permanece e continua protegendo a entrada; o achado não afirma bypass desse banimento. A suspensão, porém, é efetivamente desfeita sem ação do administrador. Restaurar o hash antigo também contraria a recuperação e pode voltar a aceitar uma credencial substituída. Nenhuma nova ação de reativação é auditada.

Reprodução: `test_perfil_preserva_alteracao_concorrente`, parâmetros `suspender`, `remover` e `senha`, preservado em E02-10. O monkeypatch intercala a alteração depois de a view ler a conta e antes de chamar a função original de salvamento. Não altera a função auditada nem os resultados; representa deterministicamente a ordem possível de duas requisições. Falhas: `ativa != suspensa`, `ativa != removida` e senha nova não confere.

Devolução: restringir a gravação aos campos efetivamente editáveis e proteger a leitura/gravação dos estados do próprio perfil que precisam de consistência (consentimento e avatar), sem sobrescrever credenciais, papel, vínculo ou moderação. Testar a intercalação com suspensão, remoção e recuperação de senha antes da correção, e demonstrar Red → Green. Não há decisão comercial em aberto.

## Correção E02-R01 conforme "Correção E02-R01" do spec.md (implementador)

**Causa confirmada.** A view `perfil` lia a conta no início da requisição e `atualizar_perfil` alterava essa instância e chamava `conta.save()` sem `update_fields`, reescrevendo todas as colunas (inclusive `situacao` e `password`) com os valores lidos antes. Uma suspensão, uma remoção ou uma troca de senha feita nesse intervalo era desfeita. A frase "sem concorrência crítica" do spec estava errada.

**Red** (código do commit `8f4dc36`, `uv run pytest tests/tecnicos/test_perfil_concorrencia.py tests/tecnicos/test_contas_google_concorrencia.py tests/tecnicos/test_contas_recuperacao.py`):

```
12 failed, 13 passed
FAILED test_perfil_preserva_alteracao_concorrente[suspender]       assert 'ativa' == 'suspensa'   (teste do revisor)
FAILED test_perfil_preserva_alteracao_concorrente[remover]         assert 302 == 403              (parâmetro com a expectativa ajustada)
FAILED test_perfil_preserva_alteracao_concorrente[senha]           check_password(senha nova) falso (revisor)
FAILED test_suspensao_depois_da_leitura_e_preservada               (A-20)
FAILED test_remocao_depois_da_leitura_recusa_o_perfil_e_nao_grava_avatar   (A-21)
FAILED test_senha_trocada_depois_da_leitura_e_preservada           (A-22)
FAILED test_gravacao_do_perfil_so_atribui_as_colunas_do_perfil     (A-23: o UPDATE atribuía todas as colunas)
FAILED test_dois_consentimentos_simultaneos_geram_uma_auditoria    (A-24: AssertionError: 0, repetição 0)
FAILED test_perfil_e_suspensao_simultaneos_terminam_suspensos_com_nome_novo   (A-25)
```

(Mais os 3 falhos do A-25 da E02-02 e os 2 do A-21 da E02-07, registrados nas respectivas fatias.) Todos os testes de intercalação por `monkeypatch` falham de forma determinística pela asserção. Os com threads (A-24 e A-25) falharam já na primeira execução do código antigo neste ambiente; como dependem da ordem real das threads, ficam como regressão. A expectativa do parâmetro `remover` do teste do revisor foi ajustada para 403, nome inalterado e situação `removida`, conforme o item 4 da regra; `suspender` e `senha` ficaram literais (302). O corpo literal do revisor recebeu apenas `type: ignore` nas funções sem anotação, `noqa: S106` nas senhas de exemplo e o formato de aspas do `ruff format`.

**Green** (`apps/contas/perfil.py`, `atualizar_perfil`): a assinatura não mudou; da instância recebida usa-se só o `pk`. Dentro de `transaction.atomic()` a conta é relida com `Conta.objects.select_for_update().get(pk=...)`; conta `removida` na linha travada levanta `PermissionDenied` (403 pela view), sem gravar, sem auditoria e sem tocar o storage (o avatar novo só é gravado depois dessa checagem; se a gravação falhar depois, o arquivo novo é apagado). Consentimento, telefone e avatar anteriores, a revogação por troca ou remoção do telefone, a auditoria e o arquivo antigo a apagar (em `on_commit`) saem todos da linha travada. A gravação é `save(update_fields=["nome", "telefone", "whatsapp_consentido_em", "avatar"])`. Conta suspensa durante a requisição grava o perfil normalmente e continua `suspensa`. A trava é a mesma da moderação (E02-08), sem segunda trava. Ao final os campos do perfil são copiados para a instância recebida.

**Verificação (após as três correções do E02-R01):**

```
test_perfil_concorrencia.py + test_contas_google_concorrencia.py (3 execuções seguidas) -> 11 passed em todas
uv run pytest -q     -> 634 passed
uv run ruff check .  -> All checks passed
uv run mypy .        -> Success: no issues found in 123 source files
```

### Inventário das gravações de uma `Conta` já existente (exigido pelo spec)

Levantamento feito em 2026-10-16 com `grep -rn "\.save(\|\.update(" apps` (migrações excluídas) e conferência dos caminhos do allauth em uso (`allauth/account/**`, `socialaccount/models.py`, `mfa`, `usersessions`):

| Gravação | Arquivo | Proteção |
|---|---|---|
| perfil | `apps/contas/perfil.py:137` | `select_for_update` + `update_fields=["nome","telefone","whatsapp_consentido_em","avatar"]` (esta correção) |
| moderação | `apps/contas/moderacao.py:44` | `select_for_update` + `update_fields=["situacao"]` (E02-08) |
| redefinição de senha | `AdaptadorConta.set_password`, `apps/contas/adaptadores.py:112` | `update_fields=["password"]` (E02-02, esta correção) |
| vínculo com o Google (caso 2) | `AdaptadorContaSocial.pre_social_login` (`sociallogin.connect` -> `SocialLogin.save` -> `user.save()`) | leitura com `select_for_update` + `verificar_acesso` + `connect` na mesma transação (E02-07, esta correção) |
| criação da conta no consumo do convite | `apps/contas/convites.py:188` | conta nova (`INSERT`), na transação com o convite travado |
| criação do administrador | `criar_administrador.py:42` | conta nova |
| `Conta.save` (override) | `apps/contas/models.py:140,166` | repassa `*args, **kwargs` (inclui `update_fields`) e protege a unicidade do e-mail |
| `update_last_login` do Django (sinal `user_logged_in`) | `django/contrib/auth/models.py` | `save(update_fields=["last_login"])` |
| atualização de hash em `check_password` | `django/contrib/auth/base_user.py` | `save(update_fields=["password"])` |
| `setup_user_email` do allauth (`user.save()`) | `allauth/account/utils.py:227` | só no vínculo social sem `connect=True` e no cadastro social novo, caminhos que o projeto não usa (cadastro por Google sem convite é recusado; o vínculo usa `connect`) |
| `SocialLogin.save` com conta já vinculada (caso 1) | `allauth/socialaccount/models.py:_lookup_by_socialaccount` | grava só a `SocialAccount`; o teste `test_login_com_conta_social_ja_vinculada_nao_regrava_a_conta` confere que a única atualização de `contas_conta` é o `last_login` |

Nenhum ponto novo sem proteção foi encontrado.

**Não feito (conforme "O que não fazer"):** não se trocou a gravação por `refresh_from_db()` sem trava, não se reverteu a suspensão nem a senha depois da gravação, e não se usou `Conta.objects.filter(pk=...).update(...)` sem a releitura travada.


## Revalidação independente — 0178d62 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

R01 encerrado: releitura com select_for_update, decisões sobre estado atual e UPDATE restrito aos quatro campos do perfil. A-20 a A-25 verdes: suspensão, remoção com 403 sem efeitos, senha, SQL restrito e concorrência de consentimento/moderação. Inventário de gravações conferido com o código e a integração allauth.

Evidências comuns: `uv run pytest -q` — **634 passed em 70,20 s**; probes independentes — **7 passed em 2,20 s**; lint, formatação, tipos e checks Django sem erros. Comandos, encerramento dos quatro achados, evidência TDD e limites em [E02-10/review.md](../E02-10/review.md), seção de revalidação do commit `0178d62`. Os pareceres anteriores acima são históricos.
