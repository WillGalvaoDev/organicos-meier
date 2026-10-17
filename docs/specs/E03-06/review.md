# E03-06 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `8064a14` (2026-10-17). E03 global: **REPROVADO**. Histórico preservado abaixo.

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


## Revalidação independente — 2e7bbcc — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

R01 e R02 encerrados nesta fatia. A-3 corrigido, A-14 documenta a recusa por quantidade no cenário completo; A-15 e os probes de capacidade passam. Ordem de validação preservada.

Evidência comum: suíte completa **1104 passed em 137,20 s**; script original independente **16 passed em 7,70 s**; probes complementares **6 failed em 2,23 s** (R03/R04); lint, formatação, tipos, migrações e checks Django sem erros. Detalhes, reprodução e limites no [parecer consolidado](../E03-08/review.md), seção deste SHA. Nenhuma alteração de produção ou testes versionados pelo revisor.


## Correção E03-R03 — implementador (aguardando nova revisão independente)

Critérios: A-12 da E03-07 (rota do incremento). Nada aqui é aprovação.

**Red.** Testes escritos antes do código (andaime: `condicoes_editaveis` devolvendo `True`, sem comportamento). `uv run pytest tests/tecnicos/test_rodadas_estoque.py tests/tecnicos/test_condicoes_congeladas_matriz.py -q` sobre `2e7bbcc` + testes: **69 failed, 99 passed**, todas por asserção (`200 != 409` na fase congelada; `ValidationError` no lugar de `CondicoesCongeladas`; `value` do limite ausente ou igual ao gravado). Os serviços `alterar_multiplo` e `alterar_incremento` já passavam, como a spec previa.

**Green.** Mudanças mínimas:
- `apps/rodadas/condicoes.py`: `condicoes_editaveis(fornecedor)`, leitura sem trava.
- `apps/fornecedores/servicos.py`, `apps/rodadas/estoque.py`: a validação do valor passou para dentro de `transaction.atomic()`, depois de `travar_condicoes`, da conferência da rodada e (no estoque) da trava do produto/estoque. Helpers e mensagens não mudaram.
- `apps/fornecedores/views.py`, `apps/catalogo/views.py`, `apps/rodadas/views.py`: no `POST`, a fase é conferida antes do formulário; fora de interesse, 409 com a mensagem única e sem campo editável.
- `apps/rodadas/views.py`, `templates/rodadas/estoque.html`: o formulário recusado volta na própria linha, com o texto bruto (escapado pelo template) e a mensagem em `role="alert"`; erros sem linha ficam no aviso do topo.

**Testes (Green).** `tests/tecnicos/test_condicoes_congeladas_matriz.py`: A-12 (rota, 5 condições × 6 situações × 5 classes de valor, com e sem `HX-Request`), A-13 (serviços), A-20 e A-21 da E03-02, completude da matriz com as classes de valor, `condicoes_editaveis` e o probe `test_minimo_excedente_fora_de_interesse_responde_409` do revisor. `tests/tecnicos/test_rodadas_estoque.py`: A-22, A-23, A-24 (verificação dentro do `<form>` com `html.parser`, inclusive escape) e o probe `test_estoque_preserva_entrada_rejeitada`. Nos dois probes literais, só mudaram a fixture (`admin` → `admin_client`/fixture local, porque `admin` já é outra fixture no arquivo de estoque) e as anotações de tipo exigidas pelo `mypy --strict`; o corpo das asserções é o do revisor.

**Resultado.** Mesmos dois arquivos: **168 passed**. Suíte completa: **1187 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros. Nenhum teste existente foi alterado ou afrouxado.


## Revalidação independente — 8064a14 — 2026-10-17

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

Aprovação mantida; incremento recusa pela fase antes do formulário. R01/R02 encerrados e regressão verde.

Suíte completa: **1187 passed em 129,30 s**. Probes independentes: **22 passed, 4 failed em 14,69 s**; os 22 anteriores passam, quatro adicionais reproduzem as pendências R03/R05. Verificações estáticas e CI verdes. Evidências, reprodução e limites no [parecer consolidado](../E03-08/review.md), seção deste SHA. Nenhuma alteração de produção ou testes versionados pelo revisor.
