# E15-04 — Falhas de comunicação e do provedor; ciência do administrador

Fatia 4 de 7 da milestone **E15 — Painel administrativo e alertas operacionais**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E15-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E15-01.

## Contexto e objetivo

Vários problemas hoje só aparecem em log ou numa lista que o administrador precisa ir procurar:
- a mensagem que falhou;
- a chamada ao provedor que falhou de vez;
- a consulta que divergiu do que o sistema tinha;
- o pagamento aprovado sem horário de aprovação, que fica sem destino;
- o pagamento aprovado sem pedido;
- os avisos do provedor recusados seguidamente.

Esta fatia transforma cada um em alerta operacional (E15-02). Para os alertas de **fato**, que registram um acontecimento passado e não uma situação em curso, ela cria a **ciência do administrador**, que os encerra.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.6 | "Falha de mensagem". |
| Especificação §12 | Registrar envio e falhas; a falha de mensagem não altera o estado financeiro. |
| Especificação §15, Operação | Alertas para falhas de comunicação. |
| Milestone 15, herdado E04 | Alertas de falhas de comunicação a partir de `Envio`/`TentativaDeEnvio`. |
| Milestone 15, herdado E07 | Alertas para `ChamadaAoProvedor` que `falhou`, para `ConsultaDoPagamento` com divergência e para avisos recusados em sequência. |
| Milestone 15, herdado E08 | Alertas para cancelamento de cobrança com chamada `falhou`, para pagamento aprovado sem horário de aprovação e para destinos `sem_pedido`. |
| E07-05 | Aviso não autêntico responde 401, sem gravar o aviso. |
| E01-04 | Toda ação do administrador é auditada. |

## Escopo

**Dentro:**
- seis verificações;
- a contagem de avisos recusados em sequência;
- o serviço e a rota de ciência.

**Fora:** as telas de listagem (E15-05).

## Regras comuns

1. **Fatos.** A verificação de um tipo `fato` devolve cada fato que **não tem alerta do par com `aberto_em` posterior ao fato**, esteja esse alerta aberto ou resolvido.
   - Um fato já alertado e já com ciência não volta.
   - Um fato novo do mesmo par, depois da ciência, abre outro alerta.
   - O instante do fato é indicado em cada verificação.
2. **Dados sem dados pessoais:** como na E15-03, regra 2.
3. **Datas no corpo:** em Brasília, `dd/mm/aaaa hh:mm`. Valores com `reais`.

## Verificações

| Tipo | Natureza | Gravidade | Condição ou fato (instante do fato) | Chave | Título | Corpo | Link |
|---|---|---|---|---|---|---|---|
| `falha_de_mensagem` | condição | aviso | há `Envio` em `falhou` com `concluido_em` nas últimas 24 horas (`instante − concluido_em ≤ 24h`) | `geral` | "Falha no envio de mensagens" | "<n> mensagem(ns) não foram entregues nas últimas 24 horas. A mais recente falhou em <data>." | `envios_lista` com `?situacao=falhou` |
| `chamada_ao_provedor_falhou` | fato | aviso | `ChamadaAoProvedor` em `falhou` com `operacao` em `cancelar_cobranca` ou `consultar_pagamento` (`concluida_em`) | `chamada:<pk>` | "Chamada ao provedor falhou" | "A operação <operação> para <alvo> falhou no provedor (<último erro>) em <data>." | `painel_administracao` |
| `consulta_com_divergencia` | fato | aviso | `ConsultaDoPagamento` com `divergencia` preenchida (`consultado_em`) | `<id_externo>:<divergencia>` | "Divergência na consulta ao provedor" | "A consulta do pagamento <id_externo> divergiu em <rótulo da divergência> em <data>." | `painel_administracao` |
| `pagamento_sem_pedido` | fato | aviso | `DestinoDoPagamento` com `destino = sem_pedido` (`decidido_em`) | `pagamento:<id_externo>` | "Pagamento sem pedido" | "O pagamento <id_externo> de <valor> foi aprovado sem pedido correspondente (<rótulo do motivo>)." | `painel_administracao` |
| `pagamento_sem_horario_de_aprovacao` | condição | aviso | `PagamentoNoProvedor` em `aprovado`, com `aprovado_no_provedor_em` nulo e sem `DestinoDoPagamento` | `pagamento:<id_externo>` | "Pagamento aprovado sem horário" | "O pagamento <id_externo> de <valor> está aprovado no provedor sem o horário de aprovação, e a decisão sobre ele está parada." | `painel_administracao` |
| `avisos_recusados_em_sequencia` | condição | aviso | a contagem de recusas seguidas (regra 6) é ≥ 5 | `geral` | "Avisos do provedor recusados" | "<n> avisos seguidos do provedor de pagamentos foram recusados como não autênticos desde <primeira>. Confira o segredo de verificação dos avisos." | `painel_administracao` |

