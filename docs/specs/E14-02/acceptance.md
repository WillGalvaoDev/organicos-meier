# E14-02 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:** os da E14-01 (AE, AE-recebido, AE-liberada, AE-48).
- **Chamada:** `registrar_ocorrencia(admin, item, quantidade, tipo, acionamento=...)`.
- **Valores:** pela §9.2, com `ROUND_HALF_UP`, sobre os valores registrados.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 48, §9.2 | positivo | AE-48, sem recebimento | ocorrência `faltante` de 2 unidades no item de Q | uma `OcorrenciaDeEntrega` (tipo, quantidade 2,000, etapa `aguardando_fornecedor`, autor, instante); um `Reembolso` com motivo `ocorrencia_de_entrega`, produtos 20,00, serviço 1,00, frete 4,00 (total 25,00); uma `ObrigacaoComComprador` de 25,00 para C; `nova = True`. **Red esperado:** a função não existe |
| A-2 | Cenário 48, §7.1 | positivo | o A-1 | comparar o `Pedido`, os `ItemDoPedido`, as parcelas, a rodada e o pedido formal com o estado anterior | iguais, campo a campo; a rodada continua em `aguardando_fornecedor` (cenário 52) |
| A-3 | Cenário 18, §9.2 | positivo | AE-18 | ocorrência `faltante` de 2 unidades no item de Q (25,00 de produtos) | `Reembolso` com produtos 25,00, serviço 1,25 e frete 5,00 (31,25); obrigação de 31,25 para C |
| A-4 | AE, §9.2 | positivo | AE | `faltante` de 2 em X-P1 | produtos 20,00, serviço 1,00, frete 2,59 (10,35 × 20/80 = 2,5875); obrigação de 23,59 para A; `sem_cobertura = 0`; o saldo da obrigação com F cai de 170,00 para 150,00 (E09-06, antes do repasse) |
| A-5 | Cenário 49 | negativo | AE | `faltante` de 4 em X-P1, depois `nao_entregue` de 3 em X-P1 | a segunda é `passa_do_saldo_do_item`, com a mensagem terminada em "(2 unidade)."; nenhum registro novo |
| A-6 | Regra 5 | negativo | AF-parcial da E13 (Y não pagou; as caixas de P2 invalidadas e as 4 unidades de X-P2 reembolsadas na apuração) | ocorrência `faltante` de 1 em X-P2 | `passa_do_saldo_do_item` (saldo 0), com "(0 unidade)."; nenhum registro |
| A-7 | Regra 4 | negativo | AE-recebido parcial: P1 recebido 9 | `faltante` de 3 em Y-P1 | `passa_do_pedido_formal`, com "(2 unidade)."; `faltante` de 2 em Y-P1 é aceita |
| A-8 | Regra 4 | negativo | AE com P2 recebido 4 | `incorreto` de 2 em Y-P2, depois `incorreto` de 3 em X-P2 | a primeira aceita (produtos 10,00, serviço 0,50, frete 1,29); a segunda `passa_do_recebido`, com "(4 unidade)." |
| A-9 | Decisão (a), regra 6 | positivo e negativo | AE-liberada, sem retirada | `incorreto` de 6 em X-P1; depois `faltante` de 1 em X-P1 | a primeira aceita, com etapa `disponivel_para_retirada` e sem conferência de recebido ou de pedido formal; a segunda `passa_do_saldo_do_item` (saldo 0). A interação com a retirada é a E14-05 A-10 |
| A-10 | Regra 4 | negativo | AE cancelada (sem reembolso); rodada em `pagamento` | registrar | `etapa` nas duas, sem escrita |
| A-11 | Regra 4 | negativo | AE; um pedido cancelado por inadimplência no AF-parcial (o de Y) | ocorrência num item de Y | `item_fora_do_pedido_formal` |
| A-12 | Regra 4 | negativo | AE | tipo `"troca"`, `""` e `None`; quantidades `0`, `-1`, `0.5` (incremento 1), `1.0001` e o `float` `1.0` | `tipo_invalido` e `quantidade_invalida`, sem escrita |
| A-13 | Regra 1 | negativo | AE | registrar com o comprador A (dono do item), com a conta de fornecedor de F e com `None` | `PermissionDenied`, sem escrita (cenário 50 no serviço) |
| A-14 | Regra 2 | positivo | o A-4 com o acionamento a1 | repetir idêntico com a1 | a mesma ocorrência, `nova = False`; um `Reembolso`; uma obrigação; uma auditoria |
| A-15 | Regra 2 | negativo | o A-14 | a1 com quantidade 1; a1 em item de Y; `"abc"` | `acionamento_invalido`, sem escrita |
| A-16 | Regra 7, cenário 115 | positivo | um item como o M da E10 (0,6 kg a 0,15/kg, subtotal 0,09, incremento 0,1) numa rodada AE | seis ocorrências de 0,1 kg | produtos 0,02, 0,02, 0,02, 0,02, 0,01 e 0,00; a sexta com `Reembolso` e sem obrigação; uma sétima `passa_do_saldo_do_item` |
| A-17 | Regra 10 | positivo | o A-4 | ler a auditoria | `ocorrencia.registrar` com o admin, o pedido, o item, `faltante`, 2, a etapa, os três componentes, a obrigação e o UUID sob `acionamento`; nenhum valor com o e-mail ou o nome de A |
| A-18 | Só inserção | negativo | o A-4 | `update` e `delete` da ocorrência pela aplicação e por SQL direto | recusados |
| A-19 | Regra 8 | positivo | o A-4 | ler as parcelas de devolução e as notificações | nenhuma `ParcelaDeDevolucao` para a obrigação; nenhuma notificação `estorno`; `autorizar_devolucao(obrigacao, autor=admin)` depois funciona como na E10 |
| A-20 | Infra 3.2, E09-06 | positivo | AE com o repasse total a F (170,00, E13-06) | `faltante` de 2 em X-P1 | obrigação de 23,59 com produtos 20,00 sem cobertura; serviço e frete cobertos pela receita e pelo frete da rodada; nenhum movimento na obrigação com F |
| A-21 | T-18 | concorrência | AE; a primeira chamada (`faltante` de 4 em X-P1) pausada depois das travas | a segunda (`nao_entregue` de 4 em X-P1, outro acionamento) numa segunda conexão, confirmada esperando com `esperar_outra_conexao_na_trava()`; depois a primeira retomada | a primeira grava (produtos 40,00, serviço 2,00, frete 5,18); a segunda `passa_do_saldo_do_item`; um `Reembolso` e uma obrigação no item |
| A-22 | T-18 | concorrência | AE | duas chamadas idênticas com a1 em paralelo | uma ocorrência, um `Reembolso` e uma obrigação; as duas devolvem o mesmo `pk` |
| A-23 | Ordem das travas, E12 | concorrência | AE; `cancelar_rodada(..., com_reembolso=True)` pausado com as travas retidas | `registrar_ocorrencia` numa segunda conexão, confirmada esperando; depois o cancelamento retomado | a ocorrência recebe `etapa`; sem impasse; o cancelamento devolve o integral de X e Y (94,35 e 106,15) |
| A-24 | Cenário 114 | positivo | AE com `faltante` de 2 em X-P1 (23,59) | `cancelar_rodada(..., com_reembolso=True)` | a obrigação do cancelamento para A é 94,35 − 23,59 = 70,76; o item X-P1 completa exatamente 60,00 de produtos; nenhuma ocorrência criada pelo cancelamento (cenário 52) |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-20 e A-24 | `tests/tecnicos/test_ocorrencias.py` |
| A-21 a A-23 | `tests/tecnicos/test_ocorrencias.py`, com transações PostgreSQL reais |
| A-1, A-2, A-3, A-5 e A-21 | também `tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py` |
