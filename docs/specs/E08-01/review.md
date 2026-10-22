# E08 — Terceira revisão independente do agente 3 — 2026-10-22

**Veredito final: APROVADO sobre `fe8dffa8a2be08424eb96d5467c445e3fc96332d`, branch `e08-implementacao`.** R06 e R08 estão encerrados. R01–R05 permanecem encerrados, sem regressão observada. Não há achado impeditivo aberto na E08. As melhorias M-3 e M-4 continuam para a revisão final, conforme a política do projeto; não foram implementadas nesta revisão. A aprovação é da entrega da fase 1 com simulador e deste commit, sem afirmar integração em main nem autorização para dinheiro real.

## Escopo e fontes

Lidas antes do código as correções de especificação e aceitação de `a41b44f`, especialmente E08-03 A-29–A-34 e a decisão expressa do responsável sobre o A-11 reescrito em E08-06. Conferidos os registros de `fe8dffa`, o diff de produção/testes de `6118ae4`, AGENTS.md e o histórico desta revisão. Mantidas as fontes superiores da revisão anterior (funcional v1.6 e infraestrutura v1.7); elas não foram alteradas neste intervalo. A decisão de estender o tratamento de R06 está registrada pelo especificador e não precisa ser solicitada novamente.

## Matriz consolidada

| Fatia | Critérios atuais | Veredito | Revalidação |
|---|---|---|---|
| E08-01 | A-1 a A-12 | APROVADO | Cálculo e validações sem alteração; suíte completa verde. |
| E08-02 | A-1 a A-27 | APROVADO | Abertura, congelamento, valor mínimo e rateio preservados; R04 e tratamento antigo de R06 continuam encerrados. M-3 não impede aprovação. |
| E08-03 | A-1 a A-34 | APROVADO | R08 corrigido: consultas individuais, combinação de agendamentos, rollback, indisponibilidade e concorrência. A-23/A-24 preservam as asserções e ajustam somente o momento de observação autorizado. |
| E08-04 | A-1 a A-17 | APROVADO | Quitação/duplicidade preservadas; reconsulta não cria segundo destino. M-4 continua não impeditiva. |
| E08-05 | A-1 a A-28 | APROVADO | Reconsulta de todos os estados, recuperação de órfãs e fronteiras preservadas; corrida da margem com recuperação passa. |
| E08-06 | A-1 a A-15 | APROVADO | Tratamento autorizado de R06 cumprido; A-11 nas duas ordens e demais cenários concorrentes verdes após a mutação de controle. |
| E08-07 | A-1 a A-9 | APROVADO | Fronteiras, políticas e simulador preservados; suíte completa sem exclusões. |

As matrizes atuais somam **142 critérios**. A revisão anterior foi preservada como evidência histórica; seu veredito sobre o commit anterior não é o veredito atual.

## Evidências executadas pelo revisor

| Comando | Resultado |
|---|---|
| `uv run pytest -q` (sem filtro nem exclusão) | **2166 passed in 220.50s (0:03:40)** |
| `uv run ruff check .` | **All checks passed!** |
| `uv run ruff format --check .` | **291 files already formatted** |
| `uv run mypy .` | **Success: no issues found in 342 source files** |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | **No changes detected** |
| `uv run pytest -c pyproject.toml "$env:TEMP/test_review_e08_fe8dffa.py" -q --tb=short` | **8 passed in 5.63s** |
| Arquivo concorrente inteiro com mutação A-11 em memória | **1 failed, 19 passed in 9.59s** (falha esperada por asserção) |
| Arquivo concorrente inteiro com mutação R08 em memória | **3 failed, 17 passed in 38.38s** (falhas esperadas por asserção) |
| `uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q -p no:cacheprovider`, sem plugin/mutação | **20 passed in 9.50s** |

Logs locais: `%TEMP%/om_e08_fe8dffa_suite.log`, `om_e08_fe8dffa_probes.log`, `om_e08_fe8dffa_mut_a11.log`, `om_e08_fe8dffa_mut_r08.log` e `om_e08_fe8dffa_concorrencia_restaurada.log`.

Docker Desktop estava parado: iniciado com `docker desktop start`, seguido de `docker compose up -d db`. Testes de banco executados sequencialmente, com PostgreSQL 17 e simulador reais da aplicação. As mutações alteraram apenas objetos Python em memória por `monkeypatch`, em processos de teste separados; nenhum arquivo de produção ou teste versionado foi editado. A árvore permaneceu limpa até a escrita destes pareceres.

As oito provas independentes incluem os seis casos anteriores de R01–R03 e dois controles novos de R08 (aviso e margem). Os seis casos foram extraídos do bloco Python de `c1d38ec:docs/specs/E08-01/review.md`, sem mudar as asserções, retirando apenas a função antiga de R04, já substituída pela decisão de cadastro e por A-22–A-27. O controle R08 original pausava uma chamada de sincronização que deixou de existir na recuperação; não foi executado para produzir um falso timeout. Foi substituído por pausa após o `falhou`, ainda dentro da transação, como autoriza a nova spec. Os controles novos verificam a conclusão concorrente, a obtenção imediata de P1 e da situação por `nowait`, os dois destinos, a tentativa recusada e a ausência de cobrança nova; código abaixo.

## R08 — ENCERRADO

`apps/pedidos/operacoes.py`, `_criacao_falhou`, agenda `consultar_pagamento` para cada resultado da busca, em ordem `(criado_em, id_externo)`, com origem `busca`. O laço não sincroniza pagamentos nem adquire a situação do pedido. As consultas e os cancelamentos das órfãs são gravados na mesma transação da marcação da tentativa; uma falha local desfaz todo esse conjunto.

Cada consulta é processada em sua própria transação, pela operação existente da E07. Assim não há mais aquisição de P2 enquanto a recuperação retém a situação adquirida ao sincronizar P1. Conferidos por busca de chamadores: criação, cancelamento e consulta agendada sincronizam um pagamento por chamada; `consultar_antes_de_decidir` mantém transação individual por pagamento. Não foi encontrado outro laço que viole a invariante no código de produção atual.

A-29/A-30 e as provas independentes confirmam que aviso e margem terminam enquanto a recuperação está parada, sem travas financeiras retidas. A-31 confere os agendamentos e sua ordem; A-32 demonstra rollback e repetição; A-33 confirma absorção da consulta já pendente; A-34 demonstra recuperação após indisponibilidade. A suíte conserva os cenários de aprovação encontrada, cancelamento da órfã e proibição de nova criação após 24h.

**Sensibilidade independente, não Red histórico:** substituí em memória somente o corpo de `_criacao_falhou` pelo de `584b323`. No arquivo concorrente inteiro, falharam exatamente A-29 (aviso não terminou com recuperação parada), A-30 (margem não terminou) e A-33 (faltou consulta agendada para P1). As falhas foram asserções do comportamento, não deadlocks nem timeout da infraestrutura. Sem a mutação, os vinte casos passaram.

**Evidência de TDD da correção:** o registro do implementador declara os comandos de arquivos inteiros, duas falhas em tentativas e três em concorrência antes da alteração, seguido da correção e do Green. A interpretação de A-31 é válida: suas asserções funcionais estavam antes da estrutural e passaram no código anterior; somente a exigência nova de agendamento falhou. Isso demonstra o controle funcional anterior à proteção, embora o teste completo tenha também uma parte estrutural vermelha. A-29/A-30 demonstraram as corridas separadamente. A-32 era proteção herdada do rollback, explicitamente declarada inicialmente verde; não se exige fabricar falha. A confirmação de sensibilidade feita nesta revisão complementa a evidência e não é apresentada como cronologia histórica.

Os dois ajustes nos testes antigos correspondem exatamente à autorização: A-23 observa o pagamento após a consulta enfileirada; A-24 processa a consulta antes de contar o cancelamento. Nenhuma asserção de negócio foi eliminada ou afrouxada.

## R06 — ENCERRADO por tratamento expressamente autorizado

A seção “Correção E08-R06, segunda revisão” de E08-06/spec.md registra a decisão de 2026-10-21: o mesmo tratamento dos critérios antigos vale para o A-11 reescrito. O complemento de E08-02/spec.md explicita essa extensão. Essa decisão resolve a pendência da revisão anterior, sem reescrever a história.

