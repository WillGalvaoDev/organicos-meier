# E10-03 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Andaime (tipos da interface, `EstornoSimulado`, `MovimentoSimulado.id_estorno`, migração 0003, `NotImplementedError` no simulador) e testes A-1 a A-20 | `ceb68d7` | `uv run pytest tests/tecnicos/test_simulador_estornos.py` | **Red: 22 failed, 5 passed.** Os 5 são o A-17 parametrizado: a validação do `NovoEstorno` faz parte do andaime da interface e já recusa os valores e as chaves inválidas (regressão, sem Red próprio) |
| Estorno, consulta e controles no simulador | `c06d379` | o mesmo arquivo | **27 passed** |

A-18 (duas chamadas com a mesma chave em paralelo) está no mesmo arquivo, com `django_db(transaction=True)`; o `estornar` trava a cobrança antes de ler o restante, então o segundo pedido vê o primeiro e devolve o mesmo `id_estorno`.

## Decisões técnicas

- A conta do simulador não guarda a tarifa devolvida (L-7 aberta): o estorno debita só o valor estornado.
- A conclusão (`concluir_estorno`) usa `estado.concluir`, o mesmo caminho do estorno imediato, para que o movimento `devolucao` seja um só.
- A referência `docs/referencias/mercado-pago-api.md` (seção 10) foi atualizada nas duas linhas indicadas pela especificação.
- `tests/conftest.py`: prefixo `test_simulador_estornos` entra na lista dos testes com o banco do simulador.

## Revisão independente — agente 3 — 2026-10-30

Objeto: branch `e10-implementacao`, commit `9ce04adcdb1b6186ee5c932ef38170989e4d19cf`, comparado à especificação de `cd735c3`. Fontes: funcional v1.7, infraestrutura v1.8, `spec.md` e `acceptance.md` das sete fatias, AGENTS.md. Os registros do implementador acima foram preservados.

A suíte existente passou integralmente (**2600 passed in 270.31s**, execução independente iniciada em 2026-10-29). Isso não encerra os requisitos: os testes adicionais do revisor expõem os casos abaixo. Comandos, limitações, histórico TDD e reproduções estão no [parecer consolidado](../E10-07/review.md).

**Decisão da fatia: REPROVADO.**

| Critérios | Evidência | Resultado |
|---|---|---|
| A-1 a A-6, A-8 a A-16, A-19 e A-20 | `test_simulador_estornos.py`; estornos, chaves, estados, controles, tarifas e contestação | Cenários existentes verdes |
| A-7 e concorrência financeira | Insuficiência sequencial passa; saldo compartilhado entre pagamentos não é protegido | R02 aberto |
| A-17 | Cinco validações verdes desde o commit de andaime | Funcionalmente verdes; não demonstram Red anterior, R08 |
| A-18 | Duas chamadas do mesmo pagamento/chave passam | Não cobre pagamentos diferentes disputando saldo; R02 e limite histórico R08 |

### R02 — importante — dois pagamentos gastam o mesmo saldo do simulador

Referências: E10-03/spec.md, `estornar`, passo 8; A-7/A-18; AGENTS §6; `apps/simulador_pagamentos/provedor.py:99–145`.

Reprodução concorrente com PostgreSQL: dois pagamentos aprovados de 80,00; saldo liberado total reduzido a 100,00; ambos pedem estorno de 80,00. Uma barreira depois da leitura do saldo e antes da criação apenas sincroniza as threads, sem remover proteção. Observado: ambos concluem, dois débitos, saldo **−60,00**. Esperado: um conclui e o outro recebe `SaldoInsuficienteParaEstorno`. A trava é por cobrança; o recurso consumido é a conta comum. Serializar a validação e o consumo desse recurso, com teste que distinga recusa temporária de recusa definitiva.

Histórico: `ceb68d7 → c06d379` separa andaime e funcional, mas a validação de `NovoEstorno` já foi implementada no primeiro commit e A-18 falhou inicialmente por ausência da operação. Ver R08 consolidado; validação observável não se torna “sem comportamento testável” por estar na interface.

## Correção E10-R02 — agente 2 — 2026-10-30

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Refatoração: `_saldo_liberado(instante)` extraída (ponto de pausa) | `a87d480` | `tests/tecnicos/test_simulador_estornos.py` | 27 passed, sem mudar comportamento |
| Testes A-21 e A-22 | `005210b` | o mesmo arquivo | **Red: A-21** (`rb.excecao` é `None`; saldo liberado −60,00). A-22 verde (regressão da ordem das travas) |
| Trava do saldo | `d9c2ef3` | o mesmo arquivo e `test_devolucoes_execucao.py` | 55 passed |

Forma da trava: `pg_advisory_xact_lock(CHAVE_DA_TRAVA_DO_SALDO = 7151002)` na conexão do simulador, tomada depois da trava da cobrança e antes da leitura do saldo. A prova do parecer `test_saldo_compartilhado_em_estornos_concorrentes` fica substituída pelo A-21, como a spec manda.

## Não conformidade de TDD (R08) — E10-03 A-17 e A-18

O registro anterior fica preservado. **Não houve Red** para: A-17 (as validações de `NovoEstorno` entraram verdes no andaime `ceb68d7`) e A-18 (o Red foi a operação ausente, não uma corrida contra a operação sem a trava). Busca de evidência histórica (passo 1): commits `ceb68d7`/`c06d379` e os logs de execução guardados de 2026-10-29 não contêm a saída desses ciclos; nada encontrado. Tratamento decidido pelo responsável (2026-10-30): registro e sensibilidade por mutação.

**Sensibilidade (mutação), não Red** — comando: `uv run pytest tests/tecnicos/test_simulador_estornos.py` (arquivo inteiro, sem `-k`); cada arquivo restaurado depois:

| Mutação | Resultado |
|---|---|
| `NovoEstorno`: `if valor <= 0` → `if False` | 2 failed (`test_novo_estorno_invalido[valor0-k]`, `[valor1-k]`): `DID NOT RAISE ValueError` |
| `valor = dinheiro(...)` → `Decimal(str(...))` | 1 failed (`[valor2-k]`) |
| chave sem o mínimo de 1 caractere | 1 failed (`[valor3-]`) |
| chave sem o máximo de 64 | 1 failed (`[valor4-xxxx…]`) |
| `estornar` sem `travar=True` na cobrança | 1 failed, `test_dois_estornos_concorrentes_com_a_mesma_chave`: `IntegrityError` na chave de idempotência no lugar de `None` |
