# E15-06 — Registro do implementador

Agente 2.

## Red

- Commit do Red: `uv run pytest tests/tecnicos/test_historico_de_acoes.py` → **17 falhas e 1 passando** (a rota não existe; o que passou é a guarda "a leitura não grava", A-12).

## Green

- `apps/operacao/historico.py` (consulta, filtros, paginação e o texto das linhas), a view `historico` em `apps/operacao/views.py` (`somente_administrador`, `require_GET`), a rota `historico_acoes`, o template `templates/administracao/historico.html` e o link "Histórico de ações" na navegação do painel.
- Resultado: `18 passed`; com o painel, `43 passed`.

## Desvios e pontos para o revisor

1. **ADM2 (especificação inviável).** Como nas E15-02 e E15-04, o banco admite um administrador só. ADM1 é o administrador; ADM2 é uma conta de comprador com esse nome, autora de e3. Por isso o A-9 usa `autor=sistema` para obter "Nenhuma ação encontrada." (a spec usa `autor=<ADM2>`, que aqui seria um filtro inválido, já que a regra 3 só aceita "sistema" ou administrador). O A-10 testa `autor=<comprador>` como inválido.
2. **Intervalo ao contrário** (`de` maior que `ate`): a mensagem é "Filtro inválido ignorado: de." e os dois filtros de data são ignorados, para o resultado ser as três linhas que o A-10 pede.
3. **Marcação própria.** Cada linha é `<tr class="entrada">` com a ação em `<td class="acao">`; os testes leem essa marcação. As alterações são uma linha "chave: valor" por chave, em JSON compacto, escapada pelo template.
4. **A-4:** o arranjo não conta as entradas de autenticação (a passkey não grava auditoria neste arranjo), e o teste lê o total do banco.

## Ajuste do especificador (commit e8c967a)

A-6 ganhou a conferência da lista de autores (só "Sistema" e ADM1) e A-10 o autor comprador chamado ADM2. Acrescentei as duas asserções e `test_autor_comprador_com_nome_de_administrador_e_invalido` (guardas: passaram de primeira, o código já filtrava por papel de administrador).


## Revisão independente — agente 3 — 2026-11-16

Referência auditada: `2f5958c`, branch `e15-especificacoes`, sobre `8b1739f` (E14). Foram lidos os documentos-base (funcional v1.7 e infraestrutura v1.8), as sete especificações e matrizes E15 e os registros Red/Green, antes da comparação com código e testes. Este parecer acrescenta-se ao registro do implementador, preservado integralmente. Evidências globais e código das reproduções estão em [E15-07/review.md](../E15-07/review.md).

**Veredito da fatia: REPROVADO.** A-1 a A-14 confrontados com listagem, paginação, filtros, autores, escape e acesso. Há uma lacuna nos limites de entrada dos filtros.

### R05 — importante — filtros conseguem interromper o histórico

- Requisito: spec.md, regra 3, e acceptance.md A-10: filtro inválido é ignorado com aviso e HTTP 200; datas válidas são inclusivas.
- Código: `apps/operacao/historico.py:58` usa `isdigit()` antes de `int()`; `:81` sempre soma um dia ao limite superior.
- Reproduções independentes: `contexto_do_historico({'autor': '\u00b2'})` (caractere ²) levanta `ValueError`; `contexto_do_historico({'ate': '9999-12-31'})` levanta `OverflowError`. A view chama esse serviço sem tratamento, interrompendo a resposta em vez da página prevista.
- No primeiro caso o autor deve ser ignorado e avisado; no segundo o limite superior válido deve ser tratado sem transbordamento. Cobrir as entradas na rota autenticada, inclusive outras representações numéricas fora da faixa aceita.

TDD: `e189ad7` antes de `32f2a33`; registro 17 falhas e uma guarda passando. O ajuste de autor que é comprador e a lista somente de administradores são coerentes com o documento-base e `e8c967a`. Não reexecutado Red histórico.

## Correção R05 (implementador, 2026-11-16)

- **Red observado** (`tests/tecnicos/test_historico_de_acoes.py`): 5 falhas: `ValueError` com `²` e `OverflowError` nos três limites do calendário e em `de=9999-12-31`. As demais entradas de A-15 a A-18 passaram de primeira (guardas).
- **Green:** `autor` só por `[1-9][0-9]{0,17}` ASCII; datas só por `[0-9]{4}-[0-9]{2}-[0-9]{2}` e data existente; limite de calendário que não pode ser representado (inclusive em UTC) não é aplicado, sem erro e sem aviso; `pagina` segue `get_page`.
