# E12-07 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_ponta_a_ponta.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-8 | `49b954c` | **8 passed; suíte completa 2900 passed**; `ruff`, `mypy`, `makemigrations --check` limpos |

## Sobre o Red
A fatia, pelo `spec.md`, não cria comportamento novo: os cenários exercitam o que as E12-01 a E12-06 entregaram. Não há Red de código de produção; os testes são de regressão ponta a ponta e passaram assim que os ajustes do próprio teste (abaixo) foram feitos. Isso é registrado como tal, e não como Red.

## Ajustes do próprio teste (antes de passar; nenhum afrouxa asserção de comportamento)
- **A-3:** a autorização acontece 3 dias depois: o pagamento aprovado depois da margem só fica liberado para estorno com o saldo do provedor depois disso (antes, `saldo_insuficiente`, `falha_temporaria` do simulador). **Ponto para o especificador:** o critério não fala do prazo de liberação.
- **A-4:** o aporte e o movimento de cobertura de despesa vão em transações separadas (regra de ordem das travas do livro); a falta de cobertura vem desse movimento, como na E12-03 A-10.
- **A-5:** o estorno da parcial é 2,50 (2,00 de produtos, 0,10 de serviço e 0,40 de frete), e o pedido de 7,99 + 0,40 + 1,60 vale 9,99; o critério fala de 2,00 do item e de "igual ao pago".
- O administrador entra de novo (`entrar_de_novo`) depois de cada avanço do relógio, como na E11-07.


## Parecer independente — agente 3 — 2026-11-01

Base auditada: `8e236e5`, branch `e12-implementacao`, comparada à E11 integrada em `d098654`. Funcional v1.7, infraestrutura v1.8, especificações e critérios das sete fatias lidos antes da avaliação da implementação. Conteúdo anterior preservado integralmente. Evidências, veredito da etapa e reproduções no [parecer consolidado E12-07](../E12-07/review.md).

**Veredito final da E12: REPROVADO sobre `8e236e5`.** Três achados abertos: R03 bloqueador, R01 e R02 importantes. Testes existentes verdes não cobrem essas combinações de ciclos e cancelamento.

### R03 — bloqueador — deadlock ao cancelar com pagamento tardio de ciclo anterior

Referências: AGENTS.md §6 (concorrência e recuperação financeira); funcional §7.2/§8.3; E12-02 regra 2; E12-03 regras 1, 3 e 4; E12-04 concorrência; E12-07 integração. Código: `apps/pedidos/cancelamento_da_rodada.py:106`, `:229`, `:252`, `:258` e `:488`; `apps/financeiro/reembolsos.py:236`; `apps/pedidos/quitacao.py:235`; `apps/financeiro/receptores.py:15`.

Arranjo: AP-insuficiente, X pago, segunda cobrança de X criada antes do prazo; apuração em 48h retorna a rodada ao interesse e gera a obrigação de mínimo do ciclo anterior. O cancelamento com reembolso termina a consulta prévia; nesse intervalo o provedor informa a aprovação tardia da segunda cobrança. A sincronização segura a situação do pedido anterior. O cancelamento, sem abertura vigente em pagamento, não trava essa situação no passo inicial: trava primeiro as fontes financeiras de todas as aberturas e depois tenta travar o pedido anterior em `reembolso_integral_do_pedido`, mesmo já integralmente reembolsado. A sincronização tenta travar a receita de serviço, incluída em `contas_do_destino`, e espera o cancelamento. Forma-se o ciclo de espera.

Duas execuções independentes da prova final reproduziram `OperationalError: deadlock detected`, no cancelamento, com contexto `while locking tuple ... in relation "pedidos_situacaodopedido"`. A transação é abortada; o usuário não obtém o cancelamento. Não se demonstrou duplicação de devolução ou perda de dinheiro: o achado é a falha operacional por inversão de travas.

O teste usa duas conexões reais e o provedor simulado real. Os wrappers apenas sincronizam os pontos após consulta, após decisão do motivo com situação travada e após trava das fontes; não removem validações, travas ou efeitos. A aprovação tardia de cobrança cancelada é suportada pelo simulador e já faz parte dos cenários de pagamentos tardios do projeto. A hipótese inicial de corrida com autorização de devolução não foi tomada como achado: a reprodução confirmada é com sincronização de pagamento tardio.

