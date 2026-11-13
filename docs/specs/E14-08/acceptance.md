# E14-08 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Execução:**
  - AE da E14-01, com a aprovação pela tela da E11-07 e o endereço registrado pela tela da E14-03;
  - as ações do administrador pelas rotas da E14-06, da E13-06 e da E10;
  - `entrar_de_novo` depois de cada avanço do relógio;
  - `processar_chamadas()` para as chamadas ao provedor;
  - o invariante financeiro conferido sem violação no fim de cada critério, como o `_invariante_ok()` da E13-08.
- **Liberação do simulador:** `simulador_pagamentos.definir_liberacao("pix", horas=0)` (como a E13-08 usa com 72), salvo indicação, para que o repasse tenha liquidez.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenários 18/48, §10 | positivo | AE; relógio em `T0 + 60h` | recebimento de P1 9 e P2 12; POST de liberação; ocorrência `faltante` de 2 em X-P1; POST de liberação de novo em `T0 + 72h` | a primeira liberação com 409 ("Ainda falta resolver: P1 (2 unidade)."); a ocorrência com 23,59; a segunda liberação aceita; os avisos `retirada_liberada` para A e B; o pedido X e os itens iguais aos originais |
| A-2 | §9.2, E10 | positivo | o A-1 | autorizar a devolução da obrigação de A pela tela da E10 (com passkey); `processar_chamadas()`; o estorno concluído no simulador | a parcela concluída; o aviso `estorno` para A; a página `pedidos/<X>/` com "Concluída" na ocorrência |
| A-3 | E13-06, infra 3.2 | positivo | o A-2 | repasse de 150,00 a F pela tela; depois mais 0,01 | o primeiro aceito; o segundo recusado (a obrigação com F tem saldo 0,00 depois dos 150,00); a obrigação com F nunca negativa |
| A-4 | Infra 3.2, E09-06 | positivo | AE-recebido com o repasse total de 170,00 a F; liberação em `L` | ocorrência `incorreto` de 2 em Y-P2 em `L + 1 dia` (depois da liberação e do repasse); cobertura da parte sem cobertura pela reserva (E09-06, com passkey); autorizar a devolução; concluir no simulador | a ocorrência com etapa `disponivel_para_retirada`; produtos 10,00 sem cobertura até a cobertura pela reserva; serviço 0,50 e frete 1,29 cobertos pela receita e pelo frete; a devolução de 11,79 concluída; nenhum movimento na obrigação com F; o saldo a retirar de Y-P2 igual a 6 |
| A-5 | Cenário 22 | positivo | o A-1 | logo depois da liberação, `rodadas_abrir` para F pela tela; incluir P1 com estoque 11; o comprador C adiciona 11 de P1; depois, em `L + 2 dias`, registrar a retirada de 4 em X-P1 na rodada antiga | a nova rodada aceita; o interesse de C com 11 reservados; a retirada antiga aceita; os registros das duas rodadas independentes |
| A-6 | Cenário 23 | positivo | o A-5; relógio em `L + 8 dias` | GET da página de retiradas; descarte de todo o saldo de X-P2 e de Y-P1 | antes do descarte, os itens com saldo como pendentes de decisão e nenhum `DescarteDeItem`; depois, os descartes gravados; nenhuma devolução nova; a página de A com "descartado 4" em X-P2 |
| A-7 | Decisão (a), cenário 52 | negativo | o A-1 (liberada) | POST de cancelamento pela tela da E12-06, com e sem reembolso | a recusa `rodada_encerrada`; nenhum `CancelamentoDaRodada`; nenhuma ocorrência criada; a rodada liberada |
| A-8 | Cenário 52 | positivo | AE com ocorrência `faltante` de 2 em X-P1 | o cancelamento com reembolso pela tela em `aguardando_fornecedor`; `processar_chamadas()` | a ocorrência e o reembolso dela intactos; a obrigação do cancelamento de A igual a 70,76 (94,35 − 23,59); nenhuma ocorrência criada pelo cancelamento; depois, a ocorrência e o recebimento recusados com `etapa` |
| A-9 | T-18, cenário 49 | concorrência | AE; com transações reais | dois POST de ocorrência ao mesmo tempo pela rota, `faltante` de 4 e `nao_entregue` de 4 em X-P1, com acionamentos distintos | um 302 e um 409 (`passa_do_saldo_do_item`); um `Reembolso` e uma obrigação no item; a soma das ocorrências de X-P1 igual a 4 |
| A-10 | Cenário 19 | positivo | o A-1 com A suspenso depois da liberação | retirada de 4 em X-P1 pela tela; GET `pedidos/<X>/` como A | a retirada aceita; a página de A com a seção de retirada |
| A-11 | Cenários 50, 21 e 67 | negativo | os estados dos A-1, A-4 e A-6 | em cada um, o comprador A tenta as rotas da E14-06 e o fornecedor F abre o portal e baixa o CSV | 403 para A, sem escrita; o portal com a etapa e o pedido formal, nas listas da E13-07, sem dados de recebimento, ocorrência, retirada ou comprador |
| A-12 | Invariantes | positivo | todos os critérios acima | no fim de cada um | `PedidoFormal`, linhas, `Pedido` e `ItemDoPedido` iguais aos do início; por item, reembolsado + retirado + descartado ≤ quantidade; o invariante financeiro sem violação |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-8 e A-10 a A-12 | `tests/tecnicos/test_retirada_ponta_a_ponta.py` |
| A-9 | `tests/tecnicos/test_retirada_ponta_a_ponta.py`, com transações PostgreSQL reais |
