# E13-02 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal_envio.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `594fcaf` | **17 failed**: o módulo `apps.pedidos.envio_do_pedido_formal` não existe |
| Green | `4568f45` | **17 passed** (inclui A-11 e A-12 com transações reais) |
| Refactor | `002c386` | `__all__` do módulo (o mypy recusava `modulo.enviar_email` nos testes) e tipo de `estado_do_envio`; suíte do arquivo verde |

## O que foi feito
- `TentativaDeEnvioDoPedidoFormal` (só inserção, com as restrições do `spec.md`), `processar_pedidos_formais()` e a tarefa periódica por minuto (`enviar_pedidos_formais`, com `queueing_lock`).
- Travas: o `EnvioDoPedidoFormal` com `select_for_update(skip_locked=True, of=("self",))` e a `Rodada` com `no_key=True`. O `of=("self",)` evita travar o pedido formal e o fornecedor junto.
- A consulta ao provedor vem antes, fora de transação; falha dela reagenda em 5 minutos sem tentativa. A rodada cancelada é conferida antes da consulta (sem consulta inútil) e de novo sob a trava.

## Decisões técnicas
- O aviso `falha_no_pedido_formal` junta as frases das tentativas num só texto, separadas por espaço; o link é uma string (a página só nasce na E13-04).
- A-17 (log): a captura do teste inclui uma falha de consulta no meio do ciclo e confere que nenhum registro leva o destino, o assunto ou o corpo.


## Revisão independente — agente 3 — 2026-11-13

Base auditada: `9af6251`, branch `e13-especificacoes`, sobre `9851bb5`. Requisitos lidos antes do código: especificação funcional v1.7, infraestrutura v1.8 e os `spec.md`/`acceptance.md` das oito fatias. Os registros do implementador acima foram preservados integralmente.

**Veredito da fatia: REPROVADO — E13-R02 aberto.**

Os critérios A-1 a A-17 têm cobertura na suíte entregue; `test_pedido_formal_envio.py`: **17 testes passaram**. Foram conferidos limites de três tentativas, intervalos, consultas prévias, aviso aos administradores, cancelamento, auditoria e exclusão mútua. O caso concorrente adicional abaixo não é coberto pelo A-11 existente, que mantém a primeira execução dentro do envio.

### E13-R02 — Importante: consulta atrasada sobrescreve o intervalo da segunda falha

- **Requisitos:** infraestrutura §4.14 (intervalos crescentes e concorrência), E13-02 regras 3 a 5, A-3/A-5/A-11; AGENTS.md §6.
- **Referência:** `apps/pedidos/envio_do_pedido_formal.py:79-99`, especialmente a atribuição da próxima tentativa na linha 97.
- **Reprodução:** depois da primeira falha, duas execuções selecionam o mesmo envio vencido em 13:05 UTC. A consulta da execução B fica pendente. A execução A consulta normalmente, registra a segunda falha de e-mail e agenda a terceira para 13:35. Só então a consulta B falha; B adquire a trava e troca o agendamento para 13:10.
- **Evidência independente:** `test_consulta_antiga_nao_encurta_intervalo_da_terceira_tentativa` falhou: esperado `2026-11-04 13:35 UTC`, obtido `13:10 UTC`; duas tentativas já registradas. O teste usa conexões PostgreSQL reais e eventos determinísticos; apenas a consulta atrasada é um dublê de falha, o restante segue o fluxo real.
- **Causa:** o caminho de falha verifica apenas `situacao=em_andamento`; não verifica se o agendamento/contador que motivou aquela consulta já avançou. A trava evita escrita simultânea, mas não uma escrita obsoleta depois do commit do outro worker.
- **Correção esperada:** sob a trava, uma consulta antiga não pode substituir o agendamento de uma tentativa posterior. Acrescentar Red/Green para esse intercalamento, preservando o reagendamento de cinco minutos quando a falha pertence ao trabalho ainda vigente. Não é necessária decisão comercial nova.

O código completo da reprodução está em [E13-08](../E13-08/review.md). Nenhuma correção de produção foi feita pelo revisor.

TDD histórico: `594fcaf` (Red, testes) precede `4568f45` (Green); `002c386` refatora exports/tipos. O registro declara 17 falhas por módulo ausente e 17 sucessos; a ordem dos commits foi conferida. Esse histórico não cobre o E13-R02 descoberto agora.

## Correção do E13-R02 — implementador — 2026-11-13

Especificação: `a858d0d` (regra 3-A, o retrato da seleção; A-18 e A-19).

- **Red (`5ae9f5e`):** `uv run pytest tests/tecnicos/test_pedido_formal_envio.py` → 2 falhas, 17 passaram. A-18: `proxima_tentativa_em` = `PRAZO + 10 min` em vez de `PRAZO + 35 min`. A-19: a execução atrasada fez a terceira tentativa (devolveu 1) sem consulta posterior à segunda.
- **Green (`0966272`):** em `apps/pedidos/envio_do_pedido_formal.py`, a falha da consulta só reagenda se, sob a trava (`skip_locked`), o envio continua `em_andamento` com `automaticas` e `proxima_tentativa_em` iguais ao retrato lido na seleção; o sucesso da consulta passa pela mesma conferência (`_igual_ao_retrato`) junto às da regra 4. Rodada cancelada continua interrompendo sem depender do retrato. Resultado: 19 passaram (A-5, A-7 e A-11 verdes).
- Ajuste do próprio teste novo antes do commit do Green: o campo da notificação é `conta`, não `destinatario` (erro meu no teste do A-19; a asserção não foi afrouxada).
- **Verificações:** ruff, format e mypy limpos; 68 testes dos módulos do pedido formal passaram. Suíte completa: ver E13-08.


## Revalidação independente das correções — agente 3 — 2026-11-13

Base auditada: `5055047`, branch `e13-especificacoes`, comparada com `7616ae8`. Histórico anterior preservado integralmente.

**APROVADO. E13-R02 encerrado.**

Conferidos os requisitos da correção em `a858d0d` (regra 3-A e A-18/A-19), compatíveis com a infraestrutura §4.14 e a consulta prévia. A falha da consulta só reagenda quando contador e próxima tentativa ainda correspondem ao estado lido antes dela. No sucesso, a mesma comparação impede que uma consulta antiga autorize a tentativa seguinte. Cancelamento mantém seu tratamento independente dessa comparação.

A-1 a A-19 reexecutados: **19 testes passaram**, dentro da matriz completa de 157. Incluem falha atrasada preservando os 30 minutos, sucesso atrasado descartado e consulta nova antes da terceira tentativa. A prova independente original do R02, sem alteração, também passou: duas tentativas registradas e agendamento em `PRAZO+35 min`.

TDD: `5ae9f5e` introduz os testes antes da produção em `0966272`. Registro Red: 2 falhas/17 sucessos; Green: 19 sucessos. Conferida a mudança de `destinatario` para `conta` no teste: corrige o nome real do campo sem enfraquecer a asserção. Não foi reexecutado o checkout histórico do Red; histórico/diff e registro corroboram a sequência. Sem achado residual. Comandos e limites em [E13-08](../E13-08/review.md).
