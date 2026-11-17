# E16-06 — Página de regras completa para o comprador

Fatia 6 de 8 da milestone **E16 — Homologação e encerramento da fase 1**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

A §13 lista entre as telas do comprador "Notificações, regras, endereço e comunicados", e a §2 diz que o comprador ativo "consulta catálogo, regras, endereço e progresso agregado". A página `regras/` (E14-03) hoje tem só a seção de retirada da §11. A E14 deixou para a E16 conferir se a §13 pede outras seções.

A leitura desta fatia: "regras" é a página de funcionamento da plataforma para o comprador. Ela precisa explicar as regras que afetam o que ele faz e paga (§3 a §11), não só a retirada.

Esta fatia acrescenta essas seções, com textos tirados das regras aprovadas. Ela não cria regra nova: cada frase da regra 2 cita a seção de origem.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, Comprador | Notificações, regras, endereço e comunicados. |
| Especificação §2 | O comprador ativo consulta catálogo, regras, endereço e progresso agregado. |
| Especificação §3 a §11 | As regras resumidas na regra 2. |
| E14-03 | A página `regras/`, com a seção "Retirada" e o endereço. |
| Milestone 16, herdado da E14 | Conferir se a §13 pede outras seções e, se pedir, especificar o conteúdo a partir da especificação funcional. |

## Escopo

**Dentro:** as seções novas da página `regras/` e o link para ela na página inicial do comprador, se ainda não houver.

**Fora:**
- mudar o acesso à página, que continua o da E14-03;
- textos para o fornecedor, que tem o portal (E13-07);
- termos de uso e política de privacidade: são documentos jurídicos, fora da especificação (§15, Operação: "não considerar este documento parecer jurídico").

## Regras

1. **Acesso e título:** o acesso à página continua o da E14-03. O título passa a "Regras de funcionamento" (`<h1>`), e o `<title>` passa a "Regras de funcionamento · Orgânicos Méier". A seção "Retirada" e o endereço não mudam.
2. **Seções**, nesta ordem, cada uma com `<h2>` e os parágrafos abaixo, com o texto exato. Os valores entre chaves vêm da configuração, quando ela existe: a taxa de serviço, os prazos de 24 horas e o prazo de retirada de sete dias. Assim a página não diverge do que o servidor aplica.
   1. **"Participação"** (§2, §3.1):
      - "O acesso é feito por convite, de uso único e válido por 24 horas. Cada e-mail corresponde a uma única conta."
      - "Contas de comprador e de fornecedor são separadas. Uma conta de fornecedor não faz compras."
   2. **"Interesse e reservas"** (§5, §5.2, §6.1):
      - "Os itens do carrinho representam interesse, não compra paga. Ao adicionar uma quantidade, ela reserva o estoque disponível da rodada; uma quantidade acima do estoque é recusada."
      - "Cada acréscimo entra na fila na ordem em que foi feito. Ao reduzir, as quantidades mais recentes saem primeiro."
      - "Cada fornecedor tem um mínimo de compra calculado só sobre os produtos, sem frete nem taxa. Em produtos vendidos por caixa, só contam as caixas completas."
      - "Quando uma caixa é invalidada por falta de pagamento de outro comprador e a rodada continua, as suas unidades pagas nela são reembolsadas e voltam para uma fila de pendentes do mesmo fornecedor, com a prioridade original. Quantidade pendente não é reserva: ela é atendida em uma próxima rodada, se houver estoque. Você pode remover quantidades pendentes a qualquer momento."
   3. **"Fechamento"** (§6.3, §7):
      - "Quando o mínimo é atingido, o administrador pode iniciar o fechamento, que dura {24} horas. Durante o fechamento ainda é possível alterar o carrinho."
      - "Ao fim do fechamento, as unidades que não completam uma caixa são removidas, pela ordem de adição, e você é avisado. Se o mínimo deixar de ser atingido, a rodada volta para a fase de interesse."
   4. **"Pagamento"** (§7, §7.1, §8.1, §8.3, §9):
      - "Quando o administrador abre o pagamento, o seu pedido é congelado: produtos e quantidades não mudam mais, nem por você nem pelo administrador."
      - "O valor a pagar é a soma dos produtos, da taxa de serviço de {5}% sobre os produtos e da sua parte do frete, proporcional ao valor dos seus produtos."
      - "Você tem {24} horas para pagar, a partir da abertura, sem prorrogação. O pagamento é feito somente pela plataforma de pagamentos integrada; nunca por Pix direto, transferência ou outro meio."
      - "Um pagamento iniciado no prazo e aprovado até {24} horas depois do fim dele é aceito. Aprovado depois disso, ele é devolvido."
   5. **"Apuração e falta de pagamento"** (§8.2):
      - "A apuração dos pagamentos é feita pelo administrador depois do fim desse período, e nunca antes."
      - "Quem não pagou perde os itens daquele fornecedor no carrinho, inclusive as reservas. Se os produtos pagos não alcançarem o mínimo, a rodada volta para a fase de interesse e todos os valores recebidos são devolvidos."
   6. **"Devoluções"** (§9.1, §9.2, §9.5):
      - "Há devolução quando o mínimo não é alcançado, quando uma caixa é invalidada, em ocorrências de entrega, no cancelamento da rodada com reembolso, em pagamento aprovado fora do prazo e em pagamento em duplicidade."
      - "As devoluções são feitas pela plataforma de pagamentos. Quando isso não for possível, o administrador devolve diretamente e registra a devolução."
      - "Depois de pagar, não há cancelamento voluntário do pedido."
   7. **"Cancelamento da rodada"** (§7.2):
      - "Só o administrador pode cancelar uma rodada, sempre por inteiro. Ao cancelar, ele indica se há reembolso; com reembolso, todos os que pagaram recebem de volta o valor pago."
   8. **"Retirada"**: a seção atual da E14-03, sem mudança.
3. **Fonte única dos valores:**
   - a taxa vem da mesma constante usada no cálculo do pedido (E08);
   - o prazo de 24 horas, da constante dos prazos (E06 e E08);
   - os sete dias, da constante da retirada (E14-05).

   O teste confere que a página muda junto com as constantes. Se alguma constante ainda não existir com nome próprio, ela é extraída sem mudar o valor.
4. **Sem dados pessoais nem de rodada:** a página não mostra rodada, pedido, comprador ou fornecedor específico. Ela é a mesma para todos os compradores, com o endereço da E14-03.
5. **Link:** a página inicial do comprador tem o link "Regras de funcionamento" para `regras/`. Se já existir link para a página, só o texto muda.

## Decisões técnicas

- **"Regras" = página de funcionamento para o comprador.** A §13 põe "regras" ao lado de notificações, endereço e comunicados, e a §2 a coloca entre o que o comprador consulta. As regras que o afetam estão nas §3 a §11. Os textos resumem essas seções, sem acrescentar condição nova, e por isso não exigem decisão comercial.
- **Texto fixo no template, com os valores da configuração.** Os textos são revisados nesta especificação. Os números vêm das constantes, para não divergir do que o servidor aplica.

## Invariantes

- Nenhuma regra nova: cada frase tem origem numa seção citada.
- O conteúdo da seção "Retirada" e o acesso à página não mudam.

## Dependências e decisões em aberto

- Depende da E14-03 e das constantes das E06, E08 e E14-05.
- Nenhuma decisão em aberto.
