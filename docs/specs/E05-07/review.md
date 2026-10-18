# E05-07 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` (inclusive a D-1, decidida em 2026-10-18) e `acceptance.md` da fatia, E02-08, E05-01 e E05-02.

## Arquivos

- `apps/interesses/servicos.py`: `remover_interesses_do_comprador(conta, *, motivo)`.
- `apps/interesses/receptores.py` e `apps/interesses/apps.py`: receptores de `conta_suspensa` e `conta_removida`, conectados no `ready()` com `dispatch_uid`.
- Testes: `tests/tecnicos/test_interesses_suspensao.py` (A-1 a A-7, A-10 a A-13) e, em `test_interesses_concorrencia.py`, A-8, A-9 e A-14 (parametrizados nas duas ordens). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** a função devolvendo zero e os dois receptores sem conexão aos sinais.

**Red.** `uv run pytest tests/tecnicos/test_interesses_suspensao.py -q`: **8 failed, 2 passed**, por asserção (`assert 'ativa' == SituacaoParcela.REMOVIDA`, `DID NOT RAISE RuntimeError` porque os receptores não estavam conectados, `DID NOT RAISE TransactionManagementError`). Passaram já no Red o A-5 (parcela `em_pedido`) e o A-12 (conta suspensa e conta de fornecedor), porque dependem de ausência.

**Green.** Mesmo arquivo: **10 passed**. Com A-8, A-9 e A-14: `test_interesses_concorrencia.py` **16 passed**. Suíte completa: **1619 passed** (eram 1603). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

**Concorrência (A-8, A-9, A-14).** Escritos depois do Green, como nas fatias anteriores (a operação que segura as travas roda numa transação externa e a outra espera em `pg_stat_activity`). Sem Red observado. Cobrem as duas ordens em cada critério: adição antes da suspensão ou da remoção (a parcela nova é removida), moderação antes da adição (a adição recebe `PermissionDenied`), e atendimento da fila antes ou depois da suspensão (A sem parcela `ativa` nem `pendente` e total reservado 0, sem deadlock).

## Decisões técnicas

- **Ordem de travas.** Conta (já travada por `suspender`/`remover`), fornecedores por id; em cada um, a rodada ativa (se houver), os produtos afetados por id, o estoque do produto na rodada e as parcelas por `travar_parcelas`. As parcelas a remover são relidas **depois** das travas, porque o atendimento da fila (E05-02) pode ter mudado uma pendente em ativa antes da suspensão.
- **Fila só onde a rodada aceita reservas** (`interesse` ou `fechamento`) e o produto tem estoque nela; nas outras etapas a reserva só é liberada.
- **Auditoria:** uma entrada por chamada, autor `SISTEMA`, objeto a conta, `{"conta", "parcelas": [[id, reservado anterior, pendente anterior], ...]}` com as quantidades como texto. Sem parcelas, nada é auditado.
- **Conta de fornecedor** na remoção: o receptor devolve sem fazer nada; a função, se chamada com uma conta que não é comprador, devolve 0 antes de travar qualquer coisa.
- **Substituição de um receptor nos testes A-6 e A-13:** o `monkeypatch` troca `remover_interesses_do_comprador` no módulo `apps.interesses.receptores`, onde o receptor o chama.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1, A-2 | `test_suspensao_esvazia_e_a_reversao_nao_restaura` (`acceptance`, cenário 19) |
| A-3 | `test_reserva_liberada_vai_para_a_fila_na_mesma_transacao` |
| A-4 | `test_rodada_que_nao_aceita_reservas_so_libera` |
| A-5 | `test_parcela_em_pedido_nao_muda` |
| A-6 | `test_falha_do_receptor_desfaz_a_suspensao` |
| A-7 | `test_exige_transacao_e_motivo_valido` |
| A-8, A-14 | `test_adicao_e_suspensao_ou_remocao_se_serializam` |
| A-9 | `test_atendimento_da_fila_e_suspensao_se_serializam` |
| A-10 | `test_remocao_da_conta_trata_os_interesses_como_a_suspensao` |
| A-11 | `test_remocao_preserva_em_pedido_e_nao_apaga_parcelas` (`acceptance`, cenário 20) |
| A-12 | `test_remover_conta_suspensa_ou_de_fornecedor_nao_mexe_em_parcelas` |
| A-13 | `test_falha_do_receptor_desfaz_a_remocao` |

## Limites da verificação

Postgres real, sem navegador. O cancelamento dos pedidos não pagos do suspenso e do removido é da E08 (a spec registra a pergunta para a E08). A D-1 foi aplicada como decidida (opção a), sem alteração.
