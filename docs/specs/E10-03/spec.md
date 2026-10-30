# E10-03 — Provedor e simulador: estorno, consulta de estornos e contestação

Fatia 3 de 7 da milestone **E10 — Devoluções**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E10-01.
- Referência de apoio: `docs/referencias/mercado-pago-api.md` (aprovada como material de apoio em `0b53825`), seções 7, 9 e 10.

## Contexto e objetivo

A interface do provedor (E07) ainda não sabe devolver dinheiro. Esta fatia acrescenta a ela duas operações:
- o **estorno** de um pagamento aprovado, total ou parcial, com chave de idempotência;
- a **consulta dos estornos** de um pagamento.

O simulador passa a reproduzir os comportamentos que a infraestrutura exige para a fase 1:
- estorno parcial;
- falha temporária, inclusive com a resposta perdida depois de executar;
- falha definitiva;
- saldo insuficiente;
- estorno que fica em processamento e termina depois;
- o risco residual de um estorno recusado que o provedor conclui mais tarde;
- a contestação, como débito na conta.

A interface continua neutra: ela não decide regra de negócio. O que cada resposta significa para a parcela de devolução é decidido na E10-04.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 7, fase 1 | Interface com "estornar". O simulador reproduz estorno parcial, falha temporária, falha definitiva, saldo insuficiente, contestação e API fora do ar. |
| Infraestrutura 4.2 | A chave de idempotência é gravada antes da chamada, uma por parcela de devolução, e reaproveitada nas novas tentativas. |
| Infraestrutura 4.7 | A reconsulta das devoluções no provedor vem antes de declarar falha definitiva. O risco residual é a conclusão tardia de uma devolução declarada como falha definitiva. |
| Infraestrutura 3.3 | O provedor só estorna com saldo disponível. |
| Especificação §9.6 (Q-8) | Contestação e MED: na fase 1, o simulador reproduz o débito, e a conciliação o aponta como divergência. Os lançamentos automáticos ficam para as fases 2a e 2b. |
| Herdado da E07 | `estornar` na interface `Provedor` e no simulador, com parcial, falha temporária, falha definitiva e saldo insuficiente. |
| Herdado da E09 | O movimento `devolucao` no provedor e no simulador. |
| Referência do Mercado Pago, §7 | `X-Idempotency-Key` obrigatório; total ou parcial; 180 dias depois da aprovação; saldo disponível; contingência com HTTP 400 e o reembolso em andamento; consulta individual e listagem de reembolsos. |

## Escopo

**Dentro:**
- Os tipos e as duas operações novas da interface.
- O campo `id_estorno` em `MovimentoNoProvedor`.
- O estorno e os controles no simulador.
- A contestação no simulador.
- O ajuste da seção 10 da referência do Mercado Pago, nas linhas que esta fatia muda.

**Fora:**
- A parcela de devolução e o que fazer com cada resposta (E10-04).
- O par do estorno na conciliação (E10-05).
- Os lançamentos da contestação (Q-8, fases 2a e 2b).
- A tradução real do Mercado Pago (fase 2a).

## Interface (`apps.pagamentos.provedor`)

| Elemento | Definição |
|---|---|
| `SituacaoDoEstorno` | `em_processamento`, `concluido` e `recusado` |
| `NovoEstorno` | `id_externo` (o pagamento), `valor` (`Decimal`, maior que zero, 2 casas) e `chave_idempotencia` (texto, 1 a 64 caracteres). O `__post_init__` recusa o que não cumprir isso com `ValueError` |
| `EstornoConsultado` | `id_estorno` (texto opaco, até 64), `id_externo`, `valor`, `situacao`, `codigo` (o motivo da recusa, ou `None`), `criado_em` e `concluido_em` (UTC, ou `None`) |
| `Provedor.estornar(novo: NovoEstorno) -> EstornoConsultado` | pede o estorno. A resposta traz `concluido` ou `em_processamento` |
| `Provedor.consultar_estornos(id_externo: str) -> list[EstornoConsultado]` | os estornos do pagamento que o provedor mostra, por `criado_em` e `id_estorno` |
| `SaldoInsuficienteParaEstorno(Exception)` | o provedor não estornou por falta de saldo disponível. **Não é definitiva:** pode tentar de novo com a mesma chave depois de um aporte |
| `MovimentoNoProvedor.id_estorno` | `str | None`, com padrão `None`. Preenchido só nos movimentos `devolucao`, com o `id_estorno` |

