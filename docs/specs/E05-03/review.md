# E05-03 — Revisão independente

## Revisão independente — 2026-10-18

Commit auditado: `32b05a24fb38aa7bcaef2d67c5917fdef59bc2c5` (`main`, PR #65). Parecer global da E05: **REPROVADO**.

Fontes: especificação funcional v1.6 (§§2, 4.4, 5, 5.1, 5.2 e 6), infraestrutura v1.7 (§§4.10–4.12), AGENTS.md e os sete pares `spec.md`/`acceptance.md` da E05, incluindo a decisão D-1 da E05-07. Código e testes foram confrontados com esses contratos. A revisão não altera regras, código de produção ou testes versionados.

Validação independente no PostgreSQL local:

- `uv run pytest -q`: **1619 passed em 161,01 s**.
- `uv run ruff check .`: passou.
- `uv run ruff format --check .`: **217 arquivos** conformes.
- `uv run mypy .`: **251 arquivos**, sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais do revisor: **8 failed, 8 passed em 4,71 s**, conforme reprodução integral em [E05-01/review.md](../E05-01/review.md). As falhas são deliberadamente asserções do contrato contra o commit auditado; não são falhas da suíte versionada.

Os registros Red/Green do implementador são preservados abaixo. Eles documentam os testes funcionais e os comandos; o revisor não afirma ter presenciado as execuções históricas. A ausência confessada de Red nos testes de concorrência é tratada em R04. Nenhum teste foi afrouxado nesta revisão. As duas mudanças nos testes da E03-08 estão autorizadas pela E05-05; a suíte de regressão inteira passou.

### Parecer da fatia: REPROVADO no gate TDD

A-1 a A-9 passaram. A remoção preserva reservas e FIFO e exclui `em_pedido`; não foi encontrado defeito funcional específico nesses cenários. R04 impede atestar o processo exigido para A-9. A reexecução verde não comprova Red anterior. Ver [parecer consolidado](../E05-01/review.md).

---

## Registro original do implementador (preservado como evidência)

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


---

## Correções do implementador após o parecer de `32b05a2` (2026-10-18)

Status: correções concluídas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Nenhum teste existente foi alterado; só acréscimos. Suíte completa: **1657 passed**.

### E05-R02 — `esperado` em `remover_pendente`

O argumento opcional `esperado` foi acrescentado e testado no critério A-20 da E05-01 (`tests/tecnicos/test_interesses_servicos.py::test_remover_pendente_com_esperado`): Red com `DID NOT RAISE InteresseDesatualizado`, Green com a conferência depois das travas e antes de remover. A regra da E05-03 não mudou; o teste `test_interesses_remover_pendente.py` segue verde sem alteração. Em `remover_pendente`, o corpo que tira as pendências virou a função interna `_tirar_pendencias`, compartilhada com `definir_interesse(..., "0")` (refatoração coberta pelos testes existentes).

### E05-R03

`_travar_conta` usa `select_for_update(no_key=True)`; o critério A-21 (caso `remover_pendente`) está em `test_interesses_concorrencia.py::test_preco_e_operacao_do_comprador_sem_deadlock[remover_pendente]`, com Red real (`deadlock detected`) e Green. Ver o registro consolidado em [E05-01/review.md](../E05-01/review.md).

### Não conformidade de TDD (E05-R04): critério A-9

**O que aconteceu:** teste escrito depois do código de produção; **sem Red observado**. Causas e tratamento: ver [E05-01/review.md](../E05-01/review.md), que confirmo para este critério.

### Sensibilidade (mutação), não Red — E05-03

Comando: `uv run pytest -q -p no:cacheprovider --tb=line tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam`.

| Critério | Mutação | Resultado mutado | Desfeita |
|---|---|---|---|
| A-9 | retirar a trava do fornecedor e a das parcelas: `travar_rodada_para_interesses`, `consultas._parcelas` e, em `remover_pendente`, `Fornecedor.objects.select_for_update()` e `Produto.objects.select_for_update()` | 2 failed, por asserção de estado: `AssertionError: assert 'ativa' == 'removida'` (ordem remoção primeiro) e `assert False` (ordem fila primeiro) | 2 passed |