O registro de E08-06 preserva a declaração verdadeira de teste escrito depois da proteção, referencia a decisão, descreve a mutação, sua falha por asserção e o Green após restauração, além de registrar a causa e a prevenção adicional. Nesta revisão, retirei em memória apenas o ramo `pedido_cancelado` de `_motivo_da_recusa` e rodei o arquivo concorrente inteiro: a variante `pagamento_antes` falhou exatamente com `('criada', '')` em vez de `('nao_criada', 'pedido_cancelado')`; os outros dezenove casos passaram. Sem mutação, os vinte passaram, incluindo as duas ordens do A-11.

Estão atendidos registro, sensibilidade e prova concorrente verde exigidos pela decisão. A não conformidade histórica continua documentada; seu tratamento está encerrado. Não se trata de dispensa para outras entregas.

## Preservação, limites e próximo gate

Conferência automática: os sete review.md de `93d3220` estavam integralmente preservados em `fe8dffa`. Todo o conteúdo de `fe8dffa`, inclusive registros do implementador, é mantido como sufixo nesta atualização. Alterados somente os sete review.md; docs/melhorias.md permanece intacto, com M-3/M-4 pendentes conforme a decisão do projeto.

Verificação com cliente Django, threads e serviços da aplicação; sem navegador, provedor externo, dinheiro real ou worker como processo separado. Não se antecipa a aprovação das próximas etapas de livro-razão, estornos, apuração ou produção. **A E08 pode seguir ao próximo gate previsto pelo projeto, sem correção impeditiva remanescente nesta revisão.**

## Reprodução dos controles novos de R08

Salvar o bloco em um arquivo de teste temporário e executar `uv run pytest -c pyproject.toml <arquivo> -q --tb=short`. Ele contém as duas variantes novas; os seis testes anteriores estão no histórico indicado acima.

```python
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import transaction
from apps.contas.moderacao import suspender, remover
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
from apps.pagamentos.consulta import consultar_antes_de_decidir
from apps.pedidos.models import DestinoDoPagamento, SituacaoDoPedido
from apps.pedidos.pagamento import pedir_pagamento
from apps.pedidos.tarefas import reconsultar_pagamentos_da_margem_agora, bloquear_tentativas_vencidas_agora
from apps.simulador_pagamentos import controle as sim
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.pedidos import T0, pedido_aberto, tentativa_criada, sincronizar
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])

@pytest.fixture(autouse=True)
def relogio():
    r=RelogioControlado()
    sim.reiniciar()
    yield r
    r.parar()
    sim.reiniciar()

@pytest.mark.parametrize('origem',['aviso','margem'])
def test_recuperacao_sem_reter_pagamento_ou_pedido(relogio,monkeypatch,origem):
    from threading import Event
    from apps.pagamentos.chamadas import OPERACOES,Operacao,_tentar
    from tests.apoio.concorrencia import executar_em_paralelo
    arranjo,pedido=pedido_aberto(relogio)
    primeira=tentativa_criada(pedido)
    sim.expirar(primeira.id_externo)
    sincronizar(primeira.id_externo)
    relogio.congelar(T0+timedelta(hours=2))
    segunda=tentativa_criada(pedido)
    sim.expirar(segunda.id_externo)
    sincronizar(segunda.id_externo)
    terceira=pedir_pagamento(arranjo.a,pedido)
    relogio.congelar(T0+timedelta(hours=3))
    sim.aprovar(primeira.id_externo)
    sim.aprovar(segunda.id_externo)
    relogio.congelar(T0+timedelta(hours=25))
    original=OPERACOES['criar_cobranca']
    parou,liberar,terminou=Event(),Event(),Event()
    def pausa(chamada,erro):
        original.falhou(chamada,erro)
        parou.set()
        assert liberar.wait(20)
    monkeypatch.setitem(OPERACOES,'criar_cobranca',Operacao(original.executar,original.concluir,pausa,original.combinar))
    def recuperar(barreira):
        barreira.wait(timeout=10)
        with transaction.atomic():
            chamada=ChamadaAoProvedor.objects.select_for_update().get(operacao='criar_cobranca',alvo=f't{terceira.pk}')
            _tentar(chamada)
    def consultar(barreira):
        barreira.wait(timeout=10)
        assert parou.wait(10)
        if origem=='aviso':
            sincronizar(segunda.id_externo,'aviso')
        else:
            reconsultar_pagamentos_da_margem_agora()
        terminou.set()
    def conferir(barreira):
        barreira.wait(timeout=10)
        try:
            assert parou.wait(10)
            assert terminou.wait(8), 'consulta espera a recuperacao parada'
            with transaction.atomic():
                PagamentoNoProvedor.objects.select_for_update(nowait=True).get(id_externo=primeira.id_externo)
                SituacaoDoPedido.objects.select_for_update(nowait=True).get(pedido=pedido)
        finally:
            liberar.set()
    resultados=executar_em_paralelo(recuperar,consultar,conferir)
    assert all(r.excecao is None for r in resultados),[repr(r.excecao) for r in resultados]
    processar_chamadas()
    assert sorted(DestinoDoPagamento.objects.filter(pedido=pedido).values_list('destino','motivo'))==[('devolucao','duplicidade'),('quita','')]
    terceira.refresh_from_db()
    assert (terceira.situacao,terceira.codigo_da_falha)==('nao_criada','prazo_encerrado')
    assert not CobrancaSimulada.objects.filter(chave_idempotencia=terceira.chave_idempotencia).exists()
    processar_chamadas()
    assert DestinoDoPagamento.objects.filter(pedido=pedido).count()==2
```

## Reprodução das mutações em memória

O plugin abaixo é salvo em `%TEMP%/review_e08_mutation.py`. Para a variante R08, `review_e08_old_falhou.txt`, na mesma pasta, contém apenas a função `_criacao_falhou` extraída de `git show 584b323:apps/pedidos/operacoes.py` (por `ast.get_source_segment` sobre o nó da função). O plugin não escreve no repositório e restaura o objeto ao final de cada teste.

Com `%TEMP%` acrescentado temporariamente a `PYTHONPATH`, executar separadamente:

```
uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q -p no:cacheprovider -p review_e08_mutation --review-mutation=a11 --tb=short
uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q -p no:cacheprovider -p review_e08_mutation --review-mutation=r08 --tb=short
uv run pytest tests/tecnicos/test_pedidos_concorrencia.py -q -p no:cacheprovider
```

As duas primeiras execuções devem falhar como registrado; a terceira, sem mutação, deve passar.

```python
import inspect
from pathlib import Path
import pytest

def pytest_addoption(parser):
    parser.addoption('--review-mutation',choices=['a11','r08'])

@pytest.fixture(autouse=True)
def review_mutation(request,monkeypatch):
    from apps.pedidos import operacoes
    escolha=request.config.getoption('--review-mutation')
    if escolha=='a11':
        f=operacoes._motivo_da_recusa
        s=inspect.getsource(f)
        trecho='    if situacao == SituacaoDePagamento.CANCELADO:\n        return "pedido_cancelado"\n'
        assert trecho in s
        s=s.replace(trecho,'')
    else:
        f=operacoes._criacao_falhou
        s=Path(__file__).with_name('review_e08_old_falhou.txt').read_text(encoding='utf-8')
    ns=dict(operacoes.__dict__)
    exec(compile(s,'<review-mutation>','exec'),ns)
    monkeypatch.setattr(f,'__code__',ns[f.__name__].__code__)
```

---

## Histórico integralmente preservado

# E08 — Nova revisão independente do agente 3 — 2026-10-21

**Veredito global: REPROVADO sobre `584b323c8ec2da97a147642f25757592323da6be`, branch `e08-implementacao`.** R01 a R05 estão corrigidos nos cenários apontados. O tratamento dos critérios antigos de R06 foi registrado conforme a decisão de 2026-10-21, mas o A-11 reescrito da E08-06 descumpriu novamente o ciclo expressamente exigido. Há também um novo achado importante, R08: impasse na recuperação de vários pagamentos. Não foi demonstrada perda definitiva de dinheiro; a repetição após o rollback recuperou os destinos.

