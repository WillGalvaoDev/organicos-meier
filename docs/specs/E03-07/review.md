# E03-07 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `8257f66` (2026-10-17). E03 global: **APROVADO**. Histórico preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** `Ciclo` e `CondicaoDoProdutoNoCiclo` só com campos
(`RegistroSoInsercao`, sem restrições nem triggers), `registrar_condicoes_do_ciclo` que devolve um
`Ciclo` vazio, `ciclo_vigente` que devolve `None`, auxiliares de teste
`tests/apoio/ciclos.py` (`simular_inicio_do_fechamento`, `simular_volta_para_interesse`) e
migração `0005_ciclos`. Suíte antes do Red: 983 passando.

**Red** (`uv run pytest tests/tecnicos/test_rodadas_ciclos*.py tests/tecnicos/test_condicoes_congeladas_matriz.py`):
**18 falhas, 36 passando**. Falhas: `DID NOT RAISE IntegrityError` (restrições e triggers),
`DID NOT RAISE CondicoesCongeladas` e `TransactionManagementError`, `assert None == 1`,
`assert None is not None`, `Ciclo.DoesNotExist`, `ValueError: Model instances passed to related
filters must be saved` (o `Ciclo()` do andaime não foi salvo) e concorrência sem efeito. Nota de
honestidade: as falhas por `ValueError` e `DoesNotExist` vêm do objeto vazio do andaime, não de uma
asserção sobre o resultado final.

Os 36 que já passavam: 35 são a **matriz consolidada A-9/A-10 (T-23, cenário 72)**, que por
desenho verifica o congelamento já implementado nas E03-02 a E03-06 (regressão consolidada; seu
valor é impedir que uma fatia futura reabra uma condição), mais A-3 (as condições voltam a ser
editáveis na volta para interesse, comportamento já existente).

**Green:** `apps/rodadas/ciclos.py` (`registrar_condicoes_do_ciclo`, `ciclo_vigente`), restrições
`ciclo_numero_unico`, `ciclo_numero_positivo`, `condicao_produto_unica` e a proteção de só
inserção por trigger (`instalar_protecao_so_insercao`) nas duas tabelas, migração
`0006_restricoes_dos_ciclos`. Resultado: arquivos da fatia 54 passando; suíte completa **1037
passando**; `ruff check`, `ruff format`, `mypy --strict`, `makemigrations --check` limpos.

