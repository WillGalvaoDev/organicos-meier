# E09-03 — Alertas financeiros

Fatia 3 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação: como na E09-01.

## Contexto e objetivo

Vários pontos da E09 precisam avisar o administrador: o invariante violado, a reserva insuficiente, a conciliação com divergência ou com pagamento sem lançamento, e os pagamentos aprovados depois da margem ou em duplicidade. Esta fatia cria o alerta financeiro: um registro com abertura e resolução, aberto uma vez por situação e enviado ao administrador no site e por e-mail. As fatias seguintes só chamam `abrir_alerta` e `resolver_alerta`.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.6 | Alertas gerados por tarefas agendadas e enviados ao admin. A lista inclui violação do invariante, insuficiência da reserva, pagamento sem conciliação, pagamento aprovado depois de `T0 + 48h`, duplicidade e divergência na conciliação diária. |
| Infraestrutura 3.3 e 3.4 | Alerta de insuficiência da reserva. Alerta crítico na violação do invariante. |
| Especificação §9.4 | O sistema apresenta alertas de insuficiência. |
| Especificação §12 | Registrar envio e falhas; falha de mensagem não altera o estado financeiro. |
| Herdado da E04 | Emitir com `emitir_evento`, na transação do fato, com chave derivada do fato. |

## Escopo

**Dentro:**

- O modelo `AlertaFinanceiro`.
- Os serviços `abrir_alerta`, `resolver_alerta` e `alertas_abertos`.
- O evento `alerta_financeiro` no catálogo, para o administrador, no site e por e-mail.

**Fora:**

- As condições de cada alerta, que ficam nas fatias que as detectam (E09-04, E09-05 e E09-07).
- Os alertas de devolução (falha, falha definitiva, elegível para excepcional), que são da E10.
- Tarefa atrasada e falha de mensagem, que são da E15.
- A tela (E09-08). O painel consolidado é da E15.

## Decisões técnicas

- **Um alerta aberto por situação.** O alerta é identificado por `(tipo, chave)`. A chave é derivada do fato: o `id_externo` do pagamento, o `id_movimento` do provedor, a data da conciliação, ou `"geral"` nos alertas de estado global. Uma restrição `UNIQUE` parcial (só para os abertos) garante no máximo um aberto por par. Abrir de novo um alerta já aberto devolve o existente, sem atualizar e sem novo aviso. Depois de resolvido, a mesma situação pode abrir um alerta novo, e o histórico fica.
- **Gravidade por tipo**, numa tabela fixa:

  | Tipo | Gravidade | Quem abre | Quem resolve |
  |---|---|---|---|
  | `invariante_violado` | crítico | E09-07 | E09-07, quando o invariante volta a valer |
  | `reserva_insuficiente` | aviso | E09-05 | E09-05, quando a condição deixa de valer |
  | `pagamento_sem_conciliacao` | aviso | E09-07 | E09-07, quando o pagamento ganha lançamento |
  | `divergencia_na_conciliacao` | aviso | E09-07 | E09-07, numa conciliação posterior sem a divergência |
  | `aprovado_apos_a_margem` | aviso | E09-04 | `liquidar_obrigacao` (E09-06), chamada pela E10, quando a obrigação fica totalmente liquidada |
  | `duplicidade` | aviso | E09-04 | `liquidar_obrigacao` (E09-06), chamada pela E10, quando a obrigação fica totalmente liquidada |

- **Aviso ao administrador.** Só a abertura avisa, pelo evento novo `alerta_financeiro` (site e e-mail), na mesma transação, com a chave `alerta_financeiro:<pk do alerta>:<conta>`. O WhatsApp não entra, porque o canal é dos compradores (E04-04). O e-mail segue a fila da E04: uma falha de envio não desfaz o alerta. Uma resolução não avisa.
- **Dados sem informação pessoal.** `dados` (JSON) guarda identificadores e valores (pagamento, pedido, rodada, valor, diferença), sem nome, e-mail ou telefone, e passa pela mesma recusa de termos de segredo da auditoria.
- **Mudança no catálogo da E04.** `DESTINATARIO_POR_EVENTO` passa a mandar para o administrador os dois eventos de alerta: `falha_no_pedido_formal` e `alerta_financeiro`. Os demais continuam iguais.

## Regras

- `abrir_alerta(tipo, chave, dados) -> AlertaFinanceiro`:
  - exige transação;
  - com um aberto do mesmo par, devolve-o;
  - senão, cria o alerta, emite o aviso e registra um log `warning` (`crítico` vira `error`), com o tipo e a chave.
- `resolver_alerta(tipo, chave, *, motivo) -> AlertaFinanceiro | None`:
  - grava `resolvido_em` e o `motivo` (texto fixo da regra) no aberto;
  - sem aberto, devolve `None` e não escreve nada.
- `alertas_abertos(tipo=None)` devolve em ordem de abertura, os críticos primeiro.
- Tipo desconhecido: `ValueError`. Chave vazia ou com mais de 64 caracteres: `ValueError`.

**Título e corpo do aviso:**

| Tipo | Título | Corpo |
|---|---|---|
| `invariante_violado` | "Alerta crítico: saldo do provedor abaixo das obrigações" | a diferença em reais; "Utilizações da reserva e retiradas de receita estão bloqueadas." |
| `reserva_insuficiente` | "Reserva insuficiente" | as obrigações sem cobertura e o saldo livre, em reais |
| `pagamento_sem_conciliacao` | "Pagamento sem conciliação" | o `id_externo` e o valor |
| `divergencia_na_conciliacao` | "Divergência na conciliação diária" | a data e a diferença, ou o movimento sem par |
| `aprovado_apos_a_margem` | "Pagamento aprovado depois da margem" | o pedido, o valor e "gerou obrigação de devolução integral" |
| `duplicidade` | "Pagamento em duplicidade" | o pedido, o valor e "gerou obrigação de devolução integral" |

O link do aviso aponta para a tela financeira (E09-08). Enquanto ela não existir, aponta para `/inicio/`.

## Interfaces

- `TipoDeAlerta` e `Gravidade` (`TextChoices`).
- `AlertaFinanceiro`, com `tipo`, `chave`, `gravidade`, `dados`, `aberto_em`, `resolvido_em` e `motivo_da_resolucao`.
- `abrir_alerta`, `resolver_alerta` e `alertas_abertos`.
- `Evento.ALERTA_FINANCEIRO`.

## Invariantes

- Nunca há dois alertas abertos com o mesmo `(tipo, chave)`.
- Um alerta resolvido não volta a aberto.
- Cada abertura gera exatamente um aviso por administrador.

## Casos-limite e concorrência

- **Duas transações abrem o mesmo alerta ao mesmo tempo:** um registro só e um aviso só. A segunda devolve o existente, pela restrição `UNIQUE` parcial com tratamento do conflito, como no `agendar_chamada` da E07.
- **A transação que abriu o alerta é desfeita:** nem o alerta nem o aviso ficam.
- **Nenhum administrador cadastrado:** o alerta é gravado sem aviso, e o log registra o motivo.

## Dependências e decisões em aberto

Depende de E04 (emissão) e de E09-01. Nenhuma decisão em aberto.
