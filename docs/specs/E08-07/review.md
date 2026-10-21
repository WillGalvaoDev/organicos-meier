# E08-07 — Revisão independente do agente 3 — 2026-10-21

**REPROVADO sobre `2714a6a2acaf88cc69e02345facf2a2403a66374`, branch `e08-implementacao`. E08 global: REPROVADO.**

Matriz examinada: **A-1 a A-8**, a partir de spec.md/acceptance.md e das fontes superiores, antes de avaliar o código. Os oito testes da tela passam. R05 impede o gate de integração: a suíte completa tem um teste vermelho. A origem correta é E07-03 A-12, que restringe apps.pagamentos; o teste incluiu também apps.simulador_pagamentos. A E08-07 já autoriza as cinco rotas: ajustar a prova preservando a proibição de registro manual é encaminhamento técnico, sem decisão comercial nova.

TDD declarado: **7 failed, 24 passed; 404 de ausência de rota e controles já verdes documentados.** O revisor confere registro, testes e diffs; não presenciou a execução histórica. Reexecuções atuais não substituem evidência de Red anterior à implementação.

Verificações independentes: suíte completa **1 failed, 2129 passed in 292.98s**, sem exclusões; provas adicionais **5 failed, 2 passed in 17.36s**; lint, formatação (288 arquivos), tipos (338 arquivos) e verificação de migrações passaram. A falha versionada é a de rotas descrita em R05; as cinco falhas adicionais correspondem a R01, R02 (duas variantes), R03 e R04.

O [parecer consolidado](../E08-01/review.md) contém matriz das sete fatias, referências, classificação, resultados, código completo das provas, limites e encaminhamentos R01–R07. R04 requer decisão sobre pedido zero, e R06 requer evidência histórica ou tratamento autorizado; as perguntas foram encaminhadas durante a revisão. R07 está no registro central como M-3.

Somente documentação foi alterada pelo revisor, sem correção silenciosa de produção ou testes. Histórico do implementador preservado integralmente abaixo. Próximo gate: correções/comprovações e nova revisão independente.

---

## Registro anterior integralmente preservado

# E08-07 — Registro do implementador (2026-10-20)

Status: implementada, **com um conflito de testes em aberto** (abaixo); **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia, os controles do simulador (E07-01), a rota de avisos (E07-05) e os testes de fronteiras de `test_pagamentos_fronteiras.py`.

## Arquivos

- `apps/simulador_pagamentos/views.py` e `urls.py`: a lista e as quatro ações; `config/urls.py` inclui as rotas em `administracao/simulador-pagamentos/`.
- `templates/simulador_pagamentos/lista.html`.
- Teste: `tests/tecnicos/test_simulador_pagamentos_tela.py` (A-1 a A-7). O A-8 é o teste existente `test_so_a_interface_e_o_proprio_simulador_importam_o_simulador`.

Nenhuma mudança de modelo nem migração.

## Andaime

Nenhum: a rota e a view não existiam, então o Red foi de rota ausente (404).

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_simulador_pagamentos_tela.py tests/tecnicos/test_pagamentos_fronteiras.py tests/tecnicos/test_permissoes_politica_rotas.py -q`: **7 failed, 24 passed**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_a_lista_mostra_as_cobrancas_e_os_botoes` | `assert 404 == 200` |
| A-2 | `test_aprovar_e_entregar_quita_o_pedido` | `IndexError: list index out of range` (sem redirecionamento: a rota não existe) |
| A-3 | `test_recusar_e_expirar` | falhou: a mensagem de sucesso não aparece (a rota não existe) |
| A-4 | `test_acao_que_a_situacao_nao_permite_responde_409` | `assert 404 == 409` |
| A-5 | `test_desconhecida_e_metodo_errado` | `assert 404 == 405` (a parte do 404 já "passava" por ausência da rota) |
| A-6 | `test_outros_papeis_e_anonimos_sao_recusados` | `AssertionError: ('get', '/administracao/simulador-pagamentos/')` (404 em vez de 302 ou 403) |
| A-6 | `test_as_cinco_rotas_declaram_a_politica_de_administrador` | `Resolver404` |
| A-7 | `test_sem_o_simulador_configurado_as_rotas_nao_existem` | **passou no Red**: 404 por ausência da rota; vira prova real depois do Green, quando só a configuração decide o 404 |
| A-8 | `test_so_a_interface_e_o_proprio_simulador_importam_o_simulador` | **passou** (regressão, antes e depois) |

## Green e verificações

