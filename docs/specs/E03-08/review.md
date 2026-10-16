# E03-08 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `2e7bbcc` (2026-10-16). E03 global: **REPROVADO**. Histórico preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** `consultas.py` com corpos triviais (`[]`), views
vazias com a política `exige_comprador`, rotas `catalogo_lista` e `catalogo_fornecedor`. Suíte
antes do Red: 1037 passando.

**Red** (`uv run pytest tests/tecnicos/test_catalogo_comprador.py tests/tecnicos/test_catalogo_permissoes.py`):
**18 falhas, 6 passando**. Falhas por asserção sobre o conteúdo (`assert 'Banana' in ''`,
`assert 'Produto indisponível' in ''`, listas e 404 que o andaime não produz, teto de consultas e
link de `/inicio/`). As 6 que passavam são guardas: a política `comprador` já declarada pelo
andaime, o comprador suspenso com 200 (o andaime já responde 200), e os testes de 403/login dos
produtos e do catálogo.

**Green:** `consultas.py` (`fornecedores_no_catalogo`, `rodada_ativa_do_catalogo`,
`produtos_da_rodada`, `produtos_do_catalogo`, estoque livre em lote), filtro `reais`, views,
templates `catalogo/comprador_lista.html` e `comprador_fornecedor.html`, link em `/inicio/`.
Resultado: arquivos da fatia 24 passando; suíte completa **1058 passando**; `ruff check`,
`ruff format`, `mypy --strict`, `makemigrations --check` limpos.

**Refactor (suíte verde):** a fórmula do estoque livre virou `calcular_livre(limite, reservado)`
em `rodadas/estoque.py` (usada por `estoque_livre` e pelo catálogo) e as situações que reservam
viraram a constante pública `SITUACOES_QUE_RESERVAM` em `interesses/consultas.py`.

