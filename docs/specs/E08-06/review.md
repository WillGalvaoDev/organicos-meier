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