Correção requerida: definir e aplicar a ordem de aquisição das situações de todos os pedidos que serão alcançados pelo reembolso, antes das contas financeiras. Alinhar E12-02 ("anteriores só são lidos") com o uso real da E12-03. É correção técnica derivada da ordem global, sem decisão comercial pendente. Acrescentar teste concorrente de ciclo anterior, além dos testes atuais da abertura vigente.

### R01 — importante — tela promete reservas removidas pelo cancelamento

Referências: funcional §7/§7.2; E12-01 regra 6; E12-06 regra 7 e fonte do aviso. Código: `apps/pedidos/views.py:50`, `templates/pedidos/detalhe.html:24`, `apps/pedidos/apuracao_tela.py:176`.

AP-insuficiente: X pago; apuração retorna ao interesse; cancelamento sem reembolso zera corretamente as reservas. GET do próprio pedido responde 200 e mostra o cancelamento, mas também afirma "seus interesses continuam reservados na rodada" no bloco da apuração anterior. A prova confere `total_reservado(P1) == 0` antes de testar a página. Não é defeito do registro histórico da apuração: a composição dos dois blocos apresenta como atual um efeito superado pelo cancelamento.

Correção requerida: apresentar cancelamento como estado vigente, sem promessa atual de reservas; se exibir a apuração anterior, identificá-la como histórico. Preservar pedidos, apuração e devoluções anteriores. Cobrir cancelamento após retorno, com ambas as indicações.

### R02 — importante — aviso sem reembolso perde a condição de pagante de ciclo anterior

Referências: funcional §7.2/§12; E12-05 regra 4 (pagante sem reembolso), regras 2/5 (destinatários e link); E12-02 caso de retorno ao interesse. Código: `apps/pedidos/cancelamento_da_rodada.py:106`, `:388` a `:427`, `:488` a `:496`.

No mesmo arranjo, A tem pedido X pago e devolução integral de mínimo ainda pendente. Ao cancelar sem reembolso, A recebe somente "Seus interesses nesta rodada foram removidos. Sem novas devoluções." Falta a informação exigida para pagantes: "O cancelamento não inicia novas devoluções. As devoluções já devidas continuam em andamento." O código também escolhe `/carrinho/`, pois não considera o pedido anterior nesse ramo. O teste falha na primeira asserção do corpo; a seleção do link foi confirmada pela leitura do código, não por uma asserção alcançada nessa execução.

Causa: a lista de pedidos/pagos é da abertura vigente; o recurso `sem_saldo` inclui históricos somente quando `com_reembolso=True`. O comprador continua destinatário por suas parcelas restauradas, mas é classificado como se não tivesse pago. Não houve apagamento real de obrigação. Corrigir a informação do aviso sem criar ou autorizar devoluções no ramo sem reembolso e sem incluir destinatários que só possuem fila não afetada.

### Verificações independentes

- Suíte completa sobre `8e236e5`, sem filtro: **2900 passed in 488.01s (0:08:08)**. Comando: `.venv/Scripts/python.exe -u "$env:TEMP/revisor_e12.py" -q -p no:cacheprovider --tb=short`, com `PYTHONPATH` na raiz. Runner define `DJANGO_SETTINGS_MODULE=config.settings.test`, configura somente `settings.DATABASES[*]["TEST"]["NAME"] = "test_organicos_revisor_e12_8e236e5"` e chama `pytest.main(sys.argv[1:])`. Banco PostgreSQL de teste isolado, sem editar configurações versionadas. Coleta anterior à criação das provas adicionais.
- Provas adicionais abaixo: **3 failed in 7.71s**. Mesmo runner com banco `test_organicos_revisor_e12_provas` e argumento `tests/tecnicos/test_cancelamento_revisao_temporaria.py`. Falhas de comportamento para R01/R02 e deadlock real para R03. O ensaio inicial da prova concorrente teve erro no próprio harness (assinatura/transação da sincronização); foi corrigido antes das duas reproduções válidas e não é usado como evidência do defeito.
- `.venv/Scripts/ruff.exe check .`: All checks passed; `.venv/Scripts/ruff.exe format --check .`: 370 files already formatted; `.venv/Scripts/mypy.exe .`: 448 source files sem erros. Executados antes da prova temporária.
- Com `DJANGO_SETTINGS_MODULE=config.settings.test`: `.venv/Scripts/python.exe manage.py check`: 0 issues; `manage.py makemigrations --check --dry-run`: No changes detected.

