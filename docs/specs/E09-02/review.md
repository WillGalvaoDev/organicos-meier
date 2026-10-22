# E09-02 — Revalidação independente sobre 2930ffd

**Veredito: APROVADO no escopo desta fatia.**

Revisão independente de 2026-10-22, base `2930ffddc8fc53ad21c6bb777719b19508d1a4da` (branch `e09-implementacao`). Foram conferidos os adendos de especificação e aceitação em `6dc9850`, o commit de testes Red `e3733ad`, os diffs das correções e os registros de implementação. O histórico anterior permanece integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2418 passed in 234.26s**, sem filtro; `uv run ruff check .` passou; `uv run ruff format --check .` → 329 arquivos; `uv run mypy .` → 393 arquivos sem erros; `uv run python manage.py makemigrations --check --dry-run` → nenhuma alteração pendente. Provas adicionais: **4 failed, 9 passed in 9.77s**. Reprodução completa, limites e veredito global no [parecer consolidado](../E09-08/review.md).

## Matriz e achados

A-1–A-18: testes verdes na suíte completa; sem mudança própria nesta correção e sem novo achado. Mantido o parecer local anterior. A E09 global continua reprovada por R07/R10; a integração real permanece fora da fase 1.

---

# E09-02 — Parecer independente sobre 34f9547

**Veredito: APROVADO no escopo desta fatia.**

Base: `34f9547ae7962687ed96997e3338914f985a277f`, branch `e09-implementacao`, revisão independente em 2026-10-22. Lidos documentos-base funcional v1.6 e infraestrutura v1.7, AGENTS.md, especificações, critérios, código, testes e registros das oito fatias. Histórico do implementador preservado integralmente abaixo.

Verificações independentes:

- `uv run pytest -q`: **2398 passed in 273.67s**, sem filtro, PostgreSQL e banco separado do simulador.
- `uv run ruff check .`: passou; `uv run ruff format --check .`: 328 arquivos conformes.
- `uv run mypy .`: 391 arquivos sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais, fora da suíte versionada: **9 failed in 8.57s**, pelos defeitos descritos no [parecer consolidado](../E09-08/review.md), que contém o código completo para reprodução.

Não foram alterados código de produção nem testes versionados. Testes verdes dos critérios existentes não bastam para aprovar as interações financeiras. O revisor não presenciou os ciclos TDD históricos; conferiu os registros e não trata mutação posterior como Red anterior à implementação.

## Matriz e achados

A-1–A-18: testes existentes verdes. Conferidos tarifa decimal, liberação, preenchimento tardio/divergências no escritor único, movimentos/saldo, controles e falhas do simulador, autorização/desligamento das rotas e query string encaminhada à validação do provedor. Registros Red/Green compatíveis. A-14 usa a trava herdada da E07; sua mutação é sensibilidade, não novo Red histórico. A-2/A-16/A-18 já verdes foram declarados como guardas. Nenhum achado próprio novo. Integração real continua fora da fase 1. Esta aprovação local não aprova a E09.

---

# E09-02 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- Interface: `apps/pagamentos/provedor.py` (`PagamentoConsultado.tarifa` e `liberado_em`, `SaldoNoProvedor`, `MovimentoNoProvedor`, `TipoDeMovimentoNoProvedor`, `consultar_saldo`, `listar_movimentos`, `verificar_aviso(corpo, cabecalhos, parametros)`).
- Registro: `apps/pagamentos/models.py` (`PagamentoNoProvedor.tarifa` e `liberado_no_provedor_em`, divergências `tarifa` e `liberacao`), `apps/pagamentos/sincronizacao.py`, migração `pagamentos/0004_tarifa_e_liberacao.py`.
- Avisos: `apps/pagamentos/avisos.py` e `views.py` (a query string chega ao provedor).
- Simulador: `models.py` (`MovimentoSimulado`, `tarifa` e `liberado_em` da cobrança, migração `0002_tarifa_liberacao_e_movimentos.py`), `plano.py` (tarifa e liberação por meio), `estado.py` (cálculo na aprovação e movimentos), `provedor.py`, `controle.py`, `views.py`, `urls.py` e `templates/simulador_pagamentos/lista.html` (dois formulários).
- Testes: `test_pagamentos_simulador.py` (A-1 a A-7, A-11, A-14 a A-16), `test_pagamentos_sincronizacao.py` (A-8 a A-10), `test_simulador_pagamentos_tela.py` (A-12), `test_pagamentos_avisos.py` (A-17 e A-18), `test_pagamentos_fronteiras.py` (A-13).

## Andaime (exceção técnica)

