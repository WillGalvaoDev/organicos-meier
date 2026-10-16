# E03-02 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **REPROVADO** sobre `2e7bbcc` (2026-10-16). E03 global: **REPROVADO**. Histórico preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** app `apps.rodadas` (modelo `Rodada` só com campos,
`Etapa`, `ETAPAS_ATIVAS`, sinal), stubs de `abrir_rodada`, `travar_condicoes`, `alterar_minimo`,
views vazias, rotas, `RodadaFactory`, migração `0001_initial`. Suíte antes do Red: 702 passando.

**Red** (`uv run pytest tests/tecnicos/test_rodadas_*.py`): **34 falhas, 3 passando**. Todas as
falhas são de asserção sobre comportamento ausente: `DID NOT RAISE RodadaAtivaExistente` (5),
`DID NOT RAISE CondicoesCongeladas` (4), `assert 200 == 409` (5), `assert 200 == 302` (3),
`DID NOT RAISE IntegrityError` (índice), `DID NOT RAISE RuntimeError` (receptor),
`DID NOT RAISE TransactionManagementError`, `DID NOT RAISE PermissionDenied`,
`DID NOT RAISE ValidationError`, `assert None is not None`, auditoria `0 == 1`/`0 == 2`, e
concorrência sem efeito. As 3 que já passavam são guardas de regressão: 403/redirecionamento de
`test_rodadas_permissoes.py` (as rotas do andaime já usam `somente_administrador`).
Ajustes de teste durante o Red (erros do teste, não do código): A-3 tinha asserção fraca (passava
no stub) e foi reforçada (`pk is not None`, duas rodadas); o teste A-10 criava um segundo
administrador (há um único por restrição do banco).

**Green:** `rodada_ativa_unica_por_fornecedor` (índice único parcial, migração `0002_restricoes`);
`travar_condicoes`; `abrir_rodada`; `alterar_minimo`; views `abrir` e `minimo`; formulário
`FormularioMinimo`; templates. Resultado: `test_rodadas_*.py` 37 passando; suíte completa
**739 passando**; `ruff check`, `ruff format`, `mypy --strict` e `makemigrations --check` limpos.