## Fontes e matriz revalidada

Lidas antes do código as correções de spec.md/acceptance.md do commit `7a1fb49`, as decisões registradas para R04/R06 e os registros acrescentados pelo implementador em `584b323`. Mantidas as fontes superiores e a leitura da revisão anterior (funcional v1.6, infraestrutura v1.7 e AGENTS.md). Conferidos os diffs de produção/testes desde `c1d38ec`, inclusive a migração do catálogo. As decisões registradas na spec autorizam a restrição do cadastro e o tratamento dos desvios antigos; não é necessário solicitar novamente essas decisões. Não se afirma integração em main.

| Fatia | Matriz atual | Parecer local | Evidência |
|---|---|---|---|
| E08-01 | A-1 a A-12 | APROVADO | Sem alteração funcional; regressão na suíte completa. |
| E08-02 | A-1 a A-27 | APROVADO | A-22–A-27 cobrem serviço, mensagens HTTP, CHECK/SQL, fronteira 0,005 e abertura de três pedidos com rateio exato. Tratamento autorizado de TDD antigo registrado; limites das mutações avaliados abaixo. |
| E08-03 | A-1 a A-28 | REPROVADO | R02/R03 originais corrigidos; novos testes passam, mas a recuperação de múltiplos pagamentos introduz R08. |
| E08-04 | A-1 a A-17 | APROVADO no escopo local | Quitação/duplicidade e corridas existentes verdes; tratamento de TDD antigo registrado. Controle adicional de chamada direta repetida passa. R08 está no chamador novo da E08-03. |
| E08-05 | A-1 a A-28 | APROVADO no escopo local | Todos os estados entram na reconsulta; órfãs recebem cancelamento; repetição e fronteiras cobertas. |
| E08-06 | A-1 a A-15 | REPROVADO no gate de processo | Comportamento corrigido, inclusive fila e criação em andamento nas duas moderações. R06 permanece exclusivamente no ciclo do A-11 reescrito. |
| E08-07 | A-1 a A-9 | APROVADO | Igualdade exata por app, provas negativas de rota adicional, políticas e simulador configurado; suíte completa verde. |

São **136 critérios** nas matrizes atuais. Aprovação local não aprova a integração enquanto R06/R08 permanecerem abertos.

## Verificações independentes

- `uv run pytest -q`, sem filtro ou exclusão: **2160 passed in 246.21s (0:04:06)**. Log `%TEMP%/om_e08_584b323_suite.log`. Inclui os arquivos inteiros de concorrência, catálogo, abertura, tentativas, prazos, moderação, telas e fronteiras.
- `uv run ruff check .`: **All checks passed!**
- `uv run ruff format --check .`: **291 files already formatted**.
- `uv run mypy .`: **Success: no issues found in 342 source files**.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: **No changes detected**.
- Seis casos da prova anterior (R01, R02 nas duas moderações, R03 e dois controles), extraídos sem alterar as asserções: **6 passed**. O cenário antigo de R04 foi retirado desse arquivo de reprodução porque a decisão agora exige recusar seu produto; sua substituição expressa são A-22–A-27, todos exercitados na suíte completa.
- Execução conjunta dessas seis provas com a nova prova R08: `uv run pytest -c pyproject.toml "$env:TEMP/test_review_e08_584b323.py" "$env:TEMP/test_review_e08_584b323_lock.py" -q --tb=short`: **1 failed, 6 passed in 6.24s**. Única falha: `OperationalError: deadlock detected`. Log `%TEMP%/om_e08_584b323_probes.log`.
- Acrescentei à prova R08 a repetição após o rollback e executei o arquivo inteiro novamente: `uv run pytest -c pyproject.toml "$env:TEMP/test_review_e08_584b323_lock.py" -q --tb=short`: **1 failed in 3.75s**, ainda na asserção de ausência de impasse; as asserções anteriores confirmaram dois destinos (`quita`/`devolucao por duplicidade`) e tentativa final `nao_criada`. Log `%TEMP%/om_e08_584b323_lock.log`.
- Controle adicional: `uv run pytest -c pyproject.toml "$env:TEMP/test_review_e08_584b323_idempotencia.py" -q --tb=short`: **1 passed in 2.51s**. Com pagamento aprovado sincronizado, dentro de transação e sob sua trava, duas chamadas a `decidir_destino` devolveram o mesmo PK e mantiveram um único destino. Código completo abaixo.

Na retomada, o contêiner local estava parado; foi iniciado com `docker compose up -d db`. Duas verificações já iniciadas ficaram esperando conexão: interrompidos apenas os processos próprios identificados, e reexecutados os comandos. Não são contadas como resultados válidos. As provas de banco foram executadas sequencialmente com PostgreSQL 17 real e simulador. Nenhum arquivo de produção ou teste versionado foi alterado.

## Fechamento dos achados anteriores

- **R01 encerrado:** prova anterior e E08-05 A-22 confirmam a duplicidade reconhecida no pedido pago, sem novo aviso de quitação; A-23 cobre os três estados.
- **R02 encerrado no comportamento:** a fila recusada não cria cobrança; a conclusão da criação em andamento relê a situação sob trava e agenda cancelamento. Suspensão/remoção terminam sem esperar a chamada externa. As duas ordens do A-11 e a reativação são exercitadas.
- **R03 encerrado no cenário original:** resposta perdida ou falha local de conclusão são recuperadas pela busca; órfãs são canceladas também pelo bloqueio a partir do pagamento. Não há criação nova depois do prazo; pagamento aprovado encontrado recebe destino. **A extensão concorrente de múltiplos resultados falha em R08**, registrado separadamente.
- **R04 encerrado:** decisão registrada de restringir no cadastro. Comparação decimal inclusiva, validação após trava na edição, última recusa de incremento e CHECK correspondem à spec. Nenhum teste anterior teve dados afrouxados. A integração da menor combinação aceita abre três pedidos e preserva o rateio.
- **R05 encerrado:** teste alinhado à autorização das cinco rotas do simulador, preservando fronteira de pagamentos e provas negativas. A-9 é teste da própria fronteira corrigida, sem novo comportamento de produção; sua execução inicialmente verde não exige fabricar Red.
- **R07 continua melhoria não impeditiva M-3**, deliberadamente fora das correções.

## R06 — IMPORTANTE — Tratamento antigo atendido; novo A-11 ainda não atende ao gate

**Referências:** E08-02/spec.md, correção R06, passo 4 e conclusão (“tratamento definitivo dos critérios antigos”); E08-06/acceptance.md, seção final (A-11 reescrito não usa mutação e exige verde funcional → Red da corrida → proteção); AGENTS.md §§3/4/8.

O implementador procurou evidência histórica e registrou a não conformidade sem apagar o passado. Conferi a existência do arquivo de sessão citado e os eventos datados nos índices 13042, 13054, 13139, 13185, 13193, 13225, 13241, 13254, 13446, 13467, 13671 e 14021: eles sustentam a cronologia declarada (testes corrigidos após código/andaime recriado e travas escritas junto com o serviço). Não se atribui a execuções atuais valor de Red histórico.

Aceito o tratamento autorizado dos critérios antigos: registros separados, causas e mutações identificadas. Não reexecutei todas as mutações do implementador. A mutação ORM do A-11 é detectada pela exceção errada em relação ao contrato esperado (`IntegrityError` em vez de `RegistroImutavel`), e não por falha de infraestrutura; isso demonstra a falta da barreira ORM. Em A-20 a trava anterior do fornecedor serializa a corrida mesmo sem a trava da rodada; a mutação complementar retirando as duas demonstra a proteção relevante. Não se exige um teste que imponha isoladamente uma trava redundante. Em A-17 o sinal só chama a decisão na mudança de estado, portanto retirar a guarda interna não afeta a corrida exercitada: é um limite declarado, com proposta de reforço, expressamente permitido pelo passo 3. Controle direto da guarda passou nesta revisão; reforço futuro registrado em M-4.