**Erros de `estornar`:**
- `ProvedorIndisponivel`: temporária.
- `SaldoInsuficienteParaEstorno`: temporária.
- `PagamentoNaoEncontrado`.
- `RecusaDoProvedor(codigo)`: definitiva, com um destes códigos:
  - `prazo_vencido`;
  - `meio_nao_permite_estorno`;
  - `parcial_nao_suportado`;
  - `estado_invalido`;
  - `valor_acima_do_disponivel`;
  - `chave_em_uso`.

`consultar_estornos` levanta `ProvedorIndisponivel` ou `PagamentoNaoEncontrado`.

## Regras do simulador

**Registro.** `EstornoSimulado`, no banco do simulador, com:
- a cobrança;
- a chave de idempotência, única;
- o valor;
- a situação e o código;
- `criado_em` e `concluido_em`;
- `visivel`, um booleano com padrão verdadeiro.

O `id_estorno` é `sim-est-<pk>`.

**`estornar`.** Passa pelo mesmo `_executar` das outras operações, com o nome `estornar`. Assim, `indisponivel()` e `falhar_proximas(..., operacao="estornar", depois_de_executar=...)` valem para ele. A ordem das verificações é:
1. **A chave já existe:**
   - com o mesmo pagamento e o mesmo valor, devolve o estorno existente, na situação atual dele, sem nada novo;
   - com outro pagamento ou outro valor, `RecusaDoProvedor("chave_em_uso")`.
2. **O pagamento não existe:** `PagamentoNaoEncontrado`.
3. **O pagamento não está aprovado:** `estado_invalido`.
4. **A aprovação foi há mais de 180 dias, pelo relógio controlado:** `prazo_vencido`.
5. **Há recusa programada para o pagamento** (`recusar_estornos`): `RecusaDoProvedor` com o código programado.
6. **Estorno parcial não suportado** (`sem_estorno_parcial`) e o valor é menor que o restante: `parcial_nao_suportado`.
7. **O valor passa do restante:** `valor_acima_do_disponivel`. O restante é o valor do pagamento menos os estornos `concluido` e `em_processamento`, inclusive os invisíveis.
8. **O saldo liberado da conta simulada é menor que o valor:** `SaldoInsuficienteParaEstorno`. O saldo liberado é a soma dos movimentos com `liberado_em ≤ agora`.
9. **Caso contrário,** grava o estorno:
   - `concluido` por padrão, com um `MovimentoSimulado` `devolucao` de −valor, o `id_externo` do pagamento, o `id_estorno`, a descrição `refund` e `liberado_em` igual ao instante;
   - `em_processamento`, sem movimento, se o pagamento tiver `estornos_em_processamento` programado.

Nos passos 1 a 8, nada é gravado, salvo no modo de recusa com processamento (abaixo).

**A tarifa não volta.** O estorno debita só o valor estornado (L-7 continua aberta, referência §7). A tarifa do pagamento continua debitada.

**Controles novos (`apps.simulador_pagamentos.controle`)**, todos apagados por `reiniciar()`:

| Controle | Efeito |
|---|---|
| `estornos_em_processamento(id_externo)` | os próximos estornos do pagamento nascem `em_processamento` |
| `concluir_estorno(id_estorno, *, em=None)` | `em_processamento` vira `concluido`, com o movimento `devolucao` no instante; o estorno passa a ser visível |
| `recusar_estorno(id_estorno, codigo)` | `em_processamento` vira `recusado`, sem movimento |
| `recusar_estornos(id_externo, codigo)` | os próximos estornos do pagamento são recusados com o código (passo 5) |
| `recusar_mas_processar(id_externo, codigo)` | o próximo estorno do pagamento grava um `EstornoSimulado` `em_processamento` **invisível** e levanta `RecusaDoProvedor(codigo)`. `consultar_estornos` não o mostra até `concluir_estorno`. Reproduz o risco residual da infraestrutura 4.7 |
| `sem_estorno_parcial(id_externo)` | o pagamento só aceita estorno do restante inteiro (passo 6) |
| `contestar(id_externo, valor=None, *, descricao="chargeback", em=None)` | um `MovimentoSimulado` `outro` com −valor (o valor do pagamento, se omitido), a descrição `chargeback` ou `med` e o `id_externo`. A situação do pagamento não muda, nenhum aviso é criado e nada é gravado no sistema |

