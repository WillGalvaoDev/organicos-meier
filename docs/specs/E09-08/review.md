# E09 — Revalidação independente das correções sobre 2930ffd

**Veredito final: REPROVADO.** Oito achados anteriores foram encerrados no alcance descrito abaixo. R07 está parcialmente corrigido e há um novo achado importante, R10, na guarda de travas. A E09 ainda não atende à Definition of Done.

Revisão independente de 2026-10-22, base `2930ffddc8fc53ad21c6bb777719b19508d1a4da` (branch `e09-implementacao`). Foram conferidos os adendos de especificação e aceitação em `6dc9850`, o commit de testes Red `e3733ad`, os diffs das correções e os registros de implementação. O histórico anterior permanece integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2418 passed in 234.26s**, sem filtro; `uv run ruff check .` passou; `uv run ruff format --check .` → 329 arquivos; `uv run mypy .` → 393 arquivos sem erros; `uv run python manage.py makemigrations --check --dry-run` → nenhuma alteração pendente. Provas adicionais: **4 failed, 9 passed in 9.77s**. Reprodução completa, limites e veredito global no [parecer consolidado](../E09-08/review.md).

## Resultado por achado

| Achado | Resultado desta revisão | Evidência |
|---|---|---|
| R01 — cobertura duplicada | Encerrado | destino e fontes travados antes do pendente; A-20–A-22 da E09-06 e prova independente verdes |
| R02 — designação versus liquidação | Defeito original encerrado | ordem comum por PK; A-16/A-17 da E09-05 e prova independente verdes; a guarda introduzida tem o novo R10 |
| R03 — referência concorrente | Encerrado | referência revalidada sob trava; A-23 e prova independente verdes |
| R04 — frete coberto omitido | Encerrado | componente fora do financiamento pela regra incluído; A-25/A-26 e prova independente verdes |
| R05 — reserva sem avaliação periódica | Encerrado | avaliação própria após invariante, inclusive indisponibilidade; A-24 e prova independente verdes |
| R06 — identificação de 64 caracteres | Encerrado | chave de alerta até 80, migração e identificador integral; A-13 da E09-03, A-25 da E09-07 e prova independente verdes |
| R07 — recortes da conciliação | Parcial; permanece importante | casos originais verdes; tarifa ainda usa o instante da despesa, produzindo diferença falsa |
| R08 — TDD | Tratamento autorizado aceito | decisão expressa em E09-01/spec.md; não conformidade, mutações e novos commits Red/Green registrados; limites abaixo |
| R09 — fontes da obrigação | Encerrado | fontes candidatas travadas antes da leitura do estado; A-24 e prova independente após a leitura verdes |
| R10 — escopo da guarda | Novo, importante | três provas falham: Atomic reutilizado e rollback de savepoint |

## Matriz das fatias

As matrizes atuais têm 150 critérios; todos os testes versionados passam. Não se confunde esse resultado com a satisfação integral das regras.

| Fatia | Critérios | Veredito local |
|---|---|---|
| E09-01 | A-1–A-21 | REPROVADO: R10 |
| E09-02 | A-1–A-18 | APROVADO no escopo local, mantido |
| E09-03 | A-1–A-13, A-6 reescrito | APROVADO no escopo local |
| E09-04 | A-1–A-13 | APROVADO no escopo local |
| E09-05 | A-1–A-17 | APROVADO nos fluxos revistos; dependência compartilhada R10 pendente |
| E09-06 | A-1–A-26 | APROVADO nos fluxos revistos; dependência compartilhada R10 pendente |
| E09-07 | A-1–A-27 | REPROVADO: R07 residual |
| E09-08 | A-1–A-15 | REPROVADO na integração; conciliação ainda mostra divergência falsa |

M-8 continua editorial, conforme decisão do especificador: o valor de mil reais é digitado `1000,00`, sem separador de milhar. Não se alterou o formulário nem o critério nesta revisão. Mantidos os demais registros de melhorias; aceito M-6 encerrado segundo o tratamento aprovado da R08.

## R07 residual — importante — tarifa pareada pela data da despesa

Referência: E09-07/spec.md, correção E09-R07, “Sem par no livro até t”: o par da tarifa é **o movimento da tarifa**, com `momento <= t`. Código: `apps/financeiro/conciliacao.py:102`, especialmente a seleção `despesas.filter(criada_em__lte=ate)` na linha 109.

A correção separa os recortes corretamente, mas continua usando `Despesa.criada_em` como evidência de que o débito já existia no livro no instante do saldo. A criação da despesa precede `lancar` em `registrar_tarifa`; os instantes podem divergir dentro da mesma transação.

Prova `test_tarifa_pareada_pelo_instante_do_lancamento`:

1. Sincronizar um pagamento real do simulador de 125,00, com tarifa fixa de 10,00.
2. A entrada de 125,00 e a despesa nascem em T; antes do lançamento da tarifa, avançar o relógio controlado 10 segundos, sem retirar nenhuma validação/efeito. O movimento da tarifa nasce em T+10s. A prova confere os dois timestamps gravados.
3. Conciliar o dia seguinte com saldo do provedor de 115,00 referente a T+5s; os movimentos do provedor são pagamento +125,00 e tarifa −10,00, ambos em T.
4. Até T+5s, o livro tem 125,00 e ainda não tem o débito. A tarifa do provedor ainda não tem par naquele instante e explica a diferença: `115 − 125 − (−10) = 0`.

**Obtido:** `movimentos=2`, `sem_par=0`, `diferenca=-10.00` e alerta `saldo:<D>` indevido. Os movimentos já têm par na data da execução, mas isso não os torna pareados no instante do saldo. O dia é consolidado como divergente de forma imutável.

**Correção necessária:** no recorte até t, conferir o movimento efetivo da tarifa e seu timestamp, sem mudar o pareamento do dia pela situação conhecida na execução. Acrescentar o caso negativo entre a criação da despesa e o débito; também preservar o caso em que ambos precedem t. Não é decisão comercial nova.

## R10 — importante — a guarda não acompanha a vida real das travas

Referência: E09-01/spec.md, regra única de travas, guarda por transação mais externa e invariantes; E09-01 A-19/A-20. Código: `apps/financeiro/livro.py:414`, `:424` e `:438`.

`_travadas_da_transacao` identifica uma transação pela identidade do objeto `Atomic` mais externo e mantém um conjunto na conexão. Um objeto `Atomic` pode ser reutilizado: isso consta no código instalado do Django (`django/db/transaction.py`, classe Atomic) e acontece também no uso como decorador. O mesmo objeto não identifica uma nova execução de transação. Além disso, rollback de savepoint libera travas adquiridas dentro dele, mas o conjunto não é ajustado.

Três reproduções independentes em transações PostgreSQL:

| Prova | Esperado | Obtido |
|---|---|---|
| `test_guarda_reinicia_com_atomic_reutilizado` | primeiro `with escopo` trava conta maior e commita; segundo trava somente a menor, sem recusa | `OrdemDeTravasViolada` indevida, baseada na transação já encerrada |
| `test_guarda_ativa_depois_de_atomic_reutilizado` | primeira transação trava menor/maior e commita; segunda trava maior e tenta menor: deve recusar | nenhuma exceção; ambas figuram como “já travadas” por causa da transação anterior |
| `test_guarda_desconta_trava_desfeita_por_savepoint` | trava menor adquirida em savepoint e desfeita; depois trava maior; nova tentativa da menor deve recusar | nenhuma exceção, embora a trava menor tenha sido liberada |

A terceira prova inclui controle em outra conexão com `lock_timeout=500ms`: ela consegue travar a conta menor depois do rollback do savepoint. Portanto, a divergência entre o conjunto e as travas realmente retidas não é apenas uma suposição sobre o PostgreSQL.

**Impacto:** o mecanismo novo recusa uso válido e permite a inversão que deveria detectar. Não se demonstrou saída financeira duplicada nesses três cenários; demonstrou-se descumprimento da garantia de ordem e reinicialização da própria correção, com risco de reintroduzir impasses nos chamadores que reutilizam contexto/decorador ou recuperam savepoints. O deadlock original de designação/liquidação foi eliminado e não é reapresentado como se permanecesse igual.

**Correção necessária:** associar o estado à execução efetiva da transação e às travas ainda retidas após savepoints, sem usar apenas identidade de Atomic como geração. Manter o novo controle ativo e os cenários de repetição legítima de trava; não contornar removendo a guarda ou recusando formas válidas de `transaction.atomic`. Red para os três casos, Green e regressão dos fluxos financeiros existentes.

## TDD e limites de evidência

O tratamento excepcional de R08 está explicitamente decidido pelo responsável em `docs/specs/E09-01/spec.md`, correção E09-R08, e não foi inferido das decisões antigas. Os registros de não conformidade nas fatias 01/06/07 preservam a cronologia e distinguem mutação de Red. O commit `e3733ad` contém testes e apenas a exceção vazia como andaime técnico, antes dos commits de implementação `742a679`, `a66a663`, `ca616ce` e `1ad1944`. O registro informa 18 falhas/129 passes antes da correção. A-20 da guarda e os negativos que já passavam foram declarados; não se inventou Red para eles.

As mutações históricas não foram reexecutadas nesta revisão. Foi conferido o relato de trechos, comandos com arquivos inteiros, falhas e restaurações verdes. Na mutação ORM de A-2, a falha foi a exceção SQL em vez da recusa específica ORM; ela comprova a sensibilidade à retirada da proteção ORM, não uma escrita indevida no banco. A mutação SQL registra também erro de limpeza apenas sob mutação, preservado como limite. A-19 antigo não detecta retirar travas de apuração; isso continua declarado e a proteção é exercitada por A-24(ii), conforme o tratamento aprovado. O log `scratchpad/red_e09.log` citado pelo implementador não está disponível nesta árvore; a evidência acessível é o registro commitado e a sequência de commits. Nenhuma reexecução atual é apresentada como testemunho do Red histórico.

As quatro provas concorrentes antigas não foram rodadas literalmente: elas esperavam a operação concorrente concluir enquanto seguravam a trava, incompatível com a serialização corrigida. As provas adaptadas liberam a pausa quando a concorrente espera no PostgreSQL, mantendo as asserções de negócio. O frete também passou a executar cada operação em sua transação, como nas rotas reais. Em R09, o ponto de pausa independente fica depois da leitura de `_ciclo_apurado`, não na preparação das fontes. As cinco provas não concorrentes e as quatro adaptadas passaram.

Não foram alterados produção, testes versionados, regras comerciais ou critérios. Não houve integração com dinheiro/provedor real, inspeção visual em navegador ou ensaio de carga. M-8 e as demais melhorias diferidas não impedem o aceite por si mesmas; R07/R10 impedem.

## Próximo gate

Corrigir o pareamento temporal da tarifa (R07) e a vida útil do registro de travas (R10), com Red real anterior à produção. Depois executar a suíte, verificações estáticas e provas relevantes e solicitar revalidação. Os achados encerrados não precisam ser reabertos sem regressão ou nova evidência. Não há decisão comercial pendente para essas duas correções técnicas.

## Reprodução das provas desta revalidação

Salvar o bloco abaixo como `$env:TEMP/test_revisao_e09_correcao.py`, na raiz do projeto executar:

```powershell
uv run pytest "$env:TEMP/test_revisao_e09_correcao.py" -q -c pyproject.toml --tb=short
```

Resultado em 2930ffd: **4 failed, 9 passed in 9.77s**. Os testes usam serviços reais; os monkeypatches de concorrência apenas pausam e o da tarifa apenas avança o relógio antes do lançamento real. Dublês substituem somente o protocolo externo de saldo/movimentos.

