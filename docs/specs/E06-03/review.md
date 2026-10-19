# E06-03 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§5, 7, 15), infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E01-03, E05-01, E05-02, E05-05, E05-07 e E06-01.

## Arquivos

- `apps/rodadas/condicoes.py`: `aceita_interesses(rodada, instante)`, o código `prazo_encerrado` em `travar_rodada_para_interesses` e o uso da regra em `interesses_editaveis`.
- Pontos de `apps/` que decidiam só pela etapa e agora usam `aceita_interesses` (busca por `Etapa.FECHAMENTO` e por `ETAPAS_QUE_ACEITAM`/`interesses_editaveis`):
  1. `apps/rodadas/condicoes.py`: `travar_rodada_para_interesses` (a fila, as operações do comprador e a remoção de pendentes que usa a primitiva passam por aqui);
  2. `apps/rodadas/condicoes.py`: `interesses_editaveis`;
  3. `apps/interesses/servicos.py`: a atribuição da fila em `remover_interesses_do_comprador`;
  4. `apps/interesses/apresentacao.py`: o cálculo de `editavel` do catálogo (a constante `ETAPAS_QUE_ACEITAM` foi removida);
  5. `apps/interesses/consultas.py`: o `editavel` do grupo do carrinho.
  Não há outro uso de `Etapa.FECHAMENTO` em `apps/` que decida se interesses são aceitos (os demais são `iniciar_fechamento` e `prazo_do_fechamento`, da E06-01).
- `tests/apoio/ciclos.py`: `dar_prazo_de_teste`; `tests/apoio/interesses.py`: `cenario()` chama o auxiliar para `fechamento` e `fechamento_encerrado`.
- Testes: `tests/tecnicos/test_rodadas_fechamento_prazo.py` (A-1 a A-7) e, em `test_rodadas_fechamento_concorrencia.py`, o A-9.

## Ciclo TDD

**Andaime (exceção técnica):** `aceita_interesses` reproduzindo a decisão atual por etapa, sem prazo, e `agora`/`prazo_encerrado` importados em `condicoes.py` para o teste do A-9 poder trocar o relógio. Nenhum ponto de `apps/` usava a função ainda.

**Red (inclui a concorrência, antes do código).** `test_rodadas_fechamento_prazo.py`: **6 failed, 1 passed**, por asserção (`DID NOT RAISE InteressesBloqueados`, `assert Decimal('3.000') == 0`, `DID NOT RAISE RuntimeError`, formulário de quantidade ainda na página). Passou já no Red o A-7 (etapas), por refletir o andaime. O A-9 em `test_rodadas_fechamento_concorrencia.py` falhou por `AssertionError: None` (a adição de C não foi recusada); uma primeira execução tinha falhado por `AttributeError` (o módulo ainda não importava `agora`), e a corrigi no andaime para o Red ser por asserção.

**Green.**
- `aceita_interesses`: `interesse` sempre; `fechamento` até o prazo (limite exclusivo, `prazo_encerrado` de E01-03), lendo `prazo_do_fechamento`; demais etapas nunca; `fechamento` sem prazo levanta `RuntimeError`. O import de `prazo_do_fechamento` é local, para evitar o ciclo `condicoes` ↔ `fechamento`.
- `travar_rodada_para_interesses` lê `agora()` **depois** das travas e recusa com `prazo_encerrado` (mesma mensagem).
- Os dois arquivos de prazo e de concorrência: **13 passed**. Suíte completa: **1702 passed** (eram 1694). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Ajuste autorizado nos testes existentes

`dar_prazo_de_teste` e a chamada em `cenario()` seguem a spec. **Nenhum outro teste precisou do auxiliar**: depois da mudança de `aceita_interesses`, a suíte inteira passou sem nenhum `RuntimeError` por rodada em `fechamento` sem prazo (todos os testes existentes que usam `fechamento` passam por `cenario()` ou por `iniciar_fechamento`/`simular_inicio_do_fechamento`, ou só exercitam condições congeladas). Nenhuma asserção existente foi alterada.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_a_fronteira_do_prazo_e_exclusiva` (`acceptance`, §15) |
| A-2 | `test_depois_do_prazo_o_comprador_nao_altera_nada` |
| A-3 | `test_depois_do_prazo_a_fila_nao_e_atendida` |
| A-4 | `test_depois_do_prazo_remover_pendente_e_suspender_continuam` |
| A-5 | `test_depois_do_prazo_as_telas_nao_oferecem_quantidade` |
| A-6 | `test_fechamento_sem_prazo_e_erro_de_invariante` |
| A-7 | `test_aceita_interesses_por_etapa` |
| A-8 | este `review.md` (lista dos pontos trocados acima; sem testes ajustados além de `cenario()`) |
| A-9 | `test_o_prazo_e_lido_depois_de_obter_as_travas` |

**A-9, meio usado para o relógio:** `monkeypatch` de `agora` em `apps.rodadas.condicoes`, com um relógio compartilhado entre as threads (`time-machine` fora da jogada, como a spec permite). A operação que segura as travas troca `servicos.travar_rodada_para_interesses` por um envoltório que chama a original (lendo o relógio a `T − 50 ms`), espera a outra aparecer em `pg_stat_activity` e só então move o relógio para depois do prazo.

## Limites da verificação

Postgres real, sem navegador. A mudança de etapa no fim do prazo e a remoção dos excedentes são da E06-05; o texto do prazo nas telas, da E06-07. Nenhuma mutação foi aplicada nesta fatia.
