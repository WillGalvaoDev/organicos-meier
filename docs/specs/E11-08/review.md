# E11-08 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Esta fatia é de testes de ponta a ponta (spec: "Verde de primeira" e "Correção"). Arquivo: `tests/tecnicos/test_fila_ponta_a_ponta.py`. Arranjo FP montado pelos serviços reais (fechamento, abertura do pagamento, pagamentos pelo simulador, apuração, aprovação; R2 aberta pelo serviço, múltiplo de P retirado e P incluído com o limite do cenário).

| Etapa | Commit | Resultado |
|---|---|---|
| Primeira execução do arquivo inteiro | `3066566` (o arquivo entrou neste commit, ainda sem passar) | **4 failed** na montagem do arranjo: `OrdemDeTravasViolada: a conta 6 foi pedida depois da 11` em `iniciar_apuracao` → `_estornar_e_restaurar` → `reembolso_parcial`. **Achado real das E11-04 e E11-05**: com dois pagantes com estorno (A e C) na mesma apuração, cada reembolso travava as contas do livro-razão separadamente, e a segunda chamada pedia contas de `pk` menor depois da maior. Os testes dessas fatias só tinham um pagante com estorno |
| Testes do defeito nos arquivos da E11-04 e da E11-05 (`test_dois_pagantes_com_estorno_na_mesma_apuracao`, `test_dois_pagantes_recebem_a_devolucao_integral_na_mesma_apuracao`) | `3066566` | **Red: 2 failed** (`OrdemDeTravasViolada`) |
| `contas_das_obrigacoes` (livro-razão) e `_travar_as_contas_das_devolucoes` (apuração): o conjunto das contas de todos os pagantes é travado de uma vez antes do primeiro estorno | commit da fatia | **47 passed** (E11-04, E11-05 e E11-08) |

Execução final do arquivo da E11-08 (`uv run pytest tests/tecnicos/test_fila_ponta_a_ponta.py`): **14 passed**. Depois do conserto acima, todos os critérios A-1 a A-13 passaram **sem mudança de produção específica da fila**: são regressões da E05 (verde de primeira), não Red. Ajustes que fiz nos próprios testes, sem afrouxar asserções: o campo `devido` (propriedade) trocado pelos componentes da obrigação; o ponto de pausa das corridas A-4 e A-10 passou a ser `receptores._alocar_produto` (o receptor importa a função pelo nome); `QuantidadeRecusada` no lugar de `Exception` no A-8.

## Decisões técnicas

- **Adição sem estoque é recusada** (`EstoqueInsuficiente`), como já faz a E05: A-2, A-4 e A-11 afirmam a recusa de D e de E (a spec aceita "recusada ou limitada").
- **A-9:** a rota recebe o `pk` de um produto; um `pk` de `ItemDoPedido` não corresponde a produto (404/recusa) e Q só tem parcela `em_pedido` (nada a remover). Afirmo que os pedidos, os reembolsos e a parcela de A em Q ficam iguais.
- A-4, A-10 e A-11 usam a `Corrida` pausando A depois do atendimento da fila e verificam que B esperou a trava (`b_esperou`).

## Riscos remanescentes e limites de verificação

- A parte do pedido formal do T-47 fica para a E13 (spec). O encerramento da rodada que tira as parcelas `em_pedido` da contagem de `total_reservado` é da E14 (registro herdado).

## Verificação final da E11 (agente 2)

```
uv run pytest                                 # 2764 passed in 382.87s, sem filtro
uv run ruff check . --no-cache                # All checks passed
uv run ruff format --check .                  # arquivos conformes
uv run mypy .                                 # Success: no issues found
uv run python manage.py makemigrations --check --dry-run   # No changes detected
```

Antes da E11 a suíte tinha 2.644 testes; a E11 acrescentou 120. Commits locais em `e11-implementacao`, sem push nem PR. Pontos abertos para o especificador e o revisor: ver "Ponto para o especificador" (E11-05), "Conflito entre critérios de fatias" (E11-04) e os riscos de cada `review.md`.


## Parecer independente — agente 3 — 2026-10-31

Base auditada: `1a36495`, branch `e11-implementacao`, comparada à base E10 integrada `1b9bf07`. Leitura dos documentos-base (funcional v1.7 e infraestrutura v1.8), spec/acceptance das oito fatias, implementação, testes e registros de TDD. O conteúdo anterior deste arquivo foi preservado integralmente. Evidências e reproduções completas no [parecer consolidado da E11-08](../E11-08/review.md).

**Veredito da etapa E11: REPROVADO.** Há dois achados importantes e dois bloqueadores. O ponto documental R03 está bloqueado para decisão/alinhamento das fontes; os defeitos R01, R02 e R04 são suficientes, independentemente dele, para reprovar a implementação.

