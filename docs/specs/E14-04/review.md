# E14-04 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_liberacao_da_retirada.py tests/aceitacao/test_cenario_22_liberacao.py` (arquivos inteiros, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | **28 failed**, todos por `ModuleNotFoundError: apps.pedidos.liberacao_da_retirada` |
| Green | **28 passed**; junto com as E14-01 e E14-02, **86 passed**; `ruff` e `mypy apps tests/apoio` limpos |

## O que foi feito
- `LiberacaoDaRetirada` (só inserção, migração `0019`, `CHECK` do prazo depois da liberação), `liberar_retirada`, `liberacao_da_rodada`, `LiberacaoRecusada` em `apps/pedidos/liberacao_da_retirada.py`.
- Travas pelo `_travar` da E11-01 e pelos compradores de `_compradores_envolvidos` da E12 (mesma ordem do cancelamento); o instante é lido depois das travas.
- As parcelas `em_pedido` passam a `removida`/`pendente` (regra 6 da E12-01), sem criar parcela nem mudar sequência; avisos `retirada_liberada` só a quem tem saldo (suspenso recebe, removido não); auditoria `rodada.liberar_retirada`.
- A recusa do cancelamento da rodada liberada (`rodada_encerrada`) já existia na E12; A-14 e A-21 a comprovam sem código novo.

## Decisão técnica registrada (tensão entre a regra 2 e o A-22)
- A regra 2 diz que a conferência prévia, sem trava, aplica "a etapa e as condições da regra 4". O critério A-22 exige que, com a ocorrência que completa o recebimento ainda não commitada, a liberação **espere** a trava e seja aceita. Uma conferência prévia de `recebimento_pendente` recusaria de imediato e o A-22 não passaria.
- Implementei a prévia só com a **etapa** (`ja_liberada`/`etapa`); o endereço e o recebimento são conferidos sob as travas. Os testes A-5, A-10 e A-22 cobrem os dois lados. Se o especificador quiser a prévia completa, o A-22 precisa mudar; deixo o ponto para o agente 3 confirmar.

## Outras notas
- A auditoria grava `liberada_em` e `prazo_final` como `datetime` (o serializador JSON os grava em UTC com `Z`).
- `tests/aceitacao/test_cenario_22_liberacao.py` foi escrito junto do Red (falhava pelo mesmo motivo).


---

## Revisão independente — agente 3 — 2026-11-16

**Objeto:** `5b00c56`, branch `e14-especificacoes`, comparação com `bc35037` (main após E13). Fontes: especificação funcional v1.7, infraestrutura v1.8, AGENTS.md e as oito especificações e matrizes da E14. Histórico do implementador acima preservado.

A execução independente e o parecer consolidado estão em [E14-08/review.md](../E14-08/review.md), incluindo o código das contraprovas. A revisão não alterou código de produção nem os testes do implementador.

**Parecer da fatia: APROVADO.**

| Critérios | Verificação |
|---|---|
| A-1 a A-4 | Liberação única, instante após travas, prazo de 168 horas, endereço fixado, avisos e liberação das reservas para nova rodada. |
| A-5 a A-10 | Pendências, faltas/não entregues, compradores com saldo, suspenso/removido e endereço obrigatório. |
| A-11 a A-19 | Repetição/etapas/permissão, cancelamento encerrado, imutabilidade financeira/comercial, previsão, repasse e auditoria. |
| A-20 a A-22 | Liberações concorrentes, cancelamento e espera pela ocorrência que resolve o recebimento. |

Código confrontado: `liberacao_da_retirada.py`, `_travar`/compradores envolvidos, migração 0019, emissão de avisos e parcelas. `test_liberacao_da_retirada.py` e cenário 22 incluídos na execução independente.

A regra 2 menciona conferência prévia das condições; a implementação confere previamente apenas a etapa, e confere todas as condições sob as travas. Aceito como resolução técnica da tensão com A-22, documentada pelo implementador: recusar previamente o saldo ainda não confirmado impediria aguardar a ocorrência concorrente exigida pelo próprio critério. Nenhuma condição de negócio foi dispensada; não é necessária decisão comercial (AGENTS.md §9).

TDD: Red `4b9b482`, Green `de622e1`; testes concorrentes com confirmação de espera no PostgreSQL. Sem achado impeditivo nesta fatia.
