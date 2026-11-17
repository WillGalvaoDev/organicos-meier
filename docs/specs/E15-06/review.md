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


## Revalidação independente das correções — agente 3 — 2026-11-16

Código auditado: `f42e08d`, branch `e15-especificacoes`. Delta desde o parecer `2d909d6`: especificação `63285a5`, produção/testes `46e178b`, `812a91a`, `1dfb6e0` e integração/registro `f42e08d`. Os documentos-base e o parecer anterior continuam como referência; os novos requisitos foram lidos antes do delta de código. Registro anterior preservado integralmente. Resultados compartilhados em [E15-07/review.md](../E15-07/review.md).

**REPROVADO. R05 parcialmente corrigido; residual aberto (importante).** A-1 a A-18 e as duas reproduções originais passaram. O formato ASCII limitado para autor evita conversões inválidas/fora da faixa; as datas passam por validação de formato/calendário e tratamento dos limites. Paginação permanece compatível com `get_page`.

### R05 residual — filtro `acao` inválido ainda causa HTTP 500

- **Requisitos:** spec.md regra 3 (ação fora da lista deve ser ignorada com aviso e HTTP 200), regra 3-A (“Nenhum valor recebido nos filtros ou em pagina pode levantar exceção nem dar resposta diferente de 200”), acceptance A-10; AGENTS.md §§6 e 8.
- **Código:** `apps/operacao/historico.py:64` consulta `EntradaAuditoria.objects.filter(acao=acao).exists()` antes de validar se a entrada pode ser enviada ao PostgreSQL. A proteção acrescentada para autor/data não cobre este filtro.
- **Reprodução no serviço:** `contexto_do_historico({'acao': 'acao\x00invalida'})` levanta `django.db.utils.DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes`.
- **Reprodução HTTP independente:** administrador autenticado por passkey, `GET /administracao/historico/?acao=acao%00invalida`: resposta **500**, esperado **200** com “Filtro inválido ignorado: acao.” e a listagem sem esse filtro.
- **Resultado:** dois testes adicionais falharam pelos sintomas acima (`2 failed, 6 deselected in 5.08s`); as seis provas antigas continuam verdes. Não é falha de preparação nem mudança presumida de regra: é o comportamento já exigido para ação inválida.
- **Correção necessária:** reconhecer a entrada inválida antes da consulta e reaproveitar o tratamento normal do filtro ignorado; manter a consulta/paginação dos demais filtros. Acrescentar regressão no serviço e na rota autenticada. Não alterar a especificação para aceitar resposta 500.

TDD das correções entregues: testes e produção em `1dfb6e0`, com Red observado registrado pelo implementador. Reexecução independente dos testes atuais sobre o código anterior reproduziu cinco falhas (autor ² e quatro casos de calendário), que ficam verdes no código atual. Essa evidência encerra as reproduções originais, mas não o residual acima.

Código das duas provas adicionais (arquivo temporário `tests/tecnicos/test_alertas_de_revisor_e15.py`, removido após a execução):

```python
import pytest
from tests.apoio.operacao import INSTANTE

pytestmark = pytest.mark.django_db(
    transaction=True, databases=['default', 'simulador_pagamentos']
)

def test_filtro_acao_malformado_e_ignorado():
    from apps.operacao.historico import contexto_do_historico
    resultado = contexto_do_historico({'acao': 'acao\x00invalida'})
    assert resultado['invalidos'] == ['acao']

def test_filtro_acao_malformado_na_rota(client, relogio, webauthn):
    from tests.apoio.admin_fluxos import administrador_logado
    relogio.congelar(INSTANTE)
    administrador_logado(client)
    client.raise_request_exception = False
    resposta = client.get('/administracao/historico/?acao=acao%00invalida')
    assert resposta.status_code == 200
    assert 'Filtro inválido ignorado: acao.' in resposta.content.decode()
```

## Residual de R05: filtro `acao` com NUL (implementador, 2026-11-17)

- **Red observado** (`uv run pytest tests/tecnicos/test_historico_de_acoes.py`): 3 falhas, `DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes`, nos casos A-19 com NUL (`acao\x00invalida`, `rodada.cancelar\x00`, `\x00`). Os demais valores do A-19 (controle `\x01`, 10.000 caracteres, espaço no fim, caixa diferente) e o A-20 inteiro passaram de primeira (guardas: o banco os aceitava como texto sem correspondência).
- **Green:** `_filtrar` recebe a lista de ações distintas já carregada para o seletor e valida `acao` por igualdade em memória (`acao in acoes`); o valor recebido não entra em consulta antes de validado. A lista é lida uma vez por requisição e serve também ao seletor.
- **Ordem do trabalho:** escrevi o Green antes de rodar o Red; desfiz a mudança (só `apps/operacao/historico.py`), observei o Red acima e reapliquei. O Red foi observado antes do Green no código final.
- **Ambiente:** o Docker Desktop estava parado ao retomar a sessão; subi o Docker e o container `om-db-1`, sem alterar dados.
- **Verificação:** suíte completa **3449 passed**; `ruff`, `mypy` (527 arquivos) limpos. Sem push, PR nem merge.