### Matriz e TDD

| Fatia | Critérios confrontados | Parecer |
|---|---|---|
| E12-01 | A-1 a A-20: estado, interesses, histórico, recusas e corridas | Sem achado próprio; etapa não aprovada |
| E12-02 | A-1 a A-16: pedidos, chamadas, bloqueios, preservação e concorrência | R03, integração com pedidos anteriores |
| E12-03 | A-1 a A-18: componentes, abatimento, financiamento, autorização, retry e exceção | R03 bloqueador |
| E12-04 | A-1 a A-8: destino, alertas, idempotência e escopo da autorização | Sem achado próprio; corrida de integração coberta por R03 |
| E12-05 | A-1 a A-7: textos, destinatários, privacidade, idempotência e canal | R02 importante |
| E12-06 | A-1 a A-19: HTTP, acesso, passkey, dados, estados e comprador | R01 importante |
| E12-07 | A-1 a A-8: simulador, execução, arredondamento, nova rodada e repetição | REPROVADO pelos cenários adicionais R01–R03 |

Registros e sequência de commits conferidos: `c9d2d08 → 670dee8`, `349f230 → de6bd01`, `610340b → e3fe30c`, `d23dbd5 → 94ce35d`, `478a51b → f95a3ce`, `7fc01ec → 4a07358`. A E12-07 (`49b954c`) é regressão sem novo comportamento, conforme a própria especificação; ausência de Red de produção explicitamente justificada. Não reexecutei os commits históricos Red. O Green foi executado independentemente; as provas adicionais fornecem Red atual dos achados.

Ajustes documentados de arranjo foram avaliados: falhar `buscar_por_referencia` em vez da consulta individual exercita a falha real do caminho; consumo de receita por despesa exercita falta de cobertura; soma do parcial inclui serviço/frete; espera pela liberação do saldo do simulador respeita seu comportamento. A asserção antiga de ausência de qualquer formulário de estoque agora permite apenas o cancelamento exigido pela E12. Não identifiquei remoção de teste para esconder os três achados; eles decorrem de combinações não cobertas. Os detalhes de critérios divergentes devem ser alinhados nos documentos pelo especificador, sem mudar negócio.

Limite da evidência E12-07: os testes A-6 a A-8 não chamam `_invariante_ok()` ao final, embora a regra comum peça a verificação em cada cenário. Completar essa cobertura ao revalidar a fatia; não alegar que o invariante foi explicitamente verificado nesses três testes. O caso depois de repasse e a decisão sobre cancelamento de rodada encerrada permanecem nos gates E13/E14 previstos. Sem inspeção visual em navegador; telas avaliadas por HTTP, templates e contexto.

### Reprodução preservada

Arquivo temporário próprio removido antes do commit dos pareceres. Nenhum código de produção corrigido pelo revisor.

