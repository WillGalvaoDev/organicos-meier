# E13-06 — O repasse ao fornecedor e o pagamento do frete

Fatia 6 de 8 da milestone **E13 — Pedido formal, repasse e portal do fornecedor**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E13-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E13-01.

## Contexto e objetivo

A transferência ao fornecedor é manual nesta versão: o administrador paga o fornecedor fora do sistema, a partir da conta do provedor, e registra o repasse no painel (§7, §10, A3). O repasse:
- usa somente a obrigação com aquele fornecedor naquela rodada (§9.3, P-2, cenário 40);
- fica limitado à parte **liberada** dessa obrigação no provedor (infraestrutura 3.4, T-11).

O registro no livro já existe (`registrar_saida`, E09-07). Esta fatia acrescenta:
- a consulta obrigatória ao provedor antes do repasse (infraestrutura 4.2);
- a liquidez do frete (herdado da E09);
- a tela das saídas da rodada.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §10 | Transferência ao fornecedor manual; o administrador registra a confirmação no painel. O repasse manual não é pagamento de comprador e continua permitido. Usa somente recursos registrados como obrigação com aquele fornecedor. |
| Especificação §9.3 | Recursos de um fornecedor exclusivos para o pagamento dele, ressalvadas as devoluções devidas antes do repasse; nunca financiam tarifas, déficits, prejuízos ou obrigações de outro fornecedor. Déficit de frete é do administrador. |
| Especificação §13 | Administrador: registro de repasse. |
| Infraestrutura 3.2 | Repasse manual: baixa da obrigação com aquele fornecedor. Devolução depois do repasse: financiada por receita de serviço, reserva ou novo aporte. |
| Infraestrutura 3.4 | Repasse limitado à parte liberada da obrigação com aquele fornecedor. Pagar A com dinheiro liberado de B financiaria A com recursos de B (P-2). |
| Infraestrutura 3.5 | Toda saída da conta do provedor é registrada no livro-razão: repasse, retirada de receita, devolução. |
| Infraestrutura 4.2 | Consulta obrigatória antes do registro de repasse; se a consulta falhar, a ação fica bloqueada. |
| Herdado da E07 | O registro de repasse chama `consultar_antes_de_decidir` e fica bloqueado com `ConsultaAoProvedorFalhou`. |
| Herdado da E09 | O repasse é `registrar_saida(tipo="repasse", conta=obrigacao_fornecedor(f, r), identificacao=...)`, limitado ao liberado. O pagamento do frete é `registrar_saida(tipo="pagamento_do_frete")`, limitado ao saldo do frete; definir aqui se precisa de liquidez própria. A tela mostra o liberado e o a liberar. |
| Cenários §16 | 40 |
| Testes técnicos | T-11 (segunda metade, pela tela) |

## Escopo

**Dentro:**
- Os serviços `registrar_repasse` e `registrar_pagamento_do_frete`.
- A liquidez do frete.
- A página das saídas da rodada e as duas rotas.

**Fora:**
- A retirada de receita (já entregue na E09-07).
- A conciliação dessas saídas, que já é a da E09-07 (L-8).
- O cancelamento depois do repasse, ponta a ponta (E13-08).

## Regras

**`registrar_repasse(autor, rodada, *, valor, identificacao, justificativa) -> MovimentoFinanceiro`:**

1. **Permissão e contrato:** só o administrador ativo (`PermissionDenied`); fora de transação (`RuntimeError`), porque a consulta vem antes.
2. **Obrigação existente:** a rodada precisa ter a apuração no livro de um ciclo (`ApuracaoNoLivro`). Sem ela, `RepasseRecusado("sem_obrigacao")`, com "A rodada não tem valores devidos ao fornecedor.", sem consulta nem escrita.
3. **Consulta prévia:**
   - `consultar_antes_de_decidir(referencia)` para cada pedido válido (`PedidoApurado`) das apurações no livro da rodada, por `pk`, fora de transação e sem trava;
   - `ConsultaAoProvedorFalhou` bloqueia o registro, sem escrita;
   - o que a consulta sincronizar (por exemplo, a data de liberação de um pagamento) já vale para o limite da regra 4.
