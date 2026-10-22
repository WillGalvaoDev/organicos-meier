# E08-03 — Terceira revisão independente — 2026-10-22

**APROVADO sobre `fe8dffa`.** Matriz: A-1 a A-34. **A E08 integrada está APROVADA**, com R06/R08 encerrados, conforme [parecer consolidado](../E08-01/review.md).

R08 encerrado: uma consulta agendada por pagamento, sem reter situação e depois adquirir outro pagamento. A-29–A-34, provas independentes de aviso/margem e controle de mutação confirmam concorrência, rollback, recuperação e idempotência. A-23/A-24 tiveram somente o ponto de observação ajustado, conforme autorização. Registro Red/Green aceito com a distinção entre asserções funcionais e estruturais de A-31; A-32 é regressão herdada.

Verificação independente: suíte completa sem filtro, **2166 passed in 220.50s**; Ruff, formatação, mypy e migrações sem pendências. Oito provas independentes passaram. Mutações de controle A-11 e R08 falharam pelos motivos esperados; arquivo concorrente inteiro sem mutações: **20 passed in 9.50s**. Comandos, reprodução, evidências de TDD e limites estão no parecer consolidado.

Os textos anteriores do revisor e do implementador foram conferidos e preservados integralmente abaixo. Nenhuma alteração em produção ou teste versionado. Aprovação restrita à entrega e ao commit revisado, sem afirmar integração em main. Melhorias M-3/M-4 seguem a política de revisão final.

---

## Histórico integralmente preservado

# E08-03 — Nova revisão independente — 2026-10-21

**REPROVADO sobre `584b323`.** Matriz: A-1 a A-28. A E08 integrada continua **REPROVADA**, por R06 e R08, conforme o parecer consolidado em [E08-01/review.md](../E08-01/review.md).

R02/R03 originais corrigidos e provas anteriores verdes. R08 novo e importante: `_criacao_falhou` sincroniza vários pagamentos na mesma transação, retém a situação após P1 e espera P2, enquanto o aviso retém P2 e espera a situação. Prova independente reproduziu `deadlock detected`; repetição recuperou os dois destinos. Corrigir ordem global com Red real e testar concorrência/rollback. Tratamento de TDD antigo de A-19 registrado e aceito.

Verificação independente global: `uv run pytest -q` sem filtro, **2160 passed in 246.21s**; Ruff lint/formatação, mypy e migrações sem pendências. Provas anteriores R01–R03: seis casos aprovados. Nova prova R08 falha por deadlock; controle de recuperação após rollback passa antes da asserção final de ausência de impasse. Comandos, fontes, limites, análise de TDD e reprodução completa no parecer consolidado.

O texto anterior do revisor e os registros do implementador foram conferidos e preservados integralmente abaixo. Nenhum código de produção ou teste versionado alterado pelo revisor.

---

## Histórico integralmente preservado

# E08-03 — Revisão independente do agente 3 — 2026-10-21

**REPROVADO sobre `2714a6a2acaf88cc69e02345facf2a2403a66374`, branch `e08-implementacao`. E08 global: REPROVADO.**

Matriz examinada: **A-1 a A-20**, a partir de spec.md/acceptance.md e das fontes superiores, antes de avaliar o código. R02: tentativa solicitada antes da moderação cria cobrança pendente depois dela. R03: resposta perdida antes de 24h vira nao_criada depois do prazo e escapa ao cancelamento. R06: falta evidência do ciclo específico da trava de A-19.

TDD declarado: **28 failed, 20 passed; tabela conferida, com ressalva de concorrência R06.** O revisor confere registro, testes e diffs; não presenciou a execução histórica. Reexecuções atuais não substituem evidência de Red anterior à implementação.

Verificações independentes: suíte completa **1 failed, 2129 passed in 292.98s**, sem exclusões; provas adicionais **5 failed, 2 passed in 17.36s**; lint, formatação (288 arquivos), tipos (338 arquivos) e verificação de migrações passaram. A falha versionada é a de rotas descrita em R05; as cinco falhas adicionais correspondem a R01, R02 (duas variantes), R03 e R04.