<!-- INICIO_PROVAS_E09_2930FFD -->
```python
from datetime import timedelta
from decimal import Decimal as D
from threading import Barrier, Event
from types import SimpleNamespace
import pytest
from django.db import transaction
from apps.financeiro import reserva as r, obrigacoes as o, apuracao as a, conciliacao as c, invariante as inv
from apps.financeiro.livro import saldo, EXTERIOR
from apps.financeiro.models import *
from apps.financeiro.liquidez import registrar_saida
from apps.pagamentos.provedor import SaldoNoProvedor
from tests.apoio.financeiro import *
from tests.apoio.concorrencia import executar_em_paralelo
from tests.conftest import relogio, simulador_pagamentos
from apps.nucleo.auditoria import SISTEMA
pytestmark = pytest.mark.django_db(transaction=True, databases=['default', 'simulador_pagamentos'])

def test_frete_coberto(relogio, simulador_pagamentos):
    ap = montar_ap()
    pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, timedelta(hours=1))
    with transaction.atomic():
        r.registrar_aporte(ap.admin, D('100'), 'deposito', 'teste')
    with transaction.atomic():
        a.registrar_apuracao_no_livro(ap.ciclo, [ap.x], autor=SISTEMA)
    with transaction.atomic():
        desp = Despesa.objects.get(tipo=TipoDeDespesa.DEFICIT_DE_FRETE, ciclo=ap.ciclo)
    with transaction.atomic():
        r.utilizar_reserva(ap.admin, desp, D('10'), 'teste')
    with transaction.atomic():
        registrar_saida(ap.admin, tipo='pagamento_do_frete', conta=frete_de(ap.rodada), valor=D('30'), identificacao='frete', justificativa='teste')
    with transaction.atomic():
        obrig, _ = o.registrar_obrigacao_com_comprador(origem=ap.x, rodada=ap.rodada, ciclo=ap.ciclo, comprador=ap.b, pedido=ap.x, motivo='teste', produtos=D('0'), servico=D('0'), frete=D('5'))
    with transaction.atomic():
        r.designar_reserva(ap.admin, obrig, D('5'), 'teste')
    with transaction.atomic():
        o.liquidar_obrigacao(obrig, D('5'), referencia='dev-frete')
    resultado = a.frete_do_ciclo(ap.ciclo)
    assert resultado.deficit_coberto == D('15'), resultado

def test_tarefa_avalia_reserva(monkeypatch, relogio):
    relogio.congelar(T0)
    montar_mundo()
    despesa_de_tarifa('10')
    monkeypatch.setattr(inv, 'obter_provedor', lambda: SimpleNamespace(consultar_saldo=lambda: SaldoNoProvedor(D('0'), D('0'), T0, T0)))
    inv.verificar_invariante_agora()
    assert AlertaFinanceiro.objects.filter(tipo=TipoDeAlerta.RESERVA_INSUFICIENTE, resolvido_em__isnull=True).exists()

def test_identificador_64_conciliavel(monkeypatch, relogio):
    relogio.congelar(T0)
    m = montar_mundo()
    with transaction.atomic():
        r.registrar_aporte(m.admin, D('100'), 'x' * 64, 'teste')
    relogio.avancar(timedelta(days=1))
    monkeypatch.setattr(c, 'obter_provedor', lambda: SimpleNamespace(consultar_saldo=lambda: SaldoNoProvedor(D('0'), D('0'), T0 + timedelta(days=1), T0 + timedelta(days=1)), listar_movimentos=lambda *args: []))
    c.conciliar_dia(T0.date())

def test_conciliacao_respeita_referente_a(monkeypatch, relogio):
    from apps.pagamentos.provedor import MovimentoNoProvedor, TipoDeMovimentoNoProvedor as P
    from datetime import datetime, UTC
    dia = T0.date()
    inicio, fim = c.limites_do_dia(dia)
    referencia = inicio + timedelta(hours=10)
    ocorrido = inicio + timedelta(hours=12)
    relogio.congelar(fim + timedelta(hours=1))
    montar_mundo()
    mov = MovimentoNoProvedor('ajuste-tarde', P.AJUSTE, 'ajuste', D('10'), None, ocorrido, ocorrido)
    monkeypatch.setattr(c, 'obter_provedor', lambda: SimpleNamespace(consultar_saldo=lambda: SaldoNoProvedor(D('0'), D('0'), referencia, fim), listar_movimentos=lambda *args: [mov]))
    resultado = c.conciliar_dia(dia)
    assert D(resultado.resumo['diferenca']) == D('0'), resultado.resumo

def test_conciliacao_nao_parea_movimento_futuro(monkeypatch, relogio):
    from apps.pagamentos.provedor import MovimentoNoProvedor, TipoDeMovimentoNoProvedor as P
    dia = T0.date()
    inicio, fim = c.limites_do_dia(dia)
    relogio.congelar(inicio + timedelta(hours=12))
    m = montar_mundo()
    with transaction.atomic():
        r.registrar_aporte(m.admin, D('100'), 'futuro', 'teste')
    instante = fim + timedelta(hours=2)
    ocorrido = fim + timedelta(hours=1)
    relogio.congelar(instante)
    mov = MovimentoNoProvedor('futuro', P.DEPOSITO, 'deposito', D('100'), None, ocorrido, ocorrido)
    monkeypatch.setattr(c, 'obter_provedor', lambda: SimpleNamespace(consultar_saldo=lambda: SaldoNoProvedor(D('100'), D('0'), instante, instante), listar_movimentos=lambda *args: [mov]))
    resultado = c.conciliar_dia(dia)
    assert resultado.resumo['sem_par'] == 1, resultado.resumo
from apps.financeiro.livro import _travar_conta, OrdemDeTravasViolada

def duas_contas():
    pequena = reserva()
    grande = despesas()
    assert pequena.pk < grande.pk
    return (pequena, grande)

def test_guarda_reinicia_com_atomic_reutilizado():
    pequena, grande = duas_contas()
    escopo = transaction.atomic()
    with escopo:
        _travar_conta(grande.pk)
    with escopo:
        _travar_conta(pequena.pk)

def test_guarda_ativa_depois_de_atomic_reutilizado():
    pequena, grande = duas_contas()
    escopo = transaction.atomic()
    with escopo:
        _travar_conta(pequena.pk)
        _travar_conta(grande.pk)
    with escopo:
        _travar_conta(grande.pk)
        with pytest.raises(OrdemDeTravasViolada):
            _travar_conta(pequena.pk)

def test_guarda_desconta_trava_desfeita_por_savepoint():
    pequena, grande = duas_contas()
    with transaction.atomic():
        try:
            with transaction.atomic():
                _travar_conta(pequena.pk)
                raise ValueError('rollback da trava')
        except ValueError:
            pass
        # Controle: a trava do savepoint não está mais retida no PostgreSQL.
        def outra_conexao(barreira):
            from django.db import connection
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '500ms'")
                _travar_conta(pequena.pk)
        resultado = executar_em_paralelo(outra_conexao)
        assert resultado[0].excecao is None, repr(resultado[0].excecao)
        _travar_conta(grande.pk)
        with pytest.raises(OrdemDeTravasViolada):
            _travar_conta(pequena.pk)

def test_tarifa_pareada_pelo_instante_do_lancamento(monkeypatch, relogio, simulador_pagamentos):
    from apps.financeiro import entradas
    from apps.pagamentos.provedor import MovimentoNoProvedor, TipoDeMovimentoNoProvedor as P
    relogio.congelar(T0)
    ap = montar_ap()
    simulador_pagamentos.definir_tarifa('pix', percentual=D('0'), fixa=D('10'))
    original = entradas.lancar

    def avancar_antes_da_tarifa(*args, **kwargs):
        if kwargs.get('tipo') == TipoDeMovimento.TARIFA:
            relogio.avancar(timedelta(seconds=10))
        return original(*args, **kwargs)
    monkeypatch.setattr(entradas, 'lancar', avancar_antes_da_tarifa)
    id_pagamento = pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, timedelta(hours=1))
    ocorrido = T0 + timedelta(hours=1)
    referencia = ocorrido + timedelta(seconds=5)
    desp = Despesa.objects.get(pagamento__id_externo=id_pagamento)
    mov = MovimentoFinanceiro.objects.get(chave=f'tarifa:{desp.pagamento_id}')
    assert desp.criada_em == ocorrido
    assert mov.momento == ocorrido + timedelta(seconds=10)
    _, fim = c.limites_do_dia(T0.date())
    relogio.congelar(fim + timedelta(hours=1))
    movimentos = [MovimentoNoProvedor('pagamento-1', P.PAGAMENTO, 'pagamento', D('125'), id_pagamento, ocorrido, ocorrido), MovimentoNoProvedor('tarifa-1', P.TARIFA, 'tarifa', D('-10'), id_pagamento, ocorrido, ocorrido)]
    monkeypatch.setattr(c, 'obter_provedor', lambda: SimpleNamespace(consultar_saldo=lambda: SaldoNoProvedor(D('115'), D('0'), referencia, fim), listar_movimentos=lambda *args: movimentos))
    resultado = c.conciliar_dia(T0.date())
    assert D(resultado.resumo['diferenca']) == D('0'), resultado.resumo
from tests.apoio.corrida import Corrida, pausar_depois_da_primeira_trava

def test_revalidacao_r01_cobertura_cruzada(monkeypatch):
    m = montar_mundo()
    caixa = reserva()
    receita = receita_de(m.ra)
    with transaction.atomic():
        semear(m, caixa, '100')
    with transaction.atomic():
        semear(m, receita, '100')
    with transaction.atomic():
        desp = despesa_de_tarifa('10', m.ra)
        mover(TipoDeMovimento.TARIFA, despesas(), EXTERIOR, '10', origem=desp.pagamento)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, r, 'pendente_da_despesa')
    primeiro, segundo = corrida.rodar(lambda: r.utilizar_reserva(m.admin, desp, D('10'), 'teste'), lambda: a.cobrir_despesa(m.admin, desp, fonte=('receita', m.ra), valor=D('10'), justificativa='teste'))
    assert primeiro.excecao is None, repr(primeiro.excecao)
    assert isinstance(segundo.excecao, r.CoberturaExcedente), repr(segundo.excecao)
    assert saldo(caixa) + saldo(receita) == D('190')
    assert saldo(despesas()) == D('0')

def test_revalidacao_r02_designacao_liquidacao(monkeypatch):
    m = montar_mundo()
    obrig = obrigacao_de_teste('50')
    dest = o.conta_da_obrigacao(obrig)
    with transaction.atomic():
        semear(m, dest, '25')
    caixa = reserva()
    with transaction.atomic():
        semear(m, caixa, '100')
    assert dest.pk < caixa.pk
    pausar_depois_da_primeira_trava(monkeypatch)

    def designar(b):
        b.wait(10)
        with transaction.atomic():
            return r.designar_reserva(m.admin, obrig, D('25'), 'teste')

    def liquidar(b):
        b.wait(10)
        with transaction.atomic():
            return o.liquidar_obrigacao(obrig, D('25'), referencia='dev-revisao')
    resultado = executar_em_paralelo(designar, liquidar)
    assert all((x.excecao is None for x in resultado)), [repr(x.excecao) for x in resultado]
    assert saldo(dest) == D('0')
    assert r.situacao_da_reserva().comprometido == D('25')
    assert saldo(caixa) == D('100')

def test_revalidacao_r03_referencia_concorrente(monkeypatch):
    m = montar_mundo()
    obrig = obrigacao_de_teste('25')
    dest = o.conta_da_obrigacao(obrig)
    with transaction.atomic():
        semear(m, dest, '25')
    reserva()
    corrida = Corrida()
    corrida.depois_de(monkeypatch, o, '_ja_liquidada')

    def liquidar():
        return o.liquidar_obrigacao(obrig, D('25'), referencia='mesma-revisao')
    primeiro, segundo = corrida.rodar(liquidar, liquidar)
    assert (primeiro.excecao, segundo.excecao) == (None, None), (repr(primeiro.excecao), repr(segundo.excecao))
    assert primeiro.valor.pk == segundo.valor.pk
    assert saldo(dest) == D('0')

def test_revalidacao_r09_pausa_apos_leitura_do_estado(monkeypatch, relogio, simulador_pagamentos):
    ap = montar_ap()
    pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, timedelta(hours=1))
    corrida = Corrida()
    corrida.depois_de(monkeypatch, o, '_ciclo_apurado')

    def obrigacao():
        return o.registrar_obrigacao_com_comprador(origem=ap.x, rodada=ap.rodada, ciclo=ap.ciclo, comprador=ap.b, pedido=ap.x, motivo='teste', produtos=D('25'), servico=D('0'), frete=D('0'))
    primeiro, segundo = corrida.rodar(obrigacao, lambda: a.registrar_apuracao_no_livro(ap.ciclo, [ap.x], autor=SISTEMA))
    assert (primeiro.excecao, segundo.excecao) == (None, None), (repr(primeiro.excecao), repr(segundo.excecao))
    assert primeiro.valor.sem_cobertura == D('0')
    assert primeiro.valor.obrigacao.depois_da_apuracao is False
    assert saldo(obrigacao_de(ap.fornecedor, ap.rodada)) == D('75')
    assert saldo(o.conta_da_obrigacao(primeiro.valor.obrigacao)) == D('25')

```
<!-- FIM_PROVAS_E09_2930FFD -->

