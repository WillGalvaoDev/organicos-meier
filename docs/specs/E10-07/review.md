# E10-07 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Testes A-1 a A-20 (telas, avisos, seção do comprador) | `E10-07: testes A-1 a A-20` | `uv run pytest tests/tecnicos/test_devolucoes_telas.py tests/tecnicos/test_devolucoes_avisos.py tests/tecnicos/test_pedidos_estornos_do_comprador.py` | **Red: 24 failed, 2 passed.** Passam o A-14 (o outro comprador já recebia 404) e a variante do A-4 de rota inexistente para o anônimo/403 que o 404 não distingue; ambos são regressão |
| `estornos.py` (textos, aviso, seção), `devolucoes_views.py`, 5 rotas, 3 templates, link no menu, avisos nos serviços da E10-04 e E10-06 | `E10-07: avisos de estorno...` | os mesmos arquivos | **26 passed** |
| Cenários 35 e 36 pelo fluxo da tela | mesmo commit | `tests/aceitacao/test_cenarios_35_36_excepcional.py` | 4 passed |

**Correção de teste (declarada).** O A-16 foi escrito com `falhar_proximas(1, operacao="estornar")` antes de `levar_a_elegivel`, o que deixaria a parcela em `falha_temporaria` e nunca chegaria a elegível. O erro era do teste, e não do código; a linha foi removida, e o caminho real já passa pela falha definitiva (que também não avisa). Nenhuma asserção foi afrouxada.

## Decisões técnicas

- Os avisos são emitidos dentro dos serviços, na transação do fato, com a chave `estorno:<parcela>:<situação>:<conta>`. No `concluir`, o aviso vem antes da liquidação; se a liquidação levanta, a transação do `concluir` se desfaz, e o aviso também (A-20).
- As rotas ficam sob `administracao/financeiro/devolucoes/` (o prefixo do menu financeiro da E09-08).
- A lista mostra seis seções (`pendentes`, `solicitadas`, `em-processamento`, `falhas`, `elegiveis`, `concluidas`), paginadas por obrigação.
- Recusa do serviço: 409; provedor fora do ar: 503; campo ou comprovante inválido na confirmação: 400 com o formulário.

## Verificações executadas (E10 inteira, sobre o último commit)

```
uv run pytest                                 # 2600 passed in 280.09s, sem filtro
uv run ruff check . --no-cache                # All checks passed
uv run ruff format --check .                  # 347 files already formatted
uv run mypy .                                 # Success: no issues found in 415 source files
uv run python manage.py makemigrations --check --dry-run   # No changes detected
```

Antes da E10 a suíte tinha 2433 testes; a E10 acrescentou 167.

## Riscos remanescentes e limites de verificação

- A trava de cada operação (pedido, parcela, confirmação) foi escrita junto com o código funcional, sem Red da corrida (E10-04 e E10-06); só mutação, que não substitui Red.
- `verificar_estornos` com falha definitiva do provedor não é reagendada.
- A leitura da cobertura na autorização não trava a reserva.
- O armazenamento do comprovante é o do Django em desenvolvimento e teste; o R2 é da E16.
- O README (Parte 1) só será atualizado no PR para a `main`, depois da aprovação.

## Revisão independente — agente 3 — 2026-10-30

**Veredito final da E10: REPROVADO.**

Revisão da branch `e10-implementacao`, commit **`9ce04adcdb1b6186ee5c932ef38170989e4d19cf`**, contra a especificação de `cd735c3`, funcional v1.7, infraestrutura v1.8 e AGENTS.md. Foram lidas as sete especificações e respectivas matrizes antes da avaliação da implementação. Os registros do implementador acima e nas outras seis fatias foram preservados. Nenhum código de produção, teste existente ou especificação foi corrigido pelo revisor.

Há **3 bloqueadores e 7 achados importantes**, todos abertos. Não há melhoria não impeditiva nova a lançar em `docs/melhorias.md`.