**Pendência nova, confirmada pelo próprio registro de E08-06:** o teste do A-11 reescrito foi escrito depois da proteção e passou na primeira execução. A mutação que remove `pedido_cancelado` não é Red histórico. Os A-13/A-21 deram Red para a recusa sequencial, mas não cumprem a sequência específica exigida para o novo critério concorrente. O tratamento aprovado excluiu expressamente esse A-11 da substituição por mutação.

**Encaminhamento:** preservar a declaração e submeter ao responsável o tratamento dessa nova não conformidade. É necessário decidir expressamente se o registro, a sensibilidade por mutação e a prova concorrente verde encerram também o A-11 reescrito; a decisão anterior cobre apenas os critérios antigos. Não refazer o passado nem remover código para chamar uma execução nova de Red. Este gate de processo permanece aberto; não é alegação de falha funcional atual da moderação.

## R08 — IMPORTANTE — Recuperação em lote inverte a ordem de travas e entra em impasse

**Referências:** AGENTS.md §6 (concorrência e recuperação); E08-03/spec.md, correção R02/R03, ordem pagamento → situação → tentativa; E08-04, casos concorrentes; E07-06 (sincronização individual em transações curtas). Código: `apps/pedidos/operacoes.py:112-136`, especialmente o laço em `:118`; integração com `apps/pedidos/quitacao.py:207` e a transação por chamada de `apps/pagamentos/chamadas.py:193`.

**Arranjo reproduzido:** duas tentativas anteriores expiradas localmente; terceira somente solicitada. As duas cobranças anteriores são aprovadas no simulador sem sincronizar. Às T0+25h, a criação da terceira é recusada e a busca devolve os dois pagamentos aprovados. Em paralelo, chega a sincronização por aviso do segundo pagamento.

1. A recuperação sincroniza P1 e retém suas travas e a situação S do pedido, porque todo o `falhou` está na transação da chamada.
2. O aviso trava P2 e tenta decidir seu destino, esperando S.
3. A recuperação segue para P2 ainda segurando S, esperando P2: **S → P2**, inverso de **P2 → S**.
4. PostgreSQL aborta uma transação com `OperationalError: deadlock detected`, reproduzido nas duas execuções. Não é timeout do harness nem falha de arranjo.

A prova usa `_tentar` sob a mesma trava/transação de `processar_chamadas` para expor a exceção; não altera a decisão de negócio. No worker normal, a exceção é capturada, registrada como erro inesperado e a chamada fica pendente para outra passada. A prova complementar confirmou que repetir recupera os dois destinos sem duplicá-los; **não foi demonstrada perda definitiva ou cobrança em dobro**. Ainda assim, uma sincronização financeira é abortada por inversão real de travas introduzida na correção, e a concorrência prescrita não está atendida.

**Correção exigida:** manter a ordem global também quando a busca devolve vários pagamentos; não basta ordenar os resultados, pois a transação continua segurando S ao buscar P2. Fazer a recuperação não adquirir outro pagamento depois da situação (por exemplo, separar a sincronização individual da conclusão, ou planejar aquisição das travas antes das decisões, mantendo as fronteiras da E07). Cobrir a corrida com aviso e com reconsulta, bem como rollback/repetição, preservando idempotência, dinheiro reconhecido e ausência de criação nova após o prazo. A solução é técnica, sem nova decisão comercial. Registrar Red real antes da correção.

## Próximo gate e preservação

Devolver R08 ao implementador e resolver o tratamento do novo desvio R06 com o responsável. Reexecutar a prova R08, a suíte relevante e os checks depois da correção. E08 ainda não está aprovada.

Os sete pareceres de `c1d38ec` estavam integralmente preservados como prefixo em `584b323`; conferência automática dos sete arquivos, não apenas leitura de trechos. Esta revisão é acrescentada antes de todo o conteúdo existente, preservando também os registros de correção do implementador. Alterados somente os sete review.md e docs/melhorias.md. Sem navegador, provedor real, dinheiro real ou worker como processo separado; sem mutação de produção nesta revisão.

## Prova completa de R08

Salvar em `%TEMP%/test_review_e08_584b323_lock.py` e executar o comando acima. O envoltório apenas sincroniza as threads entre P1 e P2, sem mudar o resultado da sincronização.

```python
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import transaction
from apps.contas.moderacao import suspender, remover
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
from apps.pagamentos.consulta import consultar_antes_de_decidir
from apps.pedidos.models import DestinoDoPagamento, SituacaoDoPedido
from apps.pedidos.pagamento import pedir_pagamento
from apps.pedidos.tarefas import reconsultar_pagamentos_da_margem_agora, bloquear_tentativas_vencidas_agora
from apps.simulador_pagamentos import controle as sim
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.pedidos import T0, pedido_aberto, tentativa_criada, sincronizar
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])

@pytest.fixture(autouse=True)
def relogio():
    r=RelogioControlado()
    sim.reiniciar()
    yield r
    r.parar()
    sim.reiniciar()


def test_recuperacao_multiplos_pagamentos_e_aviso_sem_impasse(relogio, monkeypatch):
    from threading import Event
    from apps.pedidos import operacoes
    from apps.pagamentos.chamadas import _tentar
    from apps.pagamentos.sincronizacao import sincronizar_pagamento
    from apps.pagamentos.provedor import obter_provedor
    from tests.apoio.concorrencia import executar_em_paralelo
    arranjo,pedido=pedido_aberto(relogio)
    primeira=tentativa_criada(pedido)
    sim.expirar(primeira.id_externo)
    sincronizar(primeira.id_externo)
    relogio.congelar(T0+timedelta(hours=2))
    segunda=tentativa_criada(pedido)
    sim.expirar(segunda.id_externo)
    sincronizar(segunda.id_externo)
    terceira=pedir_pagamento(arranjo.a,pedido)
    relogio.congelar(T0+timedelta(hours=3))
    sim.aprovar(primeira.id_externo)
    sim.aprovar(segunda.id_externo)
    relogio.congelar(T0+timedelta(hours=25))
    resposta2=obter_provedor().consultar_pagamento(segunda.id_externo)
    primeiro_sincronizado,segundo_travado=Event(),Event()
    original=operacoes.sincronizar_pagamento
    def pausa(consultado,**kwargs):
        resultado=original(consultado,**kwargs)
        if consultado.id_externo==primeira.id_externo:
            primeiro_sincronizado.set()
            assert segundo_travado.wait(10)
        return resultado
    monkeypatch.setattr(operacoes,'sincronizar_pagamento',pausa)
    def recuperar(barreira):
        barreira.wait(timeout=10)
        with transaction.atomic():
            chamada=ChamadaAoProvedor.objects.select_for_update().get(operacao='criar_cobranca',alvo=f't{terceira.pk}')
            _tentar(chamada)
    def aviso(barreira):
        barreira.wait(timeout=10)
        assert primeiro_sincronizado.wait(10)
        with transaction.atomic():
            PagamentoNoProvedor.objects.select_for_update().get(id_externo=segunda.id_externo)
            segundo_travado.set()
            sincronizar_pagamento(resposta2,origem='aviso')
    resultados=executar_em_paralelo(recuperar,aviso)
    processar_chamadas()  # repete a chamada se o PostgreSQL desfez a recuperacao
    sincronizar(segunda.id_externo)  # repete o aviso se ele foi a vitima
    assert sorted(DestinoDoPagamento.objects.filter(pedido=pedido).values_list('destino','motivo'))==[('devolucao','duplicidade'),('quita','')]
    terceira.refresh_from_db()
    assert terceira.situacao=='nao_criada'
    assert all(r.excecao is None for r in resultados),[repr(r.excecao) for r in resultados]
```

## Controle completo de idempotência direta

Salvar em `%TEMP%/test_review_e08_584b323_idempotencia.py`.

