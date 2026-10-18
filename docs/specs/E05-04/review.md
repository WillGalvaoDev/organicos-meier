# E05-04 — Revisão independente

## Nova revisão independente — correções em 8728b4b

Commit: `8728b4b3f459d97bf9c1ce1c74407bbaa2a8655e` (`main`, PR #66), revisto em 2026-10-18. Este parecer substitui o estado de aprovação anterior, cujo histórico permanece abaixo.

**Parecer global: E05 REPROVADA**, por R05 (importante) na apresentação de conflitos da E05-05. R01 e R03 estão corrigidos; o contrato de R02 foi decidido e seu comportamento de serviço está conforme; R04 recebeu o tratamento excepcional aprovado, sem alegação de Red retroativo.

Verificações independentes:

- `uv run pytest -q`: **1657 passed em 133,38 s** (todas as fatias e regressões).
- `uv run ruff check .`: passou; `uv run ruff format --check .`: **217 arquivos** conformes.
- `uv run mypy .`: **251 arquivos**, sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- `uv run pytest -c pyproject.toml $env:TEMP/test_review_e05_8728b4b.py -q --tb=short`: **17 passed, 3 failed em 2,98 s**. As 16 provas anteriores adaptadas ao contrato aprovado passaram; o controle adicional pelo catálogo passou; as três falhas adicionais são R05. Código e reprodução no [parecer consolidado](../E05-01/review.md).

**Fatia APROVADA (mantido).** A-1 a A-15 passaram na suíte completa. Prova independente de arredondamento, separação de pendentes e participação própria também passou.

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

### Parecer da fatia: APROVADO

A-1 a A-15 passaram, incluindo tela administrativa, elegibilidade por produto, FIFO nas caixas, privacidade, número constante de consultas e fronteira percentual. Prova adicional independente confirmou R$ 1,26 para dois compradores com 0,25 kg a R$ 2,50 e exclusão de pendentes do valor. Registro funcional Red/Green contém comandos e resultados; nenhum achado específico aberto nesta fatia. Esta aprovação não aprova a E05 inteira, que está REPROVADA pelos achados do [parecer consolidado](../E05-01/review.md).

---

## Registro original do implementador (preservado como evidência)

# E05-04 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E03-03, E03-05 e E05-01.

## Arquivos

- `apps/interesses/progresso.py` (novo): `progresso_da_rodada`, `ProgressoDaRodada`, `ProgressoDoProduto`, `ParticipacaoDoComprador`.
- `apps/rodadas/views.py` e `templates/rodadas/estoque.html`: bloco "Progresso da rodada" na página de estoque do administrador.
- Testes: `tests/tecnicos/test_interesses_progresso.py` (A-1 a A-11, A-13 a A-15) e `tests/tecnicos/test_rodadas_estoque.py` (A-12). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** os `dataclass`es e `progresso_da_rodada` devolvendo zeros e lista vazia.

**Red.** `uv run pytest tests/tecnicos/test_interesses_progresso.py -q`: **16 failed, 1 passed**, por asserção (`assert 0 == 1` no número de produtos, `valor_elegivel` 0 no lugar de 80,00/120,00, `(0, False) == (100, True)`). O que passou já no Red depende de ausência (consultas: 0 contra 0). Na primeira rodada, falhas por `ValueError` do desempacotamento do meu helper e `CheckViolation` ao gravar mínimo zero foram corrigidas **no teste** (helper agora afirma o tamanho da lista; ver abaixo o mínimo zero), sem afrouxar nenhuma garantia. A-12: `test_administrador_ve_o_progresso_agregado_sem_identidades` falhou por `assert "Progresso elegível..." in html`.

**Green.** Progresso: **17 passed**. `test_rodadas_estoque.py`: **87 passed**. Suíte completa: **1565 passed** (eram 1547). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Decisões técnicas

- **Mínimo zero.** O banco recusa mínimo zero (`fornecedor_minimo_positivo`), então o caso "mínimo R$ 0,00" do A-14 é exercitado atribuindo `0` em memória ao `fornecedor.minimo` da rodada, sem gravar. O ramo existe na consulta como defesa, como a spec determina.
- **Consultas fixas.** Leituras: fornecedor (via `rodada.fornecedor`), estoques com produto (`select_related`) e as parcelas `ativa` e `pendente` de todos os produtos, numa só consulta (`values_list`). O teste A-10 compara 2 compradores em 1 produto com 30 em 8 produtos e exige o mesmo número, no máximo 4.
- **Divisão pelas caixas** em memória, parcelas em ordem de `sequencia`: uma parcela pode ficar dividida entre a última caixa e o excedente.
- **Percentual:** piso do valor sobre o mínimo; 100 só quando atingido (99 no máximo caso contrário); mínimo zero vale 100.
- **A-12:** o produto de comparação da spec (18 unidades, múltiplo 12, R$ 120,00 de elegível) está na página junto com um segundo produto sem múltiplo (exigido para mostrar "—"), então a linha de resumo do teste é "R$ 126,00 de R$ 200,00" e "Faltam R$ 74,00."; as células da linha do produto com caixa são exatamente as da spec.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_dezoito_unidades_com_multiplo_doze` (`acceptance`, cenário 6) |
| A-2 | `test_caixa_formada_pela_ordem_de_adicao` (`acceptance`, cenário 7) |
| A-3 | `test_acrescimo_posterior_fica_com_o_excedente` |
| A-4 | `test_pendentes_nao_entram_no_minimo` (`acceptance`, cenário 104) |
| A-5 | `test_arredondamento_por_comprador` (`acceptance`, cenário 89) |
| A-6 | `test_multiplo_fracionario_e_total_zero` |
| A-7 | `test_produtos_nao_se_misturam_para_completar_caixa` |
| A-8 | `test_atingir_o_minimo_nao_muda_a_etapa_nem_grava` (`acceptance`, cenário 4) |
| A-9 | `test_so_parcela_ativa_conta` |
| A-10 | `test_numero_de_consultas_nao_cresce` |
| A-11 | `test_resultado_nao_expoe_outros_compradores` |
| A-12 | `test_administrador_ve_o_progresso_agregado_sem_identidades` (`test_rodadas_estoque.py`) |
| A-13 | `test_alteracao_de_preco_muda_o_progresso_na_proxima_leitura` |
| A-14 | `test_percentual_nos_limites_do_minimo`, `test_minimo_zero_ja_esta_atingido` |
| A-15 | `test_comprador_sem_parcela_tem_participacao_zerada` |

## Limites da verificação

Cliente HTTP do Django, sem navegador. A tela do comprador é da E05-05; a verificação do mínimo para iniciar o fechamento é da E06.
