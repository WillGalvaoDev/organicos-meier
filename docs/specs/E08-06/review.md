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
