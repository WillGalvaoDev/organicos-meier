# E15-03 — Atrasos de processamento

Fatia 3 de 7 da milestone **E15 — Painel administrativo e alertas operacionais**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E15-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E15-01.

## Contexto e objetivo

A E15-01 detecta a tarefa que parou. Mas uma tarefa pode continuar rodando e deixar um item para trás: as tarefas registram em log a falha de um item e seguem com os outros (E06-05, E08, E13-02). Esta fatia acrescenta verificações de condição (E15-02) que olham o **efeito esperado** de cada processamento. Elas acusam o item que deveria ter andado e não andou.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.6 | Tarefa atrasada. |
| Especificação §15, Tempo | Prazos calculados no servidor; processamento retomável. |
| Milestone 15, herdado E06 | Rodadas em `fechamento` com o prazo vencido há mais de alguns minutos; falhas registradas em log por rodada. |
| Milestone 15, herdado E07 | `ChamadaAoProvedor` pendente há muito tempo. |
| Milestone 15, herdado E09 (consulta à API) | Alertar quando um dia ficar sem conciliação por mais de 24 horas depois do fim dele. |
| Milestone 15, herdado E04 | Falhas de comunicação a partir de `Envio`. |
| E13-02 | O ciclo automático do pedido formal, com `proxima_tentativa_em`. |

## Escopo

**Dentro:** cinco verificações de natureza `condicao`, registradas com `registrar_verificacao` (E15-02).

**Fora:** falhas (E15-04) e telas (E15-05).

## Regras comuns

1. **Margem de atraso:** `MARGEM_DE_ATRASO = 5 minutos`. "Atrasado" significa `instante − limite > MARGEM_DE_ATRASO` (estrito). Os instantes vêm de `agora()` lido uma vez pela verificação (E15-02, regra 6).
2. **Dados sem dados pessoais:** identificadores internos, nomes de fornecedor, instantes ISO e contagens. Nunca nome, e-mail ou WhatsApp de comprador.
3. **Datas no corpo:** em Brasília, `dd/mm/aaaa hh:mm`.

## Verificações

| Tipo | Condição | Chave | Dados | Título | Corpo | Link |
|---|---|---|---|---|---|---|
| `fechamento_nao_encerrado` | rodada em `fechamento` com `prazo_do_fechamento(rodada)` atrasado (regra 1) | `rodada:<pk>` | `rodada`, `fornecedor` (nome), `prazo` | "Fechamento não encerrado" | "O fechamento da rodada de <fornecedor> terminou em <prazo> e ainda não foi encerrado." | `rodadas_estoque` da rodada |
| `pedido_formal_atrasado` | `EnvioDoPedidoFormal` em `em_andamento` com `proxima_tentativa_em` preenchida e atrasada | `pedido_formal:<pk>` | `pedido_formal`, `rodada`, `fornecedor`, `prevista_para` | "Envio do pedido formal atrasado" | "A tentativa automática do pedido formal da rodada de <fornecedor> estava prevista para <prevista_para> e não foi feita." | `rodadas_pedido_formal` da rodada |
| `conciliacao_atrasada` | existe `ConciliacaoDiaria`; com `P` = dia seguinte ao da última conciliação, `instante − fim(P) > 24 horas`, onde `fim(P)` é o segundo valor de `limites_do_dia(P)` | `dia:<P em ISO>` | `dia` (ISO), `ultima_conciliada` (ISO) | "Conciliação atrasada" | "O dia <P dd/mm/aaaa> terminou há mais de 24 horas e ainda não foi conciliado. A última conciliação é de <dd/mm/aaaa>." | `financeiro_conciliacoes` |
| `chamadas_ao_provedor_atrasadas` | há `ChamadaAoProvedor` `pendente` com `proxima_em` atrasada, ou com `instante − criada_em > 25 horas` | `geral` | `quantidade`, `mais_antiga` (o menor `criada_em` entre elas, ISO) | "Chamadas ao provedor atrasadas" | "<n> chamada(s) ao provedor de pagamentos estão pendentes além do previsto. A mais antiga é de <mais_antiga>." | `painel_administracao` |
| `envios_atrasados` | há `Envio` `pendente` com `proxima_tentativa_em` atrasada | `geral` | `quantidade`, `mais_antigo` (o menor `proxima_tentativa_em`, ISO) | "Notificações atrasadas" | "<n> notificação(ões) aguardam envio além do previsto, desde <mais_antigo>." | `envios_lista` |

Todas têm gravidade **aviso** e natureza **condição**: são resolvidas quando a condição deixa de valer (E15-02, regra 6).

4. **Sem conciliação ainda:** sem nenhuma `ConciliacaoDiaria`, `conciliacao_atrasada` não acusa nada. O atraso da tarefa `conciliar_dias_pendentes` continua coberto por `tarefa_atrasada`.
5. **Dados congelados na abertura:** os dados de um alerta `geral` aberto não são atualizados enquanto ele continua aberto (E09-03: abrir de novo devolve o existente). A contagem atual aparece no painel (E15-05).
6. **Troca de chave:** quando a conciliação avança um dia mas o seguinte também fica atrasado, o alerta do dia anterior é resolvido e o do novo dia é aberto na mesma execução.

## Decisões técnicas

- **25 horas para chamadas pendentes.** A consulta desiste depois de 24 horas sem encontrar o pagamento (E07, `nao_encontrado`). Uma chamada pendente além disso indica que o ciclo de novas tentativas não terminou como deveria.
- **Sem verificação própria para o bloqueio de tentativas (herdado E08).** As ações conferem o prazo de pagamento (infraestrutura 5), e um pagamento aprovado depois do prazo vai para devolução (E08-04). O que resta é o cancelamento da cobrança no provedor. Uma falha nele aparece como `chamada_ao_provedor_falhou` (E15-04), e a parada da tarefa aparece como `tarefa_atrasada`.
- **Uma chave `geral` para chamadas e envios.** Muitos itens atrasados ao mesmo tempo têm quase sempre uma causa comum, como o provedor fora do ar ou a fila parada. Um alerta por item inundaria o administrador.

## Invariantes

- As verificações só leem. Nenhuma muda rodada, envio, chamada ou conciliação.

## Dependências e decisões em aberto

- Depende da E15-02, da E06-05, da E13-02, da E09-07, da E07-04 e da E04-03.
- Nenhuma decisão em aberto.
