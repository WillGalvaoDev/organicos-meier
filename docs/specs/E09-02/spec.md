# E09-02 — Provedor: tarifa, liberação, saldo e movimentos da conta

Fatia 2 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação: como na E09-01.

## Contexto e objetivo

O livro-razão precisa saber três coisas que só o provedor sabe:

- quanto ele cobrou de tarifa em cada pagamento;
- quando o dinheiro de cada pagamento fica liberado;
- qual é o saldo da conta e quais movimentos ela teve, inclusive depósitos (aportes) e saídas.

Esta fatia acrescenta isso à interface `Provedor` e ao simulador, sem presumir como o Mercado Pago responde (L-8 a L-10). Ela também guarda a tarifa e a liberação no registro do pagamento.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.3 | O aporte é depositado na conta do provedor. Como aparece no extrato e na API: L-9. |
| Infraestrutura 3.4 | Cada entrada registra a data de liberação, separando valor liberado de valor a liberar (L-10). As datas variam por meio de pagamento. |
| Infraestrutura 3.5 | A conciliação diária compara o livro-razão com o saldo e os movimentos do provedor (L-9). Toda saída da conta é registrada. |
| Infraestrutura 7, fase 1 | Interface interna: consultar saldo e movimentos. O simulador reproduz datas de liberação por meio, aporte e saídas da conta. |
| Herdado da E07 | Acrescentar à interface e ao simulador saldo, movimentos, aporte, saídas e datas de liberação, sem presumir o Mercado Pago. |
| Especificação §9.2 e §9.3 | Tarifas do provedor são despesas operacionais. |

## Escopo

**Dentro:**

- `PagamentoConsultado` com `tarifa` e `liberado_em`.
- Os campos novos em `PagamentoNoProvedor`, preenchidos pela sincronização.
- Os métodos `consultar_saldo` e `listar_movimentos` no protocolo e no simulador.
- Os controles do simulador para tarifa, liberação, depósito, saída e divergência.
- Dois formulários novos na tela do simulador (E08-07): depositar e registrar saída.

**Fora:**

- O estorno pela API e os movimentos de devolução (E10). O tipo `devolucao` já existe na lista, mas o simulador só o gera na E10.
- O uso desses dados pelo livro-razão (E09-04 e E09-07).

## Decisões técnicas

- **Campos opcionais na resposta.** `tarifa: Decimal | None` e `liberado_em: datetime | None`, com padrão `None`. `None` quer dizer "o provedor não informou", e nunca zero: um pagamento sem `liberado_em` conta como **a liberar**. Essa leitura conservadora atende a L-10 sem presumir o Mercado Pago.
- **Gravação pela sincronização.** `sincronizar_pagamento` continua o único que escreve em `PagamentoNoProvedor` (cenário 37). Ela grava `tarifa` e `liberado_no_provedor_em` quando a resposta os traz e o registro ainda não os tem. Depois de gravados, um valor diferente numa consulta seguinte não é aplicado e vira divergência, com os novos códigos `tarifa` e `liberacao` em `DivergenciaDaConsulta`. É a mesma regra do `aprovado_em`.
- **Simulador.**
  - **Tarifa:** um plano por meio, com percentual sobre o valor e parte fixa, ambos `Decimal`. O padrão é zero. A tarifa é calculada na aprovação, arredondada uma vez a centavos com `ROUND_HALF_UP` e gravada na cobrança simulada.
  - **Liberação:** um prazo em horas por meio, com padrão 0. `liberado_em = aprovado_em + prazo`.
  - **Movimentos da conta:** ficam numa tabela nova do simulador, `MovimentoSimulado`, no banco do simulador. A aprovação gera um movimento `pagamento` (+valor) e, havendo tarifa, um movimento `tarifa` (−tarifa). O controle `depositar` gera `deposito` (+valor), e `registrar_saida` gera `saida` (−valor).
  - **Saldo:** liberado é a soma dos movimentos com `liberado_em ≤ agora`; a liberar é o resto. O movimento `tarifa` tem o mesmo `liberado_em` do pagamento, porque é descontado do valor dele. Depósitos, saídas e ajustes são liberados no ato.
