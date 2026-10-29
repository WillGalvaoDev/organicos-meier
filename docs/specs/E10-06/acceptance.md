# E10-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:**
- O arranjo da E10-04, com O1 de 31,25 financiada pela custódia.
- A parcela de O1 levada a `elegivel_excepcional` pelo caminho real do A-12 da E10-04 (`recusar_estornos(P1, "prazo_vencido")`).
- **Confirmação válida:** `meio="pix"`, `identificacao="E2E-123"`, uma justificativa e um PDF pequeno, válido.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §16 nº 35, §9.5 | positivo | o arranjo | `confirmar_devolucao_excepcional(parcela, autor=ADM, ...)` | uma `ConfirmacaoDeDevolucaoExcepcional` com pedido X, comprador B, valor 31,25, meio, identificação, justificativa, comprovante, autor e instante; a parcela em `concluida_fora_da_plataforma`; um movimento `devolucao_excepcional` com F16 de 31,25, de `obrigacao_comprador(O1)` para `reserva`; a obrigação liquidada; o alerta elegível resolvido; nenhum estorno novo no simulador |
| A-2 | §16 nº 35 | positivo | o arranjo, antes da confirmação | ler a obrigação | `devido − liquidado = 31,25`: a obrigação continua integral |
| A-3 | §16 nº 36, T-9 | negativo | parcelas em `solicitada`, `falha_temporaria`, `em_processamento` e `falha_definitiva` | confirmar | `DevolucaoRecusada("há devolução pendente na plataforma")`; nada gravado; nenhum arquivo no armazenamento |
| A-4 | §16 nº 36, T-9 | negativo | o A-1 feito | confirmar de novo | `DevolucaoRecusada("já confirmada")`; uma confirmação só; um F16 só |
| A-5 | T-9 | negativo | o A-1 feito | `tentar_devolucao_de_novo(parcela)`; `autorizar_devolucao(O1)`; e uma chamada `estornar` pendente da parcela, criada por fábrica, processada | a primeira recusa; a segunda devolve a mesma parcela sem nova chamada; a terceira termina em `FalhaDefinitiva("parcela_encerrada")`, sem chamar o provedor; nenhum estorno no simulador |
| A-6 | T-9, Infra 4.7 | negativo | o arranjo, com um estorno não contabilizado de 31,25 em processamento visível no simulador | confirmar | `DevolucaoRecusada("há devolução em processamento ou concluída no provedor")`; nada gravado; `verificar_estornos` agendada para a parcela |
| A-7 | Infra 4.2 | negativo | `indisponivel()` | confirmar | `ConsultaAoProvedorFalhou`; nada gravado |
| A-8 | Permissão | negativo | B e um fornecedor como autor | confirmar | `PermissionDenied`; nada gravado |
| A-9 | Validação | negativo | cada campo faltando; `meio="dinheiro"`; identificação com 101 caracteres; um `.pdf` com conteúdo de texto; um arquivo de 10 MB + 1 byte; um GIF | confirmar | `ValueError` em cada um; nada gravado; nenhum arquivo |
| A-10 | Decisão técnica | negativo | uma obrigação depois da apuração com 10,00 sem cobertura, levada a `elegivel_excepcional` | confirmar | `DevolucaoRecusada` com a mensagem de cobrir antes; depois de `designar_reserva` de 10,00, confirma: o consumo da designação (F11) e o F16 deixam a reserva com o saldo de antes |
| A-11 | Infra 3.5, 3.4 | positivo | o A-1 | `saldo_total_esperado()` e `verificar_invariante_agora()` | o total do livro igual ao de antes da confirmação; invariante sem violação |
| A-12 | Herdado E09 | positivo | uma obrigação `duplicidade` (E09-04) levada a `elegivel_excepcional`, com o alerta `duplicidade` aberto | confirmar | o alerta `duplicidade` resolvido; a confirmação com pedido X e comprador B |
| A-13 | Decisão técnica | positivo | uma obrigação `sem_pedido` levada a `elegivel_excepcional` | confirmar | a confirmação com pedido e comprador nulos; F16; parcela `concluida_fora_da_plataforma` |
| A-14 | Livro-razão | negativo | `lancar` direto com a transferência F16 e outro tipo (`devolucao`, `financiamento_de_obrigacao`); e com o tipo `devolucao_excepcional` de outra conta (`custodia`, `receita_servico`) para `reserva`, ou de `obrigacao_comprador(o)` para o exterior | lançar | `MovimentoProibido`, sem escrita (lista fechada da E09-01) |
| A-15 | Idempotência | positivo | o A-1 | `liquidar_obrigacao_fora_do_provedor(O1, 31.25, referencia=f"excepcional:{pk}")` de novo | devolve o mesmo movimento; nada novo |
| A-16 | Concorrência | concorrência | o arranjo | duas confirmações em paralelo | uma confirmação e um F16; a outra recusa com "já confirmada"; um arquivo só no armazenamento; sem `deadlock` |
| A-17 | Auditoria | positivo | o A-1 | ler a auditoria e o histórico | a confirmação com o autor e o instante; o histórico da parcela com `concluida_fora_da_plataforma` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-15 e A-17 | `tests/tecnicos/test_devolucoes_excepcional.py` |
| A-16 | `tests/tecnicos/test_devolucoes_concorrencia.py` |
| A-1, A-2, A-3 e A-4 | também `tests/aceitacao/test_cenarios_35_36_excepcional.py` |
| A-3 a A-5 | também `tests/tecnicos/test_t09_excepcional.py` (T-9) |
