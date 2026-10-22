# E09-01 — Parecer independente sobre 34f9547

**Veredito: REPROVADO.**

Base: `34f9547ae7962687ed96997e3338914f985a277f`, branch `e09-implementacao`, revisão independente em 2026-10-22. Lidos documentos-base funcional v1.6 e infraestrutura v1.7, AGENTS.md, especificações, critérios, código, testes e registros das oito fatias. Histórico do implementador preservado integralmente abaixo.

Verificações independentes:

- `uv run pytest -q`: **2398 passed in 273.67s**, sem filtro, PostgreSQL e banco separado do simulador.
- `uv run ruff check .`: passou; `uv run ruff format --check .`: 328 arquivos conformes.
- `uv run mypy .`: 391 arquivos sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais, fora da suíte versionada: **9 failed in 8.57s**, pelos defeitos descritos no [parecer consolidado](../E09-08/review.md), que contém o código completo para reprodução.

Não foram alterados código de produção nem testes versionados. Testes verdes dos critérios existentes não bastam para aprovar as interações financeiras. O revisor não presenciou os ciclos TDD históricos; conferiu os registros e não trata mutação posterior como Red anterior à implementação.

## Matriz e achados

A-1–A-18: testes existentes verdes, incluindo fluxos F1–F15, segregação, imutabilidade ORM/SQL, auditoria e corridas do lançador. Nenhum defeito adicional demonstrado no lançador isolado. R02 mostra que ordenar as travas no lançador não corrige a ordem já adquirida pelos serviços. **R08 bloqueia o gate TDD:** extrato implementado antes do teste, por declaração expressa. A falha de A-2 por conta inexistente no andaime também não demonstra Red da proteção de imutabilidade; conferir a evidência anterior das proteções ORM/SQL.

---

# E09-01 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- App novo `apps/financeiro`: `models.py` (`ContaFinanceira`, `MovimentoFinanceiro`, `TransferenciaFinanceira`, `Destinacao`, `Componente`, `TipoDeMovimento`), `livro.py` (`conta`, `lancar`, `saldo`, `extrato`, `saldo_total_esperado`, as quatro exceções e `EXTERIOR`), migração `0001_livro_razao.py` (com a trigger só-inserção nas três tabelas) e o registro em `INSTALLED_APPS`.
- Testes: `tests/tecnicos/test_financeiro_livro.py`, `tests/tecnicos/test_financeiro_concorrencia.py`, `tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py`. Apoio: `tests/apoio/financeiro.py`.

## Andaime (exceção técnica)

