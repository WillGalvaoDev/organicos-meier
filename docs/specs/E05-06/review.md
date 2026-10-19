# E05-06 — Revisão independente

## Veredito final da E05 — 2026-10-19

**E05 APROVADA** sobre `9ec351a3a364c0089af2c2e35745ece11ab84926` (main). Correção R05: `4559b57`, PR #67. Este veredito substitui os estados anteriores, preservados abaixo como histórico.

R01 a R03 permanecem resolvidos conforme o contrato aprovado; o tratamento excepcional de R04 permanece aceito, sem alegação de TDD retroativo. **R05 está encerrado. Nenhum achado aberto permanece na E05.**

Validação independente nesta revisão:

- `uv run pytest -q`: **1666 passed em 142,80 s**, incluindo E05-05 A-25 a A-27 e regressões de todas as fatias.
- `uv run ruff check .`: passou; `uv run ruff format --check .`: **217 arquivos** conformes.
- `uv run mypy .`: **251 arquivos**, sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- `uv run pytest -c pyproject.toml $env:TEMP/test_review_e05_9ec351a.py -q --tb=short`: **26 passed em 3,04 s**. As 20 provas da revisão de 8728b4b foram reexecutadas sem alteração; as três falhas de R05 agora passam. Outros seis casos verificam aviso único, nome do produto escapado, preservação de reservas/auditoria e ausência de formulário proibido, no carrinho e no catálogo.

**Restauração documental conferida:** o script original do revisor foi localizado na transcrição local da sessão (`rollout-2026-10-15T09-08-49-01a13f77-0e96-7123-a3a7-f9aaf8088eee.jsonl`). Suas constantes foram extraídas sem executar o script e comparadas aos sete pareceres restaurados; o bloco de provas também foi comparado ao arquivo original em TEMP. Resultado: **E05-01 a E05-07 EXATOS**, com normalização apenas de quebras de linha na leitura. Portanto, os trechos sobre 8728b4b estão como foram deixados pelo revisor. O relato antigo de restauração incompleta ao final da E05-05 descreve o incidente naquela data; foi superado pela restauração conferida nesta revisão.

**Fatia E05-06 APROVADA (mantido).** Suíte completa verde, sem regressão identificada nesta revisão. Evidências e matriz final no [parecer consolidado](../E05-01/review.md).

Somente os sete `review.md` foram alterados pelo revisor. Os documentos desta revisão são commitados antes da devolução, conforme AGENTS.md §10. Próximo gate: a entrega seguinte passa por especificação aprovada e implementação TDD próprias.

---

## Nova revisão independente — correções em 8728b4b

