# E02-10 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** `apps/contas/permissoes.py` com `Politica`, os decoradores e mixins como passagem direta (sem gravar política), `POLITICAS_DE_TERCEIROS` vazia, `rotas_sem_politica` devolvendo um marcador (para a varredura falhar até existir comportamento) e `politica_da_view` devolvendo `None`; `tests/apoio/views.py` (carrinho, pagamento, meus pedidos e painel do fornecedor, com contador de chamadas) e as quatro rotas `/teste/...` em `tests/apoio/urls.py`; `tests/apoio/urls_sem_politica.py` e `tests/apoio/estrategias.py`. Suíte antes do Red: `548 passed`.

**Red** (`uv run pytest` nos cinco arquivos de teste desta fatia, com o andaime):

```
31 failed, 15 passed
```

Falhas de asserção: `assert 200 == 403` (a rota de compra respondia a fornecedor, suspenso e administrador), `DID NOT RAISE PermissionDenied`, `AttributeError: 'WSGIRequest' object has no attribute 'fornecedor_vinculado'`, `DID NOT RAISE DatabaseError` (sem a trigger do papel), `assert ['(andaime)'] == []` e `assert None == Politica.X` na varredura. Os 15 que passaram são cobertura (por exemplo, a varredura estática de `email__iexact`, que já não encontra ocorrências).

**Green:** `permissoes.py` completo, `papel_imutavel.py` + migração `0005_papel_imutavel`, política declarada nas views existentes, `POLITICAS_DE_TERCEIROS` preenchida.

**Ajustes de teste durante o Green (código inalterado):** o teste de propriedade passou a capturar os callbacks de `on_commit` (o e-mail do link sai em `on_commit`); o teste do cenário 61 confere nome e papel em `/inicio/` e e-mail em `/perfil/` (a página inicial da E02-02 não mostra o e-mail); o teste do mixin de fornecedor ganhou a marca de banco.

