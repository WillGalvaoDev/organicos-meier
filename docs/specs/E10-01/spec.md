# E10-01 — Conciliação: pendências de dias anteriores não repetem a diferença de saldo

Fatia 1 de 7 da milestone **E10 — Devoluções**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7 (incorpora Q-8, 2026-10-29)
- Infraestrutura: v1.8
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável de 2026-10-15, não há revisão separada da especificação. O especificador verificou clareza, testabilidade e ausência de decisões novas. A especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Divisão da E10

| Fatia | Entrega | Depende de |
|---|---|---|
| E10-01 | Conciliação: pendências de dias anteriores não repetem a diferença de saldo | E09-07 |
| E10-02 | Cálculo do reembolso (Q-7): parcial por item, serviço e frete proporcionais, devolução integral do pedido | E08, E09-06 |
| E10-03 | Provedor e simulador: estorno, consulta de estornos e contestação | E07, E09-02 |
| E10-04 | Devolução pela plataforma: parcela, autorização, estados, nova tentativa e liquidação | E10-02, E10-03, E09-06 |
| E10-05 | Conciliação dos estornos e conclusão tardia | E10-03, E10-04, E09-07 |
| E10-06 | Devolução excepcional confirmada pelo administrador | E10-04 |
| E10-07 | Avisos de estorno, telas do administrador e do comprador | E10-04 a E10-06, E04 |

**Fronteira com as etapas seguintes.** A E10 entrega:
- o cálculo dos reembolsos e a obrigação que cada um gera (E10-02);
- a execução de qualquer obrigação com comprador, pela plataforma ou de forma excepcional (E10-04 a E10-06).

Quem decide **quando** um reembolso nasce são as etapas donas do fato:
- as caixas invalidadas e o mínimo não atingido, na E11;
- o cancelamento com reembolso, na E12;
- as ocorrências de entrega, na E14.

As obrigações já criadas pela E09-04, com destino `devolucao` ou `sem_pedido`, são executadas por esta etapa. Os cenários 90, 91 e 112 a 117 são provados aqui no nível do serviço de cálculo, chamado diretamente. Cada etapa seguinte repete o cenário pelo seu fluxo real, como na E09.

**Decisões do responsável usadas nesta etapa:**
- 2026-10-22: o simulador reproduz a contestação (E10-03).
- 2026-10-29, Q-8: quem arca com a contestação e com o MED. Já está nos documentos-base v1.7 e v1.8. Os lançamentos automáticos ficam para as fases 2a e 2b.
- 2026-10-29, opção 2A: esta fatia. A ação do administrador para explicar um ajuste do provedor fica para a E15. Lá se escolhe entre lançá-lo no livro-razão e marcá-lo como explicado.

## Contexto e objetivo

A E09-07 calcula a diferença de saldo de um dia `D` descontando só os movimentos sem par **do próprio dia**.

Exemplo:
- Um ajuste de +10,00 do provedor, sem par no livro, acontece no dia 10.
- Na conciliação do dia 10 ele é descontado, e a diferença dá zero, com o alerta de divergência do ajuste aberto.
- Do dia 11 em diante, o saldo do provedor ainda tem os 10,00, mas o ajuste não é do dia. A diferença dá +10,00, e um alerta `saldo:<D>` novo abre a cada dia, sempre pela mesma causa.

O mesmo acontece no sentido inverso: um aporte registrado sem depósito no provedor (`livro:<id>`) e um pagamento recebido sem a entrada no livro (`pagamento_sem_conciliacao`).

Esta fatia faz a conciliação descontar também as **pendências de dias anteriores que continuam sem par no instante do saldo**. Assim, só uma diferença nova abre alerta novo. Ela também resolve as pendências antigas cujo par apareceu.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.5 | Conciliação diária com o saldo e os movimentos do provedor. Divergência gera alerta. |
| Infraestrutura 3.6 | Alerta de divergência na conciliação diária. |
| E09-07 | Fórmula da diferença, recortes do dia, do par inverso e do instante `t`; alertas `divergencia_na_conciliacao` com as chaves `<id_movimento>`, `livro:<id>` e `saldo:<D>`; `pagamento_sem_conciliacao`. |
| Decisão do responsável, 2026-10-29 (2A) | Corrigir no início da E10 a repetição do alerta de diferença causada por pendência antiga. |

## Escopo

**Dentro:**
- O termo das pendências anteriores na fórmula da diferença.
- A resolução automática das pendências anteriores cujo par já existe.

**Fora:**
- A ação do administrador para explicar um `ajuste` ou um `outro` (E15).
- A classificação dos movimentos do dia e o par inverso (E09-07, sem mudança).
- O par dos estornos (E10-05).

