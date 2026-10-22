# E09-07 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- `apps/financeiro/liquidez.py` (`liquidez`, `registrar_saida`, `Liquidez`, `LiquidezInsuficiente`, `SaidaRepetida`), `invariante.py` (`verificar_invariante_agora`, `ResultadoDoInvariante`), `conciliacao.py` (`conciliar_dia`, `conciliar_dias_pendentes_agora`, `limites_do_dia`), `tarefas.py` (as tarefas `verificar_invariante`, a cada 10 minutos, e `conciliar_dias_pendentes`, de hora em hora), `models.py` (`ConciliacaoDiaria`), migração `0009_conciliacao_diaria.py` (com a trigger só-inserção).
- Resolução automática dos alertas: `entradas.py` (`registrar_entrada` resolve `pagamento_sem_conciliacao`; `registrar_tarifa` resolve a divergência de tarifa daquele pagamento) e `reserva.py` (`registrar_aporte` resolve a divergência do depósito); `registrar_saida` resolve a da saída.
- Testes: `test_financeiro_liquidez_e_saidas.py` (A-1 a A-6), `test_financeiro_invariante.py` (A-7 a A-10, A-22), `test_financeiro_conciliacao.py` (A-11 a A-18, A-21, A-23 e a resolução da tarifa), `test_financeiro_concorrencia.py` (A-19, A-20), `tests/aceitacao/test_cenario_40_repasse.py` e o repasse de A em `test_cenario_32_...`. Apoio: o arranjo L (`montar_l`, `pedidos_pagos_e_apurados`) em `tests/apoio/financeiro.py`; prefixos novos no gancho do banco do simulador (`test_cenario_32_`, `test_cenario_40_`).

## Andaime (exceção técnica)

