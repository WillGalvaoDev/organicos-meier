# E11-04 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Comandos com o arquivo de teste inteiro, sem `-k`: `uv run pytest tests/tecnicos/test_apuracao_viavel.py`.

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-14 (apoio `parcelas_de_p1`/`parcelas_de_p2`) | `b75e61e` | **Red: 13 failed, 1 passed.** Nenhum reembolso (`ObrigacaoComComprador.DoesNotExist`, produtos `0.00 != 20.00`), a parcela de A em P2 continua `em_pedido`, `RestauracaoDeCaixa` e `_estornar_e_restaurar` inexistentes. **A-6 passou** (regressão: o pedido congelado não muda) |
| `RestauracaoDeCaixa` (migração `pedidos 0010`, proteção de só inserção); `_estornar_e_restaurar`, `_avisar_a_caixa_incompleta`; auditoria `pedidos`; `quantidade_com_unidade`; contas dos compradores travadas antes do fornecedor | commit da fatia | **55 passed** (E11-01 a E11-04) |

## Decisões técnicas

- **Contas travadas primeiro.** A spec diz que a suspensão e a apuração se serializam "pela trava do fornecedor". O A-14 mostrou que não: `remover_interesses_do_comprador` (E05-07) só trava o fornecedor dos produtos em que *enxerga* parcelas `ativa`/`pendente`, e a parcela restaurada ainda não está commitada, então a suspensão terminava sem esperar (`b_esperou` falso) e deixava um pendente numa conta suspensa. As operações de interesse travam a conta primeiro (conta, fornecedor, ...). A apuração passou a travar as contas dos compradores da abertura, por `pk`, com `FOR NO KEY UPDATE` (como a moderação), antes do fornecedor. A ordem das demais travas da E11-01 não muda. Com isso a conta é lida sob trava para a regra 4 (conta suspensa ou removida não recebe a restauração).
- **Chave do reembolso** `caixa:<apuração>:<item>` e invariante: o estorno de produtos igual ao desconto do valor válido (`RuntimeError` se divergir).
- **Rótulo curto da unidade** (`un`, `kg`, `L`, `pct`, `cx`) em `quantidade_com_unidade`; só `un` aparece na spec (E11-04 A-11).
- Quando nenhuma parcela é restaurada (conta suspensa), o aviso omite a frase da fila de pendentes.

## Conflito entre critérios de fatias (para o especificador)

- **E11-02 A-4** (as parcelas de A ficam `em_pedido`, iguais às de antes) vale no estado da E11-02. Depois da E11-04, a parcela de A em P2 passa a `pendente` (E11-04 A-3), e na E11-05 a `ativa`. O teste passou a conferir a parcela de A em P1, que nenhuma fatia seguinte toca.
- **E11-02 A-6** ("A não recebe `itens_cancelados` por inadimplência"): o teste passou a filtrar a chave `itens_cancelados:inadimplencia:`, porque A recebe, na E11-04, o `itens_cancelados` de caixa incompleta.

## Riscos remanescentes e limites de verificação

- A spec não diz o que fazer com a parcela restaurada cujo comprador é suspenso depois do commit: a suspensão (E05-07) a remove, como o A-14.

## Defeito achado depois pela E11-08 (corrigido)

Com dois pagantes com estorno na mesma apuração, a segunda criação de obrigação pedia contas do livro-razão de `pk` menor que as já travadas (`OrdemDeTravasViolada`). Teste: `test_dois_pagantes_com_estorno_na_mesma_apuracao` (Red `3066566`, 1 failed). Correção: `_travar_as_contas_das_devolucoes` trava o conjunto das contas de todos os pagantes de uma vez, em ordem crescente de `pk`, antes do primeiro estorno (`contas_das_obrigacoes`, em `apps/financeiro/obrigacoes.py`). Detalhes no `review.md` da E11-08.


## Parecer independente — agente 3 — 2026-10-31

Base auditada: `1a36495`, branch `e11-implementacao`, comparada à base E10 integrada `1b9bf07`. Leitura dos documentos-base (funcional v1.7 e infraestrutura v1.8), spec/acceptance das oito fatias, implementação, testes e registros de TDD. O conteúdo anterior deste arquivo foi preservado integralmente. Evidências e reproduções completas no [parecer consolidado da E11-08](../E11-08/review.md).

**REPROVADO — R01 (importante).** A-1 a A-14 confrontados com código/testes, incluindo os dois pagantes com estorno acrescentados na E11-08. Os cenários existentes passam, mas falta a interação entre remover a sobra pendente e restaurar a parte paga congelada.

**R01 — remoção só da sobra pendente impede a restauração das unidades pagas.** Referências: funcional §5.2 (remover pendente só afeta a pendência), §8.2 passo 3.4; E11-04 regras 2/4 e invariante de restauração, E11-05 regra 1. `apps/pedidos/apuracao.py:360` e `:409` tratam qualquer parcela `removida` como impedimento, além da conta suspensa/removida prevista na spec. Uma parcela com parte congelada e sobra pendente fica `removida` legitimamente quando o comprador ativo remove toda a sobra pelo serviço. Isso não cancelou suas unidades pagas.

Prova da rodada viável: A tem 4 unidades de P2 no pedido e 2 pendentes; paga e remove apenas as 2 pendentes. A caixa das 4 é invalidada pela inadimplência de B. A apuração gera reembolso, mas mantém a parcela `removida`, pendente zero, em vez de restaurar 4. Prova de retorno: A tem 6 unidades pagas e 2 pendentes de P1; remove as 2; a rodada volta ao interesse, mas não recupera as 6 reservadas. Ambas falharam independentemente. Corrigir distinguindo a remoção da sobra da elegibilidade da conta, preservando identidade/quantidade congelada e sem ressuscitar a sobra que o comprador removeu; testar ambos os ramos e idempotência.

TDD: `b75e61e → df2b910`, e `3066566 → aae9149` para mais de um pagante; registros conferidos. A trava das contas de usuários antes do fornecedor é uma decisão técnica coerente com a moderação. O impedimento adicional `parcela_removida`, porém, não decorre da regra de conta suspensa.
