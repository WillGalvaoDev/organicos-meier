# E11-05 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Comandos com o arquivo de teste inteiro, sem `-k`: `uv run pytest tests/tecnicos/test_apuracao_retorno.py`.

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-17 (apoio `limites=(11, 12)`) | `67e5bd2` | **Red: 15 failed, 2 passed.** A rodada continua em `pagamento`; parcelas `em_pedido`/`pendente` em vez de `ativa`; nenhum `Reembolso` integral; sem aviso; `DID NOT RAISE RuntimeError` (A-10); `InteressesBloqueados`/`CondicoesCongeladas` nos A-11 a A-14; `_restaurar_as_reservas_dos_pagantes` inexistente (A-15). **A-6 e A-16 passaram** (regressões: nada é apurado no livro; os motivos da E06 continuam exigindo o fechamento encerrado) |
| `voltar_para_interesse` aceita `pagamentos_insuficientes` a partir de `pagamento` (e só com ele); `_restaurar_as_reservas_dos_pagantes`, `_conferir_o_estoque`, `_devolver_integralmente`, `_avisar_o_retorno`, auditoria `retorno` | commit da fatia | **17 passed** |

## Decisões técnicas

- Etapa diferente do motivo gera a recusa `fora_de_pagamento` (mensagem própria); os motivos da E06 mantêm `fora_de_fechamento_encerrado`.
- A conferência do estoque usa `total_reservado` depois da restauração e antes do retorno (que atende a fila), com o estoque já travado pela E11-01.

## Ponto para o especificador (A-3 não é atingível como escrito)

O A-3 espera a parcela de A em P1, depois da apuração, `ativa` com reservado 6 e **pendente 2**. Mas a regra 4 da própria fatia manda `voltar_para_interesse` atender a fila (`alocar_pendentes`), e o inadimplente B libera 5 unidades de P1: o pendente de A, o mais antigo, recebe as 2 (R-5). O resultado, com ou sem limite, é reservado 8 e pendente 0. Implementei as regras e o teste afirma os dois momentos: (1) a restauração, sozinha, deixa a reserva igual à parte congelada (6) com a pendência intacta (2), que é o que o A-3 quer provar do E08-02; (2) o retorno inteiro, ativa com 8 e 0. Peço que o A-3 seja corrigido (por exemplo, afirmar só a restauração).

## Riscos remanescentes e limites de verificação

- **Conta suspensa ou removida (A-17):** a parcela `em_pedido` dela fica `em_pedido`, ainda contada em `total_reservado`, depois de a rodada voltar ao interesse. A spec manda só não restaurar. Um interesse de conta suspensa segurando estoque numa rodada em interesse parece indesejável; não alterei o comportamento. Decisão do especificador.

## Defeito achado depois pela E11-08 (corrigido)

A devolução integral de mais de um pedido pago na mesma apuração tinha o mesmo defeito da E11-04 (`OrdemDeTravasViolada`). Teste: `test_dois_pagantes_recebem_a_devolucao_integral_na_mesma_apuracao` (Red `3066566`). A correção é a mesma: o conjunto das contas de todos os pagantes é travado antes da primeira devolução.


## Parecer independente — agente 3 — 2026-10-31

Base auditada: `1a36495`, branch `e11-implementacao`, comparada à base E10 integrada `1b9bf07`. Leitura dos documentos-base (funcional v1.7 e infraestrutura v1.8), spec/acceptance das oito fatias, implementação, testes e registros de TDD. O conteúdo anterior deste arquivo foi preservado integralmente. Evidências e reproduções completas no [parecer consolidado da E11-08](../E11-08/review.md).

**REPROVADO — R01 e R02 (importantes), R04 (bloqueador).** A-1 a A-17 confrontados com código/testes, inclusive mais de um pagante. O fluxo nominal preserva estoque, gera obrigações integrais e permite novo ciclo, mas as provas independentes abaixo falharam.

**R01:** o filtro genérico `parcela_removida` em `apps/pedidos/apuracao.py:409` perde a reserva paga quando o comprador removeu apenas a sobra pendente durante pagamento. Prova: 6 congeladas + 2 pendentes; remove 2; retorno deixa `removida/0` em vez de `ativa/6`. Ver E11-04.

**R02 — importante — estoque continua ocupado pela conta suspensa após o retorno.** Referências: funcional §2 (interesses do suspenso removidos), §8.2 (retorno ao interesse), E11-05 regra 2 e E05-07. O ramo de conta suspensa em `_restaurar_as_reservas_dos_pagantes` só pula a parcela, deixando `em_pedido` e sua reserva antiga. `total_reservado` continua incluindo essa situação. Prova: AP-insuficiente, limites 11/12, A paga e é suspenso antes da apuração; no retorno P1 ainda tem **6 reservadas** de A, em vez de liberar essa capacidade. O pedido congelado pode e deve ficar intacto; ele não exige uma reserva operacional sem uso no novo ciclo. A limitação já declarada pelo implementador não é uma aprovação. Corrigir a destinação da reserva no retorno e cobrir suspensão/remoção, sem restaurar interesses de conta impedida.