| ID | Classificação | Fatias | Achado e evidência | Parecer detalhado |
|---|---|---|---|---|
| R01 | importante | 02 | Integral aceita chave de parcial diferente; não levanta `ReembolsoConflitante` | [E10-02](../E10-02/review.md) |
| R02 | importante | 03 | Dois estornos de 80,00 consomem saldo comum de 100,00; saldo final −60,00 | [E10-03](../E10-03/review.md) |
| R03 | bloqueador | 04 | Autorização e desfazer designação concluem juntas, deixando 31,25 sem cobertura | [E10-04](../E10-04/review.md) |
| R04 | bloqueador | 04/07 | Retentativa manual × worker produz `deadlock detected` | [E10-04](../E10-04/review.md) |
| R05 | importante | 04/05/06/07 | Estorno reencontrado em processamento fica sem adoção/acompanhamento e ainda é exibido como elegível | [E10-05](../E10-05/review.md) |
| R06 | importante | 06/07 | Falha somente em `consultar_estornos` propaga exceção errada, fora do tratamento HTTP 503 | [E10-06](../E10-06/review.md) |
| R07 | importante | 06 | Rollback externo deixa PDF órfão, sem confirmação no banco | [E10-06](../E10-06/review.md) |
| R08 | importante | 03/04/06 | Comportamento novo já verde no andaime e proteção concorrente sem Red específico; exceções anteriores não autorizam esta entrega | seção TDD abaixo |
| R09 | bloqueador | 04/05/06 | Estorno recusado com ID conhecido: conclusão tardia não bloqueia excepcional e, na ordem inversa, não gera alerta crítico | [E10-05](../E10-05/review.md) |
| R10 | importante | 07 | Lista omite tentativas da falha definitiva, mesmo com uma tentativa registrada | seção abaixo |

### Matriz consolidada e decisão por fatia

“Verde” descreve o teste existente executado, não uma aprovação automática do requisito. As matrizes locais detalham os casos e as extensões que falharam.

| Fatia | Matriz lida/executada na suíte existente | Decisão | Limites relevantes |
|---|---|---|---|
| E10-01 | A-1 a A-10, `test_financeiro_conciliacao.py` | APROVADO | A-7 já era verde e seu arranjo não abre o alerta antigo; limitação explicitada pelo implementador |
| E10-02 | A-1 a A-17, `test_devolucoes_reembolso.py`, concorrência, cenários 90/91/112–117 | REPROVADO | R01; A-16 determinístico só executa parcial primeiro |
| E10-03 | A-1 a A-20, `test_simulador_estornos.py` | REPROVADO | R02/R08; a corrida existente usa o mesmo pagamento |
| E10-04 | A-1 a A-25, `test_devolucoes_execucao.py`, concorrência e T-8 | REPROVADO | R03/R04/R08; R05/R09 nos estados compartilhados |
| E10-05 | A-1 a A-9, `test_financeiro_conciliacao_estornos.py` | REPROVADO | R05/R09; caso tardio existente tem ID nulo na parcela |
| E10-06 | A-1 a A-17, `test_devolucoes_excepcional.py`, concorrência, T-9, cenários 35/36 | REPROVADO | R05/R06/R07/R08/R09 |
| E10-07 | A-1 a A-20, telas, avisos, estornos do comprador e cenários 35/36 pela tela | REPROVADO | R04/R05/R06 herdados dos serviços, R10 próprio |

### E10-07 — critérios e R10

| Critérios | Resultado da revisão |
|---|---|
| A-1 | Grupos, valores, motivos e isolamento passam no arranjo existente. A informação de tentativas da falha definitiva falta: R10 |
| A-2 a A-6 | Autorização, passkey, perfis, indisponibilidade na autorização e falta de cobertura: testes verdes |
| A-7/A-8 | Retentativa e ações forjadas passam isoladamente; R04 impede aprovar a retentativa concorrente |
| A-9 a A-12 | Formulário, recusa de processamento, arquivo inválido e download privado passam; falha da segunda consulta tem R06 |
| A-13/A-14 | Seção do comprador e 404 para outro comprador: verdes; sem exposição de comprovantes/identificação bancária |
| A-15 a A-20 | Avisos, chaves, duplicidade, sem comprador e rollback interno: verdes; estado reencontrado em processamento tem R05 |

**R10 — importante.** Referências: E10-07/spec.md, conteúdo da lista nas falhas, A-1; `apps/financeiro/devolucoes_views.py:74–94`, `templates/financeiro/devolucoes.html:25–28`.

