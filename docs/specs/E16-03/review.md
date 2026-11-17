# E16-03 — Registro do implementador

Agente 2.

## Red (observado antes do código de produção)

`uv run pytest -q tests/ambiente/test_homologacao.py`: **3 failed, 16 passed**. Falharam A-1 (o `SENTRY_DSN` não era exigido), A-2 (nenhum cliente do Sentry em `prod.py`) e A-13 (`settings.SENTRY_DSN` inexistente em `config.settings.test`). `uv run pytest -q tests/tecnicos/test_observabilidade.py`: erro de coleta, `ModuleNotFoundError: No module named 'config.observabilidade'` (as funções `opcoes_do_sentry`, `antes_de_enviar` e `MONITORES_EXTERNOS` não existiam; A-8 "nenhum check-in" ficou coberto por esse erro).

Depois do Green, três testes ainda falharam por defeito do **meu teste** (não do código), corrigidos sem afrouxar asserção:
- A-4: o cliente de testes do Django não passa pelo WSGI, onde o Sentry se liga, então o evento não tinha `method` nem `url`. O teste passou a chamar `get_wsgi_application()` com um `environ` de verdade (sem fechar a conexão da transação do teste, como o cliente faz);
- A-7: sobraram breadcrumbs `query` no evento. O código passou também a removê-los no `limpar_evento` (defesa em profundidade, além do `before_breadcrumb`);
- A-11: o teste usou `verificar_invariante`, que fala com o simulador; entrou o prefixo `test_observabilidade` em `PREFIXOS_COM_SIMULADOR`.

## Green

- `config/observabilidade.py`: `opcoes_do_sentry` (as mesmas opções em produção e nos testes), `limpar_evento`/`antes_de_enviar` (só método e URL sem query, `User-Agent`, só o `id` do usuário; e-mails e telefones trocados por `[removido]` em todo o texto do evento, inclusive nas linhas de código das pilhas; valores de chaves sensíveis em `extra`, `tags` e `contexts`; breadcrumbs SQL removidos; se o filtro falha, o evento é descartado) e `antes_do_breadcrumb`.
- `prod.py`: `SENTRY_DSN` obrigatório e `iniciar_sentry`. `dev.py`: só inicia se houver DSN. `test.py`: `SENTRY_DSN = ""`, sem iniciar.
- `apps/operacao/monitores_externos.py`: `MONITORES_EXTERNOS` (só `verificar_operacao`; a linha de `backup_diario` entra na E16-04), `slug_do_monitor` e `checkins_da_tarefa` (`in_progress`, `ok`/`error`, com o `monitor_config`; falha do envio só vai ao log). `execucao_monitorada` (E15-01) o usa; o corpo da tarefa, o registro `ExecucaoDaTarefa` e a repassagem da exceção não mudam.
- Dependência nova: `sentry-sdk` (2.75).

## Decisões e desvios

1. **`MONITORES_EXTERNOS`** está em `apps/operacao/monitores_externos.py` (a spec não fixa o módulo).
2. **A-4, "usuário só com `id`":** com `send_default_pii = False` o Sentry nem anexa o usuário; o teste confere que o usuário, se houver, só tem `id` (`<= {"id"}`), e o filtro direto confere que e-mail, nome e IP saem e o `id` fica.
3. **`test_nucleo_campos_decimais.py`** (carrega `prod.py` no processo) neutraliza `sentry_sdk.init` por `monkeypatch`, para a suíte nunca iniciar o Sentry de verdade; `_AMBIENTE_MINIMO` ganhou `SENTRY_DSN`.
4. **Melhorias registradas, não implementadas:** M-13 (token no caminho de `/convite/<token>/` e `/entrar/link/<token>/` chegaria ao Sentry, porque a regra 3 manda manter o caminho) e M-14 (o SDK 2.75 avisa que `send_default_pii` é obsoleto; a spec o fixa). Ambas em `docs/melhorias.md`.
5. O aviso `PytestWarning: ... database "test_organicos" is being accessed by other users` no fim de alguns arquivos já ocorria na E16-02 e nas fatias anteriores com o simulador; não foi causado por esta fatia.

## Verificação

`uv run pytest -q tests/tecnicos/test_observabilidade.py tests/ambiente tests/tecnicos/test_nucleo_campos_decimais.py tests/tecnicos/test_execucao_das_tarefas.py tests/tecnicos/test_alertas_de_atraso.py`: **72 passed**. `ruff` e `mypy` (537 arquivos) limpos. Suíte completa no fim da E16. Sem push, PR nem merge. Evidência no Sentry real (A-7 e A-8 da E16-08) fica para a E16-08.
