# E09-03 — Revalidação independente sobre d365475

**Veredito: APROVADO no escopo desta fatia.**

Revisão executada em 2026-10-22 e concluída em 2026-10-23, base `d365475e68c26f9a2f2e58158a19d643a5aa30b2`, branch `e09-implementacao`. Conferidos os adendos de `5bdc419`, os commits de testes anteriores à produção (`afbe7c0` e `d6a09d3`), as correções e seus registros. O histórico anterior foi preservado integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2428 passed in 361.92s**; Ruff lint passou, formatação de 329 arquivos conforme, mypy sem erros em 393 arquivos e nenhuma migração pendente. As **13 provas do parecer anterior passaram, sem alteração, em 13.66s**. Controle adicional do limite declarado: **1 failed, 2 passed in 5.01s**. O único insucesso é o isolamento da guarda em `TestCase` com objeto `atomic(savepoint=False)` reutilizado; os controles com transações reais passam. Detalhes e reprodução no [parecer consolidado](../E09-08/review.md).

## Matriz e conclusão

A-1–A-13, com A-6 reescrito: mantida a aprovação. R06 continua encerrado; a prova independente de identificação de 64 caracteres passou novamente. Nenhum novo achado próprio. A E09 global ainda depende de R10.

---

# E09-03 — Revalidação independente sobre 2930ffd

**Veredito: APROVADO no escopo desta fatia.**

Revisão independente de 2026-10-22, base `2930ffddc8fc53ad21c6bb777719b19508d1a4da` (branch `e09-implementacao`). Foram conferidos os adendos de especificação e aceitação em `6dc9850`, o commit de testes Red `e3733ad`, os diffs das correções e os registros de implementação. O histórico anterior permanece integralmente abaixo.

Verificação independente: `uv run pytest -q` → **2418 passed in 234.26s**, sem filtro; `uv run ruff check .` passou; `uv run ruff format --check .` → 329 arquivos; `uv run mypy .` → 393 arquivos sem erros; `uv run python manage.py makemigrations --check --dry-run` → nenhuma alteração pendente. Provas adicionais: **4 failed, 9 passed in 9.77s**. Reprodução completa, limites e veredito global no [parecer consolidado](../E09-08/review.md).

## Matriz e achados

A-1–A-13 (A-6 reescrito): testes verdes. Conferidos limite de 80 no serviço/modelo, migração 0010, aceitação de chaves de 70/80 e recusa de 81 caracteres, sem truncamento. Prova independente de identificação de 64 caracteres na conciliação passou. **R06 encerrado** no alcance desta fatia. Red do limite novo vem de A-13 no commit e3733ad; o negativo A-6 já passava e isso foi declarado. A aprovação local não aprova a E09 global.

---

# E09-03 — Parecer independente sobre 34f9547

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

A-1–A-12: testes existentes verdes. Conferidos deduplicação parcial dos alertas abertos, resolução/reabertura, gravidades, validação, destinatário administrador, site/e-mail e atomicidade. A-10 registra funcional sem proteção → falha da corrida → UNIQUE/tratamento. Nenhum achado próprio novo. R06 está no chamador que gera chave maior que o limite documentado; R05/R07 também são falhas de integração. A E09 global não está aprovada.

---

# E09-03 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- `apps/financeiro/alertas.py` (`abrir_alerta`, `resolver_alerta`, `alertas_abertos`), `apps/financeiro/models.py` (`AlertaFinanceiro`, `TipoDeAlerta`, `Gravidade`, restrição `UNIQUE` parcial), migrações `financeiro/0002_alertafinanceiro.py` e `0003_alerta_um_aberto_por_par.py`.
- `apps/notificacoes/eventos.py` (evento `alerta_financeiro`, site e e-mail, para o administrador) e migração `notificacoes/0007_evento_alerta_financeiro.py`.
- Testes: `tests/tecnicos/test_financeiro_alertas.py` (A-1 a A-9, A-11, A-12 e "exige transação"), `tests/tecnicos/test_financeiro_concorrencia.py` (A-10).

## Andaime (exceção técnica)

