# E08-02 — Revisão independente do agente 3 — 2026-10-21

**REPROVADO sobre `2714a6a2acaf88cc69e02345facf2a2403a66374`, branch `e08-implementacao`. E08 global: REPROVADO.**

Matriz examinada: **A-1 a A-21**, a partir de spec.md/acceptance.md e das fontes superiores, antes de avaliar o código. R04: subtotal zero de entrada válida aborta a abertura. R06: a cronologia do Red de A-4/A-11 e o ciclo específico das travas precisam de comprovação. R07/M-3: alinhar A-12/A-21 às políticas e avisos já definidos, sem mudar o comportamento correto.

TDD declarado: **42 failed, 16 passed; segunda execução 22 failed, 1 passed; ver ressalvas R06.** O revisor confere registro, testes e diffs; não presenciou a execução histórica. Reexecuções atuais não substituem evidência de Red anterior à implementação.

Verificações independentes: suíte completa **1 failed, 2129 passed in 292.98s**, sem exclusões; provas adicionais **5 failed, 2 passed in 17.36s**; lint, formatação (288 arquivos), tipos (338 arquivos) e verificação de migrações passaram. A falha versionada é a de rotas descrita em R05; as cinco falhas adicionais correspondem a R01, R02 (duas variantes), R03 e R04.

O [parecer consolidado](../E08-01/review.md) contém matriz das sete fatias, referências, classificação, resultados, código completo das provas, limites e encaminhamentos R01–R07. R04 requer decisão sobre pedido zero, e R06 requer evidência histórica ou tratamento autorizado; as perguntas foram encaminhadas durante a revisão. R07 está no registro central como M-3.

Somente documentação foi alterada pelo revisor, sem correção silenciosa de produção ou testes. Histórico do implementador preservado integralmente abaixo. Próximo gate: correções/comprovações e nova revisão independente.

---

## Registro anterior integralmente preservado

# E08-02 — Registro do implementador (2026-10-20)

Status: implementada; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia, a E08-01 (cálculo), o código de `apps/rodadas` (fechamento, avisos, views), `apps/interesses` (parcelas, fila, progresso, remoção) e as regras de prevenção da E05-R04 e da E06-R05.

## Arquivos

- `apps/pedidos/models.py` e migrações `0001_initial` e `0002_restricoes`: `AberturaDoPagamento`, `Pedido`, `ItemDoPedido`, `ParcelaNoPedido` (só inserção, com trigger e log de tentativa) e `SituacaoDoPedido` (alterável, com `CHECK` por situação).
- `apps/pedidos/abertura.py`: `abrir_pagamento` e `ResultadoDaAbertura`.
- `apps/rodadas/avisos.py`: `avisar_excedentes_removidos(…, momento=)` e `avisar_retorno_para_interesse(…, motivo=)`; `apps/rodadas/fechamento.py`: o código de recusa novo e o motivo `minimo_nao_atingido_na_abertura`.
- `apps/rodadas/views.py`, `config/urls.py` e `templates/rodadas/estoque.html`: a rota `rodadas_pagamento_abrir`, o formulário e o bloco de `pagamento`.
- Testes: `tests/tecnicos/test_pedidos_abertura.py`, `test_pedidos_abertura_tela.py` e `test_pedidos_concorrencia.py` (A-20 e A-21); apoio em `tests/apoio/pedidos.py`.

## Andaime (exceção técnica)

Antes do Red: os cinco modelos **sem** base de só inserção, sem `CHECK` e sem trigger (migração `0001`), e `abrir_pagamento` que devolve `ResultadoDaAbertura(None, "interesse")` sem fazer nada. As restrições, as triggers e o log entraram depois, na migração `0002` e na base `RegistroDoPedido`, para que o A-11 e os `CHECK` tivessem Red.

## Red (arquivos inteiros, sem `-k`)

Foram duas execuções, por um erro meu na primeira:

1. `uv run pytest tests/tecnicos/test_pedidos_abertura.py tests/tecnicos/test_pedidos_abertura_tela.py tests/tecnicos/test_pedidos_concorrencia.py tests/tecnicos/test_permissoes_politica_rotas.py -q`: **42 failed, 16 passed** (passaram os testes do arquivo de permissões, que não mudaram, e o controle do A-12). Nessa execução, o A-11 falhou pela pré-condição (`assert None is not None`, porque o serviço ainda não gravava nada) e o A-4 falhou por um erro do próprio teste (alterei `quantidade_original`, que a trigger da E03-04 protege). Ou seja, o Red do A-11 (imutabilidade) e do A-4 **não** tinha sido observado por asserção do comportamento.
2. Corrigi o teste do A-4 (o arranjo passou a aceitar `pendente_a_p1`) e o do A-11 (grava a composição direto, sem o serviço, em `_composicao_minima`). Com o andaime trocado de volta (modelos sem base nem restrição, sem a migração `0002` e o serviço vazio), rodei o arquivo `test_pedidos_abertura.py` inteiro: **22 failed, 1 passed**. As telas e a concorrência ficaram com o Red da execução 1.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_abertura_congela_um_pedido_por_comprador` | `assert 'interesse' == Etapa.PAGAMENTO` |
| A-2 | `test_caixas_numeradas_por_produto` | `assert [] == [(1, …), …]` |
| A-3 | `test_itens_guardam_a_copia_do_produto` | `AssertionError: pedidos do comprador: 0` |
| A-4 | `test_parcela_atendida_em_parte_pela_fila_fica_pendente` | `AssertionError: pedidos do comprador: 0` |
| A-5 | `test_parcela_sem_pendente_vira_em_pedido_com_a_reserva` | `assert 'ativa' == SituacaoParcela.EM_PEDIDO` |
| A-6 | `test_comprador_suspenso_antes_da_abertura_refaz_as_caixas` | `assert 'fechamento_encerrado' == Etapa.INTERESSE` |
| A-7 | `test_preco_reduzido_antes_da_abertura_derruba_o_minimo` | `assert 'fechamento_encerrado' == Etapa.INTERESSE` |
| A-8 | `test_preco_aumentado_antes_da_abertura_entra_no_pedido` | `AssertionError: aberturas: 0` |
| A-9 | `test_so_o_fechamento_encerrado_abre_o_pagamento` (3 etapas) | `DID NOT RAISE TransicaoRecusada` |
| A-10 | `test_autor_e_frete_invalidos_nao_gravam_nada`, `test_frete_acima_da_capacidade_e_recusado` | `DID NOT RAISE PermissionDenied` e `DID NOT RAISE ValueError` |
| A-11 | `test_composicao_do_pedido_nao_muda_nem_some` | `DID NOT RAISE RegistroImutavel` |
| A-11 (banco) | `test_o_banco_recusa_pedido_incoerente` | `DID NOT RAISE DatabaseError` |
| A-11 (unicidade) | `test_a_abertura_e_unica_por_ciclo` | **passou no Red**: a `OneToOne` do ciclo já era parte do modelo do andaime. Cobertura de regressão |
| A-13 | `test_composicao_fica_congelada_apos_a_abertura` | `assert []` (nenhum item congelado) |
| A-14 | `test_produto_por_peso_guarda_o_subtotal_arredondado` | `assert 0 == 1` |
| A-15 | `test_aviso_de_pagamento_aberto_por_comprador` | `ValueError: not enough values to unpack` (nenhum aviso) |
| A-16 | `test_falha_do_whatsapp_nao_desfaz_a_abertura` | `assert 0 == 2` |
| A-17 | `test_auditoria_da_abertura` | `ValueError: not enough values to unpack` (nenhuma auditoria) |
| invariante | `test_o_total_da_abertura_e_o_valor_elegivel_do_progresso` | `AssertionError: aberturas: 0` |
| caixa incompleta | `test_excedente_na_abertura_sai_e_o_pedido_so_leva_caixas_completas` | `AssertionError: pedidos do comprador: 0` |
| A-18 | `test_o_bloco_oferece_o_formulario_do_frete`, `test_abrir_pelo_formulario_redireciona_com_o_prazo`, `test_frete_invalido_volta_com_o_erro_do_campo` (5), `test_em_pagamento_mostra_t0_prazo_e_margem_sem_formulario`, `test_retorno_por_minimo_redireciona_com_o_aviso` | ausência do formulário no HTML, `AssertionError: 404`, `assert 404 == 400`, ausência de `03/11/2026 10:00` |
| A-9 (tela) | `test_transicao_recusada_responde_409` (3) | `assert 404 == 409` |
| A-19 | `test_rota_so_aceita_post`, `test_comprador_fornecedor_e_anonimo_sao_recusados`, `test_a_rota_declara_a_politica_de_administrador` | `assert 404 == 405`, `assert 404 in (302, 403)`, `Resolver404` |
| A-12 | `test_interesse_depois_da_abertura_e_recusado_com_409` | `assert []` (nenhum pedido congelado); `test_nenhuma_rota_altera_pedido_item_t0_ou_frete` **passou no Red** (controle: ainda não havia rota) |
| A-20 | `test_duas_aberturas_ao_mesmo_tempo_abrem_uma_so` | falhou na asserção do resultado (nenhuma `TransicaoRecusada` na segunda) |
| A-21 | `test_preco_gravado_antes_da_abertura_entra_nos_itens`, `test_preco_gravado_depois_da_abertura_nao_muda_os_itens` | falharam na asserção dos preços dos itens (nenhum item) |

## Green e verificações

- Os quatro arquivos: **58 passed**. Antes, em conjunto com os testes de encerramento, retorno, telas e aviso do fechamento (E06): **122 passed**.
- `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- A suíte completa roda ao final da milestone (última fatia).

