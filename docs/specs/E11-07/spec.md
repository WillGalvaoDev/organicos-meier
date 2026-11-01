# E11-07 — Telas da apuração (administrador) e efeitos para o comprador

Fatia 7 de 8 da milestone **E11 — Apuração final e fila de pendentes**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E11-01.

## Contexto e objetivo

O administrador precisa iniciar a apuração, ver o resultado e aprovar o avanço. A tela deve mostrar:
- pagos e não pagos;
- caixas invalidadas;
- mínimo;
- estornos gerados;
- déficit de frete (§13: "apuração de pagamentos, caixas inválidas, déficit de frete e autorização/acompanhamento de estornos").

O comprador precisa ver no pedido o efeito da apuração:
- o cancelamento por falta de pagamento;
- as unidades em caixa invalidada, com o estorno e a volta à fila.

O carrinho continua mostrando reservado e pendente separados (E05). Esta fatia entrega essas telas sobre os serviços das fatias E11-01 a E11-06.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13 (administrador) | Dashboard com ações necessárias. Apuração de pagamentos, caixas inválidas, déficit de frete e autorização e acompanhamento de estornos. Situação dos pagamentos na margem. |
| Especificação §13 (comprador) | Pedido congelado e pagamento. Histórico de pedidos, pagamentos e estornos. Reservado e pendente separados no carrinho, com a remoção de pendentes. |
| Especificação §7 | Apuração só a partir de `T0 + 48h`, por autorização. Avanço por aprovação do administrador. |
| Infraestrutura 3.2 e 4.8 | Operações financeiras do administrador com nova autenticação (proteção de acesso, não etapa de aprovação). |
| Infraestrutura 4.3 | O painel mostra a situação de cada pedido (E08-05). |
| Cenários §16 | 13, 14 e 15, pela tela |

## Escopo

**Dentro:**
- O bloco "Apuração final" na página da rodada do administrador (`administracao/rodadas/<pk>/estoque/`, a mesma do painel da margem, E08-05).
- As duas ações: iniciar e aprovar.
- O texto do cancelamento por inadimplência no painel e no pedido do comprador.
- A linha das unidades em caixa invalidada no pedido do comprador.

**Fora:**
- O painel consolidado (E15).
- As telas de devolução, que já existem (E10-07). Esta fatia só põe links para elas.

## Regras

**Rotas** (administrador, `somente_administrador`; POST com `exige_reautenticacao_por_passkey`, como as ações financeiras da E09-08 e da E10-07):

| Rota | Método | Ação |
|---|---|---|
| `administracao/rodadas/<pk>/apuracao/iniciar/` | POST | `iniciar_apuracao(request.user, rodada)` |
| `administracao/rodadas/<pk>/apuracao/aprovar/` | POST | `aprovar_resultado(request.user, rodada)` |

- **Sucesso:** redireciona para a página da rodada, com uma mensagem.
  - Início com resultado `valida`: "Apuração feita. Confira o resultado e aprove o avanço."
  - Início com retorno: "Apuração feita. A rodada voltou para interesse; autorize as devoluções na lista de devoluções."
  - Aprovação: "Resultado aprovado. A rodada aguarda o fornecedor."
- **`ApuracaoRecusada`:** a página da rodada com status 409 e a mensagem da recusa.
- **`ConsultaAoProvedorFalhou`:** status 503, com "Não foi possível consultar o provedor; nada foi apurado. Tente de novo."
- **GET nas rotas de ação:** 405.
- **Comprador ou fornecedor:** a recusa de `somente_administrador`.

**Bloco "Apuração final" na página da rodada:**
- **Em `pagamento`, sem apuração:**
  - antes de `T0 + 48h`: "A apuração pode começar a partir de {data e hora} (horário de Brasília)", sem botão. O servidor recusa do mesmo jeito (E11-01);
  - a partir de `T0 + 48h`: o botão "Iniciar apuração", com o texto "A apuração cancela os pedidos não pagos e invalida as caixas incompletas. Ela não pode ser desfeita."
- **Com apuração, em `pagamento` (resultado `valida`, aguardando a aprovação), em `aguardando_fornecedor` ou de volta em `interesse`:** o resultado da última apuração da rodada:
  - quando foi feita e por quem;
  - os pedidos pagos (comprador e total) e os não pagos, com a situação:
    - "Cancelado (falta de pagamento)";
    - "Cancelado (suspensão)";
    - "Cancelado (remoção da conta)";
  - as caixas invalidadas: produto e número da caixa. Sem caixas: "Nenhuma caixa invalidada.";
  - o valor válido, o mínimo do ciclo e o resultado:
    - "Mínimo atendido";
    - "Mínimo não atendido: a rodada voltou para interesse";
  - os estornos gerados, um por reembolso:
    - comprador;
    - motivo ("caixa invalidada" ou "mínimo não atingido");
    - valor;
    - a situação da devolução, com o rótulo do grupo da lista de devoluções da E10-07 no singular. Por exemplo, a obrigação sem parcela aparece como "Pendente de autorização";
    - o link para o detalhe em `financeiro/devolucoes/<obrigacao>/`;
  - em `pagamento` com `valida`: o botão "Aprovar resultado e avançar", com o texto "O frete dos pedidos não pagos fica como déficit do administrador. As devoluções podem ser autorizadas antes ou depois.";
  - depois da aprovação: frete efetivo, arrecadado e déficit (`frete_do_ciclo`) e "Resultado aprovado em {data e hora} por {nome}".
