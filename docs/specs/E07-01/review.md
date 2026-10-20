# E07 — Revisão independente do agente 3 — 2026-10-20

**Veredito global: REPROVADO sobre `d6e4d2095ac8f1128b1a315fd81e5ab579488aa3`, branch `e07-implementacao`.** R01 é bloqueador; R02, R03 e R05 são importantes; R04 é melhoria. A suíte verde não cobre as falhas de integração reproduzidas abaixo. A aprovação local de uma fatia não aprova a entrega integrada.

## Fontes, escopo e matriz

Lidos AGENTS.md, especificação funcional v1.6 (especialmente §§8.1, 8.3, 14 e 15), infraestrutura v1.7 (4.1–4.5, 5 e fase 1), os seis pares spec.md/acceptance.md e os registros de implementação. Comparação desde `e4d242c` (E06 integrada), incluindo interface/simulador, configurações, modelos/migrações e triggers, sincronização/sinal, chamadas, webhook, consulta antes de decisões, testes e alterações nos testes anteriores.

| Fatia | Critérios examinados | Parecer | Evidência e limites |
|---|---|---|---|
| E07-01 | A-1 a A-18 | REPROVADO | Idempotência, controles, falhas, assinatura e fronteiras passam na suíte; R03 na persistência integrada, R04 na normalização UTC e R05 na validação do aviso. A-4 tem a inconsistência de preparação registrada abaixo. |
| E07-02 | A-1 a A-10 | APROVADO | Configuração estrita, bloqueio na inicialização e em obter_provedor, subprocessos e ajustes autorizados dos testes conferidos. |
| E07-03 | A-1 a A-15 | APROVADO no escopo local | Unicidade, histórico imutável, divergências, transações, sinal e concorrência passam. R02 está no transporte do horário pela integração, não na atribuição quando o serviço recebe o argumento. |
| E07-04 | A-1 a A-16 | REPROVADO | Intervalos, 24h, erros, limite, skip_locked e deduplicação passam isoladamente; R01/R02 na integração com avisos e R03 no rollback do simulador. |
| E07-05 | A-1 a A-14 | REPROVADO | Assinatura, repetição, política pública, transação e concorrência dos avisos passam nos cenários existentes; R01, R02 e R05 permanecem. |
| E07-06 | A-1 a A-10 | APROVADO no escopo local | Busca, reconsulta dos conhecidos ausentes da busca, falhas bloqueantes, preservação das sincronizações anteriores e concorrência passam. Decisões de negócio e seus testes ficam nas etapas consumidoras. |

Os 83 critérios e regras associadas foram confrontados com código, testes e registros. As falhas adicionais não são representadas como falhas dos testes versionados: a suíte atual passa, mas deixa de exercitar essas combinações.

### TDD e integridade da revisão

Os seis registros trazem execução anterior ao código, comandos sem filtro por nome, tabela critério → teste → resultado e Green: E07-01 **35 failed/2 passed**, E07-02 **15/51**, E07-03 **17/5**, E07-04 **15/4**, E07-05 **13/21**, E07-06 **9/8**. As justificativas de andaime e testes já verdes estão registradas. Conferidos os testes e os motivos relatados; não foi identificada nova declaração de Red tardio como na E06. O revisor não observou a execução histórica: esta conclusão se limita à evidência registrada e à consistência com código/diffs, sem transformar as provas atuais em Red histórico.

Os ajustes em `test_configuracao_producao.py` e `test_nucleo_campos_decimais.py` correspondem à autorização de E07-02: variáveis de homologação/segredo e recarga do módulo; as assertivas anteriores foram preservadas. O único módulo adicional de produção que importa o modelo de pagamento para leitura é `apps/pagamentos/consulta.py`; a escrita continua concentrada em `sincronizacao.py`. Não há rota manual de registro, comando de pagamentos nem Django Admin.

**Correção documental recomendada:** E07-01 A-4 usa a cobrança de A-1 (criada às 13:00) e pede aprovação às 12:59:30, contrariando a recusa de aprovação anterior à criação. O implementador registrou o conflito e criou essa cobrança às 12:50 no teste. A preparação é tecnicamente coerente com a regra explícita e preserva a prova de aprovação informada depois; o especificador deve alinhar A-4. Não é necessária decisão comercial nova nem alteração da regra para essa correção editorial.

## Verificação independente executada