- `test_simulador_pagamentos_tela.py`: **8 passed**. Conjunto `-k "pagamentos or simulador or permissoes"`: **209 passed, 1 failed** (o conflito abaixo).
- `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Verificação final da milestone E08 (as sete fatias)

- `uv run pytest -q`, com o teste do conflito abaixo desmarcado (`--deselect`): **2129 passed** em 176,77 s (a suíte tinha 1945 ao fim da E07). Com ele, a suíte tem **1 teste vermelho**.
- `ruff check`, `ruff format --check`, `mypy .` (338 arquivos) e `makemigrations --check --dry-run` sem erros.
- A varredura de `float` (E08-01 A-11) cobre os módulos de dinheiro e quantidade, inclusive `apps/pedidos`.

## Conflito de testes em aberto (decisão necessária)

`tests/tecnicos/test_pagamentos_fronteiras.py::test_nenhuma_rota_comando_ou_admin_registra_pagamento` (E07-01, A-12, cenário 37) exige que **toda rota cujo módulo comece por `apps.pagamentos` ou `apps.simulador_pagamentos` se chame `pagamentos_avisos`**. A E08-07 manda colocar as views da tela em `apps/simulador_pagamentos/views.py` e dá cinco nomes novos (`simulador_pagamentos_*`). Os dois textos não podem valer juntos.

- **Referência:** E08-07 (Decisões técnicas, "Código dentro do simulador") e E07-01 A-12.
- **Impacto:** com a implementação conforme a E08-07, esse teste falha com `{'simulador_pagamentos_entregar', …} <= {'pagamentos_avisos'}`. Não alterei o teste.
- **O que as rotas fazem:** mudam o estado do **provedor** simulado (aprovar, recusar, expirar, entregar avisos); não registram nenhum pagamento no sistema, que continua só pela sincronização. O objetivo do cenário 37 é preservado.
- **Opções:** (a) o especificador ajusta o teste para permitir as cinco rotas do simulador pelo nome e manter a proibição de qualquer outra (recomendo); (b) mover as views para fora dos dois módulos, contrariando a E08-07 e a varredura de importações (A-8).
- **Decisão necessária:** qual das duas. Até lá, a suíte tem este único teste vermelho.

## Decisões técnicas

- **Só com o simulador configurado.** A checagem é `settings.PROVEDOR_PAGAMENTOS == "simulador"`, feita dentro da view, depois da política: comprador, fornecedor e anônimo são recusados antes (302 ou 403); o administrador recebe 404 sem o simulador.
- **Auditoria.** Cada ação grava `simulador.<ação>` (autor, com o `id_externo`) apontando para a cobrança; a entrega grava `simulador.entregar_avisos` com a quantidade, apontando para a conta do administrador. Nenhum dado pessoal.
- **Botões.** "Aprovar" em `pendente`, `cancelado` e `expirado`; "Recusar" e "Expirar" só em `pendente`. A situação por extenso é Pendente, Aprovada, Recusada, Cancelada ou Expirada.
- **Aviso do teardown.** O `PytestWarning` de encerramento do banco de testes ("is being accessed by other users") já aparecia com `test_pagamentos_simulador.py`, antes desta fatia; não é desta fatia.

## Limites da verificação

Postgres real e cliente HTTP do Django; sem navegador, sem o worker como processo e sem rede. Nenhuma mutação aplicada.

---

## Registro do implementador — correções R01 a R06 (2026-10-21)

Status: implementadas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Fontes lidas antes de editar: o parecer em `docs/specs/E08-01/review.md` e as seções de correção de cada `spec.md` e `acceptance.md` (commit `7a1fb49`).

### R05 — teste de fronteira alinhado ao requisito

Só teste: `tests/tecnicos/test_pagamentos_fronteiras.py` e duas urlconfs de apoio (`tests/apoio/urls_rota_extra_simulador.py` e `urls_rota_extra_pagamentos.py`). Nenhum código de produção mudou.

- **Falha de partida (linha 87):** `uv run pytest tests/tecnicos/test_pagamentos_fronteiras.py -q`: **1 falhou, 7 passaram**, `test_nenhuma_rota_comando_ou_admin_registra_pagamento`, com os cinco nomes `simulador_pagamentos_*` no conjunto que só admitia `pagamentos_avisos`.
- **Teste alinhado:** igualdade exata por app (`apps.pagamentos` = `{pagamentos_avisos}`; `apps.simulador_pagamentos` = as cinco rotas desta fatia), mais "sem admin" e "sem pasta `management`"; o comentário cita E07-03 A-12, cenário 37 e E08-07.
- **Prova negativa (A-9):** `test_uma_rota_a_mais_em_qualquer_dos_dois_apps_e_recusada[simulador]` e `[pagamentos]`. Cada um usa uma urlconf de teste com uma rota a mais, exige `AssertionError` e confere que o nome da rota aparece na mensagem. **Passaram na primeira execução**, escritas junto com o alinhamento; a sensibilidade vem de a mensagem conter o nome da rota a mais.
- **Resultado:** `test_pagamentos_fronteiras.py`: **10 aprovados**. `test_so_a_sincronizacao_escreve_nos_registros_de_pagamento` (M-2) não foi tocado.
