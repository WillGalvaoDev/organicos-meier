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