| Achado | Classificação | Fatias | Evidência independente |
|---|---|---|---|
| R01 — remover a sobra pendente impede recuperar as unidades pagas | Importante | E11-04/E11-05; reflexo em E11-07/E11-08 | Retorno mantém `removida/0` em vez de `ativa/6`; caixa invalidada mantém pendente zero em vez de 4 |
| R02 — reserva de suspenso continua ocupando estoque no retorno | Importante | E11-05 | P1 com 6 reservadas após retorno, embora a conta esteja suspensa |
| R03 — cancelamento no provedor só agendado após a decisão | Bloqueador; conflito de requisito | E11-01 | Provedor ainda retorna `pendente` após apuração; falha programada do cancelamento não bloqueia a apuração |
| R04 — retorno promove trava e causa deadlock com tarifa tardia | Bloqueador | E11-05, integração financeira | `OperationalError: deadlock detected`, FK da despesa em `rodadas_rodada`, `FOR KEY SHARE` |

Referências, causas, impacto e encaminhamento estão nos novos pareceres E11-01, E11-04 e E11-05. A reprodução completa dos quatro achados consta abaixo. Não foram feitas correções silenciosas de produção.

### Matriz de revisão

| Fatia e critérios | Resultado |
|---|---|
| E11-01 A-1 a A-21 | Cenários implementados cobertos; A-8 segue a spec local e conflita com infraestrutura §4.3: R03 |
| E11-02 A-1 a A-10 | Sem achado próprio; ajustes de composição com E11-04 explicados no parecer da fatia |
| E11-03 A-1 a A-9 | Sem achado próprio de cálculo, caixas, arredondamento ou imutabilidade |
| E11-04 A-1 a A-14 e dois pagantes | Cenários existentes passam; interação com remoção da sobra revela R01 |
| E11-05 A-1 a A-17 e dois pagantes | Cenários existentes passam; R01/R02/R04 adicionais; A-3 exige distinguir restauração isolada e atendimento subsequente da fila |
| E11-06 A-1 a A-13 | Sem achado próprio na aprovação, escrituração, déficit e sinal transacional |
| E11-07 A-1 a A-17 | HTTP/templates verificados; revalidar afirmações ao comprador nos casos R01/R02 após correções |
| E11-08 A-1 a A-13 | Fluxos da fila com pendentes reais passam; não cobrem a remoção da sobra de parcela ainda congelada antes da apuração (R01) |

Os testes de corrida da fila existentes forçam uma ordem; não afirmo ter exercitado todas as ordens possíveis. O histórico de conta suspensa continua preservado, mas isso não exige conservar uma reserva que impede uso do estoque na rodada devolvida ao interesse. Não considero a declaração prévia de um risco pelo implementador como aprovação desse comportamento.

### TDD e decisões técnicas

Conferidos os registros das oito fatias e a sequência dos commits de testes antes da produção: `e092f5b/bbc9e7f`, `9364df2/e958092`, `ca861d2/91674c7`, `b75e61e/df2b910`, `67e5bd2/47a4689`, `5a97b88/d54cdf7`, `2e5c00c/33c0cd2` e `3066566/aae9149`. As regressões que passaram antes da produção estão declaradas; não as reconto como Red. A correção de contas financeiras para mais de um pagante foi precedida dos dois testes que expunham `OrdemDeTravasViolada`. Não reexecutei commits históricos nesta rodada; a reexecução independente foi do estado atual e das provas novas.

As decisões de travar as contas dos compradores antes do fornecedor e usar `FOR NO KEY UPDATE` são tecnicamente fundamentadas. R04 mostra que a compatibilidade precisa ser mantida até o fim da transação, inclusive dentro do serviço de retorno reutilizado.

### Execuções independentes

**Suíte completa: 2764 passed em 450,07 s (7 min 30 s), sem seleção de testes.** Comando: `.venv/Scripts/python.exe -u "$env:TEMP/revisor_e11.py" -q -p no:cacheprovider --tb=short`. Suíte verde não elimina as seis falhas nas provas adicionais.