- `uv run pytest -q`: **1902 passed in 162.12s**. Log local: `%TEMP%/om_e07_d6e4d20_suite.log`.
- `uv run ruff check .`: **All checks passed!**
- `uv run ruff format --check .`: **256 files already formatted**.
- `uv run mypy .`: **Success: no issues found in 299 source files**.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: **No changes detected**.
- `uv run pytest -c pyproject.toml "$env:TEMP/test_review_e07_d6e4d20.py" -q --tb=short`: **8 failed, 2 passed in 2.79s** na versão final da prova. Primeira execução: mesmos 8/2 em 10.93s; a segunda acrescentou a observação do identificador devolvido na repetição de R03. Log local: `%TEMP%/om_e07_d6e4d20_probes.log`. Código completo preservado abaixo.

As oito falhas correspondem a R01 (1), R02 (1), R03 (1), R04 (2) e R05 (3). Os dois controles verdes são o aviso que cria sua própria consulta e o aviso que chega depois da conclusão de uma consulta anterior.

O PostgreSQL local do projeto estava parado. As primeiras tentativas ficaram aguardando conexão e foram interrompidas; não contam como resultado funcional. Foi iniciado somente o serviço já definido no repositório, `docker compose up -d db` (PostgreSQL 17, porta 5433). A suíte e as provas acima foram executadas sequencialmente após o serviço ficar saudável. Nenhum banco de aplicação foi recriado ou apagado pelo revisor.

## Achados

### R01 — BLOQUEADOR — Aviso de aprovação absorvido por consulta em andamento

Referências: funcional §§8.3 e 15; infraestrutura 4.2; integração E07-04/E07-05 (deduplicação, reconhecimento e processamento retomável). Código: `apps/pagamentos/chamadas.py:64-85,112-153,155-184` e `apps/pagamentos/avisos.py:48-57`.

A consulta pendente continua visível como pendente enquanto o worker a executa. `agendar_chamada` encontra essa linha por leitura sem trava e a devolve sem registrar que chegou um evento posterior à resposta já obtida do provedor. O worker conclui a consulta antiga, deixando o aviso novo sem trabalho futuro.

**Reprodução com duas threads e conexões reais:** agendar consulta de uma cobrança pendente; pausar o worker depois de obter a resposta pendente; na outra conexão, aprovar no simulador e entregar o aviso; confirmar HTTP lógico 200; liberar o worker. Ao processar a fila novamente, o provedor está aprovado, mas o registro local continua pendente e a única chamada está concluída. O teste falha na comparação `pendente == aprovado`, não por timeout ou erro de infraestrutura.

O evento está registrado, mas sua atualização não será obtida por essa fila. Repetir o mesmo evento também não agenda trabalho pelo caminho de deduplicação; outra busca/consulta independente pode recuperar a aprovação, o que não elimina a perda do processamento do aviso aceito. Não houve dinheiro real nesta prova.

**Correção exigida:** coordenar a deduplicação com a execução, garantindo uma consulta posterior ao aviso quando a resposta em andamento já foi obtida. Pode haver coalescência antes da consulta; não pode haver perda após a leitura. Preservar a unicidade de chamada pendente e de reconhecimento, acrescentando essa corrida e seus controles ao Red/Green. A especificação detalhada deve cobrir essa intercalação que faltou nas matrizes originais.

### R02 — IMPORTANTE — Horário do primeiro aviso não chega ao espelho quando já há consulta de tarefa

Referências: infraestrutura 4.2 (instantes separados), funcional §§14/15; E07-03 (primeiro aviso), E07-05 (avisos antes da consulta). Código: `apps/pagamentos/chamadas.py:82-84,198-205` e `apps/pagamentos/avisos.py:48-57`.

Agendar `consultar_pagamento` sem parâmetros, receber a aprovação por aviso às 13:00 e só então processar: o pagamento é aprovado, mas `primeiro_aviso_em` fica `None`. Os parâmetros do aviso são ignorados porque a chamada pendente já existia. O controle sem consulta previamente agendada grava 13:00 corretamente.

**Limite:** `AvisoRecebido.recebido_em` permanece íntegro; não há perda de todos os vestígios do evento nem alteração do horário de aprovação. A lacuna é no registro consolidado e decorre da combinação do contrato de agendamento “sem alterá-la” com o transporte do horário exclusivamente em parâmetros da chamada. O serviço de sincronização, quando recebe o horário, funciona.

**Correção exigida:** definir e testar na integração como recuperar/preservar o primeiro recebimento apesar da coalescência com uma tarefa anterior, sem sobrescrevê-lo com avisos posteriores. Alinhar as specs 04/05 para não depender de cada aviso criar a própria chamada; isso não muda a regra comercial de aceitação pelo horário do provedor.