```python
from decimal import Decimal as D
import pytest
from django.test import Client
from apps.pedidos.apuracao import iniciar_apuracao
from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
from apps.interesses.consultas import total_reservado
from apps.notificacoes.models import Notificacao
from tests.apoio.apuracao import arranjo_ap, pagar, H
from tests.apoio.pedidos import T0

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])


def retorno(relogio, sim):
    a,x,_=arranjo_ap(relogio,minimo="100.00",limites=(11,12))
    pagar(relogio,sim,x)
    relogio.congelar(T0+48*H)
    iniciar_apuracao(a.admin,a.rodada)
    return a,x


def test_cancelamento_nao_promete_reservas_do_retorno_anterior(relogio,simulador_pagamentos):
    a,x=retorno(relogio,simulador_pagamentos)
    cancelar_rodada(a.admin,a.rodada,com_reembolso=False)
    assert total_reservado(a.p1)==D("0")
    cliente=Client()
    cliente.force_login(a.a)
    resposta=cliente.get(f"/pedidos/{x.pk}/")
    assert resposta.status_code==200
    pagina=resposta.content.decode()
    assert "A rodada foi cancelada pelo administrador." in pagina
    assert "seus interesses continuam reservados na rodada" not in pagina


def test_aviso_sem_reembolso_reconhece_pedido_pago_de_ciclo_anterior(relogio,simulador_pagamentos):
    a,x=retorno(relogio,simulador_pagamentos)
    cancelar_rodada(a.admin,a.rodada,com_reembolso=False)
    aviso=Notificacao.objects.get(conta=a.a,evento="rodada_cancelada")
    assert "As devoluções já devidas continuam em andamento." in aviso.corpo
    assert aviso.link==f"/pedidos/{x.pk}/"


def test_cancelamento_de_ciclo_anterior_concorre_com_pagamento_tardio(relogio,simulador_pagamentos,monkeypatch):
    from threading import Event
    from apps.pagamentos.provedor import obter_provedor, NovaCobranca
    from tests.apoio.pedidos import sincronizar
    from apps.pedidos import cancelamento_da_rodada as cancelamento, quitacao
    from tests.apoio.concorrencia import executar_em_paralelo
    a,x,_=arranjo_ap(relogio,minimo="100.00",limites=(11,12))
    pagar(relogio,simulador_pagamentos,x)
    extra=obter_provedor().criar_cobranca(NovaCobranca("extra-revisor",x.referencia_externa,x.total,"Pedido",T0+24*H)).pagamento.id_externo
    relogio.congelar(T0+48*H)
    iniciar_apuracao(a.admin,a.rodada)
    consultado,estado_travado,fontes_travadas=Event(),Event(),Event()
    consultar_original=cancelamento._consultar_antes_de_cancelar
    motivo_original=quitacao._motivo_da_devolucao
    travar_original=cancelamento.travar_contas
    def consultar(*args,**kwargs):
        resultado=consultar_original(*args,**kwargs)
        consultado.set()
        assert estado_travado.wait(10)
        return resultado
    def motivo(*args,**kwargs):
        resultado=motivo_original(*args,**kwargs)
        estado_travado.set()
        assert fontes_travadas.wait(10)
        return resultado
    def travar(*args,**kwargs):
        resultado=travar_original(*args,**kwargs)
        fontes_travadas.set()
        return resultado
    monkeypatch.setattr(cancelamento,"_consultar_antes_de_cancelar",consultar)
    monkeypatch.setattr(quitacao,"_motivo_da_devolucao",motivo)
    monkeypatch.setattr(cancelamento,"travar_contas",travar)
    def cancelar(barreira):
        barreira.wait()
        return cancelar_rodada(a.admin,a.rodada,com_reembolso=True)
    def pagamento(barreira):
        barreira.wait()
        assert consultado.wait(10)
        simulador_pagamentos.aprovar(extra,em=T0+47*H)
        return sincronizar(extra)
    resultados=executar_em_paralelo(cancelar,pagamento)
    assert [r.excecao for r in resultados]==[None,None]
```

### Encaminhamento

R03 volta ao implementador e ao especificador para alinhar o detalhamento técnico da ordem das travas; R01/R02 voltam ao implementador com testes Red/Green. Não há decisão comercial necessária para resolver os três. Reexecutar as provas preservadas, os critérios afetados e regressões relevantes antes de nova revisão. Nenhuma melhoria não impeditiva nova foi aberta. Entrega: somente os sete `review.md`, com conteúdo anterior preservado, sem push ou PR.

## Correção da revisão — agente 2 — 2026-11-01

**Cenário 8 e invariante em todos os testes (A-9 e A-10).**

- **A-9** (`7a10818`, `test_cancelamento_depois_de_um_retorno_ao_interesse[sim|nao]`): AP-R pela tela, `processar_chamadas`. Este arquivo não cria comportamento novo; como o Red da fatia depende das correções R01 a R03, reverti temporariamente os arquivos de `apps/` para `8e236e5` (`git apply -R` do diff, reaplicado em seguida, árvore limpa) e rodei o arquivo: **2 failed, 8 passed**, as duas variantes do A-9 falhando por "seus interesses continuam reservados na rodada" e pelo link `/carrinho/` no lugar de `/pedidos/<X>/`. Com a produção atual: 10 passed.
- **A-10:** `_invariante_ok()` passou a ser a última asserção de A-6, A-7 e A-8 (e dos demais já tinha). Todos passam.
- **Alinhamentos A-3 e A-5:** os valores e o prazo já eram os do critério corrigido (7,49 e 94,35; autorização em `PRAZO + 3 dias`).

