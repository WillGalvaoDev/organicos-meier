# E14-05 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_retirada.py tests/aceitacao/test_cenario_23_descarte.py` (arquivos inteiros, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | **31 failed**: `apps.pedidos.retirada`, `RetiradaDeItem` e `DescarteDeItem` inexistentes |
| Green | **31 passed**; com as E14-01, E14-02 e E14-04, **84 passed** (o saldo do item passou a descontar retirada e descarte e as ocorrências continuam verdes); `ruff` e `mypy apps/pedidos tests/apoio` limpos |

## O que foi feito
- `RetiradaDeItem` e `DescarteDeItem` (base abstrata `_RegistroDeItemDaRetirada`, só inserção, migração `0020` com as duas proteções), `registrar_retirada`, `registrar_descarte`, `situacao_da_retirada` e `RetiradaRecusada` em `apps/pedidos/retirada.py`.
- `saldo_do_item` (E14-02) estendido: quantidade − reembolsos (todos os motivos) − retirado − descartado.
- Travas: rodada (`no_key`) e situação do pedido, na ordem da ocorrência. O descarte é aceito a partir de `prazo_final` (inclusive); a retirada depois do prazo continua aceita; nada depende da situação do comprador; nenhum efeito financeiro.
- `vencidos` é calculado na leitura (`agora >= prazo_final` e saldo > 0); nenhum registro nasce da passagem do tempo.

## Decisões técnicas
- `situacao_da_retirada` levanta `LookupError` para rodada não liberada (as telas devolvem 404 antes de chamá-la).
- A-9 (item de pedido não válido): usa o AF-parcial liberado (Y não pagou), pois um item de rodada não liberada recebe `etapa`, que vem antes.
- O arquivo de aceitação do cenário 23 foi escrito no mesmo ciclo do Red (falhava pelo mesmo motivo).


---

## Revisão independente — agente 3 — 2026-11-16

**Objeto:** `5b00c56`, branch `e14-especificacoes`, comparação com `bc35037` (main após E13). Fontes: especificação funcional v1.7, infraestrutura v1.8, AGENTS.md e as oito especificações e matrizes da E14. Histórico do implementador acima preservado.

A execução independente e o parecer consolidado estão em [E14-08/review.md](../E14-08/review.md), incluindo o código das contraprovas. A revisão não alterou código de produção nem os testes do implementador.

**Parecer da fatia: REPROVADO — E14-R01 (importante).**

| Critérios | Verificação |
|---|---|
| A-1 a A-14 | Retiradas fracionadas, saldo, prazo inclusivo do descarte, vencidos calculados, etapas/quantidades, ocorrências, apuração, comprador suspenso/removido e permissão. |
| A-15 | Passa no replay sequencial existente; falha no replay concorrente do mesmo acionamento (R01). |
| A-16 a A-18 | Ausência de efeito financeiro, auditoria e só inserção no ORM/SQL. |
| A-19 e A-20 | Corridas de saldo com ocorrência e outra retirada, com acionamentos distintos. |

### E14-R01 — replay concorrente informado como registro novo

- **Requisito:** regra 2 desta spec (`novo = False` para repetição), A-15 e convenção 3 da E14-06.
- **Local:** `apps/pedidos/retirada.py:184` e `:205-207`.
- **Reprodução:** AE-liberada, duas conexões chamam retirada de 4 em X-P1 com o mesmo UUID. A primeira pausa após `registrar_auditoria`, ainda segurando as travas; a segunda espera; após o commit, `_gravar` encontra e devolve o registro existente, mas `_registrar` acrescenta `True` incondicionalmente. O mesmo ocorre no descarte depois do prazo.
- **Evidência independente:** `test_replay_concorrente[False/True]`: ambas falham por `(True, True) != (True, False)`, com espera confirmada e **um único registro**, mesmo pk nas duas respostas. Portanto, não foi encontrada duplicação de quantidade nem de dinheiro; a falha é no contrato do resultado e na mensagem de confirmação da tela.
- **Correção esperada:** preservar a indicação de replay também no caminho encontrado sob trava, para retirada e descarte. Acrescentar Red/Green concorrente para ambas as operações e verificar a mensagem da rota.

TDD existente: `fc08145` antes de `cb56f78`, com cenário 23 e asserções A-1 a A-20. A lacuna é o replay concorrente, não coberto pelas corridas de tokens distintos.