O [parecer consolidado](../E08-01/review.md) contém matriz das sete fatias, referências, classificação, resultados, código completo das provas, limites e encaminhamentos R01–R07. R04 requer decisão sobre pedido zero, e R06 requer evidência histórica ou tratamento autorizado; as perguntas foram encaminhadas durante a revisão. R07 está no registro central como M-3.

Somente documentação foi alterada pelo revisor, sem correção silenciosa de produção ou testes. Histórico do implementador preservado integralmente abaixo. Próximo gate: correções/comprovações e nova revisão independente.

---

## Registro anterior integralmente preservado

# E08-03 — Registro do implementador (2026-10-20)

Status: implementada; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia, a E08-02 (pedido e abertura), `apps/pagamentos` (interface do provedor, chamadas, sincronização, tarefa) e o simulador (E07).

## Arquivos

- `apps/pedidos/models.py` (e migrações `0003_tentativa` e `0004_restricoes_da_tentativa`): `TentativaDePagamento` e `Pedido.referencia_externa`.
- `apps/pedidos/pagamento.py`: `pedir_pagamento`, `PagamentoRecusado`, `agendar_cancelamento`, `tentativa_aberta` e o disparo imediato.
- `apps/pedidos/operacoes.py` (registrada no `ready()`): `criar_cobranca` e `cancelar_cobranca`.
- `apps/pagamentos/chamadas.py`: `FalhaDefinitiva`, tratada como `RecusaDoProvedor`, e a função `nao_encontrado` (a regra das 24 horas de `consultar_pagamento`, extraída para as duas operações usarem a mesma).
- `apps/pedidos/views.py`, `apresentacao.py`, `templates/pedidos/lista.html` e `detalhe.html`, `config/urls.py`: as três rotas.
- `tests/conftest.py`: o gancho que declara os dois bancos agora cobre os arquivos `test_pedidos_*` e `test_simulador_pagamentos_*` (além de `test_pagamentos_*`). Nenhuma asserção mudou.
- Testes: `test_pedidos_tentativas.py`, `test_pedidos_telas_comprador.py` e, em `test_pedidos_concorrencia.py`, A-19 e A-20; apoio em `tests/apoio/pedidos.py`.

## Andaime (exceção técnica)

