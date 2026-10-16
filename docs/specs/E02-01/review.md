# E02-01 — Revisão

Estado atual: **APROVADO** no commit `0178d62` (revalidação independente ao final). A E02 global está **APROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

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


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

### Matriz da fatia

A-1 a A-20: normalização e propriedades, unicidade no Postgres, corrida de papéis, restrições, banimento imutável, comando administrativo e compatibilidade com E01. A alteração dos testes de auditoria limita-se à criação do usuário e imports, sem mudança de asserções, como autorizado.

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

Nenhum achado próprio impede o aceite desta fatia no escopo entregue. A aprovação da E02 completa depende da correção dos achados E02-R01 a E02-R04.


## Revalidação independente — 0178d62 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

Aprovação anterior mantida; sem alteração de implementação ou critérios desta fatia. Regressão coberta pela suíte completa.

Evidências comuns: `uv run pytest -q` — **634 passed em 70,20 s**; probes independentes — **7 passed em 2,20 s**; lint, formatação, tipos e checks Django sem erros. Comandos, encerramento dos quatro achados, evidência TDD e limites em [E02-10/review.md](../E02-10/review.md), seção de revalidação do commit `0178d62`. Os pareceres anteriores acima são históricos.
