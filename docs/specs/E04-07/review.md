# E04-07 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `0b52010` (2026-10-17). E04 global: **REPROVADO**. Registro do implementador preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia e a E04-02 a E04-05.

## Arquivos

- `apps/notificacoes/consultas.py` (novo): `envios_para_administracao`, `contar_falhas`, `filtros_validos` e os rótulos de situação, canal e tipo.
- `apps/notificacoes/views.py` (`envios_lista`, `envio_detalhe`), `config/urls.py`, `templatetags/notificacoes.py` (filtro `valor_do_mapa`).
- `templates/notificacoes/envios_lista.html` e `envio_detalhe.html`; `apps/contas/views.py` e `templates/administracao/painel.html` (indicador de falhas e link para a lista).
- Testes: `tests/tecnicos/test_notificacoes_administracao.py` (novo).

## Decisões técnicas

- Rotas só `GET` (`require_GET`, 405 nos demais métodos) e com a política `administrador` (`somente_administrador`).
- Filtros inválidos (`situacao`, `canal`, `tipo`) são ignorados por `filtros_validos`, sem erro; o formulário mostra "todos".
- Sem N+1: a lista usa `select_related("conta")` e uma subconsulta (`OuterRef`) para a classe do último erro; o detalhe faz um número fixo de consultas.
- "Aceito pelo serviço" é um rótulo da consulta (`ROTULOS_SITUACAO`), e não o rótulo do modelo (`SituacaoEnvio.ENVIADO`), para não criar migração só por texto.
- Detalhe: nos e-mails de acesso o corpo aparece como "(não armazenado: contém link de acesso)"; o número do WhatsApp não aparece, porque não é gravado; o destinatário é o nome da conta ou, no convite, o e-mail de destino.
- Painel inicial da administração: ganhou o link "Envios" e o indicador "Envios com falha: <n>" (só com `n > 0`).

## TDD

**Red.** Andaime (`consultas.py` devolvendo vazio/zero e views com corpo vazio): `uv run pytest tests/tecnicos/test_notificacoes_administracao.py -q` deu **14 failed, 3 passed**, por asserção (listas, filtros, detalhe, indicador e mensagens ausentes). Passaram já no Red o controle de acesso (a decoração das views estava no andaime), o teste "sem falhas" e a contagem de consultas da lista (a lista vazia não tem N+1); este último só passa a ter sentido no Green.

