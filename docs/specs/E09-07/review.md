# E09-07 — Parecer independente sobre 34f9547

**Veredito: REPROVADO.**

Base: `34f9547ae7962687ed96997e3338914f985a277f`, branch `e09-implementacao`, revisão independente em 2026-10-22. Lidos documentos-base funcional v1.6 e infraestrutura v1.7, AGENTS.md, especificações, critérios, código, testes e registros das oito fatias. Histórico do implementador preservado integralmente abaixo.

Verificações independentes:

- `uv run pytest -q`: **2398 passed in 273.67s**, sem filtro, PostgreSQL e banco separado do simulador.
- `uv run ruff check .`: passou; `uv run ruff format --check .`: 328 arquivos conformes.
- `uv run mypy .`: 391 arquivos sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais, fora da suíte versionada: **9 failed in 8.57s**, pelos defeitos descritos no [parecer consolidado](../E09-08/review.md), que contém o código completo para reprodução.

Não foram alterados código de produção nem testes versionados. Testes verdes dos critérios existentes não bastam para aprovar as interações financeiras. O revisor não presenciou os ciclos TDD históricos; conferiu os registros e não trata mutação posterior como Red anterior à implementação.

## Matriz e achados

A-1–A-23: testes existentes verdes. Conferidos liquidez por fornecedor/componente, limite das saídas, horário de Brasília, recorte do invariante e unicidade do dia conciliado. **R05 importante:** omissão da avaliação periódica da reserva. **R06 importante:** identificação válida de 64 caracteres aborta a conciliação por gerar alerta de 70 caracteres (extensão A-13/A-17). **R07 importante:** movimentos posteriores ao referente_a geram diferença falsa; movimento de D+1 é aceito como par inverso de D (spec e extensões A-13/A-14/A-15/A-23). **R08 bloqueador de processo:** proteção de A-20 introduzida antes do Red próprio; A-19 tem a sequência registrada. Corrigir os recortes separadamente e registrar provas negativas com saldo assíncrono.

---

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

## Não conformidade de TDD (E09-R08)

Tratamento decidido pelo responsável pelo projeto em 2026-10-22: o mesmo das correções E05-R04, E06-R05 e E08-R06. O registro anterior fica como estava.

| Critério | O que aconteceu |
|---|---|
| A-20 | o `UNIQUE` da data e o tratamento do conflito vieram antes do Red específico; havia só a prova por mutação |

**Evidência histórica procurada (passo 1 do tratamento).** Verifiquei o histórico git (os commits de origem das fatias (`cbe5ae3` no livro, `917f375` nas obrigações, `3f7e6e7` na conciliação) trazem testes e produção juntos, sem commit só de testes antes do código), os logs guardados e o registro anterior deste arquivo. Não há saída registrada no momento que mostre o teste falhando pelo motivo do critério antes do código de produção correspondente. Nenhum critério saiu da lista.

**Nenhum texto desta seção afirma que houve Red nesses critérios.** O que existe é a prova de sensibilidade abaixo, que **não é Red**: ela mostra que o teste de hoje detecta a remoção da proteção, não que ele tenha falhado antes de ela existir.

Mutações refeitas sobre o código de `1ad1944`. Em cada uma: o trecho é alterado, o comando roda com os arquivos inteiros e sem `-k`, a falha é registrada e o arquivo volta ao original (conferido com `git status` limpo e a execução verde de novo).

### Sensibilidade (mutação), não Red

Comando: `uv run pytest tests/tecnicos/test_financeiro_conciliacao.py tests/tecnicos/test_financeiro_concorrencia.py -q -p no:cacheprovider`. Restaurado: **40 passed**.

| Critério | Trecho mudado | Resultado mutado |
|---|---|---|
| A-20 | `apps/financeiro/conciliacao.py`: `except IntegrityError:` → `except ZeroDivisionError:` (sem o tratamento do conflito) | **1 failed, 39 passed**: `test_duas_conciliacoes_do_mesmo_dia`, `AssertionError: ['None', 'IntegrityError(\'duplicate key value violates unique constraint "financeiro_conciliacaodiaria_data_key"...` |

## Correção E09 (2026-10-22): Red → Green dos critérios novos

Critérios: **A-24 a A-27**.

**Red** (`e3733ad`, código no estado de `34f9547`; seis arquivos inteiros, sem `-k`: **18 failed, 129 passed**; log em `scratchpad/red_e09.log`, fora do repositório):

| Critério | Teste | Falha observada |
|---|---|---|
| A-24 | `test_a_tarefa_do_invariante_avalia_a_reserva` | `ValueError: not enough values to unpack (expected 1, got 0)`: o teste desempacota o alerta de reserva que a tarefa deveria ter aberto e não abriu. É falha pelo efeito ausente, não por `assert` |
| A-25 | `test_identificacao_de_64_caracteres_e_conciliavel` | `ValueError: a chave do alerta deve ter de 1 a 64 caracteres` |
| A-26 (i) | `test_a_diferenca_respeita_o_instante_do_saldo` | `assert Decimal('-10.00') == Decimal('0.00')` |
| A-26 (ii) | `test_pagamento_lancado_depois_do_instante_do_saldo_nao_cria_diferenca` | `assert Decimal('125.00') == Decimal('0.00')` |
| A-27 | `test_movimento_do_provedor_depois_do_dia_nao_e_par_de_um_aporte_do_dia` | `assert ConciliacaoDiaria.Resultado.OK == 'divergente'` |

**Green:** `1ad1944` (R05, R06 e R07: a reserva avaliada sob a trava, chave do alerta até 80 caracteres com a migração `0010`, e a leitura em três recortes). O A-25 também depende do E09-03 A-13 (limite de 80). O E09-03 A-6 reescrito (81 caracteres) já passava no Red; o Red do par vem do A-13 (`test_chave_de_80_caracteres_e_aceita_e_resolvida_inteira`: `ValueError: a chave do alerta deve ter de 1 a 64 caracteres`). Verificação em `1ad1944`: suíte completa sem filtro, **2418 passed**; as provas do parecer não substituídas (`test_frete_coberto`, `test_tarefa_avalia_reserva`, `test_identificador_64_conciliavel`, `test_conciliacao_respeita_referente_a`, `test_conciliacao_nao_parea_movimento_futuro`) passaram, a primeira depois de dividir as operações dela em transações separadas por causa da guarda.
