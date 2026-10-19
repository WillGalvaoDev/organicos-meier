# E07-05 — Recebimento idempotente dos avisos do provedor

Fatia 5 de 6 da milestone **E07 — Simulador de pagamentos e integração**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O provedor avisa o sistema por webhook quando um pagamento muda. O aviso só avisa: não é prova de pagamento (infraestrutura 4.2). Ele pode chegar atrasado, repetido, fora de ordem ou nunca chegar.

Esta fatia entrega a rota que recebe os avisos:

1. confere a autenticidade pelo provedor;
2. registra o aviso uma única vez, pelo identificador do evento;
3. agenda a consulta do pagamento (E07-04);
4. responde rápido, sem chamar o provedor.

O estado do pagamento só muda quando a consulta volta (E07-03).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §15 | Idempotência em webhooks. Validação de autenticidade de eventos da plataforma de pagamentos. Separar o tempo do evento financeiro e o do recebimento do webhook. Nenhum reconhecimento duplicado de pagamento, inclusive com webhooks concorrentes. |
| Especificação §8.3 | Repetição de evento nunca autoriza pedido duplicado. A aceitação depende do horário de aprovação do provedor, e não do horário da notificação. |
| Cenários §16 | 17 (parte do pagamento). |
| Infraestrutura 4.2 | "O webhook só avisa: o sistema verifica a assinatura [Validar L-11], registra o evento com chave única e uma tarefa consulta `GET /v1/payments/{id}` antes de aplicar qualquer estado." A ordem de chegada dos eventos não altera o resultado. |
| Infraestrutura 5 | `UNIQUE` em eventos de webhook. Nenhum dado pessoal em logs. |
| Testes técnicos | T-6: "Webhook repetido 5 vezes, em paralelo, reconhece o pagamento uma única vez." |
| E02-10 | Toda rota declara uma política; a varredura acusa rota sem política. |
| E07-01, E07-03, E07-04 | `verificar_aviso`, `sincronizar_pagamento`, `agendar_chamada` e `consultar_pagamento`. |

## Escopo

**Dentro:**

- O modelo `AvisoRecebido`.
- A função `receber_aviso` e a rota `POST /pagamentos/avisos/`.
- A ligação do simulador (`entregar_avisos`, E07-01) com essa função.

**Fora:**

- O formato e a assinatura reais do Mercado Pago (L-11, fase 2a).
- O efeito do pagamento no pedido (E08).
- O alerta de avisos recusados em sequência (E15).

## Decisões técnicas

- **Rota pública, protegida pela assinatura.** O provedor não tem sessão nem token CSRF. A rota usa a política `publica` (E02-10), com `csrf_exempt` e só `POST`. A autenticidade vem de `verificar_aviso` do provedor configurado.
- **Nada do corpo vira estado.** Do aviso se guardam o identificador do evento, o tipo, o `id_externo` e o instante de recebimento. Situação, valor e horários vêm só da consulta. Um aviso forjado com assinatura válida, ou repetido, no máximo provoca uma consulta a mais.
- **Uma consulta por pagamento, mesmo com muitos avisos.** O agendamento é idempotente por (operação, alvo) (E07-04).
- **Respostas:**
  - 200 para o aviso aceito, novo ou repetido. O provedor para de reenviar;
  - 401 para assinatura inválida;
  - 400 para corpo acima de 64 KiB;
  - 405 para métodos diferentes de `POST`;
  - 500 só para erro inesperado do banco. O provedor reenviaria, e o reenvio é seguro.
- **Tipos desconhecidos** são registrados e respondem 200, sem consulta. Um tipo novo do provedor não faz o provedor reenviar para sempre.

## Regras

**Modelo `AvisoRecebido`** (`apps/pagamentos/models.py`, `RegistroSoInsercao` com a trigger):

- `provedor`, `id_evento`, `tipo`, `id_externo` e `recebido_em`;
- `UNIQUE (provedor, id_evento)`.

**Função** (`apps/pagamentos/avisos.py`):

```
receber_aviso(corpo: bytes, cabecalhos: Mapping[str, str]) -> int
```

1. Corpo acima de 64 KiB: devolve 400, sem gravar nada.
2. `aviso = obter_provedor().verificar_aviso(corpo, cabecalhos)`. Com `AvisoInvalido`, devolve 401, sem gravar nada, e registra no log `"Aviso de pagamento recusado"`, sem o corpo nem os cabeçalhos.
3. Numa transação:
   - insere o `AvisoRecebido` com `recebido_em = agora()`, por `INSERT ... ON CONFLICT DO NOTHING`;
   - se o aviso é novo e o `tipo` é `pagamento`, chama `agendar_chamada("consultar_pagamento", aviso.id_externo, parametros={"origem": "aviso", "aviso_recebido_em": <recebido_em em ISO 8601 UTC>})`;
   - se o aviso é repetido, não agenda nada.
4. Devolve 200.

**Rota:** `POST /pagamentos/avisos/`, nome `pagamentos_avisos`, view `avisos` em `apps/pagamentos/views.py`, com `@publica`, `@csrf_exempt` e `@require_POST`. Ela lê `request.body` e os cabeçalhos e devolve uma resposta vazia com o código de `receber_aviso`. A rota não exige login, e os middlewares de conta (E02) não interferem com o anônimo.

**Simulador:** `entregar_avisos` (E07-01) passa a usar `receber_aviso` como receptor padrão. O receptor injetável continua disponível para os testes da E07-01.

**Log:** `"Aviso de pagamento <id_evento>: novo"` ou `"... repetido"`, com o `id_externo`. Sem corpo e sem cabeçalhos.

## Interfaces

- `apps/pagamentos/models.py`: `AvisoRecebido`, com a migração e a trigger.
- `apps/pagamentos/avisos.py`: `receber_aviso` e `TAMANHO_MAXIMO_DO_AVISO`.
- `apps/pagamentos/views.py` e `config/urls.py`: a rota.

## Invariantes

- Cada (provedor, id_evento) é registrado no máximo uma vez.
- Nenhum aviso muda diretamente a situação de um pagamento.
- Um aviso com assinatura inválida não grava nada.

## Casos-limite e concorrência

- **Mesmo aviso cinco vezes em paralelo (T-6):** um `AvisoRecebido`, uma chamada agendada, uma consulta executada, um registro de pagamento e um único reconhecimento da aprovação (uma auditoria, um sinal).
- **Avisos fora de ordem:** o aviso da criação chega depois do da aprovação. A consulta devolve a situação atual (`aprovado`), e a ordem não muda o resultado.
- **Aviso perdido:** nenhuma consulta é agendada por aviso. O pagamento só é encontrado por outra via: a consulta antes das decisões (E07-06) e, na E08, as reconsultas da margem.
- **Avisos diferentes do mesmo pagamento antes da consulta:** dois `AvisoRecebido` e uma chamada `pendente`. `primeiro_aviso_em` fica com o recebimento do primeiro aviso.
- **Aviso de um pagamento já consultado e concluído:** agenda uma nova consulta, porque a chamada anterior não está mais `pendente`. Se nada mudou, a consulta só acrescenta o histórico (E07-03).
- **Aprovação na margem com aviso depois de `T0 + 48h`:** o aviso chega tarde, mas `aprovado_no_provedor_em` vem do provedor. A E08 decide pelo horário do provedor.

## Dependências e decisões em aberto

- Depende de E02-10, E07-01, E07-03 e E07-04.
- Sem decisões em aberto.
