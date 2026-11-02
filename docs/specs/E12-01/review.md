# E12-01 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_da_rodada.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-20 | `c9d2d08` | **Red: 25 failed.** `ModuleNotFoundError: apps.pedidos.cancelamento_da_rodada` e `ImportError: CancelamentoDaRodada` (o serviço e o modelo não existem, o Red esperado do A-1) |
| Modelo `CancelamentoDaRodada` (só inserção, migração 0012 com a trava), serviço `cancelar_rodada`, `CancelamentoRecusado`, travas de `_travar` da apuração, auditoria `rodada.cancelar` | `670dee8` | **25 passed** |

## Decisões técnicas
- As travas reusam `_travar` da apuração (contas, fornecedor, rodada, produtos, estoques, parcelas, todas `FOR NO KEY UPDATE`).
- A guarda do autor olha a conta passada (`papel` administrador e `situacao` ativa).
- Rodada inexistente: `CancelamentoRecusado("rodada_inexistente")` (a spec não define o código).
- A auditoria lista toda parcela alterada (inclusive a `ativa` sem reserva e com pendência, que vira `pendente`).
- Pontos de pausa das corridas: `_gravar_o_cancelamento` (cancelamento), `_acrescentar` (interesse), `avisar_excedentes_removidos` (encerramento).

## Ajustes dos testes em relação ao texto dos critérios (antes do Green; o Red não mudou de motivo)
- **A-5:** o banco recusa administrador suspenso (`conta_administrador_ativo`), então o caso é exercido com a conta inativa em memória. **Ponto para o especificador.**
- **A-13:** a lista de parcelas alteradas inclui D (`ativa` sem reserva e 3 pendentes passa a `pendente`, A-2); a spec diz "por parcela alterada".
- **A-19:** o limite é 20, e não 15: com 15 a fila (C e D, 6 unidades) consome o livre e a adição de A é recusada por estoque, sem exercitar a corrida. **Ponto para o especificador.**
- **A-16:** a regra da E05 atende a fila quando o produto é incluído na rodada nova (`incluir_produto_na_rodada`).


## Parecer independente — agente 3 — 2026-11-01

Base auditada: `8e236e5`, branch `e12-implementacao`, comparada à E11 integrada em `d098654`. Funcional v1.7, infraestrutura v1.8, especificações e critérios das sete fatias lidos antes da avaliação da implementação. Conteúdo anterior preservado integralmente. Evidências, veredito da etapa e reproduções no [parecer consolidado E12-07](../E12-07/review.md).

**Sem achado próprio nos critérios A-1 a A-20; aprovação da etapa não concedida.** Conferidos registro único e só inserção, permissões, booleano obrigatório, mensagem, recusas, remoção de reservas, preservação da fila, nova rodada e corridas com interesse/fechamento. Os ajustes do arranjo A-19 (limite 20 para efetivamente haver estoque depois da fila) e A-5 (administrador inativo só em memória, pois o banco proíbe esse estado) são justificados e não alteram negócio. A guarda para etapa encerrada segue o escopo aprovado; a decisão de E14 continua fora desta entrega. A ordem global das travas precisa da correção R03 ao alcançar pedidos anteriores na E12-03.


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `5705e5d`, branch `e12-implementacao`, correções desde `4370b11`. Adendos `0fdfe8f`/`f429fc6` lidos e confrontados com o código, os critérios e os registros Red/Green. Conteúdo anterior preservado. Evidências completas no [parecer consolidado E12-07](../E12-07/review.md).

**APROVADO nesta revalidação, sem achado próprio.** Mantida a avaliação anterior dos critérios A-1 a A-20. Os ajustes de A-5/A-19 foram incorporados pelo especificador, sem mudar regra de negócio. As correções da etapa não modificam remoção de reservas, preservação da fila ou guarda de etapa encerrada.
