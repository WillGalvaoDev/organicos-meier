# E06-04 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§7, 13), infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E01-03, E03-02, E06-01 e E06-03.

## Arquivos

- `apps/rodadas/fechamento.py`: `prorrogar_fechamento`, os três códigos novos de `TransicaoRecusada` (`fora_de_fechamento`, `prazo_encerrado`, `prazo_nao_posterior`) e a mensagem do último com o prazo vigente em Brasília.
- Testes: `tests/tecnicos/test_rodadas_fechamento_prorrogacao.py` (A-1 a A-9) e, em `test_rodadas_fechamento_concorrencia.py`, A-10 e A-11. Nenhuma migração.

## Ciclo TDD

**Andaime (exceção técnica):** os códigos e mensagens de `TransicaoRecusada` e `prorrogar_fechamento` devolvendo o próprio `novo_termino`, sem gravar nem recusar. `agora` e `prazo_encerrado` ficaram importados no módulo (com `noqa`) para os testes de concorrência poderem trocar o relógio; o `noqa` saiu no Green.

**Red (inclui a concorrência, antes do código).** `uv run pytest tests/tecnicos/test_rodadas_fechamento_prorrogacao.py tests/tecnicos/test_rodadas_fechamento_concorrencia.py -k "prorroga or confirmacao or depois_das_travas" -q`: **17 failed, 2 passed em 32,6 s**, por asserção (`assert <T> == <T + 24 h>` no prazo, `DID NOT RAISE TransicaoRecusada/PermissionDenied/InstanteSemFuso`, e nos dois testes de concorrência a segunda operação não esperou a trava). Passaram já no Red o A-4 em `T − 1 ms` (o andaime devolve o novo prazo) e o A-9 (nada prorroga sozinho). Uma primeira execução tinha falhado por `AttributeError` (o módulo não importava `agora`); corrigi no andaime para o Red dos critérios de concorrência ser por asserção.

**Green.** Arquivos de prorrogação e concorrência: **25 passed**. Suíte completa: **1721 passed** (eram 1702). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- Ordem: administrador, instante com fuso (`InstanteSemFuso`, antes de qualquer trava), travas do fornecedor e da rodada ativa, depois `fora_de_fechamento`, `prazo_encerrado` (com `agora()` lido depois das travas), `prazo_nao_posterior`; então a linha `prorrogacao` e a auditoria.

## Decisões técnicas

- Nos testes de concorrência o relógio é o `monkeypatch` de `agora` em `apps.rodadas.fechamento` (relógio compartilhado entre as threads), como a spec da E06-03 permite.
- A-4 foi parametrizado em três cenários independentes (`T − 1 ms`, `T`, `T + 1 ms`), porque aceitar a primeira prorrogação mudaria o prazo vigente dos casos seguintes.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_prorrogacao_estende_o_prazo_e_audita` (`acceptance`, cenário 28) |
| A-2 | `test_o_bloqueio_usa_o_prazo_novo` |
| A-3 | `test_prorrogacoes_sucessivas` |
| A-4 | `test_fronteira_da_prorrogacao` |
| A-5 | `test_o_novo_prazo_tem_de_ser_posterior` |
| A-6 | `test_so_um_fechamento_em_andamento_pode_ser_prorrogado` |
| A-7 | `test_so_o_administrador_prorroga` |
| A-8 | `test_instante_sem_fuso_e_erro_de_programacao` |
| A-9 | `test_a_queda_do_minimo_nao_prorroga` (`acceptance`, cenário 5) |
| A-10 | `test_duas_prorrogacoes_valem_na_ordem_de_confirmacao` |
| A-11 | `test_o_prazo_da_prorrogacao_e_lido_depois_das_travas` |

## Limites da verificação

Postgres real, sem navegador. O formulário e o botão são da E06-07; não há aviso de prorrogação (a §12 não o define). Nenhuma mutação foi aplicada nesta fatia.
