# E14-04 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:** os da E14-01, com o endereço do apoio registrado.
- **Liberar:** `liberar_retirada(admin, rodada)` com o relógio em `L = T0 + 72h`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §7, §10 | positivo | AE-recebido | liberar | a rodada em `disponivel_para_retirada`; uma `LiberacaoDaRetirada` com `liberada_em = L`, `prazo_final = L + 7 dias` (2026-11-12 13:00 UTC), o endereço vigente e o autor. **Red esperado:** a função não existe |
| A-2 | Regra 6, §12 | positivo | o A-1 | ler as notificações | uma `retirada_liberada` para A (pedido X) e uma para B (pedido Y), com o título `Retirada liberada: F`, o corpo com "seu pedido <pk>", o endereço, "Retire até 12/11/2026 às 10:00 (horário de Brasília)" e a frase dos comunicados; o link `/pedidos/<pk>/`; as chaves `retirada_liberada:<liberação>:<conta>`; os envios por e-mail registrados como nos demais eventos |
| A-3 | Herdados E08/E11 | positivo | AE-recebido; o `total_reservado` de P1 e P2 igual a 11 e 12 antes | liberar | as parcelas `em_pedido` de A e B em P1 e P2 passam a `removida`, com reserva 0; `total_reservado` de P1 e P2 igual a 0; nenhuma parcela criada e nenhuma sequência mudada; uma parcela `pendente` de outro comprador em P1 continua igual |
| A-4 | Cenário 22, regra 7 | positivo | o A-1 | `abrir_rodada(admin, F)` logo depois; incluir P1 com estoque 11 e adicionar interesse de 11 de outro comprador | a nova rodada em `interesse`; o interesse de 11 aceito integralmente (o estoque não foi consumido pela rodada liberada) |
| A-5 | Regra 4, §10 | negativo | AE com P1 recebido 9 e P2 recebido 12 | liberar | `LiberacaoRecusada("recebimento_pendente")`, com "Ainda falta resolver: P1 (2 unidade)."; a rodada continua em `aguardando_fornecedor`; nada gravado; nenhum aviso |
| A-6 | Regra 4, §10 | positivo | o A-5, mais a ocorrência `faltante` de 2 em X-P1 | liberar | aceita; o aviso vai a A e a B |
| A-7 | Regra 4 | positivo | AE com P2 todo `nao_entregue` (ocorrências de 4 em X-P2 e 8 em Y-P2) e P1 recebido 11 | liberar | aceita; avisos para A e B (os dois têm P1 a retirar) |
| A-8 | Regra 6 | positivo | AE com P1 recebido 11, Y-P1 todo `incorreto` (5) e Y-P2 todo `nao_entregue` (8); P2 recebido 4 | liberar | aceita; aviso só para A; nenhum para B (sem saldo a retirar) |
| A-9 | Regra 6 | positivo | AE-recebido com B suspenso; outro arranjo com B removido | liberar | o suspenso recebe o aviso; o removido não |
| A-10 | Regra 4 | negativo | AE-recebido sem endereço registrado | liberar | `sem_endereco`, sem escrita |
| A-11 | Regra 4 | negativo | o A-1 | liberar de novo | `ja_liberada`, sem escrita; uma liberação; nenhum aviso novo |
| A-12 | Regra 4 | negativo | rodadas em `interesse`, `pagamento` e AE-recebido cancelada | liberar | `etapa` em todas |
| A-13 | Regra 1 | negativo | AE-recebido | liberar com o comprador A, com o fornecedor e com `None` | `PermissionDenied`, sem escrita |
| A-14 | Decisão (a), regra 9 | negativo | o A-1 | `cancelar_rodada(admin, rodada, com_reembolso=True)` e `com_reembolso=False` | `CancelamentoRecusado("rodada_encerrada")` nos dois; nenhum `CancelamentoDaRodada`, obrigação ou aviso; a rodada continua `disponivel_para_retirada` |
| A-15 | Regra 8 | positivo | o A-1 | comparar pedidos, itens, situações, pagamentos, `MovimentoFinanceiro`, `PedidoFormal` e `EnvioDoPedidoFormal` com o estado anterior | iguais |
| A-16 | Regra 8, E13-05 | positivo | o A-1 | `ajustar_previsao_de_entrega(admin, rodada, data futura)` | recusado como a E13-05 define fora de `aguardando_fornecedor` |
| A-17 | Regra 8, E13-06 | positivo | o A-1, com o liberado suficiente | registrar repasse de 10,00 a F | aceito, como na E13-06 |
| A-18 | Regra 5 | positivo | o A-1 | ler a auditoria | `rodada.liberar_retirada` com o autor, a rodada, o instante, o prazo, o endereço e as parcelas alteradas (situação anterior `em_pedido`, nova `removida`, reserva anterior) |
| A-19 | Regra 6 | positivo | AE-recebido com o endereço em duas linhas (`Rua A, 1\nFundos`) | liberar | o corpo do aviso contém "Rua A, 1, Fundos" |
| A-20 | Concorrência | concorrência | AE-recebido; a primeira liberação pausada com as travas retidas | uma segunda liberação numa segunda conexão, confirmada esperando com `esperar_outra_conexao_na_trava()`; depois a primeira retomada | a segunda recebe `ja_liberada`; uma liberação; dois avisos no total |
| A-21 | Concorrência, decisão (a) | concorrência | AE-recebido; a liberação pausada com as travas retidas | `cancelar_rodada(..., com_reembolso=False)` numa segunda conexão, confirmada esperando; depois a liberação retomada | o cancelamento recebe `rodada_encerrada`; sem impasse |
| A-22 | Concorrência | concorrência | AE com P1 recebido 9; a ocorrência `faltante` de 2 em X-P1 pausada com as travas retidas | a liberação numa segunda conexão, confirmada esperando; depois a ocorrência retomada | a liberação conclui depois da ocorrência e é aceita |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-19 | `tests/tecnicos/test_liberacao_da_retirada.py` |
| A-20 a A-22 | `tests/tecnicos/test_liberacao_da_retirada.py`, com transações PostgreSQL reais |
| A-1, A-4 e A-14 | também `tests/aceitacao/test_cenario_22_liberacao.py` |
