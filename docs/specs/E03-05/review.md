# E03-05 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **REPROVADO** sobre `8064a14` (2026-10-17). E03 global: **REPROVADO**. Histórico preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** `EstoqueDaRodada` só com campos (sem restrições),
sinal `estoque_alterado`, `estoque.py` com corpos triviais, views vazias, rotas,
`EstoqueDaRodadaFactory`, migração `0003_estoque`. Suíte antes do Red: 894 passando.

**Red** (`uv run pytest tests/tecnicos/test_rodadas_estoque*.py tests/tecnicos/test_rodadas_permissoes.py`):
**45 falhas, 14 passando**. Falhas por asserção/ausência de comportamento: `DID NOT RAISE`
(`CondicoesCongeladas`, `EstoqueAbaixoDoReservado`, `ValidationError`, `IntegrityError`,
`TransactionManagementError`), `200 == 302/409`, auditoria `0 == 1`, concorrência sem efeito
(`a outra conexão não ficou esperando pela trava`). As 14 que passavam: 6 guardas de permissão
(403/redirecionamento, rotas do andaime já usam `somente_administrador`), regressões
(`save()` comum, SQL válido) e 5 testes fracos demais para o andaime; depois do Red os
5 foram reforçados (inclusão de produto indisponível passou a exigir registro persistido; erros de
tela e produto de outro fornecedor passaram a exigir `role="alert"`; a tela passou a exigir o
nome do fornecedor) antes de escrever o código.

**Green:** `migrations/0004_restricoes_do_estoque` (UNIQUE, CHECK e triggers de `gatilhos.py`),
`estoque.py` (`incluir_produto_na_rodada`, `alterar_estoque`, `travar_estoque`, `estoque_livre`,
`EstoqueAbaixoDoReservado`), `forms.py`, três views, template `rodadas/estoque.html`, link no
detalhe do fornecedor. Resultado: arquivos de estoque e permissões 59 passando; suíte completa
**950 passando**; `ruff check`, `ruff format`, `mypy --strict` e `makemigrations --check` limpos.

