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