**Green.** Mesmo arquivo: **17 passed**. Suíte completa: **1385 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_lista_paginada_e_ordenada` |
| A-2 | `test_filtros_combinaveis_e_valores_invalidos_sao_ignorados` |
| A-3, A-4 | `test_detalhe_com_tentativas`, `test_corpo_de_email_de_acesso_nao_e_armazenado` |
| A-5 | `test_indicador_de_falhas_na_pagina_inicial`, `test_sem_falhas_o_indicador_nao_aparece` |
| A-6 | `test_a_lista_nao_cai_em_n_mais_um` |
| A-7, A-8, A-9 | `test_quem_nao_e_administrador_nao_consulta`, `test_so_leitura_e_id_inexistente`, `test_listas_vazias` |
| A-10 | `test_permissoes_politica_rotas.py` (varredura existente) |

## Limites da verificação

Cliente HTTP do Django, sem navegador. A consulta é só de leitura; os alertas ativos e o painel consolidado são da E15.


## Revisão independente — 0b52010 — 2026-10-17

**Parecer da fatia: APROVADO. E04 global: REPROVADO.**

A-1 a A-10 conferidos e verdes: filtros combináveis, paginação e ordem, detalhe, erros, corpo de acesso omitido, indicador, consultas constantes, permissões e somente leitura. Sem achado próprio; parecer global abaixo.

Verificação independente: **1385 passed em 160,23 s** na suíte completa. Probes adicionais: **10 failed, 4 passed em 4,39 s**, mais **1 passed em 2,52 s** no caso de isolamento acrescentado. Dez falhas correspondem a R01 (oito) e R02 (duas). Lint, formatação, tipos, Django e CI passaram.

Comandos, matriz, reproduções, TDD, critérios de correção e limites no [parecer consolidado E04-07](../E04-07/review.md). Nenhum código ou teste versionado foi alterado pelo revisor.

### Escopo e decisão global

Commit auditado: `0b520106a2a820463865bc1d4b5a80d36ce37590`, inicialmente em main com árvore limpa. Comparação com E03 aprovada em `8257f66` (pareceres incorporados pelo PR 49). Lidos AGENTS.md, requisitos pertinentes da funcional v1.6 e infraestrutura v1.7 (versões compatíveis) e sete pares spec/acceptance antes da avaliação. Conferidos registros TDD, serviços, modelos, migrações/triggers, rotas, templates e testes.

**E04 REPROVADA.** R01 e R02 são importantes e impedem encerramento. R03 é melhoria documental. Não há decisão comercial nova necessária: caminhos internos seguros e envio após commit decorrem dos requisitos existentes.

| Fatia | Critérios confrontados | Parecer |
|---|---|---|
| E04-01 | A-1 a A-14; negativos adicionais de link | REPROVADO — R01 |
| E04-02 | A-1 a A-14; emissão única/lote e lote parcialmente existente | REPROVADO — R01 |
| E04-03 | A-1 a A-12 | APROVADO |
| E04-04 | A-1 a A-13; A-9 com ressalva documental e mecanismo verificado adicionalmente | APROVADO — R03 melhoria |
| E04-05 | A-1 a A-11; commit e rollback adicionais | REPROVADO — R02 |
| E04-06 | A-1 a A-15 | APROVADO |
| E04-07 | A-1 a A-10 | APROVADO |

Todos os arquivos mapeados nos acceptance.md foram incluídos na execução integral, inclusive concorrência e regressões E01–E03. Aprovação das fatias sem achado próprio não encerra a E04 nem elimina suas dependências.

### R01 — Importante — links externos aceitos como caminhos internos

**Requisito:** E04-01/spec.md, campo link, validação e caso-limite "para que nenhum aviso aponte para fora do site"; E04-02 exige a mesma validação em toda emissão; AGENTS.md §6, segurança. A regra abreviada "começa por / e não por //" foi implementada literalmente, mas não assegura o objetivo declarado de caminho relativo do site.

**Código:** `apps/notificacoes/servicos.py:46`, `apps/notificacoes/models.py:59`, migração `0001_inicial` e `templates/notificacoes/_item.html:6` (href direto).

**Reprodução:** valores Python `'/\\externo.example/'` (uma barra invertida após a barra normal) e `'/\t/externo.example/'` (tabulação entre duas barras) são aceitos por criar_notificacao, emitir_evento, emitir_evento_para_varios e constraint do banco. O parser WHATWG `new URL(valor, 'https://om.test')`, executado localmente no Node 24, resolve ambos para `https://externo.example/`. Nenhum domínio foi acessado.

**Evidência:** seis casos de serviço e dois de banco falham com DID NOT RAISE; dois controles de caminhos internos passam. A origem do link hoje é código interno; não foi demonstrado formulário público que permita exploração. Ainda assim, a API aceita e persiste um destino externo apresentado como link interno na central.

**Correção esperada:** reforçar validação compartilhada e proteção no banco contra caminhos normalizados para outra origem, incluindo barras invertidas e controles relevantes; cobrir três entradas e banco, preservando caminhos, queries e fragmentos internos legítimos. Detalhar os negativos na spec/acceptance, sem afrouxar a restrição a links internos. Revalidar os oito casos e controles.

### R02 — Importante — recuperação de senha envia antes do commit

**Requisito:** E04-05/spec.md, decisão "Envio imediato, não pela fila", regra 1 e invariantes de registro; funcional §12, registro de envios e falhas.