---

# E09 — Parecer independente consolidado sobre 34f9547

**Veredito final: REPROVADO.** Há defeitos financeiros reproduzidos e não conformidades TDD sem tratamento autorizado. As aprovações locais de fatias não autorizam encerrar a E09.

Base: `34f9547ae7962687ed96997e3338914f985a277f`, branch `e09-implementacao`, revisão independente em 2026-10-22. Lidos documentos-base funcional v1.6 e infraestrutura v1.7, AGENTS.md, especificações, critérios, código, testes e registros das oito fatias. Histórico do implementador preservado integralmente abaixo.

Verificações independentes:

- `uv run pytest -q`: **2398 passed in 273.67s**, sem filtro, PostgreSQL e banco separado do simulador.
- `uv run ruff check .`: passou; `uv run ruff format --check .`: 328 arquivos conformes.
- `uv run mypy .`: 391 arquivos sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais, fora da suíte versionada: **9 failed in 8.57s**, pelos defeitos descritos no [parecer consolidado](../E09-08/review.md), que contém o código completo para reprodução.

Não foram alterados código de produção nem testes versionados. Testes verdes dos critérios existentes não bastam para aprovar as interações financeiras. O revisor não presenciou os ciclos TDD históricos; conferiu os registros e não trata mutação posterior como Red anterior à implementação.

## Matriz das oito fatias

As matrizes somam 133 critérios. Todos os testes versionados passam; os achados mostram lacunas relevantes nas combinações e no processo.

| Fatia | Critérios examinados | Resultado |
|---|---|---|
| E09-01 | A-1–A-18 | REPROVADO: R08; lançador isolado sem novo defeito demonstrado |
| E09-02 | A-1–A-18 | APROVADO localmente |
| E09-03 | A-1–A-12 | APROVADO localmente; integração pendente |
| E09-04 | A-1–A-13 | APROVADO localmente; integração pendente |
| E09-05 | A-1–A-15 | REPROVADO: R01, R02, R05 |
| E09-06 | A-1–A-19 | REPROVADO: R01–R04, R08, R09 |
| E09-07 | A-1–A-23 | REPROVADO: R05–R08 |
| E09-08 | A-1–A-15 | REPROVADO na integração; M-8 editorial em A-3 |

E09-08: políticas de administrador, passkey recente, validações, respostas e paginação conferidas nos testes existentes. O literal `1.000,00` de A-3 é recusado: a spec exige recusar separador de milhar, e o teste usa `1000,00`. Não se declara o literal A-3 satisfeito; M-8 solicita alinhamento editorial, sem alterar o parser. Não houve inspeção visual no navegador ou ensaio de carga. Dinheiro/provedor real permanece fora da fase 1.

