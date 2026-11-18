# E16-08 — Registro do implementador

Agente 2.

**Situação: PARCIAL, BLOQUEADA POR DEPENDÊNCIA.** A spec diz que, sem os pré-requisitos operacionais (fase 0), o implementador registra o que falta e não implanta. Foi o que fiz. Não há decisão comercial a escalar; há dependências externas e a decisão do responsável sobre as melhorias (regra 10), prevista na própria spec.

## O que falta (pré-requisitos da fase 0, fornecidos pelo responsável)

- Conta no **Fly.io** (app `organicos-meier-homolog` em `gru`).
- Projeto no **Neon** em `aws-sa-east-1` (branch da homologação e branch dedicado a testes).
- Conta no **Cloudflare** com dois buckets do R2 (arquivos e backups, credenciais separadas), a regra de 35 dias no de backups e a chave pública do `age` (a privada fica com o responsável).
- Conta na **AWS** com o SES em `sa-east-1`, o domínio e os endereços verificados (sandbox).
- Projetos no **Sentry** e no **Better Stack**, com o e-mail do responsável nos avisos.
- Cliente **OAuth do Google** com o endereço de retorno em `*.fly.dev`.

## Critérios automáticos (A-1 a A-4)

`tests/ambiente/test_artefatos_de_implantacao.py`.

- **Red observado:** `uv run pytest -q tests/ambiente/test_artefatos_de_implantacao.py`: A-1 e A-2 falharam com `FileNotFoundError` (`docs/operacao/homologacao.md` e `docs/relatorio-fase1.md` não existiam); A-3 e A-4 ficaram `xfail` (ver abaixo).
- **A-1 passa:** `docs/operacao/homologacao.md` tem as seis seções, todas as variáveis lidas por `env(...)` sem `default` em `base.py` e `prod.py` (extraídas pela árvore de sintaxe), e nenhum valor que pareça segredo. Descreve a configuração que a implantação deve produzir; o estado "ainda não implantado" está no topo. "Custos observados" está com "a medir".
- **A-2 passa:** `docs/relatorio-fase1.md` tem as nove seções, as três linhas da infraestrutura 7 e os links para a matriz e para o procedimento de restauração. **É uma versão provisória e diz que o critério de saída NÃO foi atingido** (regra 12): o resumo e as seções listam o que falta. A tabela de etapas deixa "a consolidar" para PR e reprovações das E01 a E09, que não consegui levantar com segurança nos pareceres.
- **A-3 e A-4 estão `xfail(strict=True)`**, com o motivo "E16-08 bloqueada por dependência". O A-3 exige o registro de dois testes de restauração (caminhos A e B) com todas as colunas preenchidas e um RTO numérico, que só existem depois da execução na homologação. O A-4 exige que cada melhoria pendente tenha a fase indicada, o que depende da decisão do responsável. Não os afrouxei: `strict=True` faz o teste falhar assim que passarem (aviso para tirar o marcador) e o motivo fica no código. Não afirmo que A-3 e A-4 foram atendidos.

## Critérios de execução (A-5 a A-15): não executados

Nenhuma evidência foi fabricada. Para cada um, o que falta:

| Critério | Depende de |
|---|---|
| A-5 (`fly releases`/`fly status`) | Fly.io, commit da `main` com E16-01 a E16-07 (depois do merge) |
| A-6 (`/saude/`, `/entrar/`, Better Stack) | Fly.io e Better Stack |
| A-7 (erro provocado no Sentry, sem dado pessoal) | Sentry |
| A-8 (worker parado 20 min e aviso de check-in perdido) | Fly.io, Sentry e a caixa de e-mail |
| A-9 (avatar no R2 sem URL pública) | R2 |
| A-10 (backup das 03:00 e linha no painel) | R2, worker ligado e a chave `age` |
| A-11 (e-mail de convite pelo SES) | SES e endereço verificado |
| A-12 (roteiro funcional de vários dias e isolamento) | homologação no ar |
| A-13 (dois testes de restauração cronometrados) | homologação, R2 e a chave privada do `age` |
| A-14 (suíte no commit final da `main` e no branch de testes do Neon) | merge e Neon |
| A-15 (README e relatório sem bloqueador aberto) | PR da fatia; a fase só vira "encerrada" se a regra 12 permitir |

