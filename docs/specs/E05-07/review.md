# E05-07 — Revisão independente

## Nova revisão independente — correções em 8728b4b

Commit: `8728b4b3f459d97bf9c1ce1c74407bbaa2a8655e` (`main`, PR #66), revisto em 2026-10-18. Este parecer substitui o estado de aprovação anterior, cujo histórico permanece abaixo.

**Parecer global: E05 REPROVADA**, por R05 (importante) na apresentação de conflitos da E05-05. R01 e R03 estão corrigidos; o contrato de R02 foi decidido e seu comportamento de serviço está conforme; R04 recebeu o tratamento excepcional aprovado, sem alegação de Red retroativo.

Verificações independentes:

- `uv run pytest -q`: **1657 passed em 133,38 s** (todas as fatias e regressões).
- `uv run ruff check .`: passou; `uv run ruff format --check .`: **217 arquivos** conformes.
- `uv run mypy .`: **251 arquivos**, sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- `uv run pytest -c pyproject.toml $env:TEMP/test_review_e05_8728b4b.py -q --tb=short`: **17 passed, 3 failed em 2,98 s**. As 16 provas anteriores adaptadas ao contrato aprovado passaram; o controle adicional pelo catálogo passou; as três falhas adicionais são R05. Código e reprodução no [parecer consolidado](../E05-01/review.md).

**Fatia APROVADA.** A-1 a A-16 passaram, incluindo preço × suspensão/remoção e as corridas anteriores com adição/fila. R03 encerrado; R04 tratado conforme a opção aprovada, com limites de mutação e reforço proposto preservados no histórico.

---

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

### Parecer da fatia: REPROVADO

A-1 a A-14 passaram, incluindo moderação/adição/fila nas duas ordens, rollback, `em_pedido` e remoção conforme D-1 aprovada. R03 acrescenta a corrida não coberta com edição de preço, que causa deadlock e pode abortar a suspensão. R04 registra ausência de Red para A-8/A-9/A-14. Achados e reproduções no [parecer consolidado](../E05-01/review.md).

---

## Registro original do implementador (preservado como evidência)

# E05-07 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` (inclusive a D-1, decidida em 2026-10-18) e `acceptance.md` da fatia, E02-08, E05-01 e E05-02.

## Arquivos

- `apps/interesses/servicos.py`: `remover_interesses_do_comprador(conta, *, motivo)`.
- `apps/interesses/receptores.py` e `apps/interesses/apps.py`: receptores de `conta_suspensa` e `conta_removida`, conectados no `ready()` com `dispatch_uid`.
- Testes: `tests/tecnicos/test_interesses_suspensao.py` (A-1 a A-7, A-10 a A-13) e, em `test_interesses_concorrencia.py`, A-8, A-9 e A-14 (parametrizados nas duas ordens). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** a função devolvendo zero e os dois receptores sem conexão aos sinais.

**Red.** `uv run pytest tests/tecnicos/test_interesses_suspensao.py -q`: **8 failed, 2 passed**, por asserção (`assert 'ativa' == SituacaoParcela.REMOVIDA`, `DID NOT RAISE RuntimeError` porque os receptores não estavam conectados, `DID NOT RAISE TransactionManagementError`). Passaram já no Red o A-5 (parcela `em_pedido`) e o A-12 (conta suspensa e conta de fornecedor), porque dependem de ausência.

**Green.** Mesmo arquivo: **10 passed**. Com A-8, A-9 e A-14: `test_interesses_concorrencia.py` **16 passed**. Suíte completa: **1619 passed** (eram 1603). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

**Concorrência (A-8, A-9, A-14).** Escritos depois do Green, como nas fatias anteriores (a operação que segura as travas roda numa transação externa e a outra espera em `pg_stat_activity`). Sem Red observado. Cobrem as duas ordens em cada critério: adição antes da suspensão ou da remoção (a parcela nova é removida), moderação antes da adição (a adição recebe `PermissionDenied`), e atendimento da fila antes ou depois da suspensão (A sem parcela `ativa` nem `pendente` e total reservado 0, sem deadlock).

## Decisões técnicas

- **Ordem de travas.** Conta (já travada por `suspender`/`remover`), fornecedores por id; em cada um, a rodada ativa (se houver), os produtos afetados por id, o estoque do produto na rodada e as parcelas por `travar_parcelas`. As parcelas a remover são relidas **depois** das travas, porque o atendimento da fila (E05-02) pode ter mudado uma pendente em ativa antes da suspensão.
- **Fila só onde a rodada aceita reservas** (`interesse` ou `fechamento`) e o produto tem estoque nela; nas outras etapas a reserva só é liberada.
- **Auditoria:** uma entrada por chamada, autor `SISTEMA`, objeto a conta, `{"conta", "parcelas": [[id, reservado anterior, pendente anterior], ...]}` com as quantidades como texto. Sem parcelas, nada é auditado.
- **Conta de fornecedor** na remoção: o receptor devolve sem fazer nada; a função, se chamada com uma conta que não é comprador, devolve 0 antes de travar qualquer coisa.
- **Substituição de um receptor nos testes A-6 e A-13:** o `monkeypatch` troca `remover_interesses_do_comprador` no módulo `apps.interesses.receptores`, onde o receptor o chama.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1, A-2 | `test_suspensao_esvazia_e_a_reversao_nao_restaura` (`acceptance`, cenário 19) |
| A-3 | `test_reserva_liberada_vai_para_a_fila_na_mesma_transacao` |
| A-4 | `test_rodada_que_nao_aceita_reservas_so_libera` |
| A-5 | `test_parcela_em_pedido_nao_muda` |
| A-6 | `test_falha_do_receptor_desfaz_a_suspensao` |
| A-7 | `test_exige_transacao_e_motivo_valido` |
| A-8, A-14 | `test_adicao_e_suspensao_ou_remocao_se_serializam` |
| A-9 | `test_atendimento_da_fila_e_suspensao_se_serializam` |
| A-10 | `test_remocao_da_conta_trata_os_interesses_como_a_suspensao` |
| A-11 | `test_remocao_preserva_em_pedido_e_nao_apaga_parcelas` (`acceptance`, cenário 20) |
| A-12 | `test_remover_conta_suspensa_ou_de_fornecedor_nao_mexe_em_parcelas` |
| A-13 | `test_falha_do_receptor_desfaz_a_remocao` |

## Limites da verificação

Postgres real, sem navegador. O cancelamento dos pedidos não pagos do suspenso e do removido é da E08 (a spec registra a pergunta para a E08). A D-1 foi aplicada como decidida (opção a), sem alteração.


---

## Correções do implementador após o parecer de `32b05a2` (2026-10-18)

Status: correções concluídas; **aguardando nova revisão do agente 3**. Nada aqui é aprovação. Nenhum teste existente foi alterado; só acréscimos. Suíte completa: **1657 passed**.

### E05-R03 — suspensão e remoção em paralelo com alteração de preço (critérios A-15 e A-16)

**Red real:** `uv run pytest tests/tecnicos/test_interesses_concorrencia.py -k preco -q` contra o código anterior: **6 failed** com `deadlock detected`, dos quais 2 são estes: `test_preco_e_moderacao_sem_deadlock[suspensao]` (A-15) e `[remocao]` (A-16). A pausa fica dentro da moderação: `remover_interesses_do_comprador` é substituída, em `apps.interesses.receptores`, por uma função que espera a barreira e chama a original; a edição de preço trava o produto e espera a mesma barreira.

**Green:** `_travar` de `apps/contas/moderacao.py` passou a usar `select_for_update(no_key=True)` (vale para `suspender`, `reativar` e `remover`). O teste confere: sem exceção, preço 15,99, aviso gravado com a chave da alteração, conta `suspensa` ou `removida`, parcela `removida` e, na remoção, e-mail banido. Arquivo de concorrência: **22 passed**.

### Não conformidade de TDD (E05-R04): critérios A-8, A-9 e A-14

**O que aconteceu:** testes escritos depois do código de produção; **sem Red observado**. Causas e tratamento: ver [E05-01/review.md](../E05-01/review.md), que confirmo para estes critérios.

### Sensibilidade (mutação), não Red — E05-07

Comando: `uv run pytest -q -p no:cacheprovider --tb=line tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_suspensao_ou_remocao_se_serializam tests/tecnicos/test_interesses_concorrencia.py::test_atendimento_da_fila_e_suspensao_se_serializam`.

| Critério | Mutação | Resultado mutado | Desfeita |
|---|---|---|---|
| A-8, A-9 e A-14 | `moderacao.py`: `Conta.objects.select_for_update(no_key=True).get(pk=conta.pk)` → `Conta.objects.get(pk=conta.pk)` | **6 passed: a mutação não é detectada** | 6 passed |

**Limite do teste.** Os testes não detectam a leitura sem trava em `_travar` da moderação. A causa provável (não verificada por outra prova) é que o `UPDATE` da situação, na própria moderação, já toma a trava da linha, e a adição que espera a conta espera por esse `UPDATE`. A trava explícita só importa na janela entre a leitura e o `UPDATE`, que esses critérios não exercitam. **Reforço proposto:** um critério com duas moderações concorrentes sobre a mesma conta (por exemplo, `suspender` e `remover`), segurando a primeira entre a leitura e o `UPDATE`, em que a segunda precisa revalidar a situação depois da trava e ser recusada com `ModeracaoInvalida`; sem a trava, as duas passariam pela validação.
