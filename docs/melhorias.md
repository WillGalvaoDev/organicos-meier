# Melhorias não impeditivas

Registro central das melhorias apontadas nas revisões que **não impedem** a aprovação de uma entrega. Criado por decisão do responsável pelo projeto em 2026-10-20: essas melhorias ficam aqui e são revistas no fim da implantação do projeto (antes do encerramento da fase 1, E16).

## Regras de uso

- **Quem registra.** O revisor (agente 3), ao classificar um achado como melhoria, acrescenta uma linha na tabela de pendentes, além de citá-lo no `review.md`. O especificador e o implementador também podem registrar o que perceberem e não for do escopo da tarefa.
- **O que entra.** Só achados classificados como melhoria: sem bloqueador, sem impacto em regra de negócio, dinheiro, permissão, integridade ou segurança. Se um achado afetar algum desses pontos, ele não é melhoria e segue o fluxo normal de correção (AGENTS.md §4).
- **O que não fazer.** Uma melhoria registrada não é implementada por conta própria dentro de outra tarefa. Ela só entra numa entrega quando o responsável decidir, na revisão final ou antes, se pedir.
- **Como fechar.** Quando uma melhoria for tratada, a linha passa para a tabela de encerradas, com a entrega e o commit. Uma melhoria descartada também passa para lá, com o motivo.

## Pendentes

| ID | Origem | Onde | Descrição | Sugestão |
|---|---|---|---|---|
| M-1 | E07-R08, revisão de `162e9e1` | `tests/apoio/concorrencia.py` (mensagem de `TempoEsgotado`) | A mensagem de `TempoEsgotado` com a limpeza concluída cita só `índice:nome` das operações pendentes. A correção E07-R06 (E01-05, item 7) pede também o alias e a fase, como já faz `LimpezaIncompleta`. A limpeza e a guarda estão corretas; falta só a informação de diagnóstico. | Usar `execucao.descrever(pendentes)` também nesse caminho e acrescentar a asserção da mensagem no teste do A-22 da E01-05, com Red e Green. |
| M-2 | E08-04 (implementador) | `tests/tecnicos/test_pagamentos_fronteiras.py::test_so_a_sincronizacao_escreve_nos_registros_de_pagamento` | O teste acusa qualquer módulo que cite `PagamentoNoProvedor` ou `ConsultaDoPagamento` e contenha uma chamada de escrita, mesmo quando a escrita é de outro modelo. Os módulos de pedidos evitam citar as classes (constante, função de leitura e `Protocol`) só para passar nessa heurística. | Verificar a escrita nos próprios modelos de pagamento (por exemplo, pela árvore de sintaxe) em vez da coocorrência de texto, e então permitir a citação da classe nos tipos e nas chaves estrangeiras. |
| M-3 | E08-R07, revisão de `2714a6a` | `docs/specs/E08-02/acceptance.md` (A-12 e A-21) | A-12 pede 409 para administrador em rota de comprador ativo, embora a política o recuse antes; A-21 pede ausência de aviso também quando o preço muda antes do congelamento, contrariando §5.1/E05-06. A implementação/testes respeitam as regras superiores; a inconsistência é na redação dos critérios. | Alinhar a redação à recusa pela política e ao aviso devido antes da abertura, sem alterar permissões nem o comportamento de notificações. Rever conforme a política de melhorias ao final da implantação. |
| M-4 | E08-R06, revisão de `584b323` | `tests/tecnicos/test_pedidos_quitacao.py` / `decidir_destino` | A corrida do A-17 cobre a deduplicação pela sincronização, mas não detecta retirar a guarda interna de destino existente. O limite e o reforço foram declarados no tratamento autorizado de R06; controle independente de chamada direta repetida passa no código atual, sem defeito funcional demonstrado. | Na revisão das melhorias, acrescentar teste direto sob transação e trava do pagamento que chame a decisão duas vezes, exija o mesmo destino e confira a ausência de novos registros/avisos. Preservar o teste concorrente existente; não tratar mutação como Red histórico. |
| M-5 | E09-08 (implementador) | `apps/financeiro/views.py` (resumo) e `apps/financeiro/reserva.py` (`itens_sem_cobertura`) | O resumo e a lista de itens sem cobertura percorrem todas as contas, obrigações e despesas, calculando saldo e financiado conta a conta (várias consultas por obrigação). Com o tempo a tela e o `avaliar_reserva`, que roda no fim de cada operação, ficam lentos. | Agregar os saldos numa consulta só por destinação, paginar as obrigações do resumo e medir o tempo antes de otimizar. |
| M-7 | E09-04 (implementador) | `tests/tecnicos/test_financeiro_concorrencia.py` (A-12 da E09-04) | Retirar a trava do pagamento da sincronização não faz o teste do aviso concorrente com a reconsulta falhar, porque a trava da situação do pedido e a chave idempotente do movimento também contêm a corrida. | Um teste da trava do pagamento isolada, em E07-03, se a trava merecer prova própria. |
| M-5 | E08-R06, registro do implementador (E08-02) e revisão de `584b323` | `tests/tecnicos/test_pedidos_concorrencia.py` / `abrir_pagamento` (E08-02 A-20) | Na corrida do A-20, a trava do fornecedor já serializa as duas aberturas, então a mutação que retira só a trava da rodada não é detectada; retirando as duas, o teste falha. O revisor considerou a trava da rodada redundante nesse cenário e não exigiu o reforço. Sem defeito funcional demonstrado. | Na revisão das melhorias, decidir se vale um teste que segure só a trava da rodada (outra thread travando a rodada diretamente) e confira que a abertura espera; ou registrar a trava da rodada como defesa redundante e descartar o item. |
| M-8 | E09-08, revisão de `34f9547` | `docs/specs/E09-08/acceptance.md` A-3 | O literal `1.000,00` conflita com a spec que recusa separador de milhar; teste e formulário usam/aceitam `1000,00`. Sem proposta de alterar comportamento financeiro. | Alinhar o literal à regra de entrada aprovada, mantendo os negativos de separador de milhar. |

## Encerradas

Melhorias apontadas antes da criação deste registro e já tratadas, para rastreabilidade.

| ID | Origem | Descrição | Tratamento |
|---|---|---|---|
| E03-R02 | revisão da E03 (`0ceb171`) | Pré-condição do A-3 da E03-06 não isolava o código `multiplo`. | Critério e spec ajustados pelo especificador (2026-10-16). |
| E04-R03 | revisão da E04 (`0b52010`) | Cenário 24 citava WhatsApp em `pagamento_confirmado`, que não tem esse canal. | Spec, critério e teste alinhados a `pagamento_aberto` (correção E04-R03). |
| E06-R03 | revisão da E06 (`2fbf143`) | Campo `novo` da auditoria de prorrogação fora de UTC. | Corrigido na correção da E06 (E06-04 A-12). |
| E07-R04 | revisão da E07 (`d6e4d20`) | Respostas imediatas do simulador sem normalização UTC. | Corrigido na correção da E07 (E07-01 A-21). |
| E07-R07 | revisão da E07 (`636a94c`) | Red da R03 registrado com `-k`. | Divergência reconhecida no registro; comandos com arquivos inteiros desde então. |
| M-6 | E09-06 (implementador) | O A-19 não detectava a retirada da trava das contas da apuração. | Encerrada na correção E09-R08 (2026-10-22): a trava da apuração é provada pelo E09-06 A-24 (ii); retirá-la o faz falhar (registro em `docs/specs/E09-06/review.md`). Não existe Red real possível para o A-19. |
