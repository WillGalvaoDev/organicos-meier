# E04-07 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia e a E04-02 a E04-05.

## Arquivos

- `apps/notificacoes/consultas.py` (novo): `envios_para_administracao`, `contar_falhas`, `filtros_validos` e os rótulos de situação, canal e tipo.
- `apps/notificacoes/views.py` (`envios_lista`, `envio_detalhe`), `config/urls.py`, `templatetags/notificacoes.py` (filtro `valor_do_mapa`).
- `templates/notificacoes/envios_lista.html` e `envio_detalhe.html`; `apps/contas/views.py` e `templates/administracao/painel.html` (indicador de falhas e link para a lista).
- Testes: `tests/tecnicos/test_notificacoes_administracao.py` (novo).

## Decisões técnicas

- Rotas só `GET` (`require_GET`, 405 nos demais métodos) e com a política `administrador` (`somente_administrador`).
- Filtros inválidos (`situacao`, `canal`, `tipo`) são ignorados por `filtros_validos`, sem erro; o formulário mostra "todos".
- Sem N+1: a lista usa `select_related("conta")` e uma subconsulta (`OuterRef`) para a classe do último erro; o detalhe faz um número fixo de consultas.
- "Aceito pelo serviço" é um rótulo da consulta (`ROTULOS_SITUACAO`), e não o rótulo do modelo (`SituacaoEnvio.ENVIADO`), para não criar migração só por texto.
- Detalhe: nos e-mails de acesso o corpo aparece como "(não armazenado: contém link de acesso)"; o número do WhatsApp não aparece, porque não é gravado; o destinatário é o nome da conta ou, no convite, o e-mail de destino.
- Painel inicial da administração: ganhou o link "Envios" e o indicador "Envios com falha: <n>" (só com `n > 0`).

## TDD

**Red.** Andaime (`consultas.py` devolvendo vazio/zero e views com corpo vazio): `uv run pytest tests/tecnicos/test_notificacoes_administracao.py -q` deu **14 failed, 3 passed**, por asserção (listas, filtros, detalhe, indicador e mensagens ausentes). Passaram já no Red o controle de acesso (a decoração das views estava no andaime), o teste "sem falhas" e a contagem de consultas da lista (a lista vazia não tem N+1); este último só passa a ter sentido no Green.

**Green.** Mesmo arquivo: **17 passed**. Suíte completa: **1385 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_lista_paginada_e_ordenada` |
| A-2 | `test_filtros_combinaveis_e_valores_invalidos_sao_ignorados` |
| A-3, A-4 | `test_detalhe_com_tentativas`, `test_corpo_de_email_de_acesso_nao_e_armazenado` |
| A-5 | `test_indicador_de_falhas_na_pagina_inicial`, `test_sem_falhas_o_indicador_nao_aparece` |
| A-6 | `test_a_lista_nao_cai_em_n_mais_um` |
| A-7, A-8, A-9 | `test_quem_nao_e_administrador_nao_consulta`, `test_so_leitura_e_id_inexistente`, `test_listas_vazias` |
| A-10 | `test_permissoes_politica_rotas.py` (varredura existente) |

## Limites da verificação

Cliente HTTP do Django, sem navegador. A consulta é só de leitura; os alertas ativos e o painel consolidado são da E15.
