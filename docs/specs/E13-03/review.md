# E13-03 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal_reenvio.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `590cfbc` | **19 failed**: o módulo `apps.pedidos.reenvio_do_pedido_formal` não existe |
| Green | `9ab5fed` | **19 passed** (inclui A-15 a A-17 com transações reais) |

## Ponto para o especificador
- **Chave da auditoria.** O critério A-14 pede a auditoria com "o token". O filtro de segredos da auditoria (`registrar_auditoria`) recusa qualquer chave com o termo `token` (`ValueError: chave com termo reservado a segredo`). O valor (o UUID do acionamento) é gravado sob a chave `acionamento`. O token do reenvio não é segredo (é só um identificador de idempotência), mas mudar o filtro seria alterar a regra da E01. O teste A-14 confere `{"pedido_formal", "numero", "resultado", "acionamento"}`.

## Decisões técnicas
- `pode_reenviar` e a conferência prévia leem o estado gravado sem trava; a conferência sob as trava repete a leitura. Durante o ciclo automático o reenvio é recusado sem esperar, e entre reenvios a trava do envio é esperada (`select_for_update(of=("self",))`).
- `IntegrityError` no token: a transação é desfeita e a tentativa existente é relida (regra 11).


## Revisão independente — agente 3 — 2026-11-13

Base auditada: `9af6251`, branch `e13-especificacoes`, sobre `9851bb5`. Requisitos lidos antes do código: especificação funcional v1.7, infraestrutura v1.8 e os `spec.md`/`acceptance.md` das oito fatias. Os registros do implementador acima foram preservados integralmente.

**Veredito da fatia: REPROVADO — E13-R01 aberto.**

`test_pedido_formal_reenvio.py`: **19 testes passaram**, cobrindo A-1 a A-17. Confirmados o snapshot, a recusa durante o automático/cancelamento, a consulta prévia, a serialização para o mesmo pedido e a auditoria sob a chave `acionamento`, autorizada pelo esclarecimento de 2026-11-09. O A-9 testa reutilização entre pedidos apenas sequencialmente; A-15/A-16 usam um único pedido formal.

### E13-R01 — Bloqueador: token global permite dois envios e perde o registro de um deles

- **Requisitos:** especificação funcional §10 (proteção contra duplicação e todas as tentativas auditáveis), infraestrutura §4.14/T-29; E13-03 regras 4, 8, 11 e 12, A-9/A-15; AGENTS.md §6.
- **Referência:** `apps/pedidos/reenvio_do_pedido_formal.py:154-190`, envio na linha 173 antes do registro com token na linha 178; tratamento do `IntegrityError` nas linhas 147-151.
- **Reprodução:** criar dois AF-sucesso de fornecedores distintos. Fazer dois reenvios em conexões diferentes, para pedidos diferentes, com o mesmo UUID; sincronizar a entrada em `enviar_email`. Cada chamada trava seu próprio envio e sua própria rodada, e ambas encontram o token ainda inexistente.
- **Resultado observado:** **dois e-mails aceitos**, **uma tentativa manual persistida**, uma chamada bem-sucedida e outra `ReenvioRecusado(token_invalido)`. A restrição UNIQUE atua depois do efeito externo: desfazer a transação não recolhe o e-mail já aceito, e a tentativa/auditoria do perdedor desaparece.
- **Evidência:** `test_token_global_nao_envia_dois_pedidos_concorrentes` falhou com `assert 2 == 1`. Banco PostgreSQL real, simulador de pagamentos e backend locmem; não houve envio externo real. Código integral em [E13-08](../E13-08/review.md).
- **Correção esperada:** garantir exclusão/posse do token global antes do efeito externo, inclusive entre pedidos diferentes. Preservar a serialização por pedido, a recusa do token pertencente a outro pedido e a idempotência do mesmo pedido. Adicionar Red/Green para os dois pedidos concorrentes e manter A-9/A-15/A-16 e a rota HTTP verdes. A estratégia técnica pode ser resolvida pelo implementador a partir das regras aprovadas.

Não é a limitação L-13: não houve crash nem falha de entrega posterior; é uma corrida normal que a aplicação deixa ocorrer. Nenhuma correção de produção foi feita pelo revisor.

TDD histórico: Red `590cfbc` contém os testes antes do Green `9ab5fed`, seguido de `9f2cf8c` para imports. Conferidos os commits e o registro de 19 falhas/19 sucessos. O Red da correção de E13-R01 ainda é necessário.

## Correção do E13-R01 — implementador — 2026-11-13

Especificação: `a858d0d` (regras 7, 8 e 11 corrigidas; A-19 e A-20; E13-08 A-9).

- **Red (`cfc54f2`):** `uv run pytest tests/tecnicos/test_pedido_formal_reenvio.py` → 2 falhas (A-19 e A-20), 19 passaram. No A-19 a segunda chamada não esperou o token e enviou o e-mail do PF2; a asserção `esperar_outra_conexao_na_trava()` da primeira estourou dentro de `enviar_email`, e `_tentar` a converteu em tentativa `falha` (o `except Exception` do envio), de modo que a chamada acabou recusada com `token_invalido` pelo `UNIQUE` depois do e-mail do PF2: o defeito do parecer (efeito externo antes da posse do token), por outro caminho de assertiva. No A-20 o teste falhou pelo mesmo motivo (nenhuma conexão esperando o token).
- **Green (`36efba3`):** `_tomar_a_posse_do_token`, em `apps/pedidos/reenvio_do_pedido_formal.py`, é a primeira instrução de `_tentar`: `pg_advisory_xact_lock(7151013, hashtext(<uuid>))` (forma de dois inteiros, chave diferente da `CHAVE_DA_TRAVA_DO_SALDO`), antes do envio e da rodada. Sem migração nem dependência. As conferências do token e da regra 5 seguem relidas sob as travas; o `IntegrityError` ficou como defesa. Resultado: `test_pedido_formal_reenvio.py` 21 passaram.
- **A-9 pela rota (`f9900d1`, E13-08):** teste escrito depois do Green (**Red tardio**). Para comprovar o Red, a linha `_tomar_a_posse_do_token(token)` foi trocada temporariamente por `pass`: o teste falhou (`assert 400 == 302`: o primeiro POST recebeu a recusa), e com a linha restaurada `test_pedido_formal_ponta_a_ponta.py` passa (10). A trava foi restaurada e o arquivo conferido com `git status`.
- **Verificações:** `ruff check --no-cache`, `ruff format --check` e `mypy .` (470 arquivos) limpos; os quatro módulos de teste do pedido formal (envio, reenvio, telas, ponta a ponta): 68 passaram.
