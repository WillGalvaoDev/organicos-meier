# E09-06 — Revalidação independente sobre 2930ffd

**Veredito: APROVADO no escopo desta fatia.**

Revisão independente de 2026-10-22, base `2930ffddc8fc53ad21c6bb777719b19508d1a4da` (branch `e09-implementacao`). Foram conferidos os adendos de especificação e aceitação em `6dc9850`, o commit de testes Red `e3733ad`, os diffs das correções e os registros de implementação. O histórico anterior permanece integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2418 passed in 234.26s**, sem filtro; `uv run ruff check .` passou; `uv run ruff format --check .` → 329 arquivos; `uv run mypy .` → 393 arquivos sem erros; `uv run python manage.py makemigrations --check --dry-run` → nenhuma alteração pendente. Provas adicionais: **4 failed, 9 passed in 9.77s**. Reprodução completa, limites e veredito global no [parecer consolidado](../E09-08/review.md).

## Matriz e achados

A-1–A-26: testes verdes. **R01, R03, R04 e R09 encerrados**: proteção compartilhada do pendente; referência consultada de novo após as travas; relatório soma cobertura do frete das obrigações conforme atribuição conservadora da spec; apuração e obrigação serializam a escolha de fontes.

As provas independentes repetem cobertura cruzada, mesma referência concorrente, frete pago/obrigação de frete e obrigação versus apuração. Na última, a pausa foi colocada depois de `_ciclo_apurado`, garantindo que o teste examine o ponto posterior à leitura do estado; passa com financiamento 25,00 e fornecedor 75,00. O teste versionado A-24(i) pausa em `_fontes`, que na nova implementação também é chamado na preparação das contas; essa diferença de ponto foi suprida pela prova independente, sem modificar o teste versionado.

R08: tratamento autorizado aceito, com mutações posteriores explicitamente tratadas como sensibilidade. Preservada a limitação do antigo A-19; A-24(ii) e a mutação registrada cobrem a proteção da apuração em outra corrida válida. Aceito o encerramento de M-6 no alcance definido pelo especificador. A regra conservadora de R04 é somente de relatório e não altera lançamentos/dívidas. R10 da guarda compartilhada ainda impede aprovação global.

---

# E09-06 — Parecer independente sobre 34f9547

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

A-1–A-19: testes existentes verdes. **R01/R02 bloqueadores:** cobertura excedente e inversão de travas. **R03 importante:** repetição concorrente de A-10 recusa a liquidação em vez de devolver o mesmo movimento. **R04 importante:** frete_do_ciclo omite a cobertura do componente frete das obrigações (spec e extensão de A-3/A-4/A-7). **R09 bloqueador:** obrigação concorrente à apuração escolhe fontes desatualizadas e fica sem cobertura apesar do saldo na própria rodada (P-2, A-1/A-6/A-7). **R08 bloqueador de processo:** A-17–A-19 não tiveram Red da corrida antes das travas, conforme declaração. M-6 não substitui esse gate nem cobre a corrida distinta de R09. Para R04, a prova usa obrigação exclusivamente de frete, sem dúvida de rateio; eventual atribuição de cobertura parcial de obrigação mista deve ser esclarecida pelo especificador se não puder ser derivada das regras aprovadas.

---

# E09-06 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- `apps/financeiro/apuracao.py` (`registrar_apuracao_no_livro`, `frete_do_ciclo`, `FreteDoCiclo`, `cobrir_despesa`, `cobrir_tarifas_pendentes_da_rodada`, `rodada_apurada`), `obrigacoes.py` (`registrar_obrigacao_com_comprador`, `cobrir_obrigacao_com_receita`, `liquidar_obrigacao`, `LiquidacaoRecusada`, `conta_da_obrigacao`, `travar_em_ordem`), ajustes em `reserva.py` (o consumo das designações entra no comprometido) e em `entradas.py` (a tarifa nova de uma rodada já apurada tenta a cobertura pela receita).
- `models.py` (`ApuracaoNoLivro`, `PedidoApurado`, `ObrigacaoComComprador.depois_da_apuracao`), migração `0008_apuracao_no_livro.py` (com a trigger só-inserção).
- Testes: `tests/tecnicos/test_financeiro_apuracao_e_obrigacoes.py` (A-1 a A-16), `tests/tecnicos/test_financeiro_concorrencia.py` (A-17 a A-19), `tests/aceitacao/test_cenario_31_deficit_de_frete.py`, `tests/aceitacao/test_cenario_33_devolucao_e_repasse.py`. Apoio: o arranjo `Ap` (`montar_ap`, `pagar_pedido`) em `tests/apoio/financeiro.py`; prefixos novos no gancho do banco do simulador em `tests/conftest.py`.

