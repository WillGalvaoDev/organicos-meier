# E02-10 — Revisão

Estado atual: **APROVADO** no commit `0178d62` (revalidação independente ao final). A E02 global está **APROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** `apps/contas/permissoes.py` com `Politica`, os decoradores e mixins como passagem direta (sem gravar política), `POLITICAS_DE_TERCEIROS` vazia, `rotas_sem_politica` devolvendo um marcador (para a varredura falhar até existir comportamento) e `politica_da_view` devolvendo `None`; `tests/apoio/views.py` (carrinho, pagamento, meus pedidos e painel do fornecedor, com contador de chamadas) e as quatro rotas `/teste/...` em `tests/apoio/urls.py`; `tests/apoio/urls_sem_politica.py` e `tests/apoio/estrategias.py`. Suíte antes do Red: `548 passed`.

**Red** (`uv run pytest` nos cinco arquivos de teste desta fatia, com o andaime):

```
31 failed, 15 passed
```

Falhas de asserção: `assert 200 == 403` (a rota de compra respondia a fornecedor, suspenso e administrador), `DID NOT RAISE PermissionDenied`, `AttributeError: 'WSGIRequest' object has no attribute 'fornecedor_vinculado'`, `DID NOT RAISE DatabaseError` (sem a trigger do papel), `assert ['(andaime)'] == []` e `assert None == Politica.X` na varredura. Os 15 que passaram são cobertura (por exemplo, a varredura estática de `email__iexact`, que já não encontra ocorrências).

**Green:** `permissoes.py` completo, `papel_imutavel.py` + migração `0005_papel_imutavel`, política declarada nas views existentes, `POLITICAS_DE_TERCEIROS` preenchida.

**Ajustes de teste durante o Green (código inalterado):** o teste de propriedade passou a capturar os callbacks de `on_commit` (o e-mail do link sai em `on_commit`); o teste do cenário 61 confere nome e papel em `/inicio/` e e-mail em `/perfil/` (a página inicial da E02-02 não mostra o e-mail); o teste do mixin de fornecedor ganhou a marca de banco.

