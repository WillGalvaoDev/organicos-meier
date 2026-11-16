# E14-01 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_recebimento.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `1aab88b` | **25 failed**: `apps.pedidos.recebimento` e `RecebimentoDoFornecedor` inexistentes (`ModuleNotFoundError`/`ImportError`). Os três testes de concorrência também falham pela importação. |
| Green | `65e1143` | **25 passed** (A-1 a A-17, com A-5 em seis casos e A-7 em quatro) |
| Refactor | `a766820`, `ac84a38` | tipos do `mypy` (retornos `Any`); 25 passed; `ruff` e `mypy apps/pedidos` limpos |

\* hash conferido no `git log` da branch (`E14-01: Red do recebimento do fornecedor ...`).

## O que foi feito
- `RecebimentoDoFornecedor` (só inserção, migração `0016` com `instalar_protecao_so_insercao`), `registrar_recebimento`, `situacao_do_recebimento`, `recebimento_resolvido` e `RecebimentoRecusado` em `apps/pedidos/recebimento.py`.
- Trava da rodada (`select_for_update(no_key=True)`) antes de qualquer conferência; o acionamento é conferido antes e sob a trava; `IntegrityError` é desfeito e relido.
- **Scaffolding justificado:** `apps/pedidos/ocorrencias.py` nasce só com `somas_das_ocorrencias` devolvendo zeros, como a E14-01 prevê ("até lá, a soma é zero"); a E14-02 a substitui com Red próprio.

## Decisões técnicas
- **Condições do ciclo no apoio de teste:** a preparação `dar_prazo_de_teste` não cria `CondicaoDoProdutoNoCiclo`, que o fechamento real cria (`apps/rodadas/ciclos.py`). O recebimento lê o incremento dessa condição (spec). Por isso o apoio da E14 (`tests/apoio/entrega.py`, `arranjo_ae`) cria as condições do AE; nenhum teste da E13 mudou.
- **Apoio por peso (A-14):** `unidade_de_p1` e `incremento_de_p1` opcionais em `montar_arranjo`/`arranjo_ap` (padrão igual ao anterior).
- **`tests/conftest.py`:** prefixos `test_recebimento`, `test_ocorrencias`, `test_liberacao_da_retirada`, `test_retirada`, `test_cenario_22_` e `test_cenario_23_` ligam o banco do simulador (as fatias seguintes os usam).
- **Auditoria:** a quantidade vai como `Decimal` (o JSON grava "7"); o teste compara por valor.
- Dois ajustes nos meus próprios testes durante o Green (não afrouxam critério): o auxiliar `receber(..., acionamento=None)` gerava um UUID novo em vez de testar o `None` (agora há um sentinela `NOVO`), e a comparação da auditoria passou a ser por valor decimal.


---

## Revisão independente — agente 3 — 2026-11-16

**Objeto:** `5b00c56`, branch `e14-especificacoes`, comparação com `bc35037` (main após E13). Fontes: especificação funcional v1.7, infraestrutura v1.8, AGENTS.md e as oito especificações e matrizes da E14. Histórico do implementador acima preservado.

A execução independente e o parecer consolidado estão em [E14-08/review.md](../E14-08/review.md), incluindo o código das contraprovas. A revisão não alterou código de produção nem os testes do implementador.

**Parecer da fatia: APROVADO.**

| Critérios | Verificação |
|---|---|
| A-1 a A-4 | Recebimentos parciais, soma, resolução e limite da linha formal; conferência sob trava da rodada. |
| A-5 a A-10 | Decimal finito, incremento congelado, produto/etapa/permissão e idempotência com conteúdo. |
| A-11 a A-14 | Auditoria sem dados pessoais, preservação financeira/comercial, proteção ORM/SQL e peso. |
| A-15 a A-17 | PostgreSQL: excesso concorrente, mesmo acionamento e corrida com cancelamento. |

Código confrontado: `recebimento.py`, modelo/migração 0016 e integração das somas da E14-02. Testes: `test_recebimento.py`; todos incluídos na suíte independente. Sem achado nesta fatia.

TDD: testes e apoios em `1aab88b`, produção em `65e1143`, refatorações de tipos em `a766820`/`ac84a38`. O Red de 25 falhas de importação e o Green de 25 testes estão registrados acima e são compatíveis com o conteúdo e a ordem dos commits. O scaffolding inicial das somas foi substituído na E14-02.
