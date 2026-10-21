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

---

## Registro do implementador — correções R01 a R06 (2026-10-21)

Status: implementadas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Fontes lidas antes de editar: o parecer em `docs/specs/E08-01/review.md` e as seções de correção de cada `spec.md` e `acceptance.md` (commit `7a1fb49`).

### R04 — pedido de valor zero (decisão do responsável: restringir no cadastro)

Arquivos: `apps/catalogo/models.py` (restrição `produto_menor_quantidade_custa_um_centavo`) e migração `0003_valor_minimo.py`; `apps/catalogo/servicos.py` (`criar_produto`, `editar_produto` e `alterar_incremento`, com o código novo `centavo`). Nenhuma view, template ou rota mudou: as telas já mostram os erros do serviço.

Red (arquivos inteiros, sem `-k`): `uv run pytest tests/tecnicos/test_catalogo_valor_minimo.py tests/tecnicos/test_pedidos_abertura.py -q`: **5 falharam, 24 passaram**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-22 | `test_criar_recusa_a_menor_quantidade_abaixo_de_um_centavo` | `Failed: DID NOT RAISE ValidationError` |
| A-23 | `test_editar_preco_recusa_e_nada_e_gravado` | `DID NOT RAISE ValidationError` |
| A-24 | `test_alterar_incremento_recusa_o_que_ficaria_abaixo_de_um_centavo` | `DID NOT RAISE IncrementoIncompativel` |
| A-25 | `test_o_banco_recusa_a_combinacao_na_criacao_e_no_update` | `DID NOT RAISE IntegrityError` |
| A-26 | `test_a_menor_combinacao_aceita_abre_sem_pedido_de_valor_zero` | **passou no Red**: é o caso-limite aceito (0,001 kg a R$ 5,00), que o código já tratava; fica como regressão |
| A-27 | `test_as_telas_mostram_a_mensagem_no_campo_e_nada_e_gravado` | a mensagem não aparece na página |

Green: os cinco passaram (`test_catalogo_valor_minimo.py`); a suíte inteira na época, 2138 aprovados. **Nenhum teste anterior precisou de ajuste de dados.**

Decisões técnicas: comparação em `Decimal` exato, fronteira inclusiva (R$ 5,00 com 0,001 aceita); a restrição do banco usa `ExpressionWrapper(preco * incremento)` com `DecimalField(30, 5)`; no `editar_produto` a recusa vem depois da trava do produto, com o incremento atual, antes de qualquer gravação; no `alterar_incremento` é a última recusa. A §4.2 da especificação funcional não foi alterada (cabe ao responsável).

## Não conformidade de TDD (R06) — E08-02 A-4, A-11, A-20 e A-21

Tratamento decidido pelo responsável em 2026-10-21: o mesmo da E05-R04 e da E06-R05. Os registros anteriores acima ficam sem edição.

### 1. Evidência histórica procurada

Não há commit anterior ao código de produção (os commits da E08 são um por fatia, feitos depois do Green). A única fonte datada é o registro da sessão: `C:/Users/wsgon/.claude/projects/C--Users-wsgon-OneDrive-Desktop-AI-Hive-om/eca958a3-5baa-41c1-b7a8-d4c5947c3fdc.jsonl` (registro da sessão, com horário UTC; os números são índices de linha, base 0). O resultado da procura:

| Critério | O que o registro mostra | Conclusão |
|---|---|---|
| A-4 e A-11 | Linha 13054 (19:14:42Z): Red de 42 falhas e 1 aprovação contra o andaime vazio. Linhas 13139 a 13166 (19:19:34Z a 19:19:58Z): `abertura.py` e `models.py` escritos. Linha 13185 (19:20:32Z): 1 falha e 57 aprovações; a falha era o A-4, por erro do meu teste (alterei `quantidade_original`, protegida). O teste do A-4 foi corrigido na linha 13193 (19:20:50Z) e o do A-11 na linha 13225 (19:22:11Z), **depois** de o código existir. Só então o andaime foi trocado de volta (linha 13241, 19:22:28Z) e o Red foi refeito (linha 13254). | **Sem Red válido anterior ao código.** O Red comprovado é contra um andaime recriado depois do código. |
| A-20 e A-21 | O arquivo de concorrência foi criado na linha 13042 (19:14:38Z) e o Red (linha 13054) falhou porque a abertura não existia. As travas entraram junto com o serviço, na linha 13139 (19:19:34Z). | **Sem o ciclo** verde sem trava → Red da corrida → trava. |

