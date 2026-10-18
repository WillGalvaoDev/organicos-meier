# E05-03 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E05-01 e E05-02.

## Arquivos

- `apps/interesses/servicos.py`: `remover_pendente` e `RemocaoAcimaDoPendente`.
- Testes: `tests/tecnicos/test_interesses_remover_pendente.py` (A-1 a A-8, 16 casos) e `test_interesses_concorrencia.py` (A-9, duas ordens). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** a exceção e `remover_pendente` devolvendo `ResumoDoInteresse(0, 0)`.

**Red.** `uv run pytest tests/tecnicos/test_interesses_remover_pendente.py -q`: **16 failed**, por asserção (`DID NOT RAISE QuantidadeInvalida/RemocaoAcimaDoPendente/PermissionDenied`, pendência continuava igual, parcela não virava `removida`). Entre o Red e o Green mudei só a forma de um teste (separar os dois ramos do `pytest.raises` para satisfazer o `mypy`), sem alterar asserção.

**Green.** Mesmo arquivo: **16 passed**. Com A-9: `test_interesses_concorrencia.py` **10 passed**. Suíte completa: **1547 passed** (eram 1529). `ruff check`, `ruff format --check` e `mypy .` sem erros.

**Concorrência (A-9).** Escrito depois do Green, como nas fatias anteriores (a operação que segura as travas roda numa transação externa e a outra espera em `pg_stat_activity`). Cobre as duas ordens: remoção primeiro (parcela `removida`, total reservado 0) e atendimento primeiro (parcela com 6 reservados e a remoção recusada com pendente 0). Sem Red observado.

## Decisões técnicas

- O serviço trava conta, fornecedor, produto e parcelas, sem rodada nem estoque, e não exige etapa. A trava do fornecedor é a mesma que `alocar_pendentes` toma primeiro, e é isso que os serializa.
- A quantidade é validada depois das travas, com o incremento relido do produto.
- Só parcelas `ativa` ou `pendente` do comprador entram no total removível; `em_pedido` fica de fora (A-6).

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_remocao_parcial_e_total_da_pendencia` (`acceptance`, cenário 97) |
| A-2 | `test_remocao_comeca_pela_parcela_mais_recente` |
| A-3 | `test_parcela_so_pendente_vira_removida` |
| A-4 | `test_remocao_invalida_nao_grava` (`acceptance`, cenário 98) |
| A-5 | `test_remocao_vale_em_qualquer_etapa` (pagamento, fechamento encerrado, aguardando fornecedor e cancelada, esta como "sem rodada ativa") |
| A-6 | `test_parcela_em_pedido_nao_entra_na_remocao` (`acceptance`, cenário 99) |
| A-7 | `test_so_comprador_ativo_remove_pendente` |
| A-8 | `test_remover_pendente_nao_libera_nem_reserva_estoque` |
| A-9 | `test_remocao_e_atendimento_da_fila_se_serializam` (cenário 100) |

## Limites da verificação

Parcelas pendentes criadas por fábrica (o fluxo que as produz é da E11). A rota e a tela são da E05-05. Postgres real, sem navegador.
