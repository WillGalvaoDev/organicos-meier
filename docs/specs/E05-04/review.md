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