**Refactor:** apenas `constraints` como tupla (RUF012) após o Green; suíte verde.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_rodadas_abertura.py::test_abertura_cria_rodada_em_interesse_e_audita` |
| A-2 | `::test_recusa_quando_ja_ha_rodada_ativa` (5 etapas), `::test_recusa_pela_rota_mostra_a_mensagem` |
| A-3 | `::test_abre_quando_a_ultima_rodada_terminou` |
| A-4 | `::test_banco_recusa_segunda_rodada_ativa` |
| A-5 | `test_rodadas_concorrencia.py::test_duas_aberturas_simultaneas_geram_uma_rodada` (×10) |
| A-6, A-7 | `test_rodadas_abertura.py::test_receptor_que_falha_desfaz_a_abertura`, `::test_receptor_e_chamado_uma_vez_dentro_da_transacao` |
| A-8 (cenário 71) | `test_rodadas_minimo.py::test_altera_o_minimo_em_interesse_e_audita` |
| A-9 (cenário 72, T-23) | `::test_minimo_congelado_pela_rota`, `::test_minimo_congelado_pelo_servico` |
| A-10 | `::test_sem_rodada_ativa_recusa_pela_rota_e_pelo_servico` |
| A-11 | `::test_minimo_invalido_e_erro_de_formulario`, `::test_servico_recusa_valor_invalido` |
| A-12, A-13 | `::test_mesmo_valor_nao_grava_nem_audita`, `::test_get_fora_de_interesse_mostra_mensagem_sem_formulario` |
| A-14 | `test_rodadas_concorrencia.py::test_alteracao_do_minimo_espera_a_mudanca_de_etapa` |
| A-15 | `::test_duas_alteracoes_simultaneas_ficam_em_serie` |
| A-16 | `test_rodadas_abertura.py::test_travar_condicoes_fora_de_transacao_falha` (`transaction=True`) |
| A-17 | `test_rodadas_permissoes.py` |
| A-18 | `test_rodadas_minimo.py::test_comprador_nao_pode_ser_autor` |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- `abrir_rodada` trava só o fornecedor (e não precisa travar rodada: a checagem de rodada ativa
  ocorre sob a trava do fornecedor); o índice parcial é a defesa final. Ordem global mantida:
  fornecedor → rodada.
- `travar_condicoes` detecta transação por `connection.in_atomic_block`.
- `alterar_minimo` valida o valor antes de abrir a transação (erro de valor tem precedência sobre
  fase só quando o valor é inválido); depois trava e relê.
- A auditoria grava o mínimo como texto decimal (`str(Decimal)`, duas casas).
- `abrir` aceita só `POST` (`require_POST`, depois do controle de administrador).
- A tela do mínimo preenche o campo com o valor atual (vírgula decimal) e mostra a mensagem
  única, sem formulário, quando não há rodada em `interesse` (GET) ou o serviço recusa (POST, 409).

## Limitações de verificação

- A-14 usa `pg_stat_activity.wait_event_type = 'Lock'` em todo o banco de teste; outro processo
  esperando por trava no mesmo banco poderia liberar a espera cedo (não ocorre na suíte).
- Não há transições de etapa nesta fatia: etapas posteriores são criadas pela fábrica.
- Não executei navegador; as telas foram verificadas pelo cliente de teste do Django.

## Revisão independente — 0ceb171 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

A-1 a A-18: abertura, unicidade, rollback de receptor, congelamento, no-op e concorrência cobertos e verdes. Aberturas simultâneas têm dez repetições; alteração versus fechamento confirma espera no Postgres. Falha adicional na entrada do mínimo: E03-R01.

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

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

R01 encerrado quanto ao overflow; A-19 verde em interesse. E03-R03 aberto: a precedência do congelamento expressamente exigida na especificação corrigida não é cumprida para mínimo excedente.

Evidência comum: suíte completa **1104 passed em 137,20 s**; script original independente **16 passed em 7,70 s**; probes complementares **6 failed em 2,23 s** (R03/R04); lint, formatação, tipos, migrações e checks Django sem erros. Detalhes, reprodução e limites no [parecer consolidado](../E03-08/review.md), seção deste SHA. Nenhuma alteração de produção ou testes versionados pelo revisor.


## Correção E03-R03 — implementador (aguardando nova revisão independente)

Critérios: A-20 e A-21. Nada aqui é aprovação.

**Red.** Testes escritos antes do código (andaime: `condicoes_editaveis` devolvendo `True`, sem comportamento). `uv run pytest tests/tecnicos/test_rodadas_estoque.py tests/tecnicos/test_condicoes_congeladas_matriz.py -q` sobre `2e7bbcc` + testes: **69 failed, 99 passed**, todas por asserção (`200 != 409` na fase congelada; `ValidationError` no lugar de `CondicoesCongeladas`; `value` do limite ausente ou igual ao gravado). Os serviços `alterar_multiplo` e `alterar_incremento` já passavam, como a spec previa.

**Green.** Mudanças mínimas:
- `apps/rodadas/condicoes.py`: `condicoes_editaveis(fornecedor)`, leitura sem trava.
- `apps/fornecedores/servicos.py`, `apps/rodadas/estoque.py`: a validação do valor passou para dentro de `transaction.atomic()`, depois de `travar_condicoes`, da conferência da rodada e (no estoque) da trava do produto/estoque. Helpers e mensagens não mudaram.
- `apps/fornecedores/views.py`, `apps/catalogo/views.py`, `apps/rodadas/views.py`: no `POST`, a fase é conferida antes do formulário; fora de interesse, 409 com a mensagem única e sem campo editável.
- `apps/rodadas/views.py`, `templates/rodadas/estoque.html`: o formulário recusado volta na própria linha, com o texto bruto (escapado pelo template) e a mensagem em `role="alert"`; erros sem linha ficam no aviso do topo.

**Testes (Green).** `tests/tecnicos/test_condicoes_congeladas_matriz.py`: A-12 (rota, 5 condições × 6 situações × 5 classes de valor, com e sem `HX-Request`), A-13 (serviços), A-20 e A-21 da E03-02, completude da matriz com as classes de valor, `condicoes_editaveis` e o probe `test_minimo_excedente_fora_de_interesse_responde_409` do revisor. `tests/tecnicos/test_rodadas_estoque.py`: A-22, A-23, A-24 (verificação dentro do `<form>` com `html.parser`, inclusive escape) e o probe `test_estoque_preserva_entrada_rejeitada`. Nos dois probes literais, só mudaram a fixture (`admin` → `admin_client`/fixture local, porque `admin` já é outra fixture no arquivo de estoque) e as anotações de tipo exigidas pelo `mypy --strict`; o corpo das asserções é o do revisor.

**Resultado.** Mesmos dois arquivos: **168 passed**. Suíte completa: **1187 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros. Nenhum teste existente foi alterado ou afrouxado.
