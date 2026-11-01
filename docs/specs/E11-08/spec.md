# E11-08 — Fila de pendentes de ponta a ponta, com pendentes reais da apuração

Fatia 8 de 8 da milestone **E11 — Apuração final e fila de pendentes**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E11-01.

## Contexto e objetivo

A E05 entregou a fila com pendentes criados por fábrica:
- o atendimento (`alocar_pendentes`);
- a remoção pelo comprador;
- a exibição separada de reservado e pendente;
- a exclusão das pendentes do mínimo.

A E11 cria as pendentes de verdade, na restauração de caixa invalidada (E11-04). Por isso, a milestone pede os cenários 74 a 79 e 96 a 104 e os testes T-30 a T-33 e T-42 a T-47 repetidos de ponta a ponta, com pendentes reais da apuração.

Esta fatia é, sobretudo, de testes. Ela corrige só o que esses testes mostrarem fora da especificação.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §5.2, Q-1, Q-5, R-5, R-6 | Fila do fornecedor, FIFO original, atendimento antes de reservas novas, isolamento por fornecedor, visibilidade e remoção pelo comprador, pendentes fora do mínimo, dos pedidos e das cobranças. |
| Infraestrutura 4.10 | `alocar_pendentes`, `remover_pendente`, invariantes e consultas. |
| Herdado da E05 | Os cenários 74–79 e 96–104 e os testes T-30–T-33 e T-42–T-47 repetidos de ponta a ponta com pendentes reais da apuração. |
| Cenários §16 | 75 a 78 e 96 a 102 e 104 (os cenários 74 e 79 estão na E11-04 e na E11-02, e o 103 na E11-05) |
| Testes técnicos | T-30, T-31, T-33 e T-42 a T-47 (T-20 e T-32 na E11-04; T-21 e T-22 na E11-05) |

## Escopo

**Dentro:**
- Os testes de ponta a ponta, com o arranjo abaixo.
- As correções que eles exigirem, dentro das regras já aprovadas.

**Fora:**
- O pedido formal, que lê só a quantidade reservada pela R-6 (E13). A parte do pedido formal no T-47 fica para a E13.
- O encerramento da rodada.

## Arranjo de ponta a ponta (arranjo FP)

1. **Rodada R1 do fornecedor F,** com o mínimo de 50,00:
   - o produto P (10,00, múltiplo 20), com as parcelas A 6, C 8 e B 6, nessa ordem: uma caixa só, de 20;
   - o produto Q (10,00, sem múltiplo), com A 10.
2. **Fechamento e abertura do pagamento** pelos serviços (E06, E08).
3. **Pagamentos:** A e C pagam pelo simulador; B não paga.
4. **Apuração** em `T0 + 48h`:
   - a caixa de P invalidada;
   - os estornos de A e de C;
   - as parcelas de A (6) e de C (8) em P passam a `pendente`, com as sequências originais;
   - valor válido 100,00 (Q de A), resultado `valida`.
5. **Aprovação do resultado** (E11-06).
6. **R1 fora das etapas ativas,** por atualização direta da etapa para `disponivel_para_retirada` no arranjo. O serviço que encerra a rodada é da E14. Nenhuma parcela de P fica `em_pedido`, então a atualização não afeta a contagem do estoque de P.
7. **Rodada R2 de F** aberta pelo serviço (E03), em interesse. Antes de incluir P no estoque, o administrador retira o múltiplo de P (`alterar_multiplo` com vazio, E03, permitido em interesse), para que os cenários de R2 não dependam de caixa. Depois, P entra no estoque pelo serviço de inclusão, com o limite do cenário.

Num cenário com um segundo fornecedor G, a rodada e os produtos de G são independentes.

## Regras

- **Os testes usam os serviços e as rotas reais** a partir do passo 7: abertura, inclusão e alteração de estoque, interesse, remoção de pendentes, carrinho, progresso, fechamento e abertura do pagamento.
- **Verde de primeira:** um critério que já passa antes de qualquer mudança de produção é registrado como regressão, com o comando e a saída, como determina a correção E10-R08 para critérios que já passam. Não conta como Red.
- **Correção:** um critério que falha mostra uma divergência entre o comportamento da E05 e a especificação, com pendentes reais. A correção segue TDD normal (Red, Green) e fica dentro das regras da E05 e da infraestrutura 4.10. Se a correção exigir uma regra nova, ela volta ao especificador.

## Invariantes verificados

- Total reservado ≤ estoque.
- Reservado + pendente ≤ original.
- Nenhuma reserva fictícia.
- Sequência imutável.
- Isolamento por fornecedor.

## Dependências e decisões em aberto

Depende de E11-04, E11-06 e das fatias E05-02 a E05-05. Nenhuma decisão em aberto.

**Registro para a E14:** o encerramento da rodada precisa tirar as parcelas `em_pedido` da contagem de `total_reservado`. Sem isso, a próxima rodada de um produto que teve unidades válidas conta essas unidades no estoque. O arranjo FP evita esse caso de propósito, e ele fica para a especificação da E14.

## Correções da revisão da E11 (2026-11-01)

Origem: a revisão independente sobre `1a36495` (`review.md`, "Parecer independente — agente 3 — 2026-10-31"), com o veredito REPROVADO e o R03 bloqueado por decisão. Os quatro achados se resolvem com regras técnicas derivadas dos documentos-base. Nenhuma regra comercial muda.