- `.venv/Scripts/python.exe -m ruff check .`: passou.
- `.venv/Scripts/python.exe -m ruff format --check .`: 359 arquivos conformes.
- `.venv/Scripts/python.exe -m mypy .`: sem problemas em 434 arquivos.
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`: sem mudanças.
- Provas adicionais abaixo: **6 failed em 11,88 s**, todas pelos resultados descritos na tabela. As cinco primeiras também falharam na execução inicial. A prova de deadlock foi repetida e confirmou o mesmo defeito; uma primeira tentativa dela tinha erro de uso do helper de concorrência (`list` em vez de argumentos separados), corrigido somente no arquivo temporário do revisor e não contabilizado como defeito da aplicação.

Runner com `DJANGO_SETTINGS_MODULE=config.settings.test`, `PYTHONPATH` na raiz, alteração somente de `TEST.NAME` antes de chamar `pytest.main(sys.argv[1:])`. Banco isolado da suíte: `test_organicos_revisor_e11_1a36495`; das provas: `test_organicos_revisor_e11_extra_1a36495`. O arquivo temporário de provas foi criado após a coleta da suíte completa e removido ao encerrar. As verificações estáticas foram executadas antes dele.

### Provas reproduzíveis

Salvar o bloco em um arquivo de teste temporário em `tests/tecnicos/` e executar o arquivo inteiro com pytest no ambiente do projeto, usando PostgreSQL e os dois aliases de teste. Os dois testes de R03 explicitam a exigência da infraestrutura, não a interpretação divergente do A-8 local. A prova de R04 só pausa serviços reais, depois da consulta e antes dos commits; não retira validações nem substitui a chamada externa por sucesso fictício.

```python
from decimal import Decimal as D
import pytest
from apps.pedidos.apuracao import iniciar_apuracao
from apps.interesses.servicos import remover_pendente
from apps.interesses.models import ParcelaDeInteresse
from apps.interesses.consultas import total_reservado
from apps.contas.moderacao import suspender
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.provedor import obter_provedor
from tests.apoio.apuracao import arranjo_ap, pagar, cobranca, H
from tests.apoio.pedidos import T0, montar_arranjo, abrir, pedido_de
from tests.fabricas import ParcelaFactory

pytestmark = pytest.mark.django_db(transaction=True, databases=['default','simulador_pagamentos'])

def test_remover_sobra_nao_remove_reserva_paga_no_retorno(relogio, simulador_pagamentos):
    a,x,y=arranjo_ap(relogio,minimo='100.00',pendente_a_p1=2,limites=(11,12))
    pagar(relogio,simulador_pagamentos,x)
    remover_pendente(a.a,a.p1,D('2'))
    p=ParcelaDeInteresse.objects.get(comprador=a.a,produto=a.p1)
    assert p.situacao=='removida'
    relogio.congelar(T0+48*H)
    iniciar_apuracao(a.admin,a.rodada)
    p.refresh_from_db()
    assert (p.situacao,p.quantidade_reservada)==('ativa',D('6'))

def test_remover_sobra_nao_impede_restauracao_da_caixa_paga(relogio,simulador_pagamentos):
    relogio.congelar(T0)
    a=montar_arranjo(minimo='50.00',parcelas_de_p2=(('b',6),('b',2)))
    p=ParcelaFactory.create(comprador=a.a,produto=a.p2,quantidade_original=D('6'),quantidade_reservada=D('4'),quantidade_pendente=D('2'))
    abrir(a)
    x=pedido_de(a.a)
    pagar(relogio,simulador_pagamentos,x)
    remover_pendente(a.a,a.p2,D('2'))
    p.refresh_from_db()
    assert p.situacao=='removida'
    relogio.congelar(T0+48*H)
    iniciar_apuracao(a.admin,a.rodada)
    p.refresh_from_db()
    assert (p.situacao,p.quantidade_pendente)==('pendente',D('4'))

def test_suspenso_nao_prende_estoque_no_retorno(relogio,simulador_pagamentos):
    a,x,y=arranjo_ap(relogio,minimo='100.00',limites=(11,12))
    pagar(relogio,simulador_pagamentos,x)
    suspender(a.admin,a.a)
    relogio.congelar(T0+48*H)
    iniciar_apuracao(a.admin,a.rodada)
    assert total_reservado(a.p1)==D('0')

def test_cancelamento_no_provedor_precede_apuracao(relogio,simulador_pagamentos):
    a,x,y=arranjo_ap(relogio)
    pagar(relogio,simulador_pagamentos,x)
    externo=cobranca(relogio,y)
    relogio.congelar(T0+48*H)
    iniciar_apuracao(a.admin,a.rodada)
    assert obter_provedor().consultar_pagamento(externo).situacao != 'pendente'

def test_falha_do_cancelamento_bloqueia_apuracao(relogio,simulador_pagamentos):
    a,x,y=arranjo_ap(relogio)
    pagar(relogio,simulador_pagamentos,x)
    cobranca(relogio,y)
    simulador_pagamentos.falhar_proximas(1,operacao='cancelar_cobranca')
    relogio.congelar(T0+48*H)
    with pytest.raises(ConsultaAoProvedorFalhou):
        iniciar_apuracao(a.admin,a.rodada)