**Código:** `apps/contas/adaptadores.py:67`, chamada direta em `:73`. A atomic de `apps/notificacoes/acesso.py` vira savepoint quando existe transação externa. O registro do implementador informa allauth direto; isso diverge do on_commit exigido para os três fluxos.

**Reprodução HTTP:** criar comprador, abrir transaction.atomic, fazer POST /recuperar-acesso/ para seu e-mail e provocar rollback. Resultado: **um e-mail em mail.outbox e zero Envio no banco**. No caso com commit, um e-mail já saiu antes de sair do atomic. O controle de rollback em /entrar/link/ passa (nenhum e-mail).

**Impacto:** envio externo antes da confirmação; rollback elimina o histórico do e-mail aceito. A reprodução envolve transação externa explícita; não afirma que toda requisição normal usa ATOMIC_REQUESTS.

**Correção esperada:** adaptar allauth para on_commit, preservando conteúdo renderizado, associação à conta, modelo, resposta antienumeração e tratamento de falhas. Testar commit (nada antes; uma tentativa depois), rollback (nenhum envio/registro), falha de canal e falha de gravação, sem persistir token.

### R03 — Melhoria — cenário de WhatsApp diverge da matriz

E04-04/spec.md e A-9 mencionam pagamento_confirmado gerando WhatsApp; E04-01 define esse evento só em site/e-mail. O código respeita a matriz. O teste `test_notificacoes_falha_isolada.py:36` emite também pagamento_aberto em outra transação para exercitar WhatsApp.

Alinhar redação e teste a um evento com WhatsApp, mantendo fato simulado e emissão na mesma transação; não acrescentar um canal ao pagamento_confirmado apenas para satisfazer o cenário. O probe independente test_falha_whatsapp_preserva_fato_emitido_na_mesma_transacao confirma o mecanismo com pagamento_aberto após commit real: fato preservado, notificação inalterada, e-mail aceito e WhatsApp com três falhas. Por isso não há bloqueio de implementação da E04-04 por esse ponto. Cenário com pagamento do simulador continua herdado pela E08.

### Comandos e resultados independentes

| Comando | Resultado |
|---|---|
| `uv run pytest -q` | **1385 passed em 160,23 s** |
| `uv run pytest -q -c pyproject.toml $env:TEMP/om_e04_0b52010_probes.py --tb=short --show-capture=no` | Primeiros 14 casos: **10 failed, 4 passed em 4,39 s** |
| `uv run pytest -q -c pyproject.toml $env:TEMP/om_e04_0b52010_probes.py -k falha_whatsapp --tb=short --show-capture=no` | Caso acrescentado: **1 passed, 14 deselected em 2,52 s** |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 293 arquivos formatados |
| `uv run mypy .` | Sem problemas em 233 arquivos |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | No changes detected |
| `uv run python manage.py check --settings=config.settings.test` | Nenhum problema |
| `uv sync --locked` | 51 pacotes resolvidos, 50 verificados |

[CI do commit](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/39036348697): completed/success, consultado pelo SHA completo. Logs locais: `$env:TEMP/om_e04_0b52010_suite.log` e `$env:TEMP/om_e04_0b52010_probes.log` (primeiros 14 casos). Total adicional executado: **15 casos, dez falhas e cinco sucessos**. As oito falhas de R01 são duas entradas inválidas em quatro camadas, não oito defeitos distintos.

Verificação adicional sem rede: Node 24 recebeu por stdin `for (const s of ["/\\externo.example/", "/\t/externo.example/", "/historico/"]) console.log(JSON.stringify(s), new URL(s, "https://om.test").href);`. Os dois primeiros resolvem para a origem externa; o controle resolve para https://om.test/historico/.

### TDD e limites

