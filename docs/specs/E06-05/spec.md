# E06-05 — Encerramento do fechamento e remoção de excedentes

Fatia 5 de 7 da milestone **E06 — Fechamento e caixas**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

No fim do prazo, o sistema encerra o fechamento sozinho:

- grava `fechamento_encerrado`;
- remove as unidades que não completam caixa, começando pelas adicionadas por último;
- avisa cada comprador afetado.

A verificação do mínimo e o retorno para interesse entram na E06-06, na mesma transação do encerramento.

Esta fatia entrega:

- o serviço `encerrar_fechamento(rodada)`;
- a tarefa periódica que encontra os fechamentos vencidos;
- o aviso `excedentes_removidos`.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §6.3 | "Ao terminar as 24 horas de fechamento, remover unidades que não completam caixas, respeitando prioridade por adição. É permitido reduzir parcialmente o pedido de um comprador. Informar a redução ao afetado e recalcular o mínimo. Não abrir espera adicional para completar caixas." |
| Especificação §7 | Fechamento com prazo encerrado: "Bloqueia alterações automaticamente, remove excedentes de caixas e verifica mínimo." "O encerramento automático dos prazos não autoriza automaticamente uma nova etapa." |
| Especificação §5 | Ao reduzir, saem primeiro as parcelas mais recentes. |
| Especificação §12 | "Remoção de excedentes de caixa: produto, quantidade removida e quantidade mantida." |
| Especificação §15 | Prazos calculados no servidor. Processamento retomável depois de interrupção, sem aplicar uma transição duas vezes. |
| Cenários §16 | 5 (término 24 horas depois) e 7 (as 6 excedentes de B são removidas). |
| Infraestrutura 2 e 5 | Procrastinate para tarefas periódicas e retomáveis. `select_for_update` em estoque, fila e caixas. Prazos checados nas tarefas e nas ações. |
| Infraestrutura 4.10 | Caixas e remoção de excedentes usam a mesma aritmética decimal. Nenhuma parcela fica fora do incremento. |
| Infraestrutura 8 | T-47 (as caixas ignoram pendentes). |
| E04-01, E04-02 | `excedentes_removidos`: comprador, site e e-mail; emissão na transação do fato. |
| E04-03 | Tarefa periódica no Procrastinate, com `queueing_lock`, no padrão de `apps/notificacoes/tarefas.py`. |
| E05-04 | Divisão pelas caixas por ordem de `sequencia`. A E06 usa essa mesma divisão para remover os excedentes. |
| E06-01, E06-03 | `prazo_do_fechamento` e o bloqueio das ações a partir do prazo. |

## Escopo

**Dentro:**

- O serviço `encerrar_fechamento` e o seu resultado.
- A rotina `encerrar_fechamentos_vencidos` e a tarefa periódica.
- O aviso `excedentes_removidos`.

**Fora:**

- A verificação do mínimo e o retorno para interesse (E06-06).
- O congelamento da composição das caixas e o registro de que parcela fica em que caixa, que acontecem na abertura do pagamento (§6.3, E08).
- O alerta de tarefa atrasada (E15).
- As telas (E06-07).

## Decisões técnicas

- **Mesma divisão da E05-04.** Cada parcela `ativa` com reserva fica com exatamente a sua parte "em caixas", calculada pela distribuição da E05-04 (ordem crescente de `sequencia`). O resto da reserva é removido. Assim:
  - as últimas adições perdem primeiro (§6.3, §5);
  - uma parcela pode ser reduzida em parte;
  - o resultado é igual ao `excedente` que o comprador já via no carrinho.
- **Múltiplo congelado.** O múltiplo usado é o do produto, que está congelado desde o início do fechamento (E03-07) e é igual ao do `CondicaoDoProdutoNoCiclo`. Produto sem múltiplo não tem excedente.
- **Removido é removido.** As unidades excedentes deixam a reserva e não viram pendência. A §6.3 manda remover, e a fila de pendentes da §5.2 é só para caixa invalidada por inadimplência. A pendência que a parcela já tinha antes não muda.
- **Sem fila no encerramento.** A rodada em `fechamento_encerrado` não aceita reservas (E05-02 e E06-03). O estoque liberado só volta a ser oferecido à fila se a rodada voltar para interesse (E06-06).
- **Uma transação por rodada, retomável.** Tudo acontece numa única transação, em que a etapa e o prazo são relidos sob trava:
  - a mudança de etapa;
  - a remoção dos excedentes;
  - a auditoria;
  - os avisos;
  - a verificação da E06-06.

  Uma falha desfaz tudo, e a próxima execução da tarefa refaz o encerramento. Uma segunda execução sobre a rodada já encerrada não faz nada.
- **A tarefa só procura; o serviço decide.** A tarefa lista as candidatas sem trava. Para cada uma, chama o serviço, que trava e confere de novo a etapa e o prazo, inclusive uma prorrogação confirmada no meio tempo (E06-04).

## Regras

**Serviço** (`apps/rodadas/fechamento.py`):

```
encerrar_fechamento(rodada) -> ResultadoDoEncerramento | None
```

Numa única `transaction.atomic()`:

1. **Travas e conferência.** Trava o fornecedor e a rodada, nessa ordem. Relê a rodada. Devolve `None`, sem gravar nada, quando:
   - a rodada não está em `fechamento`;
   - `prazo_encerrado(agora(), prazo_do_fechamento(rodada))` é falso.
