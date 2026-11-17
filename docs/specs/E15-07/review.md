# E15-07 — Registro do implementador

Agente 2.

## Execução

A fatia não tem Red próprio (como na E14-08): `tests/tecnicos/test_painel_ponta_a_ponta.py` verifica o que as E15-01 a E15-06 construíram, com o simulador de pagamentos, as tarefas chamadas como o worker as chama (`tarefa(timestamp=0)`), as telas do administrador pelas rotas HTTP (com `entrar_de_novo` a cada avanço do relógio) e o relógio controlado.

- Primeira execução: **12 passaram e 1 falhou**. A falha é o A-3, e revelou um defeito de produção da E15-05 (abaixo). Os 12 que passaram não têm Red porque o comportamento já existia.
- Commit do teste: o commit "E15-07: testes de ponta a ponta do painel e dos alertas operacionais".
- Depois da correção: `13 passed` no arquivo; com o painel (E15-05), `38 passed`.

## Defeito achado pelo A-3 (E15-05), corrigido

- **Sintoma:** depois de três falhas automáticas do pedido formal e de um reenvio manual aceito, a ação "O pedido formal não foi enviado depois das três tentativas: reenvie." continuava no painel.
- **Causa:** a regra da E15-05 usa só a situação `concluido_com_falhas` do `EnvioDoPedidoFormal`; o reenvio manual (E13-04) grava uma `TentativaDeEnvioDoPedidoFormal` com sucesso, mas não muda a situação do ciclo automático.
- **Correção:** `_acoes_do_pedido_formal` (`apps/operacao/painel.py`) só mostra a ação quando o ciclo está em `concluido_com_falhas` **e** nenhuma tentativa do pedido formal teve sucesso. Os critérios A-9 da E15-05 (três falhas, sem sucesso) e A-3 desta fatia passam. É o único código de produção desta fatia; vai como correção da E15-05, para o revisor conferir se a regra da E15-05 (tabela da regra 3) deve ser lida assim.

## Desvios e pontos para o revisor

1. **Um administrador só** (ADM1), como nas fatias anteriores.
2. **A-8:** o simulador não tem recusa definitiva de cancelamento (o `cancelar_cobranca` do simulador nunca recusa). O alerta de chamada que falhou de vez foi obtido com uma `consultar_pagamento` de um pagamento desconhecido, que vira `falhou` depois de 24 h (E07-04, A-9), e a ciência é dada pelo painel. A operação é uma das duas que a regra 4 da E15-04 inclui.
3. **A-10:** o simulador não devolve valor divergente; as `ConsultaDoPagamento` com divergência `valor` foram criadas direto. O que se verifica é o que a E15-04 define: a segunda consulta igual não abre outro alerta.
4. **A-1 e A-2** estão num teste só e **A-8 e A-9** em outro, porque cada passo usa o estado do anterior. A-2 usa AP-I2 (comprador de fábrica, pago pelo simulador) e não o AP de duas compras; o repasse e o frete aparecem na etapa aguardando fornecedor se liberados.
5. **A-12:** o evento de teste é `pagamento_confirmado`, o e-mail falha até o envio ficar `falhou` (o relógio avança um dia por rodada de `processar_envios`), e a central de notificações do comprador mostra a notificação. Nenhum movimento financeiro muda.
6. **A-13:** o histórico filtrado por ADM1 é comparado, página a página, com as entradas lidas do banco; entre elas estão `recebimento.registrar` e `descarte.registrar`.
7. **A-15:** o teste compara rodada, pedido, pagamento, chamada, movimento e envios antes e depois de `verificar_operacao`; os e-mails dos próprios avisos são os únicos envios novos. O invariante financeiro e "no máximo um alerta aberto por par" são conferidos no fim de cada critério.

## Verificação da etapa inteira

- `uv run pytest -q`: **3397 passed** (3260 da E14 e anteriores mais 137 novos; sem falhas).
- `uv run mypy .`: 527 arquivos sem erro. `uv run ruff check --no-cache .` e `uv run ruff format --check .`: limpos. `makemigrations --check --dry-run`: sem mudanças.
- Testes existentes alterados (só para acompanhar o evento `alerta_operacional` da regra 3 da E15-02, sem remover asserção): `test_notificacoes_eventos.py`, `test_financeiro_alertas.py`; e, na E15-04, um ajuste de contagem em `test_alertas_operacionais.py`, arquivo desta etapa.
- Sem push, PR nem merge: aguarda o parecer do agente 3. No PR à `main`, atualizar o README (Parte 1, nas duas línguas) e a milestone 15.