4. **Operações fora de `chamada_ao_provedor_falhou`:**
   - `estornar` e `acompanhar_estorno` já abrem os alertas de devolução da E10;
   - `criar_cobranca` recusada é um resultado normal, mostrado ao comprador na tentativa (E08-03);
   - `verificar_estornos` não falha de vez (E10-04).
5. **Rótulos:** a operação aparece pelo nome técnico (`cancelar_cobranca`, `consultar_pagamento`); a divergência e o motivo, pelos rótulos de `DivergenciaDaConsulta` e `MotivoDoDestino`.

### Avisos recusados em sequência

6. **Contagem:** um registro único `SequenciaDeAvisosRecusados` (`apps/pagamentos`), mutável, com `recusas_seguidas` (inteiro ≥ 0), `primeira_em` e `ultima_em` (nulos). Só o registro: nenhum corpo, cabeçalho, IP ou parâmetro do aviso.
   - **Aviso recusado como não autêntico (401):** incrementa `recusas_seguidas` de forma atômica (`UPDATE ... SET recusas_seguidas = recusas_seguidas + 1`) e grava `ultima_em = agora()`; `primeira_em = agora()` quando a contagem era 0.
   - **Aviso aceito (200, novo ou repetido):** zera a contagem e limpa os instantes, se ela não era 0.
   - **Corpo grande demais (400):** não conta.
   - **A resposta não muda:** 401, 200 e 400 como na E07-05. Uma falha ao gravar a contagem vai para o log (classe do erro) e não muda a resposta.
   - **Ajuste da E07-05:** a regra "401 e 400 não gravam nada" passa a ser "401 e 400 não gravam o aviso; o 401 só incrementa a contagem de recusas". Os testes existentes que conferem a ausência de `AvisoRecebido` continuam valendo.

### Ciência do administrador

7. **Serviço:** `dar_ciencia(autor, alerta)`, numa transação, com a trava do alerta (`select_for_update`). Conferências, na ordem, cada uma levanta `CienciaRecusada(codigo)`:

| Condição | Código | Mensagem |
|---|---|---|
| autor não é administrador ativo | `PermissionDenied` (não é `CienciaRecusada`) | — |
| tipo financeiro ou de natureza `condicao` | `nao_e_fato` | "Este alerta se encerra sozinho quando a situação é resolvida." |
| alerta já resolvido | `ja_resolvido` | "Este alerta já foi encerrado." |

   Com sucesso, o alerta é resolvido com o motivo "ciência do administrador", e a auditoria `alerta.ciencia` registra o autor, o tipo e a chave.
8. **Rota:** `POST administracao/alertas/<pk>/ciencia/` (nome `alertas_ciencia`), com `somente_administrador`.
   - `GET`: 405.
   - Alerta inexistente: 404.
   - Sucesso: 302 para `painel_administracao`, com a mensagem "Ciência registrada.".
   - `CienciaRecusada`: 302 para `painel_administracao`, com a mensagem da recusa como erro, sem escrita.
   - Comprador e fornecedor: 403. Anônimo: login.
9. **Duas ciências simultâneas** do mesmo alerta: uma resolve e grava a auditoria; a outra espera a trava e recebe `ja_resolvido`.

## Decisões técnicas

- **Ciência só para fatos.** Um alerta de condição encerrado à mão voltaria na verificação seguinte, enquanto a situação continuasse. Os alertas financeiros já têm regra própria de resolução (E09).
- **Contagem de recusas num registro só.** Gravar cada recusa permitiria a quem envia avisos falsos encher o banco. Um contador com incremento atômico custa uma atualização por recusa e basta para "em sequência".
- **Limite de 5 recusas.** Uma ou duas podem ser ruído, como um teste ou uma varredura. Cinco seguidas, sem nenhuma aceita entre elas, indicam um segredo trocado ou o provedor apontando para o lugar errado.
- **Divergência por pagamento e tipo.** Uma reconsulta que repete a mesma divergência não abre outro alerta enquanto o administrador não der ciência.

## Invariantes

- Nenhuma verificação altera pagamento, chamada, envio ou destino.
- A ciência só muda `resolvido_em` e `motivo_da_resolucao` do alerta, e grava a auditoria.

## Dependências e decisões em aberto

- Depende da E15-02, da E04-03, da E07-03 a E07-05 e da E08-04.
- Nenhuma decisão em aberto.