**R03.** A infraestrutura 4.3 já estabelece a ordem: reconsultar, cancelar no provedor, aplicar a P-6 e só então decidir, com bloqueio se o provedor falhar. A especificação local estava abaixo dela e foi alinhada (AGENTS.md §2). Não há decisão que permita adiar o cancelamento, e alinhar à fonte superior não precisa de decisão nova. Com isso, o ponto deixa de estar bloqueado.

| Achado | Decisão | Onde está a especificação | Critérios |
|---|---|---|---|
| R01 — remover a sobra pendente impedia recuperar as unidades pagas | A restauração depende só da conta, e nunca da situação da parcela; a sobra removida não volta | E11-04, "Correção E11-R01"; E11-05, "Correções da revisão", R01 | E11-04 A-15 a A-18; E11-05 A-18 |
| R02 — a reserva de conta suspensa ou removida ocupava o estoque no retorno | No retorno, as parcelas da conta impedida passam a `removida`, antes da conferência do estoque e da fila; o pedido não muda | E11-05, "Correções da revisão", R02 | E11-05 A-19 a A-21 |
| R03 — o cancelamento no provedor era só agendado depois da decisão | Passo 4-A: cancelar e confirmar no provedor antes da transação da decisão, sem travas de negócio; falha bloqueia; conferência sob as travas | E11-01, "Correção E11-R03" | E11-01 A-8 (substituído) e A-22 a A-29 |
| R04 — o retorno promovia as travas e causava impasse com a tarifa tardia | Nenhuma trava mais forte que `FOR NO KEY UPDATE` em toda a transação da apuração, inclusive nos serviços reutilizados | E11-05, "Correções da revisão", R04 | E11-05 A-22 a A-24 |
| Textos ao comprador (reflexo de R01 e R02) | O texto segue o registro da apuração (restaurada ou não) | E11-07, "Correções da revisão" | E11-07 A-18 a A-21 |

**Pontos do implementador:**
- **E11-05 A-3:** reescrito com os dois momentos, a restauração e o retorno inteiro.
- **E11-02 A-4 e A-6:** os ajustes dos testes ficam aceitos (`acceptance.md` da E11-02).
- **Conta suspensa depois do commit da restauração:** a suspensão a remove (E11-04 A-14). Isso já estava coberto e não muda.

### Ordem e regras comuns

1. **R04 primeiro:** muda as travas que os outros testes de retorno exercitam.
2. **R03.**
3. **R01, nos dois ramos, e R02, cada um com os critérios de tela da E11-07 junto.** A prevenção da E10-07 vale aqui: os critérios de tela do mesmo achado são escritos e vistos falhar antes da correção do serviço.

**Para cada critério novo:** Red real antes do código de produção, registrado no `review.md` da fatia, com o comando, o arquivo inteiro (sem `-k`), a falha pelo motivo esperado e o Green. Os critérios marcados como regressão podem passar de primeira e são registrados como regressão, como na correção E10-R08.

**Commits separados por achado.**

### Provas do parecer

As seis provas do parecer têm de passar como estão:
- `test_remover_sobra_nao_remove_reserva_paga_no_retorno`;
- `test_remover_sobra_nao_impede_restauracao_da_caixa_paga`;
- `test_suspenso_nao_prende_estoque_no_retorno`;
- `test_cancelamento_no_provedor_precede_apuracao`;
- `test_falha_do_cancelamento_bloqueia_apuracao`;
- `test_retorno_concorre_com_tarifa_sem_impasse`.

### Verificação final

O implementador repete a verificação final da E11 e registra os resultados neste `review.md`:
- a suíte completa;
- `ruff check --no-cache`;
- `ruff format --check`;
- `mypy`;
- `makemigrations --check`.

## Correção da revalidação da E11: R02 residual (2026-11-01)

Origem: a revalidação independente sobre `0af24ad` (`review.md`, "Revalidação independente das correções — agente 3 — 2026-11-01"), com o veredito REPROVADO só pelo R02 residual. R01, R03 e R04 estão encerrados. Nenhuma regra comercial muda e não há decisão pendente.

| Achado | Decisão | Onde está a especificação | Critérios |
|---|---|---|---|
| R02 residual — o pagante com conta impedida e sem parcela removível recebia o aviso e via a promessa de reservas | A apuração registra a situação da conta de cada pagante (`retorno.contas_impedidas`), com ou sem parcela removível, e guarda as não restauradas; o aviso e a tela usam esse registro, nunca a situação atual | E11-05, "Correção da revalidação: R02 residual" (regra 2-A); E11-07, "Correção da revalidação: R02 residual" | E11-05 A-25 a A-29; E11-07 A-22 a A-25; E11-04 A-19 (regressão) |

**Ordem:** primeiro os critérios de serviço (E11-05 A-25 a A-29) e os de tela (E11-07 A-22 a A-25), escritos e vistos falhar juntos; depois a correção do serviço e da tela. O E11-04 A-19 e o E11-05 A-27 e A-28 são regressões: podem passar de primeira e são registrados como tal. Valem as regras comuns de Red/Green e de registro da seção anterior. Um commit para os testes (Red) e outro para a correção.

**Provas:** a prova `test_conta_impedida_com_parcela_ja_removida` do parecer, com os dois parâmetros, e as seis provas anteriores têm de passar como estão.

**Verificação final:** a mesma da seção anterior, registrada neste `review.md`.
