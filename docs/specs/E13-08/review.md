# E13-08 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal_ponta_a_ponta.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-8 | `876f836` | **9 passed** |

## Sobre o Red
A fatia, pelo `spec.md`, não cria comportamento novo: exercita o que as E13-01 a E13-07 e as E09 a E12 entregaram. Não há Red de código de produção; os testes passaram na primeira execução completa (depois de dois ajustes do próprio teste, abaixo). Isso é registrado como Red tardio, e não como Red. Como evidência complementar, três mutações temporárias na produção (revertidas com `git checkout -- <arquivo>`; árvore limpa depois):

| Mutação | Resultado do arquivo |
|---|---|
| `_codigo_da_recusa` deixa de recusar o reenvio com o ciclo `em_andamento` (`reenvio_do_pedido_formal.py`) | 2 failed (A-2, A-3 cenário 118) |
| o repasse deixa de limitar pelo liberado (`liquidez.py`, `SAIDAS["repasse"]`) | 3 failed (A-5, A-6, A-7) |
| o receptor não gera o pedido formal (`receptores.py`) | 9 failed |

## Ajustes do próprio teste (nenhum afrouxa asserção de comportamento)
- Durante o ciclo automático e na rodada cancelada a página não traz o botão (e por isso o token): o POST do teste leva um UUID próprio.
- A-8 é conferido nos estados dos A-1, A-5 e A-6 por `_o_fornecedor_ve_so_o_permitido`, chamado ao fim de cada um (portal, CSV e as recusas da E13-07 A-12 e A-13).
- A-3 usa cookies copiados da sessão do administrador em cada thread (a sessão está no banco) e a pausa de `enviar_email` com `esperar_outra_conexao_na_trava()`.

## Verificação final da etapa (E13-01 a E13-08)

- `uv run pytest` (suíte inteira, sem `-k`): **3068 testes: 3066 passed e 2 failed na execução inteira; após o ajuste da lista de rotas, 3067 passed e 1 failed (M-10, preexistente)**.
- `uv run ruff check --no-cache .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run python manage.py makemigrations --check`: limpos (resultado no relatório de entrega).
- Resultado da suíte inteira: 2 falhas, ambas tratadas. (1) `test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete` listava as rotas com "pedido/frete" no nome: acrescentei à lista de permitidas as quatro rotas novas da E13 (`rodadas_pedido_formal`, `rodadas_pedido_formal_reenviar`, `fornecedor_pedido_formal_csv`, `rodadas_saidas_frete`), nenhuma altera o pedido congelado; o critério do teste (nenhuma rota altera pedido, item, T0 ou frete cobrado) não mudou. **Revisor: confirmar.** (2) `test_devolucoes_reembolso.py::test_o_reembolso_gera_a_obrigacao_financiada_pela_custodia` falha também isolada e sem relação com a E13: não congela o relógio e o prazo do pedido de `T0` terminou em 03/11/2026 (relógio real). Registrado como M-10 em `docs/melhorias.md`, sem alterar o teste.
- Sem push, PR nem merge: aguardam o parecer do agente 3. O PR à `main` atualizará o README (Parte 1) nas duas línguas e a milestone 13.


## Revisão independente consolidada — agente 3 — 2026-11-13

**Veredito: REPROVADO. A E13 não está aprovada.**

Base auditada: `9af6251`, branch `e13-especificacoes`, comparação com `9851bb5` (E12). Lidos os documentos-base (funcional v1.7 e infraestrutura v1.8), as oito especificações, critérios e registros de implementação antes da avaliação do comportamento. O esclarecimento de `15c7169` e a correção `c56385e` → `9af6251` foram considerados. Não foi identificada decisão comercial pendente: os achados abaixo exigem correção técnica derivável dos requisitos existentes.

Os registros anteriores do implementador foram preservados. O revisor não corrigiu produção nem os testes entregues. As provas adicionais foram temporárias; seu código integral fica neste parecer para reprodução.