**Refactor:** tipagem (`View = Callable[..., HttpResponseBase]`, porque a view de avatar devolve `FileResponse`) e ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 594 passed em 68 s
test_normalizacao_varredura.py (3 execuções seguidas, hypothesis) -> 10 passed em todas
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 120 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
manage.py check (test)                            -> 0 issues
```

## Matriz

| Critério | Teste |
|---|---|
| A-1, A-2 | `test_permissoes_papeis.py` (`tecnico`, T-25; GET/POST/PUT/PATCH/DELETE, com e sem `HX-Request`) |
| A-3, A-4, A-5, A-6, A-7 | `test_permissoes_papeis.py` |
| A-8 | `tests/aceitacao/test_cenario_61_contas_independentes.py` |
| A-9 | `test_fornecedor_sem_vinculo_e_recusado_em_profundidade` |
| A-10, A-11 | `test_permissoes_politica_rotas.py` (varredura de `config.urls` e `tests.apoio.urls`; URLconf com rota esquecida) |
| A-12, A-13 | `tests/aceitacao/test_cenario_62_papel_imutavel.py` |
| A-14, A-15, A-16 | `test_normalizacao_varredura.py` (`tecnico`, T-37) |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Política gravada na view:** cada decorador (`publica`, `exige_login`, `exige_comprador`, `exige_comprador_ativo`, `exige_fornecedor`) embrulha a view e grava `politica_de_acesso`; `somente_administrador` e `exige_reautenticacao_por_passkey` (E02-03) passaram a gravar `Politica.ADMINISTRADOR`. Nos mixins, `as_view()` grava o atributo na view resultante (inclusive no `SomenteAdministradorMixin`).
- **Recusas:** anônimo é redirecionado para `/entrar/` (com `next`); papel ou situação errados levantam `PermissionDenied` (403 sem dados da rota), antes da view e para qualquer método. `exige_fornecedor` exige `fornecedor_id` preenchido e expõe `request.fornecedor_vinculado`.
- **`POLITICAS_DE_TERCEIROS`** lista rota por rota (sem curingas): `account_login`, `account_logout`, `account_reauthenticate`, as quatro de recuperação, as rotas `mfa_*` usadas e `google_login`/`google_callback`. A entrada `mfa_remove_webauthn` cobre a rota original do allauth, que fica atrás da nossa `remover_passkey` (mesmo nome, já declarada).
- **Varredura:** percorre o `URLResolver` recursivamente (`get_resolver(urlconf)`), é exposta como `rotas_sem_politica(urlconf)` e usada pelo teste com `config.urls` e `tests.apoio.urls`; uma rota sem política aparece como `caminho (nome)`. `entradas_de_terceiros_inexistentes` acusa nomes que não existem.
- **Rotas de teste fora de `config/urls.py`:** ficam em `tests/apoio/urls.py` (usadas com `pytest.mark.urls`), com as views em `tests/apoio/views.py`.
- **Trigger de imutabilidade do papel:** `BEFORE UPDATE OF papel ... WHEN (OLD.papel IS DISTINCT FROM NEW.papel)`. O `WHEN` é necessário porque o `save()` do Django reenvia a coluna `papel` com o mesmo valor; sem ele toda gravação comum falharia. O teste `test_atualizacao_sem_mudar_o_papel_continua_permitida` cobre isso, e o ORM (`update(papel=...)`) também é recusado.
- **T-37, propriedade:** cada exemplo roda dentro de uma transação desfeita ao final (`transaction.set_rollback(True)`), com e-mails gerados por `hypothesis` (`tests/apoio/estrategias.py`). Cobre unicidade da conta, emissão de convite (uso e banimento), consumo de convite (e-mail em uso e banido), login por senha, pedido de link, recuperação de acesso, Google e `email_banido`, e verifica que o alias com `+` continua sendo outro endereço em todos.
- **T-37, estática:** `analisar_codigo` usa o AST de cada arquivo de `apps/` (exceto migrações) e acusa `*email*__iexact` (argumento nomeado ou texto) e `.lower()`/`.casefold()` sobre expressões que mencionam e-mail fora de `apps/contas/emails.py`. O teste A-16 prova que ela acusa um arquivo temporário com `email_normalizado__iexact`.

## Revisão manual do terceiro item do T-37 (consultas por `email_normalizado`)

Item que o spec reserva à revisão porque a análise estática completa não é viável. Levantamento feito com `grep -rn "email_normalizado=" apps` (migrações excluídas) em 2026-10-16:

| Local | Valor usado na consulta | Veredito |
|---|---|---|
| `adaptadores.py:169` (Google) | `email` vindo de `_email_verificado`, que chama `normalizar_email` | normalizado |
| `convites.py:97` e `:107` (emissão) | `normalizado = normalizar_email(email)` | normalizado |
| `convites.py:140` e `:176` (consumo) | `convite.email_normalizado`, gravado já normalizado (`Convite.save` + `CHECK`) | normalizado |
| `emails.py:38` (`email_banido`) | `normalizar_email(texto)` | normalizado |
| `link_de_acesso.py:50` (pedido) | `normalizado = normalizar_email(email)` | normalizado |
| `criar_administrador.py:31`, `:36` | `email = normalizar_email(...)` | normalizado |
| `models.py:133` (`Conta.save`) | `self.email_normalizado` depois de `normalizar_email` | normalizado |
| `moderacao.py:82`, `:84` (remoção) | `travada.email_normalizado` (lido do banco; `CHECK` de normalização) | normalizado |
| `forms.py:37` | monta uma `Conta` em memória, sem consulta | n/a |

Nenhuma consulta com valor não normalizado foi encontrada.

## Limitações

- Nenhuma revisão independente feita ainda.
- As rotas reais de carrinho, pagamento e fornecedor chegam nas etapas E05, E08 e E13; os decoradores estão provados nas rotas de teste. O isolamento de dados entre fornecedores dentro das consultas fica com essas etapas (spec).


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

### Matriz da fatia

A-1 a A-16: decoradores/mixins, GET/POST/PUT/PATCH/DELETE e HX-Request, papéis, registro de políticas, varredura negativa, trigger de papel imutável e normalização por propriedade/AST cobertos. Rotas reais de negócio e isolamento das consultas futuras continuam fora do escopo aprovado.

### Verificação independente comum

SHA auditado: `8f4dc36e91833ad11e327bcfb99e34fa81ba6eb8`, main/PR #32. Documentos de referência: especificação funcional v1.6 (§§2, 3 e 15), infraestrutura v1.7 (§§2, 4.11 e 5), spec e acceptance de cada fatia. Nenhuma mudança de regra de negócio foi presumida.

- `uv run pytest -q`: **594 passed em 75,74 s**, banco Postgres real, incluindo E01 e todas as fatias E02.
- `uv run ruff check .`: limpo; `uv run ruff format --check .`: 156 arquivos.
- `uv run mypy .`: 120 arquivos, sem erros.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: sem mudanças.
- `uv run python manage.py check --settings=config.settings.test`: zero issues.
- `uv sync --locked`: lock resolvido (51 pacotes), ambiente conferido (50 pacotes).
- CI do SHA exato: [run 38914653756](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38914653756), sucesso.

A suíte verde não basta para aprovar E02: os probes adicionais do revisor terminaram em **6 failed, 1 passed em 2,65 s**, reproduzindo quatro achados distintos. Script, comando e matriz global estão em `../E02-10/review.md`, seção de revisão independente. O probe de PNG/EXIF passou e não gerou achado.

### Evidência TDD e limites

Conferidos os relatos de andaime, Red por asserção/comportamento, Green e refatoração de cada fatia, comparados com o diff e os testes. As alterações autorizadas de testes anteriores estão identificadas: fábrica de conta na auditoria E01; regra temporária de login administrativo substituída pela E02-03. Ajustes de instrumentação relatados pelo implementador não foram tratados como prova de defeito em produção. Limitação: a cronologia dos ciclos é documentada pelo implementador, sem logs brutos/commits intermediários para comprovar independentemente cada passo. A execução Green acima é independente; não foi apresentada como prova retrospectiva de toda a sequência TDD.

WebAuthn usa o dublê criptográfico expressamente previsto, com views, sessão e Authenticator reais. Google usa o fluxo real do allauth com resposta simulada, sem chamada ao provedor. Cerimônia física de passkey, OAuth/credenciais reais, SES, R2 e efeitos futuros sobre pedidos/interesses não foram validados nesta etapa; permanecem nos gates previstos pelos documentos. D-1 da E02-08 (suspensão de fornecedor) não foi implementado nem reaberto.

Nenhum achado próprio impede o aceite desta fatia no escopo entregue. A aprovação da E02 completa depende da correção dos achados E02-R01 a E02-R04.

### T-37: conferência independente das consultas

`rg -n 'email_normalizado=' apps --glob '!**/migrations/**'` conferido com os chamadores: emissão, pedido de link, comando administrativo, normalização e Conta.save normalizam antes de consultar; Google recebe o resultado normalizado de `_email_verificado`; consumo/moderação consultam por valores persistidos e protegidos pelos CHECKs. As atribuições em Forms e na criação da Conta não são novas consultas por entrada crua. Não foi encontrada comparação de entrada externa sem normalização. Os testes de propriedade e AST passaram; a análise manual não foi substituída pelo AST.

### Decisão global E02

**REPROVADA no commit `8f4dc36e91833ad11e327bcfb99e34fa81ba6eb8`.**

| Fatia | Critérios versionados na suíte | Decisão integrada |
|---|---|---|
| E02-01 | A-1 a A-20 verdes | APROVADO |
| E02-02 | A-1 a A-21 verdes, A-8 substituído por E02-03/A-14 | REPROVADO: E02-R04 |
| E02-03 | A-1 a A-15 verdes | REPROVADO: E02-R02 |
| E02-04 | A-1 a A-19 verdes | APROVADO |
| E02-05 | A-1 a A-18 verdes | REPROVADO: integração E02-R04 |
| E02-06 | A-1 a A-17 verdes | APROVADO |
| E02-07 | A-1 a A-17 verdes | REPROVADO: E02-R03 |
| E02-08 | A-1 a A-19 verdes | REPROVADO: integração E02-R01 |
| E02-09 | A-1 a A-19 verdes | REPROVADO: E02-R01 |
| E02-10 | A-1 a A-16 verdes | APROVADO no escopo dos decoradores/varreduras |

| Achado | Classificação | Evidência |
|---|---|---|
| E02-R01 | Bloqueador | Perfil sobrescreve suspensão, remoção e senha atualizadas depois de sua leitura. Três probes falham; causa em `perfil.py:124`. |
| E02-R02 | Importante | Duas exclusões concorrentes deixam zero passkeys fora do comando de recuperação. |
| E02-R03 | Importante | Payload Google `verified_email=true` aceito no retorno é recusado na conclusão. |
| E02-R04 | Importante | Validador de similaridade usa atributos ausentes no modelo e aceita senha igual ao nome. |

Os testes existentes não cobrem essas intercalações/variantes, por isso seus 594 resultados verdes não encerram a entrega. Próximo gate: implementador incorporar regressões antes das correções, registrar Red → Green e retornar para revisão independente. Não é necessária decisão comercial do usuário. A aprovação histórica da E01 não foi alterada.

### Probes independentes reproduzíveis

Comando PowerShell: `uv run pytest -c pyproject.toml "$env:TEMP/om_e02_8f4dc36_probes.py" -q --tb=short`.

Resultado final: **6 failed, 1 passed em 2,65 s**. Uma primeira execução, antes do probe de similaridade, produziu 5 failed/1 passed em 3,07 s. São seis asserções falhas para quatro achados; o teste de PNG/EXIF é a confirmação adicional que passou. O script abaixo permite reconstruir o arquivo temporário sem depender de o TEMP desta máquina ser preservado. Nenhum teste versionado nem código de produção foi editado pelo revisor.

```python
import json
import threading
from io import BytesIO
import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image
from allauth.mfa.models import Authenticator
from apps.contas import views
from apps.contas.models import Conta, Convite
from apps.contas.moderacao import suspender, remover
from apps.contas.perfil import processar_avatar
from apps.contas.adaptadores import AdaptadorMFA
from tests.fabricas import ContaFactory, ConviteFactory
from tests.apoio import imagens
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.webauthn_falso import instalar
from tests.apoio.admin_fluxos import (
    administrador_com_passkey,
    entrar_com_passkey_direta,
    cadastrar_passkey,
)


