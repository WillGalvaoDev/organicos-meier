# E11-02 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Comandos com o arquivo de teste inteiro, sem `-k`: `uv run pytest tests/tecnicos/test_apuracao_inadimplentes.py`.

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-10 | `9364df2` (testes) | **Red: 7 failed, 3 passed.** A-1: parcelas de B continuam `em_pedido`; A-2: o pendente antigo continua `pendente` com 3; A-6 e A-7 (avisos), A-8 (`KeyError: 'inadimplentes'` na auditoria), A-9 (nenhum aviso) e A-10 (`_remover_as_parcelas_dos_inadimplentes` inexistente). **A-3, A-4 e A-5 passaram** (regressões: nada muda nas parcelas de outro fornecedor, nas de quem pagou e na composição do pedido; a spec só os marca com Red nos demais) |
| `_remover_as_parcelas_dos_inadimplentes` e `_avisar_o_cancelamento` na transação da apuração; auditoria com os inadimplentes | commit da fatia | **32 passed** (esta fatia e a E11-01) |

## Decisões técnicas

- As parcelas já estão travadas pela E11-01 (`FOR NO KEY UPDATE`, produtos do fornecedor inclusive os de fora do estoque da rodada); a remoção não trava mais nada e não atende a fila (a rodada continua em `pagamento`).
- O aviso `itens_cancelados` vai só aos compradores dos pedidos cancelados por esta apuração (`cancelados_agora`).

## Riscos remanescentes e limites de verificação

- O número `sequencia` do pendente antigo de B no A-2 não é anterior à dele no arranjo (a sequência é do banco e o teste não a controla); a asserção do critério não depende disso.

## Ajustes dos testes por conflito com fatias seguintes (E11-04)

Registrado também na E11-04: o A-4 passou a conferir só a parcela de A em P1, e o A-6 filtra a chave `itens_cancelados:inadimplencia:`. As asserções sobre o que a E11-02 produz não mudaram.


## Parecer independente — agente 3 — 2026-10-31

Base auditada: `1a36495`, branch `e11-implementacao`, comparada à base E10 integrada `1b9bf07`. Leitura dos documentos-base (funcional v1.7 e infraestrutura v1.8), spec/acceptance das oito fatias, implementação, testes e registros de TDD. O conteúdo anterior deste arquivo foi preservado integralmente. Evidências e reproduções completas no [parecer consolidado da E11-08](../E11-08/review.md).

**APROVADO no escopo próprio desta fatia.** A-1 a A-10 confrontados com código/testes: remoção por fornecedor inclusive produto fora do estoque, preservação dos demais compradores/fornecedores e do pedido congelado, aviso só aos cancelados agora, auditoria e corrida com remoção de pendente. Não foi encontrado achado próprio.

O ajuste registrado de A-4 é coerente com a composição das fatias: a remoção dos inadimplentes não muda A, mas E11-04 restaura a parte invalidada de A depois. Filtrar a chave do aviso de inadimplência em A-6 também distingue corretamente o evento posterior de caixa incompleta. Isso não autoriza enfraquecer a preservação dos pedidos congelados. TDD: `9364df2 → e958092`, registros Red/Green e regressões verdes conferidos. A aprovação desta fatia não aprova a etapa.