- **Falhas.** O plano de falhas da E07 (`indisponivel`, `falhar_proximas`) vale também para `consultar_saldo` e `listar_movimentos`, com os nomes de operação iguais aos dos métodos.
- **Divergência de teste.** O controle `ajustar_saldo(valor)` cria um movimento `ajuste` que nenhum registro do sistema explica. Ele serve para provar a conciliação (E09-07) e só existe no simulador.

## Regras

**Tipos novos em `apps.pagamentos.provedor`:**

| Tipo | Campos |
|---|---|
| `SaldoNoProvedor` | `liberado`, `a_liberar` (`Decimal`, podem ser negativos), `consultado_em` (UTC) |
| `MovimentoNoProvedor` | `id_movimento` (texto, até 64), `tipo` (`pagamento`, `tarifa`, `deposito`, `saida`, `devolucao`, `ajuste`), `valor` (`Decimal` com sinal, nunca zero), `id_externo` (pagamento, só para `pagamento`, `tarifa` e `devolucao`, ou `None`), `ocorrido_em` e `liberado_em` (UTC; `liberado_em` pode ser `None`) |

**Métodos novos do protocolo:**

- `consultar_saldo() -> SaldoNoProvedor`.
- `listar_movimentos(desde, ate) -> list[MovimentoNoProvedor]`, com `desde ≤ ocorrido_em < ate`, em ordem de `ocorrido_em` e `id_movimento`. Sem fuso: `InstanteSemFuso`. Com `desde > ate`: `ValueError`.

Os dois levantam `ProvedorIndisponivel` como os outros métodos.

**Controles novos do simulador** (`apps.simulador_pagamentos.controle`):

- `definir_tarifa(meio, *, percentual, fixa)`;
- `definir_liberacao(meio, *, horas)`;
- `depositar(valor, *, em=None) -> id_movimento`;
- `registrar_saida(valor, *, descricao, em=None) -> id_movimento`;
- `ajustar_saldo(valor, *, em=None) -> id_movimento`.

Valores com `float`, zero ou negativos em depósito e saída são recusados com `ValueError`. `reiniciar()` zera os planos e apaga os movimentos.

**Tela do simulador.** São dois formulários na lista do simulador:

- "Depositar na conta" (valor), para o administrador fazer o aporte na homologação;
- "Registrar saída da conta" (valor e descrição), para repasse ou retirada.

Valem as mesmas políticas e o mesmo 404 sem o simulador configurado da E08-07. O teste de fronteira de rotas (E08-07 A-9) passa a listar as sete rotas do simulador.

## Interfaces

Os tipos e métodos acima. Também `PagamentoNoProvedor.tarifa` (dinheiro, nulo) e `PagamentoNoProvedor.liberado_no_provedor_em` (nulo), com a migração.

## Invariantes

- Nenhum método do provedor escreve em tabelas do sistema. O simulador grava só no banco dele.
- A soma dos movimentos do simulador é exatamente `liberado + a_liberar`.
- `tarifa` e `liberado_no_provedor_em`, uma vez gravados, não mudam.
- Todos os instantes da interface estão em UTC.

## Casos-limite e concorrência

- **Pagamento aprovado e depois cancelado no simulador:** o simulador nunca deixa isso acontecer, porque o estado terminal não muda (E07-01). O movimento de pagamento continua.
- **Liberação exatamente em `agora`:** conta como liberado, com o limite inclusivo.
- **Consulta do pagamento antes da aprovação:** `tarifa` e `liberado_em` vêm `None`.
- **Duas aprovações concorrentes do mesmo pagamento no simulador:** um único par de movimentos (`pagamento` e `tarifa`), pela trava da cobrança da E07-01.

## Dependências e decisões em aberto

- Depende de E07 e E08-07.
- **L-8, L-9 e L-10 continuam abertas.** A fase 2a traduz o Mercado Pago para estes tipos. Se a API não der algum dado, a conciliação desse ponto fica manual, como a infraestrutura prevê.
