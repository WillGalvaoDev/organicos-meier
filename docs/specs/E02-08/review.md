# E02-08 — Revisão

Estado atual: **APROVADO** no commit `0178d62` (revalidação independente ao final). A E02 global está **APROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** `apps/contas/moderacao.py` com os sinais `conta_suspensa` e `conta_removida`, `ModeracaoInvalida` e os três serviços sem efeito; `Conta.pode_adicionar_interesse` fixo em falso; `RecusaContaSemAcesso` como passagem direta (registrado em `MIDDLEWARE`); views e rotas vazias (`/administracao/usuarios/`, `.../<pk>/remover/`, `.../<pk>/<acao>/`); rota de teste autenticada com contador de chamadas em `tests/apoio/urls.py`. Refator prévio: `encerrar_sessoes_da_conta` (E02-03) renomeada para `encerrar_sessoes`, o nome da interface desta fatia; o comando `redefinir_passkeys_administrador` foi ajustado e seus testes seguiram verdes. Suíte antes do Red: `442 passed`.

**Red** (`uv run pytest` nos quatro arquivos de teste desta fatia, com o andaime):

```
34 failed, 3 passed
```

Falhas de asserção: `DID NOT RAISE ModeracaoInvalida`, `DID NOT RAISE PermissionDenied`, `assert 200 == 302`/`403` (telas vazias), `assert 0 == 2` (nenhuma sessão apagada).

**Green:** `moderacao.py` (serviços com `select_for_update`, revalidação, auditoria e sinais), `RecusaContaSemAcesso`, `Conta.pode_adicionar_interesse`, views `usuarios_administracao`, `acao_de_moderacao` e `confirmar_remocao`, templates `usuarios/*`.

**Ajuste de teste durante o Green (sem mudar o código):** os registros do `usersessions` do allauth nascem no login real (sinal `user_logged_in`), porque `TRACK_ACTIVITY` é falso por padrão; `force_login` não os cria. Os testes de remoção abrem as sessões por login real (por senha). A segunda versão do teste A-6 também passou a abrir as quatro sessões com uma única troca de senha, porque `set_password` repetido invalida as sessões já abertas.

