# E05-02 — Atendimento da fila de pendentes

Fatia 2 de 7 da milestone **E05 — Interesses, reservas e progresso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Quantidades pendentes são unidades de um comprador que esperam estoque, na fila do fornecedor, sem reserva.

- Elas nascem na apuração final, quando uma caixa é invalidada por inadimplência (E11).
- A regra de atendimento, porém, vale sempre que há estoque: os pendentes são atendidos primeiro, na ordem FIFO original, e só depois vêm as reservas novas (R-5).

Esta fatia entrega a rotina única que atende a fila e os pontos em que ela roda. Os testes criam parcelas pendentes pela `ParcelaFactory`, já que o fluxo que as produz é da E11.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §5 | Parcelas restauradas mantêm a posição original. A restauração não cria parcela, reserva nem posição nova. |
| Especificação §5.2 | Na próxima rodada em interesse, o sistema tenta reservar as pendentes pela prioridade original e pelo estoque disponível. O que não couber continua pendente, sem reserva fictícia. Pendentes são atendidas primeiro sempre que há estoque para alocação, na abertura da fase de interesse e sempre que estoque é liberado ou aumentado. A fila de um fornecedor só é atendida pelas rodadas dele. Sem duplicação, inclusive em execuções concorrentes. Unidades reservadas a partir da fila passam a ser interesses comuns da rodada, com a posição original. |
| Cenários §16 | 75, 76, 78 (atendimento repetido ou em paralelo), 101, 102. |
| Infraestrutura 4.10 | `alocar_pendentes(fornecedor)`, numa transação, com trava de linha do estoque de cada produto: percorre as pendentes por sequência, reserva o mínimo entre pendente e livre, em múltiplos do incremento, e atualiza reservado e pendente. Roda na abertura da fase de interesse, antes de qualquer reserva nova e sempre que estoque é liberado ou aumentado. Só lê pendentes do próprio fornecedor e só reserva na rodada ativa dele. |
| Infraestrutura 8 | T-30, T-31, T-46. |
| E03-02, E03-05 | Sinais `rodada_aberta` e `estoque_alterado`, enviados dentro da transação. |
| E05-01 | Serviços de interesse, `travar_rodada_para_interesses` e a ordem de travas. |

## Escopo

**Dentro:**

- `alocar_pendentes(fornecedor)` e a versão interna por produto.
- As chamadas dessa rotina:
  - antes de cada acréscimo (`adicionar_interesse` e o acréscimo de `definir_interesse`);
  - depois de cada redução;
  - nos receptores de `rodada_aberta` e `estoque_alterado`.

**Fora:**

- A criação de pendentes: restauração de caixa invalidada e perda dos inadimplentes (E11).
- A remoção de pendentes pelo comprador (E05-03).
- A liberação por suspensão (E05-07), que reaproveita esta rotina.

## Decisões técnicas

- **Rotina por produto, chamada pelo fornecedor.**
  - `alocar_pendentes(fornecedor)` percorre os produtos do estoque da rodada ativa, em ordem de id, e chama `_alocar_produto(rodada, produto)`.
  - As chamadas internas (acréscimo, redução e estoque alterado) usam direto a versão por produto. A FIFO só importa entre parcelas do mesmo produto.
- **Etapas em que a fila é atendida:** as mesmas em que a rodada aceita reservas, ou seja, `interesse` e `fechamento` (`travar_rodada_para_interesses`, E05-01).
  - O fechamento aceita alterações e novos compradores (§7). Atender pendentes ali impede que uma reserva nova passe à frente delas, como exige R-5.
  - Em qualquer outra etapa, ou sem rodada ativa, a rotina não faz nada e não levanta exceção. As pendentes continuam pendentes.
- **Parcelas consideradas:** as do produto com `quantidade_pendente > 0` e situação `ativa` ou `pendente`.
  - Parcelas `em_pedido` ficam de fora: a composição delas está congelada (§7.1). O tratamento da pendência de uma parcela que entra em pedido é da E08.
  - Parcelas `removida` não têm pendência.