## Fora do que pude fazer agora

- **Melhorias (regra 10):** a revisão com o responsável não aconteceu. `docs/melhorias.md` não foi alterado por mim além de M-13 e M-14 (E16-03). A decisão é do responsável, apresentada pelo especificador.
- **README:** a Parte 1 do estado do projeto, nas duas línguas, é atualizada por quem abre o PR da E16 (AGENTS.md §10); não abri PR.

## Verificação

`uv run pytest -q tests/ambiente`: **32 passed, 2 xfailed**. `ruff` e `mypy` (554 arquivos) limpos. A suíte completa da etapa está registrada no fim da E16. Sem push, PR nem merge.


---

## Revisão independente — agente 3 — 2026-11-17

Base avaliada: `52f8745870ebfa007ad6a94edf7f968ae472d04e`, branch
`e16-especificacoes`, diff contra `02f8e91`. Requisitos lidos antes do código:
AGENTS.md, especificação funcional v1.7, infraestrutura v1.8 e as oito specs e
acceptances da E16. Registros do implementador acima preservados integralmente.
A evidência global de execução está no parecer da E16-08 abaixo.

**Veredito global da E16: REPROVADO. A fase 1 não está encerrada.**

A fatia E16-08 continua **BLOQUEADA POR DECISÃO/dependências operacionais** no que
exige contas da fase 0 e deliberação do responsável sobre melhorias. Isso é distinto
dos defeitos de código e evidência que já podem ser corrigidos localmente.

| Achado | Classificação | Local | Resultado |
|---|---|---|---|
| E16-R01 | Bloqueador | E16-01 | Dockerfile atual falha no collectstatic |
| E16-R02 | Bloqueador | E16-03 | Token de acesso e nome preservados no envelope do Sentry |
| E16-R03 | Importante | E16-04 | Colisão de chave sobrescreve backup confirmado |
| E16-R04 | Importante | E16-05 | Estoque histórico causa falsa falha na restauração |
| E16-R05 | Importante | E16-07 | Matriz omite afirmações dos requisitos |
| E16-R06 | Importante | E16-07 | Validador aceita classe fora da coleta e testes pulados |
| E16-R07 | Bloqueador de encerramento | E16-08 | Homologação/restauração reais e decisões pendentes |

Os detalhes, referências e reproduções de R01 a R06 estão nos respectivos pareceres.
E16-02 e E16-06 aprovadas em seu escopo; isso não aprova a integração nem encerra a fase.

### E16-R07 — Encerramento sem evidência operacional suficiente

Referências: infraestrutura §6/§7; E16-08 regras 6, 7, 10, 11 e 12 e A-3 a A-15.
O próprio registro do implementador informa ausência de implantação, roteiro real,
avisos externos, restauração dos caminhos A/B, RTO medido, suíte no Neon e decisão
sobre melhorias. A tabela de restauração está vazia, RTO “a definir”, relatório é
provisório e a história de PRs/reprovações das E01 a E09 está por consolidar.
Os dois `xfail(strict=True)` são pendências declaradas, **não critérios aprovados**.
A-1/A-2 cobrem estrutura documental, não a veracidade/completude da operação.

Retorno: após corrigir os defeitos locais e disponibilizar os pré-requisitos, executar
o roteiro da spec, registrar evidências reais e decisões, retirar xfails quando
resolvidos e submeter nova revisão. Não foram solicitadas nem usadas credenciais,
não houve implantação, comunicação externa, PR, push ou dinheiro real nesta revisão.
As decisões sobre melhorias são gate do responsável com o especificador; não foram
presumidas pelo revisor. A atualização dos READMEs cabe a quem abrir o PR, conforme §10.

Também corrigir na consolidação os custos atribuídos à infraestrutura §10: ela
informa US$ 8–15 apenas para Fly.io e US$ 15–35 para o total fixo. Os dois documentos
operacionais/final resumem equivocadamente o total como US$ 8–15. É comparação com
a fonte interna aprovada, não uma cotação atual dos serviços.

