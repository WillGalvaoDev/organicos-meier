# E15-02 — Registro do implementador

Agente 2.

## Red

- Commit `e207368`: `uv run pytest tests/tecnicos/test_alertas_operacionais.py` → 14 falhas e 1 passando. O A-8 (alerta financeiro como antes) já passava: é guarda de regressão. As demais falham pela ausência de `apps.operacao.verificacao`, do tipo `tarefa_atrasada` e da tarefa `verificar_operacao`.

## Green

- `apps/operacao/tipos.py`: `Natureza`, `Classificacao`, registro dos tipos, `link_do_alerta` e `natureza_do_alerta`.
- `apps/operacao/verificacao.py`: `registrar_verificacao`, `VERIFICACOES`, `verificar_operacao_agora` (uma transação por verificação, registros que faltam criados no começo).
- `apps/operacao/atraso_de_tarefa.py`: o tipo e a verificação de `tarefa_atrasada`; `apps/operacao/tarefas.py`: a tarefa `verificar_operacao` (`*/5 * * * *`, `queueing_lock`), com a entrada "Verificação operacional" (5 e 15 min) no catálogo.
- `apps/financeiro/alertas.py`: `abrir_alerta` aceita os tipos operacionais (gravidade, título, corpo e link da classificação) e emite `Evento.ALERTA_OPERACIONAL`; os financeiros seguem iguais. `apps/financeiro/models.py` (tipo `tarefa_atrasada`) e `apps/notificacoes/eventos.py` (evento só do administrador, site e e-mail); migrações `financeiro` e `notificacoes`.
- Resultado: `15 passed` neste arquivo.

## Desvios e pontos para o revisor

1. **Arranjo AO inviável (especificação).** O AO pede ADM1 e ADM2 ativos e ADM3 suspenso. O banco admite um único administrador e sempre ativo (`conta_administrador_unico` e `conta_administrador_ativo`, `apps/contas/models.py`; funcional §1: "Há um único administrador"). Os testes usam só ADM1 e conferem uma notificação e um e-mail para ele; "nada para ADM3" não tem o que conferir, e "uma notificação por administrador" (A-12) vira uma para ADM1. O A-9 ("sem administrador ativo") roda sem nenhum administrador. **Devolvido ao especificador**: ajustar o AO (ou decidir mudar a regra do administrador único, decisão do responsável). O código percorre todos os administradores ativos e não depende do número.
2. **Teste da E09-03 atualizado.** `test_o_catalogo_do_evento_novo` (A-11 da E09-03) comparava o conjunto de eventos do administrador com dois eventos; a regra 3 desta fatia cria um terceiro, só do administrador. Acrescentei `Evento.ALERTA_OPERACIONAL` ao conjunto esperado, mantendo a igualdade. Mudança exigida pela spec, não afrouxamento.
3. **Corpo do `tarefa_atrasada` e os dados.** A regra 9 tem dois corpos (com e sem conclusão anterior), mas os dados listados não dizem qual vale. Para não acrescentar campo aos dados, `_corpo` consulta o `ExecucaoDaTarefa` (`ultima_conclusao_em` nulo). Se o revisor preferir um campo em `dados`, é uma mudança pequena; sem decisão comercial.
4. **Ponto de pausa do A-12.** O teste pausa depois de `abrir_alerta` chamado pela verificação (`apps.operacao.verificacao.abrir_alerta`). No teste A-6 e A-7 as verificações de teste entram por substituição do dicionário `VERIFICACOES`.
5. **Segundo teste existente atualizado.** `test_a_matriz_de_canais_e_a_da_especificacao` (E04-01) transcreve a matriz de eventos; acrescentei a linha `("alerta_operacional", administrador, {site, e-mail})`, pela regra 3 desta fatia. Nenhuma asserção foi removida.

## Verificação

- Suíte completa antes deste ajuste: 3296 passed e 1 failed (este teste); depois, `tests/tecnicos/test_notificacoes_eventos.py` e `test_financeiro_alertas.py` passam. `mypy .` (513 arquivos) e `ruff` limpos.
