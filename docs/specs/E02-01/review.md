# E02-01 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, registrado como exceção técnica):** apps `apps.contas` e `apps.fornecedores`, modelos `Conta`, `EmailBanido` e `Fornecedor` só com campos (e a `UniqueConstraint` do e-mail, exigida pela checagem `auth.E003` do Django), `normalizar_email` e `email_banido` como stubs, comando sem lógica, `tests/fabricas.py`, `AUTH_USER_MODEL` e remoção de `django.contrib.admin`. O andaime existe para o Red sair por asserção, e não por erro de importação. Com ele, a suíte da E01 seguiu verde (143 passed).

**Red** (`uv run pytest tests/tecnicos/test_contas_*.py -q`, com o andaime):

```
37 failed, 11 passed
```

As falhas são de asserção ou de `DID NOT RAISE` (ex.: `assert 'Ana@Exemplo.com' == 'ana@exemplo.com'`, `DID NOT RAISE EmailInvalido`, `DID NOT RAISE IntegrityError` para cada restrição do banco, `DID NOT RAISE CommandError`), além de `ValidationError: {'password': ...}` em `full_clean` antes da senha inutilizável. Os 11 que passaram já no andaime são cobertura: unicidade pelo `UNIQUE`, `fornecedor` com vínculo válido, A-18 (admin ausente), etc.

**Green:** `apps/contas/emails.py`, `apps/contas/models.py`, `apps/contas/management/commands/criar_administrador.py`, migrações `fornecedores/0001` e `contas/0001` (com `instalar_protecao_so_insercao("contas_emailbanido")`).

**Refactor:** remoção de `noqa` desnecessários e formatação (ruff).

## Compatibilidade (A-20)

Troca autorizada pelo spec, só da **criação do usuário** em `tests/tecnicos/test_nucleo_auditoria.py`, sem alterar nenhuma asserção:

```
-    return get_user_model().objects.create_user(username="ana", password="x")  # noqa: S106
+    return ContaFactory()
-        registrar_auditoria(get_user_model()(username="novo"), "x.y", objeto, {})
+        registrar_auditoria(ContaFactory.build(), "x.y", objeto, {})
```

(mais o `import` de `ContaFactory` e a remoção do `import` de `get_user_model`). Suíte completa depois: 191 passed, incluindo todos os testes da E01.

## Verificações (final)

```
uv run pytest -q                                  -> 191 passed em 42,3 s
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 59 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
manage.py check (test)                            -> 0 issues
test_contas_modelo.py (3 execuções seguidas)      -> 19 passed em todas
```

## Matriz

| Critério | Teste |
|---|---|
| A-1 a A-5 | `test_contas_emails.py` (A-4 e A-5 com hypothesis) |
| A-6 | `test_conta_recusa_email_em_uso_com_variacao_de_caixa_e_espacos` |
| A-7 | `test_banco_recusa_email_nao_normalizado` (+ vazio) |
| A-8 | `test_conta_corrida_mesmo_email_normalizado_com_papeis_diferentes` (10 repetições, `executar_em_paralelo`) |
| A-9, A-10, A-11 | `test_banco_recusa_*` (fornecedor/papel, segundo administrador, administrador inativo) |
| A-12 | `test_is_active_depende_so_de_a_conta_nao_estar_removida` |
| A-13 a A-15 | `test_contas_banimento_modelo.py` |
| A-16, A-17 | `test_contas_criar_administrador.py` (inclui código de saída ≠ 0 via `run_from_argv`) |
| A-18 | `test_admin_do_django_ausente` |
| A-19 | `test_fabricas_geram_contas_validas` |
| A-20 | seção "Compatibilidade" acima |

## Decisões técnicas

- Trait da fábrica chamado `fornecedor`, conforme a interface do spec. Ele preenche `fornecedor_id` (e não `fornecedor`), porque o factory-boy acusa definição cíclica quando o trait e o campo têm o mesmo nome.
- Senha inutilizável aplicada em `Conta.__init__` para instâncias novas, de modo que `full_clean` (que exige `password` não vazio) funcione antes do salvamento.
- Em corrida, a violação de `conta_email_unico` é convertida em `EmailEmUso`, dentro de um ponto de salvamento (`transaction.atomic`) que não contamina a transação externa.
- `clean()` normaliza e-mail e nome; `save()` também (a aplicação nunca grava e-mail sem normalizar).
- Na `EmailBanido`, as restrições têm nomes próprios: `emailbanido_email_unico` e `emailbanido_ja_normalizado`.
- `mypy`: nos testes, `disallow_untyped_calls = false` (chamadas às fábricas do factory-boy), e as fábricas usam `DjangoModelFactory[Modelo]`; os testes usam `Fábrica.create(...)`.
- O auxiliar `_email_banido` do teste do comando usa uma conta comum em `banido_por` (o banco não impõe que seja o administrador), para não colidir com a recusa "já existe administrador".
- O `CHECK` usa `lower(btrim(...))` conforme o spec; `btrim` do Postgres remove só espaços, enquanto o `strip()` do Python remove também tabulação/quebra de linha. Isso não cria brecha: o validador de e-mail recusa qualquer espaço em branco interno, e a aplicação sempre normaliza.

## Limitações

- Nenhuma revisão independente feita ainda.
- Sem rotas nem telas nesta fatia (spec).
