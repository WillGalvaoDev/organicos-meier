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
