# E07-05 — Revalidação independente — 2026-10-20

**Parecer da fatia: APROVADO no escopo local, sobre `636a94cacde2764e297967189c5904b58f72dde6`, branch `e07-implementacao`. E07 global: REPROVADO por R06 (IMPORTANTE).**

Matriz revalidada: **A-1 a A-18**. R01, R02 e R05 encerrados: corrida, primeiro horário e validação de corpos assinados corrigidos. A aprovação local não aprova a entrega integrada.

O [parecer consolidado](../E07-01/review.md) registra a matriz das seis fatias, fontes, análise das correções, encerramento de R01–R05, achado R06 com prova reproduzível e R07 (melhoria de processo: Red de R03 usou `-k`, contrariando a prevenção vigente, sem evidência de critério omitido).

Verificação independente: suíte completa **1937 passed in 175.77s**; dez provas anteriores passam; prova nova de R06 falha (**1 failed, 10 passed in 5.85s**). `ruff check`, `ruff format --check` (257 arquivos), `mypy` (300 arquivos) e verificação de migrações passaram. Comandos, logs, adaptações justificadas das provas e código completo estão no parecer consolidado. As tabelas Red/Green foram conferidas; a revisão atual não é prova de execução histórica do Red.

R06: após timeout, uma sessão do simulador permanece ativa, a guarda informa zero pendências e a thread grava uma aprovação depois da liberação da trava. É necessário estender as garantias de E01-05 ao novo alias e revalidar antes da aprovação global. Somente pareceres foram alterados nesta revisão; conteúdo anterior preservado integralmente abaixo.

---

## Histórico integral preservado

# E07-05 — Revisão independente — 2026-10-20

**Veredito desta fatia: REPROVADO. Veredito global da E07: REPROVADO.**

Base: `d6e4d2095ac8f1128b1a315fd81e5ab579488aa3`, branch `e07-implementacao`. A-1 a A-14 examinados. R01 (bloqueador): aviso aceito durante consulta em andamento pode ficar sem consulta posterior. R02 (importante): primeiro_aviso_em fica nulo quando já existe chamada de tarefa. R05 (importante): campos autenticados maiores que os limites persistidos chegam ao banco e produzem 500.

O [parecer consolidado em E07-01](../E07-01/review.md) contém fontes, matriz das seis fatias, análise dos registros de TDD, classificação e reprodução de R01 a R05, comandos e limitações. Verificação independente: **1902 testes aprovados** na suíte; provas adicionais: **8 falhas e 2 aprovações**. Ruff, formatação, mypy e verificação de migrações passaram. A suíte verde não cobre as lacunas reproduzidas. Nenhum arquivo de produção ou teste versionado foi alterado pelo revisor.

O registro anterior abaixo foi preservado integralmente e não substitui o veredito independente. A entrega integrada requer correção e nova revisão antes do encerramento.

---

## Registro do implementador preservado

# E07-05 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§8.3, 15, cenário 17), infraestrutura v1.7 (4.2, 5), testes técnicos T-6, `spec.md` e `acceptance.md` da fatia, E02-10 (políticas das rotas) e E07-01, E07-03, E07-04.

## Arquivos

- `apps/pagamentos/models.py`: `AvisoRecebido` (`RegistroSoInsercao`, `UNIQUE (provedor, id_evento)`) e `migrations/0003_avisorecebido.py` com a trigger de só inserção.
- `apps/pagamentos/avisos.py`: `receber_aviso` e `TAMANHO_MAXIMO_DO_AVISO`. `apps/pagamentos/views.py`: `avisos` (`@publica`, `@csrf_exempt`, `@require_POST`). `config/urls.py`: `POST /pagamentos/avisos/` (`pagamentos_avisos`).
- `apps/simulador_pagamentos/controle.py`: `entregar_avisos` usa `receber_aviso` como receptor padrão (importado dentro da função); o receptor injetável continua.
- Testes: `test_pagamentos_avisos.py` (A-1 a A-11, A-14) e, em `test_pagamentos_concorrencia.py`, A-12 e A-13.

## Ciclo TDD

**Andaime (exceção técnica):** o modelo com a migração e a trigger, a view e a rota, e `receber_aviso` devolvendo 200 sem fazer nada.

### Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pagamentos_avisos.py tests/tecnicos/test_pagamentos_concorrencia.py tests/tecnicos/test_permissoes_politica_rotas.py -q`: **13 failed, 21 passed**. Uma primeira leitura teve `DoesNotExist` nas preparações; elas foram tornadas assertivas (`esperava 1 registro, há 0`) antes do Green, e o Red é o da segunda leitura, anterior ao código de produção. Falhas por asserção: `assert 0 == 1`, `assert 200 == 401`, `assert 200 == 400`, `assert 0 == 2`, `assert 0 == 5`, `esperava 1 registro, há 0` e, nas concorrências, `a outra conexão não ficou esperando pela trava`.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_aviso_valido_registra_e_agenda_a_consulta` | falhou |
| A-2 | `test_a_consulta_aplica_a_aprovacao_do_provedor` | falhou |
| A-3 | `test_aviso_repetido_nao_repete_efeitos` (`acceptance`) | falhou |
| A-4 | `test_aviso_nao_autentico_e_recusado` | falhou (`assert 200 == 401`) |
| A-5 | `test_corpo_grande_e_metodos_errados` | falhou (`assert 200 == 400`) |
| A-6 | `test_tipo_desconhecido_e_registrado_sem_consulta` | falhou |
| A-7 | `test_avisos_diferentes_antes_da_consulta_geram_uma_chamada` | falhou (`assert 0 == 2`) |
| A-8 | `test_a_ordem_dos_avisos_nao_muda_o_resultado` | falhou |
| A-9 | `test_o_horario_do_aviso_nao_decide_o_da_aprovacao` | falhou |
| A-10 | `test_a_rota_de_avisos_e_publica` e a varredura existente | **passaram no Red**: a rota do andaime já nasce com `@publica`; o teste protege a política contra regressão (a varredura `rotas_sem_politica` segue verde) |
| A-11 | `test_aviso_novo_de_pagamento_ja_consultado_agenda_outra_consulta` | falhou |
| A-12 | `test_mesmo_aviso_cinco_vezes_em_paralelo_reconhece_o_pagamento_uma_vez` (`acceptance`, T-6) | falhou por asserção (espera da outra conexão) |
| A-13 | `test_cinco_avisos_diferentes_do_mesmo_pagamento` | falhou (`assert 0 == 5`) |
| A-14 | `test_o_aviso_recebido_so_aceita_insercao` | falhou (sem registro de partida) |

### Green

Os arquivos de avisos, concorrência e simulador: **54 passed**. Suíte completa: **1892 passed** (eram 1878). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` (com as configurações de teste) sem erros.

## Decisões técnicas (derivadas da spec)

- **Inserção por SQL `INSERT ... ON CONFLICT (provedor, id_evento) DO NOTHING RETURNING id`**, para saber se o aviso é novo sem `IntegrityError` e sem savepoint; é o que a spec descreve. O modelo continua `RegistroSoInsercao`; a trigger só recusa `UPDATE` e `DELETE`.
- **A verificação e o limite de tamanho acontecem antes de qualquer gravação.** O corpo acima de 64 KiB responde 400 sem chamar o provedor; o `AvisoInvalido` responde 401 e registra só "Aviso de pagamento recusado".
- **O nome do provedor** gravado no aviso é o do `obter_provedor()` usado na verificação.
- **O log do aviso aceito** leva o `id_evento`, "novo" ou "repetido" e o `id_externo`; nunca o corpo nem os cabeçalhos.
- **Rota:** `@publica` é o decorador mais externo; o atributo `csrf_exempt` é herdado pelo `functools.wraps`, e o middleware de CSRF não exige token.

## Limites da verificação

Postgres real, cliente HTTP do Django, sem rede e sem o worker como processo. O formato e a assinatura reais do Mercado Pago (L-11) são da fase 2a; o efeito do pagamento no pedido (E08) e o alerta de avisos recusados (E15) são de outras etapas. Nenhuma mutação aplicada nesta fatia.


---

## Correções E07-R01, R02 e R05 — registro do implementador (2026-10-20)

Status: correções implementadas; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `docs/specs/E07-01/review.md`, `spec.md` e `acceptance.md` desta fatia (seção "Correção E07-R01, R02 e R05", A-15 a A-18) e as provas do revisor.

### Arquivos

Nenhum código de produção próprio desta fatia mudou: `receber_aviso` continua chamando `agendar_chamada` com os mesmos parâmetros, e as regras corrigidas estão na E07-04 (R01 e R02) e no tipo `AvisoDoProvedor` da E07-01 (R05). Testes: `test_pagamentos_avisos.py` (A-16, A-17, A-18 e o controle `test_aviso_apos_consulta_concluida_atualiza`) e `test_pagamentos_concorrencia.py` (A-15).

### Red e Green

As tabelas do Red estão nos registros da E07-04 (R01 e R02: A-15 e A-16 desta fatia, **6 falhas** no total) e da E07-01 (R05: A-17, **9 falhas** de 11 casos; A-18 passou no Red como controle). Resumo:

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-15 | `test_aviso_durante_a_consulta_espera_e_gera_outra_consulta` | falhou: `assert ['concluida'] == ['concluida', 'concluida']` |
| A-16 | `..._preservado_com_consulta_ja_agendada[tarefa-antes]` | falhou: `assert {} == {...}` |
| A-16 | `..._preservado_com_consulta_ja_agendada[sem-tarefa]` | **passou no Red** (controle: o aviso que cria a própria consulta) |
| A-17 | `test_aviso_assinado_fora_dos_limites_nao_causa_500` | 9 de 11 falharam (`assert 500 == 401`, `assert 200 == 401`); os 2 casos numéricos já passavam |
| A-18 | `test_avisos_no_limite_exato_sao_aceitos` | **passou no Red** (controle dos limites exatos, com `é` × 64) |

Green: suíte completa **1937 passed**; lint, formatação, tipos e migrações sem erros.

### Decisões técnicas

- No A-15, a mudança do aviso (`aprovar(P)` e `entregar_avisos()`) acontece na thread 2 depois de a tarefa obter a resposta pendente; o `entregar_avisos()` espera a execução terminar (trava) e devolve `[200]`.
- O A-17 usa `Client(raise_request_exception=False)` para que o 500 do código antigo apareça como asserção. Nenhum erro de banco é capturado para virar 401: a recusa vem do tipo `AvisoDoProvedor`.

### Limites da verificação

Postgres real, cliente HTTP do Django, threads reais; sem navegador, sem o worker como processo e sem rede. Nenhuma mutação aplicada nestas correções.
