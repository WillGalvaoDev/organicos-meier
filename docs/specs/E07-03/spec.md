# E07-03 — Registro dos pagamentos e reconhecimento único

Fatia 3 de 6 da milestone **E07 — Simulador de pagamentos e integração**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O sistema só sabe de um pagamento pelo que o provedor responde numa consulta (infraestrutura 4.2). Esta fatia entrega o registro dessas respostas:

- um registro por pagamento do provedor, único pelo identificador externo, com provedor e ambiente;
- o histórico de cada consulta, só de inserção;
- os quatro instantes separados: criação no provedor, aprovação no provedor, recebimento do primeiro aviso e consulta;
- a mudança de situação aplicada uma única vez, mesmo com consultas repetidas ou concorrentes, e avisada às etapas seguintes por um sinal.

Esta fatia também garante que não existe outra forma de registrar um pagamento (cenário 37).

O que o pagamento significa para o pedido (quitação, prazo, P-6, devolução) é da E08 em diante. Aqui não há pedido.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.3 | "Nunca ignorar dinheiro recebido nem autorizar pedido duplicado por repetição de evento." "Cada pagamento do provedor é reconhecido uma única vez." |
| Especificação §14 | Pagamento e eventos: tentativas, identificadores externos, horário de aprovação no provedor, horário de recebimento da notificação e conciliação. |
| Especificação §15 | Separar o tempo do evento financeiro, o do recebimento do webhook e o prazo comercial. Histórico financeiro imutável ou auditável. |
| Cenários §16 | 17 (parte do pagamento) e 37. |
| Infraestrutura 4.1 | Não existe tela nem rota para registrar como recebido um pagamento fora do provedor. Cada pagamento registra o provedor e o ambiente. |
| Infraestrutura 4.2 | O provedor é a fonte da verdade. Instantes registrados separadamente. Reconhecimento único (`UNIQUE` no identificador externo). Concorrência sob trava de linha, reconsultando o estado dentro da transação. |
| Infraestrutura 5 | `UNIQUE` em identificadores externos de pagamento. Histórico financeiro só aceita inserção. |
| E01-04, E01-05 | `RegistroSoInsercao`, a trigger de só inserção e `registrar_auditoria`. |
| E07-01, E07-02 | `PagamentoConsultado`, `obter_provedor()`, `AMBIENTE`. |

## Escopo

**Dentro:**

- Os modelos `PagamentoNoProvedor` e `ConsultaDoPagamento`.
- O serviço `sincronizar_pagamento`.
- O sinal `situacao_do_pagamento_mudou`.
- A prova do cenário 37.

**Fora:**

- Quem chama a sincronização: a tarefa das chamadas pendentes (E07-04), os avisos (E07-05) e a consulta antes das decisões (E07-06).
- Pedido, quitação, P-6, duplicidade de pagamento aceito e devolução (E08, E10 e E11).
- Alertas de divergência (E15). Aqui as divergências ficam registradas e no log.

## Decisões técnicas

- **Espelho do provedor.** `PagamentoNoProvedor` guarda o que o provedor respondeu por último e foi aplicado. Ele não guarda dados do pagador.
- **Os dados de identidade não mudam.** `referencia_externa`, `valor` e `criado_no_provedor_em` são gravados na primeira consulta e nunca mudam. Uma resposta posterior com valores diferentes fica no histórico como divergência, e o registro mantém os originais. Um pagamento antigo nunca passa a apontar para outra referência (infraestrutura 4.2).
- **`aprovado_no_provedor_em` não muda depois de gravado.** É o horário que decide P-6 (E08). Uma consulta posterior com outro horário fica registrada como divergência, e o primeiro horário é mantido.
- **Regra de situação:**
  - de `pendente` para qualquer situação terminal: aplica;
  - de uma situação terminal para outra: aplica, porque o provedor é a fonte da verdade (por exemplo, `cancelado` → `aprovado` no cancelamento que coincide com o pagamento, L-2);
  - de uma situação terminal para `pendente`: não aplica. É uma leitura atrasada (L-6). Fica no histórico com `aplicada` falso.
- **Histórico de toda consulta.** Cada resposta vira uma linha de `ConsultaDoPagamento`, mesmo sem mudança. A conciliação e a revisão de incidentes usam esse histórico.
- **Sinal dentro da transação.** `situacao_do_pagamento_mudou` é enviado na mesma transação da mudança, depois de gravá-la, uma vez por mudança aplicada. A E08 conecta a ele a quitação. Uma exceção num receptor desfaz a sincronização inteira, e a consulta é repetida depois.
- **Trava de linha.** A sincronização insere o registro se ele não existir (`INSERT ... ON CONFLICT DO NOTHING`) e depois o trava com `select_for_update`. Só então compara e aplica. Duas sincronizações do mesmo pagamento ficam em fila, e a segunda vê o que a primeira gravou.

## Regras

**Modelo `PagamentoNoProvedor`** (`apps/pagamentos/models.py`):