Reprodução pelo cliente Django autenticado: autorizar O1 com recusa `prazo_vencido`, executar só a chamada `estornar` (`limite=1`), confirmar estado `falha_definitiva` e abrir a lista. Resposta 200, mas sem `tentativas 1`. `_linha` só busca chamadas pendentes para solicitada/falha temporária/em processamento; uma falha definitiva nunca recebe a chamada encerrada e suas tentativas. Exibir o histórico de tentativas pertinente e distinguir ausência de nova tentativa agendada. O teste A-1 existente monta a falha por fábrica e não afirma essa informação para a falha definitiva.

### TDD — R08 (importante)

Referências: AGENTS §§3, 4 e 8; prevenção registrada nas correções E05-R04/E06-R05/E08-R06. A E08-01/review.md explicita que seu tratamento excepcional não é dispensa para outras entregas. Não foi encontrada decisão que estenda tal exceção à E10 nas especificações ou nos registros fornecidos.

| Fatia | Histórico inspecionado | Avaliação |
|---|---|---|
| 01 | `ff357ee → 19063a8` | Testes antes da alteração; A-7 corretamente declarado já verde |
| 02 | `2c8329c → ae25659`; `80c4a9b → dd57ba6` | Ciclo funcional e ciclo específico das travas separados e resultados registrados |
| 03 | `ceb68d7 → c06d379` | `NovoEstorno.__post_init__` e A-17 entram juntos: cinco casos já verdes não são regressão de comportamento anterior. A-18 tem Red de operação ausente, não corrida com operação funcional sem proteção |
| 04 | `ff92c20 → ddf8016 → 77fca2e` | A-23/A-24 entram depois da proteção, conforme declaração explícita; a mutação não demonstrou sequer a sensibilidade de A-23 à trava removida |
| 05 | `3aaf01e → fe06cbe`; A-7 em `deccdce` | Separação funcional registrada; A-8 e A-7 são ausência de efeito/regressão, sem fabricar Red |
| 06 | `1ab6ce0 → dabe910 → deccdce` | A-16 depois da trava; não conformidade declarada. A-2/A-14 já verdes são regressões legítimas |
| 07 | `9b61877 → 3e485e8` | Separação registrada; ajuste do arranjo A-16 inspecionado: retirada da falha temporária que impedia chegar à elegibilidade, preservando as asserções |

A inspeção do diff de `ddf8016` também identificou ajustes de fábrica e do arranjo sem cobertura, não uma retirada de asserção financeira. Isso não supre Red concorrente ausente. Modelos/assinaturas vazias podem ser andaime técnico; validações de entrada observáveis não são isentas automaticamente.

**Encaminhamento de R08:** preservar a história; procurar saída histórica contemporânea que comprove os ciclos faltantes. Na ausência dela, é necessária decisão específica do responsável sobre o tratamento desta não conformidade (registro, sensibilidade e prevenção, se esse for o tratamento autorizado). O revisor não aprova a extensão unilateral das exceções anteriores nem aceita mutação posterior como Red histórico. As correções dos defeitos desta revisão devem iniciar por testes que falhem pelo motivo do achado, antes da alteração correspondente.

### Verificações independentes

Suíte completa, sem filtro, executada em banco exclusivo `test_organicos_revisor_e10_9ce04ad`, com ambos os aliases (`default` e `simulador_pagamentos`) apontando para ele:

```powershell
$env:PYTHONPATH = (Get-Location).Path
uv run python "$env:TEMP/revisor_e10.py" -q -p no:cacheprovider --tb=short
# 2600 passed in 270.31s (0:04:30)
```

Conteúdo do runner (só troca o nome do banco de teste, não produção):

```python
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.test'
from django.conf import settings
for database in settings.DATABASES.values():
    database.setdefault('TEST', {})['NAME'] = 'test_organicos_revisor_e10_9ce04ad'
import pytest
sys.exit(pytest.main(sys.argv[1:]))
```

Verificações estáticas iniciais: `uv run ruff check .` (passou); `uv run ruff format --check .` (347 arquivos); `uv run mypy apps config` (228 arquivos, sem erros); `uv run python manage.py makemigrations --check --dry-run` (sem mudanças).

As reproduções complementares, em 2026-10-30, exigiram subir o contêiner local já existente com `docker compose up -d db`. As tentativas que ficaram aguardando conexão antes disso foram interrompidas e não são evidência de defeito. O primeiro arranjo concorrente de R03 precisou de transações próprias para os movimentos preparatórios; suas falhas de montagem não foram contadas como achado. Depois dessa correção no teste temporário, a execução final do arquivo inteiro produziu **10 failed in 18.07s**, todos pelo comportamento esperado ausente:

| Teste complementar | Resultado observado | Achado |
|---|---|---|
| `test_reconsulta_estornos_indisponivel` | `ProvedorIndisponivel` escapa | R06 |
| `test_adota_processamento_apos_elegibilidade` | `elegivel_excepcional != em_processamento` | R05 |
| `test_chave_parcial_nao_vira_integral` | não levanta `ReembolsoConflitante` | R01 |
| `test_rollback_externo_remove_comprovante` | um PDF permanece após rollback | R07 |
| `test_autorizacao_versus_desfazer_cobertura` | ambas concluem; sem cobertura 31,25 | R03 |
| `test_retentativa_manual_versus_worker` | PostgreSQL detecta deadlock | R04 |
| `test_saldo_compartilhado_em_estornos_concorrentes` | duas conclusões; saldo −60,00 | R02 |
| `test_estorno_identificado_recusado_que_conclui_tarde` | não levanta `DevolucaoRecusada` | R09 |
| `test_alerta_tardio_com_id_conhecido` | nenhum alerta crítico, só divergência comum | R09 |
| `test_lista_informa_tentativas_da_falha_definitiva` | HTTP 200 sem tentativas | R10 |

Limitações: os commits históricos de Red foram auditados pelo histórico, conteúdo e registros, não reexecutados; os testes adicionais são evidência atual. Sem API real, dinheiro real, R2 de produção, deploy ou push. Q-8 foi verificada no escopo da fase 1: débito simulado/consulta e divergência, sem antecipar suspensão ou lançamentos automáticos de fases reais. Os arranjos sem cobertura da suíte substituem a apuração real, como declarado pelo implementador; não são validação ponta a ponta das etapas futuras. A aprovação de interface foi feita pelo cliente Django e leitura de templates, sem inspeção visual em navegador.

**Próximo gate:** correções R01–R07/R09/R10 com TDD, tratamento específico de R08 e nova revisão independente. Nenhuma conclusão de aprovação da E10 é válida enquanto esses achados permanecem.

### Conferência final da entrega documental

Após remover somente o arquivo temporário criado pelo revisor:

- `.venv/Scripts/python.exe -m ruff check .`: passou.
- `.venv/Scripts/python.exe -m ruff format --check .`: 347 arquivos formatados.
- `.venv/Scripts/python.exe -m mypy .`: 415 arquivos, sem erros.
- `.venv/Scripts/python.exe manage.py check`: nenhum problema.
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`: nenhuma mudança.
- `git diff --check`: passou.
- Comparação programática com `git show HEAD:<review.md>`: todos os sete prefixos de registros do implementador preservados; cercas Markdown balanceadas e reprodução Python no parecer compilada sem erro de sintaxe.

A suíte completa não foi repetida depois das edições exclusivamente documentais: nenhum arquivo de produção nem teste existente mudou. A suíte verde e as reproduções vermelhas referem-se ao mesmo código `9ce04ad`.

### Reprodução preservada dos testes adicionais

Para reproduzir, copiar o bloco abaixo para `tests/tecnicos/test_devolucoes_revisao_temporaria.py` e usar o runner acima. O arquivo temporário usado nesta revisão foi removido após preservar este conteúdo; não se incorporam testes vermelhos à suíte existente neste commit de pareceres.

```powershell
.venv/Scripts/python.exe -u "$env:TEMP/revisor_e10.py" tests/tecnicos/test_devolucoes_revisao_temporaria.py -q -p no:cacheprovider --tb=short
```

```python
from decimal import Decimal as D
from datetime import timedelta
import pytest
from django.db import transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.financeiro import devolucoes as dev
from apps.financeiro import reserva
from apps.financeiro.models import ConfirmacaoDeDevolucaoExcepcional, ParcelaDeDevolucao
from apps.financeiro.reembolsos import reembolso_integral_do_pedido, ReembolsoConflitante
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.models import ChamadaAoProvedor
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.devolucoes import arranjo_da_devolucao, levar_a_elegivel, obrigacao_sem_cobertura, K, pedido_pago_com_itens, parcial
from tests.apoio.corrida import Corrida
from tests.apoio.pedidos import administrador

