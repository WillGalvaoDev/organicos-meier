# E14-08 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_retirada_ponta_a_ponta.py` (arquivo inteiro, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | **Não se aplica**, como na E13-08: a fatia não cria código de produção; os testes integrados verificam o que as fatias E14-01 a E14-07 construíram por TDD. Os 11 testes passaram na primeira execução |
| Mutações (prova de que os testes detectam defeito, sem substituir o Red) | (1) tirar a conferência do saldo da ocorrência (`if quantidade_afetada > saldo` → `if False`): **1 failed** (A-9, a corrida T-18 pela rota); (2) a liberação deixar de liberar as parcelas `em_pedido`: **2 failed** (A-5 e A-6, o estoque da nova rodada); (3) tirar a recusa do descarte antes do prazo: **11 passed**, isto é, **este ponto não é detectado aqui**; ele é coberto por `test_retirada.py` (A-5) e pelas telas (A-19). Todas as mutações foram revertidas e a árvore conferida com `git status` |
| Final | **11 passed**; `ruff` e `mypy` limpos |

## O que foi feito
- `tests/tecnicos/test_retirada_ponta_a_ponta.py`: o AE com a aprovação pela tela da E11-07 e o endereço pela tela da E14-03, as ações do administrador pelas rotas da E14-06, da E13-06 e da E10 (`entrar_de_novo` a cada avanço do relógio), `processar_chamadas()` e o invariante financeiro (`verificar_invariante_agora`) ao fim de cada critério.
- A-1 a A-3 (entrega parcial, ocorrência, liberação recusada e aceita, aviso, devolução concluída no simulador, repasse de 150,00 e recusa de 0,01); A-4 (ocorrência depois do repasse e da liberação, parte de produtos sem cobertura, cobertura pela reserva, devolução de 11,79); A-5 e A-6 (nova rodada imediata, retirada antiga, prazo e descarte); A-7 e A-8 (rodada liberada não cancela; cancelamento com ocorrência anterior, 70,76); A-9 (T-18 pela rota, com transações reais); A-10 (suspenso retira); A-11 (comprador sem acesso e portal do fornecedor, nos estados dos A-4, A-6 e A-7); A-12 (`_invariantes` ao fim de cada teste: congelado igual, `reembolsado + retirado + descartado ≤ quantidade`, invariante financeiro).

## Limitações
- A cobertura pela reserva (A-4) usa os serviços `registrar_aporte` e `designar_reserva` (E09-06), como a E13-08, e não a tela; a autorização da devolução e o repasse passam pelas telas.

## Verificação da etapa inteira

