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


---

## Revisão independente — agente 3 — 2026-11-17

Base avaliada: `52f8745870ebfa007ad6a94edf7f968ae472d04e`, branch
`e16-especificacoes`, diff contra `02f8e91`. Requisitos lidos antes do código:
AGENTS.md, especificação funcional v1.7, infraestrutura v1.8 e as oito specs e
acceptances da E16. Registros do implementador acima preservados integralmente.
A evidência global de execução está no parecer da E16-08 abaixo.

**Veredito da fatia: REPROVADO.**

### E16-R02 — Bloqueador — tokens e nomes chegam ao envelope do Sentry

Referências: infraestrutura §5, AGENTS.md §6, invariante da E16-03 (nenhum nome ou
token sai), regras 3/4 e A-4/A-5; `config/observabilidade.py:26`, `:58` e `:63`.
`_sem_consulta` conserva o caminho integral. `limpar_evento` não limpa novamente
`request`; a lista de chaves sensíveis tampouco inclui `nome`/`name`.

Reprodução independente, usando o fixture `tm` de
`tests/tecnicos/test_observabilidade.py` (SDK real, transporte em memória, sem rede):

```python
sentry_sdk.capture_event({"message": "erro", "request": {
    "method": "GET",
    "url": "https://exemplo.invalid/entrar/link/TOKEN-SINTETICO-DO-REVISOR/",
}})
assert "TOKEN-SINTETICO-DO-REVISOR" not in tm.texto()
# FALHA: token está em request.url do envelope capturado.

sentry_sdk.capture_event({"message": "erro", "extra": {"nome": "Pessoa Sintetica Revisora"}})
assert "Pessoa Sintetica Revisora" not in tm.texto()
# FALHA: nome está em extra.nome do envelope capturado.
```

São dois testes separados com fixture renovado. Não foram usados dados pessoais nem
credenciais reais. O caminho com segredo é usado pelas rotas de convite e link de
acesso; manter o caminho para diagnóstico não autoriza enviar sua credencial.
O registro M-13 é reclassificado: afeta segurança e, pelas próprias regras de
`docs/melhorias.md`, não pode ser melhoria não impeditiva. Não depende de decisão
comercial; deve ser corrigido conforme a precedência das fontes de verdade.

Retorno: sanitizar os segmentos sensíveis e dados identificáveis em todas as partes
permitidas do evento, com regressões que inspecionem o envelope completo. Conferir
igualmente breadcrumbs e cabeçalhos preservados. Os testes atuais de e-mail,
telefone, cookies, SQL, falha do filtro e check-ins não exercitam estes dois casos.

A-1 a A-13 têm testes locais; as opções, isolamento de falhas dos monitores e
check-ins com o mesmo ID foram conferidos. Evidência externa continua na E16-08.
O registro chama os três problemas pós-Green de defeitos do teste, mas o caso A-7
inclui correção de produção após uma falha observada; a descrição deve ser lida
assim, sem invalidar o ciclo observado. M-14 permanece melhoria, sem novo achado.

## Correção E16-R02 — tokens e nomes fora do envelope (implementador, 2026-11-17)

- **Red observado** (`tests/tecnicos/test_observabilidade.py`): 7 falhas — A-14 (`TOKEN-SINTETICO-1` em `request.url`, reprodução do revisor), A-15 (3 rotas), A-16 (`rotas_com_token_nao_cobertas` inexistente), A-17 (`Pessoa Sintetica Revisora` em `extra.nome`, reprodução do revisor), A-18. Guardas que passaram: A-19 (só o `User-Agent` já ficava) e A-20 (o padrão do SDK já é `url`; agora explícito).
- **Green** (`config/observabilidade.py`): `ROTAS_COM_SEGREDO` (`/entrar/link/`, `/convite/`, com o padrão `{token}` da rota preservado) aplicada a todo texto do evento, ao `request.url`, ao `transaction`, às mensagens, exceções, `logentry` e breadcrumbs; chaves de identificação pessoal por segmento (`nome`, `name`, `username`, `usuario`, `telefone`, `phone`, `celular`, `cpf`, `endereco`, `address`, `ip`) em `extra`, `tags`, `contexts` (menos `runtime`, `os` e `trace`) e no `data` dos breadcrumbs; `DjangoIntegration(transaction_style="url")`; `rotas_com_token_nao_cobertas` percorre o resolvedor e acusa rota nova com `token` sem cobertura (A-16).
- A prova é no texto serializado do envelope inteiro (regra 3-C). Os valores sintéticos dos testes ficam em constantes fora da linha que levanta o erro, porque o SDK anexa ao evento as linhas de código ao redor da pilha.
- M-13 encerrada em `docs/melhorias.md` ("Reclassificação pelo revisor"), com o commit `d254321`.
- Sem push, PR nem merge. Código corrigido no commit `281d191` (os commits seguintes só mudam documentos).


## Revalidação independente — 2026-11-18 — commit 5f12d21

**APROVADO no escopo corrigido; R02 encerrado.** A-14 a A-20 confrontados com a limpeza do evento e executados na suíte completa: envelope serializado sem tokens das três rotas, dados pessoais nas chaves previstas removidos, contexto técnico preservado, guarda para novas rotas, cabeçalhos restritos e transaction_style explícito. Testes WSGI exercitam as três rotas e falha real na view com transporte em memória. Registros Red/Green conferidos; não é evidência de envio ao Sentry real. Encerramento de M-13 confirmado para este escopo; demais melhorias seguem seu registro. Evidências globais na E16-08.