### Processo e limites

Foram lidos os registros Red/Green de todas as fatias e comparados com os diffs.
São registros do implementador com comandos, resultados e justificativas, não
transcrições independentes da ordem temporal. Commits combinam testes e produção.
Não foi encontrada evidência que contradiga a ordem declarada; a caracterização 116
é explicitamente admitida na spec. A exceção do usuário para `7181c67` não foi
estendida à E16. Não há aprovação baseada apenas em testes verdes.

Os probes do revisor usaram apenas dados sintéticos, transporte Sentry em memória,
S3 do moto e bancos de testes com nomes próprios. O arquivo temporário de testes foi
removido após conferir o status; os trechos reprodutíveis foram preservados nos
pareceres. Código de produção e testes versionados não foram corrigidos pelo revisor.


### Verificações independentes concluídas

| Verificação | Resultado |
|---|---|
| Suíte completa, `pytest -q -p no:cacheprovider --tb=short` | **3554 passed, 1 skipped, 2 xfailed**, 716,74 s (11min56s), saída 0 |
| `docker build -t organicos-meier:revisor-e16-52f8745 .` | **Falhou**, saída 1, falta `R2_ENDPOINT` no collectstatic (R01) |
| `.venv/Scripts/ruff.exe check .` | Passou |
| `.venv/Scripts/ruff.exe format --check .` | Passou, 461 arquivos |
| `.venv/Scripts/mypy.exe .` | Passou, 554 arquivos |
| `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=config.settings.test` | Passou, nenhuma mudança |
| Probes extras de Sentry (token e nome), backup e estoque histórico | Quatro asserções de proteção falharam, reproduzindo R02/R03/R04 |
| Probes AST de classe/skipif | Três referências indevidas aceitas, reproduzindo R06 |
| Amostra semântica da matriz | 20 cenários e 10 técnicos lidos; R05 identificado |
| `git diff --check` e preservação dos oito registros anteriores | Passaram |

A suíte foi executada com o ambiente virtual existente, PostgreSQL local e um runner
fora do repositório para não disputar o banco do implementador. Com `PYTHONPATH`
apontando para a raiz, o conteúdo do runner usado foi:

```python
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.test'
from django.conf import settings
for database in settings.DATABASES.values():
    database.setdefault('TEST', {})['NAME'] = 'test_organicos_revisor_e16_52f8745'
import pytest
sys.exit(pytest.main(sys.argv[1:]))
```

Comando: `.venv/Scripts/python.exe -u "$env:TEMP/revisor_e16.py" -q -p no:cacheprovider --tb=short`.
Os probes usaram runners equivalentes com nomes de banco separados e os trechos
registrados em cada achado. Não houve alteração nas configurações versionadas.
A suíte terminou com dez avisos de depreciação de `send_default_pii` (M-14).
Nas execuções curtas dos probes houve aviso de conexão remanescente ao tentar
remover o banco de testes; isso não afetou as asserções reproduzidas. A suíte completa
não teve esse aviso.

O único skip é E16-04 A-15: faltam `pg_dump`, `pg_restore`, `age` e `age-keygen` no
host Windows. Os xfails são E16-08 A-3/A-4. Nenhum deles foi contado como aprovação.
Sem acesso operacional nesta revisão, não foram reexecutados os critérios externos
A-5 a A-15 da E16-08 nem o job remoto do PR. Logs locais: `revisor_e16_suite.log`,
`revisor_e16_imagem.log`, `revisor_e16_probes.log` e `revisor_e16_estoque.log` em `%TEMP%`;
as evidências necessárias para reproduzir os achados estão neste commit documental.

**Próximo gate:** implementador corrige R01 a R06 com evidência Red/Green e devolve
para revisão; R07 requer completar a homologação e as decisões previstas. Não declarar
E16 aprovada nem fase 1 encerrada enquanto esses critérios não forem satisfeitos.

## Correção E16-R07 — o que se pôde corrigir sem a fase 0 (implementador, 2026-11-17)