## Achados e reprodução

### E09-R01 — bloqueador — cobertura duplicada da mesma despesa

Referências: funcional §9.3/§9.4; E09-05 A-6/A-7; E09-06 A-4/A-16; AGENTS §6. Código: `apps/financeiro/reserva.py:341`, `apps/financeiro/apuracao.py:213`.

`utilizar_reserva` lê o pendente antes de travar o destino; a cobertura pela receita pode concluir nesse intervalo. Prova `test_cobertura_cruzada`: tarifa de 10,00 lançada, reserva e receita de 100,00; pausar a reserva depois da leitura do pendente, concluir a cobertura pela receita, retomar a reserva. **Ambas passam e a cobertura soma 20,00 para uma despesa de 10,00.** O cálculo do pendente limita o resultado em zero, escondendo o excedente.

Validar o pendente sob proteção compartilhada por todas as fontes, inclusive cobertura automática; testar a corrida entre fontes diferentes. A trava exclusiva da reserva não basta.

### E09-R02 — bloqueador — deadlock entre designação e liquidação

Referências: AGENTS §6; E09-01 ordem global/A-16; E09-05 travas e E09-06 liquidação. Código: `reserva.py:289`, `obrigacoes.py:83` e `obrigacoes.py:271`.

Designação trava reserva → obrigação; liquidação trava por PK. Se a conta da obrigação nasceu primeiro, as ordens se invertem. Prova `test_ordem_designacao_liquidacao`: obrigação 50,00, financiada 25,00, reserva 100,00; designação de 25,00 em paralelo com liquidação dos 25,00 financiados, pausando cada operação após a primeira trava. **PostgreSQL detecta deadlock em financeiro_contafinanceira; uma operação falha com OperationalError.** Ambas seriam válidas em qualquer ordem serial.

Unificar a ordem efetiva ao longo de toda a transação, inclusive antes de `lancar`. Ordenar contas já travadas não resolve. É decisão técnica derivável, sem necessidade de mudar regra comercial.

### E09-R03 — importante — repetição concorrente da liquidação não é idempotente

Referências: AGENTS §6; E09-06 A-10 e contrato de liquidar_obrigacao. Código: `obrigacoes.py:271`.

A referência só é consultada antes das travas. Prova `test_mesma_referencia_concorrente`: duas chamadas de 25,00 para obrigação financiada, mesma referência, ambas consultando antes de qualquer conclusão. Uma devolve o movimento; outra lança **LiquidacaoRecusada: o valor passa do que falta devolver**. Deve devolver o mesmo movimento às duas. Não houve segunda saída: o defeito está no contrato de resposta idempotente/recuperação.

Revalidar a referência sob a proteção da liquidação, mantendo a recusa de conteúdo conflitante e de referências distintas acima do devido.

### E09-R04 — importante — relatório omite cobertura do componente frete

Referências: funcional §9.3; E09-06 contrato frete_do_ciclo e A-3/A-4/A-7; E09-08 resumo. Código: `apuracao.py:187`.

O relatório só soma coberturas de Despesa(deficit_frete). Prova `test_frete_coberto`: efetivo 30,00, arrecadado 20,00, déficit inicial 10,00 coberto; pagar frete 30,00; criar obrigação posterior exclusivamente de frete 5,00, financiar pela reserva e liquidar. **Déficit 15,00, todo coberto, mas deficit_coberto informa 10,00 em vez de 15,00.**

Confirma a pendência declarada pelo implementador. O caso não exige rateio: há apenas frete. Para cobertura parcial de obrigação mista, documentar a regra derivada ou devolver a ambiguidade residual ao especificador; não presumir uma regra comercial nem omitir a parcela inteira. O esclarecimento residual não impede corrigir/testar o caso inequívoco.

### E09-R05 — importante — avaliação periódica da reserva ausente

Referências: funcional §9.4; E09-05 spec, obrigações sem cobertura (avaliar_reserva também na tarefa do invariante); integração E09-07. Código: `tarefas.py:22`, `invariante.py:57`.

A tarefa chama verificar_invariante_agora, que não avalia a reserva. Prova `test_tarefa_avalia_reserva`: despesa pendente 10,00, reserva zero, provedor acessível e sem violação do invariante de terceiros. Após verificar, **nenhum alerta reserva_insuficiente**. Tarifas pendentes podem surgir sem uma operação manual de reserva que execute a avaliação.

Implementar/testar abertura e resolução periódicas, preservando a atomicidade e o tratamento especificado de indisponibilidade.

### E09-R06 — importante — identificação válida aborta a conciliação

Referências: E09-05 identificação até 64 caracteres; E09-07 A-13/A-17 e chave inversa; E09-03 limite da chave. Código: `conciliacao.py:228`.

Prova `test_identificador_64_conciliavel`: aporte com identificação de 64 caracteres, aceito pelo serviço; conciliar sem movimento correspondente. O prefixo livro: gera 70 caracteres e o serviço de alerta lança **ValueError: a chave do alerta deve ter de 1 a 64 caracteres**. O dia é desfeito e a tarefa não avança.

Compatibilizar as chaves derivadas sem truncamento com colisões, preservar a identificação original e não restringir silenciosamente entradas válidas. A representação técnica estável pode ser resolvida autonomamente.

### E09-R07 — importante — janelas temporais incorretas na conciliação

Referências: E09-07 decisões técnicas, janela inversa de D−3 dias até fim de D e fórmula até referente_a; A-13/A-14/A-15/A-23. Código: `conciliacao.py:119` e `conciliacao.py:149`.

A consulta ampla é reaproveitada sem os recortes próprios:

1. `test_conciliacao_respeita_referente_a`: saldo zero referente às 10h de D, ajuste +10,00 às 12h; diferença naquele instante deveria ser zero, mas informa **−10,00**, abrindo alerta de saldo indevido além do alerta legítimo do ajuste.
2. `test_conciliacao_nao_parea_movimento_futuro`: aporte de D, depósito com mesmo ID somente em D+1, execução em D+1. O depósito fora da janela é aceito como par de D, produzindo **ok e sem_par=0**, em vez de ausência de par no período prescrito.

Separar recorte da diferença, janela inversa e movimentos do dia. O registro imutável não pode consolidar um ok falso ou uma diferença falsa.

### E09-R08 — bloqueador de processo — TDD não demonstrado

Referências: AGENTS §§3/4/8 e prevenção E08-R06. Evidência: registros do implementador preservados nas fatias.

- E09-01: extrato escrito antes do teste; mutação posterior não demonstra Red histórico. A-2 falhou por conta inexistente no andaime, não por permitir mutação; conferir a cronologia das proteções ORM/SQL, que são comportamento testável.
- E09-06 A-17–A-19: travas introduzidas com a implementação, sem Red concorrente sobre comportamento funcional, expressamente declarado. Mutações posteriores detectam A-17/A-18; A-19 nem detecta retirar as travas da apuração.
- E09-07 A-20: UNIQUE/tratamento da corrida escritos antes do Red específico, expressamente declarado.

