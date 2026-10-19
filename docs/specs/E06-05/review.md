# E06-05 — Revisão independente — 2026-10-19

**Veredito desta fatia: REPROVADO. Veredito global da E06: REPROVADO.**

Base: `main`, commit `2fbf143d082b37a1e8333a0736a310008e10e9ad`. A-1 a A-16 examinados. R05 (importante): o registro informa que A-8, A-12 e A-13 só tiveram falha demonstrada após o código. Isso não satisfaz o Red anterior obrigatório. Encerramento, FIFO, rollback, concorrência e idempotência passaram na suíte. Preservar a declaração histórica e encaminhar o tratamento da quebra de processo ao responsável pelo contrato.

O [parecer consolidado em E06-01](../E06-01/review.md) registra fontes, matriz das sete fatias, classificação, referências, passos de reprodução, limites e código completo das provas independentes. Suíte completa: **1772 passed**. Provas adicionais: **7 failed, 8 passed** (as falhas confirmam R01 a R04). Ruff, formatação, mypy e verificação de migrações passaram. Não houve alteração de produção nem de testes versionados pelo revisor.

Os registros do implementador abaixo são preservados como evidência histórica; não substituem o veredito independente acima. As correções e o gate de processo R05 exigem nova avaliação antes do encerramento da E06.

---

## Registro anterior preservado

# E06-05 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§5, 6.1, 6.3, 7, 12, 15), infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E04-01 a E04-03, E05-01, E05-04, E06-01 e E06-03.

## Arquivos

- `apps/rodadas/fechamento.py`: `encerrar_fechamento`, `ResultadoDoEncerramento`, `encerrar_fechamentos_vencidos` e os auxiliares `_divisao_dos_excedentes` e `_por_comprador_e_produto`.
- `apps/rodadas/avisos.py`: `ExcedenteRemovido` e `avisar_excedentes_removidos`.
- `apps/rodadas/tarefas.py` (novo): a tarefa periódica `encerrar_fechamentos_vencidos`.
- `tests/apoio/interesses.py`: `sem_minimo(rodada)`.
- Testes: `tests/tecnicos/test_rodadas_fechamento_encerramento.py` (A-1 a A-13, mais um caso extra de pendência alheia) e, em `test_rodadas_fechamento_concorrencia.py`, A-14 a A-16. Nenhuma migração.

## Ciclo TDD

**Andaime (exceção técnica):** `encerrar_fechamento` devolvendo `None`, `encerrar_fechamentos_vencidos` devolvendo 0, `avisar_excedentes_removidos` vazio e `tarefas.py` só com a constante do nome.

**Red.** Duas leituras, para não esconder nada:
1. Contra o andaime, com um filtro `-k` que (por acidente nos nomes) deixou de fora três testes: **11 failed, 3 passed** entre os selecionados, por asserção (`assert None is not None`, `assert 'ativa' == SituacaoParcela.REMOVIDA`, `assert 0 == 1`, e `A-11`: nenhuma tarefa com esse nome), incluindo os três de concorrência (A-14 a A-16), que falharam por asserção antes do código.
2. Depois do Green, para conferir os três que o filtro tinha deixado de fora (A-8, A-12 e A-13), recriei temporariamente o andaime trocando `encerrar_fechamento` por um que devolve `None` (cópia de segurança restaurada em seguida, árvore conferida): `uv run pytest tests/tecnicos/test_rodadas_fechamento_encerramento.py -q`: **10 failed, 4 passed**, entre os 10 os três esquecidos. **Esta segunda leitura não é um Red histórico**: foi feita depois do código.
Passaram já no Red os testes que dependem de ausência ou do estado já existente (A-7, A-9, A-11 na segunda leitura e o de pendência alheia).

**Green.** Encerramento e concorrência: **25 passed**. Suíte completa: **1738 passed** (eram 1721). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- `encerrar_fechamento` trava o fornecedor e a rodada, relê etapa e prazo (`agora()` depois das travas), grava `fechamento_encerrado`, remove os excedentes pela divisão da E05-04 (as últimas adições perdem primeiro; o que sai não vira pendência), audita com autor `SISTEMA` e emite um aviso por par (comprador, produto). Qualquer falha desfaz tudo.
- `encerrar_fechamentos_vencidos` procura sem trava, em ordem de fornecedor, e isola a falha de cada rodada no log (id e tipo da exceção).

## Decisões técnicas