- **Custos (A-16):** Red observado (`tests/ambiente/test_artefatos_de_implantacao.py::test_os_custos_seguem_a_infraestrutura_10` falhou: `homologacao.md` não trazia "US$ 15–35"). `docs/operacao/homologacao.md` e `docs/relatorio-fase1.md` passaram a citar as faixas da infraestrutura 10 linha a linha (Fly.io US$ 8–15, Neon US$ 5–20, SES/R2/Sentry/Better Stack/Cloudflare US$ 0–2, total fixo US$ 15–35); US$ 8–15 só aparece como a faixa do Fly.io.
- **Etapas entregues:** no relatório, "a consolidar" virou "não registrado" (sem estimativa), como a spec manda.
- **Ordem do encerramento (regra 15):** as regras 2 a 7 só começam depois de R01 a R06 aprovadas pelo revisor, com a implantação no commit corrigido. Os dois `xfail(strict=True)` (A-3 e A-4) continuam, com o motivo declarado: não são critérios atendidos e não estão na matriz (A-17); serão retirados antes da revisão de aprovação.
- **R07 permanece aberto:** homologação, restauração dos caminhos A e B com RTO medido, suíte no Neon e decisões sobre melhorias dependem da fase 0 e do responsável. Não executei nada disso.

## Verificação final da correção

`uv run pytest -q -p no:cacheprovider -ra` no commit `281d191`: **3604 passed, 1 skipped, 2 xfailed** em 10 min 34 s. `ruff` (check e format) e `mypy` (558 arquivos) limpos; `makemigrations --check` sem mudanças. Sem push, PR nem merge. Código corrigido no commit `281d191` (os commits seguintes só mudam documentos).


## Revalidação independente — 2026-11-18 — commit 5f12d21

**Veredito global: REPROVADO. A E16 e o encerramento da fase 1 não estão aprovados.** Revisados os commits de correção até 5f12d21, sobre o parecer 6200dac, com especificações corrigidas e registros do implementador preservados.

| Achado | Classificação | Resultado desta revisão |
|---|---|---|
| R01 | Bloqueador anterior | Encerrado: build e ferramentas reais conferidos |
| R02 | Bloqueador anterior | Encerrado: tokens e identificação nos envelopes cobertos |
| R03 | Importante | Aberto: perda de sessão permite sobrescrita concorrente |
| R04 | Importante anterior | Encerrado: estoque histórico excluído |
| R05 | Importante | Aberto: matriz ainda contém provas incorretas; leitura integral não feita |
| R06 | Importante | Aberto: validador ainda aceita testes pulados/não coletados |
| R07 | Bloqueador de encerramento | Aberto: homologação, restauração real e decisões pendentes |

### Execução independente

- Suíte completa, runner temporário com `config.settings.test`, PYTHONPATH da raiz e TEST.NAME `test_organicos_revisor_e16_5f12d21`: `pytest -q -p no:cacheprovider --tb=short` — **3604 passed, 1 skipped, 2 xfailed, 18 warnings, 830,86s**. O runner só isola o banco; nenhuma alteração de produção.
- Skip local: `test_backup_externo_ferramentas.py`, ausência de pg_dump/pg_restore/age/age-keygen no Windows. Reexecutado na imagem construída de 5f12d21, com EXIGIR_FERRAMENTAS_DE_BACKUP=1 e banco isolado: **1 passed em 7,42s**.
- Xfails: `test_o_registro_da_restauracao_e_o_rto` e `test_as_melhorias_tem_decisao`. São pendências explícitas, não critérios aprovados. Nenhum deles integra a matriz.
- `ruff check .`: passou; `ruff format --check .`: 465 arquivos já formatados; `mypy .`: 558 arquivos sem erros; `python manage.py makemigrations --check --dry-run`: No changes detected. Verificações estáticas sobre a árvore entregue, antes de adicionar a prova temporária.
- Docker build: saída 0; PG 17.12, age 1.1.1, UID 10001 e Config.Env conferidos (E16-01).
- Prova adicional de perda de sessão do backup: **1 failed**, hash do objeto diverge do registro confirmado (E16-04).
- Três probes do validador: referências aceitas, porém dois skips e uma ausência de coleta no pytest (E16-07).
- Amostra semântica nova de 20 cenários + 10 técnicos, além de C2 e T-40: falhas de prova documentadas em E16-07.

