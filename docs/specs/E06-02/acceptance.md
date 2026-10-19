# E06-02 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Nos critérios de concorrência, valem as regras de prevenção da correção E05-R04 (E05-01). Salvo indicação, o fornecedor `F` ("Sítio Boa Terra") tem mínimo R$ 100,00 e rodada em `interesse`, com `P` (R$ 10,00, sem limite). O relógio está em 2026-11-02 13:30 UTC.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §12 | positivo | A com 6 reservados de `P` e B com 4; C com uma parcela `pendente` de 3; D comprador sem parcelas | `iniciar_fechamento(admin, rodada)` | A e B recebem uma notificação `fechamento_iniciado` cada; C e D não recebem; título "Fechamento iniciado: Sítio Boa Terra"; corpo com "03/11/2026 às 10:30 (horário de Brasília)" e "sem precisar confirmar nada"; link `/carrinho/`; chaves `fechamento_iniciado:<ciclo>:<conta>` |
| A-2 | E04-01, E04-04 | positivo | o estado do A-1; A com telefone e consentimento de WhatsApp, B sem | leio os envios criados | um envio de e-mail para A e um para B; um envio de WhatsApp só para A |
| A-3 | Spec da fatia | positivo | A com parcelas em dois produtos da rodada | `iniciar_fechamento` | A recebe uma única notificação |
| A-4 | E04-02 | negativo | o estado do A-1; `emitir_evento_para_varios` levanta `RuntimeError` por `monkeypatch` | `iniciar_fechamento` | a exceção chega a quem chamou; etapa `interesse`; nenhum ciclo, prazo, auditoria ou notificação |
| A-5 | Spec da fatia | positivo | mínimo R$ 0,00 e nenhuma reserva | `iniciar_fechamento` | aceito; nenhuma notificação |
| A-6 | Spec da fatia | positivo | A com 10 reservados; o fechamento é iniciado, a rodada volta para interesse por `simular_volta_para_interesse` (ou pela transição real da E06-06, quando existir) e o fechamento é iniciado de novo | leio as notificações de A | duas notificações `fechamento_iniciado`, com chaves de ciclos diferentes |
| A-7 | Spec da fatia | positivo | fornecedor com nome de 150 caracteres | `iniciar_fechamento` | o título tem no máximo 150 caracteres, e a notificação é gravada |
| A-8 | E05-R03 | concorrência | A com 10 reservados | o comprador chama `adicionar_interesse(A, P, "1")` com a pausa depois de `_travar_conta` (como em E05-01 A-21), e a transação externa do início trava o fornecedor e espera a barreira; depois da barreira, a transação externa chama `iniciar_fechamento` | as duas terminam sem exceção nem `OperationalError`; A tem a notificação `fechamento_iniciado`; a adição fica gravada no fechamento |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-7 | `tests/tecnicos/test_rodadas_fechamento_aviso.py` |
| A-1 | também marcado `acceptance`, com o comentário `§12 início do fechamento` |
| A-8 | `tests/tecnicos/test_rodadas_fechamento_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
