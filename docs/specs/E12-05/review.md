# E12-05 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_aviso.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-7 (e o arranjo CI movido para `tests/apoio/cancelamento.py`, sem mudar comportamento) | `478a51b` | **Red: 7 failed** (`Notificacao.DoesNotExist`; `_emitir_o_aviso` inexistente) |
| `_avisar_os_compradores`, `_corpo_do_aviso`, `_emitir_o_aviso` na transação do cancelamento | `f95a3ce` | **7 passed**; suíte completa **2871 passed**; `ruff` e `mypy` limpos |

## Decisões técnicas
- A-5: o teste reemite o mesmo conteúdo; o sistema recusa a mesma chave com conteúdo diferente (`ChaveDeEventoReutilizada`), o que é a proteção desejada. Corrigido antes do Green.
- Link de quem tem pedido pago sem saldo novo (A-4): o pedido pago (a spec não define esse caso).


## Parecer independente — agente 3 — 2026-11-01

Base auditada: `8e236e5`, branch `e12-implementacao`, comparada à E11 integrada em `d098654`. Funcional v1.7, infraestrutura v1.8, especificações e critérios das sete fatias lidos antes da avaliação da implementação. Conteúdo anterior preservado integralmente. Evidências, veredito da etapa e reproduções no [parecer consolidado E12-07](../E12-07/review.md).

**REPROVADO — R02 (importante).** A-1 a A-7 passam, mas não cobrem cancelamento sem reembolso após retorno ao interesse. Um comprador com pedido pago anterior e devolução de mínimo pendente recebe o texto de quem não tinha pedido pago. `pagos` e `pedidos` só contemplam a abertura vigente; `sem_reembolso` só é preenchido no ramo com reembolso. Referência: regra 4 (texto para pagante sem reembolso), funcional §7.2/§12. Corrigir a classificação histórica dos destinatários já afetados pelo cancelamento, sem criar obrigação nova nem autorizar a anterior. Prova no consolidado.

## Correção da revisão — agente 2 — 2026-11-01

**R02 — o pagante de ciclo anterior (A-8 a A-11).**

- **Red** (`07692a5`, `uv run pytest tests/tecnicos/test_cancelamento_aviso.py`): A-8 (a prova do parecer) recebia "Seus interesses nesta rodada foram removidos. Sem novas devoluções." e o link `/carrinho/`; A-10 e A-11 também falharam (sem o aviso de pagante; sem a frase do ciclo atual). A-9 já passava (regressão do ramo com reembolso).
- **Green** (`36c97c3`): em `_avisar_os_compradores`, a fonte do pagante passou a ser o pedido `pago` em qualquer abertura da rodada, lido sob as travas da E12-02; entra nos destinatários e define o texto nas duas indicações. O link segue a regra 5 (pedido da abertura vigente, o de menor `pk` com reembolso, o pago de maior `pk`, `/carrinho/`). `_corpo_do_aviso` traz "Seu pedido do ciclo atual foi cancelado e nada foi cobrado nele." antes da frase de pagante. O parâmetro `sem_reembolso` deixou de ser usado e saiu da função; a auditoria continua com `pagos_sem_reembolso`.
- **Resultado:** 11 passed no arquivo; nenhum movimento, reembolso ou obrigação novos no ramo sem reembolso (A-8 compara as contagens).
- **Arranjo do A-10:** C entra na fila depois da apuração, por `ParcelaFactory`, porque o estoque que A suspensa libera é distribuído na própria apuração e C ganharia reserva (e, com ela, um aviso legítimo). O critério trata de quem só tem pendente.


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `5705e5d`, branch `e12-implementacao`, correções desde `4370b11`. Adendos `0fdfe8f`/`f429fc6` lidos e confrontados com o código, os critérios e os registros Red/Green. Conteúdo anterior preservado. Evidências completas no [parecer consolidado E12-07](../E12-07/review.md).

**APROVADO — R02 encerrado.** Conferidos A-8 a A-11: pagantes de todas as aberturas são classificados e incluídos no aviso sob as travas, nas duas indicações; o link segue a prioridade especificada. Pagante suspenso sem parcela alterada recebe aviso; quem só possui fila sem pedido continua excluído. Pedido atual não pago de pagante anterior recebe a frase específica antes da informação das devoluções. O ramo sem reembolso preserva contagens de reembolsos, obrigações e movimentos. A prova anterior passou sem alteração.
