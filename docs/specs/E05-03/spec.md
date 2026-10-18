# E05-03 — Remoção de pendentes pelo comprador

Fatia 3 de 7 da milestone **E05 — Interesses, reservas e progresso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O comprador pode desistir, no todo ou em parte, de quantidades que esperam na fila de pendentes (Q-5). A remoção:

- só altera a quantidade pendente;
- vale em qualquer etapa, porque pendentes não fazem parte de nenhum ciclo;
- nunca vira reserva, mesmo em paralelo com o atendimento da fila.

Esta fatia entrega o serviço. A tela fica na E05-05.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Comprador ativo vê reservado e pendente separados e pode remover pendentes. |
| Especificação §5.2 | Remoção voluntária, parcial ou total. Atualiza só a pendente, sem modificar reservas válidas, posições FIFO de outras parcelas, registros financeiros, pedidos congelados nem reembolsos devidos. Não serve para editar pedido congelado. Quantidade múltipla do incremento e até o total pendente. A remoção parcial começa pelas parcelas mais recentes. Vale em qualquer fase. |
| Cenários §16 | 97, 98, 99, 100. |
| Infraestrutura 4.10 | `remover_pendente(comprador, produto, quantidade)`, numa transação com trava das parcelas do comprador no produto. Só atua sobre a quantidade pendente. Não aceita identificadores de itens de pedido nem de parcelas `em_pedido`. Marca a parcela como removida quando reservado e pendente ficam zero. Usa a mesma trava de `alocar_pendentes`. |
| Infraestrutura 8 | T-43, T-44, T-45. |
| E05-01, E05-02 | Ordem de travas e `alocar_pendentes`. |

## Escopo

**Dentro:**

- O serviço `remover_pendente` e a exceção `RemocaoAcimaDoPendente`.

**Fora:**

- A rota e a tela (E05-05).
- A pendência de parcelas que entram em pedido (E08).

## Decisões técnicas

- **Travas sem exigir etapa.** A remoção vale em qualquer etapa, então não usa `travar_rodada_para_interesses`, que recusa fora de interesse e fechamento. Ela trava, nesta ordem:
  1. a conta do comprador;
  2. o fornecedor do produto;
  3. o produto;
  4. as parcelas do produto, por sequência.

  É a ordem global da E05-01 sem a rodada e o estoque, que a remoção não usa. A trava do fornecedor é a mesma que `alocar_pendentes` adquire primeiro. Por isso, remoção e atendimento da fila se serializam (cenário 100, T-45).
- **Comprador ativo.** A §2 dá a remoção de pendentes ao comprador ativo. Um suspenso não tem pendentes, porque a suspensão as remove (E05-07). Mesmo assim, o serviço exige `pode_adicionar_interesse`.
- **Auditoria:** `interesse.remover_pendente`, com produto, quantidade e os ids das parcelas tocadas.

## Regras

```
remover_pendente(comprador, produto, quantidade) -> ResumoDoInteresse
```

Em `apps/interesses/servicos.py`, numa única `transaction.atomic()`:

1. Trava a conta e confere `pode_adicionar_interesse`. Se for falso, levanta `PermissionDenied`.
2. Trava o fornecedor do produto e depois o produto.
3. Valida a quantidade com `validar_quantidade(produto, quantidade)`: maior que zero, múltipla do incremento vigente e sem `float`.
4. Trava as parcelas do produto com `travar_parcelas(produto)` (E05-01). Calcula o pendente do comprador como a soma de `quantidade_pendente` das parcelas dele com situação `ativa` ou `pendente`.
5. Se `quantidade` passar desse total, levanta `RemocaoAcimaDoPendente(pendente)` com a mensagem "A remoção passa da quantidade pendente (<pendente>)." e não grava nada.
6. Reduz `quantidade_pendente` dessas parcelas, da **maior sequência para a menor**, até completar a quantidade. Em cada parcela tocada:
   - reservado e pendente zero: passa a `removida`;
   - situação `ativa` com reservado maior que zero: continua `ativa`;
   - situação `pendente` com pendente restante: continua `pendente`.
7. Não altera `quantidade_reservada`, `quantidade_original` nem `sequencia` de nenhuma parcela. Não toca parcelas `em_pedido` nem parcelas de outros compradores.
8. Audita e devolve o `ResumoDoInteresse` do comprador no produto.

**Entradas aceitas:** só `comprador`, `produto` e `quantidade`. O serviço não recebe id de parcela nem de item de pedido. A rota da E05-05 também não aceita esses campos (cenário 99).

**Sem alocação:** remover pendente não libera estoque, porque pendente não reserva. O serviço não chama `alocar_pendentes`.

## Interfaces

- `apps/interesses/servicos.py`: `remover_pendente` e `RemocaoAcimaDoPendente`.

## Invariantes

- A quantidade removida nunca vira reserva.
- Reservado + pendente ≤ original, em toda parcela.
- A remoção não muda reservas nem sequências de ninguém.

## Casos-limite e concorrência

- **Cenário 97:** A tem 6 reservados e 4 pendentes numa parcela `ativa`. Ao remover 2, a pendência cai para 2, e as reservas de A e dos outros compradores ficam iguais. Ao remover as 2 restantes, a pendência zera. A parcela continua `ativa`, com 6 reservados, e sai da fila.
- **Parcela só pendente:** A tem uma parcela `pendente` de 4. Ao remover 4, ela passa a `removida`.
- **Várias parcelas:** A tem pendentes de 2 (mais antiga) e 3 (mais recente). Ao remover 4, a de 3 zera e a de 2 fica com 1.
- **Cenário 98:** remover 5 com 4 pendentes, ou remover 1,5 com incremento 1, é recusado sem gravar.
- **Etapas:** a remoção é aceita com a rodada em `pagamento`, em `fechamento_encerrado` e sem rodada ativa.
- **Cenário 100 e T-45:** `remover_pendente` e `alocar_pendentes` rodam em paralelo no mesmo produto. Em qualquer ordem, ao final:
  - reservado + pendente ≤ original;
  - total reservado ≤ limite;
  - a quantidade removida não aparece em nenhuma reserva.

## Dependências e decisões em aberto

- Depende de E05-01 e E05-02.
- Sem decisões em aberto.