Decisões excepcionais de entregas anteriores não dispensam o TDD da E09. Encaminhar evidência histórica verificável onde existir; para desvios irreversíveis, obter tratamento explícito do responsável pelo projeto. Não recriar andaime e chamá-lo de Red histórico. As novas correções precisam de falha pelo defeito real antes de alterar produção. Mesmo eventual tratamento de R08 não aprova R01–R07/R09.

### E09-R09 — bloqueador — fontes desatualizadas durante a apuração

Referências: funcional §9.3; infraestrutura 3.2/P-2; E09-06 A-1/A-6/A-7 e concorrência; AGENTS §6. Código: `obrigacoes.py:129`, `apuracao.py:89`.

A obrigação lê apurado e escolhe as fontes antes das travas. Prova `test_obrigacao_concorrente_apuracao`: X pago, produtos 100,00; obrigação de produtos 25,00 lê ainda não apurado e pausa; apuração conclui, movendo 100,00 ao fornecedor; obrigação retoma usando custódia vazia. Ambas concluem, mas a obrigação fica **25,00 sem cobertura**, apesar de haver saldo na própria rodada; depois_da_apuracao permanece falso.

Em qualquer ordem serial, os 25,00 sairiam da custódia ou da obrigação com fornecedor. Serializar a decisão de estado/fontes com a apuração, respeitando a ordem global. A-19 atual cobre entrada versus apuração, não obrigação versus apuração.

## Encaminhamento

Corrigir R01–R07/R09 com Red específico, tratar R08 explicitamente e submeter nova revisão. E09 não atende à Definition of Done. M-5 (desempenho), M-6 e M-7 existentes não encerram esses achados. O registro central tem dois itens M-5, preservados sem apagar histórico alheio. Acrescentada M-8 para o literal de A-3 da E09-08.

As provas usam serviços reais e transações PostgreSQL. Nas corridas, o monkeypatch apenas pausa a execução; não remove travas, validações ou efeitos. O provedor é substituído por dublê do protocolo nas provas temporais, conforme a fase 1. O estado inicial usa apoios do projeto. Essas provas demonstram defeitos atuais, não o TDD histórico.

## Reprodução independente

Salvar o bloco Python abaixo como `$env:TEMP/test_revisao_e09.py` e, na raiz do repositório, executar:

```powershell
uv run pytest "$env:TEMP/test_revisao_e09.py" -q -c pyproject.toml --tb=short
```

Esperado em 34f9547: **9 failed**, pelos motivos acima. A primeira tentativa de montar três provas concorrentes passou uma lista onde o apoio exige argumentos posicionais; o script temporário foi corrigido antes de contabilizar resultados. A prova de cobertura foi também reforçada com o lançamento real da tarifa. O resultado final acima é da versão completa abaixo, sem alteração do produto.