### R03 — IMPORTANTE — Rollback local apaga cobrança já aceita pelo simulador

Referências: E07-01 (simulador como lado do provedor), E07-04 A-7/A-10 e caso de falha após aceitação; infraestrutura 4.2 e fase 1; AGENTS.md §6. Código: `apps/pagamentos/chamadas.py:175-176`, `apps/pagamentos/chamadas.py:120-122` e `apps/simulador_pagamentos/provedor.py:76-86`.

O savepoint externo de `_tentar` inclui a execução do provedor. Embora `concluir` tenha outro savepoint, uma exceção inesperada propagada dele desfaz também a criação feita no simulador, que compartilha a conexão/transação. O comentário de que o estado do provedor não se desfaz não vale nesse caminho.

**Reprodução:** usar a operação `criar_cobranca_de_teste` prevista na E07-04; o provedor retorna `sim-3`; `concluir` levanta `RuntimeError`; a chamada volta a pendente, mas a cobrança desaparece. Retirar a falha e repetir com a mesma chave retorna `sim-4`, em vez da cobrança aceita anteriormente. A prova usa a operação de apoio existente, sem implementar cobrança da E08.

O caso de `ProvedorIndisponivel` após executar já passa porque a exceção é tratada; isso não comprova recuperação após falha local inesperada. A limitação mencionada pelo implementador não substitui a simulação exigida. Este achado é sobre fidelidade do simulador e validade dos testes de recuperação; não demonstra duplicação de dinheiro num provedor real, ainda fora do escopo.

**Correção exigida:** preservar o estado aceito do lado simulado perante rollback/queda local e assegurar que a repetição devolva o mesmo identificador. Manter rollback dos efeitos locais de `concluir`. Cobrir tanto falha temporária após aceitação quanto falha inesperada depois da resposta, com nova evidência Red/Green.

### R04 — MELHORIA — Respostas imediatas do simulador não normalizam todos os instantes em UTC

Referências: E07-01, contrato de `PagamentoConsultado`; infraestrutura 4.2/5. Código: `apps/simulador_pagamentos/estado.py:42-61`.

Criar uma cobrança com `expira_em` em America/Sao_Paulo devolve esse offset na resposta imediata. Aprovar no cancelamento com `em` nesse fuso também devolve `aprovado_em` com -03:00. Uma leitura posterior do banco pode vir normalizada; a interface deve ser consistente em todos os caminhos.

São instantes equivalentes e não se demonstrou deslocamento temporal no banco. Normalizar os instantes ao construir `PagamentoConsultado` e testar entradas não UTC, inclusive criação, cancelamento e visão atrasada. Este desvio de representação, isoladamente, não reprovaria a entrega.

### R05 — IMPORTANTE — Avisos assinados fora dos limites dos campos provocam 500

Referências: E07-01 `verificar_aviso`/`AvisoInvalido`, E07-05 validação antes da gravação e tratamento de corpo inválido. Código: `apps/simulador_pagamentos/provedor.py:140-152`, `apps/pagamentos/avisos.py:40-46`, limites de `AvisoRecebido` em `apps/pagamentos/models.py`.

O verificador confere apenas assinatura, JSON e tipo string. Um corpo menor que 64 KiB, com assinatura válida, passa com `id_evento` de 65 caracteres, `id_externo` de 65 ou `tipo` de 41. O POST falha com `DataError: value too long for type character varying(...)` e responde 500 nos três casos. A falha é determinada pela entrada, não por indisponibilidade inesperada do banco.

**Limite:** a prova possui o segredo de teste para assinar; não é quebra de HMAC nem ataque comprovado de remetente sem assinatura. Os avisos produzidos normalmente pelo simulador usam identificadores curtos. A falha afeta a robustez da fronteira do receptor diante de corpo autenticado, porém incompatível com seu esquema persistido.

**Correção exigida:** validar o esquema e os limites antes da transação, convertendo entradas incompatíveis em `AvisoInvalido`/401, sem gravações. Manter 200 para tipos desconhecidos válidos dentro do esquema e 400 para corpo acima do limite global. Acrescentar os casos à matriz e aos testes HTTP, sem capturar indiscriminadamente erros de banco.

## Próximo gate e limitações

Devolver R01, R02, R03 e R05 para correção, com alinhamento das especificações de integração e Red/Green observável; tratar R04 e o ajuste editorial de A-4. Depois, revalidar as provas e a suíte antes de emitir aprovação. Não há motivo para antecipar a E08, o provedor real ou uma nova decisão comercial para resolver esses pontos técnicos.