Antes do Red: os tipos novos e os campos com padrão `None`; as assinaturas de `consultar_saldo` (devolve zero) e `listar_movimentos` (devolve lista vazia) no simulador; as assinaturas dos cinco controles novos (corpo vazio); o modelo `MovimentoSimulado`, os campos novos das tabelas e as migrações. Sem comportamento testável.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pagamentos_simulador.py tests/tecnicos/test_pagamentos_sincronizacao.py tests/tecnicos/test_simulador_pagamentos_tela.py tests/tecnicos/test_pagamentos_avisos.py tests/tecnicos/test_pagamentos_fronteiras.py -q -p no:cacheprovider` contra o andaime: **24 falharam, 104 passaram**.

| Critério | Teste | Resultado do Red |
|---|---|---|
| A-1, A-3, A-4, A-11, A-15 | `test_a_aprovacao_informa_...`, `test_o_saldo_separa_...`, `test_movimentos_da_conta_...`, `test_ajuste_aparece_...`, `test_reiniciar_apaga_...` | asserção: tarifa `None` em vez de `1.24`; saldo zerado; lista vazia |
| A-5 a A-7 | `test_movimentos_e_controles_recusam_...`, `test_saldo_e_movimentos_seguem_...`, `test_falhar_proximas_vale_...` | `DID NOT RAISE` |
| A-8 a A-10 | os três testes de `test_pagamentos_sincronizacao.py` | asserção: `tarifa` e `liberado_no_provedor_em` nulos |
| A-12 | `test_depositar_e_registrar_saida`, `test_valor_invalido_...` (5), `test_deposito_e_saida_so_para_...`, `test_a_lista_traz_...`, `test_as_rotas_novas_...` | 404 (rota inexistente) no lugar do 302, 400, 403 |
| A-13 | `test_nenhuma_rota_comando_ou_admin_registra_pagamento` | conjunto de rotas sem `depositar` e `saida` |
| A-14 | `test_duas_aprovacoes_concorrentes_...` | `assert sorted(...) == ['pagamento', 'tarifa']` (nenhum movimento) |
| A-17 | `test_o_provedor_recebe_os_parametros_da_url` | `assert None == {'data.id': '123', 'type': 'payment'}` |
| A-2, A-16 | `test_antes_da_aprovacao_...`, `test_o_saldo_diz_a_que_instante_...` | **passaram já no Red**: o andaime devolve `None` e `agora()`, que é o que os critérios pedem; protegem a regressão |
| A-18 | `test_a_query_string_nao_muda_...` | **passou já no Red**: a rota já ignora a query string; é guarda de regressão da E07-05 |

## Green

Simulador (tarifa por meio com `ROUND_HALF_UP` uma vez, liberação em horas, movimentos `pagamento`/`tarifa`/`deposito`/`saida`/`ajuste`, saldo liberado e a liberar, `reiniciar` apagando os movimentos); sincronização (grava a tarifa e a liberação, divergência `tarifa` e `liberacao`, preenchimento tardio); avisos (a query string vai do `request.GET` até `verificar_aviso`); tela (dois formulários, mensagens, auditoria `simulador.depositar` e `simulador.registrar_saida`, 404 sem o simulador, política de administrador). Mesmo comando: **128 passed**.

**A-14 e a proteção que já existia.** A trava da cobrança é da E07-01. Prova de sensibilidade (mutação, não Red): com `estado.obter` sem `select_for_update`, o arquivo inteiro de `test_pagamentos_simulador.py` dá **1 falhou, 53 passaram** (`test_duas_aprovacoes_concorrentes_geram_um_par_de_movimentos`, `assert 0 == 1` nos erros esperados); restaurado, **54 passed**.

## Testes antigos ajustados (só a assinatura, como a spec permite)

`tests/tecnicos/test_pagamentos_simulador.py`, as seis chamadas diretas a `verificar_aviso`, com o terceiro argumento `{}` e nenhuma outra mudança: `test_..._indisponivel` (a lambda de `verificar_aviso(b"{}", {})`), `test_verificacao_do_aviso` (as duas chamadas), `test_verificar_aviso_recusa_assinatura_...` (a de `corpo` assinado), `test_verificacao_aceita_cabecalho_em_qualquer_caixa` e `test_verificar_aviso_recusa_corpo_assinado_fora_do_limite`. Nenhum teste de `receber_aviso` precisou de ajuste: `entregar_avisos` do simulador chama `receber_aviso` com `{}` e os receptores injetados pelos testes mantêm a assinatura de dois argumentos.

## Decisões técnicas e desvios

- **Descrição do depósito.** O movimento `deposito` leva o rótulo `deposito`; `ajuste`, `ajuste`; `saida`, a descrição digitada (até 50 caracteres, cortada se passar).
- **Ordem dos movimentos.** Por `ocorrido_em` e `pk` (o `id_movimento` é `mov-<pk>`; ordenar o texto erraria a partir de `mov-10`).
- **Tarifa zero é informada.** Aprovada com o plano zerado, a cobrança informa `tarifa = 0,00` e `liberado_em = aprovado_em`, e não gera movimento de tarifa. `None` continua sendo só "não informou" (antes da aprovação).
- **Erro da tela.** Valor inválido responde 400 com a mensagem do formulário; sem descrição, 400 com "Informe a descrição da saída.".
- **Auditoria.** As duas ações novas da tela gravam auditoria (`simulador.depositar`, `simulador.registrar_saida`), como as demais ações da tela; a spec não pede, e há asserção nos testes.
- **O M-2 voltou a pesar.** Não citei `PagamentoNoProvedor` nem `ConsultaDoPagamento` em módulo de escrita fora da sincronização.

## Verificação

Os cinco arquivos da fatia: **128 passed**. Suíte completa, sem filtro, no commit da fatia (que inclui a E09-01): `uv run pytest -q -p no:cacheprovider` → **2254 passed in 264.85s**; `ruff check`, `ruff format --check` (300 arquivos), `mypy` (354 arquivos) e `makemigrations --check`: limpos.
