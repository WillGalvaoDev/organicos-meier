# E08-06 — Terceira revisão independente — 2026-10-22

**APROVADO sobre `fe8dffa`.** Matriz: A-1 a A-15. **A E08 integrada está APROVADA**, com R06/R08 encerrados, conforme [parecer consolidado](../E08-01/review.md).

R06 encerrado pelo tratamento expressamente estendido ao A-11 reescrito em a41b44f. Registro verdadeiro preservado, causa/prevenção documentadas. Mutação independente em memória retirando pedido_cancelado: 1 falha esperada, 19 aprovações. Sem mutação, 20 aprovações, incluindo as duas ordens do A-11. A sensibilidade não é apresentada como Red histórico nem dispensa de TDD para outras entregas.

Verificação independente: suíte completa sem filtro, **2166 passed in 220.50s**; Ruff, formatação, mypy e migrações sem pendências. Oito provas independentes passaram. Mutações de controle A-11 e R08 falharam pelos motivos esperados; arquivo concorrente inteiro sem mutações: **20 passed in 9.50s**. Comandos, reprodução, evidências de TDD e limites estão no parecer consolidado.

Os textos anteriores do revisor e do implementador foram conferidos e preservados integralmente abaixo. Nenhuma alteração em produção ou teste versionado. Aprovação restrita à entrega e ao commit revisado, sem afirmar integração em main. Melhorias M-3/M-4 seguem a política de revisão final.

---

## Histórico integralmente preservado

# E08-06 — Nova revisão independente — 2026-10-21

**REPROVADO no gate de processo sobre `584b323`.** Matriz: A-1 a A-15. A E08 integrada continua **REPROVADA**, por R06 e R08, conforme o parecer consolidado em [E08-01/review.md](../E08-01/review.md).

R02 funcional encerrado: fila e criação em andamento cobertas para suspensão/remoção, sem esperar chamada externa nem reabrir pedido na reativação. R06 permanece no A-11 reescrito: teste inicialmente verde após proteção, conforme declaração do implementador. O tratamento autorizado abrangia os critérios antigos e exigiu explicitamente ciclo real para este A-11; sua mutação não substitui Red histórico. Necessária decisão expressa do responsável para tratar esse novo desvio, preservando o registro verdadeiro.

Verificação independente global: `uv run pytest -q` sem filtro, **2160 passed in 246.21s**; Ruff lint/formatação, mypy e migrações sem pendências. Provas anteriores R01–R03: seis casos aprovados. Nova prova R08 falha por deadlock; controle de recuperação após rollback passa antes da asserção final de ausência de impasse. Comandos, fontes, limites, análise de TDD e reprodução completa no parecer consolidado.

O texto anterior do revisor e os registros do implementador foram conferidos e preservados integralmente abaixo. Nenhum código de produção ou teste versionado alterado pelo revisor.

---

## Histórico integralmente preservado

# E08-06 — Revisão independente do agente 3 — 2026-10-21

**REPROVADO sobre `2714a6a2acaf88cc69e02345facf2a2403a66374`, branch `e08-implementacao`. E08 global: REPROVADO.**

Matriz examinada: **A-1 a A-12**, a partir de spec.md/acceptance.md e das fontes superiores, antes de avaliar o código. R02 confirmado em suspensão e remoção: uma tentativa somente solicitada cria cobrança depois do cancelamento, sem chamada para cancelá-la. O teste de A-11 adiciona processar_chamadas à transação do clique e não cobre essa janela. O controle com cobrança já criada antes da suspensão passa. R06 também exige comprovar a sequência de TDD da concorrência.

TDD declarado: **12 failed, 13 passed; tabela conferida, com ressalva de concorrência R06.** O revisor confere registro, testes e diffs; não presenciou a execução histórica. Reexecuções atuais não substituem evidência de Red anterior à implementação.

