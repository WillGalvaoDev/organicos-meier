# E05-02 — Revisão independente

## Nova revisão independente — correções em 8728b4b

Commit: `8728b4b3f459d97bf9c1ce1c74407bbaa2a8655e` (`main`, PR #66), revisto em 2026-10-18. Este parecer substitui o estado de aprovação anterior, cujo histórico permanece abaixo.

**Parecer global: E05 REPROVADA**, por R05 (importante) na apresentação de conflitos da E05-05. R01 e R03 estão corrigidos; o contrato de R02 foi decidido e seu comportamento de serviço está conforme; R04 recebeu o tratamento excepcional aprovado, sem alegação de Red retroativo.

Verificações independentes:

- `uv run pytest -q`: **1657 passed em 133,38 s** (todas as fatias e regressões).
- `uv run ruff check .`: passou; `uv run ruff format --check .`: **217 arquivos** conformes.
- `uv run mypy .`: **251 arquivos**, sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- `uv run pytest -c pyproject.toml $env:TEMP/test_review_e05_8728b4b.py -q --tb=short`: **17 passed, 3 failed em 2,98 s**. As 16 provas anteriores adaptadas ao contrato aprovado passaram; o controle adicional pelo catálogo passou; as três falhas adicionais são R05. Código e reprodução no [parecer consolidado](../E05-01/review.md).

**Fatia APROVADA.** A-1 a A-17 reexecutados. R01 encerrado. R04 tratado conforme a opção aprovada; permanece documentado o limite de sensibilidade de A-16, com reforço proposto pelo implementador. Ver o consolidado.

---

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

### Parecer da fatia: REPROVADO

A-1 a A-16 passaram na suíte completa. R01 bloqueia a alteração ilimitado → finito; R02 afeta a composição entre redução e alocação de pendências próprias; R04 registra falta de Red anterior para A-15/A-16. Achados, requisitos, reproduções e próximo gate no [parecer consolidado](../E05-01/review.md). Não identificado problema de sobrevendagem nos cenários de fila executados.

---

## Registro original do implementador (preservado como evidência)

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


---

## Correções do implementador após o parecer de `32b05a2` (2026-10-18)

Status: correções concluídas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Nenhum teste existente foi alterado ou afrouxado; só acréscimos. Suíte completa: **1657 passed**.

### E05-R01 — estoque ilimitado que passa a ter limite (critério A-17)

**Red.** Com as provas do revisor incluídas literalmente (`test_sem_limite_para_finito` e `test_controle_transicoes_estoque`), mais o espião de `_alocar_produto`, o caso (iii) e os pares de controle, em `tests/tecnicos/test_interesses_fila.py`: **2 failed, 26 passed**, os dois com `TypeError: '>' not supported between instances of 'decimal.Decimal' and 'NoneType'` (`test_sem_limite_para_finito[0]` e `[3]`). As outras provas passaram já no Red porque descrevem o comportamento que a correção preserva (as outras transições, o caso (iii) e os pares).

**Green.** `atender_fila_no_aumento_de_estoque` (`apps/interesses/receptores.py`) classifica pelo par (`anterior`, `novo`): `anterior` nulo (ilimitado) retorna sem alocar, pois nada foi liberado; finito → `None` e finito → maior chamam `_alocar_produto`; a comparação numérica só ocorre com os dois lados finitos. A validação de reservas continua em `alterar_estoque`. Arquivo: **28 passed**.

### Não conformidade de TDD (E05-R04): critérios A-15 e A-16

**O que aconteceu:** testes escritos depois do código de produção; **sem Red observado**. Causas e tratamento: ver o registro consolidado em [E05-01/review.md](../E05-01/review.md), que confirmo para estes critérios. Não houve exceção válida do AGENTS.md.

### Sensibilidade (mutação), não Red — E05-02

Comando: `uv run pytest -q -p no:cacheprovider --tb=line <testes>`; mutação aplicada, teste rodado, mutação desfeita e teste rodado de novo (árvore limpa).

| Critério | Mutação | Resultado mutado | Desfeita |
|---|---|---|---|
| A-15 e A-16 | retirar a trava de fornecedor e rodada e a de parcelas (`consultas._parcelas`) no caminho da fila e do serviço concorrente | A-15: 1 failed em 16,8 s, `AssertionError: [AssertionError('a outra conexão não ficou esperando pela trava'), None]`. **A-16: 1 passed (não detectada)** | 2 passed |
| A-16 | retirar **todas** as travas depois da conta (fornecedor, rodada, produto, estoque e parcelas) | **1 passed: a mutação não é detectada** | 1 passed |

**Limite do teste de A-16.** As duas operações disparam juntas e não há ponto de retenção; o resultado final correto sai mesmo sem travas na intercalação que a máquina produz. **Reforço proposto:** uma variante determinística em que a redução de D segura as travas até a adição de E aparecer esperando (o mesmo arranjo do A-15), de modo que a ausência de trava produza um estado final errado ou uma falha de sincronização.