- `uv run pytest -q` (suíte completa): **3260 passed**, 0 failed (513 s). A falha preexistente M-10 foi corrigida na E13 (PR #86).
- `uv run ruff check --no-cache .` e `ruff format --check .`: limpos; `uv run mypy .`: sem erros (497 arquivos; dois ajustes de tipo nos testes da E14-03 depois da primeira passada); `makemigrations --check`: sem mudanças.
- Migrações novas da E14: `0016` (recebimento), `0017` (ocorrência), `0018` (endereço), `0019` (liberação), `0020` (retirada e descarte), todas com `instalar_protecao_so_insercao`.
- Sem push, PR ou merge: aguarda o parecer do agente 3. O PR à `main` atualizará o README (Parte 1, nas duas línguas) e a milestone 14.


---

## Revisão independente — agente 3 — 2026-11-16

**Objeto:** `5b00c56`, branch `e14-especificacoes`, comparação com `bc35037` (main após E13). Fontes: especificação funcional v1.7, infraestrutura v1.8, AGENTS.md e as oito especificações e matrizes da E14. Histórico do implementador acima preservado.

Este parecer consolida a execução independente e o código das contraprovas. A revisão não alterou código de produção nem os testes do implementador.

**Veredito da E14: REPROVADO.** Há três achados importantes de conformidade, E14-R01 a E14-R03, que precisam de correção e revalidação. Não foi constatado bloqueador de integridade financeira, duplicação de registro ou acesso indevido nos cenários executados.

| Fatia | Critérios revisados | Parecer |
|---|---|---|
| E14-01 | A-1 a A-17 | APROVADO |
| E14-02 | A-1 a A-24 | APROVADO |
| E14-03 | A-1 a A-13 | APROVADO |
| E14-04 | A-1 a A-22 | APROVADO |
| E14-05 | A-1 a A-20 + replay simultâneo | REPROVADO: R01 |
| E14-06 | A-1 a A-25 + convenção 3 | REPROVADO: R01/R03 |
| E14-07 | A-1 a A-14 + regra 5 | REPROVADO: R02 |
| E14-08 | A-1 a A-12 e integração | Testes existentes verdes; encerramento da etapa REPROVADO pelas dependências |

### Achados consolidados

| ID | Classificação | Evidência | Referência |
|---|---|---|---|
| E14-R01 | Importante | Mesmo UUID em duas conexões: um registro, mas ambas retornam `novo=True`, tanto retirada quanto descarte. | E14-05 regra 2/A-15; E14-06 convenção 3. Detalhe em [E14-05](../E14-05/review.md). |
| E14-R02 | Importante | Após ocorrência e cancelamento, a página do comprador ainda mostra a seção de ocorrências. | E14-07 regra 5. Detalhe em [E14-07](../E14-07/review.md). |
| E14-R03 | Importante | POST recusado com quantidade 7 retorna formulário vazio na retirada e quantidade 6 no descarte. | E14-06 convenção 3. Detalhe em [E14-06](../E14-06/review.md). |

### Verificação independente

- Suíte completa independente do commit `5b00c56`: **3260 passed, 0 failed, em 599,91 s**. Inclui as matrizes E14-01 a E14-08, os cenários de aceitação e as regressões anteriores. As cinco contraprovas abaixo foram executadas separadamente e não fazem parte desses 3260 testes.

- `.venv/Scripts/ruff.exe check .`: **All checks passed**.
- `.venv/Scripts/ruff.exe format --check .`: **412 files already formatted**.
- `.venv/Scripts/mypy.exe .`: **Success, 497 source files**.
- `.venv/Scripts/python.exe manage.py check --settings=config.settings.test`: nenhum problema.
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=config.settings.test`: nenhuma alteração pendente.
- Cinco contraprovas adicionais: **5 failed em 10,50 s**, precisamente nas asserções dos três achados, depois de confirmar os pré-requisitos de espera/registro único, HTTP 200 ou 409 e autenticação. A primeira tentativa do ensaio HTTP de administrador foi redirecionada ao cadastro de passkey; o ensaio foi corrigido para usar o fluxo de autenticação já existente, e só o resultado posterior foi usado como evidência.

A suíte completa usou o PostgreSQL configurado no projeto, com um nome de banco de teste isolado (`test_organicos_revisor_e14_5b00c56`); as contraprovas usaram `test_organicos_revisor_e14_probe`. O runner define `DJANGO_SETTINGS_MODULE=config.settings.test`, substitui somente `DATABASES[*].TEST.NAME` e chama `pytest.main(sys.argv[1:])`. Comandos: `.venv/Scripts/python.exe -u $env:TEMP/revisor_e14.py -q -p no:cacheprovider --tb=short`; contraprovas: o mesmo runner, com nome de banco separado, e `tests/tecnicos/test_retirada_revisor_e14.py -q -p no:cacheprovider --tb=short`.

### Integração e TDD

Confrontados os fluxos A-1 a A-12: recebimento parcial/liberação, devolução E10 com passkey e simulador, repasse limitado, falta de cobertura depois do repasse, reserva, nova rodada independente, retirada antiga, prazo inclusivo e descarte manual, cancelamento vedado após liberação, cancelamento antes dela com abatimento de obrigação anterior, concorrência T-18 e isolamento de perfis. As asserções de imutabilidade e invariante financeiro estão presentes no fim dos testes integrados. A-11 usa também as verificações de listas fechadas da E14-07/portal.

A cobertura da reserva em A-4 é por serviço, enquanto autorização da devolução e repasse passam pelas telas; isso está declarado pelo implementador. A E14-08 não introduz produção: ausência de Red próprio aceita como teste de integração de comportamentos com Red nas fatias anteriores. Mutações relatadas pelo implementador não foram reaplicadas pelo revisor e não são apresentadas como execução independente.

Conferidos os registros Red/Green e a ordem/conteúdo dos commits: `1aab88b -> 65e1143`, `6182e5e -> e91142e`, `8bac5e3 -> d1b1a49`, `4b9b482 -> de622e1`, `fc08145 -> cb56f78`, `3ee2653 -> f53999e`, `7836b63 -> d01cb27`. Commits Red contêm testes/apoios antes dos módulos de produção correspondentes. O histórico e os comandos registrados sustentam a sequência; os estados históricos não foram reexecutados nesta revisão. Não basta a suíte atual estar verde: os requisitos adicionais reproduzidos acima falham.

### Contraprovas reproduzíveis

Para reproduzir, salvar o bloco abaixo temporariamente em `tests/tecnicos/test_retirada_revisor_e14.py` e executar com os settings de teste (banco exclusivo se houver outra suíte rodando). O arquivo temporário do revisor foi removido da árvore após a execução; o código permanece aqui para o implementador escrever seus testes de correção. Os patches de pausa apenas coordenam a concorrência, sem retirar validações nem travas.

```python
import uuid
from datetime import timedelta
from decimal import Decimal as D
import pytest
from django.test import Client
from apps.pedidos import retirada as modulo
from apps.pedidos.models import RetiradaDeItem, DescarteDeItem
from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
from tests.apoio.entrega import ae_liberada, arranjo_ae, item_de, retirar, descartar, ocorrer
from tests.apoio.corrida import Corrida

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])

