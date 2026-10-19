# E06-04 — Revisão independente — 2026-10-19

**Veredito desta fatia: APROVADO. Veredito global da E06: REPROVADO.**

Base: `main`, commit `2fbf143d082b37a1e8333a0736a310008e10e9ad`. A-1 a A-11 examinados. R03 (melhoria): normalizar em UTC o campo novo da auditoria de prorrogação. O instante registrado é equivalente; autorização, transições e prazo passaram.

O [parecer consolidado em E06-01](../E06-01/review.md) registra fontes, matriz das sete fatias, classificação, referências, passos de reprodução, limites e código completo das provas independentes. Suíte completa: **1772 passed**. Provas adicionais: **7 failed, 8 passed** (as falhas confirmam R01 a R04). Ruff, formatação, mypy e verificação de migrações passaram. Não houve alteração de produção nem de testes versionados pelo revisor.

Os registros do implementador abaixo são preservados como evidência histórica; não substituem o veredito independente acima. As correções e o gate de processo R05 exigem nova avaliação antes do encerramento da E06.

---

## Registro anterior preservado

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

---

## Correção E06-R03 — registro do implementador (2026-10-19)

Status: correção implementada; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia (seção "Correção E06-R03", A-12) e o achado R03 do parecer consolidado em `E06-01/review.md`.

**Arquivos:** `apps/rodadas/fechamento.py` (`prorrogar_fechamento`), `tests/tecnicos/test_rodadas_fechamento_prorrogacao.py`. Sem andaime e sem migração.

### Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_rodadas_fechamento_prorrogacao.py tests/tecnicos/test_rodadas_fechamento_concorrencia.py -q`: **2 failed, 29 passed**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-12 (`-03:00`) | `test_a_auditoria_grava_os_instantes_em_utc[brasilia]` | falhou por asserção sobre `alteracoes["novo"]` (gravava o texto no fuso recebido) |
| A-12 (`+05:30`) | `test_a_auditoria_grava_os_instantes_em_utc[mais-05-30]` | falhou: `'2026-11-04T10:00:00+05:30' == '2026-11-04T04:30:00+00:00'` |
| A-1 a A-11 | testes existentes dos dois arquivos | passaram (29) |

O teste também confere `anterior`, o valor devolvido pelo serviço (o mesmo instante) e o prazo vigente.

### Green

Os dois arquivos mais `test_rodadas_fechamento_inicio.py`: **47 passed**. `ruff check`, `ruff format --check` e `mypy .` sem erros. A auditoria grava `anterior` e `novo` por `astimezone(UTC).isoformat()`; o valor devolvido e a linha de prazo não mudaram.

### Limites

Postgres real. A auditoria `rodada.iniciar_fechamento` não mudou (já vinha em UTC). Nenhuma mutação aplicada nesta correção.
