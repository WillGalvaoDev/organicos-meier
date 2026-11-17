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