<!-- INICIO_PROVAS_E09 -->
```python
from datetime import timedelta
from decimal import Decimal as D
from threading import Barrier, Event
from types import SimpleNamespace
import pytest
from django.db import transaction
from apps.financeiro import reserva as r, obrigacoes as o, apuracao as a, conciliacao as c, invariante as inv
from apps.financeiro.livro import saldo, EXTERIOR
from apps.financeiro.models import *
from apps.financeiro.liquidez import registrar_saida
from apps.pagamentos.provedor import SaldoNoProvedor
from tests.apoio.financeiro import *
from tests.apoio.concorrencia import executar_em_paralelo
from tests.conftest import relogio, simulador_pagamentos
from apps.nucleo.auditoria import SISTEMA
pytestmark = pytest.mark.django_db(transaction=True, databases=['default','simulador_pagamentos'])

def test_cobertura_cruzada(monkeypatch):
    with transaction.atomic():
        m=montar_mundo(); caixa=reserva(); receita=receita_de(m.ra)
        semear(m,caixa,'100'); semear(m,receita,'100')
        desp=despesa_de_tarifa('10',m.ra); mover(TipoDeMovimento.TARIFA,despesas(),EXTERIOR,'10',origem=desp.pagamento)
    leu=Event(); cobriu=Event(); original=r.pendente_da_despesa
    def pausa(d):
        v=original(d)
        if not leu.is_set():
            leu.set(); assert cobriu.wait(10)
        return v
    monkeypatch.setattr(r,'pendente_da_despesa',pausa)
    def primeira(b):
        with transaction.atomic(): return r.utilizar_reserva(m.admin,desp,D('10'),'teste')
    def segunda(b):
        assert leu.wait(10)
        try:
            with transaction.atomic(): return a.cobrir_despesa(m.admin,desp,fonte=('receita',m.ra),valor=D('10'),justificativa='teste')
        finally: cobriu.set()



    resultados=executar_em_paralelo(primeira,segunda)
    erros=[repr(x.excecao) for x in resultados]
    from django.db.models import Sum
    total=TransferenciaFinanceira.objects.filter(movimento__origem_tipo='financeiro.despesa',movimento__origem_id=str(desp.pk)).aggregate(s=Sum('valor'))['s']
    assert total<=D('10'), (total,erros)

def test_ordem_designacao_liquidacao(monkeypatch):
    with transaction.atomic():
        m=montar_mundo(); obrig=obrigacao_de_teste('50'); dest=o.conta_da_obrigacao(obrig)
        semear(m,dest,'25'); caixa=reserva(); semear(m,caixa,'100')
    assert dest.pk<caixa.pk
    barreira=Barrier(2); original=r._travar_conta
    def trava_reserva(pk):
        original(pk)
        if pk==caixa.pk: barreira.wait(10)
    def trava_obrigacao(pk):
        original(pk)
        if pk==dest.pk: barreira.wait(10)
    monkeypatch.setattr(r,'_travar_conta',trava_reserva)
    monkeypatch.setattr(o,'_travar_conta',trava_obrigacao)
    def designar(b):
        with transaction.atomic(): return r.designar_reserva(m.admin,obrig,D('25'),'teste')
    def liquidar(b):
        with transaction.atomic(): return o.liquidar_obrigacao(obrig,D('25'),referencia='dev-lock')
    resultados=executar_em_paralelo(designar,liquidar)
    assert all(x.excecao is None for x in resultados), [repr(x.excecao) for x in resultados]

def test_mesma_referencia_concorrente(monkeypatch):
    with transaction.atomic():
        m=montar_mundo(); obrig=obrigacao_de_teste('25'); dest=o.conta_da_obrigacao(obrig)
        semear(m,dest,'25'); reserva()
    barreira=Barrier(2); original=o._ja_liquidada
    def pausa(*args):
        v=original(*args); barreira.wait(10); return v
    monkeypatch.setattr(o,'_ja_liquidada',pausa)
    def liquidar(b):
        with transaction.atomic(): return o.liquidar_obrigacao(obrig,D('25'),referencia='mesma')
    resultados=executar_em_paralelo(liquidar,liquidar)
    assert all(x.excecao is None for x in resultados), [repr(x.excecao) for x in resultados]
    assert resultados[0].valor.pk==resultados[1].valor.pk

def test_frete_coberto(relogio,simulador_pagamentos):
    ap=montar_ap(); pagar_pedido(ap,ap.x,simulador_pagamentos,relogio,timedelta(hours=1))
    with transaction.atomic():
        r.registrar_aporte(ap.admin,D('100'),'deposito','teste')
        a.registrar_apuracao_no_livro(ap.ciclo,[ap.x],autor=SISTEMA)
        desp=Despesa.objects.get(tipo=TipoDeDespesa.DEFICIT_DE_FRETE,ciclo=ap.ciclo)
        r.utilizar_reserva(ap.admin,desp,D('10'),'teste')
        registrar_saida(ap.admin,tipo='pagamento_do_frete',conta=frete_de(ap.rodada),valor=D('30'),identificacao='frete',justificativa='teste')
        obrig,_=o.registrar_obrigacao_com_comprador(origem=ap.x,rodada=ap.rodada,ciclo=ap.ciclo,comprador=ap.b,pedido=ap.x,motivo='teste',produtos=D('0'),servico=D('0'),frete=D('5'))
        r.designar_reserva(ap.admin,obrig,D('5'),'teste')
        o.liquidar_obrigacao(obrig,D('5'),referencia='dev-frete')
    resultado=a.frete_do_ciclo(ap.ciclo)
    assert resultado.deficit_coberto==D('15'),resultado

def test_tarefa_avalia_reserva(monkeypatch,relogio):
    relogio.congelar(T0)
    montar_mundo(); despesa_de_tarifa('10')
    monkeypatch.setattr(inv,'obter_provedor',lambda:SimpleNamespace(consultar_saldo=lambda:SaldoNoProvedor(D('0'),D('0'),T0,T0)))
    inv.verificar_invariante_agora()
    assert AlertaFinanceiro.objects.filter(tipo=TipoDeAlerta.RESERVA_INSUFICIENTE,resolvido_em__isnull=True).exists()

def test_identificador_64_conciliavel(monkeypatch,relogio):
    relogio.congelar(T0); m=montar_mundo()
    with transaction.atomic(): r.registrar_aporte(m.admin,D('100'),'x'*64,'teste')
    relogio.avancar(timedelta(days=1))
    monkeypatch.setattr(c,'obter_provedor',lambda:SimpleNamespace(consultar_saldo=lambda:SaldoNoProvedor(D('0'),D('0'),T0+timedelta(days=1),T0+timedelta(days=1)),listar_movimentos=lambda *args:[]))
    c.conciliar_dia(T0.date())


def test_conciliacao_respeita_referente_a(monkeypatch,relogio):
    from apps.pagamentos.provedor import MovimentoNoProvedor, TipoDeMovimentoNoProvedor as P
    from datetime import datetime, UTC
    dia=T0.date(); inicio,fim=c.limites_do_dia(dia)
    referencia=inicio+timedelta(hours=10); ocorrido=inicio+timedelta(hours=12)
    relogio.congelar(fim+timedelta(hours=1)); montar_mundo()
    mov=MovimentoNoProvedor('ajuste-tarde',P.AJUSTE,'ajuste',D('10'),None,ocorrido,ocorrido)
    monkeypatch.setattr(c,'obter_provedor',lambda:SimpleNamespace(consultar_saldo=lambda:SaldoNoProvedor(D('0'),D('0'),referencia,fim),listar_movimentos=lambda *args:[mov]))
    resultado=c.conciliar_dia(dia)
    assert D(resultado.resumo['diferenca'])==D('0'),resultado.resumo

def test_conciliacao_nao_parea_movimento_futuro(monkeypatch,relogio):
    from apps.pagamentos.provedor import MovimentoNoProvedor, TipoDeMovimentoNoProvedor as P
    dia=T0.date(); inicio,fim=c.limites_do_dia(dia)
    relogio.congelar(inicio+timedelta(hours=12)); m=montar_mundo()
    with transaction.atomic(): r.registrar_aporte(m.admin,D('100'),'futuro','teste')
    instante=fim+timedelta(hours=2); ocorrido=fim+timedelta(hours=1)
    relogio.congelar(instante)
    mov=MovimentoNoProvedor('futuro',P.DEPOSITO,'deposito',D('100'),None,ocorrido,ocorrido)
    monkeypatch.setattr(c,'obter_provedor',lambda:SimpleNamespace(consultar_saldo=lambda:SaldoNoProvedor(D('100'),D('0'),instante,instante),listar_movimentos=lambda *args:[mov]))
    resultado=c.conciliar_dia(dia)
    assert resultado.resumo['sem_par']==1,resultado.resumo

def test_obrigacao_concorrente_apuracao(monkeypatch,relogio,simulador_pagamentos):
    ap=montar_ap(); pagar_pedido(ap,ap.x,simulador_pagamentos,relogio,timedelta(hours=1))
    escolheu=Event(); apurou=Event(); original=o._fontes
    def pausa(rodada,ciclo,comprador,depois):
        assert depois is False
        escolheu.set(); assert apurou.wait(10)
        return original(rodada,ciclo,comprador,depois)
    monkeypatch.setattr(o,'_fontes',pausa)
    def obrigacao(b):
        with transaction.atomic():
            return o.registrar_obrigacao_com_comprador(origem=ap.x,rodada=ap.rodada,ciclo=ap.ciclo,comprador=ap.b,pedido=ap.x,motivo='teste',produtos=D('25'),servico=D('0'),frete=D('0'))
    def apuracao(b):
        assert escolheu.wait(10)
        try:
            with transaction.atomic(): return a.registrar_apuracao_no_livro(ap.ciclo,[ap.x],autor=SISTEMA)
        finally: apurou.set()
    resultados=executar_em_paralelo(obrigacao,apuracao)
    assert all(x.excecao is None for x in resultados),[repr(x.excecao) for x in resultados]
    assert resultados[0].valor.sem_cobertura==D('0'),resultados[0].valor


```
<!-- FIM_PROVAS_E09 -->

---

# E09-08 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- `apps/financeiro/views.py` (as dez views), `apps/financeiro/urls.py`, `config/urls.py` (inclusão em `/administracao/financeiro/`), `templates/financeiro/` (`resumo`, `movimentos`, `reserva`, `aporte`, `retirada`, `conciliacoes` e o menu `_menu`), o link "Financeiro" em `templates/administracao/painel.html` e o link do aviso `alerta_financeiro` em `apps/financeiro/alertas.py` (agora `financeiro_resumo`).
- Testes: `tests/tecnicos/test_financeiro_telas.py` (A-1 a A-13, A-14 rota a rota e A-15); o teste de link do aviso em `tests/tecnicos/test_financeiro_alertas.py` foi ajustado (abaixo).