## Revisão independente — agente 3 — 2026-11-16

Referência auditada: `2f5958c`, branch `e15-especificacoes`, sobre `8b1739f` (E14). Foram lidos os documentos-base (funcional v1.7 e infraestrutura v1.8), as sete especificações e matrizes E15 e os registros Red/Green, antes da comparação com código e testes. Este parecer acrescenta-se ao registro do implementador, preservado integralmente. Evidências globais e código das reproduções estão em [E15-07/review.md](../E15-07/review.md).

**Veredito final da E15: REPROVADO.** Cinco achados importantes abertos: R01/R02 (E15-02), R03 (E15-03/E15-05), R04 (E15-05) e R05 (E15-06). Não foi encontrado bloqueador financeiro ou decisão comercial nova necessária. Os achados são descumprimentos dos requisitos aprovados, não melhorias opcionais; impedem o encerramento pelo AGENTS.md §§4 e 8.

### Rastreabilidade da avaliação

| Fatia | Matriz examinada | Resultado |
|---|---|---|
| E15-01 | A-1 a A-14 | APROVADO |
| E15-02 | A-1 a A-15 | REPROVADO: R01/R02 |
| E15-03 | A-1 a A-16 | REPROVADO: R03 |
| E15-04 | A-1 a A-28 | APROVADO no escopo auditado |
| E15-05 | A-1 a A-25 | REPROVADO: R03/R04 |
| E15-06 | A-1 a A-14 | REPROVADO: R05 |
| E15-07 | A-1 a A-15 | Cenários existentes não bastam para encerrar a etapa; regressões abaixo |

O conjunto ponta a ponta usa 13 testes para 15 critérios (A-1/A-2 e A-8/A-9 combinados). O Red de reenvio manual em `39ceae5` precede a correção `21eb36e`. Nos demais cenários de integração já havia produção: a ausência de Red novo está explicitamente justificada. Os pares Red/Green das seis fatias estão rastreados nos pareceres correspondentes; foram inspecionados os commits e registros, sem reexecutar os checkouts históricos. As alterações nos testes de eventos/alertas financeiros acrescentam o evento operacional e não removem asserções de segurança.

Limites: testes em PostgreSQL local e simulador, tarefas chamadas diretamente como nos testes da etapa; não é validação de agendamento de um worker externo, produção nem provedor real. Monitor externo continua dependência da E16. A suite verde demonstra os casos cobertos, mas não neutraliza os achados reproduzidos.

### Reproduções independentes

Arquivo temporário `tests/tecnicos/test_alertas_de_revisor_e15.py`, removido após execução. Resultado: **6 failed in 8.72s**, seis asserções/casos correspondentes aos cinco achados (R05 tem duas entradas). Código integral reproduzível abaixo; usa os apoios já existentes, sem mudança de produção ou de testes do implementador. Executar esse arquivo por pytest com `config.settings.test`.