### Achados e decisão

| ID | Classificação | Fatia | Evidência e requisito |
|---|---|---|---|
| E13-R01 | **Bloqueador** | E13-03, integração E13-04/E13-08 | Mesmo UUID, dois pedidos formais concorrentes: dois e-mails aceitos, uma tentativa persistida e uma recusa posterior ao envio. Viola funcional §10, infraestrutura §4.14/T-29 e E13-03 regras 4/8/11/12. Análise e correção esperada em [E13-03](../E13-03/review.md). |
| E13-R02 | **Importante** | E13-02, integração E13-08 | Consulta antiga que falha sobrescreve o intervalo de 30 minutos já gravado pela segunda falha de e-mail, reduzindo-o a 5 minutos. Viola a transição vigente da E13-02 regra 5 e os intervalos crescentes/concorrência da infraestrutura §4.14. Análise em [E13-02](../E13-02/review.md). |
| M-11 | Melhoria não impeditiva | E13-08 | Tornar permanentes as asserções complementares do A-6/A-7: valores exatos devidos e aprovação no provedor realmente posterior ao cancelamento. O teste entregue usa `em=T0+47h` depois de cancelar em `T0+93h`, cobrindo descoberta atrasada de aprovação anterior. A prova independente com `em=T0+94h` passou. Sem defeito funcional demonstrado; registrada em `docs/melhorias.md`. |

**M-10 preexistente:** mantido o registro de melhoria já feito pelo implementador. O arquivo afetado não mudou desde `9851bb5`. O teste não congela o relógio antes de criar a cobrança; o prazo de T0 já passou. O controle independente executou a mesma função de teste, sem mudar suas asserções, após congelar `T0+1h`, e passou. Isso explica a falha, mas não transforma a execução original da suíte em verde.

### Matriz revista

| Fatia | Critérios | Resultado dos testes entregues | Parecer |
|---|---|---|---|
| E13-01 | A-1 a A-17 | 19 passaram | APROVADO no escopo próprio: snapshot, composição, imutabilidade, rollback e auditoria. |
| E13-02 | A-1 a A-17 | 17 passaram | REPROVADO: caso concorrente adicional E13-R02. |
| E13-03 | A-1 a A-17 | 19 passaram | REPROVADO: caso concorrente adicional E13-R01. |
| E13-04 | A-1 a A-17 | 18 passaram | Escopo próprio aprovado; integração depende de E13-R01. |
| E13-05 | A-1 a A-19 | 25 passaram | APROVADO: ajuste, avisos, permissões, calendário e telas. |
| E13-06 | A-1 a A-22 | 27 passaram | APROVADO: consulta, liquidez por destinação, concorrência, auditoria e passkey. |
| E13-07 | A-1 a A-18 | 18 passaram | APROVADO: isolamento, campos fechados, CSV, recusas e correção do valor “faltam”. |
| E13-08 | A-1 a A-8 | 9 passaram | REPROVADO no conjunto pelos E13-R01/E13-R02; demais integrações verificadas. |

**152 testes da E13 passaram em 91,69 s.** Isso inclui concorrência em conexões reais, rotas HTTP, simulador de pagamentos, reenvio, repasse/consistência financeira e cancelamento depois do repasse. Os cenários A-8 estão exercitados dentro de A-1/A-5/A-6; A-3 tem três testes.

**Provas adicionais:** 2 falharam pelos defeitos E13-R01/E13-R02 e 2 passaram, em 15,04 s. O terceiro teste confirma também as obrigações de X/Y de 94,35/106,15, produtos de 80,00/90,00 sem cobertura depois do repasse, e a devolução integral do pagamento aprovado depois do cancelamento com cobertura, alerta crítico, obrigação do fornecedor zerada, repasses intactos e invariante sem violação. O quarto isola M-10 pelo relógio.

### Comandos e resultados independentes

