# E02-04 — Revisão

Estado atual: **APROVADO** no commit `8f4dc36` (revisão independente ao final). A E02 global está **REPROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** modelo `Convite` só com campos (sem restrições, `situacao` fixa em `pendente`), `apps/contas/convites.py` com `emitir_convite` que não grava nada e as exceções, `ConviteFactory` em `tests/fabricas.py`, configuração `ORIGEM_PUBLICA`, `tests/apoio/email_falho.py` e o passo `administrador_logado` em `tests/apoio/admin_fluxos.py`. Suíte antes do Red: verde (`295 passed`).

**Red** (`uv run pytest` nos quatro arquivos de teste desta fatia, com o andaime):

```
44 failed, 5 passed
```

Falhas de asserção: `404 == 200/302/403` (tela sem rota), `DID NOT RAISE EmailEmUso`, `DID NOT RAISE IntegrityError` (sem restrições no banco), `DID NOT RAISE PermissionDenied`, `AssertionError: assert 'pendente' == 'expirado'` (situação), `IndexError` ao procurar o e-mail na caixa de saída, `assert None != None`. Os 5 que já passavam são cobertura.

**Green:** `apps/contas/models.py` (`Convite` com `CHECK`s, `UNIQUE` do hash e `situacao`), `apps/contas/convites.py`, `FormularioConvite`, `convites_administracao`, rota `/administracao/convites/`, templates `convites/*` e migração `0002_convite`.

**Refactor:** ordem dos métodos do modelo (ruff DJ012), tipagem e formatação.

## Verificações (final)

```
uv run pytest -q                                  -> 344 passed em 56 s
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 86 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
```

## Matriz

| Critério | Teste |
|---|---|
| A-1 a A-10 | `test_convites_emissao.py` (A-7 também `acceptance`, cenário 80) |
| A-11, A-12 | `test_convites_permissoes.py` |
| A-13, A-14, A-15 | `test_convites_consulta.py` |
| A-16 | `test_convites_modelo.py` |
| A-17, A-18, A-19 | `test_convites_emissao.py` |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Origem do link:** `emitir_convite` ganhou o parâmetro opcional `origem` (a view passa `request.build_absolute_uri("/")`). Sem requisição vale `settings.ORIGEM_PUBLICA`, lida do ambiente com padrão `http://localhost:8000`. **Em produção `ORIGEM_PUBLICA` é obrigatória e sem padrão**, como `EMAIL_BACKEND` e `DEFAULT_FROM_EMAIL`; por isso `test.py` a define com `setdefault` (o teste da E01-02 importa `prod` no processo) e `test_configuracao_producao.py` passou a incluí-la no ambiente mínimo.
- **Restrições no banco (além do pedido explícito):** `convite_validade_24h` (`expira_em = emitido_em + 24h`) garante a invariante "exatamente 24 horas" mesmo por SQL; `convite_email_ja_normalizado` repete a normalização da conta; `convite_token_unico` é o `UNIQUE` do hash.
- **E-mail em `transaction.on_commit`:** o resultado do envio é devolvido no atributo (não coluna) `Convite.email_enviado` (`True`, `False` ou `None` se a transação externa ainda estiver aberta). A tela só mostra "Convite criado, mas o e-mail não pôde ser enviado..." quando for `False`. Por isso os testes de tela usam `django_db(transaction=True)`: com commit real o callback roda antes do retorno da view.
- **Log de falha:** registra só o `pk` do convite e o nome da classe da exceção. Nem e-mail nem token (o texto da exceção do SMTP pode conter o endereço).
- **Erros do serviço:** reaproveita `EmailInvalido` e `EmailEmUso` (E02-01); `EmailBanidoErro` e `ConviteInvalido` (papel/fornecedor) são novos.
- **Papel do convite no modelo:** `papel` usa as mesmas opções de `Papel`; a recusa de `administrador` vem do `CHECK` (e portanto de `full_clean` via `validate_constraints`), e o serviço a recusa antes.
- **Situação:** `prazo_encerrado(agora(), expira_em)` (E01-03), limite exclusivo: no instante exato de `expira_em` o convite já está expirado (A-13).
- **Fábrica:** `ConviteFactory` reaproveita o único administrador existente, para respeitar `conta_administrador_unico`.
- **Datas na tela:** filtro `date` do Django converte para `TIME_ZONE = America/Sao_Paulo`.

## Limitações

- Nenhuma revisão independente feita ainda.
- O link `/convite/<token>/` só passa a existir na E02-05; o teste confere apenas o texto do link no e-mail.
- Sem cancelamento de convite e sem registro estruturado de entrega (E04), conforme o spec.


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

### Matriz da fatia

A-1 a A-19: emissão, permissões, hash do token, 24 h, fronteiras, lista, auditoria, rollback e falha de envio cobertos. O envio em on_commit e os logs sem token/e-mail foram conferidos no código.

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
