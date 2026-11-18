# E16-09 — Parecer independente

## Gate de especificação — 2026-11-18 — 696a378

**APROVADO para implementação.** Escopo: `spec.md` e A-1 a A-7 de `acceptance.md`. Não constitui aprovação de produção nem encerramento do cenário 96/R05.

Fontes conferidas: funcional §§2, 5.2, 13 e 16.96; E05-05; E11-08 A-6; E02-10 (política comprador); decisão do responsável de 2026-11-18 registrada na especificação, que escolhe valores atuais da mesma fonte do carrinho, inclusive sem pedidos. A decisão resolve a dúvida material levantada na revisão anterior, sem retirar o histórico do requisito. A seção adicional em “Meus pedidos” preserva o histórico dos pedidos e explicita que os interesses exibidos são atuais.

| Critério | Avaliação |
|---|---|
| A-1 | Estado 6 reservado/4 pendente, estoque livre zero, pendentes reais e consulta HTTP do histórico definidos; falha inicial observável pela ausência da seção. O arranjo da E11-08 deve ser adaptado para obter exatamente 6/4, não apenas reutilizado com seus números originais. |
| A-2 | Compara os valores das duas telas e cobre zero pendente; executar as leituras sem mudança concorrente de estado, conforme a condição “no mesmo instante” da regra 9. Não exige igualdade entre requisições separadas por uma alteração legítima. |
| A-3 | Pendente continua visível sem rodada ativa e com produto indisponível; inclui zero reservado e unidade. |
| A-4 | Consulta do comprador da sessão e tentativa de escolher outro comprador pela URL têm resultado negativo verificável. |
| A-5 | Estados sem pedido e sem interesse definidos independentemente. |
| A-6 | Política preservada e referenciada na E02-10: anônimo redirecionado, outros papéis recebem 403. Comprador suspenso continua autorizado à consulta pela política `comprador`; não trocar por `comprador_ativo`. É regressão, podendo passar antes da produção. |
| A-7 | Exibição sem ação de escrita e link ao carrinho; preservação de parcelas e registros verificável. |

As regras adicionais de título, ordem, nomes, unidade/formatação, fonte única e visibilidade por etapa são obrigatórias mesmo quando o critério da tabela não enumera cada detalhe. “Em qualquer etapa” refere-se às linhas retornadas pela consulta prevista nas regras 2 e 3; não autoriza incluir parcelas `em_pedido` ou mudar a composição do carrinho. A implementação deve manter a lista e os links de pedidos existentes e não introduzir escrita, migração ou nova política.

Conferida a viabilidade da interface pela leitura de `apps/interesses/consultas.py::carrinho_do_comprador`, da view de pedidos e da política especificada, depois dos requisitos. A consulta existente já permite reutilizar os dados sem novo cálculo. Nenhum achado impeditivo de especificação; nenhuma nova decisão comercial necessária.

Verificações: leitura documental e diff do commit; sem testes executados neste gate, sem alteração de produção. Próximo passo: implementador escreve e observa os testes falharem pela ausência do comportamento, implementa a seção e registra Red/Green/Refactor e regressões. A-6 é a exceção de regressão explicitamente prevista. Depois, revisão independente da implementação e ligação do teste aprovado na E16-07 A-44. A aprovação deste documento não basta para fechar C96.