| Fatia | Red documentado | Green documentado |
|---|---|---|
| E04-01 | 43 failed, 4 passed | 47 focados; 1256 completos |
| E04-02 | 32 failed, 41 passed | 73 focados; 1295 completos |
| E04-03 | 14 failed, 89 passed | 103 focados; 1312 completos |
| E04-04 | 14 failed, 11 passed | focados verdes; 1331 completos |
| E04-05 | 8 failed, 5 passed | 13 focados; 1344 completos |
| E04-06 | 21 failed, 6 passed | 27 focados; 1368 completos |
| E04-07 | 14 failed, 3 passed | 17 focados; 1385 completos |

Registros relacionam comandos, andaimes, falhas esperadas, arquivos e ajustes. Commits por fatia combinam código e testes; a cronologia Red é evidência documental, não presenciada nesta revisão. O Green integral foi reexecutado. O ajuste relatado na E04-01 (não remarcar notificação já lida) corresponde à regra de imutabilidade. Não foi encontrado afrouxamento das asserções existentes da E02; o helper da configuração de produção foi ampliado para parametrizar módulos e CANAL_WHATSAPP. A divergência do cenário 24 está registrada em R03.

Postgres e cliente HTTP Django; WebAuthn com dublê autorizado. Sem navegador interativo, SMTP/SES real, Meta ou dinheiro real. Worker não executado como processo: conferidos registro periódico, descoberta configurada no código instalado do Procrastinate e chamada da tarefa. SMTP permanece pelo menos uma vez: queda após aceite e antes do commit pode duplicar mensagem, como previsto. Aceite não comprova entrega. Falha excepcional de gravação após envio de acesso é prevista na spec; R02 é distinto, pois inicia o envio antes do commit exigido.

Alterações do revisor: apenas sete review.md da E04, branch revisao/e04-0b52010, sem commit/push. Código e testes versionados intactos. Próximo gate: correções R01/R02 com Red → Green e revalidação independente. R03 deve ser alinhado pelo especificador, preservando a matriz.

### Script reproduzível

Salvar como `$env:TEMP/om_e04_0b52010_probes.py`. Script final com 15 casos; o último foi executado separadamente. Usa backend de e-mail de teste e simulador, sem envio real.