## Decisões técnicas e divergências para o revisor e o especificador

- **A-21, última cláusula ("nenhum `preco_alterado` para A nem para B" nos dois casos).** Não se sustenta quando o preço vem antes da abertura: nesse caso o aviso da E05-06 é devido, porque as parcelas ainda estavam `ativa` quando o preço mudou. O teste da ordem "preço antes" confere que A e B recebem exatamente esse aviso; o da ordem "preço depois" confere que não recebem nenhum, como o critério diz. **Pedido ao especificador:** confirmar ou corrigir o critério.
- **A-12, o administrador.** Ele não tem interesses e a política `comprador_ativo` o recusa com 403, e não com 409. O teste confere o 409 para o comprador A e a recusa (302 ou 403) para o administrador, sem alteração nos pedidos.
- **A-14.** Para o produto por peso, o mínimo do fornecedor vale R$ 0,00 (`sem_minimo`); com R$ 100,00 a rodada voltaria para interesse.
- **Testes reforçados depois do Red:** a unicidade e os `CHECK` da `SituacaoDoPedido` (`test_o_banco_recusa_pedido_incoerente`) e o caso de excedente na abertura (`test_excedente_na_abertura…`). Não substituem nenhuma asserção.
- **Log da tentativa de alterar.** Pelo ORM, `save()` e `delete()` gravam `Tentativa de alterar pedido congelado: <Modelo> <id>`. Nas operações em lote (`update`, `delete`, `bulk_update`), um log por registro atingido.
- **Total da abertura.** `abrir_pagamento` confere, antes de gravar a etapa, que `total_produtos` é igual ao valor elegível do progresso lido sob as mesmas travas (`RuntimeError` se divergir); a invariante da spec.
- **Prazos do bloco.** O fim do prazo e o fim da margem são calculados com `somar_horas(t0, 24)` e `somar_horas(t0, 48)`; a E08-05 os troca pelas funções de `prazos.py`.

## Limites da verificação

Postgres real, cliente HTTP do Django e threads reais; sem navegador, sem o worker como processo e sem rede. Nenhuma mutação aplicada.