Antes do Red: os modelos e as migrações; o membro `ALERTA_FINANCEIRO` do enum `Evento` com o catálogo provisório (só site, destinatário comprador, que os testes do A-11 recusam); as três funções com corpo trivial (`abrir_alerta` devolve um alerta não salvo, `resolver_alerta` devolve `None`, `alertas_abertos` devolve lista vazia). O modelo ainda **sem** a restrição `UNIQUE` parcial, que é a proteção do A-10.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_alertas.py tests/tecnicos/test_financeiro_concorrencia.py tests/tecnicos/test_notificacoes_eventos.py -q -p no:cacheprovider`: **20 falharam, 5 passaram** (com o teste de "exige transação" acrescentado depois, o arquivo de alertas ficou em **18 falharam, 2 passaram**).

| Critério | Teste | Resultado do Red |
|---|---|---|
| A-1, A-2, A-3, A-5 | os quatro primeiros de `test_financeiro_alertas.py` | `assert {} == {'sem_cobertura': '50.00', ...}`; `assert '' == Gravidade.AVISO`; `notificações do alerta: 0` |
| A-5 (cada tipo) | `test_titulo_e_corpo_de_cada_tipo` (5) | `notificações do alerta: 0` |
| A-6 | `test_entradas_invalidas_sao_recusadas` (4) | `DID NOT RAISE ValueError` |
| A-7, A-8, A-12 | `test_email_que_falha_...`, `test_alertas_abertos_...`, `test_sem_administrador_...` | asserções do alerta e da lista |
| A-11 | `test_o_catalogo_do_evento_novo` e as duas de `test_notificacoes_eventos.py` | `assert {'alerta_financeiro', 'preco_alterado'} == {'preco_alterado'}` |
| "exige transação" | `test_abrir_e_resolver_exigem_transacao` | `DID NOT RAISE TransactionManagementError` |
| A-4, A-9 | `test_resolver_sem_alerta_...`, `test_transacao_desfeita_...` | **passaram já no Red**: o andaime não grava nada, que é o que os critérios pedem; guardas de regressão |
| A-10 | `test_duas_aberturas_do_mesmo_alerta_gravam_um_so` | falha por asserção do suporte de trava: `a outra conexão não ficou esperando pela trava` |

Na primeira execução, cinco testes falharam por `ValueError: not enough values to unpack` (a lista de notificações vazia); troquei a desestruturação por um auxiliar `_unica` que afirma `len == 1` com mensagem, sem mudar o que o teste exige.

## Green, em dois passos (regra da concorrência)

1. **Verde funcional sem a proteção** (sem a restrição `UNIQUE` e sem tratar o conflito): **25 passaram, 1 falhou**. A falha é o **Red da corrida do A-10**: sem nenhuma trava, a segunda transação não espera, e a asserção do apoio de trava (`a outra conexão não ficou esperando pela trava`) falha. Um erro do meu teste apareceu aqui (`ContaFactory.create(administrador=True)` com o administrador que a fábrica de rodada já cria, violando `conta_administrador_unico`); passei a usar `m.admin`.
2. **A proteção:** a restrição `alerta_um_aberto_por_par` (única em `(tipo, chave)` para os abertos) e o tratamento do `IntegrityError` com savepoint, devolvendo o alerta que a outra transação abriu. Os três arquivos: **26 passed**.

Verificação adicional: `uv run pytest tests/tecnicos -k "notificacoes or financeiro"` → **308 passed**.

## Testes antigos ajustados

`tests/tecnicos/test_notificacoes_eventos.py`, a matriz da E04-01 (`MATRIZ`): acrescentada a linha `("alerta_financeiro", Papel.ADMINISTRADOR, {S, E})`, que a própria spec do A-11 manda ("os outros eventos sem mudança"). Nenhuma outra asserção mudou.

## Decisões técnicas

- **Corpo dos avisos.** Texto de cada tipo, com os valores em reais (`reais`), tolerante a campo ausente em `dados` (mostra um traço). O corpo do invariante usa o módulo da diferença: "O saldo do provedor está R$ 10,00 abaixo do dinheiro de terceiros. Utilizações da reserva e retiradas de receita estão bloqueadas."
- **Destinatários.** Todos os administradores ativos; os suspensos ou removidos não recebem. Sem nenhum, um log `warning` com "nenhum administrador ativo".
- **Importação privada.** A validação de segredos reaproveita `_validar_sem_segredos` da auditoria (a mesma regra), sem duplicar a lista de termos.
- **Ordem de `alertas_abertos`.** Críticos primeiro; depois `aberto_em` e `pk`.

## Verificação

Os três arquivos da fatia: **26 passed**; `ruff check`, `ruff format --check`, `mypy` e `makemigrations --check` limpos. A suíte completa, sem filtro, é registrada na verificação final da E09 (E09-08).