```python
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import transaction
from apps.contas.moderacao import suspender, remover
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
from apps.pagamentos.consulta import consultar_antes_de_decidir
from apps.pedidos.models import DestinoDoPagamento, SituacaoDoPedido
from apps.pedidos.pagamento import pedir_pagamento
from apps.pedidos.tarefas import reconsultar_pagamentos_da_margem_agora, bloquear_tentativas_vencidas_agora
from apps.simulador_pagamentos import controle as sim
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.pedidos import T0, pedido_aberto, tentativa_criada, sincronizar
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])

@pytest.fixture(autouse=True)
def relogio():
    r=RelogioControlado()
    sim.reiniciar()
    yield r
    r.parar()
    sim.reiniciar()


def test_decidir_destino_repetido_devolve_o_mesmo_registro(relogio):
    from apps.pedidos.quitacao import decidir_destino
    _,pedido=pedido_aberto(relogio)
    tentativa=tentativa_criada(pedido)
    sim.aprovar(tentativa.id_externo)
    sincronizar(tentativa.id_externo)
    with transaction.atomic():
        pagamento=PagamentoNoProvedor.objects.select_for_update().get(id_externo=tentativa.id_externo)
        primeiro=decidir_destino(pagamento)
        segundo=decidir_destino(pagamento)
        assert primeiro.pk==segundo.pk
        assert DestinoDoPagamento.objects.filter(pagamento=pagamento).count()==1
```

---

## Histórico integralmente preservado

# E08 — Revisão independente do agente 3 — 2026-10-21

**Veredito global: REPROVADO sobre `2714a6a2acaf88cc69e02345facf2a2403a66374`, branch `e08-implementacao`.** R01 é bloqueador; R02 a R06 são importantes. R04 depende de definição do tratamento comercial do valor zero, e R06 de esclarecimento/comprovação histórica ou tratamento autorizado da não conformidade de TDD. R07 é melhoria documental não impeditiva, registrada como M-3 em `docs/melhorias.md`.

## Fontes, escopo e matriz

Lidos os requisitos antes do código: especificação funcional v1.6 (especialmente §§2, 4.2, 5.1, 6.3, 7, 8.1–8.3, 9, 12 e 15), infraestrutura v1.7 (§§4.1–4.5, 4.9, 4.12 e 5), AGENTS.md vigente, `docs/melhorias.md` e os sete pares spec.md/acceptance.md. As versões dos documentos-base correspondem entre si. Conferidos os registros do implementador, código e testes, desde as especificações de `4613fdb` até `2714a6a`, incluindo alterações nos pagamentos, rodadas e configuração. Nenhuma afirmação de integração em main.

| Fatia | Critérios examinados | Parecer | Evidência e ressalvas |
|---|---|---|---|
| E08-01 | A-1 a A-12 | APROVADO no escopo local | Cálculo decimal, arredondamento único, maior resto, validações, 200 casos determinísticos e varredura AST passam. O resultado zero de entrada válida expõe a lacuna de integração R04 na abertura. |
| E08-02 | A-1 a A-21 | REPROVADO | Congelamento, divisão das caixas, pendência parcial, retorno, imutabilidade ORM/SQL, auditoria, avisos e autorização têm cobertura verde. R04 impede a abertura com subtotal zero; R06 impede aceitar a evidência de TDD como suficiente. A-12/A-21 têm as divergências editoriais de R07. |
| E08-03 | A-1 a A-20 | REPROVADO | Fluxo nominal, chave estável, cliques repetidos, 24h, políticas e telas passam. R02 na criação depois da moderação; R03 na recuperação após resposta perdida junto ao prazo; R06 nas evidências de concorrência. |
| E08-04 | A-1 a A-17 | REPROVADO no gate documental | Destinos, fronteiras de 48h, duplicidade nas duas ordens, horário do provedor, cancelamento anterior/posterior, rollback e avisos passam nos testes existentes. Não identifiquei falha nova na decisão quando chamada com o pagamento; R01 é a ausência de reconsulta na integração. R06 exige comprovar o ciclo específico das travas. |
| E08-05 | A-1 a A-21 | REPROVADO | Prazos, não antecipação, imutabilidade de T0, tarefas, autorização e painel passam nos casos existentes. R01 exclui pedidos pagos da conciliação; R03 deixa cobrança conhecida pendente sem cancelamento. |
| E08-06 | A-1 a A-12 | REPROVADO | Cancelamento das cobranças já criadas, preservação dos pagos, reativação e rollback passam. A-11 não cobre a tentativa somente solicitada: o teste acrescentou a execução síncrona da criação. R02 demonstra a lacuna; R06 é documental. |
| E08-07 | A-1 a A-8 | REPROVADO na integração | Os oito testes da tela estão verdes e as políticas/checagem do provedor foram conferidas. R05 mantém a suíte relevante vermelha por uma restrição excessiva no teste anterior. |

As sete matrizes somam **111 critérios**. A tabela distingue comportamento exercitado dos casos que faltaram: testes verdes dos critérios originais não demonstram ausência de falhas nas combinações reproduzidas abaixo. A aprovação local de E08-01 não aprova a entrega integrada.

## Verificação independente executada

- `uv run pytest -q`, **sem `--deselect` ou filtro**: **1 failed, 2129 passed in 292.98s (0:04:52)**. A única falha versionada é `tests/tecnicos/test_pagamentos_fronteiras.py::test_nenhuma_rota_comando_ou_admin_registra_pagamento`, linha 87 (R05). Log: `%TEMP%/om_e08_2714a6a_suite.log`.
- `uv run ruff check .`: **All checks passed!**
- `uv run ruff format --check .`: **288 files already formatted**.
- `uv run mypy .`: **Success: no issues found in 338 source files**.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: **No changes detected**.
- `uv run pytest -c pyproject.toml "$env:TEMP/test_review_e08_2714a6a.py" -q --tb=short`: **5 failed, 2 passed in 17.36s**. Log: `%TEMP%/om_e08_2714a6a_probes.log`. Código completo abaixo.

As falhas adicionais são R01 (1), R02 (suspensão e remoção, 2), R03 (1) e R04 (1). Os controles verdes demonstram que a consulta explícita reconhece a duplicidade e que uma cobrança já criada antes da suspensão é cancelada. Na primeira execução das provas, três consultas de apoio usaram `id_externo` como campo ORM de `CobrancaSimulada`, mas ele é uma propriedade. Corrigi apenas a consulta de apoio; essa execução não foi usada como evidência dessas três verificações. As assertivas de negócio foram preservadas, e o resultado final acima é o válido.

Docker Desktop estava parado: iniciado com `docker desktop start`, seguido de `docker compose up -d db` (PostgreSQL 17 local). Suíte e provas usaram o banco sequencialmente. Nenhum código de produção ou teste versionado foi alterado, nenhum teste foi excluído e não houve mutação do código auditado.

## R01 — BLOQUEADOR — Pedido pago sai da reconsulta e oculta pagamento duplicado

**Referências:** funcional §8.3 (nunca ignorar dinheiro; excedente gera devolução integral); infraestrutura 4.3 (reconsultar todas as tentativas do ciclo e buscar por referência); E08-04 A-6 e E08-05, integração da margem. Código: `apps/pedidos/tarefas.py:92-130`, especialmente o filtro `estado__situacao__in` em `:102`.

**Reprodução:** gerar a tentativa 1, expirá-la e sincronizar; gerar a tentativa 2, aprová-la e sincronizar às T0+3h, quitando o pedido. Às T0+25h, aprovar a tentativa 1 no simulador sem entregar o aviso e executar a tarefa da margem. Resultado: só existe `('quita', '')`; falta `('devolucao', 'duplicidade')`. O pagamento adicional recebido não é reconhecido por essa rotina. No controle, a mesma situação seguida de `consultar_antes_de_decidir(referencia)` registra a devolução corretamente.

A E08-05 escolheu reconsultar apenas aguardando/cancelado, contrariando a obrigação mais abrangente da infraestrutura. Não é um erro da decisão de duplicidade da E08-04: ela sequer recebe a nova resposta. Um aviso posterior ou a apuração futura pode recuperar o pagamento, mas não substitui a conciliação obrigatória durante a margem.

**Correção:** alinhar a spec da E08-05 à fonte superior e cobrir todos os pedidos/tentativas do ciclo, inclusive os já pagos, preservando o reconhecimento único e a devolução integral do excedente. Acrescentar Red/Green desse caso sem depender da entrega do aviso. Não é necessária nova decisão comercial.

## R02 — IMPORTANTE — Suspensão/remoção não impede cobrança que estava somente enfileirada

**Referências:** funcional §2; E08-06, objetivo, casos de concorrência e A-11; integração com E08-03. Código: `apps/pedidos/cancelamento.py:61-65`, `apps/pedidos/operacoes.py:24-57`.