**Ajustes de teste durante o Green (erros do teste, não do código):** o teste de administrador no
catálogo criava um segundo administrador (há um só, por restrição do banco); passou a autenticar o
administrador antes de criar a rodada. Linhas longas quebradas para o lint.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_catalogo_comprador.py::test_banana_mostra_preco_incremento_e_disponivel` |
| A-2 | `::test_maca_mostra_multiplo_e_sem_limite` |
| A-3 | `::test_estoque_zero_e_tudo_reservado_aparecem_como_esgotado` |
| A-4 (D-1) | `::test_produto_fora_da_rodada_nao_aparece_e_indisponivel_traz_a_marcacao` |
| A-5 | `::test_lista_de_fornecedores_com_rodada_e_produto` |
| A-6 | `::test_fornecedor_sem_rodada_ativa_ou_inexistente_da_404_igual` |
| A-7 | `test_catalogo_permissoes.py::test_comprador_suspenso_consulta_o_catalogo` |
| A-8 | `::test_fornecedor_e_administrador_nao_consultam_o_catalogo`, `::test_visitante_anonimo_vai_para_o_login_no_catalogo` |
| A-9 | `test_catalogo_comprador.py::test_campos_internos_e_dados_de_compradores_nao_aparecem` |
| A-10 | `::test_numero_de_consultas_nao_cresce_com_os_produtos` (1 e 20 produtos, teto de 8) |
| A-11 | `::test_rodada_sem_produto_mostra_a_mensagem` |
| A-12 | `::test_as_duas_rotas_declaram_a_politica_de_comprador` e a varredura `test_permissoes_politica_rotas.py` |
| A-13 (D-1) | `::test_marcacao_some_quando_o_produto_volta_a_ficar_disponivel` |

Extras: ordenação por nome, etapas fora de interesse, formato `R$ 1.234,56`, link em `/inicio/`.

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- O fornecedor aparece em `/catalogo/` quando tem rodada em qualquer etapa ativa com ao menos
  um estoque (`EXISTS`); rodadas `disponivel_para_retirada` e `cancelada` não entram.
- Sem rodada ativa e id inexistente levantam `Http404` pelo mesmo caminho, então o corpo é
  idêntico.
- A página não mostra o total reservado nem pendências: só o estoque livre.
- Teto de 8 consultas na página do fornecedor (sessão, usuário, rodada com fornecedor, estoques com
  produtos e uma agregação das reservas); medido igual com 1 e com 20 produtos.
- A unidade exibida usa o rótulo do modelo (`unidade`, `pacote`, `caixa`, `kg`, `L`), e a
  disponibilidade fica "`<quantidade> <unidade> disponível`" (por exemplo, "4 kg disponível").

## Limitações de verificação

- Adicionar interesse, carrinho, progresso e caixas são da E05 e entram nestas telas.
- O catálogo mostra o estoque livre calculado por `total_reservado` sem filtro por rodada (a parcela
  ainda não tem vínculo com a rodada; a E05 ajusta sem mudar a assinatura).
- Telas verificadas pelo cliente de teste do Django, não por navegador.

## Revisão independente — 0ceb171 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

A-1 a A-13: catálogo por rodada ativa, indisponibilidade informativa, valores, estoque livre, ordenação, privacidade, permissões e teto de oito consultas com 1/20 produtos cobertos e verdes. Sem achado impeditivo próprio desta fatia. O parecer global abaixo considera as demais fatias.

Verificação comum: `uv run pytest -q` — **1058 passed em 147,85 s**; ruff check limpo; ruff format — 238 arquivos; mypy — 193 arquivos sem erros; checks Django e migrações sem pendências. Os probes adicionais de fronteira terminaram em **8 failed, 8 passed em 4,36 s**, reproduzindo E03-R01. Não houve correção de produção ou testes pelo revisor.

Comandos completos, achados, reprodução, limites e parecer global estão em [E03-08/review.md](../E03-08/review.md), na seção de revisão independente deste SHA. Os relatos Red/Green anteriores foram conferidos com o diff e a cobertura; a execução Green é independente, a cronologia Red é evidência documentada pelo implementador.

### Parecer global e escopo

**E03: REPROVADO** sobre `0ceb1715e94af26a7af79e3881117a3b7a133263` (main, PR #45). O achado importante E03-R01 precisa ser corrigido e revalidado antes do encerramento. E03-R02 é melhoria documental, sem decisão comercial pendente. Não foi identificado bloqueador de integridade nas corridas e invariantes verificadas; a reprovação decorre do tratamento incompleto de entradas inválidas nas operações administrativas.

Fontes lidas antes da análise do código: especificação funcional v1.6 (§§2, 4, 5.1, 9, 13, 14 e cenários citados nas fatias), infraestrutura v1.7 (4.10, 4.12, 5 e testes técnicos), e os oito pares spec/acceptance. A decisão D-1 sobre disponibilidade foi respeitada: sinalização informativa, sem excluir o produto do catálogo. Não houve alteração dos documentos-base neste diff.

| Fatia | Matriz | Decisão |
|---|---|---|
| E03-01 | A-1 a A-17 verdes; fronteira superior adicional falha | REPROVADO — R01 |
| E03-02 | A-1 a A-18 verdes; fronteira superior adicional falha | REPROVADO — R01 |
| E03-03 | A-1 a A-23 verdes; fronteira superior adicional falha | REPROVADO — R01 |
| E03-04 | A-1 a A-11 verdes | APROVADO |
| E03-05 | A-1 a A-19 verdes; fronteira superior adicional falha | REPROVADO — R01 |
| E03-06 | A-1 a A-13 verdes com ajuste de pré-condição do A-3; fronteira superior adicional falha | REPROVADO — R01; R02 documental |
| E03-07 | A-1 a A-11 verdes, incluindo matriz consolidada | APROVADO |
| E03-08 | A-1 a A-13 verdes | APROVADO |

### E03-R01 — importante: entrada acima da capacidade decimal provoca HTTP 500

**Referências:** infraestrutura 4.12 (`NUMERIC(12,2)` e `NUMERIC(12,3)`); E03-01, entrada de valores e contrato de `ValidationError` por campo; E03-03, validações e erros de formulário; E03-05, validação do limite; E03-06, `IncrementoInvalido` exibido no formulário; AGENTS §§3 e 8, negativos e casos-limite. É uma consequência técnica das faixas de persistência já aprovadas, sem necessidade de definir um novo teto comercial.

**Locais:** `apps/fornecedores/servicos.py:43` (`_minimo`), `apps/catalogo/servicos.py:53` (`_preco`), `apps/catalogo/quantidades.py:35` e `:45` (incremento/múltiplo), `apps/rodadas/estoque.py:37` (`_limite`), e `apps/catalogo/forms.py:22`. As conversões verificam formato, casas e sinal, mas não a quantidade máxima de dígitos da coluna. `objects.create()`/`save()` não executam os validadores de campo automaticamente. A entrada alcança o Postgres e a `DataError` não é convertida em erro de validação.

**Reprodução independente:** administrador autenticado por passkey pelo fluxo real, criptografia simulada conforme E02; POST real, PostgreSQL real, sem substituir serviço ou resultado. `10000000000.00` em mínimo/preço e `1000000000.000` em quantidade geraram `numeric field overflow` e HTTP **500** em oito caminhos:

1. cadastro de fornecedor;
2. alteração de mínimo;
3. edição de preço;
4. cadastro de produto com incremento;
5. alteração de incremento;
6. alteração de múltiplo;
7. inclusão no estoque;
8. alteração de estoque.

Controles dentro da faixa responderam 302 nos oito caminhos: `9999999999.99` para dinheiro, `999999999.999` para quantidade e `999999999.000` para o múltiplo do produto com incremento 1. Resultado: **8 failed, 8 passed em 4,36 s**. As oito falhas são manifestações de um único defeito. O banco recusa o excesso; não se afirma corrupção de dados nem bypass de autorização.

**Devolução ao implementador:** validar a capacidade do campo antes da escrita, também em chamadas diretas aos serviços, e apresentar o erro no campo correspondente (ou no formulário de estoque), conservando o valor anterior, sem auditoria/sinal de sucesso. Não arredondar, truncar ou limitar silenciosamente a entrada. Cobrir limite exato e primeiro valor que não cabe para dinheiro e quantidade, cadastro e edição, com Red → Green. A solução pode compartilhar validação, mas deve respeitar o contrato das funções numéricas existentes e não alterar o arredondamento de subtotais.

### E03-R02 — melhoria documental: pré-condição de A-3 não isola a incompatibilidade do múltiplo

`docs/specs/E03-06/acceptance.md`, A-3, manda retirar apenas a parcela de 1,5 do cenário A-1 e espera código `multiplo` para incremento 2. Ainda resta reserva de 1,0, que não é múltipla de 2. A infraestrutura 4.12 exige testar quantidades antes do múltiplo; portanto, o resultado correto nesse cenário é `quantidade`.

O implementador registrou isso e testou o cenário completo como `quantidade`, além de um cenário isolado com somente a pendência de 2,0 para obter `multiplo`. Essa interpretação é derivável da fonte de maior precedência e está correta. Devolução ao especificador: corrigir a pré-condição de A-3 e a frase correspondente em Casos-limite da spec; não inverter a ordem de validação. Não é bloqueio por decisão nem defeito de produção.

### Comandos e resultados independentes

- `uv run pytest -q`: **1058 passed em 147,85 s**, E01/E02/E03, banco Postgres real. Nenhum outro pytest foi executado simultaneamente no mesmo banco.
- `uv run pytest -q -c pyproject.toml $env:TEMP/om_e03_0ceb171_probes.py --tb=short --show-capture=no`: **8 failed, 8 passed em 4,36 s**, descritos em R01; script integral abaixo.
- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 238 arquivos já formatados.
- `uv run mypy .`: sem erros em 193 arquivos.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: No changes detected.
- `uv run python manage.py check --settings=config.settings.test`: zero issues.
- `uv sync --locked`: 51 pacotes resolvidos, 50 conferidos.
- CI do SHA exato: [run 38948417927](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38948417927), completed/success, consultado por `gh run list --commit 0ceb1715e94af26a7af79e3881117a3b7a133263 --json databaseId,status,conclusion,url`.

### Evidência TDD e limites

Conferidos os registros Red, Green e Refactor das oito fatias, incluindo comandos, contagens, exemplos de falhas, andaimes justificados e ajustes de testes. As restrições, gatilhos, serviços e testes correspondem aos comportamentos descritos. O diff dos testes anteriores adiciona cobertura; não foi identificada remoção para esconder defeito. O ajuste de E03-06 A-3 está explicado em R02.

A sequência temporal Red antes de produção é documentada pelo implementador, não foi presenciada nem reconstruída pelo revisor em commits intermediários. O Green e os probes deste parecer foram executados independentemente. Falhas de andaime por objeto não persistido/ausência de sequência não foram apresentadas como asserções finais de negócio; a matriz consolidada é regressão de comportamentos implementados nas fatias anteriores.

As telas foram verificadas pelo cliente HTTP Django e inspeção dos templates, sem navegador. WebAuthn usa o dublê autorizado. A adição/reserva/alocação real de interesses e o recálculo por preço são E05; fechamento/retorno reais são E06; congelamento de pedidos é E08. Os auxiliares transacionais testam os contratos atuais, sem afirmar entrega dessas etapas futuras. O vínculo de parcelas com rodada é uma dependência futura expressa; não foi tratado como omissão nova.

As esperas de concorrência observam `pg_stat_activity` no banco de teste inteiro. A suíte foi executada isoladamente; para execução paralela futura, restringir a observação à conexão da operação tornaria a instrumentação mais robusta. Isso não gerou falha observada nesta revisão.

Alterações do revisor: somente os oito `review.md`, preservando os registros anteriores. Próximo gate: correção de R01 pelo implementador, com evidência TDD, seguida de revisão independente; ajuste documental R02 pelo especificador.

### Script reproduzível dos probes adicionais

Salvar como `$env:TEMP/om_e03_0ceb171_probes.py` e executar o comando acima a partir da raiz do projeto. `raise_request_exception=False` permite observar a resposta 500 real e a exceção capturada; não altera a aplicação.

```python
from decimal import Decimal as D
import pytest
from django.core.cache import cache
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.webauthn_falso import instalar
from tests.fabricas import FornecedorFactory, ProdutoFactory, RodadaFactory, EstoqueDaRodadaFactory


