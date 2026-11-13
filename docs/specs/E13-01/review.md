# E13-01 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `75c589d` | **19 failed**: `ImportError: cannot import name 'PedidoFormal'` (nenhum `PedidoFormal`, como o critério A-1 prevê) |
| Green | `83d2ec9` | **19 passed**; regressão `test_apuracao_aprovacao.py`, `test_apuracao_telas.py` e `test_cancelamento_ponta_a_ponta.py`: 38 passed |

## O que foi feito
- Modelos `PedidoFormal`, `LinhaDoPedidoFormal`, `PrevisaoDeEntrega` (só inserção, com a trigger da E01-04) e `EnvioDoPedidoFormal` (migrações `0014` e `0015`); serviço `gerar_pedido_formal` em `apps/pedidos/pedido_formal.py` e o receptor de `resultado_aprovado` em `apps/pedidos/receptores.py`.
- O valor por linha reaproveita `_calcular_o_resultado` da apuração (E11-03), o mesmo desconto do estorno proporcional.

## Decisões técnicas e pontos para o especificador
- **Número no corpo.** O corpo cita "Pedido formal nº <pk>" e o registro não pode ser alterado depois de gravado; o `pk` é reservado com `nextval` da sequência antes da inserção.
- **Unidade no e-mail.** O critério A-6 escreve `11 unidade` e `1 kg`: o e-mail usa o valor gravado em `unidade` (`unidade`, `kg`, ...), e não o rótulo curto (`un`) de `quantidade_com_unidade`.
- **Recusas sem aprovação válida.** `gerar_pedido_formal(None)` e uma aprovação de resultado que não é `valida` levantam `ValueError`, sem escrita (A-12).
- **Teste de infraestrutura.** Os arquivos `test_pedido_formal*`, `test_previsao_de_entrega*`, `test_repasse*` e `test_portal_do_fornecedor*` entraram na lista de prefixos de `tests/conftest.py` que liga o banco do simulador (sem isso o fixture do simulador é recusado).


## Revisão independente — agente 3 — 2026-11-13

Base auditada: `9af6251`, branch `e13-especificacoes`, sobre `9851bb5`. Requisitos lidos antes do código: especificação funcional v1.7, infraestrutura v1.8 e os `spec.md`/`acceptance.md` das oito fatias. Os registros do implementador acima foram preservados integralmente.

**Veredito da fatia: APROVADO.** A etapa E13 permanece REPROVADA pelos achados E13-R01 e E13-R02, consolidados em [E13-08](../E13-08/review.md).

| Critérios | Conferência independente |
|---|---|
| A-1 a A-3, A-9, A-10 e A-17 | Quantidades finais, caixas válidas, arredondamento, exclusão de inadimplentes/pendentes e igualdade com a obrigação registrada no livro. |
| A-4 a A-8 | Previsão no calendário de Brasília, assunto/corpo congelados e ausência de dados de compradores. |
| A-11 a A-16 | Repetição sem escrita, geração somente com aprovação válida, estado inicial sem envio, imutabilidade na aplicação e PostgreSQL, rollback da aprovação incoerente e auditoria. |

`test_pedido_formal.py`: **19 testes passaram**, dentro da execução independente dos 152 testes da E13. Inspecionados o receptor transacional, `pedido_formal.py`, modelos e migrações 0014/0015. Não foi encontrado achado próprio impeditivo.

TDD: o commit Red `75c589d` contém testes antes do Green `83d2ec9`, que introduz o comportamento. O registro do implementador informa comando completo, 19 falhas pela ausência do modelo e 19 sucessos. A ordem e o conteúdo dos commits corroboram o registro; não se apresenta isso como reexecução histórica do Red. Comandos e limites no parecer consolidado.


## Revalidação independente das correções — agente 3 — 2026-11-13

Base auditada: `5055047`, branch `e13-especificacoes`, comparada com `7616ae8`. Histórico anterior preservado integralmente.

**APROVADO — mantida a aprovação.** Sem alteração de produção nesta fatia. A matriz completa da E13 foi reexecutada: 157 testes passaram. R01/R02 foram encerrados; ver consolidação em [E13-08](../E13-08/review.md).