Antes do Red: `TentativaDePagamento` sem restrições (migração `0003`), `Pedido.referencia_externa`, `PagamentoRecusado` e `pedir_pagamento`/`agendar_cancelamento` que não fazem nada, e `FalhaDefinitiva` que ainda não era tratada pela tarefa. As operações, as rotas e as restrições vieram no Green.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pedidos_tentativas.py tests/tecnicos/test_pedidos_telas_comprador.py tests/tecnicos/test_pedidos_concorrencia.py tests/tecnicos/test_permissoes_politica_rotas.py -q`: **28 failed, 20 passed**. Passaram: os testes de permissões (15), os três de concorrência da E08-02 (regressão) e dois controles (abaixo).

Os `assert 0 == 1` pararam num passo intermediário do teste (nenhuma tentativa, chamada ou cobrança existia), antes das asserções finais do critério.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_pedir_pagamento_cria_a_tentativa_e_agenda_a_cobranca` | `AssertionError: tentativas: 0` |
| A-2 | `test_a_tarefa_cria_a_cobranca_no_provedor` | `assert 0 == 1` (a tarefa não tentou nenhuma chamada) |
| A-3 | `test_com_tentativa_aberta_devolve_a_mesma`, `test_solicitada_conta_como_aberta` | `assert 0 == 1` |
| A-4 | `test_apos_expirar_uma_nova_tentativa_e_permitida` | `assert 0 == 1` |
| A-5 | `test_fronteira_de_24_horas_para_pedir_pagamento` | `assert 0 == 1` (nenhuma tentativa) |
| A-6 | `test_tarefa_depois_do_prazo_nao_cria_cobranca` | `assert 0 == 1` |
| A-7 | `test_recusas_do_pedido_e_da_conta` (pago, cancelado, suspenso, de outro) | `DID NOT RAISE PagamentoRecusado` (4) |
| A-8 | `test_provedor_fora_do_ar_repete_com_a_mesma_chave` | `assert 0 == 1` |
| A-9 | `test_falha_depois_de_o_provedor_criar_devolve_a_mesma_cobranca` | `assert 0 == 1` |
| A-10 | `test_agendar_cancelamento_uma_vez_por_motivo`, `test_agendar_cancelamento_exige_transacao` | `assert 0 == 1` (a criação não ocorre) |
| A-10 (negativo) | `test_so_tentativa_criada_tem_cancelamento` | **passou no Red**: o andaime já não agenda nada; passa a ser prova depois do Green, quando a função tem a verificação real |
| A-11 | `test_aprovacao_no_instante_do_cancelamento_vale_o_que_o_provedor_registrou` | `assert 0 == 1` |
| A-12 | `test_falha_definitiva_encerra_a_chamada_sem_repetir` | `assert 'pendente' == SituacaoDaChamada.FALHOU` |
| A-13 | `test_disparo_imediato_depois_do_commit` | `assert 0 == 1` |
| A-14 a A-17 | `test_lista_e_detalhe_com_tentativa_aberta`, `test_sem_tentativa_o_botao_gera_a_cobranca`, `test_anonimo_fornecedor_e_suspenso_sao_recusados`, `test_as_tres_rotas_declaram_a_politica`, `test_pagamento_recusado_responde_409_com_a_mensagem`, `test_suspenso_ve_os_pedidos_sem_botao_de_pagar`, `test_prazo_encerrado_na_lista_e_sem_botao` | `assert 404 == 200`, `assert 404 == 302`, `assert 404 == 409`, `Resolver404`, ausência de "Pagar com Pix" |
| A-16 | `test_pedido_de_outro_comprador_nao_aparece` | **passou no Red**: sem as rotas, tudo era 404. Vira prova real depois do Green (a rota existe e responde 404 ao outro comprador) |
| A-18 | `test_log_e_auditoria_nao_levam_dados_do_pagador` | `assert 0 == 1` |
| A-19 | `test_dois_cliques_em_pagar_geram_uma_tentativa` | `assert 0 == 1` (nenhuma tentativa) |
| A-20 | `test_cancelamento_em_execucao_nao_trava_a_moderacao` | `assert 0 == 1` |

Mais um ciclo, depois do primeiro Green, para as restrições do banco (regra do modelo, sem critério numerado): `test_o_banco_recusa_tentativa_incoerente` falhou com `DID NOT RAISE DatabaseError` antes da migração `0004` e passou depois dela.

## Green e verificações

