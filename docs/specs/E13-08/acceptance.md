# E13-08 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Execução:** os cenários são os do `spec.md`, com o simulador, as chamadas processadas pelo executor real (`processar_chamadas()`), a tarefa de envio (`processar_pedidos_formais()`) e o invariante conferido no fim de cada critério.
- **Arranjos:** AF (E13-01), com a aprovação feita pela tela da E11-07.
- **Administrador:** entra de novo (`entrar_de_novo`) depois de cada avanço do relógio, como na E11-07.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenários 67 e 68 | positivo | AF; `BackendComFalhas(falhas=1)` | aprovar pela tela; rodar a tarefa em `T0 + 48h` e `+5 min`; o fornecedor abre o portal | duas tentativas automáticas (falha, sucesso); um e-mail igual ao snapshot; nenhuma `falha_no_pedido_formal`; o portal com o pedido formal (R$ 170,00) e a previsão 11/11/2026; o invariante sem violação |
| A-2 | Cenários 69, 92, 93 e 94; T-28, T-41 e T-54 | positivo | AF; `BackendQueFalha` até o reenvio manual, depois o `locmem` | rodar a tarefa até a terceira falha; entre a primeira e a terceira, POST de reenvio pela tela; depois da terceira, seguir o link do aviso e reenviar duas vezes (a primeira com falha, a segunda aceita) | o reenvio durante o ciclo com 409; três automáticas e duas manuais; o envio continua `concluido_com_falhas`; nenhuma tentativa automática depois; o `PedidoFormal` (pk, assunto, corpo, linhas) igual do começo ao fim; o invariante sem violação |
| A-3 | Cenários 70, 95, 118 e 119; T-29 e T-55 | concorrência | AF com o ciclo concluído; e, no caso do cenário 118, a terceira tentativa automática pausada dentro de `enviar_email` | pela rota HTTP, com transações reais: dois POST com o mesmo token; dois POST com tokens distintos ao mesmo tempo; um POST durante a tentativa automática pausada | um envio para o mesmo token; duas tentativas em sequência para tokens distintos, sem sobreposição; o POST durante a automática com 409, sem esperar; nenhum `PedidoFormal` a mais; o invariante sem violação |
| A-4 | Cenário 67; §12 | positivo | o A-1 | ajustar a previsão para 14/11/2026 pela tela; reenviar o pedido | os avisos a A e B; o portal e o pedido de A com 14/11/2026; o e-mail do reenvio com o corpo original (11/11/2026) |
| A-5 | Cenário 40, T-11 | positivo | AF; `definir_liberacao("pix", horas=72)`; relógio em `T0 + 50h` | POST de repasse de 10,00 pela tela; o relógio em `T0 + 80h`, repasse de 80,00; em `T0 + 92h`, repasse de 90,00; cada saída também registrada no simulador; `conciliar_dias_pendentes_agora()` no dia seguinte | o primeiro com 409 e "R$ 0,00" liberado; os outros aceitos; a obrigação com F com saldo 0,00; nenhuma outra conta muda; a conciliação dos dias sem divergência; o invariante sem violação |
| A-6 | Herdado E12; infra 3.2 e 7 | positivo | o A-5 concluído (repasse total) e o pedido formal aceito | o cancelamento com reembolso pela tela; a cobertura da falta pela reserva (e, faltando saldo livre, um aporte e a cobertura); `autorizar_devolucoes_do_cancelamento_agora()`; `processar_chamadas()`; os estornos concluídos no simulador | as obrigações de X (94,35) e de Y (106,15), com a parte de produtos (80,00 e 90,00) sem cobertura antes da escolha do administrador; o serviço e o frete financiados pela receita e pelo frete da rodada, até o saldo de cada uma (o que faltar também fica sem cobertura); depois da cobertura, os estornos concluídos; o repasse e o movimento dele iguais; o pedido formal e as tentativas iguais; o reenvio recusado com `rodada_cancelada`; o invariante sem violação |
| A-7 | Infra 7; E12-04 | positivo | o A-6, com uma segunda cobrança de X pendente no simulador desde antes do prazo | aprovar essa cobrança no simulador depois do cancelamento; processar o aviso | o destino `devolucao` com a obrigação integral financiada pelo próprio pagamento; o alerta crítico `pagamento_depois_do_cancelamento`; a obrigação com F e o repasse iguais; o invariante sem violação |
| A-8 | Cenários 21 e 67; T-25 e T-27 | negativo | os estados dos A-1, A-5 e A-6 | em cada um, a conta de F abre o portal, baixa o CSV e tenta as rotas da E13-07 A-12 e A-13 | os campos da E13-07 e as mesmas recusas em todos os estados; nenhum valor de serviço, frete, repasse, reserva ou dado de comprador |

| Critério | Arquivo de teste |
|---|---|
| A-1, A-2 e A-4 a A-8 | `tests/tecnicos/test_pedido_formal_ponta_a_ponta.py` |
| A-3 | `tests/tecnicos/test_pedido_formal_ponta_a_ponta.py`, com transações PostgreSQL reais |

## Correção da revisão: E13-R01 pela rota (2026-11-13)

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-9 | E13-R01; E13-03 A-19; E13-04 | concorrência | dois AF com o ciclo concluído com sucesso, de fornecedores distintos (PF1 e PF2); o POST de reenvio do PF1 com o token t1 pausado dentro de `enviar_email` | pela rota HTTP, com transações reais, o POST de reenvio do PF2 com o mesmo t1, confirmado esperando a trava; depois o primeiro retomado | o primeiro POST redireciona com "Reenvio registrado: aceito pelo serviço de e-mail."; o segundo responde 400 "Recarregue a página e tente de novo." (o `token_invalido` da E13-04); um e-mail no total; uma tentativa com t1, no PF1; nenhuma tentativa no PF2; o invariante sem violação |

| Critério | Arquivo de teste |
|---|---|
| A-9 | `tests/tecnicos/test_pedido_formal_ponta_a_ponta.py`, com transações PostgreSQL reais |
