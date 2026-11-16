# E15-04 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo:** o AO da E15-02.
- **Instantes:** `I = 2026-11-20 12:00 UTC`.
- **Execução:**
  - `verificar_operacao_agora()` chamada diretamente;
  - as `ChamadaAoProvedor` em `falhou`, as `ConsultaDoPagamento`, os `PagamentoNoProvedor` e os `DestinoDoPagamento` gravados diretamente, para isolar a verificação. O caminho até esses estados pelo simulador é coberto nas E07 e E08 e, no que o simulador reproduz, na E15-07;
  - os avisos enviados a `/pagamentos/avisos/` com o assinador do simulador (aceitos) ou com assinatura errada (recusados).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Falha de mensagem | positivo | dois `Envio` em `falhou`, concluídos em `I − 2h` e `I − 1h` | verificar em `I` | `falha_de_mensagem`, chave `geral`, corpo "2 mensagem(ns) não foram entregues nas últimas 24 horas. A mais recente falhou em 20/11/2026 08:00.", link `/administracao/envios/?situacao=falhou`. **Red esperado:** o tipo não existe |
| A-2 | Falha de mensagem | positivo | o A-1 | verificar em `I + 23h` e em `I + 23h + 1s` | aberto na primeira; resolvido na segunda (nenhuma falha nas últimas 24 horas) |
| A-3 | Falha de mensagem | negativo | um envio em `falhou` concluído em `I − 24h − 1s` | verificar em `I` | nada |
| A-4 | Chamada | positivo | uma `ChamadaAoProvedor` de `cancelar_cobranca` em `falhou`, com `ultimo_erro` | `processar_chamadas()`; verificar | `chamada_ao_provedor_falhou` com a chave `chamada:<pk>`, natureza fato, o corpo com `cancelar_cobranca`, o alvo e o código do erro |
| A-5 | Regra 4 | negativo | chamadas `estornar` e `criar_cobranca` em `falhou` | verificar | nenhum `chamada_ao_provedor_falhou` |
| A-6 | Regra 1, ciência | positivo | o A-4 | `dar_ciencia(ADM1, alerta)`; verificar de novo | o alerta resolvido com "ciência do administrador"; a auditoria `alerta.ciencia` com ADM1, o tipo e a chave; a verificação não reabre |
| A-7 | Divergência | positivo | consulta do pagamento `pg1` com divergência `valor` em `I` | verificar | `consulta_com_divergencia` com a chave `pg1:valor` e o rótulo "Valor" no corpo |
| A-8 | Regra 1 | positivo | o A-7 | outra consulta de `pg1` com `valor` em `I + 10min`; verificar | nenhum alerta novo (o aberto é posterior à primeira, e o par já está aberto) |
| A-9 | Regra 1 | positivo | o A-8; ciência em `I + 20min` | consulta de `pg1` com `valor` em `I + 30min`; verificar | um alerta novo do par; o anterior intacto |
| A-10 | Regra 1 | negativo | o A-7 com ciência; nenhuma consulta nova | verificar | nenhum alerta novo |
| A-11 | Sem pedido | positivo | pagamento aprovado com referência desconhecida (destino `sem_pedido`, motivo `referencia_desconhecida`) | verificar | `pagamento_sem_pedido` com a chave `pagamento:<id_externo>`, o valor e "Referência desconhecida" no corpo |
| A-12 | Sem horário | positivo | `PagamentoNoProvedor` aprovado sem `aprovado_no_provedor_em` e sem destino | verificar | `pagamento_sem_horario_de_aprovacao`, natureza condição |
| A-13 | Sem horário | positivo | o A-12 | o horário chega na consulta e o destino é decidido; verificar | o alerta resolvido |
| A-14 | Regra 6 | positivo | contagem 0 | 5 avisos com assinatura errada; verificar | cada resposta 401; `recusas_seguidas = 5`; nenhum `AvisoRecebido`; `avisos_recusados_em_sequencia` aberto, com o corpo "5 avisos seguidos..." |
| A-15 | Regra 6 | negativo | contagem 0 | 4 recusas; verificar | nenhum alerta |
| A-16 | Regra 6 | positivo | o A-14 | 1 aviso aceito (200); verificar | a contagem zerada, com os instantes limpos; o alerta resolvido |
| A-17 | Regra 6 | negativo | contagem 3 | 1 aviso com corpo acima do limite (400) | a contagem continua 3 |
| A-18 | Regra 6 | negativo | a gravação da contagem forçada a falhar | aviso com assinatura errada | resposta 401; um log com a classe do erro |
| A-19 | Regra 6 | concorrência | contagem 0; transações reais | 10 avisos recusados em 5 conexões simultâneas | `recusas_seguidas = 10` |
| A-20 | Regra 6 | negativo | o A-14 | ler o registro da contagem | só os três campos da regra; nenhum corpo, cabeçalho ou IP |
| A-21 | Regra 7 | negativo | `tarefa_atrasada` aberto (condição); `invariante_violado` aberto (financeiro) | `dar_ciencia` em cada um | `CienciaRecusada("nao_e_fato")` nos dois; os alertas abertos; nenhuma auditoria |
| A-22 | Regra 7 | negativo | o A-6 (resolvido) | `dar_ciencia` de novo | `CienciaRecusada("ja_resolvido")` |
| A-23 | Regra 7 | negativo | o A-4 | `dar_ciencia` com o comprador C, com a conta do fornecedor F e com `None` | `PermissionDenied`; o alerta aberto |
| A-24 | Regra 8 | positivo | o A-4; ADM1 autenticado com passkey | POST `/administracao/alertas/<pk>/ciencia/` | 302 para `/administracao/` com "Ciência registrada."; o alerta resolvido |
| A-25 | Regra 8 | negativo | o A-21 | POST da ciência no `tarefa_atrasada` | 302 com a mensagem de `nao_e_fato` como erro; nada gravado |
| A-26 | Regra 8 | negativo | o A-4 | GET na rota; POST com pk inexistente; POST como C e como F; POST anônimo | 405; 404; 403 e 403; redirecionamento ao login; nada gravado |
| A-27 | Regra 9 | concorrência | o A-4; transações reais | duas ciências simultâneas, a primeira pausada depois da trava | uma resolve e grava uma auditoria; a outra recebe `ja_resolvido` |
| A-28 | Regra 2 | negativo | os alertas abertos acima | ler `dados` e os corpos | nenhum nome, e-mail ou WhatsApp de comprador |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-18, A-20 a A-26 e A-28 | `tests/tecnicos/test_alertas_de_falha.py` |
| A-19 e A-27 | `tests/tecnicos/test_alertas_de_falha.py`, com transações PostgreSQL reais |
