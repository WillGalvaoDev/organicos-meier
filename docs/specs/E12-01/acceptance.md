# E12-01 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

## Arranjo CI (cancelamento em interesse)

- Fornecedor F, com a rodada em `interesse` e P1 (10,00) no estoque com limite 11.
- Parcelas de P1, em ordem de sequência:
  - C `pendente`, com 3 pendentes (fila do fornecedor, de antes da rodada);
  - A `ativa`, com reservado 6;
  - B `ativa`, com reservado 5;
  - D `ativa`, com original 3, reservado 0 e pendente 3 (sem estoque).
- Montado pelas fábricas e pelos serviços de interesse (E05), com `total_reservado(P1) = 11`.
- O autor é o administrador do apoio. O teste roda fora de transação (`transaction=True`).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §7, §7.2, cenário 41 | positivo | CI | `cancelar_rodada(admin, rodada, com_reembolso=False)` | a rodada `cancelada`; um `CancelamentoDaRodada` com o autor, `cancelada_em` igual ao relógio, `com_reembolso` falso, mensagem vazia e `etapa_anterior = interesse`; as parcelas de A e B `removida` com zero; `total_reservado(P1) = 0`. **Red esperado:** o serviço não existe |
| A-2 | §5.2, herdado E05 | positivo | o A-1 | inspecionar C e D | C `pendente` com 3, mesma sequência; D `pendente` com 3 pendentes, reservado 0 e mesma sequência; nenhuma parcela nova |
| A-3 | Regra 6 | positivo | CI com A `ativa`, original 8, reservado 6 e pendente 2 | `cancelar_rodada` | A `pendente`, com pendente 2, reservado 0 e a mesma sequência |
| A-4 | Com reembolso sem pagamento | positivo | CI | `cancelar_rodada(admin, rodada, com_reembolso=True, mensagem="  Fornecedor sem estoque  ")` | o mesmo efeito do A-1; `com_reembolso` verdadeiro; a mensagem gravada aparada; nenhum reembolso nem obrigação |
| A-5 | 17.2, cenário 42 | negativo | CI | `cancelar_rodada` com um comprador, com um fornecedor, com um administrador suspenso e com `None` | `PermissionDenied` nos quatro; nenhuma escrita (rodada, parcelas e auditoria iguais) |
| A-6 | Infra 4.8, T-13 | negativo | o A-1 feito | `cancelar_rodada` de novo, com cada indicação | `CancelamentoRecusado("ja_cancelada")`; um único registro; uma auditoria |
| A-7 | Regra 3 | negativo | CI | `com_reembolso=None`, `"sim"` e `1` | `CancelamentoRecusado("indicacao_obrigatoria")` nos três, sem escrita |
| A-8 | Regra 3 | negativo | CI | mensagem com 1001 caracteres; depois com 1000 | a primeira `mensagem_longa`, sem escrita; a segunda aceita |
| A-9 | T-16, infra 4.8 | negativo | — | inspecionar a assinatura de `cancelar_rodada`; chamar com `compradores=[A]` ou `motivo="x"` | só `autor`, `rodada`, `com_reembolso` e `mensagem`; os argumentos extras dão `TypeError`, sem escrita |
| A-10 | Contrato | negativo | CI | `cancelar_rodada` dentro de `transaction.atomic()` aberto pelo teste | `RuntimeError`, sem escrita |
| A-11 | Etapas | positivo | CI levada a `fechamento` (E06) e, em outro teste, a `fechamento_encerrado` | `cancelar_rodada` | cancela nas duas; `etapa_anterior` correspondente; o prazo do fechamento e o ciclo intactos |
| A-12 | Decisão em aberto | negativo | uma rodada com a etapa `disponivel_para_retirada` gravada no banco | `cancelar_rodada` | `CancelamentoRecusado("rodada_encerrada")`, sem escrita |
| A-13 | Auditoria, §14 | positivo | o A-1 | ler a auditoria `rodada.cancelar` | o autor; a rodada, a etapa anterior, o instante, `com_reembolso` falso, sem mensagem; as parcelas de A e B com a situação anterior `ativa`, a nova `removida` e as reservas 6 e 5; nenhum campo de motivo |
| A-14 | Depois do cancelamento | negativo | o A-1 | `adicionar_interesse(A, P1, 1)`; `iniciar_fechamento(admin, rodada)`; alterar o limite de P1 | as recusas existentes sem rodada ativa / fora de etapa; nenhuma escrita |
| A-15 | §5.2, E05-03 | positivo | o A-1 | `remover_pendente(C, P1, 1)` | aceita; C com 2 pendentes |
| A-16 | E03-02, §5.2 | positivo | o A-1 | `abrir_rodada(admin, F)` com P1 no estoque (limite 11) | uma rodada nova em `interesse`; a fila atendida pela regra da E05: C reserva 3 e D 3, na ordem de sequência; a rodada cancelada intacta |
| A-17 | Cenário 45 | positivo | o A-11 (cancelada em `fechamento`) | inspecionar ciclos, condições e prazos | iguais aos de antes do cancelamento, sem linha nova nem alterada |
| A-18 | Concorrência, T-13 | concorrência | CI | dois `cancelar_rodada` em paralelo, o primeiro pausado depois de gravar o registro, antes do commit ("Padrão das corridas", E09-01) | o segundo espera e recebe `ja_cancelada`; um registro; uma auditoria |
| A-19 | Concorrência | concorrência | CI com estoque livre (limite 15) | (i) `adicionar_interesse(A, P1, 2)` pausado antes do commit e o cancelamento em paralelo; (ii) o cancelamento pausado antes do commit e a adição em paralelo | (i) o cancelamento espera; depois, A sem reserva. (ii) a adição espera e é recusada. Nos dois, `total_reservado(P1) = 0` |
| A-20 | Concorrência | concorrência | CI em `fechamento` com o prazo vencido | `encerrar_fechamento` pausado antes do commit e o cancelamento em paralelo; depois a ordem inversa | sem impasse; a rodada `cancelada` nos dois casos; na primeira ordem, `etapa_anterior = fechamento_encerrado`; na segunda, o encerramento não grava nada |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-17 | `tests/tecnicos/test_cancelamento_da_rodada.py` |
| A-18 a A-20 | `tests/tecnicos/test_cancelamento_da_rodada.py`, com transações PostgreSQL reais |