pytestmark = pytest.mark.django_db(transaction=True, databases=['default', 'simulador_pagamentos'])

def confirmar(a, p):
    return dev.confirmar_devolucao_excepcional(p, autor=a.admin, meio='pix', identificacao='E2E', justificativa='Devolvido', comprovante=SimpleUploadedFile('c.pdf', b'%PDF-1.4 comprovante'))

def test_reconsulta_estornos_indisponivel(relogio, simulador_pagamentos):
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    p = levar_a_elegivel(a)
    a.sim.falhar_proximas(1, operacao='consultar_estornos')
    with pytest.raises(ConsultaAoProvedorFalhou):
        confirmar(a, p)

def test_adota_processamento_apos_elegibilidade(relogio, simulador_pagamentos):
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    a.sim.recusar_mas_processar(a.pagamento.id_externo, 'meio_nao_permite_estorno')
    p = dev.autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    EstornoSimulado.objects.update(visivel=True)
    with pytest.raises(dev.DevolucaoRecusada):
        confirmar(a, p)
    processar_chamadas()
    p.refresh_from_db()
    assert p.situacao == 'em_processamento'
    assert ChamadaAoProvedor.objects.filter(operacao='acompanhar_estorno', situacao='pendente').exists()

def test_chave_parcial_nao_vira_integral(relogio):
    pedido, (item,) = pedido_pago_com_itens(K)
    parcial(item, '0.25', chave='mesma-chave', motivo='cancelamento_da_rodada')
    with pytest.raises(ReembolsoConflitante), transaction.atomic():
        reembolso_integral_do_pedido(pedido, chave='mesma-chave', motivo='cancelamento_da_rodada', autor=administrador())

def test_rollback_externo_remove_comprovante(relogio, simulador_pagamentos, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    p = levar_a_elegivel(a)
    with pytest.raises(RuntimeError), transaction.atomic():
        confirmar(a, p)
        raise RuntimeError('rollback do chamador')
    assert not ConfirmacaoDeDevolucaoExcepcional.objects.exists()
    assert not list(tmp_path.rglob('*.pdf'))

def test_autorizacao_versus_desfazer_cobertura(relogio, simulador_pagamentos, monkeypatch):
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    from tests.apoio.financeiro import custodia, obrigacao_com, mover
    from apps.financeiro.livro import saldo
    rodada, ciclo = a.pedido.abertura.rodada, a.pedido.abertura.ciclo
    ralo = obrigacao_com(rodada, ciclo, a.comprador, numero=9999)
    for componente in ('produtos', 'servico', 'frete'):
        c = custodia(rodada, ciclo, a.comprador, componente)
        with transaction.atomic():
            mover('financiamento_de_obrigacao', c, ralo, saldo(c))
    o = parcial(a.i1, '1').obrigacao
    with transaction.atomic():
        d = reserva.designar_reserva(a.admin, o, o.devido, 'Cobrir')
    corrida = Corrida()
    corrida.depois_de(monkeypatch, dev, 'sem_cobertura_da_obrigacao')
    ra, rb = corrida.rodar(lambda: dev.autorizar_devolucao(o, autor=a.admin), lambda: reserva.desfazer_designacao(a.admin, d, 'Desfazer'))
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, dev.DevolucaoRecusada), (rb.excecao, reserva.sem_cobertura_da_obrigacao(o))

def test_retentativa_manual_versus_worker(relogio, simulador_pagamentos, monkeypatch, caplog):
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    a.sim.falhar_proximas(1, operacao='estornar')
    p = dev.autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    relogio.avancar(timedelta(minutes=2))
    corrida = Corrida()
    corrida.antes_de(monkeypatch, dev, '_travar_cadeia')
    ra, rb = corrida.rodar(lambda: processar_chamadas(limite=1), lambda: dev.tentar_devolucao_de_novo(p, autor=a.admin))
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None or isinstance(rb.excecao, dev.DevolucaoRecusada), rb.excecao
    assert 'OperationalError' not in caplog.text, caplog.text


