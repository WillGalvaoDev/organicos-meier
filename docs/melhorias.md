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

## Encerradas

Melhorias apontadas antes da criação deste registro e já tratadas, para rastreabilidade.

| ID | Origem | Descrição | Tratamento |
|---|---|---|---|
| E03-R02 | revisão da E03 (`0ceb171`) | Pré-condição do A-3 da E03-06 não isolava o código `multiplo`. | Critério e spec ajustados pelo especificador (2026-10-16). |
| E04-R03 | revisão da E04 (`0b52010`) | Cenário 24 citava WhatsApp em `pagamento_confirmado`, que não tem esse canal. | Spec, critério e teste alinhados a `pagamento_aberto` (correção E04-R03). |
| E06-R03 | revisão da E06 (`2fbf143`) | Campo `novo` da auditoria de prorrogação fora de UTC. | Corrigido na correção da E06 (E06-04 A-12). |
| E07-R04 | revisão da E07 (`d6e4d20`) | Respostas imediatas do simulador sem normalização UTC. | Corrigido na correção da E07 (E07-01 A-21). |
| E07-R07 | revisão da E07 (`636a94c`) | Red da R03 registrado com `-k`. | Divergência reconhecida no registro; comandos com arquivos inteiros desde então. |
