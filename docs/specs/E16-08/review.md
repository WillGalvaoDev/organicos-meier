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