## Regras

`t` é o `referente_a` do saldo, e `D` é o dia conciliado, como na E09-07.

**Pendência anterior.** É um alerta aberto no momento da execução, de um dos três tipos abaixo, cujo `dados.data` é anterior a `D`:

| Pendência | Alerta | Sinal na diferença | Continua pendente em `t` quando |
|---|---|---|---|
| Movimento do provedor sem par ou divergente | `divergencia_na_conciliacao`, com a chave de um `id_movimento` (não começa por `livro:` nem por `saldo:`) | o valor é descontado, como os movimentos do provedor sem par | o movimento, montado dos dados do alerta (`id_movimento`, `tipo`, `valor` e `id_externo`), não tem par no livro até `t` pela regra "Sem par no livro até `t`" da E09-07. `ajuste`, `outro` e tipo desconhecido nunca têm par |
| Pagamento sem entrada | `pagamento_sem_conciliacao` | o valor é descontado | a entrada do pagamento `id_externo`, com o valor do alerta, não existe com `momento ≤ t` |
| Aporte ou saída do livro sem movimento do provedor | `divergencia_na_conciliacao`, com a chave `livro:<identificacao>` | o valor, com o sinal guardado no alerta, é somado de volta, como os do livro sem par | nenhum movimento da lista do provedor tem a mesma identificação com `ocorrido_em ≤ t` |

**Fórmula (soma-se à da E09-07):**

```
diferenca = (fórmula da E09-07)
          − Σ(pendências anteriores do provedor que continuam pendentes em t)
          + Σ(pendências anteriores do livro que continuam pendentes em t)
```

Não entram na soma:
- o mesmo movimento, se ele também estiver na lista do provedor no recorte da diferença de `D`, porque já entrou pela fórmula da E09-07. A comparação é por `id_movimento`;
- um alerta `saldo:<data>`, que não é pendência de movimento.

**Resolução das pendências cujo par apareceu.** Na mesma transação da conciliação de `D`, depois da classificação:
- um `livro:<identificacao>` anterior a `D` é resolvido, com o motivo "par encontrado na conciliação de `<D>`", se a lista do provedor tem um movimento com essa identificação e `ocorrido_em < fim de D`;
- um `divergencia_na_conciliacao` de movimento do provedor, ou um `pagamento_sem_conciliacao`, anterior a `D` é resolvido se o movimento, montado dos dados do alerta, tem par no livro na execução (classificação sem `ate`). `ajuste`, `outro` e tipo desconhecido continuam abertos.

**O que não muda:**
- `movimentos` e `sem_par` do resumo continuam contando só o dia `D`.
- O resultado é `ok` só com `sem_par = 0` e diferença zero. Uma pendência anterior aberta não torna `D` divergente, porque continua visível no próprio alerta.
- O registro do dia continua imutável e único.

## Interfaces

- `conciliar_dia(data)` e `conciliar_dias_pendentes_agora()`, com as mesmas assinaturas.
- Os dados dos alertas não mudam: a E09-07 já grava `data`, `valor`, `tipo`, `id_movimento` e `id_externo` (divergência), `id_externo` e `valor` (pagamento sem conciliação) e `identificacao` e `valor` com sinal (`livro:`).

## Invariantes

- A mesma causa abre no máximo um alerta de diferença de saldo: o do dia em que apareceu, e só se o próprio dia não a explicar.
- Uma pendência entra na diferença no máximo uma vez por conciliação.
- A conciliação nunca resolve um `ajuste`, um `outro` ou um tipo desconhecido.

## Casos-limite

- **O par chega depois de `t` mas antes da execução** (por exemplo, `registrar_aporte` do depósito antigo): a pendência ainda conta para a diferença em `t`. O alerta do movimento é resolvido por quem registrou o par, como já acontece.
- **Duas pendências antigas com a mesma causa** não existem: o alerta é único por (tipo, chave) aberto (E09-03).
- **Um alerta com `dados.data` ausente ou ilegível** não entra na soma e é registrado no log `warning`, sem dados pessoais. A conciliação não falha por ele.
- **Pendência mais antiga que a janela da lista** (3 dias): a pendência do provedor é montada dos dados do alerta e não depende da lista. A do livro só é resolvida quando o movimento aparecer numa lista futura.

## Dependências e decisões em aberto

Depende de E09-07. A ação do administrador sobre o `ajuste` fica na E15, que escolhe entre lançá-lo no livro-razão e marcá-lo como explicado. Nenhuma outra decisão em aberto.
