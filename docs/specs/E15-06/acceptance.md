# E15-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo AH:**
  - o administrador ADM1, o comprador C e a conta de comprador ADM2 (nome "ADM2"), que só serve de autora de e3. Não há segundo administrador: o banco admite um único administrador, sempre ativo (especificação §1, "Há um único administrador"; `conta_administrador_unico` e `conta_administrador_ativo`);
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
| A-3 | Regra 2 | positivo | AH com e3 gravada com o id de uma conta que não existe | GET | "Conta <id>" no autor |
| A-4 | Regra 2 | positivo | 120 entradas | GET; `?pagina=3` | 50 na primeira página; 20 na terceira; `?pagina=99` dá a última, como `get_page` |
| A-5 | Regra 3 | positivo | AH | `?acao=rodada.cancelar` | só e2; a lista de ações com as três ações em ordem alfabética |
| A-6 | Regra 3 | positivo | AH | `?autor=sistema`; `?autor=<pk de ADM1>` | só e1; só e2; a lista de autores com "Sistema" e ADM1, sem C nem ADM2 |
| A-7 | Regra 3 | positivo | AH | `?de=2026-11-18&ate=2026-11-18` | só e2 (e1 é 17/11 em Brasília) |
| A-8 | Regra 3 | positivo | AH | `?de=2026-11-17&ate=2026-11-17` | só e1 |
| A-9 | Regra 3 | positivo | AH | `?acao=rodada.cancelar&autor=sistema` | "Nenhuma ação encontrada." |
| A-10 | Regra 3 | negativo | AH | `?acao=inexistente`; `?autor=<pk de C>`; `?autor=<pk de ADM2>` (comprador); `?autor=abc`; `?de=18/11/2026`; `?de=2026-11-19&ate=2026-11-18` | 200 em todos; a mensagem "Filtro inválido ignorado: <nome>." do filtro inválido; os outros filtros aplicados; as três linhas quando só havia o inválido |
| A-11 | Regra 3 | positivo | 120 entradas da mesma ação | `?acao=<ação>&pagina=2` | os links de paginação mantêm `acao` |
| A-12 | Regra 5 | negativo | AH | GET e comparar a contagem de `EntradaAuditoria` | a mesma contagem |
| A-13 | Regra 1 | negativo | AH | POST; GET como C e como a conta de um fornecedor; GET anônimo | 405; 403; 403; o fluxo de login |
| A-14 | Regra 6 | positivo | — | GET `/administracao/` | o link "Histórico de ações" para `/administracao/historico/` |
| A-15 | Regra 3-A (E15-R05) | negativo | AH | GET autenticado com `autor` igual a cada um destes: `²`, `١٢`, `+1`, `-1`, ` 1`, `0`, `01`, `1e3`, 19 dígitos `9` e 30 dígitos `9`; também `contexto_do_historico({"autor": "²"})` | 200 em todas; "Filtro inválido ignorado: autor."; as três linhas e1, e2 e e3; o serviço não levanta. **Red esperado:** `ValueError` com `²` |
| A-16 | Regra 3-A (E15-R05) | positivo | AH | `?ate=9999-12-31`; `?de=0001-01-01`; `?de=0001-01-01&ate=9999-12-31`; `?de=9999-12-31`; também `contexto_do_historico({"ate": "9999-12-31"})` | 200 em todas, sem aviso de filtro inválido; as três linhas nas três primeiras; "Nenhuma ação encontrada." na última; o serviço não levanta. **Red esperado:** `OverflowError` |
| A-17 | Regra 3-A (E15-R05) | negativo | AH | `de` ou `ate` iguais a `2026-11-18T00:00`, `20261118`, `2026-11-18 ` (espaço no fim), `２０２６-11-18` e `2026-02-30` | 200; "Filtro inválido ignorado: <de ou ate>."; as três linhas |
| A-18 | Regra 3-A (E15-R05) | positivo | 120 entradas | `?pagina=abc`; `?pagina=-1`; `?pagina=99999999999999999999999` | 200 em todas; a primeira página no primeiro caso e a última nos outros dois, como `get_page` |
| A-19 | Regra 3-A (residual de E15-R05) | negativo | AH | GET autenticado com `acao` igual a cada um destes: `acao%00invalida`, `rodada.cancelar%00`, `%00`, `rodada.cancelar%01`, 10.000 caracteres `a`, `rodada.cancelar` com um espaço no fim, `RODADA.CANCELAR`; também `contexto_do_historico({"acao": "acao\x00invalida"})` | 200 em todas; "Filtro inválido ignorado: acao."; as três linhas e1, e2 e e3; o serviço devolve `acao` entre os inválidos e não levanta. **Red esperado:** `DataError` (NUL) no serviço e 500 na rota |
| A-20 | Regra 3-A (residual de E15-R05) | negativo | AH | `?acao=rodada.cancelar&autor=1%00`; `?acao=rodada.cancelar&de=2026-11-18%00`; `?acao=rodada.cancelar&ate=2026-11-18%00`; `?acao=rodada.cancelar&pagina=1%00` | 200 em todas; o aviso do filtro com NUL (autor, de ou ate) e só e2 listada (`acao` aplicada); no último, sem aviso, só e2, na primeira página |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-20 | `tests/tecnicos/test_historico_de_acoes.py` |
