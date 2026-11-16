# E14-08 — Ponta a ponta: entrega, ocorrências, liberação, retirada e descarte

Fatia 8 de 8 da milestone **E14 — Recebimento, ocorrências, retirada e descarte**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E14-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E14-01.

## Contexto e objetivo

Exercitar, pelas telas e com o simulador de pagamentos, o caminho completo da rodada aprovada até o fim da retirada:
- os cenários 18, 22, 23 e 48 a 52;
- o T-18;
- a decisão (a);
- a integração com o repasse (E13-06), com as devoluções (E10) e com a nova rodada do fornecedor.

A fatia não cria comportamento de produção. Como a E13-08, os testes integrados verificam o que as fatias anteriores construíram por TDD.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Cenários §16 | 18, 19, 22, 23, 48, 49, 50, 52 |
| Testes técnicos | T-18 |
| Infraestrutura 7 (fase 1) | Cenários contra o simulador, incluindo ocorrências de entrega; o invariante financeiro sem violação. |
| Infraestrutura 3.2 | Ocorrência com reembolso financiada antes ou depois do repasse. |
| Decisão (a), 2026-11-13 | A rodada liberada não é cancelada; o que restar vira ocorrência. |

## Escopo

**Dentro:** os cenários abaixo, com as ações do administrador pelas rotas HTTP (com `entrar_de_novo` depois de cada avanço do relógio, como na E11-07 e na E13-08), o simulador, `processar_chamadas()` e o invariante financeiro conferido no fim de cada critério.

**Fora:** qualquer código de produção novo.

## Cenários

1. **Entrega parcial resolvida por ocorrência, antes do repasse:** recebimento parcial; ocorrência; liberação recusada e depois aceita; aviso; devolução autorizada e concluída no simulador; repasse limitado ao que sobrou da obrigação com o fornecedor.
2. **Ocorrência depois do repasse:** a parte de produtos sem cobertura; a cobertura pela reserva (E09-06); a devolução concluída.
3. **Nova rodada imediata (cenário 22)** e as retiradas antigas registradas depois, com o estoque da nova rodada livre.
4. **Prazo e descarte (cenário 23).**
5. **Decisão (a):** cancelamento recusado na rodada liberada; ocorrência depois da liberação.
6. **Concorrência pela rota (T-18):** duas ocorrências do mesmo item ao mesmo tempo.
7. **Comprador e fornecedor (cenários 50, 21 e 67)** nos estados acima.

## Invariantes conferidos

- O pedido congelado, os itens e o pedido formal iguais do começo ao fim.
- Por item: reembolsado + retirado + descartado ≤ quantidade.
- O invariante financeiro (E09) sem violação.

## Dependências e decisões em aberto

- Depende das E14-01 a E14-07, da E13-06, da E10 e da E09.
- Nenhuma decisão em aberto.