@pytest.mark.django_db
@pytest.mark.parametrize("excede", [False, True])
@pytest.mark.parametrize(
    "caso",
    [
        "fornecedor",
        "minimo",
        "preco",
        "cadastro_incremento",
        "incremento",
        "multiplo",
        "incluir_estoque",
        "alterar_estoque",
    ],
)
def test_entrada_acima_da_capacidade_vira_erro_de_campo(client, monkeypatch, caso, excede):
    cache.clear()
    instalar(monkeypatch)
    administrador_logado(client)
    f = FornecedorFactory.create()
    p = ProdutoFactory.create(fornecedor=f, incremento=D("1"), multiplo=None)
    r = RodadaFactory.create(fornecedor=f)
    e = EstoqueDaRodadaFactory.create(rodada=r, produto=p, limite=D("10"))
    q = ProdutoFactory.create(fornecedor=f)
    casos = {
        "fornecedor": (
            "/administracao/fornecedores/novo/",
            {
                "nome": "Teste",
                "email_pedido": "teste@example.com",
                "prazo_entrega_dias": "7",
                "minimo": "10000000000.00",
            },
        ),
        "minimo": (f"/administracao/fornecedores/{f.pk}/minimo/", {"minimo": "10000000000.00"}),
        "preco": (
            f"/administracao/produtos/{p.pk}/",
            {"nome": p.nome, "preco": "10000000000.00", "disponivel": "on"},
        ),
        "cadastro_incremento": (
            f"/administracao/fornecedores/{f.pk}/produtos/novo/",
            {
                "nome": "Teste",
                "unidade": "kg",
                "preco": "1.00",
                "incremento": "1000000000.000",
                "disponivel": "on",
            },
        ),
        "incremento": (
            f"/administracao/produtos/{p.pk}/incremento/",
            {"incremento": "1000000000.000"},
        ),
        "multiplo": (f"/administracao/produtos/{p.pk}/multiplo/", {"multiplo": "1000000000.000"}),
        "incluir_estoque": (
            f"/administracao/rodadas/{r.pk}/estoque/incluir/",
            {"produto": str(q.pk), "limite": "1000000000.000"},
        ),
        "alterar_estoque": (
            f"/administracao/estoque/{e.pk}/alterar/",
            {"limite": "1000000000.000"},
        ),
    }
    url, dados = casos[caso]
    if not excede:
        dados = {
            k: v.replace("10000000000.00", "9999999999.99").replace(
                "1000000000.000", "999999999.999"
            )
            for k, v in dados.items()
        }
        if caso == "multiplo":
            dados["multiplo"] = "999999999.000"
    client.raise_request_exception = False
    resposta = client.post(url, dados)
    assert resposta.status_code == (200 if excede else 302), (
        caso,
        resposta.status_code,
        resposta.exc_info[1] if resposta.exc_info else None,
    )
