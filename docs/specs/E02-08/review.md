# E02-08 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

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