## Andaime (exceção técnica)

Antes do Red: as dez rotas, com os nomes e as políticas de acesso (`somente_administrador` nas de leitura e `exige_reautenticacao_por_passkey` nas de ação), e as views com resposta vazia. Sem comportamento testável além da política.

## Red (arquivo inteiro, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_telas.py -q -p no:cacheprovider` contra o andaime: **21 falharam, 13 passaram**. As falhas são asserções sobre o conteúdo e o status (a resposta vazia não traz o resumo, a mensagem nem o redirecionamento). As 13 que passaram são as que só dependem da política do andaime: o redirecionamento para a nova autenticação (A-4), a recusa a comprador, fornecedor e anônimo (A-5), a política de cada rota (A-14) e a resposta 200 das telas de leitura. Os dois ajustes de teste que apareceram no Red: o `Tela.entrar()` precisa sair da sessão antes de entrar de novo por passkey (senão o login não cria outro registro de passkey recente), e o `Client.get` com filtro leva o `pk` como texto.

O link do aviso (A-13) teve o Red à parte: o teste do E09-03 (`test_abrir_o_alerta_avisa_so_o_administrador`) foi atualizado para o link novo e falhou por `assert '/inicio/' == '/administracao/financeiro/'`; só depois o link mudou.

## Green

`views.py`, as seis telas HTML e o link novo: `test_financeiro_telas.py` + `test_financeiro_alertas.py` + `test_permissoes_politica_rotas.py`: **69 passaram**; `test_financeiro_telas.py` sozinho: **34 passed**.

## Teste antigo ajustado

`tests/tecnicos/test_financeiro_alertas.py` (E09-03), `test_abrir_o_alerta_avisa_so_o_administrador`: o link do aviso era `/inicio/` (a spec da E09-03 diz que ele passa a apontar para `financeiro_resumo` quando a tela existir; a E09-08 A-13 pede isso). Agora a asserção é `notificacao.link == "/administracao/financeiro/"`. Nenhuma outra asserção mudou.

## Decisões técnicas e pontos para o revisor

- **A-3 e o valor com separador de milhar.** O critério A-3 diz "`POST` com `1.000,00`", enquanto o texto das regras (e o A-10) recusam separador de milhar (`1.000`, `1.000,00` não passam em `ler_decimal_digitado`). Li o A-3 como o valor de R$ 1.000,00, digitado `1000,00`; o teste usa `1000,00` e o A-10 cobre `1.000`. **Peço ao especificador que confirme** (ou corrija a redação do A-3).
- **400 e 409.** Entrada inválida (valor, identificação ou justificativa ausentes) responde 400; recusa do serviço (reserva insuficiente, liberado insuficiente, depósito repetido, designação encerrada, cobertura acima do pendente, invariante violado) responde 409, sempre sem escrita.
- **Onde a recusa aparece.** A recusa das ações do resumo (designar, cobrir) volta a página do resumo com a mensagem; a de desfazer volta a da reserva; a do aporte e a da retirada voltam o próprio formulário, com os valores digitados.
- **Mensagens com os valores.** "O valor passa do saldo livre da reserva (R$ 20,00)." e "Só R$ 0,00 da receita desta rodada estão liberados no provedor." são montadas na view com o estado atual (leitura depois da recusa), e não copiadas do texto da exceção.
- **Sem passkey recente.** As rotas de ação redirecionam para `mfa_reauthenticate_webauthn` com `next` (política `exige_reautenticacao_por_passkey` da E02-03); o `POST` não é reaplicado depois da nova autenticação (o formulário volta em branco), como nas outras telas do administrador.
- **Resumo.** Os blocos seguem a tabela da spec; as linhas de custódia, frete e receita citam rodada e ciclo (não o nome do fornecedor), e só a obrigação com fornecedor traz o nome dele.
- **Escala.** O resumo percorre todas as contas, obrigações e despesas, sem paginação (as listas desta etapa são pequenas); os movimentos paginam de 50 em 50. Candidata a melhoria na revisão final (M-5 abaixo).
- **Sem concorrência nova.** A fatia não acrescenta travas: o duplo clique no aporte é barrado pela identificação única (A-15), que é a proteção da E09-05.

## Verificação

Os arquivos da fatia: **69 passed**. A suíte completa e as verificações estáticas estão na verificação final da E09, abaixo.

## Verificação final da E09 (2026-10-22)

Suíte completa, sem filtro e sem `--deselect`, no HEAD da E09-08: `uv run pytest -q -p no:cacheprovider` → **2398 passed in 230.76s**. `uv run ruff check .` limpo; `uv run ruff format --check .` (328 arquivos) limpo; `uv run mypy .` (391 arquivos) sem erros; `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` sem mudanças. Antes da E09 eram 2160 testes (E08 reaprovada); a E09 acrescentou 238.

### Resumo por fatia

| Fatia | Registro | Commit |
|---|---|---|
| E09-01 | `docs/specs/E09-01/review.md` | `cbe5ae3`, `301dfd5` |
| E09-02 | `docs/specs/E09-02/review.md` | `aa65a6a` |
| E09-03 | `docs/specs/E09-03/review.md` | `7f8b0af` |
| E09-04 | `docs/specs/E09-04/review.md` | `cc6b944` |
| E09-05 | `docs/specs/E09-05/review.md` | `ec52e1b` |
| E09-06 | `docs/specs/E09-06/review.md` | `917f375` |
| E09-07 | `docs/specs/E09-07/review.md` | `3f7e6e7` |
| E09-08 | este arquivo | o commit que contém este registro |

### Desvios e pendências para o revisor e o especificador

- **E09-06, concorrência sem Red próprio.** Escrevi as travas junto com as operações; a prova é por mutação (A-17 e A-18 detectadas; A-19 não, M-6). Registrado na E09-06.
- **E09-06, `deficit_coberto`.** Implementei só a parcela das despesas de déficit; a segunda parcela da spec ("coberturas do componente frete sem cobertura das obrigações") não tem como ser atribuída por componente. **Pendência de especificação** registrada na E09-06.
- **E09-08, A-3.** O critério diz `1.000,00`, que as próprias regras recusam; li como R$ 1.000,00 digitado `1000,00`. **Pedido de confirmação** registrado acima.
- **Sem Red em `extrato` (E09-01) e A-12 da E09-04 e A-20 da E09-07** como critérios de concorrência: provas por mutação, registradas em cada fatia.
- **Melhorias novas:** M-5, M-6 e M-7 em `docs/melhorias.md`. A M-4 (já registrada pelo revisor da E08) continua para a revisão final.
- **Fora do escopo, como manda a spec:** o estorno e os movimentos de devolução no provedor (E10), a apuração real e a regra de quando acontece (E11), o repasse e o pagamento do frete pelo fluxo real (E13), o painel consolidado (E15). Mercado Pago real (fase 2a) não foi tocado; as limitações L-8 a L-11 seguem abertas.

