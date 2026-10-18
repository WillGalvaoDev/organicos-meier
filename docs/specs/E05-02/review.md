# E05-02 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia e a E05-01.

## Arquivos

- `apps/interesses/fila.py` (novo): `alocar_pendentes` e `_alocar_produto`.
- `apps/interesses/receptores.py` (novo) e `apps/interesses/apps.py`: receptores de `rodada_aberta` e `estoque_alterado`, conectados no `ready()` com `dispatch_uid`.
- `apps/interesses/servicos.py`: `_atender_a_fila` antes de cada acréscimo e depois de cada redução (`adicionar_interesse`, `reduzir_interesse`, `definir_interesse`).
- Testes: `tests/tecnicos/test_interesses_fila.py` (A-1 a A-14) e, em `test_interesses_concorrencia.py`, A-15 e A-16. O apoio `tests/apoio/interesses.py` reúne `cenario`, `parcelas`, `auditorias`, `reservada` e `pendente` (refatoração do que a E05-01 tinha dentro do arquivo de testes; os 45 testes da E05-01 seguem verdes).

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** `alocar_pendentes` e `_alocar_produto` devolvendo zero, sem receptores.

**Red.** `uv run pytest tests/tecnicos/test_interesses_fila.py -q`: **10 failed, 6 passed**, por asserção (parcelas continuavam `pendente`, `alocar_pendentes` devolvia 0 no lugar de 10, nenhuma auditoria, e `DID NOT RAISE TransactionManagementError`). Passaram já no Red os que dependem de ausência: A-6, A-8 (três etapas), A-11 e A-13.

**Green.** `test_interesses_fila.py` + `test_interesses_servicos.py`: **61 passed**. Com A-15 e A-16: `test_interesses_concorrencia.py` **8 passed**. Suíte completa: **1529 passed** (eram 1511). `ruff check`, `ruff format --check`, `mypy .` sem erros; nenhuma migração.

**Concorrência (A-15, A-16).** Escritos depois do Green, pelo mesmo motivo da E05-01 (dependem do serviço real para segurar as travas). O A-15 roda as duas ordens: (a) `alocar_pendentes` segura e a adição espera; (b) a trava de fornecedor e rodada é tomada por fora, a adição de E é tentada e recusada dentro da transação externa, e `alocar_pendentes` espera. No (b) a trava precisa ser tomada explicitamente, porque a recusa de E desfaz o savepoint e soltaria as travas adquiridas dentro dele. Sem Red observado para esses dois.

## Decisões técnicas

- `definir_interesse`: no acréscimo, a fila é atendida **antes** de recalcular o reservado do comprador, e só então a diferença é aplicada (se a própria fila do comprador cobrir o pedido, nada é acrescentado).
- Auditoria: `alteracoes["parcelas"]` guarda `[id, "quantidade"]` com a quantidade como texto de três casas (JSON não aceita `Decimal`).
- Sem estoque na rodada (`DoesNotExist`) em `_alocar_produto` não é tratado: quem chama já garantiu que o produto tem estoque, como a spec manda.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_pendentes_sao_atendidas_pela_ordem_original` (`acceptance`, cenário 75) |
| A-2 | `test_novo_comprador_so_recebe_o_que_sobra_da_fila` (`acceptance`, cenário 76) |
| A-3 | `test_liberacao_vai_para_a_fila_na_mesma_transacao` (`acceptance`, cenário 101) |
| A-4 | `test_reserva_nova_nao_passa_na_frente_da_fila` |
| A-5 | `test_sem_limite_a_fila_e_atendida_antes` |
| A-6 | `test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele` (`acceptance`, cenário 102) |
| A-7 | `test_incluir_o_produto_na_rodada_atende_a_fila` |
| A-8 | `test_fora_das_etapas_que_reservam_nada_acontece` (fechamento encerrado, pagamento e cancelada, esta como "sem rodada ativa") |
| A-9 a A-11 | `test_em_fechamento_a_fila_e_atendida`, `test_livre_nao_multiplo_do_incremento`, `test_parcela_em_pedido_nao_e_atendida` |
| A-12 | `test_execucao_repetida_nao_altera_nada` (`acceptance`, cenário 78) |
| A-13 | `test_reduzir_o_limite_nao_atende_a_fila` |
| A-14 | `test_alocar_exige_transacao` |
| A-15 | `test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem` |
| A-16 | `test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado` |

## Limites da verificação

Pendentes são criadas por fábrica, porque o fluxo que as produz é da E11. O receptor de `rodada_aberta` não tem teste de efeito próprio (a rodada nasce sem estoques); o teste de abertura existente garante que ele não quebra a abertura. Postgres e serviços reais, sem navegador.