**Reprodução em duas variantes:** pedir pagamento (tentativa `solicitada`); suspender ou remover a conta antes do worker; processar a fila duas vezes. O pedido fica cancelado, mas a tentativa passa a `criada`, existe uma cobrança `pendente` no simulador e não existe chamada de cancelamento. Resultado em ambas: `{'tentativa': 'criada', 'cobrancas_pendentes': ['sim-…'], 'cancelamentos': []}`.

A moderação só percorre tentativas `criada`, e o executor da criação só verifica o prazo. A conclusão tampouco reavalia o cancelamento. O teste versionado de E08-06 A-11 (`test_pedidos_concorrencia.py:339`) executa `pedir_pagamento` **e** `processar_chamadas` na transação que segura a trava, eliminando justamente a janela entre solicitação e criação que existe na aplicação. O implementador registrou a limitação; esta prova confirma o efeito. A devolução de eventual pagamento posterior não equivale a cancelar a cobrança pendente.

**Correção:** coordenar solicitação/criação e moderação: evitar criar quando o cancelamento já é conhecido e recuperar/cancelar a cobrança se a criação já estiver em andamento ou confirmada remotamente. Cobrir suspensão e remoção, tentativa somente solicitada e criação em andamento, sem violar a ordem das travas nem bloquear a moderação esperando uma chamada externa. Não reabrir o pedido nem restaurá-lo na reativação.

## R03 — IMPORTANTE — Resposta perdida perto de 24h deixa cobrança real fora do cancelamento ativo

**Referências:** infraestrutura 4.2 (recuperação com chave estável) e 4.3/4.5 (cancelamento ativo em 24h); E08-03 A-6/A-9 e E08-05 A-3. Código: `apps/pedidos/operacoes.py:29-34,59-65`, `apps/pedidos/tarefas.py:40-56`.

**Reprodução:** às T0+23h59m30s, solicitar pagamento e configurar `falhar_proximas(1, operacao='criar_cobranca', depois_de_executar=True)`. O provedor cria a cobrança, mas a resposta se perde. Às T0+24h01m, repetir o processamento, executar reconsulta da margem, bloqueio e processamento. Resultado: `{'situacao_provedor': 'pendente', 'tentativa': 'nao_criada', 'id_tentativa': None, 'pagamento_conhecido': True}`.

A segunda execução recusa pelo prazo antes de recuperar o resultado anterior e marca a tentativa como não criada. Mesmo depois de a busca encontrar a cobrança, o bloqueio só percorre tentativas `criada`, então nada é cancelado. Configurar `expira_em` não substitui o cancelamento ativo explicitamente exigido; o simulador permite demonstrar a cobrança ainda pendente.

**Correção:** distinguir uma tentativa realmente não executada de resultado remoto incerto. Recuperar e vincular a cobrança que já existia ou garantir seu cancelamento a partir do pagamento encontrado. Preservar a proibição de criar cobrança nova depois de 24h; não resolver simplesmente retirando a conferência do prazo. Cobrir também a repetição após falha local de conclusão e a idempotência do cancelamento.

## R04 — IMPORTANTE; ponto BLOQUEADO POR DECISÃO — Subtotal zero válido aborta a abertura inteira

**Referências:** funcional §§4.2 e 9; E08-01 validação/arredondamento; E08-02, constraint `produtos > 0`. Código: `apps/pedidos/calculo.py:112-142`, `apps/pedidos/abertura.py:152`, `apps/pedidos/models.py:106`.

**Reprodução:** ao arranjo comum de R$170,00, acrescentar outro comprador com 0,001 kg de um produto de R$0,01/kg, incremento 0,001. O produto passa em `full_clean()` e a quantidade é um múltiplo exato. O subtotal é R$0,00 após ROUND_HALF_UP; a rodada continua acima do mínimo. Abrir pagamento provoca `IntegrityError`, constraint `pedido_produtos_positivo`, e desfaz todos os pedidos (`pedidos gravados=0`). A view não trata esse erro; a conclusão de resposta 500 decorre da inspeção do caminho, não de uma prova HTTP separada.

A fonte permite essa combinação e manda arredondar assim. A spec da abertura exige pedido positivo, sem definir o destino do interesse que arredonda para zero. Não é correto inventar cobrança mínima, descartar a quantidade, nem declarar automaticamente pago sem regra aprovada.

**Decisão solicitada ao responsável durante a revisão, ainda sem resposta ao registrar este parecer:** definir se combinações que resultam em pedido zero serão restringidas previamente, ou se haverá um fluxo explícito de pedido zero sem cobrança, incluindo seu estado e tratamento posterior. O especificador deve detalhar o caso antes da correção; depois, testar a abertura inteira, os demais compradores e o rateio. Este ponto permanece parado, sem implementação presumida.

## R05 — IMPORTANTE — Suíte entregue vermelha por teste de fronteira mais restritivo que o requisito

**Referências:** AGENTS.md §8; E07-03 A-12 (a referência correta, não E07-01 A-12); E08-07 A-1 a A-8. Código do teste: `tests/tecnicos/test_pagamentos_fronteiras.py:83-87`.

A suíte completa falha porque o teste inclui os módulos `apps.pagamentos` **e** `apps.simulador_pagamentos` no conjunto que só admite `pagamentos_avisos`. As cinco rotas do simulador são expressamente autorizadas pela E08-07. E07-03 A-12 restringe a rota de `apps.pagamentos` e proíbe gravação externa dos registros de pagamento; não proíbe a tela que altera o estado do provedor simulado. As views novas usam os controles do simulador, e a entrada no sistema continua pela consulta/sincronização.

**Encaminhamento técnico, sem decisão comercial adicional:** alinhar o teste ao requisito, distinguindo os dois módulos, permitindo somente as cinco rotas especificadas no simulador e mantendo a prova negativa contra rotas indevidas/escrita manual. Preservar políticas, bloqueio sem simulador e varreduras. Rodar a suíte completa sem `--deselect`. O revisor não corrigiu o teste auditado. A suposta necessidade de escolher entre mover views ou mudar regra de negócio não se sustenta pela precedência documental.

## R06 — IMPORTANTE — Evidência de TDD não comprova todos os gates exigidos

**Referências:** AGENTS.md §§3, 4 e 8; prevenção de E05-R04 (E05-01/spec.md, ciclo funcional verde sem trava → Red concorrente → trava) e E06-R05 (E06-05/spec.md:190-192, Red antes do Green e proibição de substituir Red histórico por andaime recriado).

Há registros por critério nas sete fatias, com resultados e justificativas de controles já verdes. Resultados declarados: E08-01 **27/3**; E08-02 **42/16**, depois **22/1**; E08-03 **28/20**; E08-04 **25/42**; E08-05 **16/17**; E08-06 **12/13**; E08-07 **7/24** (falhas/aprovações). As execuções atuais não comprovam a ordem histórica.

Dois pontos impedem aceitar a documentação como suficiente:

1. **E08-02 A-4/A-11.** O próprio registro, linhas 23–24 do conteúdo original, afirma que o primeiro Red não foi do comportamento e que a execução seguinte usou o “andaime trocado de volta”, sem base de imutabilidade, restrições, migração 0002 e serviço real. Isso demonstra sensibilidade contra aquela versão, mas não comprova que a falha válida precedeu a implementação. Foi solicitada ao usuário a cronologia/evidência; ainda não recebida ao registrar o parecer. Não se afirma, sem ela, uma cronologia que não foi observada.
2. **Ciclos específicos das travas.** E08-02 A-20/A-21, E08-03 A-19, E08-04 A-16/A-17 e E08-06 A-11 têm Reds registrados contra serviços vazios/sem receptor, falhando por ausência de abertura, tentativa, destino ou cancelamento. Os registros não mostram a sequência funcional já verde sem proteção → Red da corrida → implementação da proteção, exigida pela prevenção de E05-R04. Um Red por ausência de todo o comportamento não documenta esse ciclo específico. E08-05 A-20, declarado controle já verde sobre a quitação herdada, não é por si uma infração nova nem motivo para fabricar Red.