Commit: `8728b4b3f459d97bf9c1ce1c74407bbaa2a8655e` (`main`, PR #66), revisto em 2026-10-18. Este parecer substitui o estado de aprovação anterior, cujo histórico permanece abaixo.

**Parecer global: E05 REPROVADA**, por R05 (importante) na apresentação de conflitos da E05-05. R01 e R03 estão corrigidos; o contrato de R02 foi decidido e seu comportamento de serviço está conforme; R04 recebeu o tratamento excepcional aprovado, sem alegação de Red retroativo.

Verificações independentes:

- `uv run pytest -q`: **1657 passed em 133,38 s** (todas as fatias e regressões).
- `uv run ruff check .`: passou; `uv run ruff format --check .`: **217 arquivos** conformes.
- `uv run mypy .`: **251 arquivos**, sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- `uv run pytest -c pyproject.toml $env:TEMP/test_review_e05_8728b4b.py -q --tb=short`: **17 passed, 3 failed em 2,98 s**. As 16 provas anteriores adaptadas ao contrato aprovado passaram; o controle adicional pelo catálogo passou; as três falhas adicionais são R05. Código e reprodução no [parecer consolidado](../E05-01/review.md).

**Fatia APROVADA.** A-1 a A-9 e os novos cenários de concorrência de preço com operações de interesse e moderação passaram. R03 encerrado; a notificação permanece na transação do preço.

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

A-1 a A-9 passaram: avisos individuais somente no site, valores exatos, auditoria, chave de evento, exclusão de `em_pedido` e rollback. R03 reproduziu deadlock com edição de preço simultânea a reserva e a suspensão, devido à combinação entre trava do produto e FK da notificação para conta travada. Requer correção transacional e testes determinísticos; ver [parecer consolidado](../E05-01/review.md).

---

## Registro original do implementador (preservado como evidência)

# E05-06 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E03-03, E04-01, E04-02 e E05-01.

## Arquivos

- `apps/interesses/avisos.py` (novo): `avisar_preco_alterado`, conectado em `apps/interesses/apps.py` com `dispatch_uid`.
- `apps/catalogo/servicos.py` (`editar_produto`) e `apps/catalogo/sinais.py`: o argumento `alteracao` no sinal `preco_alterado`.
- Teste: `tests/tecnicos/test_interesses_preco.py` (A-1 a A-9). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** `avisar_preco_alterado` com a assinatura final e corpo vazio, ainda sem conexão ao sinal.

**Red.** `uv run pytest tests/tecnicos/test_interesses_preco.py -q`: **7 failed, 2 passed**, por asserção (`assert 0 == 1` nos avisos, `assert [] == ['preco_alterado:...']`, `DID NOT RAISE RuntimeError`, e a ausência de `alteracao` no sinal). Passaram já no Red o A-5 (parcela `em_pedido`) e o A-6 (edição só de descrição e produto sem parcelas), porque dependem de ausência. Antes do Green troquei, nos testes A-8 e A-9, um desempacotamento e um acesso por chave por asserções explícitas, para a falha do Red ser por asserção.

**Green.** Mesmo arquivo: **9 passed**. Suíte completa: **1603 passed** (eram 1594). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Decisões técnicas

- O receptor usa uma consulta agregada (`values("comprador_id").annotate(Sum(...))`, ordenada por conta) mais uma leitura em lote das contas; emite com `emitir_evento` uma vez por comprador, porque o conteúdo é diferente para cada um.
- Os subtotais do aviso usam `calcular_subtotal(preco, reservado total)`; o corpo usa o filtro `reais` e `formatar_quantidade`, exatamente como a spec.
- `editar_produto` guarda o retorno de `registrar_auditoria("produto.alterar_preco")` e o passa no sinal. Os receptores existentes da E03-03 já aceitam argumentos extras (`**kw`).
- A-3 foi exercitado com o aviso real emitido por `editar_produto` seguido de duas chamadas diretas ao receptor com a mesma entrada de auditoria, dentro de uma transação.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_so_quem_tem_reserva_e_avisado` |
| A-2 | `test_cada_alteracao_gera_o_seu_aviso` |
| A-3 | `test_mesmo_fato_nao_duplica` |
| A-4 | `test_preco_alterado_no_fechamento_atinge_o_carrinho` (`acceptance`, cenário 72) |
| A-5 | `test_parcela_em_pedido_nao_e_avisada` |
| A-6 | `test_sem_parcelas_e_edicao_so_de_descricao_nao_avisam` |
| A-7 | `test_falha_na_emissao_desfaz_a_alteracao` |
| A-8 | `test_titulo_cortado_em_150_caracteres` |
| A-9 | `test_o_sinal_leva_a_entrada_de_auditoria` |

## Limites da verificação

Cliente HTTP do Django e Postgres reais, sem navegador. O aviso é só no site (matriz da E04-01). O retorno ao interesse quando o valor elegível cai abaixo do mínimo é da E06.


---

## Correções do implementador após o parecer de `32b05a2` (2026-10-18)

Status: correções concluídas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Nenhum teste existente foi alterado; só acréscimos. Suíte completa: **1657 passed**.

### E05-R03 — travas implícitas dos avisos

Nenhuma mudança no código desta fatia, como a spec da correção determina: o receptor e a emissão continuam na mesma transação da alteração de preço, sem `on_commit` e sem trava de conta na edição. A correção está nas travas de conta (`select_for_update(no_key=True)`) e os critérios são o A-21 da E05-01 e o A-15 e o A-16 da E05-07, com Red real (`deadlock detected`) e Green registrados em [E05-01/review.md](../E05-01/review.md). Os testes A-1 a A-9 desta fatia seguem verdes sem alteração.