```python
from datetime import timedelta
import pytest
from tests.apoio.operacao import INSTANTE, MIN, arranjo_ao, concluir_todas, alertas
pytestmark = pytest.mark.django_db(transaction=True, databases=['default', 'simulador_pagamentos'])

def test_monitor_nao_acusa_a_propria_execucao(relogio):
    from apps.operacao.tarefas import verificar_operacao
    arranjo_ao(relogio)
    concluir_todas(INSTANTE + 16 * MIN, exceto=('verificar_operacao',))
    relogio.congelar(INSTANTE + 16 * MIN)
    verificar_operacao(0)
    assert [a.chave for a in alertas('tarefa_atrasada', abertos=True)] == []

@pytest.mark.parametrize('parametros', [{'autor':'\u00b2'}, {'ate':'9999-12-31'}])
def test_filtro_limite_nao_interrompe_historico(parametros):
    from apps.operacao.historico import contexto_do_historico
    contexto_do_historico(parametros)

def test_acoes_ordenam_por_fornecedor_antes_de_etapa(relogio):
    from tests.tecnicos.test_painel_administrativo import _ap_i
    from tests.fabricas import RodadaFactory
    from apps.fornecedores.models import Fornecedor
    from apps.rodadas.models import Etapa
    from apps.operacao.painel import acoes_necessarias
    relogio.congelar(INSTANTE)
    interesse = _ap_i('100.00')
    Fornecedor.objects.filter(pk=interesse.fornecedor_id).update(nome='Zeta')
    encerrada = RodadaFactory.create(etapa=Etapa.FECHAMENTO_ENCERRADO)
    Fornecedor.objects.filter(pk=encerrada.fornecedor_id).update(nome='Alfa')
    nomes = [a.fornecedor for a in acoes_necessarias(INSTANTE) if a.fornecedor]
    assert nomes == sorted(nomes)

def test_corrida_conta_so_alerta_realmente_aberto(relogio, monkeypatch):
    from apps.operacao import verificacao
    from tests.apoio.corrida import Corrida
    arranjo_ao(relogio)
    concluir_todas(INSTANTE + 6 * MIN, exceto=('processar_envios_pendentes',))
    relogio.congelar(INSTANTE + 6 * MIN)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, verificacao, 'abrir_alerta')
    ra, rb = corrida.rodar(verificacao.verificar_operacao_agora, verificacao.verificar_operacao_agora, a_atomica=False, b_atomica=False)
    assert ra.excecao is None and rb.excecao is None
    assert ra.valor[0] + rb.valor[0] == len(alertas(abertos=True))

def test_painel_mostra_contagem_atual_sem_mudar_alerta(relogio):
    from tests.tecnicos.test_alertas_de_atraso import _chamada, _verificar
    from apps.operacao.painel import contexto_do_painel
    arranjo_ao(relogio)
    _chamada('a1', proxima_em=INSTANTE, criada_em=INSTANTE)
    _verificar(relogio, INSTANTE + 6 * MIN)
    _chamada('a2', proxima_em=INSTANTE, criada_em=INSTANTE)
    _verificar(relogio, INSTANTE + 6 * MIN)
    assert alertas('chamadas_ao_provedor_atrasadas')[0].dados['quantidade'] == 1
    contexto = contexto_do_painel(INSTANTE + 6 * MIN)
    linha = next(a for a in contexto['alertas'] if a['titulo'] == 'Chamadas ao provedor atrasadas')
    assert linha['corpo'].startswith('2 chamada(s)'), contexto
```

### Verificações executadas pelo revisor

Ambiente: `.venv/Scripts/python.exe`, `DJANGO_SETTINGS_MODULE=config.settings.test`. Para evitar interferência com outro agente, o runner temporário configura `settings.DATABASES[alias]["TEST"]["NAME"]` com nomes exclusivos `test_organicos_revisor_e15_2f5958c` (suíte completa) e `test_organicos_revisor_e15_probes` (execuções sequenciais de provas e fatias), antes de `pytest.main`. `PYTHONPATH` aponta para a raiz do repositório. Nenhum banco de aplicação foi utilizado como banco de testes.