**Refactor:** apenas ajustes de lint/tipos (linhas longas, `Any`) após o Green.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_rodadas_estoque.py::test_inclusao_com_e_sem_limite_pela_tela` |
| A-2 | `::test_nova_rodada_comeca_sem_produtos` |
| A-3 | `::test_produto_de_outro_fornecedor_e_recusado`, `::test_banco_recusa_produto_de_outro_fornecedor` |
| A-4 | `::test_produto_ja_incluido_e_recusado` |
| A-5 a A-7 (cenário 71, T-23) | `::test_reducao_ate_o_reservado_e_aceita`, `::test_reducao_abaixo_do_reservado_e_recusada`, `::test_sem_limite_nao_pode_ir_abaixo_do_reservado` |
| A-8 | `::test_remover_o_limite_envia_o_sinal` |
| A-9 (cenário 72, T-23) | `::test_estoque_congelado_pela_rota`, `::test_estoque_congelado_pelo_servico` (4 etapas) |
| A-10 | `::test_estoque_de_rodada_antiga_nunca_muda` |
| A-11, A-12 | `::test_sinal_na_inclusao_e_na_alteracao`, `::test_receptor_que_falha_desfaz_a_alteracao`, `::test_receptor_que_falha_desfaz_a_inclusao` |
| A-13 | `::test_estoque_livre`, `::test_estoque_livre_tem_piso_zero` |
| A-14 | `::test_banco_recusa_limite_negativo_troca_de_produto_e_exclusao`, `::test_banco_recusa_troca_de_rodada` |
| A-15 | `test_rodadas_estoque_concorrencia.py::test_alteracao_do_estoque_espera_a_mudanca_de_etapa` |
| A-16 | `::test_reserva_concluida_antes_barra_a_reducao` |
| A-17 | `::test_duas_inclusoes_do_mesmo_produto` (×10) |
| A-18 | `test_rodadas_permissoes.py::test_estoque_so_para_administrador`, `::test_estoque_visitante_anonimo_vai_para_o_login` |
| A-19 | `test_rodadas_estoque.py::test_tela_somente_leitura_fora_de_interesse` |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- Produto de outro fornecedor é verificado **antes** de qualquer trava, comparando
  `produto.fornecedor_id` com `rodada.fornecedor_id` (senão a ausência de rodada ativa do outro
  fornecedor mascararia o erro); a trigger do banco repete a regra.
- `travar_estoque(rodada, produto)` trava o produto e depois o estoque, exige transação aberta
  (`TransactionManagementError`) e supõe que o chamador já fez `travar_condicoes`.
- `alterar_estoque` lê o total reservado com `total_reservado(produto, travar=True)` (parcelas
  travadas em ordem de sequência) e compara só depois de o limite igual ao atual ter retornado
  sem gravar, auditar ou enviar sinal.
- Auditoria de alteração: `{"estoque", "rodada", "produto", "anterior", "novo"}` com texto
  decimal ou `null`.
- Sinal na inclusão: `anterior=Decimal("0")` e `novo=<limite ou None>`, como na especificação.
- A tela re-renderiza com `role="alert"` para erros (status 200), e com 409 para
  `CondicoesCongeladas`; `produto` inexistente no `POST` de inclusão vira "Produto inválido." (200).

## Limitações de verificação

- A reserva real (E05) não existe: A-16 simula a reserva com a mesma ordem de travas
  (`travar_condicoes`, `travar_estoque`, `UPDATE` da parcela).
- A-15 e A-16 detectam a espera com `pg_stat_activity.wait_event_type = 'Lock'` no banco inteiro;
  outro processo esperando por trava no mesmo banco liberaria a thread antes da hora (não ocorre
  na suíte).
- `alocar_pendentes` ao aumentar o estoque é da E05; aqui só o sinal é provado.
- Telas verificadas pelo cliente de teste do Django, não por navegador.

## Revisão independente — 0ceb171 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

A-1 a A-19: isolamento de fornecedor, estoque por rodada, redução até a reserva, congelamento, rollback de receptor e concorrência cobertos e verdes. Reserva simulada anterior impede redução; inclusão duplicada tem dez repetições. Falha adicional na faixa do limite: E03-R01.

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

R01 encerrado quanto ao overflow e às garantias de persistência/sinal; A-20/A-21 verdes. E03-R04 aberto: a regra comum exige preservar a entrada rejeitada, mas os formulários de estoque a descartam.

Evidência comum: suíte completa **1104 passed em 137,20 s**; script original independente **16 passed em 7,70 s**; probes complementares **6 failed em 2,23 s** (R03/R04); lint, formatação, tipos, migrações e checks Django sem erros. Detalhes, reprodução e limites no [parecer consolidado](../E03-08/review.md), seção deste SHA. Nenhuma alteração de produção ou testes versionados pelo revisor.


## Correção E03-R03/R04 — implementador (aguardando nova revisão independente)

Critérios: A-22, A-23 e A-24; A-12 da E03-07. Nada aqui é aprovação.

**Red.** Testes escritos antes do código (andaime: `condicoes_editaveis` devolvendo `True`, sem comportamento). `uv run pytest tests/tecnicos/test_rodadas_estoque.py tests/tecnicos/test_condicoes_congeladas_matriz.py -q` sobre `2e7bbcc` + testes: **69 failed, 99 passed**, todas por asserção (`200 != 409` na fase congelada; `ValidationError` no lugar de `CondicoesCongeladas`; `value` do limite ausente ou igual ao gravado). Os serviços `alterar_multiplo` e `alterar_incremento` já passavam, como a spec previa.

**Green.** Mudanças mínimas:
- `apps/rodadas/condicoes.py`: `condicoes_editaveis(fornecedor)`, leitura sem trava.
- `apps/fornecedores/servicos.py`, `apps/rodadas/estoque.py`: a validação do valor passou para dentro de `transaction.atomic()`, depois de `travar_condicoes`, da conferência da rodada e (no estoque) da trava do produto/estoque. Helpers e mensagens não mudaram.
- `apps/fornecedores/views.py`, `apps/catalogo/views.py`, `apps/rodadas/views.py`: no `POST`, a fase é conferida antes do formulário; fora de interesse, 409 com a mensagem única e sem campo editável.
- `apps/rodadas/views.py`, `templates/rodadas/estoque.html`: o formulário recusado volta na própria linha, com o texto bruto (escapado pelo template) e a mensagem em `role="alert"`; erros sem linha ficam no aviso do topo.

**Testes (Green).** `tests/tecnicos/test_condicoes_congeladas_matriz.py`: A-12 (rota, 5 condições × 6 situações × 5 classes de valor, com e sem `HX-Request`), A-13 (serviços), A-20 e A-21 da E03-02, completude da matriz com as classes de valor, `condicoes_editaveis` e o probe `test_minimo_excedente_fora_de_interesse_responde_409` do revisor. `tests/tecnicos/test_rodadas_estoque.py`: A-22, A-23, A-24 (verificação dentro do `<form>` com `html.parser`, inclusive escape) e o probe `test_estoque_preserva_entrada_rejeitada`. Nos dois probes literais, só mudaram a fixture (`admin` → `admin_client`/fixture local, porque `admin` já é outra fixture no arquivo de estoque) e as anotações de tipo exigidas pelo `mypy --strict`; o corpo das asserções é o do revisor.

**Resultado.** Mesmos dois arquivos: **168 passed**. Suíte completa: **1187 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros. Nenhum teste existente foi alterado ou afrouxado.


## Revalidação independente — 8064a14 — 2026-10-17

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

A-22 a A-24 e probes anteriores verdes. R04 encerrado: texto bruto e erro retornam à linha correta, com escape e sem efeitos persistidos. R03 permanece parcialmente aberto: após fechamento entre leitura e serviço, a resposta 409 ainda contém campos editáveis. R05 novo: identificador inválido no tratamento do formulário pode causar HTTP 500.

Suíte completa: **1187 passed em 129,30 s**. Probes independentes: **22 passed, 4 failed em 14,69 s**; os 22 anteriores passam, quatro adicionais reproduzem as pendências R03/R05. Verificações estáticas e CI verdes. Evidências, reprodução e limites no [parecer consolidado](../E03-08/review.md), seção deste SHA. Nenhuma alteração de produção ou testes versionados pelo revisor.


## Correção E03-R03 (complemento) e E03-R05 — implementador (aguardando nova revisão independente)

Critérios: A-25, A-26 e A-27; complemento da E03-02 (409 sempre só de leitura). Nada aqui é aprovação.

**Red.** Testes escritos antes do código, sobre `8064a14`: `uv run pytest tests/tecnicos/test_rodadas_estoque.py tests/tecnicos/test_condicoes_congeladas_matriz.py -q` deu **10 failed, 180 passed**.
- A-25 e o probe `test_fechamento_entre_leitura_e_servico_devolve_estoque_somente_leitura` (inclusão e alteração): 409 correto, mas `name="limite"`, botões e etapa antiga na página.
- A-27 e o probe `test_id_invalido_no_formulario_nao_provoca_500`: HTTP 500 por `ValueError` para `²` e para 4301 algarismos (`Exceeds the limit (4300 digits)`).
- Já passavam no Red, por já existir o comportamento: A-26 (guarda de regressão das rotas de mínimo, múltiplo e incremento, como a spec previu), os ids `-1`, `0`, vazio e `99999999999999999999` do A-27 (o Django trata o valor fora da faixa do `bigint` no filtro) e o "Produto inválido." de um id inexistente dentro da faixa. O `max_value` do campo foi acrescentado mesmo assim, como a spec exige.

**Green.** Em `apps/rodadas/views.py`:
- `_pagina_do_estoque` calcula `editavel = status != 409 and rodada.etapa == INTERESSE`; a mensagem única sai uma vez só no aviso do topo.
- `_pagina_congelada` relê a rodada do banco (sem trava) depois de o serviço recusar e monta a página só de leitura com a etapa gravada; usada no 409 direto e no `CondicoesCongeladas` do serviço, na inclusão e na alteração.
- `_id` foi removido: a linha da inclusão recusada só é identificada por `form.cleaned_data["produto"]` e só quando `produto` não está em `form.errors`; `produto` inválido vai para o aviso do topo, sem linha. Não captura `ValueError` nem muda o limite de conversão do Python.
- `apps/rodadas/forms.py`: `produto` com `max_value=9223372036854775807`.
A validação transacional do serviço não mudou.

**Resultado.** Mesmos dois arquivos: todos passando. Suíte completa: **1209 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros. Nos probes literais do revisor mudaram só a fixture (`admin` → `admin_client`), as anotações de tipo e a leitura de `exc_info` por `getattr` (exigência do `mypy --strict`); as asserções são as dele. Nenhum teste existente foi alterado ou afrouxado.