`concluir_estorno` e `recusar_estorno` só aceitam estorno `em_processamento`; fora disso, `ValueError`. `contestar` aceita só pagamento aprovado e valor entre 0,01 e o valor do pagamento.

**`consultar_estornos`.** Devolve os estornos visíveis do pagamento.

**`listar_movimentos`.** Leva o `id_estorno` nos movimentos `devolucao`.

## Decisões técnicas

- **Saldo insuficiente não é recusa definitiva.** A referência (§7) mostra que falta de saldo se resolve com aporte. Uma exceção própria evita que a E10-04 trate esse caso como inviável (P-5).
- **Valor sempre explícito.** A interface manda o valor mesmo no estorno do restante inteiro. A tradução da fase 2a decide se envia o `amount` ou não.
- **`id_estorno` no movimento.** O par da conciliação (E10-05) precisa identificar o estorno, e não só o pagamento, porque um pagamento pode ter vários estornos de mesmo valor. Como o rótulo real dos relatórios ainda está a confirmar (L-8, L-9), a tradução da fase 2a o preenche pelo campo que as amostras mostrarem.
- **Contestação sem efeito no sistema.** Pela Q-8, os lançamentos e a suspensão automáticos entram só com o meio real. O simulador gera apenas o débito que a conciliação já aponta como `outro` (E09-07).
- **Referência do Mercado Pago.** O implementador atualiza a seção 10 da referência nas linhas "Reembolso Pix em processamento" e "Reembolso e contestação no `status`". Elas passam a dizer o que o simulador reproduz. A revisão desta fatia confere essa atualização.

## Invariantes

- **Estornos do pagamento.** A soma dos estornos `concluido` e `em_processamento` nunca passa do valor do pagamento.
- **Idempotência.** A mesma chave nunca produz dois estornos.
- **Movimento.** Todo estorno `concluido` tem exatamente um movimento `devolucao` de −valor, e nenhum outro estorno tem movimento.
- **Saldo.** O saldo simulado cai exatamente pelo valor estornado.

## Casos-limite

- **Falha depois de executar** (`depois_de_executar=True`): o estorno fica gravado no simulador, e a resposta se perde. A repetição com a mesma chave devolve o mesmo estorno, como no T-8.
- **Dois `estornar` concorrentes com a mesma chave:** um estorno só, pela unicidade da chave no banco do simulador. O segundo devolve o primeiro.
- **Estorno parcial seguido de outro parcial:** os dois são aceitos até o restante.

## Dependências e decisões em aberto

Depende de E07 (interface, simulador e plano de falhas) e de E09-02 (movimentos e saldo). Nenhuma decisão em aberto. O comportamento real fica para a L-7 (fase 2a).

## Correção E10-R02 — saldo comum disputado por estornos de pagamentos diferentes (2026-10-30)

Origem: parecer sobre `9ce04ad`, R02 (`docs/specs/E10-03/review.md`). Vale a correção E10-R08 (E10-07, `spec.md`).

### Diagnóstico

O passo 8 de `estornar` confere o saldo liberado da conta simulada. A trava, porém, é a da cobrança: ela serializa os estornos do mesmo pagamento, mas não os de pagamentos diferentes. O recurso que os dois consomem é o saldo da conta, comum a todos os pagamentos. Duas transações leem o mesmo saldo, as duas aceitam, e o saldo liberado fica negativo (−60,00 na prova do revisor).

### Regras

- **O saldo liberado da conta simulada é um recurso único.** Toda operação do simulador que lê esse saldo para aceitar um débito toma uma **trava do saldo**, comum à conta, antes da leitura. Hoje, a única operação assim é `estornar`.
- **Ordem:** a trava da cobrança primeiro, a trava do saldo depois. Os estornos de pagamentos diferentes ficam serializados só no trecho do saldo, e não há inversão.
- **Forma da trava:** é escolha do implementador, registrada no `review.md`. As duas formas aceitas são uma trava consultiva de transação do PostgreSQL (`pg_advisory_xact_lock`, com uma chave constante e nomeada, na conexão do simulador) ou uma linha única da conta simulada travada com `select_for_update`. A trava acaba com a transação do simulador.
- **A recusa não muda:** quem perde a disputa recebe `SaldoInsuficienteParaEstorno`, que é **temporária** (passo 8), e não uma `RecusaDoProvedor`. Na E10-04, isso leva a parcela a `falha_temporaria` com `saldo_insuficiente`, como no A-11 de lá.
- Os controles de teste que registram saídas (`registrar_saida`) representam débitos externos à plataforma e não validam saldo; não mudam.
- **Limite de verificação (L-7):** o tratamento real do Mercado Pago para estornos concorrentes com saldo insuficiente não está validado. O simulador adota o comportamento conservador: o saldo nunca fica negativo por estornos.

