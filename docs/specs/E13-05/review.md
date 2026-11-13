# E13-05 — Registro da implementação (agente 2, 2026-11-04)

Comandos: `uv run pytest tests/tecnicos/test_previsao_de_entrega.py tests/tecnicos/test_previsao_de_entrega_telas.py` (arquivos inteiros, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `e83683e` | **23 failed, 2 passed**: módulo, rota e bloco inexistentes. Passam por ausência o 404 da rota sem pedido formal e a ausência da linha de previsão no pedido inválido (regressão) |
| Green | `783d315` | os dois arquivos e `test_pedido_formal_telas.py`: **43 passed** |

## O que foi feito
- `ajustar_previsao_de_entrega` e `PrevisaoRecusada` em `apps/pedidos/previsao_de_entrega.py`; aviso `previsao_de_entrega_alterada` por comprador de pedido válido (suspensos recebem, removidos não); rota `administracao/rodadas/<pk>/previsao/`; bloco da previsão na página do pedido formal; linha "Previsão de entrega" no pedido do comprador (`previsao_do_pedido`).
- A-19 (concorrência): o segundo ajuste com a mesma data espera a trava da rodada e recebe `sem_alteracao`.


## Revisão independente — agente 3 — 2026-11-13

Base auditada: `9af6251`, branch `e13-especificacoes`, sobre `9851bb5`. Requisitos lidos antes do código: especificação funcional v1.7, infraestrutura v1.8 e os `spec.md`/`acceptance.md` das oito fatias. Os registros do implementador acima foram preservados integralmente.

**Veredito da fatia: APROVADO.** A etapa E13 permanece REPROVADA por E13-R01/E13-R02.

| Critérios | Conferência |
|---|---|
| A-1 a A-5 e A-12 | Registro só inserção, snapshot original intacto, avisos por comprador válido, suspensos incluídos/removidos excluídos, privacidade e auditoria. |
| A-6 a A-11 e A-19 | Fronteira de Brasília, data passada/igual/tipo inválido, etapa, autorização e serialização dos ajustes. |
| A-13 a A-18 | Histórico e formulário administrativo, respostas HTTP e previsão apenas no pedido válido de rodada aguardando fornecedor. |

`test_previsao_de_entrega.py` e `test_previsao_de_entrega_telas.py`: **25 testes passaram** na matriz independente. Inspecionadas as travas compartilhadas com cancelamento/envio. Sem achado próprio impeditivo.

TDD: Red `e83683e` antes do Green `783d315`; o registro explicita os dois casos que já passavam e a verificação conjunta de 43 testes com as telas do pedido formal. Evidências gerais em [E13-08](../E13-08/review.md).


## Revalidação independente das correções — agente 3 — 2026-11-13

Base auditada: `5055047`, branch `e13-especificacoes`, comparada com `7616ae8`. Histórico anterior preservado integralmente.

**APROVADO — mantida a aprovação.** Sem alteração de produção nesta fatia. Seus 25 testes passaram na matriz completa. Nenhuma regressão identificada em ajuste, histórico, avisos e permissões. Consolidação em [E13-08](../E13-08/review.md).