- **Estoque sem limite:** atende todas as pendentes do produto.
- **Arredondamento ao incremento:** o livre pode não ser múltiplo do incremento (por exemplo, limite 10 com incremento 4). Cada parcela recebe `min(pendente, piso(livre ÷ incremento) × incremento)`. As pendentes são sempre múltiplas do incremento vigente (E03-06).
- **Auditoria:** cada produto em que algo foi alocado grava uma entrada `interesse.alocar_pendentes`, com autor `SISTEMA`, produto, rodada e `{"parcelas": [[id, quantidade], ...]}`. Sem nada alocado, não há auditoria.

## Regras

**`alocar_pendentes(fornecedor) -> Decimal`** (`apps/interesses/fila.py`):

1. Exige transação aberta (`TransactionManagementError` fora dela).
2. Chama `travar_rodada_para_interesses(fornecedor)`. Se levantar `InteressesBloqueados`, devolve `Decimal("0.000")` sem gravar nada. A recusa não se propaga, porque não é erro de quem chamou.
3. Para cada `EstoqueDaRodada` da rodada, em ordem de `produto_id`, chama `_alocar_produto(rodada, produto)`.
4. Devolve a soma alocada.

**`_alocar_produto(rodada, produto) -> Decimal`:**

A função não confere a etapa e não trava fornecedor nem rodada. Quem chama já travou os dois e sabe que a rodada aceita reservas, seja por `travar_rodada_para_interesses` ou, na suspensão (E05-07), conferindo a etapa da rodada travada. O produto precisa ter estoque nessa rodada.

1. `travar_estoque(rodada, produto)`.
2. Trava as parcelas do produto com `travar_parcelas(produto)` (E05-01) e calcula o reservado a partir da lista travada.
3. Calcula `livre = calcular_livre(limite, reservado)`.
4. Percorre as parcelas consideradas em ordem crescente de `sequencia`. Para cada uma:
   - calcula `q = pendente`, se o livre for `None`; ou `min(pendente, piso(livre ÷ incremento) × incremento)`, nos outros casos;
   - se `q > 0`, soma `q` em `quantidade_reservada`, subtrai `q` de `quantidade_pendente`, passa a situação para `ativa` e, havendo limite, reduz o livre em `q`;
   - para quando o livre chega a zero.
5. Grava só as parcelas alteradas, com `save(update_fields=[...])` ou `bulk_update`.
6. `quantidade_original` e `sequencia` não mudam.
7. Nenhuma parcela é criada.

**Chamadas obrigatórias:**

- **Antes de reservar:** em `adicionar_interesse` e no acréscimo de `definir_interesse`, `_alocar_produto` roda depois das travas do passo 5 da E05-01 e antes de calcular o livre para o acréscimo. A reserva nova só recebe o que sobrar.
  - O livre informado em `EstoqueInsuficiente` já desconta as pendentes atendidas.
  - Se o acréscimo for recusado, a transação inteira é desfeita, inclusive essa alocação, e vale a regra da E05-01 de que uma recusa não grava nada.
  - Isso não deixa pendentes esperando estoque livre: as chamadas depois de liberar e no aumento de estoque já as atenderam. Na prática, a alocação antes de reservar só tem efeito num estado que nenhum serviço produz, como o criado por fábrica nos testes.
- **Depois de liberar:** em `reduzir_interesse` e na redução de `definir_interesse`, `_alocar_produto` roda depois da redução, na mesma transação.
- **`rodada_aberta`:** um receptor em `apps.interesses` chama `alocar_pendentes(rodada.fornecedor)`. Na abertura, a rodada ainda não tem estoques, então o efeito real vem da inclusão de produtos. O receptor existe para que a rotina rode em qualquer abertura futura que já traga estoques.
- **`estoque_alterado`:** um receptor chama `_alocar_produto(rodada, estoque.produto)` quando o estoque aumentou, conforme a classificação da correção E05-R01. A inclusão de produto na rodada conta como aumento, porque o `anterior` é `Decimal("0")`.
- Os receptores são conectados no `ready()` de `apps.interesses`. Eles rodam dentro da transação do remetente: uma falha desfaz a abertura ou a alteração de estoque.

**Isolamento por fornecedor:** a rotina só lê parcelas de produtos do fornecedor da rodada travada e só reserva no estoque dessa rodada (cenário 102, R-5).

## Interfaces

