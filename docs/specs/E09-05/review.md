# E09-05 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- `apps/financeiro/reserva.py` (`registrar_aporte`, `designar_reserva`, `desfazer_designacao`, `utilizar_reserva`, `situacao_da_reserva`, `itens_sem_cobertura`, `obrigacoes_sem_cobertura`, `avaliar_reserva` e as cinco exceções), `models.py` (`DesignacaoDaReserva`, `DesignacaoDesfeita`), migrações `0006_designacoes_da_reserva.py` (com a trigger só-inserção) e `0007_restricoes_das_designacoes.py`.
- Testes: `tests/tecnicos/test_financeiro_reserva.py` (A-1 a A-11, A-15 e as restrições), `tests/tecnicos/test_financeiro_concorrencia.py` (A-12 a A-14), `tests/aceitacao/test_cenario_29_aporte.py`, `tests/aceitacao/test_cenario_34_reserva_insuficiente.py`. Apoio: `obrigacao_de_teste` e `despesa_de_tarifa` em `tests/apoio/financeiro.py`.

## Andaime (exceção técnica)

Antes do Red: os dois modelos (sem as restrições `CHECK`, que são comportamento testado) e as migrações; `reserva.py` com as exceções, os tipos e as assinaturas com corpo trivial (`situacao_da_reserva` zerada, listas vazias, objetos não salvos).

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_reserva.py tests/tecnicos/test_financeiro_concorrencia.py tests/aceitacao/test_cenario_29_aporte.py tests/aceitacao/test_cenario_34_reserva_insuficiente.py -q -p no:cacheprovider`: **17 falharam, 7 passaram**. Todas as falhas são asserções (`DID NOT RAISE ...`, `assert Decimal('0.00') == Decimal('70.00')`, `assert [] == [('obrigacao', Decimal('50.00'))]`).

| Critério | Teste | Resultado do Red |
|---|---|---|
| A-1 a A-3, A-6, A-15 | os testes do aporte, da designação e da utilização | saldo e livre zerados; listas vazias |
| A-2, A-4, A-7, A-8, A-10, A-11 | os testes de recusa | `DID NOT RAISE AporteRepetido / ReservaInsuficiente / CoberturaExcedente / DesignacaoEncerrada / InvarianteViolado / PermissionDenied` |
| A-5 | `test_obrigacoes_sem_cobertura_...` | `assert Decimal('0.00') == Decimal('52.00')` |
| Restrições | `test_o_banco_recusa_designacao_incoerente` | `DID NOT RAISE IntegrityError` |
| A-12 a A-14 | os três de `test_financeiro_concorrencia.py` | ver "Green" |
| A-9 | `test_nenhuma_tarefa_periodica_faz_aporte` | **passou já no Red**: nada cria aporte, nem o andaime; guarda de regressão (P-4) que percorre o registro das tarefas periódicas do Procrastinate, então vale também para as tarefas das fatias seguintes |

## Green, em dois passos (regra da concorrência)

1. **Verde funcional sem a trava da reserva:** `reserva.py` completo, mas calculando o livre sem travar a conta `reserva`. Os testes sequenciais: **14 passaram, 1 falhou** (as restrições do banco). **Red da corrida**, por asserção, nos três testes de concorrência: `assert 2 == 1` em `sum(e is None ...)` (as duas designações passam, a designação e a utilização passam, e os dois aportes iguais passam). Antes de registrar este Red, corrigi o teste do A-14: a conta `reserva` nascia dentro da própria transação paralela e, por isso, a criação dela já serializava as duas chamadas; passei a criá-la antes, para que só a trava da reserva decida.
2. **A trava:** `_travar_a_reserva()` (e a trava da conta da obrigação, quando ela existe) antes de calcular o livre, em todas as operações. Os quatro arquivos: **23 passaram, 1 falhou** (as restrições). Depois as restrições `designacao_valor_positivo`, `designacao_justificativa_preenchida` e `desfeita_justificativa_preenchida`: **24 passed**.

## Decisões técnicas

- **Quem é o autor.** `PermissionDenied` para quem não é a conta do administrador ativa (comprador, fornecedor, `AnonymousUser`, `None`). A nova autenticação por passkey fica na rota (E09-08).
- **Chave da utilização.** `cobertura:<despesa>:<uuid>`: cada decisão do administrador é um movimento próprio. A proteção contra clique duplo é do formulário (E09-08); o aporte, que tem identificação do depósito, é idempotente pela chave.
- **O valor coberto de uma despesa** é a soma das transferências dos movimentos `cobertura_de_despesa` cuja origem é a despesa (`financeiro.despesa`); a E09-06 usa a mesma origem para a cobertura pela receita.
- **O que falta cobrir numa obrigação** é o devido menos tudo que entrou na conta dela (o saldo mais o já devolvido) menos o designado ativo; nunca abaixo de zero.
- **Cálculo sem cache.** `itens_sem_cobertura` percorre todas as obrigações e despesas; a escala desta etapa não pede mais. Fica como candidata a M-n se a lista crescer.
- **Consumo da designação.** Pertence à liquidação (E09-06); o comprometido passa a descontá-lo lá.

## Verificação

`ruff check`, `ruff format --check` (313 arquivos), `mypy` (374 arquivos) e `makemigrations --check`: limpos. Os arquivos da fatia: **24 passed**; o conjunto `financeiro`, cenários 29/30/32/34/39, matriz de eventos e fronteiras: **131 passed**. A suíte completa, sem filtro, é registrada na verificação da E09-06.