2. **Etapa:** grava `etapa = fechamento_encerrado` (`update_fields`).
3. **Excedentes:** para cada estoque da rodada, em ordem de `produto_id`:
   1. executa `travar_estoque(rodada, produto)` e `travar_parcelas(produto)` (E05-01);
   2. sem múltiplo, passa ao próximo produto;
   3. com múltiplo `m`, calcula `quantidade_elegivel` e, para cada parcela `ativa` com reserva, a parte em caixas, pelas regras da E05-04;
   4. em cada parcela com parte em caixas menor que a reserva, grava `quantidade_reservada = parte em caixas`. A situação segue as regras da redução da E05-01:
      - reserva zero com pendência maior que zero: `pendente`;
      - as duas zero: `removida`;
      - nos outros casos, continua `ativa`;
   5. `quantidade_original` e `sequencia` nunca mudam.
4. **Auditoria:** uma entrada `rodada.encerrar_fechamento`, com autor `SISTEMA`, objeto igual à rodada e com `rodada`, `ciclo`, `prazo` (ISO 8601 UTC) e `removidas`. `removidas` é uma lista de `[parcela, produto, quantidade removida]` em texto decimal, vazia quando nada sai.
5. **Avisos:** um aviso `excedentes_removidos` por par (comprador, produto) com quantidade removida maior que zero, conforme o texto abaixo.
6. **Mínimo:** a verificação do mínimo da E06-06.
7. Devolve `ResultadoDoEncerramento`.

**`ResultadoDoEncerramento`** é um `dataclass` imutável com:

- `rodada`;
- `ciclo`;
- `removidas`: a soma removida por produto, como `dict[int, Decimal]`;
- `etapa_final`.

**Aviso** (`apps/rodadas/avisos.py`), com `emitir_evento` por par (comprador, produto):

- `titulo`: `"Excedentes removidos: " + produto.nome`, cortado em 150 caracteres.
- `corpo`, em uma linha:

  ```
  No fim do fechamento da rodada de <fornecedor>, <removida> <unidade> de <produto> não completaram caixa e foram removidas do seu interesse. Continuam no seu interesse: <mantida> <unidade>.
  ```

  - `<removida>` é a soma removida do comprador naquele produto.
  - `<mantida>` é o reservado dele no produto depois da remoção.
  - As quantidades usam `formatar_quantidade`, e a unidade é o rótulo de `Unidade`.
- `link`: `"/carrinho/"`.
- `chave`: `f"excedentes_removidos:{ciclo.pk}:{produto.pk}:{conta.pk}"`.

**Rotina e tarefa** (`apps/rodadas/fechamento.py` e `apps/rodadas/tarefas.py`):

```
encerrar_fechamentos_vencidos() -> int
```

1. Lista, sem trava, as rodadas em `fechamento` cujo prazo vigente é menor ou igual a `agora()`, em ordem de `fornecedor_id`.
2. Para cada uma, chama `encerrar_fechamento`. Uma exceção numa rodada é registrada em log com o id da rodada e o tipo da exceção, sem dado pessoal. As demais rodadas seguem.
3. Devolve quantas rodadas foram encerradas.

A tarefa `encerrar_fechamentos_vencidos` roda a cada minuto (`@app.periodic(cron="* * * * *")`), com `queueing_lock` igual ao próprio nome, no padrão da E04-03, e chama a rotina.

## Interfaces

- `apps/rodadas/fechamento.py`: `encerrar_fechamento`, `ResultadoDoEncerramento` e `encerrar_fechamentos_vencidos`.
- `apps/rodadas/tarefas.py`: a tarefa periódica.
- `apps/rodadas/avisos.py`: `avisar_excedentes_removidos`.

## Invariantes

- Depois do encerramento, o total reservado de cada produto com múltiplo é múltiplo de `m`.
- Nenhuma parcela fica com reserva fora do incremento.
- Nenhuma parcela adicionada antes perde unidades enquanto uma adicionada depois mantém excedente.
- Nenhum `quantidade_original` ou `sequencia` muda, e nenhuma pendência existente diminui.
- Cada rodada é encerrada uma única vez por ciclo.

## Casos-limite e concorrência

- **Cenário 7:** múltiplo 12, A com 8 e B com 10, nessa ordem. B fica com 4, e A, com 8. B recebe o aviso "6 [...] removidas [...] Continuam no seu interesse: 4", e A não recebe aviso.
- **Total abaixo de uma caixa:** 7 com múltiplo 12. Todas as parcelas do produto perdem toda a reserva.
- **Total exato:** 24 com múltiplo 12. Nada é removido e nenhum aviso é emitido.
- **Múltiplo fracionário:** múltiplo 1 kg, incremento 0,25 e total 2,75 kg. Saem 0,75 kg, da última parcela para a primeira.
- **Parcela com pendência:** A tem uma parcela `ativa` com 5 reservados, 3 pendentes e excedente total. A parcela fica `pendente`, com 0 reservado e 3 pendentes.
- **Comprador com várias parcelas no produto:** recebe um aviso com a soma removida.
- **Rodada sem produtos com múltiplo:** encerrada sem remoções e sem avisos.
- **Tarefa atrasada:** o encerramento usa o mesmo prazo, qualquer que seja o atraso. As ações já estavam bloqueadas desde o prazo (E06-03).
- **Duas execuções da tarefa em paralelo:** a segunda espera a trava do fornecedor, encontra `fechamento_encerrado` e devolve `None`.
- **Prorrogação confirmada antes da tarefa obter a trava:** o serviço relê o prazo novo e devolve `None`.
- **Encerramento em paralelo com alteração de preço ou com suspensão:** as notificações pedem só `FOR KEY SHARE` nas contas (E05-R03), e as transações terminam sem deadlock.

## Dependências e decisões em aberto

- Depende de E04-01 a E04-03, E05-01, E05-04, E06-01 e E06-03.
- Sem decisões em aberto.
