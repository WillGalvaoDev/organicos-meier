# E06 — Parecer independente do agente 3 — 2026-10-19

**Veredito global: REPROVADO.** Base examinada: `main`, commit `2fbf143d082b37a1e8333a0736a310008e10e9ad` (PR #76). A aprovação local de uma fatia abaixo não aprova a entrega integrada. R01 é bloqueador; R02, R04 e R05 são importantes e impedem atender ao contrato de pronto; R03 é melhoria de conformidade do registro de auditoria.

## Fontes, escopo e matriz

Lidos os documentos-base (funcional v1.6, especialmente §§5, 6.3, 7, 12, 13 e 15; infraestrutura v1.7, especialmente 4.10 e 5), AGENTS.md e os sete pares spec.md/acceptance.md antes de avaliar a implementação. Conferidos serviços, modelos/migração, avisos, tarefa periódica, consultas, formulários, views, templates, testes e registros Red/Green. A revisão abrange a E06 inteira, incluindo autorização, fronteira temporal, integridade, concorrência, idempotência, rollback e regressões.

| Fatia / critérios examinados | Parecer da fatia | Resultado da revisão |
|---|---|---|
| E06-01 A-1 a A-14 | APROVADO | Início administrativo, mínimo elegível, ciclo/condições, prazo de 24h, histórico e transação. A integração da leitura com retorno é objeto de R01 nas fatias 03/07. |
| E06-02 A-1 a A-8 | APROVADO | Destinatários com reserva positiva, canais, consentimento, unicidade por ciclo e atomicidade dos avisos. |
| E06-03 A-1 a A-9 | REPROVADO | Fronteira e ações sob trava passam; R01 na consulta sem trava usada pelas páginas. |
| E06-04 A-1 a A-11 | APROVADO | Extensão antes do vencimento, prazo estritamente posterior, histórico e autorização passam; melhoria R03 na representação da auditoria. |
| E06-05 A-1 a A-16 | REPROVADO | Encerramento, remoção FIFO, idempotência, isolamento das falhas e concorrência passam; R05 no gate obrigatório de TDD. |
| E06-06 A-1 a A-12 | REPROVADO | Retorno automático e destinatários explícitos passam; R04 viola o contrato do argumento omitido. |
| E06-07 A-1 a A-14 | REPROVADO | Permissões, respostas, visibilidade e consultas passam nos testes existentes; R01 e R02 descobertos na revisão. |

A matriz registra avaliação dos critérios e regras associadas; não afirma que os testes existentes cobrem as lacunas encontradas. Ajustes de preparação dos testes antigos para criar ciclos/prazos e o uso de um mínimo distinto do subtotal no teste de privacidade são compatíveis com os requisitos; não foram tratados como afrouxamento de assertivas. Testes de concorrência usam mínimo positivo baixo para preservar a restrição do banco.

## Verificação executada pelo revisor

- `uv run pytest -q`: **1772 passed in 186.18s**, PostgreSQL de testes. Log local: `%TEMP%/om_e06_2fbf143_suite.log`.
- `uv run ruff check .`: **All checks passed!**
- `uv run ruff format --check .`: **229 files already formatted**.
- `uv run mypy .`: **Success: no issues found in 265 source files**.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: **No changes detected**.
- Provas independentes reproduzíveis abaixo: `uv run pytest -c pyproject.toml "$env:TEMP/test_review_e06_2fbf143.py" -q --tb=short`: **7 failed, 8 passed**, execução inicial 4.45s e confirmação 3.51s. Sete falhas: duas de R01, três de R02, uma de R03 e uma de R04. Os oito controles aprovados cobrem destinatários explícitos, prazo em -1/0/+1 ms e quatro totais com remoção FIFO/idempotência (18, 23, 24, 25; múltiplo 12).

Nenhum código de produção ou teste versionado foi alterado pelo revisor. As provas adicionais foram executadas em arquivo temporário; seu conteúdo está preservado neste parecer. Não houve dinheiro real, navegador ou execução do worker como processo separado: a suíte verifica o registro da tarefa e executa a rotina. R01 é uma intercalação determinística entre leituras, usando o serviço real de encerramento, não um teste com duas threads. As concorrências versionadas integram a suíte completa. E08/E11 e integrações de fases posteriores permanecem fora do escopo.

## Achados

### R01 — BLOQUEADOR — Retorno legítimo ao interesse provoca erro 500 no carrinho e no catálogo

Referências: E06-03 (consulta `aceita_interesses`), E06-06 (retorno ao interesse), E06-07 (carrinho/catálogo), funcional §§7, 13 e 15. Código: `apps/rodadas/condicoes.py:82`, `apps/rodadas/fechamento.py:125`, `apps/interesses/consultas.py:142` e `apps/interesses/apresentacao.py:145`.

`aceita_interesses` observa `rodada.etapa` no objeto já carregado, mas `prazo_do_fechamento` relê a etapa no banco. Se o encerramento devolver a rodada ao interesse entre as leituras, a primeira etapa continua sendo fechamento e a segunda consulta devolve `None`. O resultado é `RuntimeError: rodada em fechamento sem prazo gravado`, embora exista histórico válido e a transição seja legítima.

Reprodução: iniciar fechamento com 10 unidades a R$ 10 e mínimo R$ 100; baixar preço para R$ 9; no vencimento, intercalar `encerrar_fechamento` entre a leitura da rodada pela página e `aceita_interesses`. GET `/carrinho/` e `/catalogo/<fornecedor>/` falham. A prova usa monkeypatch apenas no ponto da intercalação e executa a transição real.

Correção esperada: tornar coerentes as leituras da etapa e do prazo, ou reler/repetir a decisão após a mudança de etapa. Preservar a detecção de fechamento realmente sem prazo; não mascarar toda exceção como interesse permitido. Cobrir ambas as páginas e manter os testes de ações concorrentes e fronteira temporal.

### R02 — IMPORTANTE — Prorrogação aceita entradas fora do formato e do fuso definidos

Referência: E06-07, regra “Campo do novo prazo” e contrato POST. Código: `apps/rodadas/forms.py:29`, consumo do formulário em `fechamento_prorrogar`.

`DateTimeField(input_formats=["%Y-%m-%dT%H:%M"])` não restringe o parser ISO do Django. As três entradas `2026-11-04`, `2026-11-04T01:30:59` e `2026-11-04T01:30:00+00:00` são aceitas. A segunda preserva segundos 59; a terceira preserva UTC, em vez da interpretação America/Sao_Paulo exigida. O serviço recebe esse instante sem uma nova validação do formato.

Correção esperada: validar integralmente `AAAA-MM-DDTHH:MM` no servidor e converter em America/Sao_Paulo com segundos zero. Entradas fora do contrato devem seguir a resposta 200 de erro de formulário, conservar o texto escapado e não gravar prazo. As provas desta revisão exercitam o formulário; acrescentar também a regressão no POST.

### R03 — MELHORIA — Campo `novo` da auditoria não é normalizado em UTC

Referência: E06-04, regra 7; infraestrutura §5. Código: `apps/rodadas/fechamento.py:174`.

Prorrogar com `2026-11-04T01:30:00-03:00` grava esse texto em `alteracoes['novo']`, enquanto o contrato pede ISO 8601 em UTC (`2026-11-04T04:30:00+00:00`). A validação via `somar_horas(..., 0)` não aproveita o retorno normalizado. O instante é equivalente e não há evidência de deslocamento do prazo no banco; o desvio é a representação do registro auditável. Normalizar antes de serializar e cobrir entrada com fuso não UTC. Este achado isolado não reprovaria a entrega.

### R04 — IMPORTANTE — Destinatários padrão são capturados depois da alocação da fila

Referência: E06-06, decisão dos destinatários: “Chamado sem `destinatarios`, o serviço usa os compradores com reserva no momento da chamada.” Código: `apps/rodadas/fechamento.py:361-363`.

`voltar_para_interesse` primeiro chama `alocar_pendentes` e só depois resolve os destinatários omitidos. Com A já reservado e B apenas pendente na entrada, o retorno aloca B e envia o aviso a A e B; o conjunto contratado para esse argumento é somente A. A prova prepara o estado de entrada do auxiliar e o chama dentro de transação, conforme sua interface.

Limite do impacto: `encerrar_fechamento` passa participantes explicitamente, antes de remover excedentes; esse caminho principal está correto, inclusive no controle independente. O defeito está na modalidade pública com argumento omitido. Capturar o conjunto padrão antes de alocar e manter inalterado o comportamento com destinatários explícitos.

### R05 — IMPORTANTE — Três critérios da E06-05 sem Red observado antes do código

Referências: AGENTS.md §§3, 4 e 8; introdução TDD de E06-05/acceptance.md; registro “Ciclo TDD” de E06-05/review.md.

O próprio registro informa que o filtro excluiu A-8 (prazo/idempotência), A-12 (rollback do aviso) e A-13 (prorrogação adia encerramento) no Red inicial. A execução com andaime restaurado ocorreu depois do Green e é corretamente identificada pelo implementador como não histórica. Portanto, comprova sensibilidade dos testes, mas não a sequência exigida para esses comportamentos. A suíte verde atual não elimina essa desconformidade. Eventual tratamento excepcional anterior da E05 não autoriza automaticamente exceção na E06.

Encaminhamento: preservar o registro factual e submeter o tratamento desta quebra de processo ao responsável pelo projeto, sem reconstruir um Red histórico fictício. As correções desta revisão devem registrar testes novos falhando antes do código correspondente. Para aprovação é necessário resolver o gate de processo conforme o contrato, além das correções funcionais; repetir agora o teste com código removido não reconstitui a ordem histórica.

## Próximo gate

Devolver ao implementador R01, R02 e R04, com Red/Green verificável e regressão da suíte; tratar R03; obter tratamento explícito de R05 pelo responsável pelo contrato. Depois, revisão independente das correções e novo veredito. A E06 não está pronta para encerramento neste commit.

## Provas independentes completas

Salvar o bloco abaixo como `$env:TEMP/test_review_e06_2fbf143.py` e executar o comando registrado acima a partir da raiz, com o mesmo ambiente PostgreSQL dos testes do projeto. São provas da revisão, não mudanças nos testes da implementação.

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from zoneinfo import ZoneInfo
import pytest
import time_machine
from django.db import transaction
from django.test import Client
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.interesses.servicos import adicionar_interesse, interesse_do_comprador
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.fechamento import iniciar_fechamento, encerrar_fechamento, prorrogar_fechamento, prazo_do_fechamento, voltar_para_interesse
from apps.rodadas.models import Rodada, Etapa
from apps.catalogo.servicos import editar_produto
from tests.apoio.interesses import cenario, pendente
from tests.fabricas import ContaFactory

T0=datetime(2026,11,2,13,30,tzinfo=UTC)
T=T0+timedelta(hours=24)

def montar():
    r,p,e=cenario('20',preco=D('10'))
    Fornecedor.objects.filter(pk=r.fornecedor_id).update(minimo=D('100'))
    a=ContaFactory.create()
    admin=Conta.objects.get(papel='administrador')
    adicionar_interesse(a,p,'10')
    iniciar_fechamento(admin,r)
    return r,p,a,admin

@pytest.mark.django_db
@pytest.mark.parametrize('origem',['carrinho','catalogo'])
def test_leitura_durante_retorno_nao_causa_500(monkeypatch,origem):
    with time_machine.travel(T0,tick=False):
        r,p,a,admin=montar()
        editar_produto(admin,p,preco='9')
        c=Client(); c.force_login(a)
    from apps.interesses import consultas, apresentacao
    modulo=consultas if origem=='carrinho' else apresentacao
    original=modulo.aceita_interesses
    def entre_leituras(rodada,instante):
        encerrar_fechamento(r)
        assert Rodada.objects.get(pk=r.pk).etapa==Etapa.INTERESSE
        return original(rodada,instante)
    monkeypatch.setattr(modulo,'aceita_interesses',entre_leituras)
    with time_machine.travel(T,tick=False):
        # Renova a sessão no instante da leitura para não testar expiração de login.
        c.force_login(a)
        resposta=c.get('/carrinho/' if origem=='carrinho' else f'/catalogo/{r.fornecedor_id}/')
        assert resposta.status_code==200

@pytest.mark.django_db
@pytest.mark.parametrize('texto',['2026-11-04','2026-11-04T01:30:59','2026-11-04T01:30:00+00:00'])
def test_formato_do_prazo_restrito_ao_contrato(texto):
    from apps.rodadas.forms import FormularioProrrogacao
    form=FormularioProrrogacao({'termino':texto})
    assert not form.is_valid(), form.cleaned_data

@pytest.mark.django_db
def test_prorrogacao_audita_utc():
    with time_machine.travel(T0,tick=False):
        r,p,a,admin=montar()
        novo=datetime(2026,11,4,1,30,tzinfo=ZoneInfo('America/Sao_Paulo'))
        prorrogar_fechamento(admin,r,novo)
        entrada=EntradaAuditoria.objects.get(acao='rodada.prorrogar_fechamento')
        assert entrada.alteracoes['novo']==novo.astimezone(UTC).isoformat(),entrada.alteracoes

@pytest.mark.django_db
@pytest.mark.parametrize('explicitos',[False,True])
def test_destinatarios_do_retorno_antes_da_alocacao(explicitos):
    with time_machine.travel(T0,tick=False):
        r,p,a,admin=montar()
        b=ContaFactory.create(); pendente(b,p,2)
        Rodada.objects.filter(pk=r.pk).update(etapa=Etapa.FECHAMENTO_ENCERRADO)
        with transaction.atomic():
            voltar_para_interesse(r,motivo='minimo_nao_atingido',**({'destinatarios':[a]} if explicitos else {}))
        assert interesse_do_comprador(b,p).reservado==2
        destinatarios=set(Notificacao.objects.filter(evento='retorno_para_interesse').values_list('conta_id',flat=True))
        assert destinatarios=={a.pk},destinatarios

@pytest.mark.django_db
@pytest.mark.parametrize('delta',[-1,0,1])
def test_fronteira_independente(delta):
    from apps.interesses.servicos import reduzir_interesse
    from apps.rodadas.condicoes import InteressesBloqueados
    with time_machine.travel(T0,tick=False): r,p,a,admin=montar()
    with time_machine.travel(T+timedelta(milliseconds=delta),tick=False):
        if delta<0:
            reduzir_interesse(a,p,'1')
            assert interesse_do_comprador(a,p).reservado==9
        else:
            with pytest.raises(InteressesBloqueados): reduzir_interesse(a,p,'1')
            assert interesse_do_comprador(a,p).reservado==10

@pytest.mark.django_db
@pytest.mark.parametrize('total',[18,23,24,25])
def test_encerramento_independente_fifo_e_repeticao(total):
    with time_machine.travel(T0,tick=False):
        r,p,e=cenario(None,preco=D('10'),multiplo=D(12))
        Fornecedor.objects.filter(pk=r.fornecedor_id).update(minimo=D('100'))
        a,b=ContaFactory.create(),ContaFactory.create()
        admin=Conta.objects.get(papel='administrador')
        adicionar_interesse(a,p,'8'); adicionar_interesse(b,p,str(total-8))
        iniciar_fechamento(admin,r)
    with time_machine.travel(T,tick=False):
        resultado=encerrar_fechamento(r)
        assert resultado.etapa_final==Etapa.FECHAMENTO_ENCERRADO
        assert interesse_do_comprador(a,p).reservado==8
        assert interesse_do_comprador(b,p).reservado==(total//12)*12-8
        antes=(Notificacao.objects.count(),EntradaAuditoria.objects.count())
        assert encerrar_fechamento(r) is None
        assert antes==(Notificacao.objects.count(),EntradaAuditoria.objects.count())

```

---

## Registro anterior preservado

# E06-01 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E01-03, E03-02, E03-07 e E05-04.

## Arquivos

- `apps/rodadas/models.py`: `PrazoDoFechamento` (só inserção) e `OrigemDoPrazo`; migrações `0007_prazo_do_fechamento` e `0008_restricoes_do_prazo` (trigger de só inserção, `UNIQUE` parcial do `inicio` por ciclo e `CHECK` de origem).
- `apps/rodadas/fechamento.py` (novo): `iniciar_fechamento`, `prazo_do_fechamento`, `TransicaoRecusada`, `HORAS_DO_FECHAMENTO`.
- `tests/apoio/trava.py` (novo): `segurando` e `esperando` para os testes de trava, com espera de prazo e falha por asserção.
- Testes: `tests/tecnicos/test_rodadas_fechamento_inicio.py` (A-1 a A-10), `tests/tecnicos/test_rodadas_fechamento_concorrencia.py` (A-12 a A-14) e os ajustes de A-11 em `tests/apoio/ciclos.py` e `tests/tecnicos/test_rodadas_ciclos.py`.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** o modelo sem restrições nem trigger (migração `0007`), `TransicaoRecusada` e as duas funções devolvendo `None`.

**Red, critérios funcionais.** `uv run pytest tests/tecnicos/test_rodadas_fechamento_inicio.py -q`: **15 failed, 1 passed**, por asserção (`assert 'interesse' == Etapa.FECHAMENTO`, `DID NOT RAISE TransicaoRecusada/PermissionDenied/CondicoesCongeladas`, `prazo_do_fechamento` devolvendo `None`). Passou já no Red o A-4 (nada inicia sozinho), porque depende de ausência.

**Red, concorrência (A-12 a A-14), antes do código.** `uv run pytest tests/tecnicos/test_rodadas_fechamento_concorrencia.py -q`: **4 failed em 47,7 s**, contra o andaime (que não trava nada nem recusa): a segunda operação não esperou (`AssertionError('a outra conexão não ficou esperando pela trava')`) e `AssertionError: [None, None]` no A-14 (nenhuma das duas recusada). A trava usada pelo Green é a que `registrar_condicoes_do_ciclo` já tem (E03-07); não escrevi trava nova.

**Green.** Os dois arquivos: **20 passed**. Suíte completa: **1686 passed** (eram 1666). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- `iniciar_fechamento` exige o administrador; chama `registrar_condicoes_do_ciclo` (que trava fornecedor, rodada, produtos e estoques) e traduz `CondicoesCongeladas` em `TransicaoRecusada`; relê a rodada com o fornecedor **depois** da trava e confere `progresso_da_rodada(...).atingido`; grava `fechamento`, o prazo (`somar_horas(ciclo.iniciado_em, 24)`) e a auditoria `rodada.iniciar_fechamento`. Qualquer recusa desfaz a transação inteira.
- `prazo_do_fechamento` lê a etapa do banco (não confia no objeto recebido) e devolve o maior `termina_em` do ciclo vigente.

## A-11: ajustes nos testes da E03-07

Autorizados pela spec: `simular_inicio_do_fechamento` (`tests/apoio/ciclos.py`) agora chama `iniciar_fechamento` com o administrador; `_cenario()` ganhou uma parcela de 30 de `Q` (R$ 300,00).

**Fora da lista autorizada, com decisão do responsável nesta sessão ("só acrescentar preparação"):** dois outros testes de `test_rodadas_ciclos.py` deixavam de passar porque o serviço real recusa o início sem mínimo atingido. Só acrescentei preparação; nenhuma asserção mudou:
- `test_rodada_sem_produtos_registra_ciclo_sem_condicoes`: o mínimo passa a R$ 0,00 (o banco recusa zero, então a restrição `fornecedor_minimo_positivo` sai dentro do teste e volta com o rollback);
- `test_ciclos_de_outra_rodada_do_mesmo_fornecedor_tem_numeracao_propria`: `Q` entra no estoque da rodada nova, para o mínimo ser atingido.
O revisor deve conferir o diff desses dois arquivos.

## Decisões técnicas

- **A-7, mínimo zero.** O banco não aceita mínimo zero; o teste tira a restrição só na própria transação (rollback desfaz), para exercitar o critério como escrito.
- **Mínimo lido sob trava.** A conferência usa a rodada relida com o fornecedor (e não o objeto do chamador, que pode estar defasado).
- **Instante do prazo = instante do ciclo** (`ciclo.iniciado_em`), como a spec manda.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_inicio_registra_ciclo_prazo_de_24_horas_e_auditoria` (`acceptance`, cenário 5) |
| A-2 | `test_minimo_nao_conta_pendentes` (`acceptance`, cenário 104) |
| A-3 | `test_so_conta_a_quantidade_em_caixas_completas` |
| A-4 | `test_atingir_o_minimo_nao_inicia_nada_sozinho` (`acceptance`, cenário 4) |
| A-5 | `test_so_o_administrador_inicia` |
| A-6 | `test_rodada_ja_em_fechamento_nao_inicia_de_novo`, `test_rodada_em_pagamento_nao_inicia`, `test_sem_rodada_ativa_nao_inicia` |
| A-7 | `test_exatamente_no_minimo_e_aceito`, `test_minimo_zero_sem_reservas_e_aceito` |
| A-8 | `test_prazo_vale_24_horas_corridas_mesmo_de_madrugada` |
| A-9 | `test_condicoes_congeladas_mas_o_preco_continua_editavel` |
| A-10 | `test_prazo_so_aceita_insercao`, `test_uma_so_linha_de_inicio_por_ciclo` |
| A-11 | `tests/tecnicos/test_rodadas_ciclos.py` (17 passed) |
| A-12 | `test_reducao_que_confirma_antes_derruba_o_minimo`, `test_inicio_que_confirma_antes_aceita_a_reducao_no_fechamento` |
| A-13 | `test_alteracao_de_minimo_depois_do_inicio_e_recusada` |
| A-14 | `test_dois_inicios_simultaneos_so_um_confirma` |

## Limites da verificação

Serviços e Postgres reais, sem navegador. O aviso aos compradores (E06-02), o bloqueio das ações pelo prazo (E06-03), a prorrogação (E06-04), o encerramento (E06-05/06) e as telas (E06-07) são de outras fatias. Nenhuma mutação foi aplicada nesta fatia: o Red dos critérios de concorrência foi observado contra o andaime.