As execuções completas e a prova real no contêiner concluíram antes da interrupção da sessão. Nesta retomada, Docker/PostgreSQL estavam desligados; foram reiniciados para a prova residual, que concluiu. Nenhum deploy, conta externa, dinheiro real, push ou execução de CI remoto. Os 18 warnings da suíte não causaram falha (incluem depreciação da opção send_default_pii).

### R07 e próximo gate

Correção documental dos custos e explicitação da pendência aceitas. Continuam faltando homologação nos provedores, restauração dos caminhos A/B com RTO medido, suíte no Neon e decisões do responsável sobre melhorias, conforme as regras da E16-08. Os xfails são permitidos durante a pendência, mas não autorizam encerrar a etapa. Pela regra 15 corrigida, iniciar essa execução real somente após R01 a R06 aprovados; R03, R05 e R06 ainda impedem esse gate.

Próximo passo: especificador/implementador tratam a garantia insuficiente do R03 e o implementador conclui R05/R06 com evidência. Nova revisão técnica antes da homologação. Não houve correção de produção pelo revisor. Pareceres anteriores e registros Red/Green permanecem integralmente preservados.


## Nova revalidação independente — 2026-11-18 — commit 9f4163b

**Veredito global: REPROVADO. E16 e encerramento da fase 1 continuam pendentes.** Revisão das correções de 07deb0e a 9f4163b, sobre o parecer 91c7c6f. Árvore inicialmente limpa.

| Achado | Resultado atual |
|---|---|
| R01/R02/R04 | Encerramentos anteriores mantidos; respectivas implementações não alteradas nesta rodada |
| R03 | **Encerrado**: identificador por execução e reprodução de perda da sessão passaram |
| R05 — importante | **Aberto**: matriz ainda atribui provas parciais a afirmações completas |
| R06 — importante | **Aberto**: formas não coletadas/puladas aceitas; A-23 admite erro de configuração como sucesso e falha com xfailed real |
| R07 — bloqueador de encerramento | **Aberto**: homologação, restauração real/RTO e decisões pendentes |

### Verificações independentes

Runner temporário: `config.settings.test`, PYTHONPATH da raiz e TEST.NAME `test_organicos_revisor_e16_9f4163b`, sem mudança no repositório. Comando de pytest:

```text
pytest -q tests/tecnicos/test_backup_externo.py tests/rastreabilidade tests/ambiente tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py -p no:cacheprovider --tb=short
```

Resultado: **1 failed, 113 passed, 2 xfailed, 1 warning, 64,56s**. Falha em A-23 detalhada na E16-07. Os testes de backup (inclusive A-26), caracterizações novas e demais guardas selecionadas passaram. Xfails continuam sendo restauração/RTO e decisão sobre melhorias da E16-08; não contam como aprovação. Warning de depreciação send_default_pii.

- `ruff check .`: passou.
- `ruff format --check .`: 466 arquivos já formatados.
- `mypy .`: 559 arquivos sem erros.
- `python manage.py makemigrations --check --dry-run`: No changes detected.
- Terceira amostra semântica de 20 cenários e 10 técnicos, mais revalidação dos exemplos e limites declarados: R05 permanece (E16-07).
- Probes em arquivos temporários: dois casos aceitos pelo validador, mas sem asserção executada pelo pytest; diagnóstico do falso verde de A-23 comprovado com e sem PYTHONPATH (E16-07).

Não foi repetida a suíte completa nesta rodada: a seleção abrange os arquivos de implementação/testes alterados e já revela falha impeditiva. O resultado **3626 passed, 1 skipped, 2 xfailed** permanece como relato do implementador, não como execução independente desta revisão; o falso verde do A-23 exige revalidar esse registro. Build e backup com ferramentas reais têm evidência da revisão anterior, não foram reexecutados neste commit. Sem execução de CI remoto, deploy, acesso a provedor real, push ou alteração de produção.

### Próximo gate

