# E09-05 — Reserva e aportes

Fatia 5 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação: como na E09-01.

## Contexto e objetivo

A reserva é capital próprio do administrador. Ela começa com um aporte de R$ 1.000,00 e pode cobrir estornos, tarifas, déficits de frete e outros prejuízos, mas nunca recursos de fornecedores nem obrigações já comprometidas. Esta fatia entrega:

- o aporte;
- o saldo comprometido, quando a reserva é designada para uma obrigação;
- o saldo livre;
- a recusa de qualquer uso acima do saldo livre;
- o alerta de insuficiência quando as obrigações sem cobertura passam do saldo livre.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9.4 | Aporte inicial de R$ 1.000,00, que não é receita. Usos permitidos. Não limita a responsabilidade e não autoriza usar recursos de fornecedores. Não pode comprometer recursos reservados para obrigações existentes. Sem recomposição automática. Saldo e alertas de insuficiência. Tudo no livro-razão. |
| Infraestrutura 3.3 | Saldo comprometido, saldo livre = saldo − comprometido, nenhuma utilização acima do livre, sem recomposição, alerta de insuficiência quando as obrigações sem cobertura superam o livre. O aporte é depositado na conta do provedor (L-9). |
| Infraestrutura 3.2 | Aporte: entrada na reserva. Escolha de origem exige o administrador com nova autenticação. |
| Infraestrutura 2 | Nova autenticação por passkey antes de aportes e movimentações entre destinações. |
| Cenários §16 | 29 e 34 (no nível do livro-razão; a devolução concluída fica na E10) |
| Testes técnicos | T-10 |
| Decisões | A1, P-3, P-4 |

## Escopo

**Dentro:**

- `registrar_aporte`.
- `designar_reserva` e `desfazer_designacao`.
- `utilizar_reserva`, o movimento de cobertura com a reserva como fonte.
- `situacao_da_reserva`: saldo, comprometido e livre.
- `obrigacoes_sem_cobertura`.
- `avaliar_reserva`, que abre ou resolve o alerta `reserva_insuficiente`.

**Fora:**

- As telas (E09-08).
- O consumo da designação na liquidação da devolução (E09-06 fornece a operação, e a E10 a chama).
- O bloqueio pelo invariante, cuja condição vem da E09-07. Esta fatia só consulta o alerta.

## Decisões técnicas

- **Aporte sem consulta ao provedor.** O administrador registra o aporte depois de depositar na conta do provedor e informa a identificação do movimento do depósito. Na fase 1, é o `id_movimento` do simulador. O registro não consulta o provedor, porque L-9 pode não permitir isso no Mercado Pago. A conferência é feita pela conciliação diária (E09-07). A identificação é única, com a chave do movimento `aporte:<identificação>`, e o mesmo depósito nunca entra duas vezes.
- **Valor do aporte.** Qualquer valor positivo. Os R$ 1.000,00 de A1 são o aporte inicial que o administrador faz, e não um valor imposto pelo sistema. O sistema nunca cria aporte sozinho (P-4).
- **Designação.** `DesignacaoDaReserva` é um registro só de inserção, com o alvo (uma `ObrigacaoComComprador`), o valor, o autor, a justificativa e o momento.
  - O desfazer é outro registro só de inserção, que cita a designação e traz justificativa.
  - O consumo é o movimento de financiamento que cita a designação (E09-06, na liquidação).
  - O comprometido é a soma das designações nem desfeitas nem consumidas.
- **Designação ou utilização.**
  - **Obrigação com comprador:** recebe uma designação. O dinheiro fica na reserva, separado para ela, até a devolução ser feita (infraestrutura 3.3).
  - **Despesa pendente** (tarifa ou déficit de frete): recebe uma utilização imediata, porque o dinheiro já saiu (a tarifa) ou precisa ir para o frete (o déficit). A utilização é um movimento F11 de `reserva` para `despesas_a_cobrir` ou `frete(r)`.
- **Novo aporte como fonte.** A infraestrutura lista receita de serviço, reserva e novo aporte. O "novo aporte" é feito como aporte seguido de designação ou utilização da reserva. Assim todo aporte passa pela reserva (A1), e a escolha continua sendo do administrador.
- **Obrigações sem cobertura:**
  - de cada obrigação com comprador, o devido menos o financiado (saldo recebido em `obrigacao_comprador`, mais o já devolvido) menos o designado;
  - mais o pendente de cada despesa.

  O alerta `reserva_insuficiente` (chave `"geral"`) fica aberto enquanto esse total for maior que o saldo livre. `avaliar_reserva` roda no fim de cada operação desta fatia e da E09-06, na mesma transação, e também na tarefa do invariante (E09-07).
- **Bloqueio pelo invariante.** Com um alerta `invariante_violado` aberto, `designar_reserva` e `utilizar_reserva` são recusados com `InvarianteViolado`. O aporte continua aceito, porque só pode melhorar o quadro.
- **Travas.** Toda operação trava a conta `reserva` antes de calcular o livre, e depois o alvo (a obrigação ou a despesa). Duas designações concorrentes nunca passam juntas do livre.

## Regras

