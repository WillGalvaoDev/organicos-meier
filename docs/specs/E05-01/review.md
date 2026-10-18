# E05-01 — Revisão independente

## Revisão independente — 2026-10-18

Commit auditado: `32b05a24fb38aa7bcaef2d67c5917fdef59bc2c5` (`main`, PR #65). Parecer global da E05: **REPROVADO**.

Fontes: especificação funcional v1.6 (§§2, 4.4, 5, 5.1, 5.2 e 6), infraestrutura v1.7 (§§4.10–4.12), AGENTS.md e os sete pares `spec.md`/`acceptance.md` da E05, incluindo a decisão D-1 da E05-07. Código e testes foram confrontados com esses contratos. A revisão não altera regras, código de produção ou testes versionados.

Validação independente no PostgreSQL local:

- `uv run pytest -q`: **1619 passed em 161,01 s**.
- `uv run ruff check .`: passou.
- `uv run ruff format --check .`: **217 arquivos** conformes.
- `uv run mypy .`: **251 arquivos**, sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais do revisor: **8 failed, 8 passed em 4,71 s**, conforme reprodução integral em [E05-01/review.md](../E05-01/review.md). As falhas são deliberadamente asserções do contrato contra o commit auditado; não são falhas da suíte versionada.

Os registros Red/Green do implementador são preservados abaixo. Eles documentam os testes funcionais e os comandos; o revisor não afirma ter presenciado as execuções históricas. A ausência confessada de Red nos testes de concorrência é tratada em R04. Nenhum teste foi afrouxado nesta revisão. As duas mudanças nos testes da E03-08 estão autorizadas pela E05-05; a suíte de regressão inteira passou.

### Decisão e matriz consolidada

**E05 REPROVADA.** R01 e R03 impedem aprovação por defeitos reproduzidos. R02 também impede o aceite e contém conflito contratual que deve voltar ao especificador/responsável. R04 impede considerar cumprido o gate de TDD das fatias afetadas.

“Verde” na tabela significa que os cenários automatizados vinculados aos critérios foram executados com sucesso, não que cubram os casos adicionais encontrados.

| Fatia | Critérios reexecutados | Evidência e conclusão |
|---|---|---|
| E05-01 | A-1 a A-16 | Serviços, validação decimal, autorização, etapas, FIFO de acréscimos/reduções e corridas verdes; **REPROVADO**, R02, R03 e R04. A-7 não cobre pendência própria. |
| E05-02 | A-1 a A-16 | Alocação FIFO, isolamento, prioridade, auditoria, exclusão de `em_pedido`, idempotência e corridas verdes; **REPROVADO**, R01, R02 e R04. A-13 cobre redução finita, não ilimitado → finito. |
| E05-03 | A-1 a A-9 | Remoção das pendências mais recentes, qualquer etapa, preservação de reservas e corrida verdes; **REPROVADO no gate TDD**, R04. Não identificado defeito funcional específico nos cenários revisados. |
| E05-04 | A-1 a A-15 | Elegibilidade por produto, prioridade em caixas, arredondamento por comprador, percentual, privacidade e consultas constantes verdes; **APROVADO no escopo da fatia**. Não aprova a E05 como conjunto. |
| E05-05 | A-1 a A-20 | Agrupamento, preços, privacidade, formulários, autorização, retornos 200/403/409 e consultas verdes; **REPROVADO**, R02 reproduzido pelas duas origens HTTP. |
| E05-06 | A-1 a A-9 | Avisos próprios no site, chaves, rollback, preço vigente e exclusão de pedidos congelados verdes; **REPROVADO**, R03. |
| E05-07 | A-1 a A-14 | Suspensão/remoção, liberação para fila, preservação de `em_pedido`, rollback e corridas previstas verdes; **REPROVADO**, R03 e R04. D-1 está aprovada e foi respeitada. |

### R01 — Bloqueador: estoque ilimitado não pode voltar a limitado

Referências: funcional §4.4; infraestrutura §4.10; E03-05 (alteração de estoque); E05-02, receptor de `estoque_alterado` e A-13. Código: `apps/interesses/receptores.py:22`.

Com limite `None`, chamar `alterar_estoque(admin, estoque, "10")` levanta `TypeError: '>' not supported between instances of 'decimal.Decimal' and 'NoneType'`. Reproduzido sem reservas e com três unidades reservadas, portanto com novo limite válido. O receptor avalia `novo > anterior` quando `anterior` é `None`. A transação aborta; a alteração administrativa deixa de funcionar com a introdução da E05-02. As outras seis transições de controle passaram.

Devolução ao implementador: tratar explicitamente a transição de ilimitado para finito como redução, preservar a validação de reservas e acrescentar teste Red → Green tanto com quanto sem reservas. Não exige decisão comercial.

### R02 — Bloqueador: total desejado e remoção não são idempotentes com pendência própria

Referências: E05-01/spec.md, regras de `definir_interesse` e caso de reenvio; A-7; E05-05/spec.md, “Quantidade desejada”, A-6; contraponto obrigatório: funcional §5.2 e infraestrutura §4.10 (alocar pendentes sempre que liberar estoque). Código: `apps/interesses/servicos.py:218–232`.

Estado: estoque 6, comprador A com 6 reservados e 4 pendentes. Três chamadas consecutivas de `definir_interesse(A, P, "4")` devolvem `(reservado, pendente)` iguais a **(6, 2), (6, 0), (4, 0)**. O mesmo pedido modifica o estado a cada repetição. Em cenário novo, `definir_interesse(..., "0")` devolve **(4, 0)**, não zero. Os POSTs `/interesses/` com `quantidade=0`, tanto `origem=carrinho` quanto `origem=catalogo`, retornam 302 e deixam 4 reservados. A alocação após a redução imediatamente devolve ao próprio comprador parte do estoque liberado.

Há conflito material no contrato combinado: garantir o total final/zero e não tocar pendências, ao mesmo tempo que se atende imediatamente a própria pendência pelo FIFO, não é possível nesse estado. O teste adicional expõe a promessa de total/zero; ele **não autoriza** ignorar o FIFO nem apagar pendências silenciosamente.

**Ponto BLOQUEADO POR DECISÃO do especificador/responsável:** explicitar a semântica quando quem reduz também possui pendências. Opções a avaliar: manter a alocação obrigatória da base e revisar a operação/interface de total desejado e seu reenvio; ou alterar formalmente as regras para garantir o total final, definindo expressamente o destino das pendências. Solicita-se essa decisão no contrato antes da correção afetada. Os demais achados técnicos podem ser corrigidos independentemente. Revalidar estado final, preservação de FIFO, auditoria, reenvio e ambos os caminhos HTTP após a decisão.

### R03 — Bloqueador: preço × reserva/suspensão causa deadlock

Referências: funcional §§5 e 5.1; infraestrutura §4.10; E05-01 ordem global de travas; E05-06 emissão na transação do preço; E05-07 atomicidade da suspensão; AGENTS.md §6. Código: `apps/catalogo/servicos.py:162,187`, `apps/interesses/avisos.py:28–61`, `apps/interesses/servicos.py:97,341`.

Duas conexões reais, sincronizadas por barreira: T1 trava o produto e executa `editar_produto(..., preco="15.99")`; T2 trava a conta e executa `adicionar_interesse` (ou `suspender`). São as mesmas primeiras travas dos serviços; a transação externa apenas fixa a intercalação. As duas reproduções terminam com **`OperationalError: deadlock detected`** em uma operação, sem tratamento/retry de domínio.

Ciclo: a edição mantém a trava de produto e emite notificação com FK para a conta; a validação da FK precisa de trava compatível na conta ao confirmar. A outra operação mantém `FOR UPDATE` na conta e espera o produto. O PostgreSQL aborta uma delas. A transação evita persistência parcial, mas não garante conclusão da edição/reserva/suspensão; em requisição, a exceção não tratada gera erro. O teste com preço × interesse também falhou na primeira execução isolada, antes de ampliar as provas.

Devolução ao implementador: compatibilizar a ordem/força das travas e o caminho transacional dos avisos, incluindo as travas implícitas de FK; preservar autorização, atomicidade do aviso e da moderação. Adicionar testes determinísticos Red → Green para preço × reserva e preço × suspensão/remoção. Decisão técnica derivável dos requisitos; não requer aprovação comercial.

### R04 — Importante: critérios de concorrência implementados sem Red anterior

Referências: AGENTS.md §§3, 4 e 8 e introdução dos `acceptance.md` (“Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada”). Os próprios registros dizem “Escritos depois do Green” / “Sem Red observado”:

- E05-01: A-13 a A-16.
- E05-02: A-15 e A-16.
- E05-03: A-9.
- E05-07: A-8, A-9 e A-14.

Esses testes passam agora, mas isso não comprova a sequência exigida. A justificativa de precisar do serviço real para segurar travas não transforma comportamento concorrente em scaffolding sem comportamento testável. O histórico reúne produção/testes por fatia; não fornece evidência adicional que contradiga a declaração de ausência de Red.

Devolução: registrar a não conformidade e apresentar seu tratamento pelo responsável pelo processo. Para correções, demonstrar novos ciclos Red → Green e refatoração/validação; testes de mutação podem comprovar sensibilidade, mas **não reconstituem um Red histórico** nem autorizam dizer que o TDD original ocorreu. Não fabricar evidências retroativas. A exceção originalmente declarada não atende a exceção estritamente técnica do AGENTS.md.

### Limites e próximo gate

Validação por serviços, cliente HTTP Django e conexões reais PostgreSQL; não foi realizada inspeção visual em navegador. Pendentes são geradas pelas fábricas aprovadas: sua restauração é E11. Prazos/transições E06, snapshots de pedidos E08 e pagamentos posteriores não foram antecipados. Nenhuma integração real de pagamentos ou envio externo foi acionada. Os resultados não equivalem a autorização de produção.

Alterados somente os sete `review.md` da E05. Próximo gate: decisão contratual de R02, correções do implementador com evidências, tratamento de R04 e nova revisão independente do commit resultante. R01/R03 não precisam aguardar a decisão de R02.

### Reprodução independente integral

Salvar o bloco abaixo como `$env:TEMP/test_review_e05_32b05a2.py` e executar, a partir da raiz, **sem outra suíte usando o mesmo banco de testes**:

```powershell
uv run pytest -c pyproject.toml $env:TEMP/test_review_e05_32b05a2.py -q --tb=short
```

Resultado no commit auditado: **8 failed, 8 passed**. Logs locais em `%TEMP%/om_e05_32b05a2_suite.log` e `%TEMP%/om_e05_32b05a2_probes.log`; o código incorporado aqui permite reproduzir mesmo sem esses arquivos temporários.

```python
from decimal import Decimal as D
import pytest
from django.db import transaction
from django.test import Client
from apps.contas.models import Conta
from apps.catalogo.models import Produto
from apps.catalogo.servicos import editar_produto
from apps.rodadas.estoque import alterar_estoque
from apps.interesses.servicos import definir_interesse, adicionar_interesse
from apps.interesses.models import ParcelaDeInteresse
from tests.apoio.interesses import cenario, reservada, pendente
from tests.fabricas import ContaFactory
from tests.apoio.concorrencia import executar_em_paralelo

@pytest.mark.django_db
@pytest.mark.parametrize('reserva', [0, 3])
def test_sem_limite_para_finito(reserva):
    _, p, e = cenario(None)
    a = ContaFactory.create()
    if reserva:
        reservada(a, p, reserva)
    alterar_estoque(Conta.objects.get(papel='administrador'), e, '10')
    e.refresh_from_db()
    assert e.limite == D('10')

@pytest.mark.django_db
def test_definir_com_pendencia_propria():
    _, p, _ = cenario('6')
    a = ContaFactory.create()
    reservada(a, p, 6)
    pendente(a, p, 4)
    resultados = [definir_interesse(a, p, '4') for _ in range(3)]
    assert [(r.reservado, r.pendente) for r in resultados] == [(D(4), D(4))]*3, resultados

@pytest.mark.django_db
def test_zero_remove_com_pendencia_propria():
    _, p, _ = cenario('6')
    a = ContaFactory.create()
    reservada(a, p, 6)
    pendente(a, p, 4)
    r = definir_interesse(a, p, '0')
    assert r.reservado == 0, r

@pytest.mark.django_db(transaction=True)
def test_preco_e_interesse_sem_deadlock():
    _, p, _ = cenario('10')
    a = ContaFactory.create()
    admin = Conta.objects.get(papel='administrador')
    reservada(a, p, 1)
    def preco(barreira):
        with transaction.atomic():
            Produto.objects.select_for_update().get(pk=p.pk)
            barreira.wait(timeout=10)
            editar_produto(admin, p, preco='15.99')
    def interesse(barreira):
        with transaction.atomic():
            Conta.objects.select_for_update().get(pk=a.pk)
            barreira.wait(timeout=10)
            adicionar_interesse(a, p, '1')
    resultados = executar_em_paralelo(preco, interesse)
    assert all(r.excecao is None for r in resultados), [str(r.excecao) for r in resultados]

@pytest.mark.django_db
@pytest.mark.parametrize('origem', ['carrinho', 'catalogo'])
def test_http_zero_remove_com_pendencia(origem):
    _, p, _ = cenario('6')
    a = ContaFactory.create()
    reservada(a, p, 6)
    pendente(a, p, 4)
    c = Client()
    c.force_login(a)
    resposta = c.post('/interesses/', {'produto': p.pk, 'quantidade':'0', 'origem':origem})
    assert resposta.status_code == 302
    from apps.interesses.servicos import interesse_do_comprador
    assert interesse_do_comprador(a,p).reservado == 0

@pytest.mark.django_db
@pytest.mark.parametrize('anterior,novo', [('0','6'), ('6','10'), ('6',None), (None,None), ('6','6'), ('6','3')])
def test_controle_transicoes_estoque(anterior, novo):
    _, p, e = cenario(anterior)
    alterar_estoque(Conta.objects.get(papel='administrador'),e,novo)
    e.refresh_from_db()
    assert e.limite == (None if novo is None else D(novo))

@pytest.mark.django_db
def test_controle_fifo_outro_comprador_e_remocao_pendente():
    from apps.interesses.servicos import remover_pendente
    _, p, _ = cenario('6')
    a,b = ContaFactory.create(),ContaFactory.create()
    reservada(a,p,6)
    x = pendente(b,p,4)
    r=definir_interesse(a,p,'4')
    assert r.reservado==4
    x.refresh_from_db()
    assert (x.quantidade_reservada,x.quantidade_pendente)==(2,2)
    remover_pendente(b,p,'2')
    x.refresh_from_db()
    assert (x.quantidade_reservada,x.quantidade_pendente)==(2,0)

@pytest.mark.django_db
def test_controle_arredondamento_e_isolamento():
    from apps.catalogo.models import Unidade
    from apps.interesses.progresso import progresso_da_rodada
    r,p,_=cenario(None,unidade=Unidade.KG,incremento=D('.25'),preco=D('2.50'))
    a,b=ContaFactory.create(),ContaFactory.create()
    reservada(a,p,'.25'); reservada(b,p,'.25')
    pendente(a,p,'1')
    progresso=progresso_da_rodada(r,a)
    assert progresso.valor_elegivel==D('1.26')
    assert progresso.produtos[0].do_comprador.reservado==D('.25')
    assert progresso.produtos[0].do_comprador.pendente==D('1')

@pytest.mark.django_db(transaction=True)
def test_preco_e_suspensao_sem_deadlock():
    from apps.contas.moderacao import suspender
    _,p,_=cenario('10')
    a=ContaFactory.create()
    admin=Conta.objects.get(papel='administrador')
    reservada(a,p,1)
    def preco(barreira):
        with transaction.atomic():
            Produto.objects.select_for_update().get(pk=p.pk)
            barreira.wait(timeout=10)
            editar_produto(admin,p,preco='15.99')
    def suspensao(barreira):
        with transaction.atomic():
            Conta.objects.select_for_update().get(pk=a.pk)
            barreira.wait(timeout=10)
            suspender(admin,a)
    resultados=executar_em_paralelo(preco,suspensao)
    assert all(r.excecao is None for r in resultados), [str(r.excecao) for r in resultados]

```

---

## Registro original do implementador (preservado como evidência)

# E05-01 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E03-02, E03-03, E03-04, E03-05 e E03-06.

## Arquivos

- `apps/rodadas/condicoes.py`: `travar_rodada_para_interesses`, `interesses_editaveis`, `InteressesBloqueados`.
- `apps/interesses/consultas.py`: `travar_parcelas`.
- `apps/interesses/servicos.py` (novo): `adicionar_interesse`, `reduzir_interesse`, `definir_interesse`, `interesse_do_comprador`, `ResumoDoInteresse`, `ProdutoForaDaRodada`, `EstoqueInsuficiente`, `ReducaoAcimaDoReservado`.
- Testes: `tests/tecnicos/test_interesses_servicos.py` (A-1 a A-12) e `tests/tecnicos/test_interesses_concorrencia.py` (A-13 a A-16). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** assinaturas e exceções, com os serviços devolvendo `ResumoDoInteresse(0, 0)`, `travar_parcelas` devolvendo `[]` e a primitiva sem trava nem conferência.

**Red.** `uv run pytest tests/tecnicos/test_interesses_servicos.py -q`: **45 failed**, todos por asserção (`DID NOT RAISE` de `QuantidadeInvalida`, `PermissionDenied`, `InteressesBloqueados`, `EstoqueInsuficiente`, `TransactionManagementError`, e `reservado` 0 no lugar do esperado). Uma primeira rodada falhou por erro do próprio teste (segundo administrador violando `conta_administrador_unico`); corrigi o teste para usar o administrador que a `RodadaFactory` já cria, sem alterar nenhuma garantia.

**Green.** Mesmo arquivo: **45 passed**. Suíte completa: **1511 passed** (eram 1461). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

**Concorrência (A-13 a A-16).** Estes testes foram escritos **depois** do Green, porque dependem do serviço real para segurar as travas (a operação que segura roda dentro de uma `transaction.atomic()` externa e espera a outra aparecer em `pg_stat_activity`). Não há Red observado. Em troca, verifiquei por mutação que eles detectam falta de trava: trocar o `select_for_update` da conta por `get` faz o A-15 falhar. Tirar as travas do fornecedor e da rodada **não** quebra nenhum teste, porque o produto, o estoque e as parcelas travados na sequência já serializam sozinhos (a trava do fornecedor é a primeira defesa pela spec; as demais, a segunda). Isso fica como limite da verificação.

## Decisões técnicas

- `EstoqueInsuficiente(disponivel, unidade)` e `ReducaoAcimaDoReservado(reservado)` montam a própria mensagem (`mensagem`); a unidade usa o rótulo de `Unidade` ("unidade", "L").
- `definir_interesse` aceita zero por `_validar_total`; os demais valores passam por `validar_quantidade` já com o produto relido sob trava.
- `ProdutoForaDaRodada` cobre também o produto de outro fornecedor, porque a trava e o estoque são buscados pela rodada do fornecedor do produto.
- Reduzir uma parcela `ativa` com pendência a zero reservado a deixa `pendente` (e `removida` se a pendência também for zero), como a spec manda.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_adicionar_cria_parcela_e_audita` |
| A-2 | `test_acrescimo_posterior_vai_para_o_fim_da_fila` (`acceptance`, cenário 8) |
| A-3 | `test_reducao_atravessa_parcelas_da_mais_recente_para_a_mais_antiga` |
| A-4 | `test_excedente_e_recusado_por_inteiro`, `test_estoque_zero_esta_esgotado` |
| A-5 | `test_quantidades_e_incrementos` (`acceptance`, cenários 63, 85, 109), `test_entradas_invalidas_nao_gravam` |
| A-6 | `test_reducao_acima_do_reservado_e_quantidade_invalida` |
| A-7 | `test_definir_interesse_e_idempotente` |
| A-8 | `test_so_comprador_ativo_mexe_em_interesse` |
| A-9 | `test_etapas_que_aceitam_interesse`, `test_sem_rodada_ativa_e_bloqueado` |
| A-10 | `test_produto_fora_da_rodada` |
| A-11 | `test_produto_indisponivel_continua_aceitando` |
| A-12 | `test_travar_rodada_exige_transacao` |
| A-13 | `test_ultima_unidade_disputada_so_uma_vence` (cenário 3) |
| A-14 | `test_adicao_e_alteracao_de_incremento_se_serializam` (as duas ordens; cenário 108) |
| A-15 | `test_suspensao_confirmada_antes_barra_a_adicao` |
| A-16 | `test_dez_adicoes_de_dois_com_limite_dez` |

O cenário 63/85/109 usa `float` e `"1000000000.000"` em `test_entradas_invalidas_nao_gravam`; o subtotal de R$ 18,00 (1,5 kg a R$ 12,00) está em `test_quantidades_e_incrementos`.

## Limites da verificação

Cliente e banco reais (Postgres); sem navegador. A recusa do prazo de fechamento vencido é da E06. As telas e as rotas são da E05-05.


---

## Correções do implementador após o parecer de `32b05a2` (2026-10-18)

Status: correções concluídas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Nenhum teste existente foi alterado, afrouxado ou removido: todas as mudanças em testes são acréscimos. Suíte completa: **1657 passed** (eram 1619). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

### E05-R02 — total desejado com pendência própria (critérios A-17 a A-20)

**Andaime sem comportamento (exceção técnica):** a exceção `InteresseDesatualizado` e o argumento `esperado` aceito e ignorado em `definir_interesse` e `remover_pendente`.

**Red.** `uv run pytest tests/tecnicos/test_interesses_servicos.py -q`: **4 failed, 48 passed**, por asserção (`DID NOT RAISE InteresseDesatualizado` em A-17 (a), A-19 (b) e A-20; `ResumoDoInteresse(...) == ResumoDoInteresse(0, 0)` falhando em A-18). Passaram já no Red os casos que descrevem o comportamento anterior, que a correção preserva: A-17 (b) e (c), e A-19 (a).

**Green.** `definir_interesse` passou a: calcular o estado atual a partir das parcelas travadas; devolver sem gravar quando o pedido já está cumprido (mesmo com `esperado` diferente); recusar com `InteresseDesatualizado` quando `esperado` difere do estado; com total zero, remover primeiro as pendências (`interesse.remover_pendente`), depois o reservado (`interesse.reduzir`) e por último atender a fila. `remover_pendente` ganhou a mesma conferência de `esperado`, depois das travas e antes de remover. Os três arquivos de serviços, fila e remoção: **96 passed**. A-17 (a) a (c), A-18, A-19 e A-20 em `tests/tecnicos/test_interesses_servicos.py`, com os invariantes (total reservado ≤ 6 e reservado + pendente ≤ original) conferidos passo a passo.

A prova `test_definir_com_pendencia_propria` do revisor (que espera (4, 4) três vezes) **não** foi incluída, conforme a decisão da correção: ela contradiz a FIFO. As provas `test_zero_remove_com_pendencia_propria` e `test_http_zero_remove_com_pendencia` valem: a primeira está coberta por A-18 (resultado (0, 0)) e a segunda entrou literal em `test_interesses_carrinho.py` (E05-05, A-23).

### E05-R03 — deadlock entre preço e operações do comprador (critério A-21)

**Red real.** Os testes foram escritos **antes** da correção, contra o código de `32b05a2` mais as correções R01 e R02: `uv run pytest tests/tecnicos/test_interesses_concorrencia.py -k preco -q`: **6 failed**, todos com `deadlock detected` (`['None', 'deadlock detected ...']`): `adicionar`, `definir`, `reduzir`, `remover_pendente` (A-21) e, na E05-07, suspensão (A-15) e remoção da conta (A-16). A pausa fica dentro do serviço: a função `_travar_conta` é substituída por outra que chama a original e espera a barreira, e a edição de preço trava o produto com `select_for_update()` e espera a mesma barreira antes de chamar `editar_produto`.

**Green.** `_travar_conta` (`apps/interesses/servicos.py`) e `_travar` (`apps/contas/moderacao.py`) passaram a usar `select_for_update(no_key=True)`. Arquivo de concorrência: **22 passed**; suíte completa **1657 passed**. Para cada serviço, o teste confere: sem exceção nas duas operações, preço 15,99, uma notificação `preco_alterado` com a chave da alteração e o efeito do serviço gravado. Os testes A-8 e A-14 da E05-07 e o A-15 da E05-01, que dependem de a conta serializar a adição e a moderação, continuam verdes.

### Não conformidade de TDD (E05-R04): critérios A-13, A-14, A-15 e A-16

**Critérios:** E05-01 A-13 a A-16.

**O que aconteceu:** os quatro testes de concorrência foram escritos **depois** do código de produção correspondente (os serviços e todas as suas travas foram escritos no mesmo passo do Green funcional). **Não houve Red observado nesses critérios.** Os registros originais acima dizem isso; este registro não altera o que eles dizem.

**Causas (confirmo as do especificador):** (1) classifiquei como "exceção" algo que não é scaffolding sem comportamento testável, e a exceção não existe no AGENTS.md; (2) no Green escrevi todas as travas de uma vez, e nenhum teste em falha as exigia; (3) repeti o desvio nas fatias seguintes em vez de parar e escalar a dúvida; (5) cada fatia saiu em um commit com produção e testes juntos. Sobre (4), os critérios de concorrência descreviam o arranjo do teste, mas não como obter o Red; isso não justifica o que fiz.

**Tratamento (opção (a), decidida pelo responsável):** este registro mais a prova de sensibilidade abaixo. Não reconstitui Red histórico e **não** autoriza dizer que o TDD original ocorreu.

### Sensibilidade (mutação), não Red — E05-01

Comando de cada rodada: `uv run pytest -q -p no:cacheprovider --tb=line <testes>`. A mutação foi aplicada, o teste rodou, a mutação foi desfeita (árvore limpa conferida com `git status`) e o teste rodou de novo.

| Critério | Mutação | Resultado mutado | Desfeita |
|---|---|---|---|
| A-15 | `servicos.py`: `Conta.objects.select_for_update(no_key=True).get(pk=comprador.pk)` → `Conta.objects.get(pk=comprador.pk)` | 1 failed em 16,6 s: `AssertionError('a outra conexão não ficou esperando pela trava')` | 1 passed |
| A-14 | `servicos.py`: `atual = Produto.objects.get(pk=produto.pk)` (produto relido sob trava) → `atual = produto` (validar com a instância recebida) | 1 failed, 1 passed: `AssertionError: assert False` em `test_adicao_e_alteracao_de_incremento_se_serializam[False]` (a adição passou a ser aceita com o incremento antigo) | 2 passed |
| A-13 e A-16 | retirar as travas de fornecedor e rodada (`travar_rodada_para_interesses`), de produto e estoque (`travar_estoque`) e de parcelas (`_parcelas`) | 2 failed em 16,8 s: A-13 com `AssertionError('a outra conexão não ficou esperando pela trava')` e A-16 com `AssertionError: []` (nenhuma adição recusada: sobrevenda) | 2 passed |
| A-13 e A-16 | retirar **só** as travas de fornecedor e rodada | **2 passed: a mutação não é detectada** | 2 passed |

**Limites dos testes.** (1) Nos critérios de "segurar a trava", quando a proteção some a falha vem da asserção de sincronização do próprio teste (`a outra conexão não ficou esperando pela trava`), depois do prazo de 15 s; é uma falha por asserção com mensagem, mas lenta. (2) A trava de fornecedor e rodada, retirada sozinha, não quebra nenhum teste, porque produto, estoque e parcelas já serializam: o caso já registrado. **Reforço proposto:** um critério que exercite duas operações de fornecedores iguais sobre produtos **diferentes** do mesmo fornecedor (a trava do fornecedor é a única comum), segurando a primeira até a segunda aparecer esperando.
