# E07-06 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§8.3, 15), infraestrutura v1.7 (4.2, 4.3, 4.4), `spec.md` e `acceptance.md` da fatia, E07-01 e E07-03.

## Arquivos

- `apps/pagamentos/consulta.py`: `consultar_antes_de_decidir` e `ConsultaAoProvedorFalhou`.
- Testes: `tests/tecnicos/test_pagamentos_consulta.py` (A-1 a A-9) e, em `test_pagamentos_concorrencia.py`, A-10. Sem migração.

## Ciclo TDD

**Andaime (exceção técnica):** a exceção `ConsultaAoProvedorFalhou` (dados) e a função devolvendo lista vazia, sem consultar nada.

### Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pagamentos_consulta.py tests/tecnicos/test_pagamentos_concorrencia.py -q`: **9 failed, 8 passed**. Falhas por asserção: `assert [] == ['sim-1']`, `assert [] == ['sim-2', 'sim-3']`, `assert [] == ['busca', 'busca']`, `Failed: DID NOT RAISE ConsultaAoProvedorFalhou` (4) e, na concorrência, `a outra conexão não ficou esperando pela trava`. Os 8 que passaram são os testes de concorrência das fatias anteriores e o A-7.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_pagamento_aprovado_sem_aviso_e_identificado` (`acceptance`) | falhou (`assert [] == ['sim-1']`) |
| A-2 | `test_dois_pagamentos_aprovados_da_mesma_referencia` | falhou |
| A-3 | `test_busca_atrasada_e_corrigida_pela_reconsulta` | falhou |
| A-4 | `test_provedor_fora_do_ar_bloqueia` | falhou (`DID NOT RAISE`) |
| A-5 | `test_falha_numa_reconsulta_bloqueia_mas_mantem_o_que_foi_sincronizado` | falhou (`DID NOT RAISE`) |
| A-6 | `test_pagamento_registrado_que_o_provedor_nao_conhece_bloqueia` | falhou (`DID NOT RAISE`) |
| A-7 | `test_referencia_sem_pagamento_devolve_lista_vazia` | **passou no Red**: o andaime já devolve lista vazia; é o resultado esperado e o teste protege o caso contra regressão |
| A-8 | `test_consultas_repetidas_so_acrescentam_historico` | falhou |
| A-9 | `test_a_falha_nao_revela_valor_descricao_nem_dados_para_pagar` | falhou (`DID NOT RAISE`) |
| A-10 | `test_consulta_antes_de_decidir_durante_o_processamento_do_aviso` | falhou por asserção (espera da outra conexão: o andaime não toma a trava da linha) |

### Green

Os dois arquivos: **17 passed**. Suíte completa: **1902 passed** (eram 1892). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` (com as configurações de teste) sem erros.

## Decisões técnicas (derivadas da spec)

- Cada resposta da busca e cada reconsulta é sincronizada em `transaction.atomic()` próprio (savepoint quando há transação aberta); o que já foi sincronizado fica gravado se uma consulta posterior falhar (A-5).
- A reconsulta cobre os registros do mesmo provedor e da mesma referência que não vieram na busca, em ordem de `criado_no_provedor_em` e `id_externo`.
- Os três erros do provedor (`ProvedorIndisponivel`, `RecusaDoProvedor`, `PagamentoNaoEncontrado`) viram `ConsultaAoProvedorFalhou` com motivo `indisponivel`, `recusa` e `nao_encontrado`, com a exceção original encadeada; o log leva só a referência e o motivo.
- O serviço não segura travas durante a consulta (quem chama o usa antes de abrir a transação da decisão); a trava da linha só existe dentro de cada `sincronizar_pagamento`.

## Decisões que devem chamar o serviço

A tabela da spec (E08: aprovação do resultado da cobrança; E10: devolução; E11: apuração final; E12: cancelamento com reembolso; E13: pedido formal e repasse) fica registrada para as etapas seguintes; nenhuma decisão existe ainda, então nada nesta fatia a chama.

## Limites da verificação

Postgres real; o simulador é o único provedor. O bloqueio na tela e as mensagens ao administrador, e os testes de "nada é decidido quando o serviço levanta", são de cada etapa que chamar o serviço. Nenhuma mutação aplicada nesta fatia.
