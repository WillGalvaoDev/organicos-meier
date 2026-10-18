# E05-01 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E03-02, E03-03, E03-04, E03-05 e E03-06.

## Arquivos

- `apps/rodadas/condicoes.py`: `travar_rodada_para_interesses`, `interesses_editaveis`, `InteressesBloqueados`.
- `apps/interesses/consultas.py`: `travar_parcelas`.
- `apps/interesses/servicos.py` (novo): `adicionar_interesse`, `reduzir_interesse`, `definir_interesse`, `interesse_do_comprador`, `ResumoDoInteresse`, `ProdutoForaDaRodada`, `EstoqueInsuficiente`, `ReducaoAcimaDoReservado`.
- Testes: `tests/tecnicos/test_interesses_servicos.py` (A-1 a A-12) e `tests/tecnicos/test_interesses_concorrencia.py` (A-13 a A-16). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** assinaturas e exceções, com os serviços devolvendo `ResumoDoInteresse(0, 0)`, `travar_parcelas` devolvendo `[]` e a primitiva sem trava nem conferência.

**Red.** `uv run pytest tests/tecnicos/test_interesses_servicos.py -q`: **45 failed**, todos por asserção (`DID NOT RAISE` de `QuantidadeInvalida`, `PermissionDenied`, `InteressesBloqueados`, `EstoqueInsuficiente`, `TransactionManagementError`, e `reservado` 0 no lugar do esperado). Uma primeira rodada falhou por erro do próprio teste (segundo administrador violando `conta_administrador_unico`); corrigi o teste para usar o administrador que a `RodadaFactory` já cria, sem alterar nenhuma garantia.

**Green.** Mesmo arquivo: **45 passed**. Suíte completa: **1511 passed** (eram 1461). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

**Concorrência (A-13 a A-16).** Estes testes foram escritos **depois** do Green, porque dependem do serviço real para segurar as travas (a operação que segura roda dentro de uma `transaction.atomic()` externa e espera a outra aparecer em `pg_stat_activity`). Não há Red observado. Em troca, verifiquei por mutação que eles detectam falta de trava: trocar o `select_for_update` da conta por `get` faz o A-15 falhar. Tirar as travas do fornecedor e da rodada **não** quebra nenhum teste, porque o produto, o estoque e as parcelas travados na sequência já serializam sozinhos (a trava do fornecedor é a primeira defesa pela spec; as demais, a segunda). Isso fica como limite da verificação.

## Decisões técnicas

- `EstoqueInsuficiente(disponivel, unidade)` e `ReducaoAcimaDoReservado(reservado)` montam a própria mensagem (`mensagem`); a unidade usa o rótulo de `Unidade` ("unidade", "L").
- `definir_interesse` aceita zero por `_validar_total`; os demais valores passam por `validar_quantidade` já com o produto relido sob trava.
- `ProdutoForaDaRodada` cobre também o produto de outro fornecedor, porque a trava e o estoque são buscados pela rodada do fornecedor do produto.
- Reduzir uma parcela `ativa` com pendência a zero reservado a deixa `pendente` (e `removida` se a pendência também for zero), como a spec manda.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_adicionar_cria_parcela_e_audita` |
| A-2 | `test_acrescimo_posterior_vai_para_o_fim_da_fila` (`acceptance`, cenário 8) |
| A-3 | `test_reducao_atravessa_parcelas_da_mais_recente_para_a_mais_antiga` |
| A-4 | `test_excedente_e_recusado_por_inteiro`, `test_estoque_zero_esta_esgotado` |
| A-5 | `test_quantidades_e_incrementos` (`acceptance`, cenários 63, 85, 109), `test_entradas_invalidas_nao_gravam` |
| A-6 | `test_reducao_acima_do_reservado_e_quantidade_invalida` |
| A-7 | `test_definir_interesse_e_idempotente` |
| A-8 | `test_so_comprador_ativo_mexe_em_interesse` |
| A-9 | `test_etapas_que_aceitam_interesse`, `test_sem_rodada_ativa_e_bloqueado` |
| A-10 | `test_produto_fora_da_rodada` |
| A-11 | `test_produto_indisponivel_continua_aceitando` |
| A-12 | `test_travar_rodada_exige_transacao` |
| A-13 | `test_ultima_unidade_disputada_so_uma_vence` (cenário 3) |
| A-14 | `test_adicao_e_alteracao_de_incremento_se_serializam` (as duas ordens; cenário 108) |
| A-15 | `test_suspensao_confirmada_antes_barra_a_adicao` |
| A-16 | `test_dez_adicoes_de_dois_com_limite_dez` |

O cenário 63/85/109 usa `float` e `"1000000000.000"` em `test_entradas_invalidas_nao_gravam`; o subtotal de R$ 18,00 (1,5 kg a R$ 12,00) está em `test_quantidades_e_incrementos`.

## Limites da verificação

Cliente e banco reais (Postgres); sem navegador. A recusa do prazo de fechamento vencido é da E06. As telas e as rotas são da E05-05.