**Exigido:** complementar a cronologia com evidências existentes e separar regressões já verdes de comportamentos novos. Se o Red válido não precedeu a implementação, registrar a não conformidade verdadeira e encaminhar seu tratamento ao responsável, preservando o histórico. Não refazer o passado com andaimes nem chamar mutação de Red histórico; tratamentos aprovados em E05/E06 não constituem dispensa automática para E08. Nenhuma reconstrução ou mutação foi executada nesta revisão para suprir essa falta.

## R07 — MELHORIA documental não impeditiva — Duas cláusulas de aceitação contradizem regras superiores já claras

E08-02 A-12 pede 409 também para o administrador em rota exclusiva de comprador ativo; a política vigente o recusa antes, com 403/redirecionamento. A-21 pede ausência de aviso de preço em ambas as ordens, mas uma alteração confirmada **antes** da abertura deve avisar quem ainda tem reserva ativa (funcional §5.1/E05-06). Os testes seguem corretamente essas regras superiores: mantêm aviso na ordem preço-antes e o suprimem quando o preço vem depois do congelamento.

Alinhar a redação dos critérios, sem alterar autorização nem emissão de avisos. Não requer nova decisão de negócio nem reprova os comportamentos corretos. Registrado em `docs/melhorias.md` como **M-3**, para revisão conforme a política de melhorias. M-2 já registra a heurística de escrita dos modelos; não foi duplicado nem implementado nesta revisão.

## Próximo gate e limites

E08 não está pronta. R01–R03 e R05 têm encaminhamento técnico derivável dos requisitos; as specs devem cobrir as combinações que faltaram. R04 aguarda decisão sobre valor zero; R06 aguarda evidência histórica suficiente ou tratamento autorizado. Após correções, reexecutar a suíte sem exclusões, as provas abaixo e as corridas relevantes, e submeter nova revisão.

Foram alterados somente os sete review.md da E08 e o registro de melhorias. Os textos anteriores do implementador foram preservados integralmente como sufixo. As provas usam PostgreSQL, simulador e serviços reais; a suíte usa também cliente HTTP do Django e threads. Não houve navegador, provedor externo, dinheiro real ou worker como processo separado. A revisão não antecipa livro-razão, execução de estornos ou apuração das próximas etapas.

## Provas independentes completas

Salvar o bloco abaixo em `%TEMP%/test_review_e08_2714a6a.py` e executar o comando registrado acima. O cenário de R04 demonstra o erro não tratado, sem prescrever o tratamento comercial do valor zero.

```python
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import transaction
from apps.contas.moderacao import suspender, remover
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
from apps.pagamentos.consulta import consultar_antes_de_decidir
from apps.pedidos.models import DestinoDoPagamento, SituacaoDoPedido
from apps.pedidos.pagamento import pedir_pagamento
from apps.pedidos.tarefas import reconsultar_pagamentos_da_margem_agora, bloquear_tentativas_vencidas_agora
from apps.simulador_pagamentos import controle as sim
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.pedidos import T0, pedido_aberto, tentativa_criada, sincronizar
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])

@pytest.fixture(autouse=True)
def relogio():
    r=RelogioControlado()
    sim.reiniciar()
    yield r
    r.parar()
    sim.reiniciar()


def duas_tentativas(relogio):
    arranjo,pedido=pedido_aberto(relogio)
    primeira=tentativa_criada(pedido)
    sim.expirar(primeira.id_externo)
    sincronizar(primeira.id_externo)
    relogio.congelar(T0+timedelta(hours=2))
    segunda=tentativa_criada(pedido)
    return pedido,primeira,segunda


def test_margem_reconsulta_duplicidade_de_pedido_ja_pago(relogio):
    pedido,primeira,segunda=duas_tentativas(relogio)
    relogio.congelar(T0+timedelta(hours=3))
    sim.aprovar(segunda.id_externo)
    sincronizar(segunda.id_externo)
    assert SituacaoDoPedido.objects.get(pedido=pedido).situacao=='pago'
    relogio.congelar(T0+timedelta(hours=25))
    sim.aprovar(primeira.id_externo)
    reconsultar_pagamentos_da_margem_agora()
    achados=list(DestinoDoPagamento.objects.filter(pedido=pedido).values_list('destino','motivo'))
    assert sorted(achados)==[('devolucao','duplicidade'),('quita','')],achados


def test_busca_explicita_recupera_a_duplicidade_controle(relogio):
    pedido,primeira,segunda=duas_tentativas(relogio)
    relogio.congelar(T0+timedelta(hours=3))
    sim.aprovar(segunda.id_externo)
    sincronizar(segunda.id_externo)
    relogio.congelar(T0+timedelta(hours=25))
    sim.aprovar(primeira.id_externo)
    consultar_antes_de_decidir(pedido.referencia_externa)
    assert sorted(DestinoDoPagamento.objects.filter(pedido=pedido).values_list('destino','motivo'))==[('devolucao','duplicidade'),('quita','')]


@pytest.mark.parametrize('moderar',[suspender,remover],ids=['suspensao','remocao'])
def test_tentativa_enfileirada_nao_deixa_cobranca_pendente_apos_moderacao(relogio,moderar):
    arranjo,pedido=pedido_aberto(relogio)
    tentativa=pedir_pagamento(arranjo.a,pedido)
    assert tentativa.situacao=='solicitada'
    moderar(arranjo.admin,arranjo.a)
    assert SituacaoDoPedido.objects.get(pedido=pedido).situacao=='cancelado'
    processar_chamadas()
    processar_chamadas()
    tentativa.refresh_from_db()
    pendentes=[c.id_externo for c in CobrancaSimulada.objects.filter(situacao='pendente')]
    assert not pendentes,{'tentativa':tentativa.situacao,'cobrancas_pendentes':pendentes,'cancelamentos':list(ChamadaAoProvedor.objects.filter(operacao='cancelar_cobranca').values_list('alvo',flat=True))}


def test_criacao_confirmada_antes_da_suspensao_e_cancelada_controle(relogio):
    arranjo,pedido=pedido_aberto(relogio)
    tentativa=tentativa_criada(pedido)
    suspender(arranjo.admin,arranjo.a)
    processar_chamadas()
    assert CobrancaSimulada.objects.get().situacao=='cancelado'


def test_criacao_com_resposta_perdida_antes_do_prazo_e_cancelada(relogio):
    arranjo,pedido=pedido_aberto(relogio)
    relogio.congelar(T0+timedelta(hours=23,minutes=59,seconds=30))
    tentativa=pedir_pagamento(arranjo.a,pedido)
    sim.falhar_proximas(1,operacao='criar_cobranca',depois_de_executar=True)
    processar_chamadas()
    assert CobrancaSimulada.objects.count()==1
    relogio.congelar(T0+timedelta(hours=24,minutes=1))
    processar_chamadas()
    reconsultar_pagamentos_da_margem_agora()
    bloquear_tentativas_vencidas_agora()
    processar_chamadas()
    tentativa.refresh_from_db()
    cobranca=CobrancaSimulada.objects.get()
    assert cobranca.situacao=='cancelado',{'situacao_provedor':cobranca.situacao,'tentativa':tentativa.situacao,'id_tentativa':tentativa.id_externo,'pagamento_conhecido':PagamentoNoProvedor.objects.filter(id_externo=cobranca.id_externo).exists()}


def test_abertura_com_subtotal_zero_por_arredondamento(relogio):
    from apps.catalogo.models import Unidade
    from apps.pedidos.abertura import abrir_pagamento
    from apps.pedidos.models import Pedido
    from tests.apoio.pedidos import montar_arranjo
    from tests.fabricas import ContaFactory, ProdutoFactory, EstoqueDaRodadaFactory, ParcelaFactory
    relogio.congelar(T0)
    arranjo=montar_arranjo()
    comprador=ContaFactory.create()
    produto=ProdutoFactory.create(fornecedor=arranjo.fornecedor,unidade=Unidade.KG,incremento=Decimal('0.001'),preco=Decimal('0.01'))
    EstoqueDaRodadaFactory.create(rodada=arranjo.rodada,produto=produto,limite=None)
    ParcelaFactory.create(comprador=comprador,produto=produto,quantidade_original=Decimal('0.001'),quantidade_reservada=Decimal('0.001'),quantidade_pendente=Decimal('0'))
    produto.full_clean()
    try:
        abrir_pagamento(arranjo.admin,arranjo.rodada,Decimal('22.00'))
    except Exception as erro:
        pytest.fail(f'entrada válida provoca {type(erro).__name__}: {erro}; pedidos gravados={Pedido.objects.count()}')

```