Antes do Red: o modelo `ConciliacaoDiaria` e a migração; `liquidez.py`, `invariante.py` e `conciliacao.py` com as exceções, os tipos e as assinaturas com corpo trivial (liquidez zerada, `None`, objeto não salvo, `0`), importando `obter_provedor` para os testes poderem trocá-lo.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_liquidez_e_saidas.py tests/tecnicos/test_financeiro_invariante.py tests/tecnicos/test_financeiro_conciliacao.py tests/tecnicos/test_financeiro_concorrencia.py tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py tests/aceitacao/test_cenario_40_repasse.py -q -p no:cacheprovider`: **27 falharam, 16 passaram**. As falhas são asserções: `assert None == ResultadoDoInvariante(saldo_do_provedor=Decimal('1189.00'), ...)`, `assert 0 == 3`, `assert None == datetime.date(2026, 11, 2)`, `DID NOT RAISE LiquidezInsuficiente / MovimentoProibido / InvarianteViolado / PermissionDenied / ValueError`.

| Critério | Teste | Resultado do Red |
|---|---|---|
| A-1 a A-6 | os oito de `test_financeiro_liquidez_e_saidas.py` | liquidez zerada; `DID NOT RAISE ...` |
| A-7 a A-10, A-22 | os cinco de `test_financeiro_invariante.py` | resultado `None`; nenhum alerta aberto |
| A-11 a A-18, A-23 | os dez de `test_financeiro_conciliacao.py` | `assert 0 == 3`, `assert None == datetime.date(...)`, `assert [] == [...]` |
| A-21 | `test_conciliacao_nao_cria_movimento_no_livro` | **passou já no Red**: o andaime não lança nada; guarda de regressão |
| A-19, A-20 | `test_dois_repasses_...`, `test_duas_conciliacoes_do_mesmo_dia` | ver "Green" |

## Green, em passos (regra da concorrência)

1. **Verde funcional sem a trava do repasse:** `liquidez.py` sem `select_for_update`, `invariante.py` e `conciliacao.py` completos. Os arquivos de liquidez, invariante, conciliação e aceitação: **26 passaram, 3 falharam**. As falhas: o A-12 (o alerta `pagamento_sem_conciliacao` não é resolvido pela entrada), o A-13 (a divergência do depósito não é resolvida pelo aporte) e o A-23 (um defeito do dublê do meu teste, que dava ao movimento um instante fora do dia; corrigi o teste para um instante fixo dentro de D). Acrescentei então o teste da resolução da divergência de tarifa, que falhou pelo mesmo motivo: nenhum dos três ganchos de resolução existia.
2. **Ganchos de resolução automática** em `registrar_entrada`, `registrar_aporte`, `registrar_tarifa` e `registrar_saida`: os quatro arquivos, **29 passaram**.
3. **Red da corrida do A-19** com o repasse sem trava, por asserção: `isinstance(SaldoInsuficiente('obrigacao_fornecedor:f40:r40'), LiquidezInsuficiente)` falso, isto é, as duas saídas passaram juntas pelo limite do liberado e só o saldo da conta barrou a segunda (o limite do liberado não foi respeitado).
4. **A trava** (`_travar_conta` da conta antes de calcular o liberado): `test_financeiro_concorrencia.py` e os demais, **62 passed**.
5. **A-20:** a proteção (o registro da conciliação é inserido primeiro, `UNIQUE` na data, e o conflito devolve o registro do outro) já veio com o código, sem Red anterior. Prova de sensibilidade (mutação, não Red): sem o tratamento do `IntegrityError`, `test_duas_conciliacoes_do_mesmo_dia` falha com `IntegrityError('duplicate key ... financeiro_conciliacaodiaria_data_key')`; restaurado, **14 passed**. A mutação do A-19 (retirar a trava do repasse) também foi detectada (**1 falhou, 13 passaram**), e a restauração voltou a **14 passed**.

## Decisões técnicas e pontos para o revisor

- **Uma só consulta de movimentos por dia.** `conciliar_dia` pede ao provedor os movimentos de `D − 3 dias` até o maior entre o fim de `D` e o `referente_a` do saldo; o recorte do dia, a janela dos três dias do sentido inverso e o trecho até o `referente_a` (para a diferença) saem dessa lista. Assim uma falha do provedor interrompe o dia inteiro, e a fila avança em ordem.
- **A diferença usa os movimentos sem par de `D` até o `referente_a`**, como a spec manda; os de dias posteriores a `D` que já estejam conciliáveis (com par) não entram na diferença.
- **A divergência do `outro` e do `ajuste`** leva o `descricao_no_provedor` nos dados; a de tarifa leva `tipo` e `id_externo`, que é como `registrar_tarifa` acha o alerta para resolver.
- **`devolucao` do provedor** ainda não tem par (a E10 acrescenta): hoje cai em divergência, como os tipos desconhecidos.
- **Invariante em uma consulta.** `obrigacoes_de_terceiros` soma entradas e saídas das quatro destinações num único `aggregate` condicional, só com os movimentos até o `referente_a`.
- **Liquidez de um fornecedor com vários pedidos.** Cada transferência da apuração para a conta é atribuída ao pedido da custódia de origem (ciclo e comprador); o pagamento que quitou esse pedido dá a data de liberação. A conta de outras destinações levanta `ValueError`.
- **`pagamento_do_frete`** limita-se ao saldo da conta (quem barra é a recusa de saldo do livro).
- **Alertas de conciliação por data de execução.** O alerta `saldo:<D>` é resolvido por qualquer conciliação posterior com diferença zero (todas as chaves `saldo:*` abertas).

## Verificação

Os arquivos da fatia e `tests/aceitacao`: **62 passed**. A suíte completa, sem filtro, e as verificações estáticas estão no fim deste arquivo.

**Suíte completa, sem filtro, com o estado da fatia:** `uv run pytest -q -p no:cacheprovider` → **2364 passed in 210.56s**; `ruff check`, `ruff format --check`, `mypy` (388 arquivos) e `makemigrations --check`: limpos.