**Refactor:** tipagem e ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 479 passed em 73 s
test_moderacao_concorrencia.py (3 execuções seguidas) -> 2 passed em todas
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 102 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
```

## Matriz

| Critério | Teste |
|---|---|
| A-1 | `test_suspender_pela_tela_nao_encerra_a_sessao_nem_bane` (cenário 60) |
| A-2, A-3 | `test_sinal_de_suspensao_roda_dentro_da_transacao`, `test_receptor_que_falha_desfaz_a_suspensao` |
| A-4 | `test_reativar_volta_a_ativa_sem_restaurar_nada` (cenários 19 e 60) |
| A-5 | `test_remocao_bane_o_email_e_apaga_as_sessoes` (cenários 20, 58, 83; T-24, T-36) |
| A-6 | `test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou` (GET redireciona, POST 403, view não executa) e `..._email_banido_mesmo_ativa` |
| A-7, A-8 | `test_remocao_preserva_conta_historico_e_convite`, `test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite` (senha, link, Google e convite) |
| A-9, A-10 | `test_remocao_afeta_so_o_endereco_exato`, `test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa` |
| A-11, A-12, A-14 | `test_administrador_nunca_e_alvo`, `test_suspender_fornecedor...`, `..._ja_esta_suspenso...`, `test_reativar_quem_esta_ativo...`, `test_remover_quem_ja_foi_removido...`, `test_outro_autor_que_nao_o_administrador_e_recusado` |
| A-13, A-18 | `test_moderacao_tela.py` |
| A-15, A-16 | `test_moderacao_concorrencia.py` (10 repetições cada) |
| A-17 | `test_falha_ao_encerrar_sessoes_desfaz_a_remocao` |
| A-19 | `test_pode_adicionar_interesse_so_para_comprador_ativo` |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **O middleware olha a sessão, não `request.user`:** o backend do Django trata como anônima a sessão de conta removida (`is_active` falso), então `request.user` não serviria para o A-6 (POST precisa de 403 e a view não pode executar). `RecusaContaSemAcesso` lê `SESSION_KEY`, relê a conta do banco (situação e e-mail) e consulta `email_banido`; se removida ou banida, faz `logout` e responde (GET: redirecionamento ao login com "Sua sessão foi encerrada."; outros métodos: 403). Ele fica antes de `ProtegeRotasDeMfa` e `ExigePasskeyDoAdministrador`, depois do `AuthenticationMiddleware` e do `AccountMiddleware`.
- **Travas:** os três serviços fazem `select_for_update` da conta-alvo e revalidam papel e situação depois da trava; `_travar` devolve a situação anterior para a auditoria. Duas remoções simultâneas: a segunda espera a trava e recebe `ModeracaoInvalida`. Suspensão e remoção simultâneas terminam em `removida` com banimento.
- **Banimento idempotente na transação:** `remover` só insere em `EmailBanido` se o e-mail ainda não estiver banido (caso de e-mail banido por outra via), para a remoção não falhar por unicidade.
- **Sinais com `send`, não `send_robust`:** um receptor que falha desfaz a moderação (A-3).
- **Tela:** compradores e fornecedores (sem o administrador), com os botões da tabela de alvos. Suspender e reativar são `POST` com CSRF; remover abre a página de confirmação ("A remoção é definitiva e bane o e-mail."). Recusas do serviço viram mensagem ("Esta ação não é permitida para esta conta."), ação desconhecida ou conta inexistente dá 404.
- **Decisão em aberto D-1 do spec (não bloqueia):** não existe suspensão de fornecedor nesta fatia; só remoção.

## Limitações

- Nenhuma revisão independente feita ainda.
- Os efeitos da suspensão sobre interesses e pedidos não pagos se conectam ao sinal `conta_suspensa` nas etapas E05 e E08 (spec).


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

### Matriz da fatia

A-1 a A-19: serviços, permissões, sinais transacionais, rollback, banimento, preservação de histórico, isolamento de sessões e corridas internas cobertos. A-15/A-16 repetem 10 corridas cada. A integração com a gravação de perfil não preserva a situação final (E02-R01), embora os serviços de moderação isoladamente passem.

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

### Pendência de integração: E02-R01

A moderação usa trava e grava somente a situação, porém um POST de perfil já em andamento pode gravar depois uma cópia anterior da conta inteira e restaurar `ativa`. A reprodução está detalhada em E02-09/review.md. No caso de remoção, o EmailBanido continua existindo e ainda bloqueia login: não foi demonstrado contorno do banimento, mas a situação fica inconsistente. No caso de suspensão, não há banimento, e a conta volta a satisfazer `pode_adicionar_interesse` sem reativação administrativa. Os serviços isolados passaram; o aceite integrado da fatia está REPROVADO até a gravação do perfil preservar a moderação.

## Correção E02-R01 (integração) conforme o spec.md (implementador)

Os serviços de moderação não mudaram. A invariante explícita ("só a moderação altera `situacao`; toda outra gravação de uma conta existente usa `update_fields` restrito ou relê a conta com `select_for_update` na mesma transação") agora vale em todos os caminhos: perfil (E02-09, A-20 a A-25), redefinição de senha (E02-02, A-25) e vínculo com o Google (E02-07, A-21). O inventário das gravações de `Conta` com a proteção de cada uma está em `docs/specs/E02-09/review.md`. O aceite integrado desta fatia depende desses critérios, todos verdes.

**Verificação (após as três correções do E02-R01):**

```
test_perfil_concorrencia.py + test_contas_google_concorrencia.py (3 execuções seguidas) -> 11 passed em todas
uv run pytest -q     -> 634 passed
uv run ruff check .  -> All checks passed
uv run mypy .        -> Success: no issues found in 123 source files
```


## Revalidação independente — 0178d62 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

R01 encerrado na integração da moderação: perfil, recuperação e vínculo Google não restauram situação antiga. Serviços desta fatia preservados; regressão de moderação verde. D-1 permanece fora do escopo.

Evidências comuns: `uv run pytest -q` — **634 passed em 70,20 s**; probes independentes — **7 passed em 2,20 s**; lint, formatação, tipos e checks Django sem erros. Comandos, encerramento dos quatro achados, evidência TDD e limites em [E02-10/review.md](../E02-10/review.md), seção de revalidação do commit `0178d62`. Os pareceres anteriores acima são históricos.