### 2. O que aconteceu

- **A-4 e A-11:** Red obtido contra andaime recriado depois do código; sem Red observado antes do código de produção.
- **A-20 e A-21:** Red só pela ausência do serviço; sem o ciclo verde sem trava → Red da corrida → trava.

Nenhum texto deste registro dá a entender que houve Red válido nesses critérios.

### 3. Causas

Confirmo as três causas prováveis da spec: (1) o Green foi maior que o mínimo, com as travas escritas junto com o comportamento; (2) a tabela de cobertura não separava critério de concorrência de critério funcional; (3) o andaime dependia dos testes, e os testes do A-4 e do A-11 só foram corrigidos depois que o código existia.

### 4. Sensibilidade (mutação), não Red

Cada mutação retira só a proteção do critério. Comandos: `uv run pytest <arquivo inteiro> -q -p no:cacheprovider --create-db`, sem `-k`. Depois de cada uma, o arquivo foi restaurado por `git checkout -- <arquivo>` (o `git diff --ignore-cr-at-eol` estava vazio: só mudou o fim de linha) e a suíte voltou a passar (ver a verificação final).

| Critério | Mutação | Arquivo de teste | Resultado da mutação |
|---|---|---|---|
| A-4 | `abertura.py`: `if parcela.quantidade_pendente == 0:` vira `if True:` (parcela inteira como `em_pedido`) | `test_pedidos_abertura.py` | 1 falhou, 23 passaram: `test_parcela_atendida_em_parte_pela_fila_fica_pendente`, `AssertionError: ('em_pedido', …) == (PENDENTE, …)` |
| A-11, caminho do ORM | `models.py`: `ParcelaNoPedido(RegistroDoPedido)` vira `ParcelaNoPedido(models.Model)` | `test_pedidos_abertura.py` | 1 falhou, 23 passaram: `test_composicao_do_pedido_nao_muda_nem_some`. A falha chega como `IntegrityError` da trigger no lugar do `RegistroImutavel` esperado pelo `pytest.raises`; é falha do critério, mas não por asserção própria |
| A-11, caminho da trigger | migração `0002`: sai `instalar_protecao_so_insercao("pedidos_parcelanopedido")` | `test_pedidos_abertura.py` | 1 falhou, 23 passaram: `Failed: DID NOT RAISE DatabaseError` |
| A-20 | `abertura.py`: a rodada relida sem `select_for_update` | `test_pedidos_concorrencia.py` | **17 passaram: a mutação não foi detectada** (limite abaixo) |
| A-20, complemento | os dois: fornecedor e rodada sem `select_for_update` | `test_pedidos_concorrencia.py` | 1 falhou, 16 passaram: `test_duas_aberturas_ao_mesmo_tempo_abrem_uma_so`, `AssertionError: 'fora_de_fechamento_encerrado' == 'fora_de_fechamento_encerrado_para_pagamento'` |
| A-21 | `fechamento.py`, `_divisao_dos_excedentes`: sai `travar_estoque` (que trava o produto), único ponto onde a abertura trava os produtos | `test_pedidos_concorrencia.py` | 2 falharam, 15 passaram: `test_preco_gravado_antes_da_abertura_entra_nos_itens` e `test_preco_gravado_depois_da_abertura_nao_muda_os_itens`, `AssertionError: {10.00} == {11.00}` |

**Limite do teste (A-20).** A trava do fornecedor, que vem antes, já serializa as duas aberturas; a trava da rodada, sozinha, é redundante para esse teste. Retirando as duas, o teste falha por asserção. Reforço proposto, sem mudar o critério: um teste que segure só a trava da rodada (outra thread tentando travar a rodada diretamente) e confira que a abertura espera. Fica a cargo de quem revisar decidir se o reforço entra agora.

Observação sobre o A-21: a spec fala em "ler os produtos sem trava na abertura"; no código a trava dos produtos está em `travar_estoque`, chamado pela divisão dos excedentes, e a mutação foi feita ali.