Antes do Red: o app com os modelos e a migração, as exceções e as assinaturas de `conta`, `lancar`, `saldo` e `saldo_total_esperado` com corpo trivial (`conta` devolve uma conta não salva, `lancar` devolve um movimento não salvo, `saldo` devolve zero). Não há comportamento testável no andaime; ele só deixa os testes importáveis, para a falha ser por asserção.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_livro.py tests/tecnicos/test_financeiro_concorrencia.py tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py -q -p no:cacheprovider` contra o andaime: **61 falharam, 1 passou** (o teste de que o movimento do sistema não grava auditoria, que passa com o andaime).

Na primeira execução, 10 das falhas (o A-8 parametrizado) não eram por asserção, e sim por artefato do andaime (a conta e o movimento não salvos): `TypeError: Model instances without primary key value are unhashable` e, depois do primeiro ajuste, `ValueError: ... needs to have a primary key value`. Corrigi só a **forma** do teste, sem mudar o que ele exige: o `antes` do A-8 passou de dicionário a lista de pares, e a asserção dos saldos veio antes da contagem de transferências do movimento. Depois disso, todas as falhas são asserções (`AssertionError`, `DID NOT RAISE`).

| Critério | Teste | Resultado do Red |
|---|---|---|
| A-1 | `test_entrada_de_pagamento_em_tres_componentes` | `assert Decimal('0.00') == Decimal('100.00')` |
| A-2 | `test_movimentos_e_transferencias_so_aceitam_insercao` | falha por asserção (a conta do andaime não existe) |
| A-3 a A-6 | `test_tarifa_...`, `test_dinheiro_do_fornecedor_...`, `test_obrigacao_do_fornecedor_so_vai_...` (16 casos), `test_custodia_nao_vai_...` | `DID NOT RAISE MovimentoProibido` |
| A-7, A-8 | `test_ressalva_da_p2_...`, `test_todos_os_fluxos_da_lista_sao_aceitos[1..15]`, F11 | saldos zerados |
| A-9, A-10 | `test_saldo_insuficiente_nao_grava_nada`, `test_despesas_a_cobrir_...` | `DID NOT RAISE SaldoInsuficiente`; `Decimal('0.00') == Decimal('-1.50')` |
| A-11 | `test_valor_invalido_...` (4), `test_transferencias_invalidas_...`, `test_administrador_exige_justificativa` (2) | `DID NOT RAISE MovimentoInvalido` |
| A-12 | `test_repetir_a_chave_...`, `test_repetir_a_retirada_...` | `DID NOT RAISE MovimentoConflitante` |
| A-13 | `test_movimento_do_administrador_guarda_autor_e_auditoria` | asserção do movimento gravado |
| A-17, A-18 | `test_lancar_fora_de_transacao_...`, `test_saldo_total_esperado_ate_um_instante` | `DID NOT RAISE TransactionManagementError`; `Decimal('0.00') == Decimal('125.00')` |
| A-14 a A-16 | `test_financeiro_concorrencia.py` | falham por asserção (nada foi gravado) |

## Green, em três passos (a regra da concorrência: verde funcional, Red da corrida, trava)

1. **Verde funcional sem trava.** `lancar` completo (validação, lista fechada, idempotência, saldo, gravação, auditoria), sem `select_for_update`. Mesmo comando: **3 falharam, 59 passaram**. Das falhas, A-14 e A-15 são o **Red das corridas**, por asserção: no A-14 as duas retiradas passam (`sum(e is None ...) == 1` falha) e no A-15 `[None, IntegrityError('duplicate key ... financeiro_movimentofinanceiro_chave_key')]` falha em `all(r.excecao is None ...)`. A terceira falha era o `_saldos()` do cenário 32 contando contas vazias criadas durante as tentativas (defeito do meu teste); passei a comparar só os saldos não nulos, que é o que "nenhuma escrita de dinheiro" quer dizer.
2. **Trava na ordem de aparição das contas** (e a conferência da chave sob a trava): **1 falhou, 61 passaram**. A-14 e A-15 verdes. A-16 é o **Red da ordem**, e o critério pede justamente ausência de impasse: `OperationalError('deadlock detected' ...)` em uma das duas transações.
3. **Trava em ordem crescente de `pk`:** os três arquivos, **62 passaram**.

## Desvios declarados

- **`extrato` sem teste antes do código.** A spec lista `extrato`, mas nenhum critério o cobre, e eu o escrevi junto com `saldo`. Depois escrevi `test_extrato_lista_as_transferencias_da_conta_com_o_saldo_acumulado` e provei a sensibilidade por mutação (não é Red): com `extrato` devolvendo `[]`, o teste falha em `assert [] == [(98, Decimal('100.00'), ...)]`; restaurado, o arquivo inteiro passa (**58 passed**).
- **A chave das contas.** A spec fala em "destinação e chave" sem fixar o formato. Decisão técnica: a conta guarda as chaves em colunas (rodada, ciclo, comprador, fornecedor, componente, obrigação) e um texto derivado, com `UNIQUE (destinacao, chave)`. A conta de obrigação com comprador guarda o número da obrigação (o modelo nasce na E09-04) e, opcionalmente, rodada, ciclo e comprador, de que as regras F8 a F10 dependem.
- **Justificativa.** A spec exige justificativa só do administrador; exigi não vazia de todo movimento (Infra 3.1 pede justificativa em todo lançamento).
- **F11 literal.** `receita_servico` e `reserva` podem ir para `despesas_a_cobrir`, `frete` e `obrigacao_comprador` com os tipos `cobertura_de_despesa` ou `financiamento_de_obrigacao`, sem restringir o par tipo-destino além do que a tabela diz.
- **Idempotência por conteúdo.** O conteúdo comparado é o tipo, a origem e as transferências (conta, conta, valor); a justificativa e o autor ficam de fora.

## Verificação

- Os três arquivos da fatia mais a varredura de `float` (`tests/tecnicos/test_varredura_float.py`): `uv run pytest tests/tecnicos/test_financeiro_livro.py tests/tecnicos/test_financeiro_concorrencia.py tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py tests/tecnicos/test_varredura_float.py -q -p no:cacheprovider` → **67 passed**.
- `ruff check`, `ruff format --check`, `mypy` e `makemigrations --check` limpos no commit da fatia.
- A suíte completa, sem filtro, é registrada na verificação final da E09 (E09-08), depois da última fatia.

## Correção posterior (2026-10-22)

A suíte completa, rodada depois do commit da fatia, acusou `tests/tecnicos/test_pagamentos_fronteiras.py::test_so_a_sincronizacao_escreve_nos_registros_de_pagamento`: a heurística da melhoria M-2 (coocorrência do texto `PagamentoNoProvedor` com uma chamada de escrita) pegou o docstring de `apps/financeiro/livro.py`, que citava a classe. Corrigi só o texto do docstring (agora diz "o pagamento no provedor"), sem mudar o teste nem o comportamento. O teste passa de novo. É o mesmo atrito já registrado na M-2: os módulos que escrevem precisam evitar citar essas classes.

## Não conformidade de TDD (E09-R08)

Tratamento decidido pelo responsável pelo projeto em 2026-10-22: o mesmo das correções E05-R04, E06-R05 e E08-R06. O registro anterior fica como estava.

| Critério | O que aconteceu |
|---|---|
| `extrato` (sem critério próprio) | escrito junto com `saldo`; o teste veio depois |
| A-2 | o Red falhou porque a conta do andaime não existia, e não porque a mutação fosse permitida; a ordem em que a recusa do ORM e a trigger entraram não está registrada |

**Evidência histórica procurada (passo 1 do tratamento).** Verifiquei o histórico git (os commits de origem das fatias (`cbe5ae3` no livro, `917f375` nas obrigações, `3f7e6e7` na conciliação) trazem testes e produção juntos, sem commit só de testes antes do código), os logs guardados e o registro anterior deste arquivo. Não há saída registrada no momento que mostre o teste falhando pelo motivo do critério antes do código de produção correspondente. Nenhum critério saiu da lista.

**Nenhum texto desta seção afirma que houve Red nesses critérios.** O que existe é a prova de sensibilidade abaixo, que **não é Red**: ela mostra que o teste de hoje detecta a remoção da proteção, não que ele tenha falhado antes de ela existir.

Mutações refeitas sobre o código de `1ad1944`. Em cada uma: o trecho é alterado, o comando roda com os arquivos inteiros e sem `-k`, a falha é registrada e o arquivo volta ao original (conferido com `git status` limpo e a execução verde de novo).

### Sensibilidade (mutação), não Red

Comando das cinco mutações: `uv run pytest tests/tecnicos/test_financeiro_livro.py tests/tecnicos/test_financeiro_concorrencia.py tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py -q -p no:cacheprovider`. Restaurado, o comando dá **86 passed** (confirmado depois de cada mutação).

| Critério | Trecho mudado | Resultado mutado |
|---|---|---|
| `extrato` | `apps/financeiro/livro.py`: `return linhas` → `return []` | **1 failed, 85 passed**: `test_extrato_lista_as_transferencias_da_conta_com_o_saldo_acumulado`, `assert [] == [(98, Decimal...mal('75.00'))]` |
| `extrato` | `apps/financeiro/livro.py`: `.order_by("movimento__pk", "pk")` → `.order_by("-movimento__pk", "-pk")` | **1 failed, 85 passed**: o mesmo teste, `assert [(100, ...)] == [(98, ...)]` |
| A-2, caminho do ORM | `apps/financeiro/models.py`: `MovimentoFinanceiro` ganha `save()` que chama `models.Model.save` direto (sem a recusa) | **1 failed, 85 passed**: `test_movimentos_e_transferencias_so_aceitam_insercao`. Limite declarado: quem barrou foi a trigger do banco (`IntegrityError: tabela financeiro_movimentofinanceiro só aceita inserção`) e o teste, que espera `RegistroImutavel`, falhou por exceção de outro tipo, e não por `assert` |
| A-2, caminho do SQL | `apps/financeiro/migrations/0001_livro_razao.py`: retirada a linha `instalar_protecao_so_insercao('financeiro_movimentofinanceiro')` | **1 failed, 85 passed, 1 error**: o mesmo teste, `Failed: DID NOT RAISE DatabaseError` (linha 136). O erro extra é um `ForeignKeyViolation` na limpeza do banco de teste, que só aparece com a mutação; restaurado, não há erro |

## Correção E09 (2026-10-22): Red → Green dos critérios novos

Critérios desta fatia: **A-19, A-20 e A-21** (a guarda da ordem das travas e a regra única).

- **Andaime (exceção técnica, sem comportamento):** no commit do Red, `e3733ad`, a classe `OrdemDeTravasViolada` foi criada em `apps/financeiro/livro.py` (+4 linhas), só para o teste importar. A guarda em si não existia.
- **Red** (`e3733ad`, código ainda no estado de `34f9547`): rodei os seis arquivos de teste financeiros inteiros, sem `-k`: **18 failed, 129 passed**. Log guardado em `scratchpad/red_e09.log` (fora do repositório). Para esta fatia: A-19 `test_travar_fora_de_ordem_e_recusado_antes_de_travar`: `Failed: DID NOT RAISE OrdemDeTravasViolada`.
- **A-20 passou já no Red.** `test_travar_de_novo_e_o_registro_recomeca_em_cada_transacao` é o lado positivo da guarda e o código antigo já aceitava travar de novo. Declaro que ele não teve Red; o Red da guarda vem do A-19.
- **Green:** `742a679` (guarda no `_travar_conta`, `travar_contas`) fez o A-19 e o A-20 passarem. `a66a663` aplicou a regra única às operações.
- **A-21 (suíte completa com a guarda ativa):** a guarda acusou inversões reais, corrigidas no código: a apuração, na cobertura automática, não travava `despesas_a_cobrir` no conjunto; e o receptor travava a entrada e só depois a tarifa. Acusou também setups de teste que juntavam várias operações numa transação só; dividi cada um em transações separadas (`_tres_contas` no livro, a fixture `dia` da conciliação, o A-16 da concorrência e o `semear` do apoio, que agora trava o conjunto antes). Mudou ainda a asserção do cenário 39, de "nenhuma conta de receita" para "nenhuma com saldo diferente de zero", porque a regra "criar antes de travar" cria a conta vazia. Nenhum teste foi afrouxado quanto ao que exige.
- **Limite da guarda:** em teste do tipo `TestCase`, sem transação própria, a guarda fica desligada (só o bloco do próprio `TestCase` existe). Os testes de concorrência usam transações reais e ficam cobertos.
- **Verificação (`1ad1944`):** `uv run pytest -q -p no:cacheprovider` sem filtro: **2418 passed**.