**Ajuste depois do Green:** acrescentei ao teste A-1 a asserção `autor_tipo == "sistema"` (a
transição é do sistema); passou de imediato porque o código já usa `SISTEMA`.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_rodadas_ciclos.py::test_inicio_do_fechamento_registra_as_condicoes_vigentes` |
| A-2 (cenário 73) | `::test_cenario_73_ciclos_anteriores_nao_mudam` |
| A-3 (cenário 73) | `::test_condicoes_voltam_a_ser_editaveis_na_volta_para_interesse` |
| A-4 | `::test_ciclo_e_condicoes_so_aceitam_insercao_no_orm`, `::test_banco_recusa_alterar_ou_apagar_ciclo`, `::test_banco_recusa_alterar_ou_apagar_condicao` |
| A-5 | `::test_registro_fora_de_interesse_e_recusado`, `::test_segunda_chamada_no_mesmo_ciclo_e_recusada`, `::test_registro_de_rodada_antiga_e_recusado` |
| A-6 | `::test_registro_fora_de_transacao_falha` (`transaction=True`) |
| A-7 | `::test_ciclo_vigente` |
| A-8 | `::test_banco_recusa_segundo_ciclo_com_o_mesmo_numero`, `::test_banco_recusa_numero_zero_e_condicao_repetida` |
| A-9 (T-23, cenário 72) | `test_condicoes_congeladas_matriz.py::test_nenhuma_condicao_muda_fora_de_interesse` (5 condições × 6 situações; rota com e sem `HX-Request`, e serviço) |
| A-10 | `::test_preco_muda_nas_quatro_etapas_ativas` |
| A-11 | `test_rodadas_ciclos_concorrencia.py::test_fechamento_iniciado_primeiro_registra_o_minimo_anterior`, `::test_dois_inicios_simultaneos_geram_um_ciclo` |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- Auditoria `ciclo.registrar_condicoes` com autor `SISTEMA` (a transição não tem usuário na
  assinatura da especificação, `registrar_condicoes_do_ciclo(rodada)`).
- `registrar_condicoes_do_ciclo` usa `travar_condicoes` (que exige transação aberta e confere que
  a rodada travada é a recebida), trava os produtos da rodada por id e depois os estoques por
  `produto_id`, e relê o fornecedor sob a trava para gravar o mínimo vigente.
- O número do ciclo é o maior número da rodada mais 1, seguro pela trava da rodada; o
  `UNIQUE (rodada, numero)` é a defesa final.
- As condições são inseridas com `bulk_create` (a base `RegistroSoInsercao` só recusa alterar e
  apagar).
- Os auxiliares de `tests/apoio/ciclos.py` seguem o contrato da E06: travam fornecedor e rodada,
  chamam o serviço e gravam a etapa na mesma transação.

## Limitações de verificação

- A transição real para `fechamento` e a volta para `interesse` são da E06; os testes usam os
  auxiliares. A E06 deve passar pelos mesmos testes.
- Pedidos, caixas e cobranças vinculados ao ciclo ficam para E06 e E08.
- A-11 detecta a espera com `pg_stat_activity.wait_event_type = 'Lock'` no banco inteiro.
- A "margem" e a "aptidão para apuração" estão cobertas pela linha `pagamento`, como na
  especificação.

## Revisão independente — 0ceb171 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

A-1 a A-11: registro de condições atuais, ciclos anteriores preservados, proteção ORM/SQL, numeração e concorrência cobertos e verdes. A matriz T-23 cobre cinco operações × seis situações, pelas rotas normal/HTMX e pelos serviços; preço permanece editável nas quatro etapas ativas. Transições reais continuam na E06.

Verificação comum: `uv run pytest -q` — **1058 passed em 147,85 s**; ruff check limpo; ruff format — 238 arquivos; mypy — 193 arquivos sem erros; checks Django e migrações sem pendências. Os probes adicionais de fronteira terminaram em **8 failed, 8 passed em 4,36 s**, reproduzindo E03-R01. Não houve correção de produção ou testes pelo revisor.

Comandos completos, achados, reprodução, limites e parecer global estão em [E03-08/review.md](../E03-08/review.md), na seção de revisão independente deste SHA. Os relatos Red/Green anteriores foram conferidos com o diff e a cobertura; a execução Green é independente, a cronologia Red é evidência documentada pelo implementador.


## Revalidação independente — 2e7bbcc — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

Aprovação mantida; implementação e critérios inalterados, matriz de congelamento existente e regressão completas verdes. R03 trata a combinação adicional de fase congelada e valor excedente no mínimo.

Evidência comum: suíte completa **1104 passed em 137,20 s**; script original independente **16 passed em 7,70 s**; probes complementares **6 failed em 2,23 s** (R03/R04); lint, formatação, tipos, migrações e checks Django sem erros. Detalhes, reprodução e limites no [parecer consolidado](../E03-08/review.md), seção deste SHA. Nenhuma alteração de produção ou testes versionados pelo revisor.


## Correção E03-R03 — implementador (aguardando nova revisão independente)

Critérios: A-12 e A-13. Nada aqui é aprovação.

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

Matriz estendida A-12/A-13 verde: cinco operações, seis situações, classes de valor, HTTP normal/HTMX e serviços. O teste adicional de mudança de etapa entre leitura e serviço encontrou uma pendência de apresentação em E03-05, descrita em R03.

Suíte completa: **1187 passed em 129,30 s**. Probes independentes: **22 passed, 4 failed em 14,69 s**; os 22 anteriores passam, quatro adicionais reproduzem as pendências R03/R05. Verificações estáticas e CI verdes. Evidências, reprodução e limites no [parecer consolidado](../E03-08/review.md), seção deste SHA. Nenhuma alteração de produção ou testes versionados pelo revisor.


## Revalidação independente — 8257f66 — 2026-10-17

**Parecer: APROVADO. E03 global: APROVADO.**

Aprovação da fatia mantida. Conferidos o escopo do diff, os critérios aplicáveis e as regressões na suíte completa; as correções restantes da E03-05 não introduzem mudanças de regra de negócio nesta fatia.

Suíte completa: **1209 passed em 101,35 s**. Reexecução dos três scripts independentes preservados no histórico: **26 passed em 4,01 s**, incluindo as quatro falhas anteriores. Verificações estáticas, Django e CI verdes. Comandos, fechamento dos achados e limitações no [parecer consolidado](../E03-08/review.md), seção deste SHA.
