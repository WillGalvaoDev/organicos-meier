# E16-05 — Registro do implementador

Agente 2.

## Red (observado antes do código de produção)

- `uv run pytest -q tests/tecnicos/test_conferir_restauracao.py`: **falhou em todos os testes** com `CommandError: Unknown command: 'conferir_restauracao'` (o comando não existia; cobre A-1 a A-12).
- `uv run pytest -q tests/ambiente/test_artefatos_de_implantacao.py`: **1 failed, 3 passed** — o A-13 (`docs/operacao/restauracao.md` ausente).

## Green

- `apps/operacao/conferencia.py`: sete seções (`Ponto recuperado`, `Invariante financeiro`, `Estoque`, `Prazos encerrados`, `Pendências com o provedor`, `Conciliação`, `Reconferir com o extrato`) com `OK`, `ATENÇÃO` ou `FALHA`. Reutiliza `obrigacoes_de_terceiros` e `consultar_saldo` (E09-07, sem abrir nem resolver alerta), `total_reservado`, `prazos_encerrados` (E15-05) e o cálculo de dias da E09-07. Roda inteiro numa transação com `SET LOCAL transaction_read_only = on`, desfeita no fim (`set_rollback(True)`), de modo que uma escrita em qualquer seção falha o comando.
- `conferir_restauracao` (`--antes-de AAAA-MM-DDTHH:MM`, Brasília): saída 1 com `FALHA`, 0 com só `ATENÇÃO`, 2 para instante inválido ("Instante inválido: use AAAA-MM-DDTHH:MM."). A última linha é "Conferência: n falha(s), m atenção(ões).".
- `docs/operacao/restauracao.md`: as dez seções da regra 6, os dois caminhos, o roteiro cronometrado e a tabela "Registro dos testes" (sem linhas ainda: o teste é da E16-08).

Os 12 testes do comando passaram na primeira execução com o código completo (o Red foi só o comando ausente, descrito acima).

## Decisões e desvios

1. **Ponto de extensão para o A-3:** a lista `apps.operacao.conferencia.SECOES` (funções `(instante, antes_de) -> Secao`). O teste acrescenta uma seção que grava uma `EntradaAuditoria` e espera `DatabaseError` (transação somente leitura).
2. **Por que `SET LOCAL ... = on` e desfazer a transação:** `SET TRANSACTION READ ONLY` exige ser a primeira instrução e a transação do teste já tem consultas; o `SET LOCAL` vale dentro de um savepoint e é revertido pelo rollback, então nada vaza para o resto de um teste nem para a conexão.
3. **Valor de cada movimento do extrato:** soma das transferências do movimento (para os cinco tipos listados, uma transferência por movimento).
4. **Devoluções "não concluídas no provedor":** toda `ParcelaDeDevolucao` fora de `concluida` e `concluida_fora_da_plataforma` (inclui falha definitiva e elegível para excepcional).
5. **Estoque:** só `EstoqueDaRodada` com limite, de rodada não cancelada; o reservado é `total_reservado(produto)`. No A-6 o limite foi baixado por `update()` no banco depois da reserva, porque o serviço de reserva não deixa passar do estoque.
6. **Dias sem conciliação:** reaproveita a fórmula de `conciliar_dias_pendentes_agora` (primeiro dia pendente = seguinte à última conciliação, ou o dia anterior na primeira vez), sem refatorar a E09-07.
7. **A-8:** o número de `Envio` pendentes depende do arranjo (a devolução gera avisos); o teste confere a contagem impressa contra a contagem do banco, mais "pelo menos 2", e confere as de chamada e devolução (1 e 1).
8. **A-12:** o teste compara nome, e-mail e telefone de cada conta que não é administradora com o texto do relatório; não há seção que liste compradores.
9. **Prefixo `test_conferir_`** em `PREFIXOS_COM_SIMULADOR`.

## Verificação

`uv run pytest -q tests/ambiente tests/tecnicos/test_conferir_restauracao.py`: **42 passed**. `ruff` e `mypy` (547 arquivos) limpos. Suíte completa no fim da E16. Sem push, PR nem merge. A execução do teste cronometrado e o RTO são da E16-08.