O resultado do A-3 questionado pelo implementador está correto pela regra 4 e R-5: imediatamente após restaurar são 6 reservadas e 2 pendentes; depois de atender a fila, com o estoque liberado por B, são 8 e 0. O teste separa esses dois momentos. Não considero isso mudança comercial nem defeito de produção; o texto do critério precisa refletir a composição das regras.

**R04 — bloqueador — deadlock entre retorno e registro de tarifa tardia.** Referências: AGENTS.md §6 (concorrência e recuperação financeira), E11-01 ordem de travas, E11-05 atomicidade, regra financeira única da E09. A apuração toma `FOR NO KEY UPDATE`, mas em `apps/rodadas/fechamento.py:371`/`:372` o retorno reutilizado promove fornecedor/rodada a `FOR UPDATE`. Depois espera contas financeiras em `apps/pedidos/apuracao.py:621`/`:486`. A tarefa `registrar_tarifas_pendentes_agora` pode já deter a conta de receita/contas financeiras e tentar confirmar uma despesa com FK para a rodada. O commit pede `FOR KEY SHARE` na rodada: uma transação espera a outra.

Prova com duas conexões reais, sem retirar validações: consulta da apuração termina; a tarefa registra a tarifa e pausa antes do commit; a apuração retorna para interesse e começa a devolução; a tarefa tenta confirmar. PostgreSQL: **`OperationalError: deadlock detected`**, contexto `rodadas_rodada ... FOR KEY SHARE`. Reproduzido duas vezes após ajustar a chamada do helper na prova. Em ambas a tarefa financeira foi a vítima; o banco pode escolher outra vítima. As pausas só ordenam uma execução possível. Corrigir a ordem/compatibilidade de travas em todo o ramo, não apenas em `_travar`; acrescentar regressão contra a tarifa tardia. Não é necessário alterar regra de negócio.

TDD: `67e5bd2 → 47a4689` e correção de múltiplos pagantes `3066566 → aae9149`, registros conferidos; os cenários novos deste parecer não estavam cobertos.

## Correções R01, R02 e R04 — agente 2 — 2026-11-01

Comando: `uv run pytest tests/tecnicos/test_apuracao_retorno.py` (arquivo inteiro, sem `-k`).

| Achado | Testes (commit) | Red | Correção (commit) |
|---|---|---|---|
| R04 (primeiro) | `6a19f6d` A-22, A-23 | **2 failed.** A-22: `OperationalError: deadlock detected` com `FOR KEY SHARE` em `rodadas_rodada`; A-23: a inserção com chave para a rodada esperou o fim do retorno (trava promovida) | `0ac4ba0`: `travar_condicoes`, `travar_rodada_para_interesses`, `travar_estoque`, `travar_parcelas` e `voltar_para_interesse` travam com `FOR NO KEY UPDATE`. 20 passed |
| R01 | `be1b362` A-18 | **1 failed** (`('removida', 0) != ('ativa', 6)`) | `ee1a720`: só a conta impede a restauração da reserva |
| R02 | `b3949f7` A-19, A-21 | **2 failed** (`{'em_pedido'} != {'removida'}`; auditoria sem `removidas_por_conta_impedida`). **A-20 passou** (regressão: a reserva liberada por B bastava para o pendente de C; o critério vale mesmo assim) | `ee1a720`: `_remover_as_parcelas_das_contas_impedidas` antes da restauração, da conferência do estoque e da fila; o aviso `retorno_para_interesse` só aos pagantes com conta ativa |

**Decisões técnicas.**
- **R04, forma (b):** as funções de trava de interesse passam a usar `FOR NO KEY UPDATE` em todo o sistema (a exclusão mútua continua, porque ele conflita consigo mesmo e com `FOR UPDATE`). O teste existente `test_travar_estoque_exige_transacao_e_trava_a_linha` (E03) afirmava o texto "FOR UPDATE" no SQL; passou a afirmar "FOR NO KEY UPDATE" nas duas tabelas. É consequência direta do caminho (b), e a asserção de que a linha é travada continua.
- **R02, auditoria:** a chave `retorno.nao_restauradas` deu lugar a `retorno.removidas_por_conta_impedida` (comprador, parcela, motivo, reservada e pendente). O E11-05 A-17 foi substituído pelo A-19.
- **A-3:** o teste já afirmava os dois momentos; acrescentei a sequência no primeiro.
- **A-24 (regressão):** os arquivos de concorrência de interesses, moderação, pedidos, rodadas, catálogo e a fila de ponta a ponta passaram (suíte completa, abaixo).
- Os commits de R01 e R02 ficaram juntos (`ee1a720`) porque as duas correções mexem nas mesmas funções do retorno; os testes de cada um estão em commits separados.