## Andaime (exceção técnica)

Antes do Red: os modelos novos e a migração; `apuracao.py` e `obrigacoes.py` com os tipos, as exceções e as assinaturas com corpo trivial (`FreteDoCiclo` com tudo `None`, objetos não salvos).

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_apuracao_e_obrigacoes.py tests/tecnicos/test_financeiro_concorrencia.py tests/aceitacao/test_cenario_31_deficit_de_frete.py tests/aceitacao/test_cenario_33_devolucao_e_repasse.py -q -p no:cacheprovider`: **23 falharam, 10 passaram**. As falhas são asserções: `assert (None, None, None) == (Decimal('30.00'), Decimal('20.00'), Decimal('10.00'))`, `assert Decimal('0.00') == Decimal('100.00')`, `assert [Decimal('100.00'), ...] == [Decimal('75.00'), ...]`, `DID NOT RAISE ValueError / MovimentoConflitante`. As 10 que passaram incluem o A-14 (o andaime já devolve tudo `None`, que é o pedido) e os testes das fatias anteriores do mesmo arquivo de concorrência.

## Green

`obrigacoes.py` e `apuracao.py` completos, mais o consumo da designação em `reserva.py` e a cobertura da tarifa nova em `entradas.py`: os quatro arquivos, **33 passed**; nesse passo também o conjunto `tests/aceitacao`, **50 passed**. Um erro do meu teste do A-5 apareceu aqui: ele esperava a lista de itens sem cobertura só com a tarifa de 0,80, mas o déficit de frete de 10,00 também está pendente; passei a procurar a tarifa pelo `pk` dentro da lista.

## Desvio de processo declarado (concorrência sem Red próprio)

Escrevi as travas das contas junto com as operações (`travar_em_ordem`), sem o passo "verde funcional sem a trava → Red da corrida → trava" que a prevenção da E08-R06 pede. Os três testes de concorrência (A-17 a A-19) nunca foram vistos falhar por corrida antes das travas. A prova de sensibilidade é por mutação (não é Red), com `test_financeiro_concorrencia.py` inteiro e restauração verde depois de cada uma (`scratchpad/mutacoes_e09.py`):

| Mutação | Resultado |
|---|---|
| `registrar_obrigacao_com_comprador` sem `travar_em_ordem` | **1 falhou, 11 passaram**: `test_duas_obrigacoes_do_mesmo_comprador_disputam_a_mesma_custodia` (A-17) |
| `liquidar_obrigacao` sem `travar_em_ordem` | **1 falhou, 11 passaram**: `test_duas_liquidacoes_da_mesma_obrigacao` (A-18) |
| `registrar_apuracao_no_livro` sem `travar_em_ordem` | **nenhuma falha**: limite do A-19 |

Restaurado cada arquivo, o arquivo de concorrência volta a **12 passed**. Sobre o A-19: a garantia de "nunca mover só parte" vem de o destino `quita` e a entrada na custódia serem gravados na mesma transação (E09-04): a apuração ou vê o destino e a entrada juntos, ou não vê nenhum dos dois e recusa por `ValueError`. A trava da custódia na apuração protege contra uma entrada posterior ao cálculo dos saldos, que o teste não consegue provocar de forma determinística; fica como limite declarado. Lição aplicada: nas E09-07 e E09-08 sigo a sequência completa.

## Decisões técnicas e pontos para o revisor

- **Apuração idempotente pelo conjunto.** O conjunto de pedidos fica em `PedidoApurado`; repetir com o mesmo conjunto devolve a `ApuracaoNoLivro` existente, e com outro levanta `MovimentoConflitante`. A chave do movimento é `apuracao:<ciclo>`. Lista vazia é aceita (sem movimento, só o registro e o déficit inteiro).
- **Obrigação "depois da apuração".** Um campo imutável `depois_da_apuracao` registra, no nascimento, se o ciclo já tinha sido apurado. Ele decide as fontes e entra no `devolvido` do relatório; comparar horários não serve com o relógio congelado dos testes.
- **Déficit por devolução de frete.** Quando uma obrigação depois da apuração tira frete de `frete(r)`, nasce uma `Despesa(deficit_frete)` com o valor efetivamente tirado.
- **Pendência de especificação (não implementada).** O `deficit_coberto` da spec soma "as coberturas das despesas de déficit do ciclo mais as coberturas do componente frete sem cobertura das obrigações". Um financiamento posterior de uma obrigação (cobertura pela receita, consumo de designação) não diz a que componente se refere, então não há como separar a parte do frete. Implementei só a primeira parcela (as despesas de déficit), que é o que os critérios A-3, A-4 e A-7 exercitam. Peço ao especificador que diga qual regra de atribuição vale para a segunda parcela.
- **Liquidação.** Primeiro o saldo da conta da obrigação, depois as designações ativas em ordem de criação (movimento F11 da reserva que cita a designação, parcial se preciso), depois a saída F15 com a chave `devolucao:<referencia>`. Repetir a referência com o mesmo valor devolve o movimento; com outro valor, `MovimentoConflitante`. Valor não positivo ou não `Decimal` também é `LiquidacaoRecusada`.
- **Alerta ao liquidar tudo.** Resolvido pela chave `id_externo` do pagamento do destino que originou a obrigação, no motivo `aprovado_apos_a_margem` ou `duplicidade`.
- **Importações privadas.** `obrigacoes.py` e `apuracao.py` reaproveitam as validações de `reserva.py` (`_exigir_administrador`, `_valor`, `_justificativa`, `_exigir_transacao`), para não duplicar a regra de quem é o administrador.

## Verificação

Os quatro arquivos da fatia e `tests/aceitacao`: **50 passed**. Suíte completa, sem filtro, com o estado da fatia: `uv run pytest -q -p no:cacheprovider` → **2334 passed in 295.76s**; `ruff check`, `ruff format --check` (318 arquivos), `mypy` (380 arquivos) e `makemigrations --check`: limpos.

## Não conformidade de TDD (E09-R08)

Tratamento decidido pelo responsável pelo projeto em 2026-10-22: o mesmo das correções E05-R04, E06-R05 e E08-R06. O registro anterior, inclusive o "Desvio de processo declarado", fica como estava.

| Critério | O que aconteceu |
|---|---|
| A-17, A-18 e A-19 | as travas foram escritas junto com as operações, sem a sequência "verde funcional sem a trava → Red da corrida → trava". A mutação do registro anterior detectava A-17 e A-18, mas não A-19 |

**Evidência histórica procurada (passo 1 do tratamento).** Verifiquei o histórico git (os commits de origem das fatias (`cbe5ae3` no livro, `917f375` nas obrigações, `3f7e6e7` na conciliação) trazem testes e produção juntos, sem commit só de testes antes do código), os logs guardados e o registro anterior deste arquivo. Não há saída registrada no momento que mostre o teste falhando pelo motivo do critério antes do código de produção correspondente. Nenhum critério saiu da lista.

**Nenhum texto desta seção afirma que houve Red nesses critérios.** O que existe é a prova de sensibilidade abaixo, que **não é Red**: ela mostra que o teste de hoje detecta a remoção da proteção, não que ele tenha falhado antes de ela existir.

Mutações refeitas sobre o código de `1ad1944`. Em cada uma: o trecho é alterado, o comando roda com os arquivos inteiros e sem `-k`, a falha é registrada e o arquivo volta ao original (conferido com `git status` limpo e a execução verde de novo).

### Sensibilidade (mutação), não Red

Comando das três mutações: `uv run pytest tests/tecnicos/test_financeiro_apuracao_e_obrigacoes.py tests/tecnicos/test_financeiro_concorrencia.py -q -p no:cacheprovider`. Restaurado, o comando dá **43 passed**.

| Critério | Trecho mudado | Resultado mutado |
|---|---|---|
| A-17 | `apps/financeiro/obrigacoes.py`: retirada a linha `travar_contas(*_contas_candidatas(rodada, ciclo, comprador))` de `registrar_obrigacao_com_comprador` | **6 failed, 37 passed**. O A-17 (`test_duas_obrigacoes_do_mesmo_comprador_disputam_a_mesma_custodia`) falha porque as operações levantam `OrdemDeTravasViolada` (a guarda acusa a trava tardia da conta nova), e não por saldo; o `assert Decimal('25.00') == Decimal('0.00')` aparece no A-24 (i). Falham também A-18 antigo, A-23 (i) e (ii) e A-24 (i) e (ii) |
| A-18 | `apps/financeiro/obrigacoes.py`: retirada a linha `travar_contas(destino, caixa)` de `liquidar_obrigacao` | **1 failed, 42 passed**: `test_duas_liquidacoes_da_mesma_obrigacao`, `AssertionError: SaldoInsuficiente('obrigacao_comprador:o19')` (as duas liquidações passam juntas) |
| A-19 | `apps/financeiro/apuracao.py`: retirada a chamada `travar_contas(*destinos.values(), conta(DESPESAS_A_COBRIR), *custódias)` de `registrar_apuracao_no_livro` | **4 failed, 39 passed**. O **A-19 em si não falha**: o limite continua declarado. Falham `test_dois_repasses_que_juntos_passam_do_liberado`, `test_duas_conciliacoes_do_mesmo_dia` e, o que importa, **os dois testes do A-24 (ii)** (`test_apuracao_que_le_os_saldos_e_a_obrigacao_se_serializam`, `AssertionError: ("OrdemDeTravasViolada('a conta 289 foi pedida depois da 292...')", 'None')`) e A-24 (i). Falha por exceção da guarda dentro da corrida |

**A-19 e a M-6.** Não existe Red real possível para o A-19: a proteção já existe e a entrada concorrente na custódia de um pedido já quitado não acontece pelas regras (destino `quita` e entrada saem na mesma transação, E09-04). A trava da apuração passa a ser provada pelo A-24 (ii): retirá-la o faz falhar, como acima. Com isso a M-6 foi movida para "Encerradas" em `docs/melhorias.md`.

## Correção E09 (2026-10-22): Red → Green dos critérios novos

Critérios: **A-20 a A-26**.

**Red** (`e3733ad`, código no estado de `34f9547`; seis arquivos inteiros, sem `-k`: **18 failed, 129 passed**; log em `scratchpad/red_e09.log`, fora do repositório). Em todos, a corrida ou a conta já eram exercitadas em série pelos 129 testes que passavam (o verde funcional); o Red da corrida é o teste novo:

| Critério | Teste | Falha observada |
|---|---|---|
| A-20 | `test_reserva_e_receita_nao_cobrem_a_mesma_despesa_duas_vezes` | `AssertionError: [None, None]`, `assert 2 == 1` |
| A-21 | `test_receita_e_reserva_nao_cobrem_a_mesma_despesa_duas_vezes` | `AssertionError: [None, None]`, `assert 2 == 1` |
| A-22 | `test_cobertura_automatica_e_reserva_nao_cobrem_a_mesma_despesa` | `assert False = isinstance(None, CoberturaExcedente)` |
| A-23 (i) | `test_a_mesma_referencia_devolve_o_mesmo_movimento` | `LiquidacaoRecusada('o valor passa do que falta devolver')` no lugar de `None` |
| A-23 (ii) | `test_a_mesma_referencia_com_valor_diferente_e_conflito` | `isinstance(LiquidacaoRecusada(...), MovimentoConflitante)` falso |
| A-24 (i) | `test_obrigacao_que_le_o_estado_da_apuracao_e_a_apuracao_se_serializam` | `assert Decimal('25.00') == Decimal('0.00')` |
| A-24 (ii) | `test_apuracao_que_le_os_saldos_e_a_obrigacao_se_serializam` | `assert Decimal('25.00') == Decimal('0.00')` |
| A-25 | `test_cobertura_da_obrigacao_so_de_frete_entra_no_deficit_coberto` | `assert [..10.00] == [..15.00]` |
| A-26 | `test_o_que_falta_da_obrigacao_mista_e_atribuido_primeiro_ao_frete` | `assert [..10.00] == [..13.00]` |

**Green:** `a66a663` (regra única de travas: A-20 a A-24) e `ca616ce` (R04, atribuição conservadora do frete: A-25 e A-26). Verificação em `1ad1944`: suíte completa sem filtro, **2418 passed**.