**Provas do revisor (arquivo temporário, removido, nunca commitado):**

| Prova | Resultado sobre a correção |
|---|---|
| `test_cancelamento_nao_promete_reservas_do_retorno_anterior` | passa sem mudança |
| `test_aviso_sem_reembolso_reconhece_pedido_pago_de_ciclo_anterior` | passa sem mudança |
| `test_cancelamento_de_ciclo_anterior_concorre_com_pagamento_tardio` | sem impasse; a pausa do teste original espera a trava das contas, que agora vem depois da liberação da situação (E12-03 A-19, adaptada como o `acceptance.md` prevê) |

Os mesmos casos estão nos testes permanentes: E12-06 A-20, E12-05 A-8 e E12-03 A-19.


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `5705e5d`, branch `e12-implementacao`, correções desde `4370b11`. Adendos `0fdfe8f`/`f429fc6` lidos e confrontados com o código, os critérios e os registros Red/Green. Conteúdo anterior preservado. Evidências completas no [parecer consolidado E12-07](../E12-07/review.md).

### Avaliação das correções

**R01 encerrado:** a existência do cancelamento transforma o retorno ao interesse em informação histórica no contexto; o template não apresenta a frase de reserva atual. O estado vigente aparece primeiro, e o pedido sem novo reembolso informa a continuidade das devoluções anteriores. Registros históricos e cálculos não mudam.

**R02 encerrado:** pagantes de qualquer abertura são identificados pela mesma fonte nas duas indicações, depois das travas de situação; a classificação independe de reembolso novo. A implementação contempla o pagante suspenso sem parcelas restauradas e o pagante de ciclo anterior cujo pedido atual foi cancelado. Destinatários, textos, links e ausência de novos movimentos no ramo sem reembolso foram confrontados com os novos critérios.

**R03 encerrado:** `_travar_as_situacoes` é executado depois das travas de contas de compradores/fornecedor/rodada/estoque/parcelas e antes dos efeitos em pedidos, chamadas e contas financeiras. A consulta única, ordenada por `pedido_id`, alcança todas as aberturas. Ao executar o reembolso de um pedido antigo, sua situação já está travada. Isso elimina a inversão situação ↔ fontes financeiras demonstrada na revisão anterior. A correção não adquire trava de pagamento ou destino dentro dessa transação. O adendo substitui explicitamente a decisão técnica que causava a inversão; nenhum conflito de regra comercial permanece.

A cobertura adicional E12-07 A-9 exercita o cancelamento após retorno pela tela, com as duas indicações. A-10 acrescenta `_invariante_ok()` ao final dos testes A-6/A-7/A-8, fechando a limitação registrada anteriormente. Os demais critérios e os gates futuros E13/E14 mantêm seu escopo.

### Provas independentes e adaptação necessária de R03

Os três testes do bloco Python do parecer anterior foram extraídos para `tests/tecnicos/test_cancelamento_revisao_temporaria.py`. R01 e R02 foram executados literalmente. Em R03, preservados arranjo, operações, wrappers das funções reais e asserção final de ausência de exceções, houve apenas esta adaptação:

```python
from tests.apoio.trava import esperar_outra_conexao_na_trava
# Dentro do wrapper motivo(), depois de estado_travado.set():
# antes: assert fontes_travadas.wait(10)
esperar_outra_conexao_na_trava()
```

Esperar a aquisição das contas pelo cancelamento enquanto a sincronização retém a situação criaria uma espera circular no próprio teste corrigido. A nova pausa espera o cancelamento bloquear na situação e então libera a sincronização. A correção E12-03/acceptance.md prevê exatamente essa adaptação. O Red real da implementação anterior continua preservado neste documento; timeout do harness antigo não seria evidência de regressão.

