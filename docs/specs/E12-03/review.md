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

## Correção da revisão — agente 2 — 2026-11-01

**R03 — impasse com pagamento tardio de ciclo anterior (A-19 a A-21).**

- **Red** (`da9f6aa`): A-19 `test_cancelamento_com_reembolso_e_pagamento_tardio_de_ciclo_anterior` falhou com `OperationalError: deadlock detected`, como no parecer. A-21 (sincronização primeiro, sem reembolso) e A-21 (cancelamento primeiro, sem reembolso) falharam porque o cancelamento sem reembolso não tocava a situação de X (a sincronização nunca viu o cancelamento esperando; `corrida.b_esperou` falso). A-20 (cancelamento primeiro, com reembolso) já passava: o cancelamento travava a situação de X dentro do reembolso; fica como regressão.
- **Green** (`8d1a899`, mesma correção da E12-02): os cinco testes passam. Nenhum `deadlock detected`; a rodada `cancelada`; a cobrança extra com destino `devolucao`/`duplicidade` e obrigação integral sem parcela; X sem reembolso do cancelamento e entre os `pagos_sem_reembolso`; o alerta `pagamento_depois_do_cancelamento` só quando o cancelamento vem antes (A-20); invariante sem violação.
- **A prova original do parecer** (`test_cancelamento_de_ciclo_anterior_concorre_com_pagamento_tardio`), copiada sem mudança para um arquivo temporário (removido, nunca commitado): o cancelamento termina sem exceção e não há impasse; a thread da sincronização falha na própria pausa (`fontes_travadas.wait(10)` vence), porque agora o cancelamento só trava as contas depois de a sincronização soltar a situação. É a mudança de pausa que o `acceptance.md` prevê; o A-19 usa `esperar_outra_conexao_na_trava()` no lugar dela.
- Ajuste de arranjo do A-19: a obrigação da duplicidade é buscada por `origem_tipo="pedidos.destinodopagamento"` e `origem_id`, pois só o `origem_id` podia coincidir com a obrigação de mínimo.


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `5705e5d`, branch `e12-implementacao`, correções desde `4370b11`. Adendos `0fdfe8f`/`f429fc6` lidos e confrontados com o código, os critérios e os registros Red/Green. Conteúdo anterior preservado. Evidências completas no [parecer consolidado E12-07](../E12-07/review.md).

**APROVADO — R03 encerrado.** Conferidos A-19 a A-21, nas duas ordens e indicações: as situações dos ciclos anteriores já estão travadas quando o reembolso as relê; contas financeiras continuam adquiridas depois. Os testes verificam destino de duplicidade, obrigação integral sem autorização pelo cancelamento, ausência de reembolso novo para X, alerta conforme a ordem e invariante financeiro. A prova independente não apresenta deadlock. Nenhuma validação, trava ou efeito foi removido para fazê-la passar.
