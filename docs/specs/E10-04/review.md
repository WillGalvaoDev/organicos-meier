# E10-04 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Andaime (`ParcelaDeDevolucao`, `HistoricoDaDevolucao`, migração 0012, três tipos de alerta, gancho `adiada` sem chamada) e testes A-1 a A-22 e A-25 | `E10-04: andaime` | `uv run pytest tests/tecnicos/test_devolucoes_execucao.py` | **Red: 25 failed** (`NotImplementedError`) |
| `devolucoes.py`, operações `estornar`, `acompanhar_estorno` e `verificar_estornos`, `adiada` em `_tentar`, recusa em `desfazer_designacao` | `E10-04: parcela de devolucao` | o mesmo arquivo | **25 passed** |
| Corridas A-23 e A-24 e T-8 | `E10-04: corridas A-23 e A-24 e T-8` | `test_devolucoes_concorrencia.py`, `test_t08_devolucao_idempotente.py` | 7 passed |

**Não conformidade de TDD declarada.** As travas (pagamento → situação do pedido → parcela) foram escritas junto com o código funcional, e não depois de um Red da corrida. A mutação que tira só `travar_pagamento` da autorização não derruba o A-23, porque a trava da `SituacaoDoPedido` e a unicidade da parcela por obrigação também serializam a autorização. Mutação não substitui Red; fica registrado como limite de verificação. O tratamento é o mesmo da E05-R04, da E06-R05 e da E08-R06.

## Desvios de arranjo nos testes (a especificação pede "depois da apuração")

- **A-7, A-21 e a variante do A-6 da E10-07:** em vez de apurar a rodada, a custódia do comprador é esvaziada antes do reembolso (`obrigacao_sem_cobertura`). O efeito é o mesmo: a obrigação nasce sem cobertura e só a designação da reserva a cobre.
- **A-11:** o saldo do simulador é reduzido com `registrar_saida(1.100,00)`, e não pela remoção do aporte.
- **A-8:** a parcela de 125,00 já concluída é uma fábrica (`ParcelaDeDevolucao` direta).
- **A-20:** a chamada `estornar` pendente é criada por fábrica, como a especificação pede.

## Decisões técnicas

- `autorizar_devolucao` lê a cobertura sob a trava da conta da obrigação, mas não trava a reserva: uma designação criada em paralelo só aumenta a cobertura, e o desfazer de designação com parcela aberta é recusado.
- `transicionar` é a única porta das mudanças de situação; a tabela cobre também `elegivel_excepcional → concluida` (E10-05).
- `verificar_estornos` que falha de forma definitiva não é reagendada: a parcela fica em `falha_definitiva` com o alerta aberto.
- `devolucao_concluida_tardiamente` (crítico) e a ampliação de `AlertaFinanceiro.tipo` para 40 caracteres entram já na migração 0012, para não haver duas migrações do mesmo campo; o uso do alerta é da E10-05.

## Revisão (agente 3)

| Achado | Classificação (bloqueador, importante, melhoria) | Evidência | Requisito |
|---|---|---|---|
| | | | |

**Decisão:** pendente

## Revalidação

—
