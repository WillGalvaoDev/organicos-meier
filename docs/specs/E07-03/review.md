# E07-03 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§8.3, 14, 15, cenários 17 e 37), infraestrutura v1.7 (4.1, 4.2, 5), `spec.md` e `acceptance.md` da fatia, E01-04, E01-05, E07-01 e E07-02.

## Arquivos

- `apps/pagamentos/models.py`: `PagamentoNoProvedor`, `ConsultaDoPagamento` (`RegistroSoInsercao`), `OrigemDaConsulta`, `DivergenciaDaConsulta`; `migrations/0001_initial.py` com a trigger de só inserção em `pagamentos_consultadopagamento`.
- `apps/pagamentos/sincronizacao.py`: `sincronizar_pagamento`, `Sincronizacao`, `ORIGENS_DA_CONSULTA`. `apps/pagamentos/sinais.py`: `situacao_do_pagamento_mudou`.
- Testes: `test_pagamentos_sincronizacao.py` (A-1 a A-11, A-15), `test_pagamentos_concorrencia.py` (A-13, A-14, mais o A-15 da E07-01) e `test_pagamentos_fronteiras.py` (A-12).

## Ciclo TDD

**Andaime (exceção técnica):** os dois modelos com a migração e as restrições, o sinal, e `sincronizar_pagamento` devolvendo um resultado vazio, sem gravar nada, sem validar e sem enviar o sinal.

### Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pagamentos_sincronizacao.py tests/tecnicos/test_pagamentos_concorrencia.py tests/tecnicos/test_pagamentos_fronteiras.py -q`: **17 failed, 5 passed**. Uma primeira leitura teve falhas por `DoesNotExist` e por desempacotamento de listas vazias; as preparações foram tornadas assertivas (`assert len(...) == 1`) antes do Green, e o Red abaixo é o da segunda leitura, anterior ao código de produção. Falhas por asserção: `esperava 1 registro, há 0` (11), `assert 0 == 1`, `assert None`, `DID NOT RAISE TransactionManagementError`, `DID NOT RAISE RuntimeError`.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_a_primeira_consulta_cria_o_registro` | falhou (nenhum registro) |
| A-2 | `test_a_aprovacao_e_aplicada_com_os_quatro_instantes` | falhou |
| A-3 | `test_consultas_repetidas_nao_repetem_efeitos` (`acceptance`) | falhou |
| A-4 | `test_o_primeiro_registro_ja_aprovado` | falhou |
| A-5 | `test_leitura_atrasada_nao_volta_atras` | falhou |
| A-6 | `test_cancelado_pode_virar_aprovado` | falhou |
| A-7 | `test_resposta_divergente_nao_altera_a_identidade` (4 campos) | falharam |
| A-8 | `test_o_historico_so_aceita_insercao` | falhou (sem linha de histórico) |
| A-9 | `test_restricoes_do_banco` | falhou (sem registro de partida) |
| A-10 | `test_exige_transacao_e_origem_valida` | falhou (`DID NOT RAISE TransactionManagementError`) |
| A-11 | `test_receptor_que_falha_desfaz_a_sincronizacao` | falhou (`DID NOT RAISE RuntimeError`) |
| A-12 | `test_so_a_sincronizacao_escreve_nos_registros_de_pagamento` (`acceptance`) | falhou por asserção: `sincronizacao.py` ainda não escrevia nos modelos. `test_nenhuma_rota_comando_ou_admin_registra_pagamento` **passou no Red**: é estrutura que já valia (sem admin, sem rota nem comando de pagamentos) e protege contra regressão |
| A-13 | `test_cinco_sincronizacoes_do_mesmo_pagamento_aprovado` | falhou por asserção: `a outra conexão não ficou esperando pela trava` (o andaime não trava a linha) |
| A-14 | `test_primeira_consulta_concorrente_cria_um_registro_so` | falhou, mesma asserção |
| A-15 | `test_os_registros_nao_guardam_dados_do_pagador` | **passou no Red**: o teste confere os nomes dos campos (já definidos no andaime) e o log; o log do Green foi conferido pelo mesmo teste depois do código |

### Green

Os três arquivos: **22 passed**. Suíte completa: **1862 passed** (eram 1843). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Decisões técnicas (derivadas da spec)

- **Criação e histórico.** O registro nasce já com a primeira resposta (situação, aprovação, `primeiro_aviso_em`). Quem decide que a sincronização é a criadora é a ausência de histórico depois de travar a linha: a linha de outra transação só fica visível junto com o histórico dela. A criação conta como `aplicada`; só vira mudança (auditoria e sinal, com `anterior` nulo) quando já nasce em situação terminal.
- **Autonomia da transação.** O serviço abre `transaction.atomic()` (savepoint) dentro da transação exigida, de modo que uma exceção do receptor do sinal desfaz tudo mesmo que quem chamou a capture e continue na mesma transação (o teste A-11 confere isso sem sair da transação).
- **`aprovado_no_provedor_em`** é preenchido na criação ou na primeira resposta que o traz com a situação aplicável (a mudança ou a mesma situação); uma resposta atrasada (`pendente` sobre terminal) não preenche nem muda nada.
- **Divergência de aprovação** só quando o registro já tem horário e a resposta traz outro diferente; resposta sem horário não é divergência (é leitura atrasada).
- **`ultima_consulta_em`** nunca recua (`max`), para respostas fora de ordem.
- **Auditoria:** `aprovado_em` em ISO 8601 UTC; `anterior` e `atual` como texto. Log de divergência em nível `warning`, só com o identificador e o nome do campo.

## Cenário 37 (A-12): módulos de `apps/` que mencionam os modelos

Fora das migrações, só `apps/pagamentos/models.py` e `apps/pagamentos/sincronizacao.py` os mencionam; não há módulo só de leitura nesta fatia. O teste varre todo `apps/` e recusa métodos de escrita em qualquer módulo, além desses dois, que mencione os modelos. Também confere: `django.contrib.admin` fora do `INSTALLED_APPS`, as rotas de `apps.pagamentos` e `apps.simulador_pagamentos` limitadas a `pagamentos_avisos` (hoje nenhuma) e nenhum `management/` nesses apps.

## Limites da verificação

Postgres real; sem rede e sem worker como processo. Quem chama a sincronização (E07-04, E07-05, E07-06) e a quitação do pedido (E08) são de outras fatias. A varredura do cenário 37 é textual (nomes de métodos de escrita), não uma análise de fluxo. Nenhuma mutação aplicada nesta fatia.