Usados `.venv/Scripts/python.exe`, Ruff e mypy já instalados. O Docker Desktop estava parado; o revisor iniciou o serviço local `docker compose up -d db` para executar PostgreSQL 17. Não foi usado provedor de pagamentos real nem serviço de e-mail externo.

Para evitar disputa com bancos de outros agentes, o runner temporário abaixo define o nome de TEST nos dois aliases antes de chamar pytest; nenhum settings do repositório foi modificado:

```python
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.test'
from django.conf import settings
for database in settings.DATABASES.values():
    database.setdefault('TEST', {})['NAME'] = 'test_organicos_revisor_e13_9af6251'
import pytest
sys.exit(pytest.main(sys.argv[1:]))
```

`$env:PYTHONPATH=(Get-Location).Path`; runner salvo em `$env:TEMP/revisor_e13.py`. Para a matriz foi usada uma cópia com banco `test_organicos_revisor_e13_provas`; para as provas, outra com `test_organicos_revisor_e13_complemento`. Os três bancos são exclusivos desta revisão.

| Comando | Resultado |
|---|---|
| `.venv/Scripts/python.exe -u "$env:TEMP/revisor_e13.py" -q -p no:cacheprovider --tb=short` | **3067 passed, 1 failed em 706,63 s**; única falha: M-10 (`test_devolucoes_reembolso.py:169`, `PagamentoRecusado`, prazo terminado em 03/11/2026 às 10:00 Brasília). Nenhum teste foi excluído ou alterado. |
| `.venv/Scripts/python.exe -u "$env:TEMP/revisor_e13_provas.py" tests/tecnicos/test_pedido_formal.py tests/tecnicos/test_pedido_formal_envio.py tests/tecnicos/test_pedido_formal_reenvio.py tests/tecnicos/test_pedido_formal_telas.py tests/tecnicos/test_previsao_de_entrega.py tests/tecnicos/test_previsao_de_entrega_telas.py tests/tecnicos/test_repasse.py tests/tecnicos/test_repasse_telas.py tests/tecnicos/test_portal_do_fornecedor.py tests/tecnicos/test_pedido_formal_ponta_a_ponta.py -q -p no:cacheprovider --tb=short` | 152 passed. Arquivos inteiros, sem `-k`. |
| `.venv/Scripts/python.exe -u "$env:TEMP/revisor_e13_complemento.py" tests/tecnicos/test_pedido_formal_revisao_temporaria.py -q -p no:cacheprovider --tb=short` | 2 failed, 2 passed; falhas E13-R01/E13-R02. |
| `.venv/Scripts/ruff.exe check .` | All checks passed. |
| `.venv/Scripts/ruff.exe format --check .` | 390 files already formatted. |
| `.venv/Scripts/mypy.exe .` | Success: no issues found in 470 source files. |
| `DJANGO_SETTINGS_MODULE=config.settings.test; .venv/Scripts/python.exe manage.py check` | System check identified no issues. |
| Mesmo settings; `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` | No changes detected. |

As verificações estáticas foram executadas antes da criação do arquivo temporário de provas, sobre o código entregue. O arquivo temporário não integra o commit do parecer. Logs locais: `$env:TEMP/revisor_e13_suite.log`, `revisor_e13_matriz.log` e `revisor_e13_complemento.log`; resultados relevantes e reprodução estão preservados aqui, sem dependência desses arquivos para entender o parecer.

### TDD e limites

As fatias E13-01 a E13-07 têm commits de testes antes dos commits de produção correspondentes, conferidos por histórico/diff, e registros com comandos e resultados Red/Green. Detalhes nos respectivos pareceres. Confirmadas as alterações autorizadas do arranjo financeiro da E09, da lista de rotas da E08 e do progresso da E05; não foram usadas para encobrir os achados novos.

E13-08 não introduz comportamento de produção; a execução inicial verde dos testes integrados é aceitável como verificação complementar dos comportamentos construídos por TDD nas fatias anteriores. As mutações relatadas pelo implementador não são Red histórico e não foram reexecutadas nesta revisão. A ordem dos commits corrobora a precedência dos testes, mas não permite autenticar independentemente a saída original dos comandos históricos.

