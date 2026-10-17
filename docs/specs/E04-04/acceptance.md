# E04-04 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). O simulador é reiniciado pela fixture de `tests/apoio` em cada teste. "Comprador com consentimento" tem `telefone="+5521999990000"` e `whatsapp_consentido_em` preenchido.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §12 | positivo | um comprador com consentimento e `CANAL_WHATSAPP="simulado"` | emito `retirada_liberada` com link `/retiradas/` e processo os envios | envios `email` e `whatsapp`, ambos `enviado`; o simulador registrou uma mensagem para `+5521999990000` com o texto `"<titulo> https://om.test/retiradas/"`; o `destino` do envio de WhatsApp está vazio |
| A-2 | Spec §3.2, §12 | negativo | um comprador sem telefone; outro com telefone e sem consentimento | emito `retirada_liberada` para os dois | só envios de e-mail; nenhum de WhatsApp |
| A-3 | Spec da fatia | negativo | um comprador com consentimento | emito `estorno` | nenhum envio de WhatsApp |
| A-4 | Spec da fatia | negativo | um comprador com consentimento e `CANAL_WHATSAPP="desligado"` (`override_settings`) | emito `pagamento_aberto` | nenhum envio de WhatsApp; o e-mail é criado |
| A-5 | E02-09 | negativo | um envio de WhatsApp pendente | revogo o consentimento pelo perfil (E02-09) e processo | envio `cancelado`, `motivo_cancelamento="sem_consentimento"`, `concluido_em` preenchido; nenhuma tentativa; o simulador não recebeu nada; o e-mail do mesmo evento é enviado |
| A-6 | Spec da fatia | negativo | um envio de WhatsApp pendente | passo para `CANAL_WHATSAPP="desligado"` e processo | `cancelado` com `motivo_cancelamento="canal_desligado"`; nenhuma tentativa |
| A-7 | Spec da fatia | positivo | um envio de WhatsApp pendente; troco o telefone para `+5521988887777`, mantendo o consentimento | processo | mensagem enviada para `+5521988887777`; a tentativa não grava o número |
| A-8 | Spec da fatia | negativo | `falhar_proximas(2)` | processo três vezes, avançando pelos intervalos da E04-03 | falha, falha, sucesso, com `erro="FalhaNoCanalExterno"`; uma mensagem no simulador |
| A-9 | Cenário 24, E04-R03 | positivo | um comprador com consentimento; `falhar_sempre()` | numa única transação, gravo o fato de teste e emito `pagamento_aberto` para o comprador, sem nenhuma outra emissão; confirmo; processo até esgotar as tentativas; abro a central como o comprador | o fato de teste continua gravado e inalterado; WhatsApp `falhou` com três tentativas; e-mail `enviado`; a notificação aparece na central com o conteúdo emitido; nenhuma exceção chegou ao código que emitiu nem a `processar_envios` |
| A-10 | Cenário 24, Infra 7 | negativo | o simulador com `falhar_sempre()` | emito dentro de uma transação e, antes de confirmar, chamo `processar_envios` noutra conexão | o envio ainda não existe para a outra conexão (nada é tentado antes da confirmação); depois da confirmação, é tentado |
| A-11 | Spec da fatia, A3 por analogia | negativo | as configurações de produção com `CANAL_WHATSAPP=simulado` no ambiente; noutro caso, `CANAL_WHATSAPP=meta` em qualquer ambiente | carrego as configurações num subprocesso, como no teste de configuração de produção da E02-02 | `ImproperlyConfigured` nos dois casos; em produção sem a variável, o valor é `desligado` |
| A-12 | Spec da fatia | positivo | — | inspeciono `obter_canal_whatsapp()` com `simulado` e com `desligado` | devolve `CanalWhatsAppSimulado` e `CanalWhatsAppDesligado`; o processamento não importa nenhuma das classes diretamente (teste que procura o nome da classe no módulo de processamento) |
| A-13 | Infra 5 | negativo | `caplog` em `DEBUG`, com falhas e um sucesso no simulador | processo | nenhum registro de log contém o número nem o texto da mensagem |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-8, A-12, A-13 | `tests/tecnicos/test_notificacoes_whatsapp.py` |
| A-9, A-10 | `tests/tecnicos/test_notificacoes_falha_isolada.py` (marcador `acceptance`, com o comentário `cenário 24`; o A-10 com `django_db(transaction=True)`). O teste do A-9 é reescrito conforme a correção E04-R03, e o probe `test_falha_whatsapp_preserva_fato_emitido_na_mesma_transacao` do revisor de `0b52010` entra literalmente |
| A-11 | `tests/tecnicos/test_configuracao_producao.py` (arquivo existente) |