- **Na rodada de volta em `interesse`:** o bloco aparece enquanto o ciclo apurado for o último ciclo da rodada com abertura, para o administrador acompanhar as devoluções. Ele some quando um novo pagamento é aberto.

**Painel da margem (E08-05):** `CANCELAMENTOS_POR_EXTENSO` ganha `inadimplencia: "Cancelado (falta de pagamento)"`.

**Pedido do comprador** (`pedidos/<pk>/`, só o dono, como hoje):
- **pedido cancelado por inadimplência:** a situação "Cancelado por falta de pagamento" e a frase "O pagamento não foi identificado até o fim do prazo. Nada foi cobrado neste pedido.";
- **pedido pago com unidades em caixa invalidada:** por item, "{quantidade} {unidade} em caixa que ficou incompleta: estorno proporcional e unidades na fila de pendentes do fornecedor". O estorno aparece na seção de estornos que já existe (E10-07). As unidades restauradas aparecem no carrinho como pendentes (E05);
- **pedido pago de rodada que voltou para interesse:** "A rodada voltou para interesse. O valor pago será devolvido integralmente, e seus interesses continuam reservados na rodada."

**Dados mínimos:** a tela do comprador não mostra outros compradores, a caixa inteira nem o mínimo do fornecedor (§2, §6.2).

## Invariantes

- Nenhuma rota GET altera estado.
- Nenhuma tela de comprador expõe dados de outro comprador.

## Dependências e decisões em aberto

Depende das fatias E11-01 a E11-06 e de E10-07. Nenhuma decisão em aberto.

## Correções da revisão: textos ao comprador nos casos de R01 e R02 (2026-11-01)

Origem: revisão independente sobre `1a36495` (`docs/specs/E11-08/review.md`, matriz: "revalidar afirmações ao comprador nos casos R01/R02"). Vale o resumo na E11-08 (`spec.md`, "Correções da revisão da E11").

- **Pedido pago de rodada que voltou para interesse, com a conta ativa:** o texto continua o mesmo, inclusive no caso do R01 (a reserva da parte paga volta mesmo depois da remoção da sobra).
- **Pedido pago de rodada que voltou para interesse, com a conta suspensa ou removida na apuração** (R02): a página mostra só "A rodada voltou para interesse. O valor pago será devolvido integralmente." Ela não afirma que os interesses continuam reservados. O comprador suspenso pode consultar os pedidos pagos (§2).
- **Pedido pago com unidades em caixa invalidada:**
  - **com a parcela restaurada** (inclusive o caso do R01): continua "… estorno proporcional e unidades na fila de pendentes do fornecedor";
  - **sem restauração** (conta impedida na apuração): "… estorno proporcional", sem a menção à fila.
- **O aviso `itens_cancelados` de caixa incompleta (E11-04, regra 7)** segue a mesma distinção. Sem restauração, o corpo não tem a frase da fila de pendentes.

A fonte da distinção é o registro da apuração:
- a `RestauracaoDeCaixa`, na rodada viável;
- a auditoria das parcelas não restauradas, no retorno.

A tela não deduz nada da situação atual da conta.

## Correção da revalidação: R02 residual (2026-11-01)

Origem: revalidação sobre `0af24ad` (`docs/specs/E11-08/review.md`, "R02 residual"). Vale a regra 2-A da E11-05 (`spec.md`, "Correção da revalidação").

- **A fonte:** saber se o pedido pago de uma rodada que voltou para interesse tinha a conta impedida na apuração vem de `retorno.contas_impedidas`, na auditoria da apuração. Deixa de vir de `removidas_por_conta_impedida`, que só lista as remoções feitas no retorno.
- **O texto:** com o comprador em `contas_impedidas`, a página mostra só "A rodada voltou para interesse. O valor pago será devolvido integralmente.", sem afirmar interesses reservados (`interesses_reservados` falso no contexto). Fora dela, o texto continua o mesmo.
- **Sem estado atual:** a tela não consulta a situação atual da conta para isso. Reativar a conta depois da apuração não faz a página prometer reservas; suspendê-la depois não muda o que a página diz do efeito da apuração.
- **Sem a auditoria da apuração** (situação que não deve ocorrer num pedido pago apurado): a página não afirma interesses reservados.
