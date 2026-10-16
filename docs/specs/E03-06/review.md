# E03-06 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **REPROVADO** sobre `0ceb171` (2026-10-16). E03 global: **REPROVADO**. Evidências históricas do implementador abaixo; revisão independente ao final.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** exceção `IncrementoIncompativel` (sem mensagem),
`alterar_incremento` que não altera nada, view vazia e rota `produtos_incremento`. Suíte antes do
Red: 950 passando.

**Red** (`uv run pytest tests/tecnicos/test_catalogo_incremento*.py tests/tecnicos/test_catalogo_permissoes.py`):
**32 falhas, 4 passando**. Falhas por asserção/ausência de comportamento: `DID NOT RAISE`
(`IncrementoIncompativel`, `IncrementoInvalido`, `CondicoesCongeladas`, `PermissionDenied`),
`200 == 302/409`, auditoria `0 == 1`, concorrência sem efeito (`a outra conexão não ficou esperando
pela trava`). As 4 que passavam são guardas de regressão: 403/redirecionamento das permissões e
"preço continua editável no fechamento" (A-7, comportamento já existente da E03-03).

**Green:** `servicos.py` (`alterar_incremento`, `IncrementoIncompativel` com `codigo`),
`FormularioIncremento`, view `incremento`, template `catalogo/incremento.html`, link na tela do
produto. Resultado: `test_catalogo_*.py` 154 passando; suíte completa **983 passando**;
`ruff check`, `ruff format`, `mypy --strict` e `makemigrations --check` limpos.

**Refactor:** apenas quebra de linha longa em teste (E501) depois do Green.

## Inconsistência da especificação (registrada, sem bloqueio)

O critério **A-3** pede o código `multiplo` ao alterar para `2` "no mesmo produto, sem a parcela
de 1,5". Nesse produto ainda restam a reservada de 1,0 e a pendente de 2,0, e 1,0 não é múltiplo de
2; pela ordem dos passos da especificação (quantidades antes do múltiplo, também na infraestrutura
4.12 e no texto da spec: "vale a ordem dos passos"), a recusa sai como `quantidade`. Decisão
técnica: manter a ordem especificada e provar `multiplo` num produto em que só a pendente de 2,0
fica em uso (as outras parcelas `removida`); o cenário 106 literal (alterar para 2 no produto
completo) é testado como `quantidade`. O resultado observável do cenário 106 (recusa, nada
alterado) é o mesmo. Se o responsável preferir outro código nesse caso, é uma mudança de ordem.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 (cenário 105, T-48) | `test_catalogo_incremento.py::test_incremento_compativel_e_aceito` |
| A-2 (cenário 106, T-48) | `::test_incremento_incompativel_com_reservada_e_recusado`, `::test_incremento_para_2_no_cenario_106_e_recusado` |
| A-3 | `::test_incremento_incompativel_com_o_multiplo_e_recusado` (ver inconsistência acima) |
| A-4 (Q-6) | `::test_pendente_da_fila_tambem_conta` |
| A-5 | `::test_incremento_invalido_pela_tela`, `::test_incremento_invalido_pelo_servico` |
| A-6 (cenário 107, T-48) | `::test_incremento_congelado` (4 etapas, sem rodada, rodada terminada), `::test_get_fora_de_interesse_mostra_so_a_mensagem` |
| A-7 | `::test_preco_continua_editavel_no_fechamento` |
| A-8 | `::test_parcela_removida_nao_impede_a_mudanca` |
| A-9 | `::test_mesmo_valor_nao_grava_nem_audita` |
| A-10 | `test_catalogo_incremento_concorrencia.py::test_alteracao_espera_a_mudanca_de_etapa` |
| A-11 | `::test_parcela_criada_antes_da_trava_barra_a_alteracao` |
| A-12 | `::test_duas_alteracoes_ficam_em_serie` |
| A-13 | `test_catalogo_permissoes.py` (rota do incremento incluída nos dois testes) |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- O valor igual ao atual retorna depois da validação e antes da leitura das parcelas: não grava,
  não audita e não trava as parcelas.
- `eh_multiplo` é aplicado a cada quantidade lida por `quantidades_em_uso(produto, travar=True)`;
  a leitura usa `FOR UPDATE` em ordem de sequência (provado por captura de SQL).
