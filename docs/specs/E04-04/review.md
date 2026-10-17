# E04-04 — Registro do implementador (aguardando revisão independente)

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
