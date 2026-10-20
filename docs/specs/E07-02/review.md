# E07-02 — Revalidação independente — 2026-10-20

**Parecer da fatia: APROVADO no escopo local, sobre `636a94cacde2764e297967189c5904b58f72dde6`, branch `e07-implementacao`. E07 global: REPROVADO por R06 (IMPORTANTE).**

Matriz revalidada: **A-1 a A-10**. Configuração, bloqueio em produção e regressões preservados. A aprovação local não aprova a entrega integrada.

O [parecer consolidado](../E07-01/review.md) registra a matriz das seis fatias, fontes, análise das correções, encerramento de R01–R05, achado R06 com prova reproduzível e R07 (melhoria de processo: Red de R03 usou `-k`, contrariando a prevenção vigente, sem evidência de critério omitido).

Verificação independente: suíte completa **1937 passed in 175.77s**; dez provas anteriores passam; prova nova de R06 falha (**1 failed, 10 passed in 5.85s**). `ruff check`, `ruff format --check` (257 arquivos), `mypy` (300 arquivos) e verificação de migrações passaram. Comandos, logs, adaptações justificadas das provas e código completo estão no parecer consolidado. As tabelas Red/Green foram conferidas; a revisão atual não é prova de execução histórica do Red.

R06: após timeout, uma sessão do simulador permanece ativa, a guarda informa zero pendências e a thread grava uma aprovação depois da liberação da trava. É necessário estender as garantias de E01-05 ao novo alias e revalidar antes da aprovação global. Somente pareceres foram alterados nesta revisão; conteúdo anterior preservado integralmente abaixo.

---

## Histórico integral preservado

# E07-02 — Revisão independente — 2026-10-20

**Veredito desta fatia: APROVADO. Veredito global da E07: REPROVADO.**

Base: `d6e4d2095ac8f1128b1a315fd81e5ab579488aa3`, branch `e07-implementacao`. A-1 a A-10: configuração, bloqueio de produção com simulador, segredo e ajustes autorizados dos testes conferidos; nenhum achado local aberto.

O [parecer consolidado em E07-01](../E07-01/review.md) contém fontes, matriz das seis fatias, análise dos registros de TDD, classificação e reprodução de R01 a R05, comandos e limitações. Verificação independente: **1902 testes aprovados** na suíte; provas adicionais: **8 falhas e 2 aprovações**. Ruff, formatação, mypy e verificação de migrações passaram. A suíte verde não cobre as lacunas reproduzidas. Nenhum arquivo de produção ou teste versionado foi alterado pelo revisor.

O registro anterior abaixo foi preservado integralmente e não substitui o veredito independente. A entrega integrada requer correção e nova revisão antes do encerramento.

---

## Registro do implementador preservado

# E07-02 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§15), infraestrutura v1.7 (4.1, 5, 7), `spec.md` e `acceptance.md` da fatia, E04-04 e E07-01.

## Arquivos

- `config/settings/base.py`: `PROVEDOR_PAGAMENTOS` (padrão `simulador`, valor exato, qualquer outro levanta `ImproperlyConfigured`).
- `config/settings/dev.py` e `test.py`: `AMBIENTE` `desenvolvimento` e `testes` (o segredo dos avisos já vinha da E07-01).
- `config/settings/prod.py`: `AMBIENTE` obrigatório (`homologacao` ou `producao`), recusa de `producao` com o simulador e `SEGREDO_AVISOS_SIMULADOR` obrigatório com o simulador, sem padrão.
- `apps/pagamentos/provedor.py`: `obter_provedor()` recusa `AMBIENTE == "producao"`.
- `.env.example`: a linha comentada de `PROVEDOR_PAGAMENTOS`.
- Testes novos: `tests/tecnicos/test_configuracao_pagamentos.py` (A-1 a A-8, subprocesso) e `test_producao_recusa_o_simulador_em_obter_provedor` em `test_pagamentos_simulador.py` (A-9).

Sem andaime e sem migração.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_configuracao_pagamentos.py tests/tecnicos/test_pagamentos_simulador.py tests/tecnicos/test_configuracao_producao.py tests/tecnicos/test_nucleo_campos_decimais.py -q`: **15 failed, 51 passed**, todas as falhas por asserção (`assert 0 != 0` no código de saída, `assert None == 'homologacao'`, `DID NOT RAISE`).

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_producao_com_o_simulador_nao_carrega` (`acceptance`) | falhou: `assert 0 != 0` (a produção carregava) |
| A-2 | `test_producao_sem_provedor_configurado_nao_recebe_o_simulador` | falhou |
| A-3 | `test_nem_a_web_nem_o_worker_sobem_em_producao_com_o_simulador` (`check` e `procrastinate worker --help`) | falharam (saída zero) |
| A-4 | `test_homologacao_usa_o_simulador` | falhou: `assert None == 'homologacao'` |
| A-5 | `test_ambiente_invalido_nao_carrega` (ausente, `teste`, `Producao`) | falharam (saída zero) |
| A-6 | `test_provedor_diferente_de_simulador_nao_carrega` (3 valores, dev e prod) | falharam (`AssertionError: mercado_pago` etc.) |
| A-7 | `test_homologacao_exige_o_segredo_dos_avisos` | falhou |
| A-8 | `test_dev_e_testes_tem_ambiente_provedor_e_segredo` | falharam (`None == 'desenvolvimento'`, `None == 'testes'`) |
| A-9 | `test_producao_recusa_o_simulador_em_obter_provedor` | falhou (`DID NOT RAISE`) |
| A-10 | arquivos existentes | passaram no Red (ainda sem `AMBIENTE` obrigatório); após o Green, 5 deles falharam pelo motivo novo e receberam o ajuste autorizado abaixo |

## Green

Os quatro arquivos: **66 passed** (já com o ajuste autorizado). Suíte completa: **1843 passed** (eram 1828). `ruff check`, `ruff format --check`, `mypy .` sem erros.

## Ajuste autorizado nos testes existentes (A-10)

Cinco testes falharam, pelo motivo novo (`AMBIENTE deve ser 'homologacao' ou 'producao'.`): quatro em `test_configuracao_producao.py` (`test_producao_cookies_seguros`, `test_validador_de_semelhanca_...`, `test_producao_sem_a_variavel_deixa_o_whatsapp_desligado`, `test_producao_recusa_o_simulador_de_whatsapp`) e `test_app_de_testes_fora_da_producao` em `test_nucleo_campos_decimais.py`. Diff:

- `test_configuracao_producao.py`: `_AMBIENTE_MINIMO` ganhou `"AMBIENTE": "homologacao"` e `"SEGREDO_AVISOS_SIMULADOR": "segredo-de-teste"`.
- `test_nucleo_campos_decimais.py`: `monkeypatch.setenv` das duas variáveis antes da importação e `importlib.reload` quando o módulo já estava importado (`import sys` acrescentado).

Nenhuma asserção mudou. Nenhum outro teste falhou.

## Decisões técnicas

- Os testes de carregamento removem do ambiente herdado as variáveis desta fatia, para o `.env` local não interferir; `MINIMO` do arquivo novo é o `_AMBIENTE_MINIMO` sem elas, e cada teste as define.
- O erro de `AMBIENTE` ausente usa `env("AMBIENTE", default="")` para dar a mensagem pedida pela spec, em vez da mensagem genérica da biblioteca.

## Limites da verificação

Subprocesso com Python, sem a hospedagem. A homologação no Fly.io (E16) e o provedor real (fase 2a) são de outras etapas. Nenhuma mutação aplicada nesta fatia.
