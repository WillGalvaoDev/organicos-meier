# E04-04 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `8b4e771` (2026-10-18). E04 global: **APROVADO**. Histórico preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E02-09 e E04-01 a E04-03.

## Arquivos

- `apps/notificacoes/whatsapp.py` (novo): `CanalWhatsApp` (Protocol), `CanalWhatsAppDesligado`, `CanalWhatsAppSimulado` (singleton `SIMULADOR`), `FalhaNoCanalExterno`, `obter_canal_whatsapp`.
- `apps/notificacoes/emissao.py`: `_envios_externos` cria o envio de WhatsApp quando o canal não está desligado e a conta tem telefone e consentimento. `apps/notificacoes/processamento.py`: cancelamento sem tentativa e envio de WhatsApp.
- `config/settings/base.py`, `dev.py`, `test.py`, `prod.py`: `CANAL_WHATSAPP`.
- `tests/conftest.py` (fixture `simulador_whatsapp`); testes em `test_notificacoes_whatsapp.py`, `test_notificacoes_falha_isolada.py` (novos) e `test_configuracao_producao.py`.

## Decisões técnicas

- `CANAL_WHATSAPP`: lido do ambiente em `base.py` (padrão `desligado`) e recusado com `ImproperlyConfigured` se não for `desligado` nem `simulado`, em qualquer ambiente; `dev.py` usa `simulado` por padrão; `test.py` fixa `simulado`; `prod.py` recusa `simulado`.
- Acréscimo à interface da spec: `enviar(numero_e164, texto, *, envio_id=None)`. O parâmetro opcional serve só para o log do simulador (`"WhatsApp simulado: envio <id> aceito"`), porque a spec pede esse id e a assinatura original não o carrega. Nenhuma implementação registra número nem texto.
- Verificação no processamento: a conta é relida sem trava no início de cada tentativa. Sem telefone ou consentimento: `cancelado` com `sem_consentimento`; canal desligado: `canal_desligado`; ambos sem tentativa e sem chamar o canal. O número usado é o atual da conta.
- `processar_envios` devolve as tentativas feitas, e o `limite` conta os envios retirados da fila, inclusive os cancelados sem tentativa (spec E04-03).
- O fato de teste do cenário 24 reaproveita `ModeloContador` de `tests/apoio` (já existente), em vez de criar tabela nova.
- Ajuste em teste existente, sem afrouxar nenhuma asserção: o helper `_carregar_producao` de `test_configuracao_producao.py` ganhou o parâmetro do módulo de configurações, lê as chaves com `getattr(m, k, None)` e inclui `CANAL_WHATSAPP`.

## TDD

**Red.** Andaime (`whatsapp.py` sem comportamento e sempre desligado; `CANAL_WHATSAPP = "desligado"` fixo na base; emissão e processamento ainda sem WhatsApp): `uv run pytest tests/tecnicos/test_notificacoes_whatsapp.py tests/tecnicos/test_notificacoes_falha_isolada.py tests/tecnicos/test_configuracao_producao.py -q` deu **14 failed, 11 passed**, por asserção (nenhum envio de WhatsApp criado, simulador sem mensagens, configuração aceitando `simulado` em produção e `meta`).

**Green.** Mesmos arquivos: todos passando. Suíte completa: **1331 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 a A-8, A-12, A-13 | `test_notificacoes_whatsapp.py` |
| A-9 (cenário 24) | `test_notificacoes_falha_isolada.py::test_falha_no_whatsapp_nao_desfaz_o_fato_nem_a_notificacao` (marcado `acceptance`) |
| A-10 | `test_notificacoes_falha_isolada.py::test_nada_e_tentado_antes_da_confirmacao_da_transacao` (`transaction=True`, duas conexões) |
| A-11 | `test_configuracao_producao.py` (subprocesso, como na E02-02) |

## Limites da verificação

Nenhuma integração com a Meta: só o simulador, como a fase 1 exige. O cenário 24 usa um fato de teste; a E08 o repete com o pagamento real do simulador de pagamentos. As pendências da Meta (conta comercial, templates e tarifas) continuam abertas.


## Revisão independente — 0b52010 — 2026-10-17

**Parecer da fatia: APROVADO. E04 global: REPROVADO.**

A-1 a A-8 e A-10 a A-13 conferidos e verdes: consentimento, número atual, desligamento, tentativas, isolamento e recusa do simulador em produção. R03 melhoria: A-9 menciona WhatsApp para pagamento_confirmado, que não possui esse canal na matriz. O mecanismo foi confirmado adicionalmente com fato e pagamento_aberto na mesma transação efetivamente confirmada; alinhar a redação sem acrescentar canal ao evento.

Verificação independente: **1385 passed em 160,23 s** na suíte completa. Probes adicionais: **10 failed, 4 passed em 4,39 s**, mais **1 passed em 2,52 s** no caso de isolamento acrescentado. Dez falhas correspondem a R01 (oito) e R02 (duas). Lint, formatação, tipos, Django e CI passaram.

Comandos, matriz, reproduções, TDD, critérios de correção e limites no [parecer consolidado E04-07](../E04-07/review.md). Nenhum código ou teste versionado foi alterado pelo revisor.


## Correção E04-R03 — implementador (aguardando nova revisão)

**Sem Red esperado**, como a spec da correção determina: o defeito estava na redação e no teste, e não no mecanismo. O A-9 corrigido e o probe do revisor passaram assim que foram escritos, contra o código inalterado.

**Alterações.** `test_falha_no_whatsapp_nao_desfaz_o_fato_nem_a_notificacao` foi reescrito conforme o A-9 corrigido: uma única `transaction.atomic()` com o fato de teste e uma só emissão de `pagamento_aberto` (saíram a emissão de `pagamento_confirmado` e a segunda transação). Continuam exigidos: o fato inalterado, três tentativas de WhatsApp, e-mail `enviado`, notificação idêntica à emitida e o conteúdo na central. As duas asserções de texto da central que dependiam de `pagamento_confirmado` ("Pagamento confirmado", "Recebemos seu pagamento.") foram substituídas pelo texto da notificação de `pagamento_aberto` ("Pague em 24 horas."). Motivo: o teste antigo seguia uma redação contraditória da especificação. A matriz não mudou.

O probe `test_falha_whatsapp_preserva_fato_emitido_na_mesma_transacao` do revisor entrou com o corpo original em `tests/tecnicos/test_notificacoes_falha_isolada.py`. Resultado: o arquivo tem **3 passed**.

Verificação final da correção: suíte completa **1461 passed**; `ruff check`, `ruff format --check`, `mypy .`, `makemigrations --check --dry-run` e `manage.py check` sem erros. Nenhuma asserção existente foi afrouxada ou removida.


## Revalidação independente — 8b4e771 — 2026-10-18

**Parecer da fatia: APROVADO. E04 global: APROVADO.**

R03 encerrado. Spec e A-9 agora usam pagamento_aberto, com fato e emissão na mesma transação. Matriz de canais preservada. Teste corrigido e probe independente com commit real passam; nenhuma mudança no mecanismo de envio foi necessária.

Suíte completa: **1461 passed em 137,79 s**. Script independente original da revisão de 0b52010, sem alterações: **15 passed em 6,78 s**. As dez falhas anteriores não se reproduzem. Lint, formatação, tipos, verificações Django e CI passaram. Evidências e limites no [parecer consolidado](../E04-07/review.md), seção deste SHA.
