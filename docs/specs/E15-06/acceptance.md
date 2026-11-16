# E15-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo AH:**
  - ADM1 e ADM2 administradores ativos e o comprador C;
  - entradas gravadas com `registrar_auditoria` e o relógio congelado:

| # | Momento (UTC) | Autor | Ação | Objeto | Motivo | Alterações |
|---|---|---|---|---|---|---|
| e1 | 2026-11-18 02:59:59 | SISTEMA | `rodada.apuracao_final` | uma rodada R | — | `{"pedidos": 3}` |
| e2 | 2026-11-18 03:00:00 | ADM1 | `rodada.cancelar` | a rodada R | "teste" | `{"com_reembolso": true}` |
| e3 | 2026-11-19 12:00:00 | ADM2 | `alerta.ciencia` | um alerta | — | `{"tipo": "<b>x</b>"}` |

- **Página:** `GET /administracao/historico/` como ADM1 autenticado com passkey.
- **Entradas da autenticação:** se a autenticação de ADM1 no arranjo gravar auditoria, essas entradas ficam fora da conferência, identificadas pelo código de ação. "Só eN" quer dizer que, entre e1, e2 e e3, só eN aparece.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 2 | positivo | AH | GET | 200; as linhas e3, e2 e e1, nessa ordem; e3 com "19/11/2026 09:00:00", "ADM2" (nome), `alerta.ciencia`, o objeto como "<objeto_tipo> <objeto_id>" gravados e "—" no motivo; e1 com "Sistema" e "17/11/2026 23:59:59". **Red esperado:** a rota não existe |
| A-2 | Regra 2 | negativo | AH | GET | o texto `<b>x</b>` escapado (`&lt;b&gt;`), sem elemento `<b>` vindo de e3 |
| A-3 | Regra 2 | positivo | AH com a conta de ADM2 ausente (id que não existe mais, gravado diretamente) | GET | "Conta <id>" no autor |
| A-4 | Regra 2 | positivo | 120 entradas | GET; `?pagina=3` | 50 na primeira página; 20 na terceira; `?pagina=99` dá a última, como `get_page` |
| A-5 | Regra 3 | positivo | AH | `?acao=rodada.cancelar` | só e2; a lista de ações com as três ações em ordem alfabética |
| A-6 | Regra 3 | positivo | AH | `?autor=sistema`; `?autor=<pk de ADM1>` | só e1; só e2 |
| A-7 | Regra 3 | positivo | AH | `?de=2026-11-18&ate=2026-11-18` | só e2 (e1 é 17/11 em Brasília) |
| A-8 | Regra 3 | positivo | AH | `?de=2026-11-17&ate=2026-11-17` | só e1 |
| A-9 | Regra 3 | positivo | AH | `?acao=rodada.cancelar&autor=<pk de ADM2>` | "Nenhuma ação encontrada." |
| A-10 | Regra 3 | negativo | AH | `?acao=inexistente`; `?autor=<pk de C>`; `?autor=abc`; `?de=18/11/2026`; `?de=2026-11-19&ate=2026-11-18` | 200 em todos; a mensagem "Filtro inválido ignorado: <nome>." do filtro inválido; os outros filtros aplicados; as três linhas quando só havia o inválido |
| A-11 | Regra 3 | positivo | 120 entradas da mesma ação | `?acao=<ação>&pagina=2` | os links de paginação mantêm `acao` |
| A-12 | Regra 5 | negativo | AH | GET e comparar a contagem de `EntradaAuditoria` | a mesma contagem |
| A-13 | Regra 1 | negativo | AH | POST; GET como C e como a conta de um fornecedor; GET anônimo | 405; 403; 403; o fluxo de login |
| A-14 | Regra 6 | positivo | — | GET `/administracao/` | o link "Histórico de ações" para `/administracao/historico/` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-14 | `tests/tecnicos/test_historico_de_acoes.py` |
