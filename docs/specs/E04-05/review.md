# E04-05 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **REPROVADO** sobre `0b52010` (2026-10-17). E04 global: **REPROVADO**. Registro do implementador preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E02-02, E02-04, E02-06 e E04-02/03.

## Arquivos

- `apps/notificacoes/acesso.py` (novo): `enviar_email_de_acesso`. `apps/notificacoes/models.py`: `Envio.modelo`, constantes `CONVITE`, `LINK_DE_ACESSO`, `CONTA_ALLAUTH` e `TIPOS_DE_ACESSO`, e os `CHECK`s por tipo. Migração `0004_acesso`.
- `apps/contas/convites.py`, `apps/contas/link_de_acesso.py`, `apps/contas/adaptadores.py` (`AdaptadorConta.send_mail`): passam a usar a função.
- Testes novos: `test_notificacoes_acesso.py` e `test_notificacoes_ponto_unico_de_email.py`.

## Decisões técnicas

- Sem retentativa automática e sem fila nos três e-mails (spec): o registro nasce concluído, com `corpo` vazio, uma tentativa e `chave = "<tipo>:<referência>"`. A referência é o id do convite, o id do `LinkDeAcesso` e, no allauth, um `uuid4`.
- A função envia primeiro e grava depois, numa `transaction.atomic()` própria; nunca propaga exceção. Se a gravação falhar, registra `logger.error` com tipo e referência (sem destino) e devolve um `Envio` não gravado com o resultado do envio. Falha de envio também gera `logger.error` com tipo, referência e classe do erro (substitui as mensagens que cada fluxo já registrava).
- `convite.email_enviado` passa a ser `envio.situacao == enviado`, e a tela continua igual.
- allauth: `send_mail` renderiza assunto e corpo de texto com `render_mail` e registra `modelo = template_prefix`. A alternativa HTML do allauth, se houvesse, não é enviada; os templates atuais do projeto só têm texto. `conta` é a dona do e-mail (`None` se não existir; nesse caso o `CHECK` recusa o registro, o fluxo segue e o erro é logado).
- `CHECK`s: `notificacao` nula se e somente se o tipo é de acesso; `conta` nula só no convite; tipos de acesso só por e-mail. Substituem o `CHECK` da E04-02.
- O allauth chama `send_mail` direto na requisição (como antes); convite e link continuam em `transaction.on_commit`.

## TDD

**Red.** Andaime (`enviar_email_de_acesso` sem comportamento, `Envio.modelo` sem uso, fluxos ainda com `EmailMessage`): `uv run pytest tests/tecnicos/test_notificacoes_acesso.py tests/tecnicos/test_notificacoes_ponto_unico_de_email.py -q` deu **8 failed, 5 passed**, por asserção (nenhum `Envio` de acesso gravado, `EmailMessage(` ainda em `apps/contas`). Passaram já no Red, porque dependem de ausência: e-mail sem conta (A-4, A-6), `email_enviado` falso na falha (A-2 pelo serviço), transação desfeita (A-9) e a ausência de segredo no banco e no log (A-7, que passa trivialmente enquanto não há registro). O A-7 só se torna significativo no Green.

**Green.** Mesmos arquivos: **13 passed**. Suíte completa, que inclui os testes existentes das E02-02, E02-04 e E02-06 sem nenhuma alteração (A-11): **1344 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1, A-2 | `test_notificacoes_acesso.py::test_convite_*`, `test_falha_no_envio_do_convite_e_registrada` |
| A-3, A-4 | `test_link_*` |
| A-5, A-6 | `test_recuperacao_*` |
| A-7 | `test_nenhum_segredo_no_banco_nem_no_log` |
| A-8 | `test_notificacoes_ponto_unico_de_email.py` |
| A-9, A-10 | `test_convite_em_transacao_desfeita_*`, `test_falha_ao_gravar_o_registro_*` |
| A-11 | arquivos existentes da E02, sem alteração |

## Limites da verificação

Cliente HTTP do Django e backends de e-mail de teste; nenhum SMTP real. A limitação "pelo menos uma vez" não se aplica aqui (envio único, sem fila).


## Revisão independente — 0b52010 — 2026-10-17

**Parecer da fatia: REPROVADO. E04 global: REPROVADO.**

A-1 a A-11 exemplificados passam, incluindo regressões E02 sem alterações de asserção. R02 importante: recuperação allauth envia antes do commit, contrariando a regra 1; o rollback apaga o registro de um e-mail que já saiu. Dois probes falharam; o controle equivalente do link de acesso passou.

Verificação independente: **1385 passed em 160,23 s** na suíte completa. Probes adicionais: **10 failed, 4 passed em 4,39 s**, mais **1 passed em 2,52 s** no caso de isolamento acrescentado. Dez falhas correspondem a R01 (oito) e R02 (duas). Lint, formatação, tipos, Django e CI passaram.

Comandos, matriz, reproduções, TDD, critérios de correção e limites no [parecer consolidado E04-07](../E04-07/review.md). Nenhum código ou teste versionado foi alterado pelo revisor.


## Correção E04-R02 — implementador (aguardando nova revisão)

**Red.** Com os testes novos e o código de `0b52010` (`uv run pytest tests/tecnicos/test_notificacoes_acesso.py -q`): **5 failed, 16 passed**, todos por asserção (`assert 1 == 0` em `len(mail.outbox)` e em `BackendQueFalhaPara.chamadas`: o e-mail do allauth saía antes do commit). Falharam: A-12, A-13, A-14 (caso com transação) e os probes `test_recuperacao_rollback_nao_envia_email` e `test_recuperacao_so_envia_apos_commit`. Passaram já no Red, como a spec previu, por serem guardas de regressão: o convite e o link de acesso do A-12 e do A-13 (já usavam `on_commit`), o A-14 sem transação, A-15, A-16 e o probe `test_link_rollback_nao_envia_email`.

**Green.** `AdaptadorConta.send_mail` renderiza a mensagem, lê o destino, busca a conta e gera a referência na requisição, e registra `transaction.on_commit(enviar)` com `enviar_email_de_acesso(...)`. Nada é guardado em banco, cache ou sessão; `ATOMIC_REQUESTS` continua desligado. Docstring de `enviar_email_de_acesso` atualizada. Arquivo de acesso: **21 passed**.

**Testes existentes da E02 ajustados (A-11).** Quatro ajustes de marcador ou de captura, sem mudar asserção, todos porque o e-mail do allauth agora só sai no commit:
- `tests/tecnicos/test_contas_recuperacao.py`: `pytestmark` passou a `django_db(transaction=True)` (13 testes falhavam sem isso);
- `tests/tecnicos/test_normalizacao_varredura.py`: a chamada a `/recuperar-acesso/` ficou dentro de `django_capture_on_commit_callbacks(execute=True)` (o teste já usava o fixture para o link de acesso);
- `tests/tecnicos/test_contas_google_cadastro.py`: o teste `test_conta_criada_pelo_google_define_senha_pela_recuperacao` recebeu o mesmo fixture e a mesma chamada.

**Decisão técnica no A-14.** O critério cita `BackendQueFalha`, que não tem contador. Usei `BackendQueFalhaPara`, que também falha e conta as chamadas, para provar que nada é tentado antes da confirmação.

Verificação final da correção: suíte completa **1461 passed**; `ruff check`, `ruff format --check`, `mypy .`, `makemigrations --check --dry-run` e `manage.py check` sem erros. Nenhuma asserção existente foi afrouxada ou removida.