Verificação em PostgreSQL real local, cliente HTTP do Django e simulador; R01 usa duas conexões reais. Não houve navegador, worker do Procrastinate como processo separado, rede de pagamentos ou dinheiro real. O registro da tarefa e sua rotina foram exercitados pelos testes. E08 em diante e L-1 a L-11 do provedor real continuam fora do escopo. O revisor não alterou produção, testes versionados ou especificações; somente os seis review.md.

## Provas independentes reproduzíveis

Salvar o bloco abaixo como `$env:TEMP/test_review_e07_d6e4d20.py` e executar o comando registrado acima, a partir da raiz, com o PostgreSQL de testes disponível. A prova R03 inclui uma repetição após a falha; os identificadores exatos variam com a sequência do banco.

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
import hashlib
import hmac
import json
import threading
import pytest
import time_machine
from django.conf import settings
from django.db import transaction
from django.test import Client
from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import OPERACOES, Operacao, agendar_chamada, processar_chamadas
from apps.pagamentos.models import AvisoRecebido, ChamadaAoProvedor, PagamentoNoProvedor
from apps.pagamentos.provedor import NovaCobranca, obter_provedor
from apps.simulador_pagamentos import controle as sim
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.chamadas import operacao_de_teste, NOME

T = datetime(2026,11,2,13,tzinfo=UTC)

@pytest.fixture(autouse=True)
def resetar():
    sim.reiniciar()
    yield
    sim.reiniciar()

def criar(expira=None):
    return obter_provedor().criar_cobranca(NovaCobranca('probe','ref-probe',Decimal('45.90'),'Teste',expira or agora()+timedelta(days=1))).pagamento

@pytest.mark.django_db(transaction=True)
def test_aviso_durante_consulta_nao_e_perdido(monkeypatch):
    p=criar()
    with transaction.atomic(): agendar_chamada('consultar_pagamento',p.id_externo)
    consultou,notificou=threading.Event(),threading.Event()
    original=OPERACOES['consultar_pagamento']
    def pausar(provedor,chamada):
        resposta=original.executar(provedor,chamada)
        consultou.set()
        assert notificou.wait(20), 'notificacao nao terminou'
        return resposta
    monkeypatch.setitem(OPERACOES,'consultar_pagamento',Operacao(pausar,original.concluir))
    def avisar(barreira):
        assert consultou.wait(20), 'consulta nao ocorreu'
        try:
            sim.aprovar(p.id_externo)
            return sim.entregar_avisos()
        finally: notificou.set()
    resultados=executar_em_paralelo(lambda barreira: processar_chamadas(),avisar)
    assert all(r.excecao is None for r in resultados),[r.excecao for r in resultados]
    assert resultados[1].valor==[200]
    monkeypatch.setitem(OPERACOES,'consultar_pagamento',original)
    processar_chamadas()
    assert obter_provedor().consultar_pagamento(p.id_externo).situacao=='aprovado'
    assert PagamentoNoProvedor.objects.get().situacao=='aprovado',list(ChamadaAoProvedor.objects.values('situacao','parametros'))

@pytest.mark.django_db
@pytest.mark.parametrize('pre_agendada',[False,True])
def test_primeiro_aviso_preservado_com_consulta_ja_agendada(pre_agendada):
    with time_machine.travel(T,tick=False):
        p=criar()
        if pre_agendada:
            with transaction.atomic(): agendar_chamada('consultar_pagamento',p.id_externo)
        sim.aprovar(p.id_externo)
        assert sim.entregar_avisos()==[200]
        assert processar_chamadas()==1
        assert PagamentoNoProvedor.objects.get().primeiro_aviso_em==T

@pytest.mark.django_db
def test_falha_local_nao_apaga_cobranca_aceita(monkeypatch):
    with time_machine.travel(T,tick=False),operacao_de_teste(),monkeypatch.context() as patch:
        with transaction.atomic():
            agendar_chamada(NOME,'ref-probe',parametros={'valor':'45.90','expira_em':(T+timedelta(days=1)).isoformat()},chave_idempotencia='probe-falha')
        original=OPERACOES[NOME]
        vistos=[]
        def falhar(chamada,resultado):
            vistos.append(resultado.pagamento.id_externo)
            raise RuntimeError('falha local depois da resposta')
        patch.setitem(OPERACOES,NOME,Operacao(original.executar,falhar))
        assert processar_chamadas()==1
        assert len(vistos)==1
        assert ChamadaAoProvedor.objects.get().situacao=='pendente'
        preservada = CobrancaSimulada.objects.filter(chave_idempotencia='probe-falha').exists()
        patch.setitem(OPERACOES,NOME,original)
        assert processar_chamadas()==1
        atual = CobrancaSimulada.objects.get().id_externo
        assert preservada and atual==vistos[0], {'preservada':preservada,'primeiro_id':vistos[0],'repeticao_id':atual}

