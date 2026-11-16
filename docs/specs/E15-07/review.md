# E15-07 — Registro do implementador

Agente 2.

## Execução

A fatia não tem Red próprio (como na E14-08): `tests/tecnicos/test_painel_ponta_a_ponta.py` verifica o que as E15-01 a E15-06 construíram, com o simulador de pagamentos, as tarefas chamadas como o worker as chama (`tarefa(timestamp=0)`), as telas do administrador pelas rotas HTTP (com `entrar_de_novo` a cada avanço do relógio) e o relógio controlado.

- Primeira execução: **12 passaram e 1 falhou**. A falha é o A-3, e revelou um defeito de produção da E15-05 (abaixo). Os 12 que passaram não têm Red porque o comportamento já existia.
- Commit do teste: o commit "E15-07: testes de ponta a ponta do painel e dos alertas operacionais".
- Depois da correção: `13 passed` no arquivo; com o painel (E15-05), `38 passed`.

## Defeito achado pelo A-3 (E15-05), corrigido

- **Sintoma:** depois de três falhas automáticas do pedido formal e de um reenvio manual aceito, a ação "O pedido formal não foi enviado depois das três tentativas: reenvie." continuava no painel.
- **Causa:** a regra da E15-05 usa só a situação `concluido_com_falhas` do `EnvioDoPedidoFormal`; o reenvio manual (E13-04) grava uma `TentativaDeEnvioDoPedidoFormal` com sucesso, mas não muda a situação do ciclo automático.
- **Correção:** `_acoes_do_pedido_formal` (`apps/operacao/painel.py`) só mostra a ação quando o ciclo está em `concluido_com_falhas` **e** nenhuma tentativa do pedido formal teve sucesso. Os critérios A-9 da E15-05 (três falhas, sem sucesso) e A-3 desta fatia passam. É o único código de produção desta fatia; vai como correção da E15-05, para o revisor conferir se a regra da E15-05 (tabela da regra 3) deve ser lida assim.

## Desvios e pontos para o revisor

1. **Um administrador só** (ADM1), como nas fatias anteriores.
2. **A-8:** o simulador não tem recusa definitiva de cancelamento (o `cancelar_cobranca` do simulador nunca recusa). O alerta de chamada que falhou de vez foi obtido com uma `consultar_pagamento` de um pagamento desconhecido, que vira `falhou` depois de 24 h (E07-04, A-9), e a ciência é dada pelo painel. A operação é uma das duas que a regra 4 da E15-04 inclui.
3. **A-10:** o simulador não devolve valor divergente; as `ConsultaDoPagamento` com divergência `valor` foram criadas direto. O que se verifica é o que a E15-04 define: a segunda consulta igual não abre outro alerta.
4. **A-1 e A-2** estão num teste só e **A-8 e A-9** em outro, porque cada passo usa o estado do anterior. A-2 usa AP-I2 (comprador de fábrica, pago pelo simulador) e não o AP de duas compras; o repasse e o frete aparecem na etapa aguardando fornecedor se liberados.
5. **A-12:** o evento de teste é `pagamento_confirmado`, o e-mail falha até o envio ficar `falhou` (o relógio avança um dia por rodada de `processar_envios`), e a central de notificações do comprador mostra a notificação. Nenhum movimento financeiro muda.
6. **A-13:** o histórico filtrado por ADM1 é comparado, página a página, com as entradas lidas do banco; entre elas estão `recebimento.registrar` e `descarte.registrar`.
7. **A-15:** o teste compara rodada, pedido, pagamento, chamada, movimento e envios antes e depois de `verificar_operacao`; os e-mails dos próprios avisos são os únicos envios novos. O invariante financeiro e "no máximo um alerta aberto por par" são conferidos no fim de cada critério.

## Verificação da etapa inteira

- `uv run pytest -q`: **3397 passed** (3260 da E14 e anteriores mais 137 novos; sem falhas).
- `uv run mypy .`: 527 arquivos sem erro. `uv run ruff check --no-cache .` e `uv run ruff format --check .`: limpos. `makemigrations --check --dry-run`: sem mudanças.
- Testes existentes alterados (só para acompanhar o evento `alerta_operacional` da regra 3 da E15-02, sem remover asserção): `test_notificacoes_eventos.py`, `test_financeiro_alertas.py`; e, na E15-04, um ajuste de contagem em `test_alertas_operacionais.py`, arquivo desta etapa.
- Sem push, PR nem merge: aguarda o parecer do agente 3. No PR à `main`, atualizar o README (Parte 1, nas duas línguas) e a milestone 15.
