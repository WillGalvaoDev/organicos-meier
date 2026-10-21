# E08-05 — Revisão independente do agente 3 — 2026-10-21

**REPROVADO sobre `2714a6a2acaf88cc69e02345facf2a2403a66374`, branch `e08-implementacao`. E08 global: REPROVADO.**

Matriz examinada: **A-1 a A-21**, a partir de spec.md/acceptance.md e das fontes superiores, antes de avaliar o código. R01: pedidos pagos excluídos da reconsulta, em desacordo com infraestrutura 4.3. R03: cobrança criada antes do prazo, cuja resposta se perdeu, segue pendente mesmo depois de a busca encontrá-la. Os testes nominais de prazos, tarefas e acompanhamento passam, mas não cobrem essas combinações.

TDD declarado: **16 failed, 17 passed; justificativas de controles herdados/já verdes conferidas. A-20 herdado da quitação não exige fabricar Red tardio.** O revisor confere registro, testes e diffs; não presenciou a execução histórica. Reexecuções atuais não substituem evidência de Red anterior à implementação.

Verificações independentes: suíte completa **1 failed, 2129 passed in 292.98s**, sem exclusões; provas adicionais **5 failed, 2 passed in 17.36s**; lint, formatação (288 arquivos), tipos (338 arquivos) e verificação de migrações passaram. A falha versionada é a de rotas descrita em R05; as cinco falhas adicionais correspondem a R01, R02 (duas variantes), R03 e R04.

O [parecer consolidado](../E08-01/review.md) contém matriz das sete fatias, referências, classificação, resultados, código completo das provas, limites e encaminhamentos R01–R07. R04 requer decisão sobre pedido zero, e R06 requer evidência histórica ou tratamento autorizado; as perguntas foram encaminhadas durante a revisão. R07 está no registro central como M-3.

Somente documentação foi alterada pelo revisor, sem correção silenciosa de produção ou testes. Histórico do implementador preservado integralmente abaixo. Próximo gate: correções/comprovações e nova revisão independente.

---

## Registro anterior integralmente preservado

# E08-05 — Registro do implementador (2026-10-20)

Status: implementada; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia, as E08-02 a E08-04 e a E06-04 (prorrogação só do fechamento).

## Arquivos

- `apps/pedidos/prazos.py`: `prazo_de_pagamento`, `fim_da_margem`, `aceita_tentativas`, `em_margem` e `pode_iniciar_apuracao`. `pedir_pagamento`, `decidir_destino`, a operação de criação, as telas do comprador e o bloco do administrador passaram a usá-las (refatoração, sem mudar comportamento).
- `apps/pedidos/tarefas.py`: `bloquear_tentativas_vencidas` (a cada minuto) e `reconsultar_pagamentos_da_margem` (`*/10 * * * *`), as duas com `queueing_lock`, e as funções testáveis `…_agora()`.
- `apps/pedidos/acompanhamento.py`: `situacao_dos_pedidos` e `devolucoes_devidas`.
- `apps/pagamentos/consulta.py`: `aprovados_da_referencia` e `travar_pagamento` (leitura e trava; nenhuma escrita).
- `apps/rodadas/views.py` e `templates/rodadas/estoque.html`: a linha do tempo, a tabela dos pedidos e as devoluções devidas no bloco do administrador em `pagamento`.
- Testes: `test_pedidos_prazos.py` (A-1 a A-15, A-18, A-19), `test_pedidos_acompanhamento.py` (A-16, A-17) e, em `test_pedidos_concorrencia.py`, A-20 e A-21.

## Andaime (exceção técnica)

Antes do Red: as cinco funções de `prazos.py` com valores fixos, as duas funções `…_agora()` que devolvem zero, as funções de `acompanhamento.py` que devolvem lista vazia e nenhuma tarefa registrada.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pedidos_prazos.py tests/tecnicos/test_pedidos_acompanhamento.py tests/tecnicos/test_pedidos_concorrencia.py -q`: **16 failed, 17 passed**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_as_fronteiras_da_linha_do_tempo` | `assert datetime(2026, 11, 2, 13, 0) == datetime(2026, 11, 3, 13, 0)` |
| A-2 | `test_a_apuracao_so_pode_comecar_em_48_horas` | `assert False is True` |
| A-3 | `test_bloqueio_cancela_so_o_que_esta_pendente` | `assert 0 == 1` |
| A-4 | `test_bloqueio_nao_repete_o_que_ja_foi_agendado` | `assert 0 == 1` |
| A-5 | `test_cancelamento_recusado_nao_e_reagendado` | `assert 0 == 1` |
| A-10 | `test_a_margem_reconsulta_e_encontra_o_pagamento_sem_aviso` | `assert 0 == 2` |
| A-12 | `test_provedor_fora_do_ar_na_margem_registra_o_motivo` | `AssertionError: []` (nenhum aviso no log) |
| A-13 | `test_a_margem_decide_o_destino_que_ficou_pendente` | `assert 'aguardando_pagamento' == 'pago'` |
| A-14 | `test_nenhuma_rota_formulario_ou_servico_altera_os_prazos` | erro de preparação no primeiro Red (ver abaixo) |
| A-15 | `test_o_t0_nao_muda_nem_por_sql` | `assert (…) == (…)` dos prazos (as funções do andaime devolvem `T0`) |
| A-18 | `test_as_tarefas_estao_registradas_como_periodicas` | `AssertionError: bloquear_tentativas_vencidas` |
| A-19 | `test_falha_numa_abertura_nao_impede_as_outras` | `assert 0 == 1` |
| A-16 | `test_a_pagina_mostra_a_linha_do_tempo_os_pedidos_e_as_devolucoes` | `KeyError: 'Comprador A'` (a página não tem a tabela) |
| A-16 | `test_o_servico_devolve_as_linhas_e_as_devolucoes`, `test_sem_devolucoes_a_lista_diz_que_nao_ha` | falharam: listas vazias e ausência de "Nenhuma devolução devida." |
| A-21 | `test_bloqueio_e_aviso_de_outra_mudanca_ao_mesmo_tempo` | `assert 'pendente' == 'cancelado'` |