Provas do parecer `test_remover_sobra_nao_remove_reserva_paga_no_retorno`, `test_suspenso_nao_prende_estoque_no_retorno` e `test_retorno_concorre_com_tarifa_sem_impasse` (esta é o A-22): passam como estão.

Mais dois testes existentes afirmavam o texto "FOR UPDATE" no SQL da leitura travada das parcelas (`test_catalogo_incremento.py::test_leitura_das_parcelas_e_travada_em_ordem_de_sequencia` e `test_interesses_consultas.py::test_leitura_com_trava_usa_for_update_ordenado_pela_sequencia`); passaram a afirmar "FOR NO KEY UPDATE", pela mesma consequência do R04 (a suíte completa os acusou). A ordem por `sequencia` e a trava da linha continuam afirmadas.


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `0af24ad`, branch `e11-implementacao`; correções desde o parecer `3aa8858` sobre `1a36495`. Requisitos corrigidos em `732b7bb`, código, testes e registros Red/Green confrontados. Conteúdo anterior preservado. Evidências e prova residual no [parecer consolidado E11-08](../E11-08/review.md).

**REPROVADO — R02 residual (importante). R01 e R04 encerrados.** As provas anteriores de reserva após remover sobra, liberação de estoque da conta suspensa e corrida com tarifa passam. Porém, se a suspensão já removeu todas as parcelas do pagante antes da apuração, `removidas_por_conta_impedida` fica vazio. O filtro de destinatários deduz desse conjunto vazio que o comprador não está impedido e emite `retorno_para_interesse`, contrariando o adendo R02 (aviso só a conta ativa). A lista de não restaurações também é descartada em `_retornar_para_interesse`. A reserva permanece corretamente zero; o residual é de registro e comunicação, não repetição do estoque preso. Prova e encaminhamento no consolidado.

## Correção do R02 residual — agente 2 — 2026-11-01

Comando: `uv run pytest tests/tecnicos/test_apuracao_retorno.py tests/tecnicos/test_apuracao_viavel.py tests/tecnicos/test_pedidos_apuracao_do_comprador.py` (arquivos inteiros, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes E11-05 A-25 a A-29, E11-04 A-19, E11-07 A-22 a A-25 | `f86423d` | **Red: 8 failed, 52 passed.** A-25/A-26: `KeyError: 'contas_impedidas'` (e A recebia o aviso); A-27 e A-29: `KeyError: 'contas_impedidas'`; A-28: `KeyError: 'contas_impedidas'`; tela A-22, A-23 e A-24: `assert True is False` (`interesses_reservados` verdadeiro). **Passaram de primeira (regressão prevista):** E11-04 A-19 e E11-07 A-25 |
| `_contas_impedidas_dos_pagantes` lê a situação uma só vez e alimenta a remoção, a não restauração, os destinatários do aviso e o registro `retorno.contas_impedidas`; `retorno.nao_restauradas` deixa de ser descartado; a tela lê `contas_impedidas` | `14f634e` | **60 passed** nos três arquivos |

**Decisões técnicas.**
- `_restaurar_as_reservas_dos_pagantes` recebe `impedidas` (opcional): a chamada direta do teste existente `test_parcela_com_pendente_volta_a_ativa_com_a_parte_congelada` continua sem alteração e deriva a situação pelo mesmo auxiliar. A apuração sempre passa o resultado único.
- Tela: sem a auditoria da apuração a página não afirma interesses reservados (spec E11-07).
- **Expectativa corrigida no meu teste novo A-28** (antes do Green): previ reserva 6 para a parcela de A, mas a pendência de 2 é atendida pela fila com o estoque liberado por B (R-5), então a parcela fica `ativa` com reserva 8 e pendência 0. O Red do A-28 foi o `KeyError: 'contas_impedidas'`, não essa expectativa.

Prova do parecer `test_conta_impedida_com_parcela_ja_removida` (aviso e tela): **2 passed** (arquivo temporário, removido).

**Verificação final:** `uv run pytest` = **2795 passed** (antes 2785; +10). `ruff check --no-cache` limpo, `ruff format --check` conforme (359 arquivos), `mypy .` sem erros (434 arquivos), `makemigrations --check` sem mudanças.