- Erros do formulário aparecem no campo `incremento` (status 200); `CondicoesCongeladas` dá 409; o
  `GET` fora de interesse mostra só a mensagem.
- Redirecionamento após sucesso: detalhe do fornecedor (consistente com as outras telas do
  catálogo).

## Limitações de verificação

- Cenário 108 e T-49 (concorrência com adição de interesse) ficam para a E05, como previsto na
  especificação; A-11 simula a adição com a mesma ordem de travas.
- A-10 e A-11 detectam a espera com `pg_stat_activity.wait_event_type = 'Lock'` no banco inteiro.
- Telas verificadas pelo cliente de teste do Django, não por navegador.

## Revisão independente — 0ceb171 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

A-1 a A-13: compatibilidade com reservas/pendentes/múltiplo, ordem das recusas, no-op, fase, permissões e concorrência cobertos e verdes, com ressalva documental em A-3 (E03-R02, melhoria). A implementação aplica corretamente a precedência da infraestrutura 4.12. Falha adicional na faixa do incremento: E03-R01.

Verificação comum: `uv run pytest -q` — **1058 passed em 147,85 s**; ruff check limpo; ruff format — 238 arquivos; mypy — 193 arquivos sem erros; checks Django e migrações sem pendências. Os probes adicionais de fronteira terminaram em **8 failed, 8 passed em 4,36 s**, reproduzindo E03-R01. Não houve correção de produção ou testes pelo revisor.

Comandos completos, achados, reprodução, limites e parecer global estão em [E03-08/review.md](../E03-08/review.md), na seção de revisão independente deste SHA. Os relatos Red/Green anteriores foram conferidos com o diff e a cobertura; a execução Green é independente, a cronologia Red é evidência documentada pelo implementador.


## Correção E03-R01 — implementador (aguardando nova revisão independente)

Achado do revisor: entrada acima da capacidade das colunas `NUMERIC(12,2)`/`NUMERIC(12,3)` virava
HTTP 500 (`numeric field overflow`). Corrigido conforme a seção "Correção E03-R01" da spec.

- **Red:** com as primitivas só em andaime (constantes `0`, `cabe_*` sempre verdadeiro) e os
  testes de `tests/tecnicos/test_capacidade_decimal.py` e `test_rodadas_minimo.py` escritos:
  **37 falhas, 27 passando**. Os 8 casos do script de probes do revisor que excedem a
  capacidade falharam com `500` e `DataError('numeric field overflow')`, reproduzindo o achado;
  os demais falharam por `DID NOT RAISE` e por asserções de valores.
- **Green:** `apps/nucleo/valores.py` ganhou `MAIOR_DINHEIRO`, `MAIOR_QUANTIDADE` (derivadas de
  `CampoDinheiro` e `CampoQuantidade`), as mensagens de capacidade, `cabe_em_dinheiro` e
  `cabe_em_quantidade`; a regra entrou nos serviços depois das regras de sinal/mínimo e antes da
  compatibilidade: `_minimo` (E03-01/02), `_preco` (E03-03), `validar_incremento`,
  `validar_multiplo`, `validar_quantidade` (E03-03/06) e `_limite` do estoque (E03-05). Nenhuma
  função numérica existente mudou e nenhum `DataError` é capturado. Resultado: suíte completa
  **1104 passando**; `ruff check`, `ruff format --check`, `mypy --strict` e
  `makemigrations --check` limpos.
- **Testes:** `tests/tecnicos/test_capacidade_decimal.py` (A-18 a A-20 da E03-01, A-24 a A-28 da
  E03-03, A-20 e A-21 da E03-05, A-15 da E03-06 e o script de probes do revisor, literal: 16 casos,
  8 no limite com 302 e 8 acima com 200); A-19 da E03-02 em `test_rodadas_minimo.py`.
- **E03-R02:** os testes já cobrem a pré-condição corrigida (A-3: só a pendente de 2,0 →
  `multiplo`; A-14: produto completo → `quantidade`); nenhuma mudança de código.
- **Limite:** um texto com 30 dígitos é recusado pela conversão/formulário com a mensagem de
  formato (permitido pela spec); a exigência é erro de campo, nunca 500.