**Refactor:** tipagem (`View = Callable[..., HttpResponseBase]`, porque a view de avatar devolve `FileResponse`) e ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 594 passed em 68 s
test_normalizacao_varredura.py (3 execuções seguidas, hypothesis) -> 10 passed em todas
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 120 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
manage.py check (test)                            -> 0 issues
```

## Matriz

| Critério | Teste |
|---|---|
| A-1, A-2 | `test_permissoes_papeis.py` (`tecnico`, T-25; GET/POST/PUT/PATCH/DELETE, com e sem `HX-Request`) |
| A-3, A-4, A-5, A-6, A-7 | `test_permissoes_papeis.py` |
| A-8 | `tests/aceitacao/test_cenario_61_contas_independentes.py` |
| A-9 | `test_fornecedor_sem_vinculo_e_recusado_em_profundidade` |
| A-10, A-11 | `test_permissoes_politica_rotas.py` (varredura de `config.urls` e `tests.apoio.urls`; URLconf com rota esquecida) |
| A-12, A-13 | `tests/aceitacao/test_cenario_62_papel_imutavel.py` |
| A-14, A-15, A-16 | `test_normalizacao_varredura.py` (`tecnico`, T-37) |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Política gravada na view:** cada decorador (`publica`, `exige_login`, `exige_comprador`, `exige_comprador_ativo`, `exige_fornecedor`) embrulha a view e grava `politica_de_acesso`; `somente_administrador` e `exige_reautenticacao_por_passkey` (E02-03) passaram a gravar `Politica.ADMINISTRADOR`. Nos mixins, `as_view()` grava o atributo na view resultante (inclusive no `SomenteAdministradorMixin`).
- **Recusas:** anônimo é redirecionado para `/entrar/` (com `next`); papel ou situação errados levantam `PermissionDenied` (403 sem dados da rota), antes da view e para qualquer método. `exige_fornecedor` exige `fornecedor_id` preenchido e expõe `request.fornecedor_vinculado`.
- **`POLITICAS_DE_TERCEIROS`** lista rota por rota (sem curingas): `account_login`, `account_logout`, `account_reauthenticate`, as quatro de recuperação, as rotas `mfa_*` usadas e `google_login`/`google_callback`. A entrada `mfa_remove_webauthn` cobre a rota original do allauth, que fica atrás da nossa `remover_passkey` (mesmo nome, já declarada).
- **Varredura:** percorre o `URLResolver` recursivamente (`get_resolver(urlconf)`), é exposta como `rotas_sem_politica(urlconf)` e usada pelo teste com `config.urls` e `tests.apoio.urls`; uma rota sem política aparece como `caminho (nome)`. `entradas_de_terceiros_inexistentes` acusa nomes que não existem.
- **Rotas de teste fora de `config/urls.py`:** ficam em `tests/apoio/urls.py` (usadas com `pytest.mark.urls`), com as views em `tests/apoio/views.py`.
- **Trigger de imutabilidade do papel:** `BEFORE UPDATE OF papel ... WHEN (OLD.papel IS DISTINCT FROM NEW.papel)`. O `WHEN` é necessário porque o `save()` do Django reenvia a coluna `papel` com o mesmo valor; sem ele toda gravação comum falharia. O teste `test_atualizacao_sem_mudar_o_papel_continua_permitida` cobre isso, e o ORM (`update(papel=...)`) também é recusado.
- **T-37, propriedade:** cada exemplo roda dentro de uma transação desfeita ao final (`transaction.set_rollback(True)`), com e-mails gerados por `hypothesis` (`tests/apoio/estrategias.py`). Cobre unicidade da conta, emissão de convite (uso e banimento), consumo de convite (e-mail em uso e banido), login por senha, pedido de link, recuperação de acesso, Google e `email_banido`, e verifica que o alias com `+` continua sendo outro endereço em todos.
- **T-37, estática:** `analisar_codigo` usa o AST de cada arquivo de `apps/` (exceto migrações) e acusa `*email*__iexact` (argumento nomeado ou texto) e `.lower()`/`.casefold()` sobre expressões que mencionam e-mail fora de `apps/contas/emails.py`. O teste A-16 prova que ela acusa um arquivo temporário com `email_normalizado__iexact`.

## Revisão manual do terceiro item do T-37 (consultas por `email_normalizado`)

Item que o spec reserva à revisão porque a análise estática completa não é viável. Levantamento feito com `grep -rn "email_normalizado=" apps` (migrações excluídas) em 2026-10-16:

| Local | Valor usado na consulta | Veredito |
|---|---|---|
| `adaptadores.py:169` (Google) | `email` vindo de `_email_verificado`, que chama `normalizar_email` | normalizado |
| `convites.py:97` e `:107` (emissão) | `normalizado = normalizar_email(email)` | normalizado |
| `convites.py:140` e `:176` (consumo) | `convite.email_normalizado`, gravado já normalizado (`Convite.save` + `CHECK`) | normalizado |
| `emails.py:38` (`email_banido`) | `normalizar_email(texto)` | normalizado |
| `link_de_acesso.py:50` (pedido) | `normalizado = normalizar_email(email)` | normalizado |
| `criar_administrador.py:31`, `:36` | `email = normalizar_email(...)` | normalizado |
| `models.py:133` (`Conta.save`) | `self.email_normalizado` depois de `normalizar_email` | normalizado |
| `moderacao.py:82`, `:84` (remoção) | `travada.email_normalizado` (lido do banco; `CHECK` de normalização) | normalizado |
| `forms.py:37` | monta uma `Conta` em memória, sem consulta | n/a |

Nenhuma consulta com valor não normalizado foi encontrada.

## Limitações

- Nenhuma revisão independente feita ainda.
- As rotas reais de carrinho, pagamento e fornecedor chegam nas etapas E05, E08 e E13; os decoradores estão provados nas rotas de teste. O isolamento de dados entre fornecedores dentro das consultas fica com essas etapas (spec).