- **A verificação do mínimo (E06-06)** ainda não existe: o passo 6 da spec fica para a próxima fatia, que o acrescenta na mesma transação. Os testes desta fatia usam fornecedor sem mínimo, como a spec manda, para a verificação nunca devolver a rodada a interesse.
- **Mínimo zero:** o banco recusa mínimo zero, então `sem_minimo` retira a restrição `fornecedor_minimo_positivo` dentro da transação do teste (o rollback a devolve). Isso só vale para testes não transacionais: nos de concorrência (A-14 a A-16), que confirmam de verdade, a restrição não é mexida (DDL sobreviveria ao teste), e o mínimo é **R$ 1,00** (o estado do A-1 tem R$ 120,00 elegíveis, então a verificação nunca devolveria a rodada). Registro como diferença em relação ao texto "mínimo R$ 0,00" da spec.
- **Relógio nos testes de concorrência:** `monkeypatch` de `agora` em `apps.rodadas.fechamento`, fixo em `T`.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_as_ultimas_adicoes_perdem_o_excedente` (`acceptance`, cenário 7) |
| A-2 | `test_sai_primeiro_a_parcela_mais_recente` |
| A-3 | `test_abaixo_de_uma_caixa_sai_tudo` |
| A-4 | `test_total_exato_nao_remove_nem_avisa` |
| A-5 | `test_multiplo_fracionario` |
| A-6 | `test_parcela_com_pendencia_vira_pendente` |
| A-7 | `test_produto_sem_multiplo_fica_intacto` |
| A-8 | `test_o_encerramento_acontece_uma_unica_vez_e_so_no_prazo` |
| A-9 | `test_a_tarefa_nao_mexe_no_que_nao_venceu` (`acceptance`, cenário 4) |
| A-10 | `test_uma_rodada_com_falha_nao_impede_as_outras` |
| A-11 | `test_a_tarefa_esta_registrada_como_periodica` |
| A-12 | `test_falha_no_aviso_desfaz_o_encerramento` |
| A-13 | `test_a_prorrogacao_adia_o_encerramento` |
| A-14 | `test_dois_encerramentos_simultaneos_so_um_age` |
| A-15 | `test_encerramento_e_suspensao_sem_deadlock` |
| A-16 | `test_encerramento_espera_a_edicao_de_preco` |

## Limites da verificação

Postgres real, sem navegador; o worker do Procrastinate não foi executado como processo (a tarefa é conferida no registro e a rotina é chamada direto, como na E04-03). Nenhuma mutação foi aplicada nesta fatia.

---

## Não conformidade de TDD — tratamento da E06-R05 (implementador, 2026-10-19)

Tratamento aprovado pelo responsável pelo projeto em 2026-10-19 (spec desta fatia, "Correção E06-R05"). O registro do implementador acima fica sem edição.

**Critérios afetados:** A-8, A-12 e A-13.

**O que aconteceu:** teste escrito antes do código, mas excluído do Red por um filtro `-k`; sem Red observado antes do código de produção. A leitura feita depois do Green, com o andaime recriado, não é Red histórico e não é apresentada como tal.

**Tratamento aplicado:** uma prova de sensibilidade por critério, abaixo. Isto é **sensibilidade (mutação), não Red**: ela mostra que o teste detecta a retirada da proteção, não que o teste falhou antes do código.

Método: cópia de `apps/rodadas/fechamento.py`, mutação de um trecho, `uv run pytest tests/tecnicos/test_rodadas_fechamento_encerramento.py -q` (arquivo inteiro, sem `-k`), restauração da cópia. Depois das quatro mutações, `git status` limpo. Script em arquivo temporário da sessão, fora do repositório.

| Critério | Mutação (só a proteção do critério) | Teste que falhou | Falha por asserção |
|---|---|---|---|
| A-8 (releitura sob trava) | `if travada is None or travada.etapa != Etapa.FECHAMENTO: return None` vira `if travada is None: return None` | `test_o_encerramento_acontece_uma_unica_vez_e_so_no_prazo` | `assert ResultadoDoEncerramento(...) is None` na terceira chamada (reencerrou) |
| A-8 (prazo vencido) | removida a linha `if not prazo_encerrado(agora(), prazo): return None` | o mesmo teste | `assert ResultadoDoEncerramento(...) is None` na chamada em `T − 1 ms` (encerrou antes do prazo) |
| A-12 (aviso na transação) | `avisar_excedentes_removidos(...)` envolvido em `try/except Exception: pass` | `test_falha_no_aviso_desfaz_o_encerramento` | `Failed: DID NOT RAISE RuntimeError` |
| A-13 (maior prazo do ciclo) | em `prazo_do_fechamento`, `Max("termina_em")` passa a filtrar `origem=INICIO` | `test_a_prorrogacao_adia_o_encerramento` | `assert 1 == 0` em `encerrar_fechamentos_vencidos()` (encerrou apesar da prorrogação) |

Cada mutação deixou os outros 13 testes do arquivo verdes (14 no arquivo, 1 falha por mutação). Em cada caso a falha é por asserção, e não por tempo esgotado ou erro de infraestrutura. Nenhuma mutação deixou o teste passar, então não há limite de teste a registrar nem reforço a propor. As mutações foram desfeitas; o código de produção desta fatia não mudou.

A prevenção da R05 (Red sem `-k`, tabela de cobertura do Red antes do Green, parada diante de Red tardio) vale para as correções R01 a R04 e está aplicada nos registros abaixo.
