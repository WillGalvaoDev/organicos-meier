# E04-03 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E04-01 e E04-02.

## Arquivos

- `apps/notificacoes/canais.py` (`enviar_email`), `processamento.py` (`processar_envios`, `MAXIMO_DE_TENTATIVAS`, `INTERVALOS`), `tarefas.py` (tarefa periódica), `models.py` (`TentativaDeEnvio`, `ResultadoDaTentativa`), migração `0003_tentativa` (com a trigger de só inserção da E01-04).
- `config/settings/base.py` (`procrastinate.contrib.django` em `INSTALLED_APPS`, `EMAIL_TIMEOUT = 10`, `PROCRASTINATE_AUTODISCOVER_MODULE_NAME = "tarefas"`), `config/settings/prod.py` (SMTP lido do ambiente), `README.md` (como subir o *worker*).
- `tests/apoio/email_falho.py` (`BackendComFalhas`, `BackendQueFalhaPara`); testes em `test_notificacoes_processamento.py`, `_tarefas.py` (novos), `_modelo.py` e `_concorrencia.py`.

## Decisões técnicas

- Cada envio é processado numa `transaction.atomic()` própria, com `select_for_update(skip_locked=True)` ordenado por `proxima_tentativa_em` e `id`; o canal é chamado com a linha travada e o resultado (tentativa e estado do envio) é gravado na mesma transação. Pelo menos uma vez: a limitação (possível duplicata se o processo cair entre o aceite do serviço e a confirmação) está na spec e fica registrada aqui.
- Toda exceção do canal vira falha; só o nome da classe é gravado em `erro` (até 100 caracteres). Os logs trazem apenas id do envio, número da tentativa e classe do erro (`warning` nas duas primeiras falhas, `error` na terceira).
- Intervalos: 1 minuto após a primeira falha e 10 minutos após a segunda; a terceira encerra o envio como `falhou`.
- O despacho por canal é um dicionário (`email` agora; o WhatsApp entra na E04-04).
- Tarefa: `@app.periodic(cron="* * * * *")` sobre `@app.task(name="processar_envios_pendentes", queueing_lock=...)`; o módulo é descoberto pela configuração `PROCRASTINATE_AUTODISCOVER_MODULE_NAME = "tarefas"`. As migrações do Procrastinate entram com o app.
- O SES não é considerado validado (L-13 e sandbox pendentes).

## TDD

**Red.** Andaime (modelo `TentativaDeEnvio` sem restrições nem trigger; `enviar_email` e `processar_envios` sem comportamento; tarefa sem registro; app do Procrastinate fora de `INSTALLED_APPS`): `uv run pytest tests/tecnicos/test_notificacoes_*.py -q` deu **14 failed, 89 passed**, todas por asserção (nenhuma tentativa gravada, banco aceitando `UPDATE`/`DELETE`/número repetido, tarefa não registrada, configuração ausente). Antes disso, dois ajustes de teste por erro meu de escrita: tipagem do teste da tarefa e a marca `django_db` do teste de migrações.

**Green.** Mesmos arquivos: **103 passed**. Suíte completa: **1312 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 a A-5, A-7, A-8, A-12 | `test_notificacoes_processamento.py` |
| A-6 | `test_notificacoes_concorrencia.py::test_processador_pula_o_envio_travado_por_outro` |
| A-9 | `test_notificacoes_modelo.py` |
| A-10, A-11 | `test_notificacoes_tarefas.py` |

## Limites da verificação

O *worker* do Procrastinate não foi subido: os testes chamam `processar_envios` e a tarefa diretamente, e conferem o registro periódico. Nenhum SMTP real foi usado (`locmem` e backends de teste). A leitura do SMTP em produção é coberta apenas pela suíte de configuração existente (carregamento sem erro).