R03 está aprovado no escopo corrigido. Implementador deve completar a cobertura semântica de R05 e a guarda/prova real de R06, com registros Red/Green e regressões pertinentes. Só após aprovação de R01 a R06 começa a homologação real prevista pela regra 15 da E16-08. R07 não pode ser encerrado por testes locais nem pelos xfails. Os pareceres e registros anteriores foram preservados integralmente.

## Revalidação independente das novas correções — 2026-11-18 — de1111c

**Veredito global: REPROVADO. A E16 e o encerramento da fase 1 não estão aprovados.** Revisados os commits 181bf98 a de1111c, sobre o parecer ec5c9d3. Árvore inicialmente limpa. As alterações desta rodada concentram-se na E16-07, testes, matriz e conferência no CI; não há alteração de produção.

R01, R02, R03 e R04 mantêm seus encerramentos anteriores. **R05 permanece importante e aberto**: a quarta amostra e a releitura das entradas apontadas encontraram vínculos insuficientes em C63, T-11 e T-38; C96 continua sem cobertura do histórico exigido pelo texto-base. Evidências, requisitos e retorno detalhados no novo parecer de `docs/specs/E16-07/review.md`. O verde da suíte e da conferência estrutural/JUnit não comprova sozinho a adequação semântica dessas ligações.

**R07 permanece bloqueador de encerramento**: faltam as evidências de homologação nos provedores, suíte no Neon, restauração dos caminhos A/B com RTO medido e decisões do responsável sobre melhorias. Os xfails de pendência não representam critérios cumpridos. A regra 15 da E16-08 continua impedindo iniciar essa execução real antes de R01 a R06 aprovados; R05 ainda impede esse gate. Não se realizou deploy nem acesso a provedor real nesta revisão.

Próximo gate: implementador corrige a rastreabilidade residual; especificador trata a devolução de C96 conforme a fonte de verdade, sem eliminar silenciosamente o requisito. Após aprovação técnica, executar e revisar a homologação/recuperação e as decisões previstas pela E16-08. Pareceres e registros anteriores preservados integralmente. Sem correções de produção e sem push pelo revisor.

### Resultado final das verificações independentes

**R06 encerrado**, conforme a revisão da lista fechada, do A-23 isolado, dos testes do JUnit e do fluxo de CI registrada na E16-07. Situação final: **R01 a R04 e R06 encerrados; R05 importante aberto; R07 bloqueador aberto**.

Runner temporário fora do repositório, com `DJANGO_SETTINGS_MODULE=config.settings.test`, PYTHONPATH da raiz e TEST.NAME `test_organicos_revisor_e16_de1111c`, executando `pytest.main` com:

```text
pytest -q -p no:cacheprovider --tb=short --junitxml=<TEMP>/revisor_e16_de1111c.xml
python -m tests.rastreabilidade.conferir_execucao <TEMP>/revisor_e16_de1111c.xml
```

- Suíte completa: **3651 passed, 1 skipped, 2 xfailed, 18 warnings em 844,31s**; saída 0.
- JUnit: **“Toda referência da matriz passou na execução.”**, saída 0. As 279 referências distintas foram encontradas e passaram; nenhum skip/xfail da suíte integra a matriz.
- `python -m ruff check .`: All checks passed.
- `python -m ruff format --check .`: 469 arquivos já formatados.
- `python -m mypy .`: 562 arquivos sem erros.
- `python manage.py makemigrations --check --dry-run`: No changes detected.
- Conferência estática da matriz: nenhum problema; 174 entradas, 594 afirmações e 599 ligações. Quarta amostra semântica: R05 permanece, pelos contraexemplos registrados na E16-07.

O skip é `test_backup_externo_ferramentas.py`: pg_dump, pg_restore, age e age-keygen ausentes no ambiente Windows. Os dois xfails são `test_o_registro_da_restauracao_e_o_rto` e `test_as_melhorias_tem_decisao`; permanecem pendências explícitas de R07. Os warnings não causaram falha e incluem a depreciação de send_default_pii. Build e teste de backup com ferramentas reais têm evidências da revisão anterior, não foram repetidos nesta rodada sem alterações de produção. Nenhuma execução de CI remoto, homologação externa ou restauração operacional foi inferida desses resultados locais. **Veredito mantido: REPROVADO.**