4. **Registro:** numa transação, `registrar_saida(autor, tipo="repasse", conta=obrigacao_fornecedor(fornecedor, rodada), valor=..., identificacao=..., justificativa=...)` (E09-07):
   - o limite é o liberado da obrigação com aquele fornecedor naquela rodada, calculado sob a trava da conta;
   - as recusas são as da E09-07: `LiquidezInsuficiente` (com o liberado e o a liberar), `SaidaRepetida`, `MovimentoInvalido` e a justificativa vazia;
   - o movimento só baixa `obrigacao_fornecedor(fornecedor, rodada)`. Nenhuma outra conta muda (cenário 40).
5. **Etapa:** o repasse é registrável em qualquer etapa em que a obrigação tenha saldo liberado: `aguardando_fornecedor`, `disponivel_para_retirada` e também `cancelada`. No cancelamento, os valores continuam nas destinações e qualquer movimento posterior segue P-2 (infraestrutura 3.2; §7.2). O limite é sempre o do livro.
6. **Auditoria `rodada.repasse`:** o autor, a rodada, o fornecedor, o valor, a identificação, o liberado e o a liberar antes do registro.

**`registrar_pagamento_do_frete(autor, rodada, *, valor, identificacao, justificativa) -> MovimentoFinanceiro`:**

7. **Permissão e registro:** só o administrador ativo. Numa transação, `registrar_saida(tipo="pagamento_do_frete", conta=frete(rodada), ...)`. Sem a apuração no livro: `RepasseRecusado("sem_obrigacao")`, com "A rodada não tem frete apurado."
8. **Liquidez do frete** (decisão desta fatia, herdada da E09). O pagamento do frete passa a ser limitado ao **liberado** do frete, e não mais ao saldo:
   - `liquidez(frete(r))` passa a ser aceita;
   - `E_lib(frete)` é a soma de duas partes:
     - o que a apuração transferiu para o frete a partir de pedidos com o pagamento que quitou já liberado (a mesma regra da obrigação com fornecedor, E09-07);
     - as coberturas de déficit recebidas pelo frete (`cobertura_de_despesa`), que vêm da receita de serviço ou da reserva e contam como liberadas;
   - `S(frete)` é tudo o que já saiu do frete por qualquer fluxo (pagamentos do frete e financiamento de devoluções);
   - `liberado = max(0, min(saldo, E_lib − S))`;
   - na tabela `SAIDAS` da E09-07, o `pagamento_do_frete` passa a limitar pelo liberado. Ele continua sem bloqueio por invariante violado.
9. **Consulta:** o pagamento do frete não está na lista de decisões com consulta obrigatória da infraestrutura 4.2, então não consulta.
10. **Auditoria `rodada.pagamento_do_frete`:** como a regra 6.

**Tela** `GET administracao/rodadas/<pk>/saidas/` (nome `rodadas_saidas`), `somente_administrador`; sem apuração no livro: 404.

11. **Bloco "Repasse ao fornecedor":**
    - a obrigação com o fornecedor nesta rodada: o saldo, o liberado e o a liberar;
    - o histórico dos repasses (momento em Brasília, valor, identificação, justificativa e administrador);
    - o formulário com o valor, a identificação da saída no provedor e a justificativa, e o botão "Registrar repasse".
12. **Bloco "Frete":**
    - o frete efetivo, o arrecadado, o déficit e o coberto (`frete_do_ciclo`, E09-06);
    - o saldo, o liberado e o a liberar do frete;
    - o histórico dos pagamentos do frete;
    - o formulário igual ao do repasse, com o botão "Registrar pagamento do frete".
13. **Rotas** `POST administracao/rodadas/<pk>/saidas/repasse/` (`rodadas_saidas_repasse`) e `POST administracao/rodadas/<pk>/saidas/frete/` (`rodadas_saidas_frete`):
    - protegidas por `exige_reautenticacao_por_passkey`, como a retirada de receita (E09-07);
    - `GET` dá 405;
    - o valor é lido como na retirada (`_valor_digitado`: vírgula decimal, duas casas, maior que zero).

    | Situação | Resposta |
    |---|---|
    | Sucesso | Redireciona para a página com "Repasse de <valor> registrado." ou "Pagamento do frete de <valor> registrado." |
    | Valor inválido | 400, com a mensagem da retirada |
    | Sem identificação ou sem justificativa | 400, com "Informe a identificação da saída no provedor." ou "Informe a justificativa." |
    | `LiquidezInsuficiente` | 409, com "Só <liberado> estão liberados no provedor (<a liberar> a liberar)." |
    | `SaidaRepetida` | 409, com "Esta identificação de saída já foi registrada." |
    | `ConsultaAoProvedorFalhou` (só no repasse) | 503, com "Não foi possível consultar o provedor; o repasse não foi registrado. Tente de novo." |
    | `RepasseRecusado` | 409, com a mensagem |