@pytest.mark.django_db
@pytest.mark.parametrize('campo,tamanho',[('id_evento',65),('tipo',41),('id_externo',65)])
def test_aviso_assinado_fora_dos_limites_nao_causa_500(campo,tamanho):
    dados={'id_evento':'ev-probe','tipo':'pagamento','id_externo':'sim-999'}
    dados[campo]='x'*tamanho
    corpo=json.dumps(dados).encode()
    assinatura=hmac.new(settings.SEGREDO_AVISOS_SIMULADOR.encode(),corpo,hashlib.sha256).hexdigest()
    cliente=Client(raise_request_exception=False)
    resposta=cliente.post('/pagamentos/avisos/',data=corpo,content_type='application/json',headers={'X-Simulador-Assinatura':'sha256='+assinatura})
    assert resposta.status_code==401
    assert not AvisoRecebido.objects.exists()
    assert not ChamadaAoProvedor.objects.exists()

@pytest.mark.django_db
@pytest.mark.parametrize('operacao',['criar','cancelar'])
def test_resposta_do_simulador_normaliza_utc(operacao):
    with time_machine.travel(T,tick=False):
        local=ZoneInfo('America/Sao_Paulo')
        p=criar((T+timedelta(days=1)).astimezone(local))
        if operacao=='cancelar':
            sim.aprovar_no_cancelamento(p.id_externo,em=T.astimezone(local))
            p=obter_provedor().cancelar_cobranca(p.id_externo)
            assert p.aprovado_em.utcoffset()==timedelta(0)
        assert p.expira_em.utcoffset()==timedelta(0)

@pytest.mark.django_db
def test_aviso_apos_consulta_concluida_atualiza():
    p=criar()
    with transaction.atomic(): agendar_chamada('consultar_pagamento',p.id_externo)
    assert processar_chamadas()==1
    sim.aprovar(p.id_externo)
    assert sim.entregar_avisos()==[200]
    assert processar_chamadas()==1
    assert PagamentoNoProvedor.objects.get().situacao=='aprovado'

