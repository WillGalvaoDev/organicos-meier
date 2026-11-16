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
