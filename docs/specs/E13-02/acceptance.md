# E13-02 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo:** AF (E13-01), aprovado em `T0 + 48h`.
- **Serviço de e-mail simulado:** os backends de `tests/apoio/email_falho.py` (`BackendComFalhas.configurar(falhas=n)` e `BackendQueFalha`), ou o `locmem` quando o envio dá certo. A "aceitação" é o retorno sem exceção de `enviar_email`.
- **Relógio:** o `RelogioControlado`. "Rodar a tarefa" é chamar `processar_pedidos_formais()` com o relógio no instante indicado.
- **Administradores:** o do apoio e um segundo administrador ativo, para conferir o aviso aos dois.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §10, cenário 68 inverso | positivo | AF; e-mail aceito | rodar a tarefa em `T0 + 48h` | uma tentativa `automatica` nº 1, `ordem_automatica = 1`, `sucesso`, resposta `aceito pelo serviço de e-mail`, destino `pedidos@f.example`; o envio `concluido_com_sucesso`, `automaticas = 1`, sem próxima; um e-mail em `mail.outbox` para `pedidos@f.example` com o assunto e o corpo iguais, caractere a caractere, aos gravados. **Red esperado:** a tarefa não existe |
| A-2 | Cenário 68 | positivo | AF; `BackendComFalhas(falhas=1)` | rodar a tarefa em `T0 + 48h`; depois em `T0 + 48h + 5 min` | duas tentativas automáticas: a 1 com `falha` (resposta `ConnectionError`) e a 2 com `sucesso`; depois da primeira, `em_andamento` com a próxima em `+5 min`; no fim, `concluido_com_sucesso`; nenhuma notificação `falha_no_pedido_formal` |
| A-3 | Cenário 69, T-28 | positivo | AF; `BackendQueFalha` | rodar a tarefa em `T0 + 48h`, `+5 min` e `+35 min`; depois de novo em `+2 h` e `+1 dia` | exatamente três tentativas automáticas com `falha`; o envio `concluido_com_falhas` depois da terceira; as execuções seguintes não fazem tentativa (`processar_pedidos_formais()` devolve 0) |
| A-4 | §12, regra 6 | positivo | o A-3 | ler as notificações | uma `falha_no_pedido_formal` para cada administrador ativo, com a chave `falha_no_pedido_formal:<pedido formal>:<conta>`, o título `Falha no envio do pedido formal: F`, o corpo com o nº do pedido, a rodada, "3 tentativas automáticas", as três frases `Tentativa <n> em <data hora>: ConnectionError.` e "Use Reenviar pedido", e o link `/administracao/rodadas/<pk>/pedido-formal/`; nenhum comprador ou fornecedor notificado |
| A-5 | Regra 5 | negativo | AF; `BackendQueFalha` | rodar a tarefa em `T0 + 48h` e de novo em `T0 + 48h + 4 min` | uma tentativa só (a segunda execução vem antes do intervalo de 5 minutos); `proxima_tentativa_em = T0 + 48h + 5 min` |
| A-6 | Banco | negativo | o A-3 | criar diretamente uma quarta `TentativaDeEnvioDoPedidoFormal` automática (`ordem_automatica = 4`, e também `ordem_automatica = 3` repetida) | recusada pelas restrições (`IntegrityError`) |
| A-7 | Infra 4.2, regra 3 | negativo | AF; `falhar_proximas(1, operacao="buscar_por_referencia")` no simulador | rodar a tarefa em `T0 + 48h`; depois em `T0 + 48h + 5 min`, com o provedor normal | na primeira execução: nenhuma tentativa, nenhum e-mail, `automaticas = 0` e próxima em `+5 min`; na segunda: a tentativa nº 1, com `ordem_automatica = 1` e `sucesso`. **Red esperado:** o e-mail sai sem a consulta |
| A-8 | Infra 4.2 | positivo | AF | rodar a tarefa com o simulador registrando as consultas | antes da tentativa, uma busca por referência de X e uma de Y no simulador; nenhuma consulta depois do envio |
| A-9 | Herdado E12, regra 2 | positivo | AF; a rodada cancelada (E12, sem reembolso) antes da primeira execução | rodar a tarefa | nenhuma tentativa e nenhum e-mail; o envio `interrompido`, `motivo_da_interrupcao = rodada_cancelada`, sem próxima; auditoria `pedido_formal.interromper` |
| A-10 | Herdado E12 | positivo | AF; `BackendQueFalha`; a primeira tentativa falhou; a rodada cancelada depois | rodar a tarefa em `+5 min` | nenhuma segunda tentativa; o envio `interrompido`; nenhuma notificação `falha_no_pedido_formal` |
| A-11 | Concorrência, regra 4 | concorrência | AF; o primeiro envio pausado dentro de `enviar_email`, com as travas retidas | rodar a tarefa numa segunda conexão ao mesmo tempo | a segunda execução não espera nem envia (`skip_locked`): devolve 0; ao fim, uma tentativa e um e-mail |
| A-12 | Concorrência, herdado E12 | concorrência | AF; a primeira tentativa pausada dentro de `enviar_email` | `cancelar_rodada(..., com_reembolso=False)` numa segunda conexão; depois a tentativa retomada | o cancelamento espera a trava da rodada (`esperar_outra_conexao_na_trava()`) e conclui depois da tentativa; uma tentativa registrada; sem impasse; na próxima execução, se o envio ainda estava `em_andamento`, ele fica `interrompido` |
| A-13 | Regra 8 | positivo | AF; um backend que levanta `RuntimeError` | rodar a tarefa | a tentativa registrada com `falha` e resposta `RuntimeError`; a tarefa não levanta; o envio `em_andamento` com a próxima em `+5 min` |
| A-14 | Regra 7, §12 | positivo | o A-3 | comparar o livro-razão, a rodada, os pedidos e os pagamentos antes e depois | iguais: nenhum `MovimentoFinanceiro`, nenhuma mudança de etapa nem de situação |
| A-15 | Regra 4 | positivo | AF; o e-mail do pedido de F alterado para `novo@f.example` entre a primeira falha e a segunda tentativa | rodar a tarefa duas vezes | a tentativa 1 com destino `pedidos@f.example` e a 2 com `novo@f.example`; o assunto e o corpo das duas iguais aos gravados |
| A-16 | Regra 10 | positivo | o A-3 | ler a auditoria | `pedido_formal.ciclo_concluido` com autor `SISTEMA`, o estado `concluido_com_falhas` e as três tentativas (número, resultado, resposta) |
| A-17 | Privacidade, log | negativo | o A-3 com a captura de log | ler os registros de log | nenhum contém o e-mail do fornecedor, o assunto ou o corpo do pedido |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-10 e A-13 a A-17 | `tests/tecnicos/test_pedido_formal_envio.py` |
| A-11 e A-12 | `tests/tecnicos/test_pedido_formal_envio.py`, com transações PostgreSQL reais |