def test_saldo_compartilhado_em_estornos_concorrentes(relogio, simulador_pagamentos, monkeypatch):
    from threading import Barrier
    from tests.apoio.concorrencia import executar_em_paralelo
    from tests.apoio.pedidos import T0
    from apps.pagamentos.provedor import NovaCobranca, NovoEstorno, SaldoInsuficienteParaEstorno, obter_provedor
    from apps.simulador_pagamentos.plano import PLANO
    sim = simulador_pagamentos
    relogio.congelar(T0)
    provedor = obter_provedor()
    ids=[]
    for n in range(2):
        c=provedor.criar_cobranca(NovaCobranca(f'c{n}', f'r{n}', D('80.00'), 'Pedido', T0+timedelta(days=1)))
        sim.aprovar(c.pagamento.id_externo)
        ids.append(c.pagamento.id_externo)
    sim.registrar_saida(D('60.00'), descricao='saida')
    assert provedor.consultar_saldo().liberado == D('100.00')
    encontro=Barrier(2)
    original=PLANO.consumir_recusa_mas_processa
    def pausar(pk):
        result=original(pk)
        encontro.wait(timeout=10)
        return result
    monkeypatch.setattr(PLANO, 'consumir_recusa_mas_processa', pausar)
    def op(n):
        def executar(b):
            b.wait(timeout=10)
            return provedor.estornar(NovoEstorno(ids[n], D('80.00'), f'k{n}'))
        return executar
    resultados=executar_em_paralelo(op(0),op(1))
    assert sum(isinstance(r.excecao, SaldoInsuficienteParaEstorno) for r in resultados)==1, (resultados, provedor.consultar_saldo().liberado)

def test_estorno_identificado_recusado_que_conclui_tarde(relogio, simulador_pagamentos, settings, tmp_path):
    settings.MEDIA_ROOT=tmp_path
    a=arranjo_da_devolucao(simulador_pagamentos, relogio)
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    p=dev.autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    e=EstornoSimulado.objects.get()
    a.sim.recusar_estorno(e.id_estorno, 'estado_invalido')
    processar_chamadas()
    p.refresh_from_db()
    assert p.situacao == 'elegivel_excepcional'
    assert p.id_estorno == e.id_estorno
    # Dublê da conclusão tardia depois de recusa definitiva, com ID já conhecido.
    EstornoSimulado.objects.filter(pk=e.pk).update(situacao='em_processamento')
    a.sim.concluir_estorno(e.id_estorno)
    with pytest.raises(dev.DevolucaoRecusada):
        confirmar(a,p)

def test_alerta_tardio_com_id_conhecido(relogio, simulador_pagamentos, settings, tmp_path):
    from apps.financeiro.models import AlertaFinanceiro
    from apps.financeiro.conciliacao import conciliar_dia, limites_do_dia
    from datetime import date
    settings.MEDIA_ROOT=tmp_path
    a=arranjo_da_devolucao(simulador_pagamentos, relogio)
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    p=dev.autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    e=EstornoSimulado.objects.get()
    a.sim.recusar_estorno(e.id_estorno, 'estado_invalido')
    processar_chamadas()
    confirmar(a,p)
    EstornoSimulado.objects.filter(pk=e.pk).update(situacao='em_processamento')
    a.sim.concluir_estorno(e.id_estorno)
    dia=date(2026,11,2)
    relogio.congelar(limites_do_dia(dia)[1]+timedelta(hours=1))
    conciliar_dia(dia)
    assert AlertaFinanceiro.objects.filter(tipo='devolucao_concluida_tardiamente', chave=e.id_estorno, resolvido_em=None).exists()

def test_lista_informa_tentativas_da_falha_definitiva(client, webauthn, relogio, simulador_pagamentos):
    from tests.apoio.devolucoes import montar_tela
    a, _ = montar_tela(client, simulador_pagamentos, relogio)
    a.sim.recusar_estornos(a.pagamento.id_externo, 'prazo_vencido')
    p = dev.autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    p.refresh_from_db()
    assert p.situacao == 'falha_definitiva'
    resposta=client.get('/administracao/financeiro/devolucoes/')
    assert resposta.status_code == 200
    assert 'tentativas 1' in resposta.content.decode()