```


## Revalidação independente — 2e7bbcc — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

Aprovação própria mantida; catálogo inalterado e regressão verde. Parecer global abaixo considera as pendências das E03-02 e E03-05.

Evidência comum: suíte completa **1104 passed em 137,20 s**; script original independente **16 passed em 7,70 s**; probes complementares **6 failed em 2,23 s** (R03/R04); lint, formatação, tipos, migrações e checks Django sem erros. Detalhes, reprodução e limites no [parecer consolidado](../E03-08/review.md), seção deste SHA. Nenhuma alteração de produção ou testes versionados pelo revisor.

### Parecer global

**E03: REPROVADO** sobre `2e7bbcc8f37f8cbbdd8432844e3d47dfd7060b9e` (main, PR #46). **R01 encerrado**: os oito caminhos que geravam HTTP 500 agora recusam a capacidade excedida antes de persistir. **R02 encerrado**: os documentos agora distinguem corretamente incompatibilidade de quantidade e de múltiplo. Permanecem duas divergências reproduzíveis com as exigências da especificação revisada, R03 e R04 abaixo. Não foi observado bypass de congelamento nem corrupção dos dados persistidos.

A revisão comparou o diff desde `0ceb171`, leu as seções de correção e os critérios adicionais antes de verificar código/testes. As fontes-base permanecem funcional v1.6 e infraestrutura v1.7. As validações novas ficam nos serviços; não capturam `DataError`, não truncam nem modificam as primitivas aritméticas anteriores. Conferidos A-18 a A-20 de E03-01, A-19 de E03-02, A-24 a A-28 de E03-03, A-20/A-21 de E03-05 e A-3/A-14/A-15 de E03-06. Os critérios versionados passam, mas não cobrem as combinações a seguir.

### E03-R03 — importante: mínimo excedente em fase congelada retorna 200 e formulário editável

Referência exata: `docs/specs/E03-02/spec.md:180`, seção Correção E03-R01: “em qualquer etapa fora de interesse, a resposta continua sendo 409 com `CondicoesCongeladas`”. Isso é uma exigência expressa do documento corrigido; não se trata de novo limite comercial.

Local: `apps/fornecedores/servicos.py:167`, limpeza de `novo` antes de `travar_condicoes`; `apps/fornecedores/views.py:102`, tratamento do erro como validação comum. O excesso é recusado antes de verificar a fase, e o template volta a oferecer o formulário.

Reprodução: fornecedor com mínimo 150 e rodada em cada uma de `fechamento`, `fechamento_encerrado`, `pagamento`, `aguardando_fornecedor`; POST `/administracao/fornecedores/<id>/minimo/` com `minimo=10000000000.00`. **Nos quatro casos: 200, esperado 409.** O mínimo permanece 150, portanto não há escrita indevida; a falha é o contrato de fase/resposta e a apresentação de edição de condição congelada.

Devolução: garantir a precedência de fase prevista no documento, preservando a checagem transacional antes de qualquer escrita; testar fase congelada com entrada acima da capacidade, pela rota e pelo serviço, além do caso em interesse. Não remover a validação de capacidade para fazer esses testes passarem. Registrar Red → Green.

### E03-R04 — importante: estoque descarta o valor digitado após recusa

Referências: regra comum em `docs/specs/E03-01/spec.md:158`, Correção R01 (“o valor digitado de volta no formulário”), expressamente aplicada às demais fatias; E03-05, Correção R01, remete à regra comum e exige mensagem no formulário correspondente.

Locais: `apps/rodadas/views.py:39` (`_pagina_do_estoque`) e `templates/rodadas/estoque.html`. Na inclusão, o input de limite volta vazio; na alteração, volta ao limite persistido. O valor enviado não é transportado para o contexto/template. A mensagem de capacidade é mostrada, mas o usuário perde a entrada que deveria corrigir.

Reprodução: em interesse, POST de inclusão e de alteração com `limite=1000000000,000`. **200 e mensagem corretos nos dois; o input não contém o valor rejeitado** (inclusão sem value, alteração com valor anterior 10). Os testes novos A-20/A-21 verificam mensagem e persistência, mas não a preservação do formulário.

Devolução: renderizar o formulário submetido com seu valor e erro na linha do produto/estoque correspondente; conservar os valores das demais linhas e o estado persistido. Cobrir inclusão e alteração com entrada rejeitada, sem gravação/auditoria/sinal. Registrar Red → Green. Não é necessário alterar a regra comercial nem o esquema do banco.

### Execuções independentes

- `uv run pytest -q`: **1104 passed em 137,20 s**. E01/E02/E03, Postgres real, execução isolada.
- `uv run pytest -q -c pyproject.toml $env:TEMP/om_e03_0ceb171_probes.py --tb=short --show-capture=no`: **16 passed em 7,70 s**. Arquivo original do revisor, sem alterações: oito excessos com 200 e oito controles com 302.
- `uv run pytest -q -c pyproject.toml $env:TEMP/om_e03_2e7bbcc_complementares.py --tb=short --show-capture=no`: **6 failed em 2,23 s**. Quatro falhas por `200 != 409` em R03 e duas por perda da entrada em R04; não foram erros de infraestrutura.
- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 239 arquivos já formatados.
- `uv run mypy .`: sem erros em 194 arquivos.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: No changes detected.
- `uv run python manage.py check --settings=config.settings.test`: zero issues.
- `uv sync --locked`: 51 pacotes resolvidos, 50 conferidos.
- CI do SHA exato: [run 38952625937](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38952625937), completed/success, consultado com `gh run list --commit 2e7bbcc8f37f8cbbdd8432844e3d47dfd7060b9e --json databaseId,status,conclusion,url`.

### TDD e limites

Conferido o relato de Red (37 falhas/27 passando com andaimes), incluindo os oito overflows originais, e o Green do implementador, comparando os testes novos com o diff. A cronologia anterior ao código é documentada pelo implementador; não foi reconstruída pelo revisor. A suíte e os probes acima são execuções independentes. Não houve afrouxamento identificado das asserções originais.

Mantêm-se os limites da revisão anterior: cliente HTTP Django sem navegador; WebAuthn com dublê criptográfico autorizado; transições/reservas reais das etapas futuras não entregues aqui. Os novos probes usam rotas, templates, autenticação e banco reais, sem substituir os serviços auditados.

Alterações do revisor: somente oito `review.md`. Próximo gate: correção de R03/R04 e revalidação; as aprovações próprias de E03-01, 03, 04, 06, 07 e 08 ficam mantidas/atualizadas neste SHA. E03-02 e E03-05 permanecem reprovadas.

### Probes complementares reproduzíveis

Salvar como `$env:TEMP/om_e03_2e7bbcc_complementares.py` e executar o comando acima:

```python
from decimal import Decimal
import pytest
from django.core.cache import cache
from django.test import Client
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.webauthn_falso import instalar
from tests.fabricas import FornecedorFactory, RodadaFactory, ProdutoFactory, EstoqueDaRodadaFactory