@pytest.fixture(autouse=True)
def limpar_cache():
    cache.clear()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("acao", ["suspender", "remover", "senha"])
def test_perfil_preserva_alteracao_concorrente(client, monkeypatch, acao):
    admin = ContaFactory.create(administrador=True)
    conta = ContaFactory.create()
    conta.set_password("senha-antiga-forte-9271!")
    conta.save()
    client.force_login(conta)
    original = views.atualizar_perfil

    def intercalar(lida, **kwargs):
        atual = Conta.objects.get(pk=lida.pk)
        if acao == "suspender":
            suspender(admin, atual)
        elif acao == "remover":
            remover(admin, atual)
        else:
            atual.set_password("senha-nova-forte-9262!")
            atual.save(update_fields=["password"])
        return original(lida, **kwargs)

    monkeypatch.setattr(views, "atualizar_perfil", intercalar)
    resposta = client.post("/perfil/", {"nome": "Nome editado"})
    assert resposta.status_code == 302
    conta.refresh_from_db()
    if acao == "senha":
        assert conta.check_password("senha-nova-forte-9262!")
    else:
        assert conta.situacao == {"suspender": "suspensa", "remover": "removida"}[acao]


def test_png_regravado_remove_exif_gps():
    with Image.open(BytesIO(imagens.jpeg_com_gps())) as origem:
        buf = BytesIO()
        origem.save(buf, format="PNG", exif=origem.getexif())
    with Image.open(BytesIO(buf.getvalue())) as origem_png:
        assert 0x8825 in origem_png.getexif()
    resultado = processar_avatar(SimpleUploadedFile("gps.png", buf.getvalue()))
    with Image.open(BytesIO(resultado.read())) as final:
        assert len(final.getexif()) == 0, dict(final.getexif())