Passaram no Red, e o motivo está registrado:

- **A-6, A-11** (`test_antes_do_prazo_o_bloqueio_nao_faz_nada`, `test_fora_da_margem_a_reconsulta_nao_consulta_nada`): o andaime devolve zero e não consulta; são prova de regressão depois do Green.
- **A-7, A-8, A-9** (`test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa`, `test_na_margem_nada_se_reabre`, `test_depois_de_48_horas_nada_acontece_sozinho`): o comportamento já vinha da E08-03 e da E05/E06 (recusa no servidor, etapa `pagamento` sem interesses); aqui entram como prova de que nada reabre nem se move sozinho, inclusive depois das tarefas.
- **A-17** (`test_comprador_e_fornecedor_nao_veem_a_pagina`): a política da página já existe (E06).
- **A-20 (i), (ii) e (iii)** (`test_bloqueio_e_aviso_em_qualquer_ordem_quitam_uma_vez` e `test_bloqueio_e_aviso_ao_mesmo_tempo_quitam_uma_vez`): o resultado esperado depende só do que o provedor registrou e da decisão da E08-04; sem o bloqueio, o aviso sozinho já quita. **Não foi possível observar Red aqui.** O teste vale como prova de que o bloqueio não altera o resultado depois do Green. Os testes de concorrência da E08-04 (A-16 e A-17) cobrem as travas da decisão.

Erro de preparação no primeiro Red: o teste do A-14 chamava `administrador_logado` depois de montar o arranjo, e a conta de administrador já existia (`conta_administrador_unico`). A ordem foi corrigida (o administrador entra antes do arranjo, como nos outros testes de tela), sem mudar a asserção.

## Green e verificações

- Os quatro arquivos da E08-05 e `test_pedidos_abertura_tela.py`: **50 passed**. Conjunto `-k "pedidos or pagamentos or rodadas or interesses or permissoes or nucleo or varredura"`: **1011 passed**.
- `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- A suíte completa roda ao final da milestone.

## Decisões técnicas e ajustes

- **Formato das datas no bloco do administrador.** A E08-05 define a linha "Prazo de pagamento até 03/11/2026 às 10:00. Margem até 04/11/2026 às 10:00."; o bloco da E08-02 mostrava as datas como "03/11/2026 10:00". As três asserções do `test_pedidos_abertura_tela.py` foram ajustadas ao formato com "às" (a E08-02 só pedia "mostrar" os instantes no fuso da operação); o conteúdo continua o mesmo.
- **Bloqueio.** Cada tentativa `criada` sem chamada `cancelar_cobranca` com o alvo `t<id>:prazo` (em qualquer situação, inclusive `falhou`) tem o cancelamento agendado por `agendar_cancelamento`, que só agenda se o pagamento não é terminal. Uma abertura que falha vai para o log com o id e o tipo da exceção.
- **Margem.** Reconsulta os pedidos `aguardando_pagamento` e `cancelado` da abertura em margem (os dois extremos incluídos), uma consulta por pedido fora de transação; depois decide o destino dos aprovados sem destino (`aprovados_da_referencia` + `travar_pagamento` + `decidir_destino`, numa transação por pagamento).
- **Cenário 37.** As tarefas e o acompanhamento não citam `PagamentoNoProvedor` nem escrevem nele (ver a E08-04 e o item M-2 de `docs/melhorias.md`).
- **"Sem resposta do provedor".** A última chamada entre a criação, os cancelamentos e as consultas do pedido está `pendente` com `ultimo_erro` preenchido.

## Limites da verificação

Postgres real, cliente HTTP do Django, threads reais e a fila do Procrastinate no banco; sem o worker como processo, navegador ou rede. Nenhuma mutação aplicada.
