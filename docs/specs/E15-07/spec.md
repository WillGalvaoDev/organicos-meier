# E15-07 — Ponta a ponta: painel e alertas operacionais

Fatia 7 de 7 da milestone **E15 — Painel administrativo e alertas operacionais**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E15-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E15-01.

## Contexto e objetivo

Exercitar o que as E15-01 a E15-06 construíram, com o simulador de pagamentos, as tarefas periódicas chamadas como o worker as chama, as telas do administrador e o relógio controlado:
- o painel acompanha uma rodada do interesse até o fim da retirada;
- os alertas operacionais abrem, avisam e se encerram;
- comprador e fornecedor ficam de fora.

Como nas E13-08 e E14-08, a fatia não cria código de produção.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, administrador | Dashboard, ações necessárias, histórico. |
| Especificação §15, Operação | Alertas para pagamentos sem conciliação, estornos falhos, tarefas atrasadas e falhas de comunicação. |
| Infraestrutura 3.6 | A lista dos alertas ao admin. |
| Infraestrutura 7 (fase 1) | Cenários contra o simulador; falhas e atrasos do provedor reproduzidos. |
| Especificação §2 | Isolamento entre perfis. |

## Escopo

**Dentro:** os cenários abaixo, com:
- as ações do administrador pelas rotas HTTP (com `entrar_de_novo` depois de cada avanço do relógio, como nas E13-08 e E14-08);
- as tarefas periódicas chamadas diretamente (`tarefa(timestamp=0)`), o que inclui o envoltório da E15-01;
- `processar_chamadas()` e `processar_envios()` quando o cenário pede.

**Fora:** código de produção novo.

## Cenários

1. **Rodada inteira pelo painel.** A cada passo, a ação necessária esperada aparece e a anterior some:
   - mínimo atingido;
   - fechamento;
   - fechamento encerrado;
   - abertura do pagamento;
   - margem;
   - apta para a apuração;
   - apuração;
   - aprovação;
   - pedido formal;
   - repasse e frete liberados;
   - recebimento;
   - liberação;
   - prazo de retirada;
   - descarte.

   No fim, a rodada sai do painel.
2. **Worker parado e retomado.** As tarefas deixam de concluir. A verificação abre `tarefa_atrasada`, e o administrador recebe a notificação no site e o e-mail (que sai quando os envios voltam). O painel mostra "Atrasada". Quando as tarefas voltam, os alertas são resolvidos. Na retomada depois de um período longo, a própria verificação não se acusa (E15-02, regra 10).
3. **Provedor com problemas.** Uma consulta de pagamento falha de vez no simulador (pagamento desconhecido por mais de 24 horas). Uma consulta com valor divergente é gravada diretamente, porque o simulador não a produz. Chegam avisos com assinatura errada. Os alertas de fato e de condição abrem, e a ciência pelo painel encerra os de fato.
4. **Mensagens falhando.** O e-mail falha até o envio ser encerrado sem sucesso. `falha_de_mensagem` abre, e a notificação no site continua correta (§12).
5. **Histórico.** As ações dos cenários anteriores aparecem no histórico, com os filtros funcionando.
6. **Isolamento.** Comprador e fornecedor não acessam o painel, o histórico nem a ciência, e não recebem nenhum alerta operacional.

## Invariantes conferidos

- Nenhuma verificação altera rodada, pedido, pagamento, chamada, envio ou livro-razão.
- O invariante financeiro (E09) continua sem violação no fim de cada critério, conferido como na E14-08.
- No máximo um alerta aberto por `(tipo, chave)`.

## Dependências e decisões em aberto

- Depende das E15-01 a E15-06 e das etapas cujos fluxos o cenário 1 percorre (E05 a E14).
- Nenhuma decisão em aberto.