@pytest.fixture
def admin(client, monkeypatch):
    cache.clear()
    instalar(monkeypatch)
    administrador_logado(client)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize(
    "etapa", ["fechamento", "fechamento_encerrado", "pagamento", "aguardando_fornecedor"]
)
def test_minimo_excedente_fora_de_interesse_responde_409(admin, etapa):
    f = FornecedorFactory.create(minimo=Decimal("150"))
    RodadaFactory.create(fornecedor=f, etapa=etapa)
    resposta = admin.post(
        f"/administracao/fornecedores/{f.pk}/minimo/", {"minimo": "10000000000.00"}
    )
    f.refresh_from_db()
    assert f.minimo == Decimal("150")
    assert resposta.status_code == 409


@pytest.mark.django_db
@pytest.mark.parametrize("incluir", [True, False])
def test_estoque_preserva_entrada_rejeitada(admin, incluir):
    r = RodadaFactory.create()
    p = ProdutoFactory.create(fornecedor=r.fornecedor)
    if incluir:
        url = f"/administracao/rodadas/{r.pk}/estoque/incluir/"
    else:
        e = EstoqueDaRodadaFactory.create(rodada=r, produto=p, limite=Decimal("10"))
        url = f"/administracao/estoque/{e.pk}/alterar/"
    resposta = admin.post(url, {"produto": str(p.pk), "limite": "1000000000,000"})
    assert resposta.status_code == 200
    assert "O valor máximo aceito é 999999999,999." in resposta.content.decode()
    assert 'value="1000000000,000"' in resposta.content.decode()
```
