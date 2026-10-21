# E08-04 — Revisão independente do agente 3 — 2026-10-21

**REPROVADO sobre `2714a6a2acaf88cc69e02345facf2a2403a66374`, branch `e08-implementacao`. E08 global: REPROVADO.**

Matriz examinada: **A-1 a A-17**, a partir de spec.md/acceptance.md e das fontes superiores, antes de avaliar o código. Os testes funcionais de quitação, destinos, fronteiras e duplicidade passam; a consulta explícita também passou no controle independente. R01 está na seleção de pedidos pela margem, que impede a decisão de receber o pagamento duplicado. O gate documental continua REPROVADO por R06: comprovar o ciclo específico das travas de A-16/A-17.

TDD declarado: **25 failed, 42 passed; tabela conferida, com ressalva de concorrência R06.** O revisor confere registro, testes e diffs; não presenciou a execução histórica. Reexecuções atuais não substituem evidência de Red anterior à implementação.

Verificações independentes: suíte completa **1 failed, 2129 passed in 292.98s**, sem exclusões; provas adicionais **5 failed, 2 passed in 17.36s**; lint, formatação (288 arquivos), tipos (338 arquivos) e verificação de migrações passaram. A falha versionada é a de rotas descrita em R05; as cinco falhas adicionais correspondem a R01, R02 (duas variantes), R03 e R04.

O [parecer consolidado](../E08-01/review.md) contém matriz das sete fatias, referências, classificação, resultados, código completo das provas, limites e encaminhamentos R01–R07. R04 requer decisão sobre pedido zero, e R06 requer evidência histórica ou tratamento autorizado; as perguntas foram encaminhadas durante a revisão. R07 está no registro central como M-3.

Somente documentação foi alterada pelo revisor, sem correção silenciosa de produção ou testes. Histórico do implementador preservado integralmente abaixo. Próximo gate: correções/comprovações e nova revisão independente.

---

## Registro anterior integralmente preservado

# E08-04 — Registro do implementador (2026-10-20)

Status: implementada; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia, as E08-02 e E08-03, a sincronização e o sinal da E07-03, a consulta antes de decidir (E07-06) e a interface de notificações (E04).

## Arquivos

- `apps/pedidos/models.py` (migrações `0005_destino` e `0006_restricoes_do_destino`): `DestinoDoPagamento`, só inserção (base `RegistroSoInsercao`, trigger no banco), com a unicidade de um `quita` por pedido e o `CHECK` de destino e motivo.
- `apps/pedidos/quitacao.py`: `decidir_destino`, `ler_referencia`, `MOTIVOS_DE_DEVOLUCAO` e o protocolo `PagamentoDoProvedor`.
- `apps/pedidos/receptores.py` e `apps/pedidos/apps.py`: o receptor do sinal `situacao_do_pagamento_mudou`, ligado no `ready()` depois das operações.
- `apps/pedidos/views.py` e `templates/pedidos/detalhe.html`: "Pago em <data> às <hora> (horário de Brasília)."
- `apps/pagamentos/consulta.py` (`situacao_registrada`, só leitura) e `apps/pagamentos/models.py` (`PAGAMENTO_REGISTRADO`): ver a decisão sobre o cenário 37.
- Testes: `tests/tecnicos/test_pedidos_quitacao.py` (A-1 a A-15) e, em `test_pedidos_concorrencia.py`, A-16 e A-17; apoio em `tests/apoio/pedidos.py`.

## Andaime (exceção técnica)