Verificações independentes: suíte completa **1 failed, 2129 passed in 292.98s**, sem exclusões; provas adicionais **5 failed, 2 passed in 17.36s**; lint, formatação (288 arquivos), tipos (338 arquivos) e verificação de migrações passaram. A falha versionada é a de rotas descrita em R05; as cinco falhas adicionais correspondem a R01, R02 (duas variantes), R03 e R04.

O [parecer consolidado](../E08-01/review.md) contém matriz das sete fatias, referências, classificação, resultados, código completo das provas, limites e encaminhamentos R01–R07. R04 requer decisão sobre pedido zero, e R06 requer evidência histórica ou tratamento autorizado; as perguntas foram encaminhadas durante a revisão. R07 está no registro central como M-3.

Somente documentação foi alterada pelo revisor, sem correção silenciosa de produção ou testes. Histórico do implementador preservado integralmente abaixo. Próximo gate: correções/comprovações e nova revisão independente.

---

## Registro anterior integralmente preservado

# E08-06 — Registro do implementador (2026-10-20)

Status: implementada; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia, a moderação (E02-08), a remoção de interesses (E05-07) e as E08-03 e E08-04.

## Arquivos

- `apps/pedidos/cancelamento.py`: `cancelar_pedidos_nao_pagos` e `MOTIVOS_DE_CANCELAMENTO`.
- `apps/pedidos/receptores.py` e `apps/pedidos/apps.py`: os receptores de `conta_suspensa` e `conta_removida`, ligados no `ready()` (o app `interesses` vem antes na lista, então os receptores de interesses rodam primeiro).
- Testes: `tests/tecnicos/test_pedidos_moderacao.py` (A-1 a A-10) e, em `test_pedidos_concorrencia.py`, A-11 e A-12.

Nenhuma mudança de modelo: a transição `aguardando_pagamento → cancelado` e os campos de cancelamento já existiam na `SituacaoDoPedido` (E08-02).

## Andaime (exceção técnica)

Antes do Red: `cancelar_pedidos_nao_pagos` que devolve 0 e `MOTIVOS_DE_CANCELAMENTO`; nenhum receptor ligado.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pedidos_moderacao.py tests/tecnicos/test_pedidos_concorrencia.py -q`: **12 failed, 13 passed**. Passaram os 11 testes de concorrência das fatias anteriores (regressão) e dois deste arquivo (abaixo).

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_suspensao_cancela_o_pedido_nao_pago` | `assert 'aguardando_pagamento' == 'cancelado'` |
| A-2 | `test_a_cobranca_pendente_e_cancelada_no_provedor` | `assert 0 == 1` (nenhuma chamada a processar) |
| A-3 | `test_remocao_da_conta_cancela_com_o_proprio_motivo` | `assert ('aguardando_pagamento', '') == ('cancelado', 'remocao_da_conta')` |
| A-4 | `test_pago_no_provedor_antes_da_suspensao_quita_mesmo_assim` | `assert None == 'suspensao'` (o cancelamento sem efeito nunca existiu) |
| A-5 | `test_pago_no_provedor_depois_da_suspensao_gera_devolucao` | `assert ('quita', '') == ('devolucao', 'pedido_cancelado')` |
| A-6 | `test_reativar_nao_restaura_o_pedido` | `assert 'Cancelado' in '<!doctype html>…'` |
| A-7 | `test_o_suspenso_ve_o_cancelado_e_o_pago` | `assert 'Cancelado' in '<!doctype html>…'` |
| A-8 | `test_motivo_invalido_e_conta_de_fornecedor` e `test_o_servico_exige_transacao` | `DID NOT RAISE ValueError` e `DID NOT RAISE TransactionManagementError` |
| A-9 | `test_falha_de_outro_receptor_desfaz_a_suspensao` | **passou no Red**: sem o receptor de pedidos, a exceção do receptor de teste já desfaz a suspensão; passa a provar também o desfazer do cancelamento depois do Green (os pedidos continuam `aguardando_pagamento` e sem chamada) |
| A-10 | `test_sem_pedidos_ou_com_pedido_cancelado_nada_muda` | **passou no Red**: o andaime não cancela nada; é prova de regressão depois do Green |
| A-11 | `test_suspensao_e_pagamento_ao_mesmo_tempo` (2 ordens) | `assert 'aguardando_pagamento' == 'cancelado'` |
| A-12 | `test_a_suspensao_nao_espera_o_cancelamento_em_andamento` | `assert 'aguardando_pagamento' == 'cancelado'` |