@pytest.mark.django_db
@pytest.mark.urls("tests.apoio.urls")
def test_google_userinfo_verificado_conclui_cadastro(client):
    token = "token-revisor-google"
    ConviteFactory.create(email_normalizado="google@x.com", token_hash=Convite.hash_do_token(token))
    assert client.post(f"/convite/{token}/google/").status_code == 302
    dados = {
        "id": "google-revisor",
        "email": "google@x.com",
        "verified_email": True,
        "name": "Google",
    }
    retorno = client.post("/teste/retorno-google/", {"extra_data": json.dumps(dados)})
    assert retorno.status_code == 302
    assert retorno["Location"] == "/entrar/google/concluir/"
    resposta = client.post("/entrar/google/concluir/", {"nome": "Google"})
    assert resposta["Location"] == "/inicio/"
    assert Conta.objects.filter(email_normalizado="google@x.com").exists()


@pytest.mark.django_db(transaction=True)
def test_duas_remocoes_preservam_ultima_passkey(monkeypatch):
    instalar(monkeypatch)
    primeiro = Client()
    conta, chave = administrador_com_passkey(primeiro)
    entrar_com_passkey_direta(primeiro, chave, conta)
    cadastrar_passkey(primeiro, nome="Segunda")
    segundo = Client()
    entrar_com_passkey_direta(segundo, chave, conta)
    ids = list(Authenticator.objects.filter(user=conta).values_list("pk", flat=True))
    assert len(ids) == 2
    sincronizar = threading.Barrier(2)
    original = AdaptadorMFA.can_delete_authenticator

    def checar_e_esperar(self, autenticador):
        permitido = original(self, autenticador)
        sincronizar.wait(timeout=5)
        return permitido

    monkeypatch.setattr(AdaptadorMFA, "can_delete_authenticator", checar_e_esperar)

    def apagar(cliente, pk):
        return lambda b: cliente.post(f"/seguranca/webauthn/keys/{pk}/remove/").status_code

    try:
        resultados = executar_em_paralelo(apagar(primeiro, ids[0]), apagar(segundo, ids[1]))
        assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
        assert Authenticator.objects.filter(user=conta).count() >= 1
    finally:
        sincronizar.abort()