| Operação | Quem | Recusas, sem escrita |
|---|---|---|
| `registrar_aporte(autor, valor, identificacao, justificativa)` | administrador; nova autenticação por passkey na rota (E09-08) | valor ≤ 0, `float` ou mais de duas casas; identificação vazia ou com mais de 64 caracteres; identificação já registrada (`AporteRepetido`); justificativa vazia |
| `designar_reserva(autor, obrigacao, valor, justificativa)` | administrador | valor > livre (`ReservaInsuficiente`); valor > sem cobertura da obrigação (`CoberturaExcedente`); invariante violado; justificativa vazia |
| `desfazer_designacao(autor, designacao, justificativa)` | administrador | designação já desfeita ou consumida (`DesignacaoEncerrada`); justificativa vazia |
| `utilizar_reserva(autor, despesa, valor, justificativa)` | administrador | valor > livre; valor > pendente da despesa; invariante violado; justificativa vazia |

**Efeitos:**

- **Aporte:** um movimento `aporte` F3 com a identificação, o autor e a justificativa, e uma `EntradaAuditoria`. A receita de serviço e as outras destinações não mudam (cenário 29).
- **Designação:** a designação e a auditoria. Nenhum movimento: o saldo da reserva não muda, o comprometido aumenta e o livre diminui.
- **Desfazer:** o comprometido volta, e a auditoria é gravada com a justificativa.
- **Utilização:** um movimento F11 e a auditoria. O pendente da despesa diminui, e o saldo e o livre da reserva diminuem.

Tudo termina com `avaliar_reserva()`.

**Sem recomposição:** nenhuma tarefa ou receptor cria aporte. A reserva pode ficar abaixo de R$ 1.000,00, até zero, e o sistema só alerta.

## Interfaces

- `registrar_aporte`, `designar_reserva`, `desfazer_designacao` e `utilizar_reserva`.
- `situacao_da_reserva() -> SituacaoDaReserva(saldo, comprometido, livre)`.
- `obrigacoes_sem_cobertura() -> Decimal`, com a lista detalhada em `itens_sem_cobertura()`.
- `avaliar_reserva()`.
- `DesignacaoDaReserva` e `DesignacaoDesfeita`.
- As exceções `ReservaInsuficiente`, `CoberturaExcedente`, `AporteRepetido`, `DesignacaoEncerrada` e `InvarianteViolado`.

## Invariantes

- `comprometido ≤ saldo` em todo momento. Por isso o livre nunca é negativo.
- Nenhuma utilização ou designação passa do livre.
- Uma obrigação nunca tem financiado mais designado acima do devido.
- A obrigação continua com o devido integral, qualquer que seja a reserva (A1).

## Casos-limite e concorrência

- **Duas designações concorrentes** que juntas passam do livre: uma é aceita e a outra recusada (T-10).
- **Designação concorrendo com utilização:** o mesmo, pela trava da conta `reserva`.
- **Aporte enquanto a reserva está insuficiente:** depois dele, o alerta resolve se o livre passar a cobrir as obrigações.
- **O mesmo depósito registrado duas vezes em paralelo:** um aporte, e a outra chamada levanta `AporteRepetido`.

## Dependências e decisões em aberto

Depende de E09-01, E09-03 e E09-04 (obrigação e despesa). Nenhuma decisão em aberto.

## Correção E09-R02 — travas da designação e da utilização (2026-10-22)

Origem: parecer sobre `34f9547`, R02, com a parte da utilização vinda do R01. Valem a "Regra única de travas do financeiro" e a correção E09-R08 (E09-01, `spec.md`). A regra "Travas" desta fatia (a conta `reserva` primeiro, depois o alvo) fica revogada.

### Diagnóstico

- **Ordem.** `designar_reserva` trava a `reserva` e depois a conta da obrigação. `liquidar_obrigacao` (E09-06) trava as duas em ordem crescente de `pk`. Quando a conta da obrigação nasceu antes da `reserva`, as duas operações se travam mutuamente, e uma falha com `OperationalError`, embora as duas sejam válidas em qualquer ordem serial.
- **Conta inexistente.** `designar_reserva` só trava a conta da obrigação quando ela existe. Uma obrigação sem conta pode ser coberta ao mesmo tempo pela designação e pela receita (`cobrir_obrigacao_com_receita`), e cada uma lê o sem cobertura sem ver a outra.
- **Utilização.** `utilizar_reserva` lê o pendente da despesa travando só a `reserva`. O defeito e os critérios estão na E09-06, na correção E09-R01.

### Regras

- `designar_reserva` obtém a conta `obrigacao_comprador(o)`, criando-a se ainda não existir. Trava essa conta e a `reserva` juntas, em ordem crescente de `pk`. Só depois lê o livre, o sem cobertura e o alerta de invariante.
- `utilizar_reserva` trava a `reserva` e o destino da despesa juntos, em ordem crescente de `pk`. O destino é `despesas_a_cobrir` ou `frete(r)`. Só depois lê o livre e o pendente.
- `registrar_aporte` e `desfazer_designacao` continuam travando só a `reserva`.
- Os resultados e as recusas desta fatia não mudam. Só muda o momento das leituras, que passa a ser depois de todas as travas.
