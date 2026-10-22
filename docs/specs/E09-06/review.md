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
