# E14-08 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_retirada_ponta_a_ponta.py` (arquivo inteiro, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | **Não se aplica**, como na E13-08: a fatia não cria código de produção; os testes integrados verificam o que as fatias E14-01 a E14-07 construíram por TDD. Os 11 testes passaram na primeira execução |
| Mutações (prova de que os testes detectam defeito, sem substituir o Red) | (1) tirar a conferência do saldo da ocorrência (`if quantidade_afetada > saldo` → `if False`): **1 failed** (A-9, a corrida T-18 pela rota); (2) a liberação deixar de liberar as parcelas `em_pedido`: **2 failed** (A-5 e A-6, o estoque da nova rodada); (3) tirar a recusa do descarte antes do prazo: **11 passed**, isto é, **este ponto não é detectado aqui**; ele é coberto por `test_retirada.py` (A-5) e pelas telas (A-19). Todas as mutações foram revertidas e a árvore conferida com `git status` |
| Final | **11 passed**; `ruff` e `mypy` limpos |

## O que foi feito
- `tests/tecnicos/test_retirada_ponta_a_ponta.py`: o AE com a aprovação pela tela da E11-07 e o endereço pela tela da E14-03, as ações do administrador pelas rotas da E14-06, da E13-06 e da E10 (`entrar_de_novo` a cada avanço do relógio), `processar_chamadas()` e o invariante financeiro (`verificar_invariante_agora`) ao fim de cada critério.
- A-1 a A-3 (entrega parcial, ocorrência, liberação recusada e aceita, aviso, devolução concluída no simulador, repasse de 150,00 e recusa de 0,01); A-4 (ocorrência depois do repasse e da liberação, parte de produtos sem cobertura, cobertura pela reserva, devolução de 11,79); A-5 e A-6 (nova rodada imediata, retirada antiga, prazo e descarte); A-7 e A-8 (rodada liberada não cancela; cancelamento com ocorrência anterior, 70,76); A-9 (T-18 pela rota, com transações reais); A-10 (suspenso retira); A-11 (comprador sem acesso e portal do fornecedor, nos estados dos A-4, A-6 e A-7); A-12 (`_invariantes` ao fim de cada teste: congelado igual, `reembolsado + retirado + descartado ≤ quantidade`, invariante financeiro).

## Limitações
- A cobertura pela reserva (A-4) usa os serviços `registrar_aporte` e `designar_reserva` (E09-06), como a E13-08, e não a tela; a autorização da devolução e o repasse passam pelas telas.

## Verificação da etapa inteira

- `uv run pytest -q` (suíte completa): **3260 passed**, 0 failed (513 s). A falha preexistente M-10 foi corrigida na E13 (PR #86).
- `uv run ruff check --no-cache .` e `ruff format --check .`: limpos; `uv run mypy .`: sem erros (497 arquivos; dois ajustes de tipo nos testes da E14-03 depois da primeira passada); `makemigrations --check`: sem mudanças.
- Migrações novas da E14: `0016` (recebimento), `0017` (ocorrência), `0018` (endereço), `0019` (liberação), `0020` (retirada e descarte), todas com `instalar_protecao_so_insercao`.
- Sem push, PR ou merge: aguarda o parecer do agente 3. O PR à `main` atualizará o README (Parte 1, nas duas línguas) e a milestone 14.
