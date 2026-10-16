# E03-01 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** campos novos em `Fornecedor` (`email_pedido`, `minimo`, `prazo_entrega_dias`, `informacoes_frete`, `criado_em`) sem restrições, com a migração `0002` usando valores provisórios e `preserve_default=False` nos três obrigatórios; `apps/fornecedores/servicos.py`, `forms.py` e `views.py` sem lógica; rotas `/administracao/fornecedores/...` com `somente_administrador`; `ler_decimal_digitado` devolvendo zero; `FornecedorFactory` com os campos novos. Suíte antes do Red: `634 passed`.

**Red** (`uv run pytest` nos três arquivos novos e em `test_nucleo_valores.py`):

```
64 failed, 52 passed
```

Falhas de asserção: `DID NOT RAISE ValorInvalido` (leitura digitada), `assert 200 == 302` (cadastro sem efeito), `Fornecedor.DoesNotExist` (nada gravado), `'NoneType' object is not subscriptable` (sem formulário no contexto), `DID NOT RAISE IntegrityError` (sem os `CHECK`s).

**Green:** `ler_decimal_digitado` (E01-02), `CHECK`s `fornecedor_minimo_positivo` e `fornecedor_prazo_valido` (migração `0003_restricoes`), serviços `criar_fornecedor`/`editar_fornecedor`, formulários, as quatro views e os templates `fornecedores/*`.

**Refactor:** tipagem e ruff. Um caso do próprio teste mostrou uma ambiguidade real e foi tratado no Green (ver decisões).

## Verificações (final)

```
uv run pytest -q                                  -> 702 passed em 90 s
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 131 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
```

## Matriz

| Critério | Teste |
|---|---|
| A-1, A-2, A-3, A-4, A-5 | `test_fornecedores_cadastro.py` (cadastro pela tela; mínimo `150,00`/`150.00` e inválidos; nome, e-mail, prazo e frete) |
| A-6 | `test_servico_recusa_float_no_minimo` |
| A-7 | `test_banco_recusa_minimo_zero_e_prazo_fora_da_faixa` |
| A-8, A-9, A-10 | `test_fornecedores_tela.py` |
| A-11 | `test_auditoria_do_cadastro_nao_tem_o_email` |
| A-12 | `test_fornecedores_permissoes.py` |
| A-13 | `test_so_o_administrador_cria_e_edita_pelo_servico` |
| A-14, A-15, A-16 | `test_fornecedores_tela.py` |
| A-17 | `test_permissoes_politica_rotas.py::test_nenhuma_rota_do_projeto_fica_sem_politica` (existente, verde com as novas rotas) |
| `ler_decimal_digitado` | `test_nucleo_valores.py` (aceitos, recusados e tipos não texto) |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Serviços como única fonte das regras:** o formulário só lê e tipa; `criar_fornecedor` e `editar_fornecedor` validam tudo e levantam `ValidationError` com mensagens por campo; a view as transforma em erros do formulário. Assim a regra é a mesma na tela e em chamada direta.
- **Mínimo:** texto passa por `ler_decimal_digitado(texto, 2)`; `Decimal` por `dinheiro()`; `float`, `int` e `bool` são recusados (`ValorInvalido` virando erro do campo `minimo`). Piso de R$ 0,01 no serviço e no `CHECK`.
- **Ambiguidade tratada em `ler_decimal_digitado`:** em dinheiro, `1.000` ou `1,000` (grupo de três dígitos depois do separador) parece milhar e é recusado, junto com `1.000,00` (já exigido pelo spec). Para quantidade (3 casas) esse padrão é um decimal legítimo e continua aceito.
- **Edição:** a linha é relida com `select_for_update` e só as colunas alteradas são gravadas (`update_fields`), seguindo a invariante da correção E02-R01; edição sem mudança não grava auditoria; a auditoria lista os nomes dos campos alterados na ordem do modelo, nunca os valores. Campo fora da lista editável (inclusive `minimo`) chamado direto no serviço é recusado; na tela o `minimo` simplesmente não é campo do formulário e é ignorado.
- **Detalhe:** lista as contas de fornecedor do fornecedor (todas as situações, ordenadas por nome). Valores monetários são exibidos com `floatformat:2` (localizado em pt-BR).
- **Migração:** valores provisórios só para linhas existentes (fase 1, sem dados de produção); README orienta recriar o banco local.

## Limitações

- Nenhuma revisão independente feita ainda.
- A rodada ativa no detalhe do fornecedor entra com a E03-02 (spec).