```

## Correções da revisão — agente 2 — 2026-10-30

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Testes A-21 a A-23 | `085ccd8` | `tests/tecnicos/test_devolucoes_telas.py`, `tests/tecnicos/test_pedidos_estornos_do_comprador.py` | **Red: A-21** (sem `tentativas 1`). **Red tardio declarado:** A-22 e A-23 foram escritos depois da correção dos serviços (R05/R06 vieram antes na ordem pedida); o Red foi conferido contra o código de produção anterior (`44727d1`): A-22 `ProvedorIndisponivel`, A-23 `'elegivel_excepcional' == 'em_processamento'` |
| `_acompanhamento_da_falha` (tentativas das chamadas `estornar` e `acompanhar_estorno`; próxima, reconsulta agendada ou sem nova tentativa) na lista e no detalhe | `7a7ff5a` | os mesmos e `test_devolucoes_avisos.py` | 29 passed; o detalhe teve Red próprio antes do template |

## Verificação final consolidada da correção (E10-R01 a R10)

```
uv run pytest                                 # 2627 passed in 294.47s, sem filtro
uv run ruff check . --no-cache                # All checks passed
uv run ruff format --check .                  # 347 files already formatted
uv run mypy .                                 # Success: no issues found in 416 source files
uv run python manage.py makemigrations --check --dry-run   # No changes detected
```

Provas do parecer (arquivo temporário, não commitado): 8 das 10 passam. `test_saldo_compartilhado_em_estornos_concorrentes` foi substituída pelo E10-03 A-21 (a barreira esgota o tempo, como a spec previu). `test_retentativa_manual_versus_worker` falha só pelo arranjo (ver "Ponto para o revisor" na E10-04); sem a transação externa em B, passa.

Riscos remanescentes: a decisão acima; `verificar_estornos` que falha de forma definitiva no provedor não é reagendada; armazenamento do comprovante local até a E16.

## Complemento das correções (P2 e tela do P4) — agente 2 — 2026-10-30

**P2 — Red tardio do A-22 e do A-23 (E10-R08).** Sequência real dos commits: as correções de serviço R06 (`ee375bd`) e R05 vieram antes dos testes de tela (`085ccd8`), porque a ordem pedida punha R05/R06 antes de R10. Não houve Red antes do código de produção desses dois critérios. Nenhum código foi revertido.

**Sensibilidade (execução contra o código anterior), não Red.** Comando, com os dois arquivos inteiros e sem `-k`, executado em um worktree descartável com o código de produção de `44727d1` e os testes do commit atual:

```
uv run pytest tests/tecnicos/test_devolucoes_telas.py tests/tecnicos/test_pedidos_estornos_do_comprador.py
# 4 failed, 20 passed
```

- A-22 (`test_consulta_de_estornos_fora_do_ar_na_confirmacao_responde_503`): `apps.pagamentos.provedor.ProvedorIndisponivel: falha simulada do provedor` (500 em vez de 503).
- A-23 (`test_estorno_adotado_em_processamento_aparece_em_processamento`): `assert 'elegivel_excepcional' == 'em_processamento'`.
- Falharam também, pela ausência de tentativas na tela, o A-21 (`'tentativas 1'` ausente) e o teste do P4 abaixo.

No código atual: `test_devolucoes_telas.py` e `test_pedidos_estornos_do_comprador.py` passam (suíte completa verde). O worktree foi removido.

**P4 — regra de tela.** O detalhe da falha definitiva com a reconsulta pendente mostra "reconsulta: <último erro> · tentativas N". O teste `test_detalhe_da_falha_definitiva_mostra_o_erro_e_as_tentativas_da_reconsulta` teve Red antes do código (o texto não aparecia, no `uv run pytest tests/tecnicos/test_devolucoes_telas.py`), e passa depois (`_acompanhamento_da_falha` devolve a chamada de reconsulta; `devolucao.html`). Commit `1634081`. A lista continua com "reconsulta agendada".

## Verificação final do complemento

```
uv run pytest                                 # 2633 passed in 350.78s, sem filtro
uv run ruff check . --no-cache                # All checks passed
uv run ruff format --check .                  # 347 files already formatted
uv run mypy .                                 # Success: no issues found in 416 source files
uv run python manage.py makemigrations --check --dry-run   # No changes detected
```

Provas do parecer (arquivo temporário, não commitado): 9 passam e 2 falham, as duas substituídas pela spec: `test_saldo_compartilhado_em_estornos_concorrentes` (E10-03 A-21) e `test_retentativa_manual_versus_worker` (E10-04 A-29; a operação B recebe `RuntimeError` da guarda, A-31).

Riscos remanescentes: a parcela em `verificacao_inconclusiva` fica sem reconsulta pendente (ver E10-04); armazenamento do comprovante local até a E16.
