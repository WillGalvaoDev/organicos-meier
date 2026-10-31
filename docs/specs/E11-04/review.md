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
