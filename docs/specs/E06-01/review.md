# E06-01 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E01-03, E03-02, E03-07 e E05-04.

## Arquivos

- `apps/rodadas/models.py`: `PrazoDoFechamento` (só inserção) e `OrigemDoPrazo`; migrações `0007_prazo_do_fechamento` e `0008_restricoes_do_prazo` (trigger de só inserção, `UNIQUE` parcial do `inicio` por ciclo e `CHECK` de origem).
- `apps/rodadas/fechamento.py` (novo): `iniciar_fechamento`, `prazo_do_fechamento`, `TransicaoRecusada`, `HORAS_DO_FECHAMENTO`.
- `tests/apoio/trava.py` (novo): `segurando` e `esperando` para os testes de trava, com espera de prazo e falha por asserção.
- Testes: `tests/tecnicos/test_rodadas_fechamento_inicio.py` (A-1 a A-10), `tests/tecnicos/test_rodadas_fechamento_concorrencia.py` (A-12 a A-14) e os ajustes de A-11 em `tests/apoio/ciclos.py` e `tests/tecnicos/test_rodadas_ciclos.py`.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** o modelo sem restrições nem trigger (migração `0007`), `TransicaoRecusada` e as duas funções devolvendo `None`.

**Red, critérios funcionais.** `uv run pytest tests/tecnicos/test_rodadas_fechamento_inicio.py -q`: **15 failed, 1 passed**, por asserção (`assert 'interesse' == Etapa.FECHAMENTO`, `DID NOT RAISE TransicaoRecusada/PermissionDenied/CondicoesCongeladas`, `prazo_do_fechamento` devolvendo `None`). Passou já no Red o A-4 (nada inicia sozinho), porque depende de ausência.

**Red, concorrência (A-12 a A-14), antes do código.** `uv run pytest tests/tecnicos/test_rodadas_fechamento_concorrencia.py -q`: **4 failed em 47,7 s**, contra o andaime (que não trava nada nem recusa): a segunda operação não esperou (`AssertionError('a outra conexão não ficou esperando pela trava')`) e `AssertionError: [None, None]` no A-14 (nenhuma das duas recusada). A trava usada pelo Green é a que `registrar_condicoes_do_ciclo` já tem (E03-07); não escrevi trava nova.

**Green.** Os dois arquivos: **20 passed**. Suíte completa: **1686 passed** (eram 1666). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- `iniciar_fechamento` exige o administrador; chama `registrar_condicoes_do_ciclo` (que trava fornecedor, rodada, produtos e estoques) e traduz `CondicoesCongeladas` em `TransicaoRecusada`; relê a rodada com o fornecedor **depois** da trava e confere `progresso_da_rodada(...).atingido`; grava `fechamento`, o prazo (`somar_horas(ciclo.iniciado_em, 24)`) e a auditoria `rodada.iniciar_fechamento`. Qualquer recusa desfaz a transação inteira.
- `prazo_do_fechamento` lê a etapa do banco (não confia no objeto recebido) e devolve o maior `termina_em` do ciclo vigente.

## A-11: ajustes nos testes da E03-07

Autorizados pela spec: `simular_inicio_do_fechamento` (`tests/apoio/ciclos.py`) agora chama `iniciar_fechamento` com o administrador; `_cenario()` ganhou uma parcela de 30 de `Q` (R$ 300,00).

**Fora da lista autorizada, com decisão do responsável nesta sessão ("só acrescentar preparação"):** dois outros testes de `test_rodadas_ciclos.py` deixavam de passar porque o serviço real recusa o início sem mínimo atingido. Só acrescentei preparação; nenhuma asserção mudou:
- `test_rodada_sem_produtos_registra_ciclo_sem_condicoes`: o mínimo passa a R$ 0,00 (o banco recusa zero, então a restrição `fornecedor_minimo_positivo` sai dentro do teste e volta com o rollback);
- `test_ciclos_de_outra_rodada_do_mesmo_fornecedor_tem_numeracao_propria`: `Q` entra no estoque da rodada nova, para o mínimo ser atingido.
O revisor deve conferir o diff desses dois arquivos.

## Decisões técnicas

- **A-7, mínimo zero.** O banco não aceita mínimo zero; o teste tira a restrição só na própria transação (rollback desfaz), para exercitar o critério como escrito.
- **Mínimo lido sob trava.** A conferência usa a rodada relida com o fornecedor (e não o objeto do chamador, que pode estar defasado).
- **Instante do prazo = instante do ciclo** (`ciclo.iniciado_em`), como a spec manda.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_inicio_registra_ciclo_prazo_de_24_horas_e_auditoria` (`acceptance`, cenário 5) |
| A-2 | `test_minimo_nao_conta_pendentes` (`acceptance`, cenário 104) |
| A-3 | `test_so_conta_a_quantidade_em_caixas_completas` |
| A-4 | `test_atingir_o_minimo_nao_inicia_nada_sozinho` (`acceptance`, cenário 4) |
| A-5 | `test_so_o_administrador_inicia` |
| A-6 | `test_rodada_ja_em_fechamento_nao_inicia_de_novo`, `test_rodada_em_pagamento_nao_inicia`, `test_sem_rodada_ativa_nao_inicia` |
| A-7 | `test_exatamente_no_minimo_e_aceito`, `test_minimo_zero_sem_reservas_e_aceito` |
| A-8 | `test_prazo_vale_24_horas_corridas_mesmo_de_madrugada` |
| A-9 | `test_condicoes_congeladas_mas_o_preco_continua_editavel` |
| A-10 | `test_prazo_so_aceita_insercao`, `test_uma_so_linha_de_inicio_por_ciclo` |
| A-11 | `tests/tecnicos/test_rodadas_ciclos.py` (17 passed) |
| A-12 | `test_reducao_que_confirma_antes_derruba_o_minimo`, `test_inicio_que_confirma_antes_aceita_a_reducao_no_fechamento` |
| A-13 | `test_alteracao_de_minimo_depois_do_inicio_e_recusada` |
| A-14 | `test_dois_inicios_simultaneos_so_um_confirma` |

## Limites da verificação

Serviços e Postgres reais, sem navegador. O aviso aos compradores (E06-02), o bloqueio das ações pelo prazo (E06-03), a prorrogação (E06-04), o encerramento (E06-05/06) e as telas (E06-07) são de outras fatias. Nenhuma mutação foi aplicada nesta fatia: o Red dos critérios de concorrência foi observado contra o andaime.