```python
import pytest
from django.core import mail
from django.core.cache import cache
from django.db import transaction, IntegrityError
from django.utils.http import url_has_allowed_host_and_scheme
from apps.notificacoes.eventos import Evento
from apps.notificacoes.models import Envio, Notificacao
from apps.notificacoes.servicos import criar_notificacao, NotificacaoInvalida
from apps.notificacoes.emissao import emitir_evento, emitir_evento_para_varios
from tests.fabricas import ContaFactory, NotificacaoFactory

@pytest.fixture(autouse=True)
def limpar_cache():
    cache.clear()

@pytest.mark.django_db
@pytest.mark.parametrize('link', ['/\\externo.example/', '/\t/externo.example/'], ids=['barra_invertida', 'tabulacao'])
@pytest.mark.parametrize('modo', ['criar', 'emitir', 'lote'])
def test_link_externo_disfarcado_de_relativo_deve_ser_recusado(link, modo):
    conta = ContaFactory.create()
    with pytest.raises(NotificacaoInvalida), transaction.atomic():
        if modo == 'criar':
            criar_notificacao(conta, Evento.ESTORNO, titulo='t', corpo='c', link=link, chave='probe')
        elif modo == 'emitir':
            emitir_evento(Evento.ESTORNO, conta, titulo='t', corpo='c', link=link, chave='probe')
        else:
            emitir_evento_para_varios(Evento.ESTORNO, [conta], titulo='t', corpo='c', link=link, chave_base='probe')

@pytest.mark.django_db
@pytest.mark.parametrize('link', ['/\\externo.example/', '/\t/externo.example/'], ids=['barra_invertida', 'tabulacao'])
def test_banco_deve_recusar_link_externo_disfarcado(link):
    conta = ContaFactory.create()
    with pytest.raises(IntegrityError), transaction.atomic():
        NotificacaoFactory.create(conta=conta, link=link)

@pytest.mark.django_db
@pytest.mark.parametrize('link', ['/historico/', '/catalogo/1/?q=abc#x'])
def test_links_internos_continuam_validos(link):
    conta = ContaFactory.create()
    n = criar_notificacao(conta, Evento.ESTORNO, titulo='t', corpo='c', link=link, chave='probe')
    assert n.link == link
    assert url_has_allowed_host_and_scheme(link, allowed_hosts={'om.test'})

@pytest.mark.django_db(transaction=True)
def test_recuperacao_rollback_nao_envia_email(client):
    conta = ContaFactory.create()
    with pytest.raises(RuntimeError), transaction.atomic():
        resposta = client.post('/recuperar-acesso/', {'email': conta.email_normalizado})
        assert resposta.status_code == 302
        raise RuntimeError('rollback deliberado')
    assert Envio.objects.count() == 0
    assert len(mail.outbox) == 0, 'email saiu, mas seu registro foi desfeito pelo rollback'

@pytest.mark.django_db(transaction=True)
def test_recuperacao_so_envia_apos_commit(client):
    conta = ContaFactory.create()
    with transaction.atomic():
        resposta = client.post('/recuperar-acesso/', {'email': conta.email_normalizado})
        assert resposta.status_code == 302
        antes_do_commit = len(mail.outbox)
    assert len(mail.outbox) == 1
    assert Envio.objects.count() == 1
    assert antes_do_commit == 0, 'email enviado antes do commit'

@pytest.mark.django_db(transaction=True)
def test_link_rollback_nao_envia_email(client):
    conta = ContaFactory.create()
    with pytest.raises(RuntimeError), transaction.atomic():
        resposta = client.post('/entrar/link/', {'email': conta.email_normalizado})
        assert resposta.status_code == 200
        raise RuntimeError('rollback deliberado')
    assert Envio.objects.count() == 0
    assert len(mail.outbox) == 0

@pytest.mark.django_db
def test_lote_parcialmente_existente_cria_so_as_novas():
    a, b = ContaFactory.create(), ContaFactory.create()
    with transaction.atomic():
        assert emitir_evento_para_varios(Evento.ESTORNO, [a], titulo='t', corpo='c', chave_base='probe') == 1
    with transaction.atomic():
        assert emitir_evento_para_varios(Evento.ESTORNO, [b, a, b], titulo='t', corpo='c', chave_base='probe') == 1
    assert Notificacao.objects.count() == Envio.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_falha_whatsapp_preserva_fato_emitido_na_mesma_transacao():
    from datetime import datetime, UTC, timedelta
    import time_machine
    from apps.notificacoes.whatsapp import SIMULADOR
    from apps.notificacoes.processamento import processar_envios
    from apps.nucleo.tempo import agora
    from tests.apoio.models import ModeloContador
    SIMULADOR.reiniciar()
    SIMULADOR.falhar_sempre()
    try:
        with time_machine.travel(datetime(2026, 10, 17, 15, tzinfo=UTC), tick=False) as relogio:
            conta = ContaFactory.create(telefone='+5521999990000', whatsapp_consentido_em=agora())
            with transaction.atomic():
                fato = ModeloContador.objects.create(valor=7)
                n = emitir_evento(Evento.PAGAMENTO_ABERTO, conta, titulo='Aberto', corpo='c', chave='fato:1')
            for minutos in (0, 1, 10):
                relogio.shift(timedelta(minutes=minutos))
                processar_envios()
            fato.refresh_from_db()
            assert fato.valor == 7
            assert Notificacao.objects.get(pk=n.pk).corpo == 'c'
            e = Envio.objects.get(canal='whatsapp')
            assert (e.situacao, e.tentativas) == ('falhou', 3)
            assert Envio.objects.get(canal='email').situacao == 'enviado'
    finally:
        SIMULADOR.reiniciar()

```