@pytest.mark.django_db
def test_cadastro_recusa_senha_igual_ao_nome(client):
    token = "token-revisor-similaridade"
    convite = ConviteFactory.create(token_hash=Convite.hash_do_token(token))
    senha = "NomeCompletoExclusivo9271"
    resposta = client.post(
        f"/convite/{token}/", {"nome": senha, "senha": senha, "confirmacao": senha}
    )
    assert resposta.status_code == 200
    assert not Conta.objects.filter(email_normalizado=convite.email_normalizado).exists()
```

Foram alterados apenas os dez `docs/specs/E02-*/review.md`, na branch `revisao/e02-8f4dc36`, sem commit, push ou merge. Os achados detalhados estão nos relatórios E02-09 (R01), E02-03 (R02), E02-07 (R03) e E02-02 (R04).


## Revalidação independente — 0178d62 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

Aprovação anterior mantida; implementação e critérios desta fatia inalterados. Suíte completa confirma regressão das políticas e invariantes. Parecer consolidado abaixo.

Evidências comuns: `uv run pytest -q` — **634 passed em 70,20 s**; probes independentes — **7 passed em 2,20 s**; lint, formatação, tipos e checks Django sem erros. Comandos, encerramento dos quatro achados, evidência TDD e limites em [E02-10/review.md](../E02-10/review.md), seção de revalidação do commit `0178d62`. Os pareceres anteriores acima são históricos.

### Parecer consolidado

**E02: APROVADO** sobre `0178d6214779504ef55abb183c4e8e5b5dfb1256`. E02-R01 a E02-R04 encerrados; nenhum achado impeditivo remanescente identificado nesta revalidação. Todas as dez fatias aprovadas. Nas E02-01, E02-04, E02-06 e E02-10, a aprovação anterior foi mantida com regressão completa; não se atribuem mudanças funcionais a essas fatias.

Escopo: diff desde `8f4dc36`, especificações/aceitações corrigidas das fatias afetadas e integração. Referências de negócio e infraestrutura permanecem nas versões 1.6 e 1.7 utilizadas na revisão anterior. Os acréscimos detalham invariantes existentes, sem nova decisão comercial pendente.

| Achado | Resultado independente | Critérios adicionais conferidos |
|---|---|---|
| R01 — bloqueador | Encerrado: perfil não restaura situação/senha; conta removida recebe 403 sem gravação; recuperação restringe UPDATE; vínculo Google serializa a leitura e gravação | E02-09 A-20 a A-25; E02-02 A-25; E02-07 A-21; integração E02-08 |
| R02 — importante | Encerrado: remoções concorrentes conservam exatamente uma passkey; probe com barreira original passa | E02-03 A-16/A-17, regressão de gestão/recência e renderização |
| R03 — importante | Encerrado: userinfo e ID token concluem cadastro; marcações ausentes, não booleanas ou contraditórias são recusadas | E02-07 A-18 a A-20 |
| R04 — importante | Encerrado: similaridade compara os atributos reais, tanto no cadastro como na recuperação; configuração de produção coberta | E02-02 A-22 a A-24; E02-05 A-19/A-20 |

### Execuções independentes neste SHA

- `uv run pytest -q`: **634 passed em 70,20 s**, incluindo E01, todas as fatias E02 e os testes novos. Banco Postgres real; testes concorrentes usam conexões independentes. Os cenários de duas remoções, consentimento e perfil/suspensão executam dez repetições internas conforme os testes.
- `uv run pytest -q -c pyproject.toml $env:TEMP/om_e02_0178d62_probes.py`: **7 passed em 2,20 s**. Script derivado do probe integral preservado acima: três intercalações de perfil, corrida de remoção de passkeys, Google userinfo, similaridade de senha e PNG/EXIF.
- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 159 arquivos já formatados.
- `uv run mypy .`: sem erros em 123 arquivos.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: No changes detected.
- `uv run python manage.py check --settings=config.settings.test`: zero issues.
- `uv sync --locked`: 51 pacotes resolvidos, 50 conferidos.
- CI do SHA exato: [run 38923022498](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38923022498), completed/success, consultado com `gh run list --commit 0178d6214779504ef55abb183c4e8e5b5dfb1256 --json databaseId,status,conclusion,url`.

Para reproduzir os probes, usar o script histórico acima com **somente** este ajuste autorizado por E02-09, Correção R01, item 4: capturar `nome_anterior = conta.nome` antes do POST de perfil; substituir a asserção de status por `assert resposta.status_code == (403 if acao == 'remover' else 302)`; depois do refresh, no caso `remover`, exigir também `assert conta.nome == nome_anterior`. As demais asserções permanecem literais. Isso fortalece a recusa da conta removida, sem ocultar a verificação original da situação. O arquivo temporário antigo foi preservado. As reproduções também estão incorporadas nos testes versionados indicados nos relatórios das fatias.

### TDD, escopo e limites

Conferidos os registros Red/Green do implementador nos relatórios E02-02, E02-03, E02-07 e E02-09, com comandos, falhas por comportamento e nomes dos testes, comparados com os testes novos e o diff de produção. R01 relata falhas de preservação de estado/credenciais e SQL; R02 relata zero passkeys; R03 relata recusa de userinfo e aceitação indevida de marcas conflitantes; R04 relata aceitação de senhas semelhantes e configuração incorreta. A adição de `django.contrib.humanize` atende à renderização de templates allauth já no escopo, com Red documentado e regressão verde. Não houve afrouxamento identificado para acomodar as correções.

A cronologia Red antes de produção continua apoiada nos registros do implementador: esta revalidação não observou retrospectivamente sua execução nem reproduziu os novos testes sobre o commit antigo. O Green e os probes acima foram executados pelo revisor. Mantém-se a distinção entre evidência documentada de TDD e execução independente.

WebAuthn usa o dublê criptográfico previsto, com views, sessões e persistência reais. Google usa resposta simulada no fluxo do allauth; não houve OAuth externo. Cerimônia física de passkey, credenciais Google, SES e R2 reais continuam nos gates de homologação previstos; esta aprovação não declara esses testes realizados nem autoriza produção. D-1 de E02-08 permanece fora do escopo.

Alterações do revisor: somente os dez `review.md`, com parecer atual e histórico preservado. Nenhuma alteração de produção ou teste versionado. Próximo gate: encerramento da E02 com este parecer e seleção/especificação da próxima entrega conforme o fluxo do projeto.