def test_retorno_concorre_com_tarifa_sem_impasse(relogio,simulador_pagamentos,monkeypatch):
    from dataclasses import replace
    from threading import Event
    from django.db import transaction
    from apps.pedidos import apuracao
    from apps.financeiro import entradas
    from apps.pagamentos.sincronizacao import sincronizar_pagamento
    from tests.apoio.concorrencia import executar_em_paralelo
    a,x,y=arranjo_ap(relogio,minimo='100.00')
    simulador_pagamentos.definir_tarifa('pix',percentual=D('1'),fixa=D('0'))
    externo=cobranca(relogio,x)
    simulador_pagamentos.aprovar(externo)
    completa=obter_provedor().consultar_pagamento(externo)
    with transaction.atomic():
        sincronizar_pagamento(replace(completa,tarifa=None),origem='tarefa')
    relogio.congelar(T0+48*H)
    consultas=Event(); tarifa=Event(); retorno=Event()
    original_travar=apuracao._travar
    original_tarifa=entradas.registrar_tarifa
    original_devolver=apuracao._devolver_integralmente
    def travar(*args,**kwargs):
        consultas.set()
        assert tarifa.wait(15)
        return original_travar(*args,**kwargs)
    def registrar(*args,**kwargs):
        resultado=original_tarifa(*args,**kwargs)
        tarifa.set()
        assert retorno.wait(15)
        return resultado
    def devolver(*args,**kwargs):
        retorno.set()
        return original_devolver(*args,**kwargs)
    monkeypatch.setattr(apuracao,'_travar',travar)
    monkeypatch.setattr(entradas,'registrar_tarifa',registrar)
    monkeypatch.setattr(apuracao,'_devolver_integralmente',devolver)
    def apurar(barreira):
        barreira.wait(timeout=10)
        return apuracao.iniciar_apuracao(a.admin,a.rodada)
    def registrar_pendentes(barreira):
        barreira.wait(timeout=10)
        assert consultas.wait(15)
        return entradas.registrar_tarifas_pendentes_agora()
    resultados=executar_em_paralelo(apurar,registrar_pendentes)
    for r in resultados:
        if r.excecao is not None:
            print(type(r.excecao).__name__, str(r.excecao))
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
```

### Encaminhamento e limites

R01/R02/R04 voltam ao implementador com testes Red/Green e revalidação independente. R03 volta ao especificador/responsável: esclarecer eventual decisão aprovada que altere a ordem da infraestrutura ou alinhar spec/implementação à ordem vigente; a pergunta foi enviada ao responsável nesta revisão. Até documentar esse alinhamento, não presumir que agendar seja equivalente a efetivar o cancelamento.

L-6 (provedor real), pedido formal/parte do T-47 (E13) e encerramento que retira `em_pedido` da contagem na rodada seguinte (E14) permanecem fora desta entrega conforme spec. R02 ocorre no retorno da própria rodada, dentro da E11, e não pode ser transferido para a E14. Nenhuma nova melhoria não impeditiva foi aberta; docs/melhorias.md não foi alterado.

Entrega do revisor: somente os oito review.md, com conteúdo anterior preservado. Nenhum push nem PR. A E11 não está pronta para aprovação enquanto esses pontos permanecerem abertos.

## Correções da revisão — agente 2 — 2026-11-01

Ordem seguida: R04, R03, R01 e R02 (com os critérios de tela). Commits: `6a19f6d`/`0ac4ba0` (R04), `ffcefc6`/`e510c4f` (R03), `be1b362`/`b3949f7`/`ee1a720` (R01 e R02). Detalhes e Red de cada critério nos `review.md` das E11-01, E11-04, E11-05 e E11-07.

Provas do parecer (arquivo temporário, removido): `test_remover_sobra_nao_remove_reserva_paga_no_retorno`, `test_remover_sobra_nao_impede_restauracao_da_caixa_paga`, `test_suspenso_nao_prende_estoque_no_retorno`, `test_cancelamento_no_provedor_precede_apuracao` e `test_falha_do_cancelamento_bloqueia_apuracao`: **5 passed**. A sexta, `test_retorno_concorre_com_tarifa_sem_impasse`, é o E11-05 A-22 e passa na suíte.

### Verificação final das correções (agente 2, 2026-11-01)

```
uv run pytest                                 # 2785 passed in 318.16s, sem filtro
uv run ruff check . --no-cache                # All checks passed
uv run ruff format --check .                  # arquivos conformes
uv run mypy .                                 # Success: no issues found
uv run python manage.py makemigrations --check --dry-run   # No changes detected
```

Antes das correções a suíte tinha 2.764 testes; as correções acrescentaram 21. Commits locais em `e11-implementacao`, sem push nem PR.
