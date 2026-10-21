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