14. **Links:** a página do pedido formal (E13-04) e a página da rodada mostram "Saídas da rodada" quando há apuração no livro.

## Decisões técnicas

- **O frete ganha liquidez.**
  - **Por quê:** pagar o frete com dinheiro de compradores ainda não liberado usaria o saldo liberado de outras destinações, por exemplo a obrigação com outro fornecedor. É o mesmo efeito que a infraestrutura 3.4 proíbe no repasse (P-2: recursos de fornecedor nunca financiam despesas).
  - **Coberturas contam como liberadas:** elas vêm da receita de serviço ou da reserva, recursos da plataforma que o administrador escolheu usar para o déficit (P-1). O lançamento delas já é limitado pelas regras da E09 (saldo da receita, saldo livre da reserva).
- **Sem consulta no pagamento do frete.** A infraestrutura 4.2 lista as decisões que exigem consulta; o pagamento do frete não está entre elas. Acrescentar a consulta seria uma regra nova.
- **Repasse permitido na rodada cancelada.** O §7.2 preserva repasses e obrigações, e a infraestrutura 3.2 diz que, sem reembolso, os valores continuam onde estavam e qualquer movimento segue P-2. O repasse registra uma transferência que o administrador já fez fora do sistema, e toda saída da conta do provedor precisa estar no livro (infraestrutura 3.5); recusar o registro deixaria o livro diferente do provedor. Com reembolso, as devoluções já consumiram a obrigação (E12-03), e o limite do livro impede repassar o que não é mais devido.
- **Nova autenticação nas duas rotas.** É a proteção que a E09-07 já aplica às saídas da conta do provedor (retirada de receita).

## Invariantes

- Um repasse só baixa a obrigação com aquele fornecedor naquela rodada (cenário 40).
- Nenhum repasse passa do liberado da obrigação; nenhum pagamento do frete passa do liberado do frete (T-11).
- A mesma identificação de saída nunca é registrada duas vezes.

## Casos-limite e concorrência

- **Dois repasses concorrentes que juntos passam do liberado:** um passa e o outro recebe `LiquidezInsuficiente`, pela trava da conta (E09-07).
- **Repasse de A com B liberado e A a liberar:** recusado, mesmo com saldo suficiente no provedor (T-11).
- **Pagamento descoberto na consulta prévia:** segue as regras da E08-04 e da E11 (devolução de destino); não muda a obrigação com o fornecedor.
- **Devolução depois de repasse total:** a parte de produtos fica sem cobertura e o administrador escolhe a fonte (infraestrutura 3.2; E09-06). É exercitado na E13-08.

## Dependências e decisões em aberto

- Depende da E13-01 (links), da E09-06/E09-07 (livro, liquidez e saídas) e da E07-06 (consulta).
- Nenhuma decisão em aberto.

## Esclarecimento da implementação (2026-11-09)

**Ajuste de arranjo aceito no E09-07 A-25** (correção R06, `tests/tecnicos/test_financeiro_conciliacao.py::test_identificacao_de_64_caracteres_e_conciliavel`):
- **Por quê:** o teste semeava o frete por uma apuração simulada, sem pagamento liberado, e pagava 5,00 dele. Pela regra 8, esse pagamento passa a ser recusado (`LiquidezInsuficiente`), e a recusa é o comportamento certo.
- **O ajuste:** o arranjo passa a semear o frete por uma cobertura de déficit vinda da receita de serviço, que conta como liberada.
- **O que fica igual:** o objeto do critério, a conciliação de identificações de 64 caracteres. As asserções não mudam.

O A-25 continua valendo com esse arranjo, e nenhuma regra muda.