---

## Registro anterior integralmente preservado

# E08-01 — Registro do implementador (2026-10-20)

Status: implementada; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia, AGENTS.md e as regras de prevenção da E05-R04 e da E06-R05.

## Arquivos

- `apps/pedidos/` (app novo, em `INSTALLED_APPS`): `apps.py` e `calculo.py` (`ItemACobrar`, `CompradorACobrar`, `ItemCobrado`, `CobrancaDoComprador`, `TAXA_DE_SERVICO`, `calcular_cobranca`). Sem modelos.
- `tests/apoio/varredura_float.py` (código de teste): varredura pela árvore de sintaxe.
- `tests/tecnicos/test_pedidos_calculo.py` (A-1 a A-10 e A-12) e `tests/tecnicos/test_varredura_float.py` (A-11).

## Andaime (exceção técnica)

Antes do Red: o app `apps.pedidos` (sem comportamento), a assinatura e os tipos de `calcular_cobranca` com corpo que devolve lista vazia, e `varrer_arquivo` que devolve lista vazia. Não há comportamento testável nesse andaime; ele só deixa os testes importáveis, para a falha ser por asserção.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pedidos_calculo.py tests/tecnicos/test_varredura_float.py -q`: **27 failed, 3 passed**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_cobranca_rateia_o_frete_pelos_produtos` | falhou: `ValueError: not enough values to unpack` (o resultado era a lista vazia) |
| A-2 | `test_subtotal_arredondado_por_item` | falhou: o resultado era a lista vazia (desempacotamento) |
| A-3 | `test_produtos_soma_os_subtotais_ja_arredondados` | falhou: o resultado era a lista vazia (desempacotamento) |
| A-4 | `test_subtotal_e_arredondado_uma_vez_so` | falhou: o resultado era a lista vazia (desempacotamento) |
| A-5 | `test_centavo_do_frete_vai_ao_menor_comprador_no_empate` | falhou: `[] != [3.34, 3.33, 3.33]` |
| A-6 | `test_frete_pelo_maior_resto` | falhou: `[] != [0.00, 0.00, 0.05]` |
| A-7 | `test_resultado_nao_depende_da_ordem_da_entrada` | falhou: `assert []` |
| A-8, A-9 | `test_frete_zero`, `test_servico_arredonda_meio_centavo_para_cima` | falharam: o resultado era a lista vazia (asserção ou desempacotamento) |
| A-10 | `test_frete_invalido_e_recusado` (7), `test_preco_invalido_e_recusado`, `test_quantidade_invalida_e_recusada` (4), `test_quantidade_float_e_recusada`, `test_estruturas_invalidas_sao_recusadas` | falharam: `DID NOT RAISE ValueError` |
| A-12 | `test_cobranca_aleatoria_respeita_as_invariantes` | falhou: `assert 0 == 19` (comprimento do resultado) |
| A-11 | `test_a_varredura_acusa_float_com_arquivo_e_linha` | falhou: `assert [] == [(1, 'literal float'), ...]` |
| A-11 | `test_modulos_de_dinheiro_nao_usam_float`, `test_a_varredura_cobre_os_modulos_e_ignora_as_migracoes`, `test_a_varredura_nao_acusa_inteiros_decimais_nem_anotacoes` | **passaram no Red**: controles. Com a varredura vazia os módulos "estão limpos" por definição, e a cobertura da lista de arquivos não depende da varredura. Protegem contra regressão; a prova positiva de que a varredura enxerga `float` é o teste do arquivo temporário, que falhou. |

## Green e verificações

- Os dois arquivos: **30 passed**.
- `ruff check`, `ruff format --check` e `mypy .` sem erros. A varredura nova não encontrou `float` nos oito conjuntos de módulos do A-11.
- A suíte completa é rodada ao final da milestone e registrada na última fatia.

## Decisões técnicas

- O maior resto é calculado em `Decimal` exato (`frete * P / T` sem arredondamento intermediário); o truncamento usa `ROUND_DOWN` a centavos, e o desempate é por `comprador_id`.
- Os validadores de preço, quantidade e frete exigem `Decimal` (nunca `float` nem `bool`) e recusam excesso de casas sem arredondar.
- A semente do A-12 é `20261102`; `random.Random` leva `noqa: S311` porque é teste com semente fixa.

## Limites da verificação

Função pura: sem banco, rede ou navegador. Nenhuma mutação aplicada.

---

## Registro do implementador — correções R01 a R06 (2026-10-21)

Status: implementadas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Fontes lidas antes de editar: o parecer em `docs/specs/E08-01/review.md` e as seções de correção de cada `spec.md` e `acceptance.md` (commit `7a1fb49`).

Resumo das correções (detalhes e Red/Green no `review.md` de cada fatia):

| Achado | Onde está o registro | Commit |
|---|---|---|
| R05 | E08-07 | `3a7bdf6` |
| R04 | E08-02 | `705a5b5`, `0c94ecf` (anotação de tipo) |
| R02, R03 (criação) | E08-03 e E08-06 | `9b8d512` |
| R01, R03 (bloqueio) | E08-05 | `4aebf38` |
| R06 | E08-02 (A-4, A-11, A-20, A-21), E08-03 (A-19), E08-04 (A-16, A-17), E08-06 (A-11) | registros |
| R07 | `docs/melhorias.md` (M-3), sem implementação | — |

**Verificação final** (sem `--deselect` e sem filtro):

```
ruff check: All checks passed!
ruff format --check: 291 files already formatted
mypy: Success: no issues found in 342 source files
makemigrations --check: No changes detected
pytest: 2160 passed in 247.71s (0:04:07)
```

Comandos: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` e `uv run pytest -q`.

**Pontos para o revisor:** (1) mutações do A-20 (só a trava da rodada) e do A-17 não foram detectadas pelos testes atuais, com reforço proposto nos registros da E08-02 e da E08-04; (2) o E08-06 A-11 reescrito não teve Red próprio (Red tardio, declarado na E08-06); (3) a prova R04 do parecer foi substituída pelos critérios A-22 a A-27, porque a fábrica de produto agora é recusada pelo `CHECK`; (4) a §4.2 da especificação funcional não foi alterada.

## Registro do implementador — correções da segunda revisão, R08 e R06 (2026-10-21)

Especificações: commit `a41b44f` (seção "Correções da segunda revisão da E08" de `docs/specs/E08-01/spec.md`). R01 a R05 estavam encerrados; R07 segue como M-3 e M-4 fica para a revisão final.

| Achado | Onde está o registro | Commit |
|---|---|---|
| R08 | E08-03 ("Registro do implementador — correção R08") | `6118ae4` |
| R06, A-11 reescrito | E08-06 ("Não conformidade de TDD (R06) — A-11 reescrito (segunda revisão)") | registros |

Ordem seguida: primeiro o R08 (verde funcional e Red das corridas contra o código anterior, depois a correção); depois o registro do R06.

**Verificação final** (sem `--deselect` e sem filtro):

```
ruff check: All checks passed!
ruff format --check: 291 files already formatted
mypy: Success: no issues found in 342 source files
makemigrations --check: No changes detected
pytest: 2166 passed in 259.82s (0:04:19)
```

**Pontos para o revisor:** (1) o A-32 passou já no Red (o rollback da transação da chamada já existia) e o A-31 é verde funcional com Red só na asserção estrutural: interpretação declarada na E08-03; (2) os testes A-23 e A-24 da correção R03 só tiveram o ponto de observação ajustado, listados com antes e depois; (3) a invariante "nenhuma transação de chamada sincroniza mais de um pagamento" foi conferida em todos os chamadores de `sincronizar_pagamento`, e só o `_criacao_falhou` a violava; (4) as mutações do A-20 e do A-17 seguem como declarado (M-4 para o A-17).