```

---

## Registro do implementador preservado

# E07-01 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§8.1, 15), infraestrutura v1.7 (4.1 a 4.5, 7, 9.2), `spec.md` e `acceptance.md` da fatia, E04-04 (precedente do simulador de WhatsApp) e AGENTS.md §§3, 6 e 7.

## Arquivos

- `apps/pagamentos/` (app novo, sem modelos nesta fatia): `provedor.py` com `SituacaoNoProvedor`, `NovaCobranca` (validação local), `PagamentoConsultado`, `CobrancaCriada`, `AvisoDoProvedor`, os quatro erros, o protocolo `Provedor` e `obter_provedor()`.
- `apps/simulador_pagamentos/` (app novo): `models.py` (`CobrancaSimulada`, `AvisoSimulado`) e `migrations/0001_initial.py`; `provedor.py` (`ProvedorSimulado`); `estado.py` (leitura e mudança do estado, assinatura, log); `plano.py` (plano de falhas no processo); `controle.py` (os controles dos testes).
- `config/settings/base.py` (dois apps em `INSTALLED_APPS`; `SEGREDO_AVISOS_SIMULADOR` lido do ambiente, sem padrão), `dev.py` e `test.py` (valor padrão só neles).
- `tests/conftest.py`: fixture `simulador_pagamentos` (reinicia o plano antes e depois do teste).
- Testes: `tests/tecnicos/test_pagamentos_simulador.py` (A-1 a A-14, A-17, A-18), `test_pagamentos_concorrencia.py` (A-15), `test_pagamentos_fronteiras.py` (A-16).

## Ciclo TDD

**Andaime (exceção técnica, sem comportamento testável):** os tipos, os erros, o protocolo, as duas tabelas com a migração, `obter_provedor()` e métodos neutros no simulador e nos controles (devolvem valores vazios; `reiniciar` zera o plano). Nenhuma validação, regra de idempotência nem aviso existia antes dos testes.

### Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pagamentos_simulador.py tests/tecnicos/test_pagamentos_concorrencia.py tests/tecnicos/test_pagamentos_fronteiras.py -q`: **35 failed, 2 passed**. Todas as falhas são por asserção (`DID NOT RAISE ...`, `assert 0 == 3`, `assert [] == [...]`, `assert <pendente> == <aprovado>`). Uma primeira leitura teve falhas por `ValueError`/`IndexError` ao desempacotar listas vazias nas preparações; as preparações foram tornadas assertivas (`assert len(...) == 3`) antes do Green e o Red acima é o da segunda leitura, anterior a todo código de produção.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_criar_cobranca_devolve_o_pagamento_pendente` | falhou (`assert False` em `id_externo.startswith("sim-")`) |
| A-2 | `test_a_mesma_chave_devolve_a_mesma_cobranca` | falhou (`assert 0 == 1` linhas) |
| A-3 | `test_pedido_invalido_e_recusado_antes_do_provedor` (10 casos), `test_expiracao_que_nao_e_futura_e_recusada` | falharam (`DID NOT RAISE` nos 10; `DID NOT RAISE RecusaDoProvedor`) |
| A-4 | `test_aprovacao_informada_depois` | falhou (`assert 0 == 1` avisos) |
| A-5 | `test_aprovacao_depois_do_vencimento_ou_do_cancelamento`, `test_recusar_e_expirar_so_a_partir_de_pendente` | falharam (`pendente == aprovado`; `DID NOT RAISE ValueError`) |
| A-6 | `test_cancelar_so_muda_a_pendente` | falhou (`pendente == cancelado`) |
| A-7 | `test_cancelamento_que_coincide_com_o_pagamento` | falhou (`pendente == aprovado`) |
| A-8 | `test_buscar_por_referencia` | falhou (`assert [] == ['', '']`) |
| A-9 | `test_identificador_desconhecido` | falhou (`DID NOT RAISE PagamentoNaoEncontrado`) |
| A-10 | `test_provedor_indisponivel` | falhou (`DID NOT RAISE ProvedorIndisponivel`) |
| A-11 | os três testes `tempo_esgotado...`, `falha_antes...`, `falhar_proximas_de_outra...` | falharam (`assert 0 == 1`, `DID NOT RAISE ProvedorIndisponivel`) |
| A-12 | `test_atraso_de_consistencia`, `..._vale_tambem_para_a_busca` | falharam (`pendente == aprovado`; `[] == [pendente]`) |
| A-13 | `test_avisos_atrasados_repetidos_fora_de_ordem_e_perdidos`, `test_avisos_pendentes_na_ordem_de_criacao`, `test_reemitir_aviso_nao_muda_a_situacao` | falharam (`assert 0 == 3` na preparação dos três avisos; `assert 0 == 2`) |
| A-14 | `test_verificacao_do_aviso`, `test_corpo_que_nao_e_json_com_assinatura_valida_e_invalido`, `test_verificacao_aceita_cabecalho_em_qualquer_caixa` | falharam (`DID NOT RAISE AvisoInvalido`; `assert 0 == 3`) |
| A-15 | `test_a_mesma_chave_em_duas_conexoes_cria_uma_cobranca_so` | falhou por asserção contra o andaime (Red anterior ao código de produção) |
| A-16 | `test_so_a_interface_e_o_proprio_simulador_importam_o_simulador`, `test_o_simulador_nao_importa_modelos_de_pagamentos` | **passaram no Red**: é propriedade de estrutura que o andaime já cumpria (só `apps/pagamentos/provedor.py` importa o simulador; ele não importa modelos de pagamentos); protegem contra regressão |
| A-17 | `test_o_log_nao_leva_dado_do_pedido` | falhou (`assert []`: nenhuma mensagem de operação) |
| A-18 | `test_a_mesma_sequencia_da_o_mesmo_resultado` | falhou (a primeira sequência já difere do esperado) |

### Green

Os três arquivos: **37 passed**. Suíte completa: **1828 passed** (eram 1791). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Decisões técnicas (derivadas da spec)

- **Identificadores derivados da chave primária.** `id_externo` (`sim-<pk>`) e `id_evento` (`sim-ev-<pk>`) são propriedades da chave sequencial, e não colunas: assim são sequenciais, únicos e livres de corrida, sem segunda gravação. `sim-` seguido de algo que não seja o inteiro canônico é desconhecido (`PagamentoNaoEncontrado`).
- **Idempotência.** Primeiro a leitura da chave; sem ela, a inserção dentro de um savepoint; em `IntegrityError` (outra conexão criou a mesma chave), relê a existente. "Mesmos dados" compara referência, valor, descrição, meio e `expira_em`. A chave existente é devolvida mesmo que o `expira_em` já tenha passado (a repetição de uma criação antiga não vira `expiracao_invalida`).
- **Plano no processo, incluindo o atraso de consistência.** O plano guarda a situação anterior à última mudança (gravada em toda mudança) e as consultas atrasadas restantes; a consulta consome uma só quando há situação anterior para mostrar. A criação e o cancelamento devolvem sempre o estado real do provedor.
- **`aprovar_no_cancelamento`** é guardado no plano (processo), como o resto dos controles de teste; sem `em`, aprova em `agora()` no cancelamento. `em` anterior a `criado_em` é `ValueError` já na chamada.
- **Controles de situação** não passam pelo plano de falhas; só as cinco operações da interface passam.
- **`entregar_avisos`:** o receptor é um parâmetro obrigatório até a E07-05; sem ele, `RuntimeError`. O contador `entregas` sobe depois de cada chamada ao receptor.
- **Segredo sem padrão em `base.py`;** o simulador recusa assinar ou verificar com segredo vazio (`RuntimeError`). A decisão para `prod.py` é da E07-02.
- **Log:** `"Simulador de pagamentos: <operação> <id_externo>"` em `apps.simulador_pagamentos`; a busca por referência não registra a referência.

## Conflito do critério A-4 com a regra de `em`

O A-4 aprova a "cobrança do A-1" (criada às 13:00) com `em` = 12:59:30, mas a regra de `aprovar` e o A-5 mandam `ValueError` quando `em` é anterior a `criado_em`. O teste cria a cobrança às 12:50 e aprova em 12:59:30 com o relógio em 13:10, que preserva o que o critério quer provar (aprovação informada depois, com `em` no passado, `consultado_em` 13:10). Registro para o especificador; nenhum teste foi enfraquecido.

## Mapeamento dos critérios

Ver a tabela do Red: cada critério tem os testes listados, todos no `test_pagamentos_simulador.py`, exceto A-15 (`test_pagamentos_concorrencia.py`) e A-16 (`test_pagamentos_fronteiras.py`). Os marcadores `acceptance` ficam no A-1.

## Limites da verificação

Postgres real, sem rede. O simulador não foi exercitado por um worker como processo separado. A mutação não foi aplicada nesta fatia. Os receptores dos avisos (E07-05), o registro dos pagamentos (E07-03) e a configuração por ambiente (E07-02) são de outras fatias.


---

## Correções E07-R03, R04 e R05 e ajuste do A-4 — registro do implementador (2026-10-20)

Status: correções implementadas; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: este parecer, `spec.md` e `acceptance.md` desta fatia (seção "Correção E07-R03, R04 e R05 e ajuste do A-4", A-19 a A-22), as seções de correção das E07-04 e E07-05 e as provas do revisor.

### Arquivos

- **R03:** `config/settings/base.py` (alias `simulador_pagamentos`, cópia profunda de `default`, e `DATABASE_ROUTERS`), `apps/simulador_pagamentos/roteador.py` (novo), `apps/simulador_pagamentos/provedor.py` e `controle.py` (`transaction.atomic(using=ALIAS)` em toda operação com mais de uma instrução ou `select_for_update`). Sem migração nova.
- **R04:** `apps/pagamentos/provedor.py`: `PagamentoConsultado.__post_init__` converte os quatro instantes para UTC (`somar_horas(x, 0)`; sem fuso levanta `InstanteSemFuso`).
- **R05:** `apps/pagamentos/provedor.py`: `LIMITE_ID_EVENTO`, `LIMITE_TIPO`, `LIMITE_ID_EXTERNO` e `AvisoDoProvedor.__post_init__`; `apps/pagamentos/models.py` (`AvisoRecebido` usa as constantes, sem migração); `apps/simulador_pagamentos/provedor.py` (`verificar_aviso` entrega os três campos ao tipo).
- **Testes e apoio:** `test_pagamentos_simulador.py` (A-19, A-21, A-22), `test_pagamentos_fronteiras.py` (A-20), `tests/conftest.py` (gancho dos bancos), `tests/apoio/trava.py` (`outra_conexao_esperando` e `segurando(..., using=)`).

### Ciclo TDD (arquivos inteiros, sem `-k`)

**Andaime (exceção técnica):** o alias e `DATABASE_ROUTERS` em `base.py`, o roteador com métodos que devolvem `None` (sem roteamento) e o gancho de `tests/conftest.py`, para que a infraestrutura de bancos funcione antes dos testes; nenhum comportamento de roteamento existia.

**R04 e R05.** Red: `uv run pytest tests/tecnicos/test_pagamentos_simulador.py tests/tecnicos/test_pagamentos_avisos.py -q`: **15 failed, 51 passed**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-21 | `test_toda_resposta_do_simulador_vem_em_utc` | falhou: `assert ZoneInfo('America/Sao_Paulo') is timezone.utc` |
| A-21 | `test_pagamento_consultado_recusa_instante_sem_fuso` | falhou: `DID NOT RAISE InstanteSemFuso` |
| A-22 | `test_aviso_fora_do_esquema_e_invalido[id_evento\|tipo\|id_externo]` | falharam: `DID NOT RAISE AvisoInvalido` |
| A-22 | `test_verificar_aviso_recusa_corpo_assinado_fora_do_limite` | falhou: `DID NOT RAISE AvisoInvalido` |
| A-22 | `test_aviso_no_limite_com_caracteres_acentuados` | **passou no Red** (limite exato já era aceito); protege contra regressão |
| E07-05 A-17 | `test_aviso_assinado_fora_dos_limites_nao_causa_500` (11 casos) | 9 falharam (`assert 500 == 401` nos acima do limite e com `\u0000`; `assert 200 == 401` nos campos vazios); os 2 casos com número no lugar do texto **passaram** (o verificador já recusava) |
| E07-05 A-18 | `test_avisos_no_limite_exato_sao_aceitos` | **passou no Red** (controle dos limites exatos) |

O A-17 usa `Client(raise_request_exception=False)` para o 500 aparecer como `assert 500 == 401` (e não como `DataError`).

**R03.** Red: `uv run pytest tests/tecnicos -k pagamentos -q`: **5 failed, 141 passed**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-19 | `test_o_estado_do_simulador_sobrevive_ao_rollback_do_sistema` | falhou: `assert 0 == 1` (a cobrança do bloco desapareceu) |
| A-20 | `test_o_roteador_manda_o_simulador_para_a_conexao_propria` | falhou: `assert None == 'simulador_pagamentos'` |
| A-20 | `test_o_simulador_tem_conexao_propria_para_o_mesmo_banco`, `test_a_producao_tambem_declara_a_conexao_do_simulador`, `test_as_migracoes_nao_acusam_mudanca` | **passaram no Red**: o andaime já tinha o alias, o roteador declarado e nenhuma mudança de migração |
| A-15 (adaptado) | `test_a_mesma_chave_em_duas_conexoes_cria_uma_cobranca_so` | falhou (`a outra conexão não ficou esperando pela trava`): a trava do teste passou a ser a do banco do simulador, que ainda não era usado |
| E07-04 A-21 | `test_falha_local_nao_apaga_cobranca_aceita` | falhou: `assert 0 == 1` (a `CobrancaSimulada` sumiu no rollback) |
| E07-04 A-22 | `test_queda_do_processo_nao_apaga_cobranca_aceita` | falhou: `assert 0 == 1` |

### Green

`-k pagamentos`: **146 passed**. Suíte completa: **1937 passed** (eram 1902). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` (com as configurações de dev e de teste) sem erros.