- Os arquivos da E08-02 e E08-03, mais `test_permissoes_politica_rotas.py` e `test_pagamentos_chamadas.py`: **107 passed**.
- `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- A suíte completa roda ao final da milestone.

## Decisões técnicas

- **Tentativa aberta.** `solicitada`, ou `criada` com o pagamento `pendente` (sem registro do pagamento, conta como aberta); as outras permitem uma tentativa nova.
- **Disparo imediato.** `transaction.on_commit` enfileira `processar_chamadas_ao_provedor`; `AlreadyEnqueued` é ignorada e qualquer outra falha vai para o log sem dados. O `defer` roda num `atomic()` próprio, para a recusa do `queueing_lock` não deixar a transação corrente abortada.
- **Ordem das travas.** `pedir_pagamento` trava a situação do pedido e depois as tentativas; nunca um pagamento. O `concluir` da criação chega com o pagamento travado pela sincronização e então trava a tentativa.
- **`conta_inativa`** relê a conta depois das travas, para uma suspensão confirmada entre o clique e a trava aparecer.
- **`nao_e_seu`** tem a mensagem "Este pedido não é seu."; a rota responde 404 antes de chegar ao serviço.
- **Descrição da cobrança** "Orgânicos Méier — pedido <id>"; a validade vem de `T0 + 24h`, igual em todas as repetições da mesma chave (o simulador recusa a chave reutilizada com dados diferentes).
- **`pagar`** usa `exige_comprador_ativo`: o suspenso recebe 403 pela política, e `conta_inativa` fica para a corrida.
- O fim do prazo mostrado nas telas é calculado com `somar_horas(t0, 24)`; a E08-05 troca pela função de `prazos.py`.

## Limites da verificação

Postgres real, cliente HTTP do Django, threads reais e a fila do Procrastinate no banco; sem o worker como processo, sem navegador e sem rede. Nenhuma mutação aplicada.

---

## Registro do implementador — correções R01 a R06 (2026-10-21)

Status: implementadas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Fontes lidas antes de editar: o parecer em `docs/specs/E08-01/review.md` e as seções de correção de cada `spec.md` e `acceptance.md` (commit `7a1fb49`).

### R02 e R03 — a criação que não pode mais ser paga

Arquivos: `apps/pagamentos/chamadas.py` (`FalhaDefinitiva(codigo, *, encontrados=())`); `apps/pedidos/operacoes.py` (`_motivo_da_recusa`, `_recusar_criacao`, `_concluir_criacao` com a situação travada, `_criacao_falhou` que sincroniza o encontrado e agenda `t<tentativa>:recuperacao:<n>`); `apps/pedidos/apresentacao.py` (a espera só aparece dentro do prazo).

Red (arquivos inteiros): `uv run pytest tests/tecnicos/test_pedidos_tentativas.py tests/tecnicos/test_pedidos_moderacao.py tests/tecnicos/test_pedidos_telas_comprador.py -q`: **11 falharam, 40 passaram**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-21 | `test_criacao_de_pedido_cancelado_e_recusada_sem_criar_cobranca` | `('concluida', '') == (FALHOU, 'pedido_cancelado')` |
| A-22 | `test_criacao_de_pedido_pago_e_recusada_e_so_resta_a_cobranca_anterior` | `('concluida', '') == (FALHOU, 'pedido_pago')` |
| A-23 | `test_resposta_perdida_perto_do_prazo_e_a_orfa_e_cancelada` | `PagamentoNoProvedor.DoesNotExist` (a órfã não é registrada) |
| A-24 | `test_falha_local_na_conclusao_desfaz_a_chamada_e_a_orfa_ainda_e_cancelada` | `not enough values to unpack` (nenhum cancelamento) |
| A-25 | `test_busca_indisponivel_repete_e_recusa_da_busca_vai_para_o_log` | `('concluida', 'indisponivel') == (FALHOU, 'pedido_cancelado')` |
| A-26 | `test_orfa_aprovada_depois_do_prazo_quita_pela_e08_04` | `('aguardando_pagamento', None) == ('pago', …)` |
| A-28 | `test_pedido_cancelado_nao_mostra_mensagem_de_tentativa` | `'' == 'pedido_cancelado'` (a tentativa ficava `criada`) |
| regra da tela | `test_a_espera_so_aparece_dentro_do_prazo` | "Estamos gerando a sua cobrança" aparece depois do prazo |
| E08-06 A-13 (×2) e A-15 | `test_pedidos_moderacao.py` | `1 == 0` cobranças no simulador; `'' == 'pedido_cancelado'` |

Green: 51 aprovados nos três arquivos.

**Concorrência, com as duas linhas do registro (E08-R06).**

| Critério | Verde funcional sem a proteção | Red da corrida |
|---|---|---|
| A-27 | os A-21 e A-22 acima (recusa no `executar`) verdes, sem proteção no `concluir` | `uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q`: **3 falharam, 14 passaram**. `test_pedido_quitado_durante_a_criacao_cancela_a_cobranca_nova`: `ValueError: not enough values to unpack` (nenhuma chamada de cancelamento agendada) |
| E08-06 A-14 (suspensão e remoção) | idem | `test_moderacao_durante_a_criacao_nao_espera_e_a_cobranca_e_cancelada[suspensao]` e `[remocao]`: o mesmo `not enough values to unpack` |

Só depois entrou a proteção no `_concluir_criacao` (trava `SituacaoDoPedido`, depois a tentativa, depois `agendar_cancelamento`); com ela, o arquivo passou: **17 aprovados**. A thread da moderação (e a da quitação) termina sem esperar a criação parada, conferido pelo teste.

Desvios e interpretações, para o revisor:

- **A-23 e A-24 ("`processar_chamadas()` duas vezes").** A mesma execução também processa o cancelamento recém-agendado. Para ver o estado intermediário pedido pela spec (pagamento ainda `pendente` depois da recusa), o teste usa `processar_chamadas(limite=1)` na segunda e `processar_chamadas()` na terceira.
- **A-25 (i).** Para chegar ao reprocessamento depois da indisponibilidade, o relógio avança 2 minutos (o intervalo da primeira repetição é de 1 minuto).
- **E08-06 A-15** está em dois testes: o estado do A-13 em `test_pedidos_moderacao.py` e a continuação do A-14 (i) em `test_pedidos_concorrencia.py`.
- **Log da busca recusada.** A mensagem é "Busca na recusa da criação recusada pelo provedor: tentativa <id>, recusa <código>".
- **A-26.** `quitado_em` ficou igual ao `aprovado_em` do provedor (T0 + 24h00min30s), como pede a spec.

## Não conformidade de TDD (R06) — E08-03 A-19

Evidência procurada em `C:/Users/wsgon/.claude/projects/C--Users-wsgon-OneDrive-Desktop-AI-Hive-om/eca958a3-5baa-41c1-b7a8-d4c5947c3fdc.jsonl` (registro da sessão, com horário UTC; os números são índices de linha, base 0): os testes A-19 e A-20 foram acrescentados na linha 13446 (19:28:27Z) e o único Red é o da linha 13467 (19:28:47Z), **28 falharam e 20 passaram**, contra o serviço de tentativas ainda inexistente. Não há registro de verde funcional sem trava seguido de Red da corrida.

- **O que aconteceu:** Red só pela ausência do serviço; sem o ciclo verde sem trava → Red da corrida → trava.
- **Causas:** as três confirmadas na seção equivalente da E08-02.
- **Sensibilidade (mutação), não Red.** `pagamento.py`: `SituacaoDoPedido.objects.select_for_update()` vira `SituacaoDoPedido.objects` em `pedir_pagamento`. `uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q --create-db`: **3 falharam, 14 passaram**: `test_dois_cliques_em_pagar_geram_uma_tentativa` (`[None, IntegrityError('duplicate key … chave_idempotencia')]`, asserção `all(r.excecao is None …)`) e as duas variantes de `test_suspensao_e_pagamento_ao_mesmo_tempo`. Arquivo restaurado por `git checkout -- apps/pedidos/pagamento.py` e suíte verde de novo.

## Registro do implementador — correção R08 (2026-10-21)

Especificação: `docs/specs/E08-03/spec.md` e `acceptance.md`, seção "Correção E08-R08" (commit `a41b44f`). Commit da correção: `6118ae4`.

### Critério → teste → resultado do Red (antes de qualquer mudança de produção)

O arranjo R está no apoio `recuperacao_de_dois_pagamentos` (`tests/apoio/pedidos.py`). Comandos, com o arquivo inteiro e sem `-k`:

- `uv run pytest tests/tecnicos/test_pedidos_tentativas.py -q -p no:cacheprovider` → **2 falharam, 28 passaram**.
- `uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q -p no:cacheprovider` → **3 falharam, 17 passaram**.

| Critério | Teste | Resultado contra o código anterior |
|---|---|---|
| A-29 | `test_aviso_de_um_pagamento_nao_espera_a_recuperacao_dos_outros` (concorrência) | **Red da corrida, por asserção:** `a outra thread não terminou enquanto a recuperação estava parada: a transação da recuperação a segura` (`Event.wait(8)` sem sinal). Nenhum `deadlock detected` nem tempo esgotado da infraestrutura: o controle converte a espera em asserção e libera a recuperação no `finally`. |
| A-30 | `test_reconsulta_da_margem_nao_espera_a_recuperacao_e_nao_duplica` (concorrência) | **Red da corrida, por asserção**, a mesma mensagem. |
| A-31 | `test_a_recuperacao_consulta_cada_pagamento_encontrado` (tentativas) | **verde funcional sem a proteção + Red estrutural:** as asserções funcionais, postas primeiro (chamada `falhou` com `prazo_encerrado`, destinos `[("devolucao","duplicidade"),("quita","")]`, tentativa 3 `nao_criada`, nenhuma cobrança com a chave da tentativa 3, uma `ConsultaDoPagamento` `busca` por pagamento), passam contra o código anterior. Falha só a asserção estrutural: `assert [] == ['sim-13', 'sim-14']` (nenhuma chamada `consultar_pagamento` agendada). |
| A-32 | `test_falha_local_depois_de_agendar_desfaz_a_recuperacao_inteira` (tentativas) | **passou já no Red.** O rollback da transação da chamada já existia; o teste protege a propriedade que a correção precisa preservar (agora também para as consultas agendadas). Sem Red próprio, declarado. |
| A-33 | `test_aviso_novo_antes_da_recuperacao_fica_com_uma_consulta_so` (concorrência) | Red por asserção: `assert 0 == 1` na consulta do pagamento 1 (a recuperação anterior sincronizava direto, sem consulta). |
| A-34 | `test_provedor_indisponivel_depois_da_busca_deixa_as_consultas_pendentes` (tentativas) | Red por asserção: `assert 0 == 2` (`len(consultas)`). |

**Interpretação a conferir.** A spec chama de "verde funcional sem a proteção" o A-31 contra o código atual. Como o A-31 também exige as chamadas `consultar_pagamento`, que só existem depois da correção, ele não é verde por inteiro. Pus as asserções funcionais antes das estruturais, e o Red mostra que só a estrutural falha. A parte do ciclo "Red da corrida" é a do A-29 e do A-30. Não observei um Red separado das travas `nowait` do A-29, porque a asserção do término do aviso falha antes dela.

### Green

`apps/pedidos/operacoes.py`, `_criacao_falhou`: no lugar de `sincronizar_pagamento` para cada pagamento achado, agenda `consultar_pagamento` (alvo igual ao `id_externo`, `parametros={"origem": "busca"}`), na ordem `(criado_em, id_externo)`. O cancelamento das órfãs e a marcação da tentativa não mudaram. O `falhou` não trava mais `PagamentoNoProvedor` nem `SituacaoDoPedido`.

Os mesmos dois arquivos, depois do Green: os seis critérios passam; falharam **2** testes antigos (A-23 e A-24 da correção R03), pelo motivo previsto na spec ("o pagamento passa a ser registrado pela consulta agendada").

### Testes antigos ajustados (só o ponto de observação, como a spec permite)

Arquivo `tests/tecnicos/test_pedidos_tentativas.py`:

- `test_resposta_perdida_perto_do_prazo_e_a_orfa_e_cancelada` (A-23). Antes: logo depois da recusa, `PagamentoNoProvedor...situacao == "pendente"`. Depois: o mesmo `assert`, movido para depois de `assert processar_chamadas(limite=1) == 1` (a consulta agendada pelo `falhou`), acrescentado antes dele. Nenhuma outra asserção mudou.
- `test_falha_local_na_conclusao_desfaz_a_chamada_e_a_orfa_ainda_e_cancelada` (A-24). Antes: `assert processar_chamadas() == 1` (o cancelamento) logo depois da recusa. Depois: acrescentado `assert processar_chamadas(limite=1) == 1` antes dele, para a consulta; o `== 1` do cancelamento ficou igual.
- A-25 e A-26 passaram sem ajuste. No A-26, a quitação da órfã aprovada vem agora da consulta agendada, na mesma `processar_chamadas()`.

Nenhuma asserção foi removida, afrouxada nem trocada.

### Invariante nova ("nenhuma transação de chamada sincroniza mais de um pagamento")

Chamadores de `sincronizar_pagamento` conferidos por `grep`:

- `apps/pagamentos/chamadas.py` (`_concluir_consulta`): um pagamento por chamada.
- `apps/pedidos/operacoes.py` (`_concluir_criacao`, `_concluir_cancelamento`): um pagamento por chamada.
- `apps/pagamentos/consulta.py` (`consultar_antes_de_decidir`): uma transação curta por pagamento, fora de transação de chamada.
- `apps/pedidos/operacoes.py` (`_criacao_falhou`): **era o único que violava a invariante**, corrigido.

Nenhum outro caminho viola a invariante, e não ampliei o escopo.

### Verificação

`uv run pytest -q -p no:cacheprovider` (suíte completa, sem filtro): **2166 passed in 259.82s** (eram 2160). `ruff check`, `ruff format --check` (291 arquivos), `mypy` (342 arquivos) e `makemigrations --check`: limpos. A prova R08 do parecer fica substituída pelo A-29, como a spec determina.