- `apps/interesses/fila.py`: `alocar_pendentes` e `_alocar_produto`.
- `apps/interesses/apps.py`: conexão dos receptores.
- `apps/interesses/servicos.py`: as chamadas antes de reservar e depois de liberar.

## Invariantes

- Total reservado ≤ limite do estoque, em todo momento.
- Reservado + pendente ≤ original, em cada parcela (`CHECK` da E03-04).
- Nenhuma pendente é atendida enquanto existe pendente mais antiga do mesmo produto que caberia no livre.
- Uma reserva nova nunca é feita enquanto existe pendente do mesmo produto que caberia no livre.
- A rotina é idempotente: uma segunda execução sem estoque novo não altera nada.

## Casos-limite e concorrência

- **Cenário 75:** limite 10, A com 6 pendentes (sequência mais antiga) e C com 8. A recebe 6 reservadas e fica `ativa` com pendente 0. C recebe 4 reservadas, fica `ativa` e continua com 4 pendentes. Total reservado: 10.
- **Cenário 76:** na mesma rodada, D tenta adicionar 3 sem livre e é recusado (`EstoqueInsuficiente`). Ao aumentar o limite para 13, C recebe 3 e fica com 1 pendente. Uma adição de D depois disso também é recusada.
- **Cenário 101:** D tem 3 reservados e reduz 3, e C tem 4 pendentes. C recebe 3 na mesma transação da redução. E, que adiciona ao mesmo tempo, só recebe o que sobrar.
- **Cenário 102:** pendentes do fornecedor X nunca são alocadas na rodada do fornecedor Y, mesmo com estoque livre em Y.
- **Execução repetida** (cenário 78): `alocar_pendentes` duas vezes, sem estoque novo. A segunda devolve 0 e não grava nada, nem auditoria.
- **Execuções em paralelo** (T-31, T-46): `alocar_pendentes` e `adicionar_interesse` no mesmo produto, em qualquer ordem. As duas se serializam pela trava do fornecedor, e o resultado final é idêntico: pendentes primeiro e total reservado ≤ limite.
- **Produto fora da rodada:** as pendentes de um produto do fornecedor que não está no estoque da rodada continuam pendentes.
- **Rodada em `fechamento_encerrado` ou `pagamento`:** nada é alocado.
- **Livre não múltiplo do incremento:** limite 10, incremento 4 e uma pendente de 12 recebem 8 e ficam com 4 pendentes.

## Correção E05-R01 — estoque sem limite que passa a ter limite (2026-10-18)

### Diagnóstico

- Escrevi o critério do receptor como "`novo is None` ou `novo > anterior`" e não tratei o `anterior` igual a `None`, que significa sem limite (E03-05).
- O código seguiu a frase. Em `alterar_estoque(admin, estoque, "10")` com o limite atual `None`, a comparação `Decimal > None` levanta `TypeError`. Isso desfaz a alteração e impede o administrador de limitar um estoque que estava sem limite. O defeito aparece com ou sem reservas.

### Regra

O receptor classifica a mudança pelo par (`anterior`, `novo`), em que `None` é sem limite:

| `anterior` | `novo` | Classificação | Receptor |
|---|---|---|---|
| `None` | finito | redução (ilimitado → limitado) | não aloca |
| finito | `None` | aumento | chama `_alocar_produto` |
| finito | finito, maior | aumento | chama `_alocar_produto` |
| finito | finito, menor ou igual | redução ou sem mudança | não aloca |
| `None` | `None` | sem mudança (`alterar_estoque` nem envia o sinal) | não aloca |

- A comparação numérica só acontece com os dois lados finitos.
- A inclusão continua chegando com `anterior=Decimal("0")` e cai nas linhas de aumento: finito → `None` ou finito → maior.
- A validação de reservas não muda e continua em `alterar_estoque` (E03-05), antes do sinal. Um limite novo menor que o total reservado é recusado com `EstoqueAbaixoDoReservado`, também quando o limite anterior era `None`.
- Sem alocação na passagem de ilimitado para limitado: nenhuma unidade foi liberada. Com estoque sem limite, as pendentes do produto já tinham sido atendidas na inclusão ou no aumento.

## Dependências e decisões em aberto

- Depende de E05-01.
- Sem decisões em aberto.