### Decisões técnicas e ajustes nos testes

- **Gancho central.** `pytest_collection_modifyitems` em `tests/conftest.py` acrescenta `databases=["default", "simulador_pagamentos"]` ao marcador `django_db` dos arquivos `test_pagamentos_*.py`, preservando o resto do marcador (`transaction=True` etc.). Nenhuma asserção existente mudou.
- **A-15 da E07-01:** o teste continua o mesmo; só o meio de segurar a trava mudou: `segurando(..., using="simulador_pagamentos")` segura a transação do banco do simulador, porque a inserção dele agora se confirma na conexão própria e uma transação do sistema não a seguraria.
- **A-4:** nenhum ajuste de código (o teste já criava a cobrança às 12:50).
- **Erro de teste meu, corrigido no Green do A-21:** a terceira cobrança do teste foi criada às 13:00 e aprovada com `em` 12:59, que o simulador recusa (A-5); passou a ser criada às 12:50, como no A-4. Foi erro de preparação do teste, não um enfraquecimento.
- **`tests/apoio/trava.py`:** `esperar_outra_conexao_na_trava` foi refatorada para usar a nova `outra_conexao_esperando()`, sem mudar o comportamento; as suítes de concorrência anteriores continuam verdes.
- **`executar_em_paralelo` não mudou:** as threads fecham todas as conexões (`close_all`); a conexão do simulador, nas threads, não leva o `application_name` único da operação (só a de `default` leva). Limite registrado.
- **Produção:** o alias existe em todos os ambientes (inclusive homologação); as migrações continuam rodando só em `default`.

### Limites da verificação

Postgres real, sem rede, worker nem navegador. Nenhuma mutação aplicada nestas correções.