Resultado independente: **3 passed in 13.97s**. Comando: `.venv/Scripts/python.exe -u "$env:TEMP/revisor_e12_provas.py" tests/tecnicos/test_cancelamento_revisao_temporaria.py -q -p no:cacheprovider --tb=short`, com `PYTHONPATH` na raiz, `config.settings.test` e banco PostgreSQL isolado `test_organicos_revisor_e12_provas`. O arquivo temporário próprio foi removido após conferir `git status`; nenhum arquivo de produção foi alterado.

Os testes permanentes reforçam a prova: E12-02 A-17 usa uma terceira conexão para demonstrar que as fontes ainda estão livres enquanto o cancelamento espera a situação; A-18 inspeciona alcance e ordem das travas SQL. E12-03 A-19 a A-21 verificam ambas as ordens, com e sem reembolso, incluindo os efeitos financeiros e o invariante. Não foi feito afrouxamento de asserções anteriores.

### TDD e verificações estáticas

Histórico conferido: R03 `da9f6aa → 8d1a899`; R02 `07692a5 → 36c97c3`; R01 `1b45103 → 42084bd`. Os commits Red alteram somente testes/apoios, antes da produção correspondente. Registros distinguem os cenários já verdes dos que falharam. Não reexecutei commits históricos Red nesta rodada. O ensaio por reversão temporária registrado pelo implementador na E12-07 é evidência de regressão/mutação sobre comportamento já implementado, não substitui a sequência Red anterior das três correções.

Verificações independentes (antes da prova temporária):
- `.venv/Scripts/ruff.exe check .`: All checks passed.
- `.venv/Scripts/ruff.exe format --check .`: 370 files already formatted.
- `.venv/Scripts/mypy.exe .`: 448 source files sem erros.
- `DJANGO_SETTINGS_MODULE=config.settings.test`, `.venv/Scripts/python.exe manage.py check`: 0 issues; `manage.py makemigrations --check --dry-run`: No changes detected.

### Suíte completa e veredito final

Suíte independente, sem filtro, sobre `5705e5d`: **2916 passed in 368.77s (0:06:08)**, incluindo os novos critérios e regressões E11/E12. Comando: `.venv/Scripts/python.exe -u "$env:TEMP/revisor_e12_correcao.py" -q -p no:cacheprovider --tb=short`, com `PYTHONPATH` na raiz. Runner define `DJANGO_SETTINGS_MODULE=config.settings.test`, altera somente `settings.DATABASES[*]["TEST"]["NAME"]` para `test_organicos_revisor_e12_5705e5d` e executa `pytest.main(sys.argv[1:])`. Banco PostgreSQL isolado; configurações versionadas intactas. Coleta feita antes da criação das três provas, executadas separadamente.

| Fatia | Critérios desta correção | Resultado |
|---|---|---|
| E12-01 | Alinhamentos A-5/A-19 e regressões | APROVADO |
| E12-02 | A-17/A-18, alcance e ordem das travas | APROVADO, R03 encerrado |
| E12-03 | A-19 a A-21, duas ordens e indicações | APROVADO, R03 encerrado |
| E12-04 | Alinhamento do alerta e regressões | APROVADO |
| E12-05 | A-8 a A-11, pagantes de ciclos anteriores | APROVADO, R02 encerrado |
| E12-06 | A-20 a A-22, estado vigente e histórico | APROVADO, R01 encerrado |
| E12-07 | A-9/A-10 e regressões ponta a ponta | APROVADO |

**Veredito final da E12: APROVADO sobre `5705e5d`.** R01, R02 e R03 encerrados. Nenhum novo achado impeditivo ou melhoria identificado nesta revalidação. Aprovação fundamentada na conformidade dos requisitos, revisão de código, sequência e registros de TDD, provas independentes e regressão completa verde.

Limites: não houve inspeção visual em navegador nem validação com provedor real; telas avaliadas por HTTP e leitura de templates/contexto. Os gates já documentados de E13/E14 permanecem fora desta aprovação.

Entrega: sete `review.md`, conteúdo anterior integralmente preservado por comparação de prefixo; nenhum código de produção alterado, sem push ou PR. Próximo gate: integração pelo responsável pela branch, com atualização bilíngue dos READMEs antes do merge conforme AGENTS.md §10.
