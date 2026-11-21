# E16-09 — Reservado e pendente no histórico do comprador (cenário 96)

Fatia 9 da milestone **E16 — Homologação e encerramento da fase 1**, aberta na revalidação de 2026-11-18 (achado E16-R05, devolução do cenário 96). Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

O cenário 96 pede que o carrinho **e o histórico** mostrem separadamente "reservado: 6" e "pendente: 4", inclusive com o estoque do produto zerado.

- **O que já existe:** o carrinho mostra os dois valores desde a E05-05, com pendentes reais desde a E11-08.
- **O que falta:** o histórico do comprador é a tela "Meus pedidos" (`GET /pedidos/`), e ela só lista pedidos. A E11-08 A-6 citava "a consulta do histórico", mas o teste entregue só abriu o carrinho.
- **O revisor:** apontou a lacuna na revalidação de 2026-11-18 sobre `de1111c` (E16-07, R05).

Esta fatia faz a tela "Meus pedidos" mostrar as quantidades reservadas e pendentes do comprador.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Funcional §16.96 | "Comprador A tem 6 unidades reservadas e 4 pendentes de um produto. O carrinho e o histórico mostram separadamente "reservado: 6" e "pendente: 4", inclusive quando o estoque do produto está zerado." |
| Funcional §2, comprador ativo | "vê separadamente suas quantidades reservadas e pendentes [...]; consulta seu histórico e notificações" |
| Funcional §5.2, visibilidade | "O comprador vê separadamente suas quantidades reservadas e pendentes, inclusive quando não há estoque disponível." |
| Funcional §13, comprador | "Histórico de pedidos, pagamentos, estornos e retirada por item." É a única tela de histórico do comprador. |
| E05-05 | Formato "Reservado: <x>" e "Pendente: <y>", sempre os dois, mesmo com zero e com o estoque zerado; fonte `carrinho_do_comprador`. |
| E11-08 A-6 | Cenário 96 de ponta a ponta, com pendentes reais da apuração, no carrinho e no histórico. |
| Decisão do responsável, 2026-11-18 | O histórico mostra os valores **atuais** de cada produto, os mesmos do carrinho e da mesma fonte, mesmo com estoque zerado e mesmo sem pedidos. A remoção de pendentes continua só no carrinho. |

## Decisão registrada

Os documentos não diziam se o histórico mostra valores atuais ou os de um evento passado. O especificador apresentou três alternativas ao responsável:
1. **Valores atuais**, numa seção de "Meus pedidos". Impacto: só exibição, sem regra nova.
2. **Atuais e por evento:** além dos atuais, cada pedido mostraria quantas unidades dele foram para a fila. Impacto: pede um registro por pedido que hoje não é exibido.
3. **Retirar o histórico do cenário.** Impacto: exige mudar o texto-base.

O responsável escolheu a alternativa 1 em 2026-11-18. "Reservado" é uma quantidade presente, que não existe como fato passado de um pedido. O cenário descreve o estado atual ("tem 6 reservadas e 4 pendentes").

## Escopo

**Dentro:**
- a view `apps/pedidos/views.py::lista` e o template `templates/pedidos/lista.html`;
- os testes da fatia;
- a ligação da afirmação do histórico do cenário 96 na matriz da E16-07 (E16-07 regra 2-F, A-44) e o documento gerado.

**Fora:**
- remover pendentes pelo histórico: o formulário continua só no carrinho;
- quantidades por pedido ou por evento (alternativa 2, não escolhida);
- mudar o carrinho, os serviços de interesse, os modelos ou as migrações;
- mudar as políticas de acesso.

## Regras

1. **Seção nova:** `GET /pedidos/` passa a ter, depois da lista de pedidos, uma seção com o título `<h2>Interesses reservados e pendentes</h2>`.
2. **Fonte única:** as linhas da seção vêm de `carrinho_do_comprador(comprador)` (`apps/interesses/consultas.py`), a mesma função do carrinho. Nenhuma consulta própria recalcula reservado ou pendente.
3. **Conteúdo de cada linha:** uma por produto devolvido pela função, na ordem dela (fornecedor, depois produto), com:
   - o nome do fornecedor e o nome do produto;
   - `Reservado: <x>` e `Pendente: <y>`, sempre os dois, mesmo quando um deles é zero, com o filtro `quantidade_br` e a unidade do produto (`get_unidade_display`), como no carrinho.
4. **Estoque e etapa não escondem a linha:** a linha aparece com o estoque do produto zerado, com o produto indisponível, em qualquer etapa da rodada e sem rodada ativa do fornecedor. Isso cobre o pendente que espera uma rodada futura (§5.2).
5. **Sem interesses:** quando a função não devolve linhas, a seção mostra "Você não tem interesses reservados nem pendentes."
6. **Sem pedidos:** a mensagem "Você ainda não tem pedidos." continua, e a seção de interesses aparece do mesmo jeito.
7. **Só leitura:**
   - a seção não tem formulário nem botão;
   - um link "Alterar no carrinho" aponta para `/carrinho/`;
   - a requisição não grava nada.
8. **Isolamento:**
   - a seção só mostra as parcelas do comprador da sessão, como já garante a função;
   - a política da rota (`exige_comprador`) não muda: fornecedor, administrador e anônimo continuam recebendo a mesma recusa de hoje;
   - nenhum parâmetro da requisição escolhe outro comprador.
9. **Igualdade com o carrinho:** para o mesmo comprador, no mesmo instante, os pares (produto, reservado, pendente) do histórico são iguais aos do carrinho.

## Interfaces

- `GET /pedidos/` (rota `pedidos_lista`), com o contexto acrescido de `interesses`, que é a lista de grupos de `carrinho_do_comprador`. O template percorre `grupo.linhas`.
- Nenhuma rota nova, nenhum serviço novo, nenhuma migração.

## Invariantes

- Histórico e carrinho mostram os mesmos valores, pela mesma função.
- Nenhum dado de outro comprador aparece no histórico.
- Abrir o histórico não grava nada.

## TDD

Cada critério do `acceptance.md` começa por um teste que falha.

- **Red esperado do A-1:** "Interesses reservados e pendentes" ausente da página.
- **Teste que pode passar no Red:** o A-6, de política, porque a política não muda. Ele é teste de regressão, e o `review.md` registra isso.

## Dependências e decisões em aberto

- **Depende de:** E05-05, E11-08 e E02-10 (política `exige_comprador`).
- **Habilita:** a E16-07 A-44, que só fecha depois desta fatia aprovada.
- **Dependência nova:** nenhuma.
- **Decisão em aberto:** nenhuma. A semântica foi decidida pelo responsável em 2026-11-18.