@pytest.mark.parametrize("descarte", [False, True])
def test_replay_concorrente(relogio, simulador_pagamentos, monkeypatch, descarte):
    a, x, _, _ = ae_liberada(relogio, simulador_pagamentos)
    from apps.pedidos.models import LiberacaoDaRetirada
    relogio.congelar(LiberacaoDaRetirada.objects.get(rodada=a.rodada).prazo_final + timedelta(days=1))
    item = item_de(x, a.p1)
    chave = uuid.uuid4()
    funcao = descartar if descarte else retirar
    modelo = DescarteDeItem if descarte else RetiradaDeItem
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(lambda: funcao(a.admin, item, D("4"), chave), lambda: funcao(a.admin, item, D("4"), chave), a_atomica=False, b_atomica=False)
    assert ra.excecao is None and rb.excecao is None
    assert corrida.b_esperou
    assert modelo.objects.count() == 1
    assert ra.valor.registro.pk == rb.valor.registro.pk
    assert (ra.valor.novo, rb.valor.novo) == (True, False)

def test_cancelada_sem_secao_de_ocorrencias(relogio, simulador_pagamentos):
    a, x, _, _ = arranjo_ae(relogio, simulador_pagamentos)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    cliente = Client()
    cliente.force_login(a.a)
    resposta = cliente.get(f"/pedidos/{x.pk}/")
    assert resposta.status_code == 200
    assert "Ocorrências de entrega" not in resposta.content.decode()

@pytest.mark.parametrize("descarte", [False, True])
def test_recusa_preserva_quantidade(relogio, simulador_pagamentos, descarte, webauthn):
    from html.parser import HTMLParser
    from apps.pedidos.models import LiberacaoDaRetirada
    from tests.tecnicos.test_recebimento_e_retirada_telas import _ae
    from tests.apoio.devolucoes import entrar_de_novo
    cliente = Client()
    a, x, _, credencial = _ae(cliente, relogio, simulador_pagamentos, estado="liberada")
    relogio.congelar(LiberacaoDaRetirada.objects.get(rodada=a.rodada).prazo_final)
    item = item_de(x, a.p1)
    entrar_de_novo(cliente, credencial, a.admin)
    acao = "descartes" if descarte else "retiradas"
    rota = f"/administracao/rodadas/{a.rodada.pk}/{acao}/registrar/"
    resposta = cliente.post(rota, {"item": item.pk, "quantidade": "7", "acionamento": str(uuid.uuid4())})
    assert resposta.status_code == 409
    class Forms(HTMLParser):
        def __init__(self):
            super().__init__()
            self.forms = []
            self.current = None
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "form":
                self.current = {"action": attrs.get("action")}
            elif tag == "input" and self.current is not None:
                self.current[attrs.get("name")] = attrs.get("value", "")
        def handle_endtag(self, tag):
            if tag == "form" and self.current is not None:
                self.forms.append(self.current)
                self.current = None
    parser = Forms()
    parser.feed(resposta.content.decode())
    form = next(f for f in parser.forms if f.get("action") == rota and f.get("item") == str(item.pk))
    assert form["quantidade"] == "7"
```

### Entrega e próximo gate

Alterados apenas os oito `review.md` da E14, preservando os registros anteriores. Sem correção de produção, push, PR ou merge. O próximo gate é o implementador acrescentar testes Red para R01/R02/R03, corrigi-los, apresentar Green e devolver para revalidação independente; a E14 não está liberada para encerramento. Atualização bilíngue dos READMEs continua sendo obrigação de quem abrir o PR para main (AGENTS.md §10).


---

## Correção do implementador — verificação da etapa inteira (2026-11-16)

R01, R02 e R03 corrigidos em TDD (Red `e69bedc`, depois o Green; detalhes em E14-05, E14-06 e E14-07/review.md).

- `uv run pytest -q`: 3268 passed (3260 anteriores + 8 novos: A-21, A-22, A-26, A-27, A-28, A-29, A-15, A-16, com A-21/A-22 parametrizados em 2).
- `uv run mypy .`: 497 arquivos sem erro. `uv run ruff check --no-cache .` e `ruff format --check .`: limpos. `makemigrations --check`: sem mudanças.
- Nenhum teste existente foi alterado ou afrouxado. Aguarda nova revisão do agente 3.