Antes do Red: o modelo `DestinoDoPagamento` sem base de só inserção, sem `CHECK` e sem trigger (migração `0005`), `ler_referencia` que devolve `None` e `decidir_destino` que devolve `None`, e nenhum receptor ligado. As restrições, a trigger e o receptor vieram no Green.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pedidos_quitacao.py tests/tecnicos/test_pedidos_concorrencia.py tests/tecnicos/test_pedidos_tentativas.py tests/tecnicos/test_pedidos_telas_comprador.py -q`: **25 failed, 42 passed**. Passaram: as 34 dos arquivos de tentativas, telas e as concorrências anteriores (regressão) e os oito casos negativos de `ler_referencia` (o andaime já devolve `None`: cobertura de regressão, sem Red).

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_aprovacao_no_prazo_quita_o_pedido` | `AssertionError: destinos de sim-1: 0` |
| A-2 | `test_fronteira_de_48_horas_da_margem` | `assert 'aguardando_pagamento' == 'pago'` |
| A-3 | `test_aviso_atrasado_nao_muda_o_horario_de_aprovacao` | `AssertionError: destinos …: 0` |
| A-4 | `test_aprovacao_depois_da_margem_gera_devolucao` | `AssertionError: destinos …: 0` |
| A-5 | `test_iniciado_no_prazo_ou_fora_dele` (2) | `AssertionError: destinos …: 0` |
| A-6 | `test_dois_pagamentos_aceitos_so_um_quita` (2 ordens) | `AssertionError: destinos …: 0` |
| A-7 | `test_sincronizar_de_novo_nao_repete_nada` | `AssertionError: destinos …: 0` |
| A-8 | `test_referencia_desconhecida_vai_para_devolucao_sem_pedido` (3) | `AssertionError: destinos …: 0` |
| A-9 | `test_aprovado_sem_horario_nao_gera_destino` | falhou na asserção da mensagem do log (o andaime não registra nada) |
| A-10 | `test_valor_diferente_do_pedido_vai_para_devolucao` | `AssertionError: destinos …: 0` |
| A-11 | `test_aprovado_antes_da_suspensao_quita_o_pedido_cancelado` | `AssertionError: destinos …: 0` |
| A-12 | `test_aprovado_na_suspensao_ou_depois_gera_devolucao` (2) | `AssertionError: destinos …: 0` |
| A-13 | `test_o_detalhe_mostra_o_pagamento_confirmado` | `AssertionError: destinos …: 0` (primeiro passo do teste) |
| A-14 | `test_falha_do_whatsapp_nao_desfaz_a_quitacao` | `assert 'aguardando_pagamento' == 'pago'` |
| A-15 | `test_falha_de_outro_receptor_desfaz_a_sincronizacao` | `assert 'aguardando_pagamento' == 'pago'` |
| `ler_referencia` | `test_ler_referencia` (os dois casos válidos) | `assert None == (12, 34)` e `assert None == (1, 1)` |
| modelo | `test_destino_so_aceita_insercao_e_e_coerente` | `DID NOT RAISE DatabaseError` |
| A-16 | `test_dois_pagamentos_ao_mesmo_tempo_um_quita_e_o_outro_duplica` | `assert 0 == 1` (nenhum destino) |
| A-17 | `test_aviso_e_tarefa_ao_mesmo_tempo_decidem_uma_vez` | `assert 0 == 1` (nenhum destino) |

(Os `AssertionError: destinos …: 0` vêm da função de apoio que confere o destino único de um pagamento antes das demais asserções.)

## Green e verificações

- Os quatro arquivos acima mais `test_pagamentos_fronteiras.py`: **60 passed** (E08-04 e E08-03). Conjunto `-k "pedidos or pagamentos or rodadas or interesses or permissoes or nucleo"`: **969 passed**.
- `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- A suíte completa roda ao final da milestone.

## Decisões técnicas

- **Cenário 37 (E07-01 A-12).** O teste estático existente acusa qualquer módulo que cite `PagamentoNoProvedor` ou `ConsultaDoPagamento` e contenha uma chamada de escrita (`.create(`, `.save(`…), mesmo quando a escrita é de outro modelo. Para não mexer no teste, os módulos de pedidos não citam essas classes: a chave estrangeira usa a constante `PAGAMENTO_REGISTRADO`, a leitura da situação passa por `situacao_registrada` (em `apps/pagamentos/consulta.py`), e `decidir_destino` recebe o pagamento por um `Protocol` só de leitura (`PagamentoDoProvedor`). Nada em `apps/pedidos` escreve em `PagamentoNoProvedor`. Sugestão de melhoria para o registro central: o teste poderia verificar a escrita nos próprios modelos de pagamento, e não a coocorrência de texto.
- **Objeto da auditoria `pagamento.destino`.** Como o serviço não recebe o modelo do pagamento, a entrada aponta para o `DestinoDoPagamento` recém-gravado; o `id_externo`, o pedido, o destino e o motivo estão em `alteracoes`.
- **Quem quita entre dois aceitos.** O primeiro a ser decidido; o resultado observável é o mesmo em qualquer ordem (testado nas duas).
- **`na_margem`** é `aprovado_no_provedor_em ≥ T0 + 24h`.
- **Aviso `estorno`** não é emitido aqui: é da E10, quando a devolução for processada.
- **Pedido cancelado e aprovação anterior ao cancelamento.** O pagamento quita, o `cancelado_em` e o motivo são limpos e a auditoria registra `cancelamento_sem_efeito`; a igualdade de horários vai para devolução.

## Limites da verificação

Postgres real, cliente HTTP do Django e threads reais; sem navegador, sem o worker como processo e sem rede. Nenhuma mutação aplicada.