## Green e verificações

- Os dois arquivos: **25 passed**. Conjunto `-k "moderacao or suspensao or contas or pedidos"`: **437 passed**.
- `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- A suíte completa roda ao final da milestone.

## Decisões técnicas e pontos para o especificador

- **A-11, "pagamento antes".** O critério diz que a tentativa "nasce e logo recebe o cancelamento com alvo `:suspensao`". `agendar_cancelamento` (E08-03) só agenda para tentativa `criada`. Para o teste produzir esse cenário, a thread que segura a trava faz `pedir_pagamento` e `processar_chamadas()` dentro da mesma transação (a cobrança nasce antes de a suspensão chegar). Se a tentativa estivesse só `solicitada` quando a suspensão ocorresse, nenhum cancelamento seria agendado: a cobrança seria criada depois, e um pagamento dela iria para devolução (`pedido_cancelado`, E08-04). Peço ao especificador que confirme se isso basta ou se a criação deve recusar o pedido cancelado.
- **Reavaliação sob a trava.** O serviço lê os pedidos candidatos sem trava, trava cada `SituacaoDoPedido` por `pedido_id` e só então confere de novo que ela continua `aguardando_pagamento` e lê o instante do cancelamento (se um pagamento quitou o pedido no meio, o pedido não é cancelado).
- **Motivo no alvo.** O alvo do cancelamento na moderação é `t<tentativa>:<motivo>` (E08-03), diferente do bloqueio por prazo; a moderação não espera uma chamada em andamento (A-12).
- **Auditoria `pedido.cancelar`** aponta para o pedido, com o motivo e o `cancelado_em` em UTC.

## Limites da verificação

Postgres real, cliente HTTP do Django e threads reais; sem navegador, sem o worker como processo e sem rede. Nenhuma mutação aplicada.

---

## Registro do implementador — correções R01 a R06 (2026-10-21)

Status: implementadas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Fontes lidas antes de editar: o parecer em `docs/specs/E08-01/review.md` e as seções de correção de cada `spec.md` e `acceptance.md` (commit `7a1fb49`).

### R02 — a cobrança que estava só enfileirada na suspensão ou na remoção

A coordenação está na E08-03 (`executar` recusa com `pedido_cancelado`; `concluir` agenda o cancelamento com o motivo da moderação). `cancelar_pedidos_nao_pagos` não mudou. Os Red e Green estão no registro da E08-03 (A-13 e A-15 em `test_pedidos_moderacao.py`; A-14 em `test_pedidos_concorrencia.py`):

- A-13 (suspensão e remoção, tentativa só `solicitada`): **Red** em `test_pedidos_moderacao.py` (2 falhas por asserção) e Green depois da recusa no `executar`.
- A-14 (i) e (ii): **Red da corrida** (2 falhas: nenhum cancelamento agendado) antes da proteção no `concluir`; depois, Green.
- A-15: Red e Green como descritos na E08-03.

**A-11 reescrito (sem andaime).** O teste antigo foi substituído pelo texto novo (`test_suspensao_e_pagamento_ao_mesmo_tempo`, duas ordens), sem remover o critério antigo do histórico: o teste e o texto antigos estão em `git show 2714a6a:tests/tecnicos/test_pedidos_concorrencia.py`.

**Desvio de processo que preciso reportar (Red tardio).** O A-11 reescrito **passou na primeira execução**, porque a recusa no `executar` (que cobre a ordem "pagamento antes") já tinha entrado, sob o Red dos A-13 e A-21, antes de eu escrever o teste de corrida. Não houve, portanto, o Red próprio do A-11 reescrito (verde sem a proteção → Red da corrida → proteção). A prova de que o teste detecta a ausência dessa proteção é a mutação abaixo, que **não é Red**.

**Sensibilidade (mutação), não Red.** `operacoes.py`: sai de `_motivo_da_recusa` o ramo `pedido_cancelado`. `uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q`: **1 falhou, 16 passaram**: `test_suspensao_e_pagamento_ao_mesmo_tempo[pagamento_antes]`, `AssertionError: ('criada', '') == ('nao_criada', 'pedido_cancelado')`. Arquivo restaurado por `git checkout -- apps/pedidos/operacoes.py`.

## Não conformidade de TDD (R06) — texto antigo do E08-06 A-11

O A-11 antigo dizia que a tentativa "nasce e logo recebe o cancelamento com alvo `:suspensao`", e o teste antigo executava `pedir_pagamento` e `processar_chamadas()` dentro da transação que segurava a trava, fechando a janela entre a solicitação e a criação. Evidência: `C:/Users/wsgon/.claude/projects/C--Users-wsgon-OneDrive-Desktop-AI-Hive-om/eca958a3-5baa-41c1-b7a8-d4c5947c3fdc.jsonl` (registro da sessão, com horário UTC; os números são índices de linha, base 0), Red da linha 14021 (19:49:57Z), **12 falharam e 13 passaram**, contra um serviço que devolvia zero; sem o ciclo verde sem trava → Red da corrida → trava. O critério foi reescrito (R02) e o texto novo segue o ciclo real descrito acima, com o desvio declarado.

## Não conformidade de TDD (R06) — A-11 reescrito (segunda revisão, 2026-10-21)

Especificação: `docs/specs/E08-06/spec.md`, seção "Correção E08-R06, segunda revisão" (commit `a41b44f`). Este registro soma-se ao anterior, que não foi editado.

1. **O critério e o que aconteceu.** Critério: A-11 reescrito, `test_suspensao_e_pagamento_ao_mesmo_tempo` (duas ordens). Conforme já declarado neste arquivo: "teste escrito depois da proteção, verde na primeira execução; sem Red observado antes do código de produção".
2. **Decisão aplicável.** O responsável pelo projeto decidiu em 2026-10-21 que o mesmo tratamento dos critérios antigos vale para este A-11: o registro, a sensibilidade por mutação e a prova concorrente verde encerram o gate. Não refaço o passado, não retiro código para produzir um Red novo, e a decisão não é dispensa para as próximas etapas.
3. **Sensibilidade (mutação), não Red.** Repetida com o código atual (HEAD `6118ae4`), por `scratchpad/mutacao_a11.py`:
   - Trecho mudado, em `apps/pedidos/operacoes.py`, `_motivo_da_recusa`: o ramo `if situacao == SituacaoDePagamento.CANCELADO: return "pedido_cancelado"` foi retirado.
   - Comando (arquivo inteiro, sem `-k`): `uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q -p no:cacheprovider`.
   - Resultado: **1 falhou, 19 passaram**: `test_suspensao_e_pagamento_ao_mesmo_tempo[pagamento_antes]`, por asserção: `assert ('criada', '') == ('nao_criada', 'pedido_cancelado')`.
   - Restauração: o script regravou os bytes originais do arquivo; `git status` ficou limpo.
   - Mesmo comando, depois da restauração: **20 passed in 13.50s**.
4. **Prova concorrente verde.** `test_suspensao_e_pagamento_ao_mesmo_tempo`, nas duas ordens (`pagamento_antes` e a de suspensão antes), com o arquivo inteiro: `uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q -p no:cacheprovider` → **20 passed** (restaurado) e, na suíte completa depois da correção R08, **2166 passed**.
5. **Causa.** O Green de um critério sequencial (A-13 e A-21) também entregou a proteção de um critério concorrente que ainda não tinha teste. A prevenção da spec (conferir, antes do Green de um critério sequencial, se a proteção cobre uma corrida sem Red; se cobrir, escrever antes o teste da corrida e registrar as duas linhas) passa a valer para as próximas etapas.
