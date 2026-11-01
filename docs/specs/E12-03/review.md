# E12-03 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_com_reembolso.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-18 | `610340b` | **Red: 16 failed, 2 passed.** Falhas pelo comportamento ausente: `Reembolso` e `ObrigacaoComComprador` inexistentes (A-1, A-2, A-3, A-6, A-7, A-9, A-15), `DID NOT RAISE ConsultaAoProvedorFalhou` (A-4), Y `cancelado` em vez de `pago` (A-5), `KeyError: pagos_sem_reembolso` (A-8), `ImportError: autorizar_devolucoes_do_cancelamento_agora` (A-10 a A-13), auditoria sem `reembolsos` (A-16), `_reembolsar_os_pedidos_pagos` inexistente (A-17). **Passaram de primeira (regressão):** A-14 (sem pagamento não há reembolso) e A-18 (o aviso espera a situação travada) |
| Consulta prévia, `_reembolsar_os_pedidos_pagos` (travas do livro numa chamada, `reembolso_integral_do_pedido`), autorização pelo sistema depois do commit, `autorizar_devolucoes_do_cancelamento_agora` e a tarefa periódica (10 min) | `e3fe30c` | **18 passed**; suíte completa **2856 passed**; `ruff`, `mypy`, `makemigrations --check` limpos |

## Decisões técnicas
- `_autorizar` não relança `ConsultaAoProvedorFalhou` nem `DevolucaoRecusada` e também registra, sem relançar, uma exceção inesperada (o cancelamento já confirmou); o log leva só a obrigação e o tipo.
- A tarefa e a função ficam em `apps/pedidos/cancelamento_da_rodada.py` e `apps/pedidos/tarefas.py`.
- Auditoria: `reembolsos` (chave, pedido, comprador, componentes) e `pagos_sem_reembolso` (pedidos pagos sem saldo).

## Ajustes dos testes em relação ao texto dos critérios (por defeito do critério; o Red não mudou de motivo)
- **A-4:** `falhar_proximas(operacao="consultar_pagamento")` não dispara: a consulta por referência já traz o pagamento registrado e `consultar_pagamento` só roda para os não vistos. O teste usa `operacao="buscar_por_referencia"`. Mutação: sem a consulta prévia, A-4 e A-5 falham. **Ponto para o especificador.**
- **A-10:** com a tarifa de 10% a receita de serviço continua 3,00 (a despesa fica pendente para a reserva), e a obrigação nasce coberta. O teste consome a receita com um movimento `cobertura_de_despesa` antes do cancelamento, para ter a falta de cobertura. **Ponto para o especificador.**
- **A-7 e A-15:** montados pelos apoios existentes (`pedido_composto`, `K`, `recusar_estornos`).


## Parecer independente — agente 3 — 2026-11-01

Base auditada: `8e236e5`, branch `e12-implementacao`, comparada à E11 integrada em `d098654`. Funcional v1.7, infraestrutura v1.8, especificações e critérios das sete fatias lidos antes da avaliação da implementação. Conteúdo anterior preservado integralmente. Evidências, veredito da etapa e reproduções no [parecer consolidado E12-07](../E12-07/review.md).

**REPROVADO — R03 (bloqueador).** A-1 a A-18 e o fluxo de autorização/repetição conferidos; os testes existentes passam. A corrida adicional com pagamento tardio de ciclo anterior aborta o cancelamento por `OperationalError: deadlock detected`. O cancelamento trava fontes financeiras antes de adquirir a situação do pedido anterior, enquanto a sincronização segura essa situação e espera as fontes. Incluir os pedidos anteriores na estratégia de travas antes das contas financeiras, preservando leitura atualizada, consultas fora de transação e idempotência. Prova completa no consolidado.