| Campo | Regra |
|---|---|
| `provedor` | nome da implementação, como `simulador` |
| `ambiente` | `settings.AMBIENTE` no momento da primeira gravação |
| `id_externo` | texto; `UNIQUE (provedor, id_externo)` |
| `referencia_externa` | texto, com índice |
| `valor` | `Decimal`, duas casas, maior que zero (`CHECK`) |
| `situacao` | `SituacaoNoProvedor` (E07-01), com `CHECK` dos valores |
| `criado_no_provedor_em`, `expira_em` | instantes do provedor |
| `aprovado_no_provedor_em` | instante do provedor ou nulo; preenchido no máximo uma vez |
| `primeiro_aviso_em` | instante do recebimento do primeiro aviso que levou à consulta, ou nulo |
| `primeira_consulta_em`, `ultima_consulta_em` | instantes do sistema |

**Modelo `ConsultaDoPagamento`** (`RegistroSoInsercao`, com a trigger de só inserção):

- `pagamento`;
- `origem`: `aviso`, `tarefa`, `decisao` ou `busca`;
- a resposta: `situacao`, `aprovado_em`, `referencia_externa` e `valor` como vieram;
- `consultado_em`;
- `aplicada`: verdadeiro quando a resposta mudou a situação ou preencheu `aprovado_no_provedor_em`, inclusive na criação do registro. Atualizar só `ultima_consulta_em` ou `primeiro_aviso_em` não conta;
- `divergencia`: vazio, `referencia`, `valor`, `criacao` ou `aprovacao` (a primeira encontrada, na ordem dos campos).

**Serviço** (`apps/pagamentos/sincronizacao.py`):

```
sincronizar_pagamento(consultado: PagamentoConsultado, *, origem: str, aviso_recebido_em: datetime | None = None) -> Sincronizacao
```

1. Exige transação aberta (`TransactionManagementError`) e `origem` válida (`ValueError`).
2. Insere o registro com os dados de `consultado`, se não existir, e trava a linha.
3. Compara a resposta com o registro e calcula `divergencia`.
4. Aplica a regra de situação. Grava `aprovado_no_provedor_em` se estava nulo e a resposta trouxe um horário.
5. Preenche `primeiro_aviso_em` com `aviso_recebido_em`, se estava nulo. Atualiza `primeira_consulta_em` (na criação) e `ultima_consulta_em`.
6. Insere a linha de `ConsultaDoPagamento`.
7. Se a situação mudou (ou o registro foi criado já numa situação terminal):
   - audita `pagamento.situacao`, com autor `SISTEMA`, objeto igual ao registro e alterações `id_externo`, `anterior` (nulo na criação), `atual`, `aprovado_em` (ISO 8601 em UTC ou nulo) e `origem`;
   - envia `situacao_do_pagamento_mudou(pagamento, anterior, atual)`.
8. Com divergência, registra no log `"Pagamento <id_externo>: divergência em <campo>"`, sem os valores.
9. Devolve `Sincronizacao(pagamento, anterior, atual, mudou, divergencia)`.

**Sinal** (`apps/pagamentos/sinais.py`): `situacao_do_pagamento_mudou`, com `pagamento`, `anterior` (`SituacaoNoProvedor` ou `None`) e `atual`.

**Cenário 37, sem registro por fora:**

- Nenhuma rota, formulário, comando de `manage.py` nem tela do Django Admin grava `PagamentoNoProvedor` ou `ConsultaDoPagamento`. O Django Admin não está instalado, e continua assim.
- Só `apps/pagamentos/sincronizacao.py` cria ou altera esses registros. Um teste varre o código de `apps/` e confere isso.
- A única rota de `apps.pagamentos` é a de avisos (E07-05), que só agenda uma consulta.

## Interfaces

- `apps/pagamentos/models.py`, com a migração e a trigger.
- `apps/pagamentos/sincronizacao.py`: `sincronizar_pagamento`, `Sincronizacao` e `ORIGENS_DA_CONSULTA`.
- `apps/pagamentos/sinais.py`: `situacao_do_pagamento_mudou`.

## Invariantes

- Há no máximo um `PagamentoNoProvedor` por (provedor, id_externo).
- Cada mudança de situação gera exatamente uma auditoria e um sinal.
- `aprovado_no_provedor_em`, `referencia_externa`, `valor` e `criado_no_provedor_em` nunca mudam depois de gravados.
- Uma situação terminal nunca volta a `pendente`.
- O histórico de consultas só cresce.
- Nenhum registro guarda nome, e-mail, documento ou dados para pagar.

## Casos-limite e concorrência

- **Primeira consulta já aprovada** (o aviso de criação se perdeu): o registro nasce `aprovado`, com uma auditoria (`anterior` nulo) e um sinal.
- **Duas consultas iguais seguidas:** a segunda só acrescenta o histórico, sem auditoria nem sinal.
- **Consulta atrasada depois da aprovação** (L-6): `pendente` não é aplicado e fica no histórico com `aplicada` falso.
- **Cinco sincronizações concorrentes do mesmo pagamento aprovado:** um registro, uma mudança, uma auditoria, um sinal e cinco linhas de histórico.
- **Receptor do sinal falhando:** a exceção chega a quem chamou, e nada da sincronização fica gravado.

## Dependências e decisões em aberto

- Depende de E01-04, E01-05, E07-01 e E07-02.
- Sem decisões em aberto.