- Sete módulos E15 (`test_execucao_das_tarefas.py`, `test_alertas_operacionais.py`, `test_alertas_de_atraso.py`, `test_alertas_de_falha.py`, `test_painel_administrativo.py`, `test_historico_de_acoes.py`, `test_painel_ponta_a_ponta.py`), pytest `-q --tb=short`: **131 passed in 44.38s**.
- Provas adicionais acima, pytest `-q --tb=short`: **6 failed in 8.72s**, pelos defeitos descritos, não por falha de preparação.
- `.venv/Scripts/ruff.exe check .`: passou.
- `.venv/Scripts/ruff.exe format --check .`: 435 arquivos já formatados.
- `.venv/Scripts/mypy.exe .`: 527 arquivos sem erro.
- `.venv/Scripts/python.exe manage.py check --settings=config.settings.test`: nenhum problema.
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=config.settings.test`: nenhuma mudança pendente.

Próximo gate: implementador reproduz e corrige R01 a R05 com Red/Green, conserva os registros anteriores e devolve para revalidação independente. Não alterei código de produção nem a especificação. Não abri PR, fiz push ou alterei README: este é o parecer na branch de trabalho; a atualização bilíngue de estado continua exigida antes do PR/merge, conforme AGENTS.md §10.

### Resultado final da regressão completa

Runner isolado acima, comando equivalente a `pytest -q -p no:cacheprovider --tb=short`, sem as provas temporárias (coleta realizada antes da criação delas): **3399 passed in 765.03s (0:12:45)**, saída 0. Os 3397 informados pelo implementador no registro anterior referem-se à execução anterior às duas guardas de `2f5958c`; o resultado atual auditado é 3399. Os testes completos e os 131 testes específicos passam, enquanto as seis provas adicionais demonstram R01 a R05. Mantido o veredito **REPROVADO**.

Entrega documental: sete `review.md`, somente acréscimos; os conteúdos anteriores foram comparados com `git show HEAD:<arquivo>` e preservados integralmente. `git diff --check` limpo. Nenhuma melhoria opcional nova registrada nesta revisão.

## Correção R01 ponta a ponta (implementador, 2026-11-16)

A-16 (`test_a_retomada_longa_nao_acusa_a_verificacao`): sem Red próprio, pois o comportamento vem do Green da E15-02 (guarda). Aos 20 min, antes da retomada, "Atrasada desde" aparece em 6 linhas (as cinco de 1 minuto e a verificação; as de 10 min e a horária ainda estão em tolerância), e não nas 11 da redação "nas demais": registro como leitura da spec. Depois da retomada, "Em dia" nas 11.

Verificação: suíte completa antes do A-16 novo, **3437 passed**; arquivo do A-16, 14 passed; `ruff`, `mypy` (527 arquivos) e `makemigrations --check` limpos. Sem push, PR nem merge.


## Revalidação independente das correções — agente 3 — 2026-11-16

Código auditado: `f42e08d`, branch `e15-especificacoes`. Delta desde o parecer `2d909d6`: especificação `63285a5`, produção/testes `46e178b`, `812a91a`, `1dfb6e0` e integração/registro `f42e08d`. Os documentos-base e o parecer anterior continuam como referência; os novos requisitos foram lidos antes do delta de código. Registro anterior preservado integralmente. Resultados compartilhados em [E15-07/review.md](../E15-07/review.md).

**Veredito da E15: REPROVADO.** R01–R04 encerrados; R05 permanece aberto somente pelo filtro `acao` com NUL (`%00`), que produz erro de banco e HTTP 500. Detalhes, requisito e provas em [E15-06/review.md](../E15-06/review.md). Nenhum outro achado impeditivo identificado no delta.

| Fatia | Cobertura revalidada | Resultado |
|---|---|---|
| E15-01 | A-1 a A-14 | APROVADO, ratificado |
| E15-02 | A-1 a A-20 | APROVADO; R01/R02 encerrados |
| E15-03 | A-1 a A-16, integração com E15-05 | APROVADO; R03 encerrado |
| E15-04 | A-1 a A-28 | APROVADO, ratificado |
| E15-05 | A-1 a A-30, incluindo A-18-A | APROVADO; R03/R04 encerrados |
| E15-06 | A-1 a A-18 e filtros adversos adicionais | REPROVADO; R05 residual |
| E15-07 | A-1 a A-16 | Testes existentes verdes; etapa não encerrada |

A-16 de integração: a expectativa de seis tarefas atrasadas aos 20 minutos é derivada das tolerâncias da E15-01 (cinco tarefas de um minuto e a própria verificação). As demais não excederam suas tolerâncias; exigir onze atrasadas contrariaria o catálogo. Aceito o registro do implementador como interpretação técnica compatível, sem decisão comercial pendente. Depois da retomada, as onze ficam em dia, sem alerta próprio. É guarda de integração após o Red/Green da E15-02.

### Verificações independentes

Ambiente `.venv/Scripts/python.exe`, `DJANGO_SETTINGS_MODULE=config.settings.test`, PostgreSQL local e simulador. Runner temporário lê as configurações e configura somente o nome TEST de cada alias antes de `pytest.main`; nomes exclusivos `test_organicos_revisor_e15_f42e08d` e sufixos `_provas`, `_red`, `_limites`. Não usado banco de aplicação como banco de teste.

- Sete módulos E15, `tests/tecnicos/test_financeiro_alertas.py` e as seis provas originais (copiadas sem alteração do bloco Python deste parecer), `pytest -q --tb=short`: **197 passed in 55.54s**.
- Duas provas adicionais do filtro `acao`, `pytest .../test_alertas_de_revisor_e15.py -k filtro_acao -q --tb=short`: **2 failed, 6 deselected in 5.08s**. Serviço: DataError; rota autenticada: 500 em vez de 200.
- Reprodução do Red em worktree destacado de `2d909d6`, com os três módulos de teste atuais (`test_alertas_operacionais.py`, `test_painel_administrativo.py`, `test_historico_de_acoes.py`) e sem mudanças no código antigo: **13 failed, 85 passed in 36.55s**. Quatro falhas de R01/R02, quatro de R03/R04 e cinco de R05, todas coerentes com os achados. A-18 operacional passou como guarda; ressalva da contagem registrada em E15-02. O worktree temporário foi limpo e removido após conferir que somente os três testes copiados pelo revisor estavam alterados.
- A reconstrução Red confirma que os testes distinguem o código anterior do corrigido. Não prova por si só a ordem das execuções do implementador: a afirmação Red antes da implementação vem dos registros preservados, pois testes e produção foram commitados juntos.
- `ruff check .`: passou; `ruff format --check .`: 435 arquivos formatados; `mypy .`: 527 arquivos sem erro.
- `manage.py check --settings=config.settings.test`: nenhum problema; `manage.py makemigrations --check --dry-run --settings=config.settings.test`: nenhuma mudança.

Limites mantidos: simulador/fase 1, tarefas invocadas diretamente; não é certificação de produção, worker externo ou provedor real. Nenhuma melhoria opcional nova. Próximo gate: corrigir o residual de R05 com Red/Green e devolver para revalidação. Não corrigi produção, testes permanentes ou especificações; preservados os pareceres anteriores e os registros do implementador.

### Encerramento da revalidação — 2026-11-17

A suíte completa iniciada em 2026-11-16 terminou com **3438 passed in 713.38s (0:11:53)**. Comando: runner isolado descrito acima, `pytest -q -p no:cacheprovider --tb=short`. A coleta ocorreu antes da criação das provas temporárias, portanto esse total representa os testes permanentes da branch. O resultado foi conferido na retomada em 2026-11-17; o HEAD permanece `f42e08d`, sem mudança de código durante esta revisão.

Resultado consolidado: 3438 testes permanentes verdes; 197 aprovações na execução dirigida (E15, alertas financeiros e seis provas originais); duas provas adicionais falhando no residual de R05, no serviço e na rota HTTP. **E15 REPROVADA**, com R01–R04 encerrados e somente o residual de R05 pendente. Testes verdes não substituem o atendimento à regra de ignorar filtros inválidos com resposta 200.

Entrega: somente acréscimos nos sete `review.md`; preservação integral dos textos de HEAD conferida por comparação com `git show`. Provas temporárias e worktree de reconstrução do Red removidos; nenhuma alteração em produção, especificações ou testes permanentes. `git diff --check` limpo. Pareceres commitados na branch de trabalho, sem push. Próximo gate: correção do filtro `acao` e revalidação independente.


## Revalidação do residual de R05 — agente 3 — 2026-11-17

Referência auditada: `7181c67`, branch `e15-especificacoes`, delta desde `2536eb4`; especificação do residual em `2e7718b`. Papel mantido: revisor independente. Registros anteriores preservados integralmente.

**Veredito: BLOQUEADO POR DECISÃO.** R01–R05 estão encerrados funcionalmente; não foi identificado defeito funcional remanescente no escopo revisado. R06 (importante, processo) aguarda decisão do responsável sobre a exceção pontual à sequência TDD, conforme [E15-06/review.md](../E15-06/review.md). Não é necessária decisão de regra de negócio nem mudança de produção para o defeito anterior.

### Escopo e resultados

- Lidos os novos spec/acceptance e o registro do implementador antes de avaliar o delta. A mudança está restrita à validação do filtro `acao` em `apps/operacao/historico.py`, com testes A-19/A-20. As demais correções e aprovações funcionais anteriores permanecem válidas.
- Extraídos sem mudança dos pareceres os seis casos originais e os dois casos do residual, em arquivo temporário `tests/tecnicos/test_alertas_de_revisor_e15.py`.
- Runner isolado com `.venv/Scripts/python.exe`, `DJANGO_SETTINGS_MODULE=config.settings.test`, `PYTHONPATH` na raiz e `TEST.NAME = test_organicos_revisor_e15_7181c67` nos aliases. Comando pytest `-q --tb=short`, sete módulos E15 (`test_execucao_das_tarefas`, `test_alertas_operacionais`, `test_alertas_de_atraso`, `test_alertas_de_falha`, `test_painel_administrativo`, `test_historico_de_acoes`, `test_painel_ponta_a_ponta`), `test_financeiro_alertas` e provas temporárias: **210 passed in 38.42s**, saída 0.
- `.venv/Scripts/ruff.exe check .`: passou; `ruff format --check .`: 435 arquivos formatados; `mypy .`: 527 arquivos sem erro.
- `manage.py check --settings=config.settings.test`: nenhum problema; `manage.py makemigrations --check --dry-run --settings=config.settings.test`: nenhuma mudança.
- Não reexecutei nesta rodada a suíte global. A regressão independente foi dimensionada ao delta de uma função de leitura e abrangeu toda a E15, seus alertas financeiros e as reproduções. O implementador registra **3449 passed** para a suíte global; esse número é evidência dele, não execução independente desta rodada. A suíte global independente anterior está registrada acima (3438 em `f42e08d`).
- O registro Red do implementador informa três falhas por NUL e guardas já verdes. A declaração explícita de Green escrito antes de observar Red origina R06; os resultados verdes não eliminam essa pendência de processo.

As fatias E15-01 a E15-05 continuam aprovadas funcionalmente; E15-06 atende os requisitos funcionais e aguarda somente a decisão de processo, refletida no encerramento da E15-07. Não foram acrescentadas melhorias opcionais. Mantidos os limites de fase 1/simulador e de tarefas chamadas diretamente, sem validação de produção ou monitor externo.

Entrega: acréscimos em E15-06/review.md e E15-07/review.md, preservando integralmente os registros anteriores. Provas temporárias removidas após conferência de autoria; nenhuma mudança de produção, especificações ou testes permanentes. Parecer commitado, sem push. Próximo gate: decisão explícita do responsável sobre a exceção TDD pontual; se autorizada, registrar a decisão e encerrar a revisão sem inventar uma nova sequência histórica.


## Decisão do responsável e encerramento — 2026-11-17

O responsável pelo projeto autorizou explicitamente nesta sessão: “autorizo uma exceção pontual à ordem do TDD só para o commit 7181c67”.

A exceção cobre exclusivamente a ordem do TDD na correção de `7181c67`. Não altera o AGENTS.md, não dispensa testes ou revisão e não se estende a outros commits ou entregas. Preservados a declaração do implementador e o achado histórico; a autorização não reescreve a sequência efetivamente realizada.

**R06 encerrado pela decisão explícita do responsável. R01–R05 permanecem encerrados pelas validações funcionais.**

**Veredito final da E15: APROVADO**, para o código de `7181c67`, com a exceção pontual de processo autorizada acima. As sete fatias estão aprovadas; nenhum achado impeditivo permanece aberto nesta revisão.

Base da decisão: 210 testes independentes aprovados (toda a E15, alertas financeiros e oito provas do revisor), ruff, formatação, mypy, check do Django e verificação de migrações limpos. Os resultados da suíte global e sua autoria permanecem discriminados no registro anterior. Não houve mudança de código desde a revalidação; esta atualização é apenas documental e não exigiu repetir os testes.

Próximo gate: preparação do PR à main, com atualização bilíngue do estado nos README pelo responsável por abrir o PR, conforme AGENTS.md §10. Esta aprovação não autoriza produção, dinheiro real ou fases posteriores. Registros preservados, documentos commitados na branch de trabalho, sem push.