### Invariante acrescentado

- Nenhuma combinação de estornos aceitos pelo simulador deixa o saldo liberado abaixo de zero.

## Correção E10-R02 residual — saldo comprometido por estornos em processamento (2026-10-30)

Origem: nova revisão sobre `74b38c0`, R02 residual (`docs/specs/E10-03/review.md` e `docs/specs/E10-07/review.md`, "Nova revisão independente das correções"). Vale a correção E10-R08 (E10-07, `spec.md`). Nenhuma regra comercial muda.

### Diagnóstico

A trava do saldo da correção E10-R02 serializa as aceitações, mas a conferência do passo 8 lê só os movimentos liberados. Um estorno aceito `em_processamento` ainda não tem movimento. Por isso ele não reduz o saldo que a aceitação seguinte confere, e o débito só entra na conclusão (`concluir_estorno`), que não confere nada. Duas cobranças de 80,00 e uma saída de 60,00 deixam 100,00 liberados. Os dois estornos de 80,00 são aceitos em processamento, e a conclusão dos dois leva o saldo a −60,00, sem concorrência nenhuma.

### Regras

- **O estorno aceito compromete o saldo na aceitação, e não na conclusão.** No passo 8 de `estornar`, sob a trava do saldo, o valor conferido passa a ser o **saldo disponível para estorno**: o saldo liberado no instante menos a soma dos estornos `em_processamento` da conta simulada, de todos os pagamentos. A soma inclui os invisíveis de `recusar_mas_processar`, porque o provedor os está processando. Quando esse saldo for menor que o valor, a função levanta `SaldoInsuficienteParaEstorno` (temporária), como antes.
- **A conclusão não confere o saldo de novo.** O débito de um estorno em processamento já foi reservado na aceitação, e `concluir_estorno` só o transforma em movimento. Recusar a conclusão de um estorno aceito seria uma regra nova do provedor, e o comportamento real é limite L-7.
- **A recusa de um estorno em processamento** (`recusar_estorno`) libera o valor comprometido: ele sai da soma e não gera movimento.
- **Leitura coerente.** As duas somas do passo 8 (movimentos liberados e estornos em processamento) são lidas sob a trava do saldo. `concluir_estorno` e `recusar_estorno` também tomam a trava do saldo, depois da trava do estorno e na mesma transação da mudança. Uma aceitação nunca enxerga um estorno que saiu de `em_processamento` sem enxergar o movimento correspondente, nem o contrário. A ordem é sempre a mesma: primeiro a trava da cobrança ou do estorno, e a do saldo por último. Não há inversão, porque `estornar` não trava linhas de estorno existentes.
- **`consultar_saldo` não muda.** Ele continua informando o saldo liberado pelos movimentos, que é o que a conciliação da E09 compara. O comprometimento é uma regra interna da aceitação do simulador.
- **Débitos externos.** Os controles `registrar_saida`, `ajustar_saldo` e `contestar` representam débitos fora da plataforma e continuam sem validar saldo (regra já aprovada). Um débito desses, feito depois da aceitação, pode levar o saldo liberado abaixo de zero quando o estorno concluir. Nesse caso, nenhuma aceitação nova passa enquanto o saldo disponível for menor que o valor.
- **Limite de verificação (L-7):** como o Mercado Pago reserva o saldo de estornos em processamento não está validado. O simulador adota o comportamento conservador.

### Invariante reescrito

O invariante "Nenhuma combinação de estornos aceitos pelo simulador deixa o saldo liberado abaixo de zero" passa a ser:

- **Depois de toda aceitação de estorno,** o saldo liberado menos os estornos `em_processamento` é maior ou igual a zero.
- **Por consequência, sem débitos externos,** nenhuma sequência de aceitações, conclusões e recusas de estornos deixa o saldo liberado abaixo de zero.
- **Só os débitos externos de controle** podem deixá-lo negativo.