L-13 continua válida: sucesso é aceitação pelo backend, não comprovação de entrega/bounce. A limitação de crash entre aceitação e commit permanece documentada; E13-R01 não depende de crash. Não foram auditadas integrações reais de fases posteriores.

Próximo gate: implementador corrige E13-R01/E13-R02 com Red/Green, preserva as garantias existentes e devolve para revisão independente. Reexecutar as matrizes afetadas, as provas concorrentes e as regressões pertinentes. A falha de relógio M-10 deve continuar explicitamente informada enquanto existir; este parecer não declara a suíte global verde.

### Código completo das provas independentes

Para reproduzir, gravar o bloco abaixo em `tests/tecnicos/test_pedido_formal_revisao_temporaria.py` e executar o comando da tabela. Os dois primeiros testes expressam o resultado exigido e falham no commit auditado; os outros dois são controles positivos. Nenhuma alteração de produção é necessária para reproduzir.

```python
import uuid
from threading import Barrier

import pytest

from apps.pedidos import reenvio_do_pedido_formal as reenvio
from apps.pedidos.models import TentativaDeEnvioDoPedidoFormal
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.pedido_formal import af_sucesso

pytestmark = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


def test_token_global_nao_envia_dois_pedidos_concorrentes(
    relogio, simulador_pagamentos, monkeypatch
):
    a, _, _, primeiro = af_sucesso(relogio, simulador_pagamentos)
    b, _, _, segundo = af_sucesso(relogio, simulador_pagamentos)
    token = uuid.uuid4()
    encontro = Barrier(2)
    enviados = []
    original = reenvio.enviar_email

    def enviar(destino, assunto, corpo):
        encontro.wait(timeout=10)
        original(destino, assunto, corpo)
        enviados.append(assunto)

    monkeypatch.setattr(reenvio, "enviar_email", enviar)
    resultados = executar_em_paralelo(
        lambda _: reenvio.reenviar_pedido_formal(a.admin, primeiro, token=token),
        lambda _: reenvio.reenviar_pedido_formal(b.admin, segundo, token=token),
    )
    assert sum(r.excecao is None for r in resultados) == 1
    recusas = [r.excecao for r in resultados if r.excecao is not None]
    assert isinstance(recusas[0], reenvio.ReenvioRecusado)
    assert recusas[0].codigo == "token_invalido"
    assert TentativaDeEnvioDoPedidoFormal.objects.filter(token=token).count() == 1
    assert len(enviados) == 1, f"E-mails aceitos: {enviados}; tentativas persistidas: 1"


def test_consulta_antiga_nao_encurta_intervalo_da_terceira_tentativa(
    relogio, simulador_pagamentos, settings, monkeypatch
):
    from threading import Event, local
    from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
    from apps.pedidos import envio_do_pedido_formal as envio
    from apps.pedidos.models import EnvioDoPedidoFormal
    from tests.apoio.pedido_formal import af_meio, FALHA, PRAZO, M

    _, _, _, pedido = af_meio(relogio, simulador_pagamentos, settings)
    settings.EMAIL_BACKEND = FALHA
    relogio.congelar(PRAZO + 5 * M)
    consulta_iniciada, segunda_concluida = Event(), Event()
    contexto = local()
    original = envio.consultar_antes_de_decidir

    def consultar(referencia):
        if getattr(contexto, "falha_atrasada", False):
            consulta_iniciada.set()
            assert segunda_concluida.wait(10)
            raise ConsultaAoProvedorFalhou(referencia, "indisponivel")
        return original(referencia)

    monkeypatch.setattr(envio, "consultar_antes_de_decidir", consultar)

    def atrasada(_):
        contexto.falha_atrasada = True
        return envio.processar_pedidos_formais()

    def segunda(_):
        assert consulta_iniciada.wait(10)
        try:
            return envio.processar_pedidos_formais()
        finally:
            segunda_concluida.set()

    resultados = executar_em_paralelo(atrasada, segunda)
    assert all(r.excecao is None for r in resultados), resultados
    assert [r.valor for r in resultados] == [0, 1]
    estado = EnvioDoPedidoFormal.objects.get(pedido_formal=pedido)
    assert estado.automaticas == 2
    assert estado.proxima_tentativa_em == PRAZO + 35 * M


def test_pagamento_aprovado_realmente_depois_do_cancelamento(
    client, relogio, simulador_pagamentos, webauthn
):
    from decimal import Decimal
    from apps.financeiro.livro import conta, saldo
    from apps.financeiro.models import (
        AlertaFinanceiro, Destinacao, MovimentoFinanceiro, ObrigacaoComComprador,
    )
    from apps.financeiro.reserva import sem_cobertura_da_obrigacao
    from apps.pedidos.models import DestinoDoPagamento
    from tests.apoio.apuracao import H
    from tests.apoio.pedidos import T0
    from tests.tecnicos.test_pedido_formal_ponta_a_ponta import (
        _cancelar_depois_do_repasse, _processar_tudo, _invariante_ok,
    )

    a, x, y, _, _, extra, repasses = _cancelar_depois_do_repasse(
        client, relogio, simulador_pagamentos, com_segunda_cobranca=True
    )
    obrigacoes = ObrigacaoComComprador.objects.filter(motivo="cancelamento_da_rodada")
    assert {o.pedido_id: o.devido for o in obrigacoes} == {
        x.pk: Decimal("94.35"), y.pk: Decimal("106.15"),
    }
    assert {o.pedido_id: o.produtos for o in obrigacoes} == {
        x.pk: Decimal("80.00"), y.pk: Decimal("90.00"),
    }
    assert all(sem_cobertura_da_obrigacao(o) >= o.produtos for o in obrigacoes)
    relogio.congelar(T0 + 94 * H)
    simulador_pagamentos.aprovar(extra, em=T0 + 94 * H)
    simulador_pagamentos.entregar_avisos()
    _processar_tudo()
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=extra)
    assert destino.destino == "devolucao"
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, origem_id=str(destino.pk))
    assert obrigacao.integral == x.total
    assert sem_cobertura_da_obrigacao(obrigacao) == 0
    assert AlertaFinanceiro.objects.filter(
        tipo="pagamento_depois_do_cancelamento", gravidade="critico"
    ).exists()
    assert saldo(conta(
        Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk
    )) == 0
    assert list(MovimentoFinanceiro.objects.filter(tipo="repasse").order_by("pk").values()) == repasses
    _invariante_ok()


def test_controle_do_relogio_da_regressao_m10(relogio, simulador_pagamentos):
    from tests.apoio.apuracao import H
    from tests.apoio.pedidos import T0
    from tests.tecnicos.test_devolucoes_reembolso import (
        test_o_reembolso_gera_a_obrigacao_financiada_pela_custodia as verificar,
    )

    relogio.congelar(T0 + H)
    verificar(relogio, simulador_pagamentos)
```

## Correções E13-R01 e E13-R02 — implementador — 2026-11-13

Commits: Red `cfc54f2` → Green `36efba3` (R01), A-9 pela rota `f9900d1` (Red tardio, comprovado removendo a trava), Red `5ae9f5e` → Green `0966272` (R02). Detalhes em [E13-03](../E13-03/review.md) e [E13-02](../E13-02/review.md).

Suíte completa (`uv run pytest -q`): **1 failed, 3072 passed** (452 s); a falha é a preexistente M-10 (`test_devolucoes_reembolso.py::test_o_reembolso_gera_a_obrigacao_financiada_pela_custodia`, relógio real). `ruff check --no-cache`, `ruff format --check` e `mypy .` limpos. Sem push, PR ou merge, aguardando a revalidação do agente 3.
