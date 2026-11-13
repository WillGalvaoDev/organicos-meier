# E13-07 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_portal_do_fornecedor.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `0952f9f` | **13 failed, 5 passed** (rotas do portal inexistentes). Passam por ausência ou por políticas que já existiam: A-10, A-11, A-12, A-13 e A-16; ficam como regressão |
| Green | `9235d17` | **18 passed** |

## O que foi feito
- `apps/fornecedores/portal.py` (serializadores com lista fechada e CSV), `apps/fornecedores/portal_views.py` (`exige_fornecedor`, `Rodada.objects.filter(fornecedor=request.fornecedor_vinculado)`), três rotas (`fornecedor_painel`, `fornecedor_rodada`, `fornecedor_pedido_formal_csv`), dois templates e o link "Minhas rodadas" em `inicio/`.

## Ponto para o especificador
- **"0 faltando" no A-3.** Para P2 com 12 unidades em caixas de 6, o critério diz "2 caixas completas, 0 faltando". O `progresso_da_rodada` da E05 (que a regra cita como fonte) devolve `faltam_para_proxima_caixa = 6` nesse caso (a conta é `múltiplo − total % múltiplo`; o teste E05 `test_interesses_progresso.py:54` fixa esse valor). O portal segue o critério: mostra **0** quando as caixas estão fechadas e o valor da E05 nos demais casos. Se a intenção era mostrar 6, é uma linha em `_faltam` (`apps/fornecedores/portal.py`) e no teste.
- No A-15, o administrador chega à rota do fornecedor só com a passkey: com `force_login` (sem prova de passkey) o redirecionamento para cadastrar a passkey vem antes da política da rota. O teste entra por passkey, como nas demais telas.


## Correção conforme o esclarecimento do especificador — agente 2 — 2026-11-09

- **Red** (`uv run pytest tests/tecnicos/test_portal_do_fornecedor.py`, arquivo inteiro): com o A-3/A-4 corrigidos (`faltam_para_proxima_caixa` de P2 = 6), `test_as_chaves_da_rodada_em_interesse` falhou com `Decimal('0') != 6`; os outros 17 passaram.
- **Green:** removi `_faltam` de `apps/fornecedores/portal.py`; o portal usa o valor de `progresso_da_rodada` sem ajuste. 35 passed com `test_pedidos_abertura_tela.py`.
- A lista de rotas do `test_pedidos_abertura_tela.py` ganhou, em cada rota da E13, o comentário com a fatia que a cobre.
- E13-03 (chave `acionamento`) e E13-06 (arranjo do A-25) já estavam conforme os esclarecimentos; o "ponto para o especificador" do item "0 faltando" acima está resolvido pela correção.


## Revisão independente — agente 3 — 2026-11-13

Base auditada: `9af6251`, branch `e13-especificacoes`, sobre `9851bb5`. Requisitos lidos antes do código: especificação funcional v1.7, infraestrutura v1.8 e os `spec.md`/`acceptance.md` das oito fatias. Os registros do implementador acima foram preservados integralmente.

**Veredito da fatia: APROVADO.** A etapa E13 permanece REPROVADA por E13-R01/E13-R02.

A-1 a A-18: conferidos os campos fechados dos serializadores, filtro de fornecedor no queryset, etapas, pedido/previsão, CSV, proibição de escrita e recusas de acesso direto por comprador/fornecedor/administrador/anônimo. Templates usam os dados permitidos; as consultas e o CSV não expõem compradores, pagamentos, serviço, frete, reserva ou repasses. `test_portal_do_fornecedor.py`: **18 testes passaram**.

Confirmada a correção do especificador: P2 com 12 unidades e múltiplo 6 informa **6 faltando para a próxima caixa**, usando diretamente o progresso da E05. O ajuste da lista de rotas no teste da E08 foi conferido: as quatro rotas novas não editam o pedido congelado, seus itens, T0 ou frete cobrado; cada inclusão está comentada com a cobertura correspondente.

TDD: `0952f9f` → `9235d17`, com distinção dos testes de recusa já atendidos; para a correção, `c56385e` altera primeiro a expectativa e `9af6251` remove a transformação indevida do valor. Registro Red/Green compatível com a sequência inspecionada. Sem achado próprio impeditivo. Evidências gerais em [E13-08](../E13-08/review.md).


## Revalidação independente das correções — agente 3 — 2026-11-13

Base auditada: `5055047`, branch `e13-especificacoes`, comparada com `7616ae8`. Histórico anterior preservado integralmente.

**APROVADO — mantida a aprovação.** Sem alteração de produção nesta fatia. Seus 18 testes passaram na matriz completa, mantendo campos fechados, isolamento, exportação e recusas. Consolidação em [E13-08](../E13-08/review.md).
