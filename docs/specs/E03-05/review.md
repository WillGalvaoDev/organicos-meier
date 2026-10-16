# E03-05 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **REPROVADO** sobre `0ceb171` (2026-10-16). E03 global: **REPROVADO**. Evidências históricas do implementador abaixo; revisão independente ao final.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** `EstoqueDaRodada` só com campos (sem restrições),
sinal `estoque_alterado`, `estoque.py` com corpos triviais, views vazias, rotas,
`EstoqueDaRodadaFactory`, migração `0003_estoque`. Suíte antes do Red: 894 passando.

**Red** (`uv run pytest tests/tecnicos/test_rodadas_estoque*.py tests/tecnicos/test_rodadas_permissoes.py`):
**45 falhas, 14 passando**. Falhas por asserção/ausência de comportamento: `DID NOT RAISE`
(`CondicoesCongeladas`, `EstoqueAbaixoDoReservado`, `ValidationError`, `IntegrityError`,
`TransactionManagementError`), `200 == 302/409`, auditoria `0 == 1`, concorrência sem efeito
(`a outra conexão não ficou esperando pela trava`). As 14 que passavam: 6 guardas de permissão
(403/redirecionamento, rotas do andaime já usam `somente_administrador`), regressões
(`save()` comum, SQL válido) e 5 testes fracos demais para o andaime; depois do Red os
5 foram reforçados (inclusão de produto indisponível passou a exigir registro persistido; erros de
tela e produto de outro fornecedor passaram a exigir `role="alert"`; a tela passou a exigir o
nome do fornecedor) antes de escrever o código.

**Green:** `migrations/0004_restricoes_do_estoque` (UNIQUE, CHECK e triggers de `gatilhos.py`),
`estoque.py` (`incluir_produto_na_rodada`, `alterar_estoque`, `travar_estoque`, `estoque_livre`,
`EstoqueAbaixoDoReservado`), `forms.py`, três views, template `rodadas/estoque.html`, link no
detalhe do fornecedor. Resultado: arquivos de estoque e permissões 59 passando; suíte completa
**950 passando**; `ruff check`, `ruff format`, `mypy --strict` e `makemigrations --check` limpos.

**Refactor:** apenas ajustes de lint/tipos (linhas longas, `Any`) após o Green.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_rodadas_estoque.py::test_inclusao_com_e_sem_limite_pela_tela` |
| A-2 | `::test_nova_rodada_comeca_sem_produtos` |
| A-3 | `::test_produto_de_outro_fornecedor_e_recusado`, `::test_banco_recusa_produto_de_outro_fornecedor` |
| A-4 | `::test_produto_ja_incluido_e_recusado` |
| A-5 a A-7 (cenário 71, T-23) | `::test_reducao_ate_o_reservado_e_aceita`, `::test_reducao_abaixo_do_reservado_e_recusada`, `::test_sem_limite_nao_pode_ir_abaixo_do_reservado` |
| A-8 | `::test_remover_o_limite_envia_o_sinal` |
| A-9 (cenário 72, T-23) | `::test_estoque_congelado_pela_rota`, `::test_estoque_congelado_pelo_servico` (4 etapas) |
| A-10 | `::test_estoque_de_rodada_antiga_nunca_muda` |
| A-11, A-12 | `::test_sinal_na_inclusao_e_na_alteracao`, `::test_receptor_que_falha_desfaz_a_alteracao`, `::test_receptor_que_falha_desfaz_a_inclusao` |
| A-13 | `::test_estoque_livre`, `::test_estoque_livre_tem_piso_zero` |
| A-14 | `::test_banco_recusa_limite_negativo_troca_de_produto_e_exclusao`, `::test_banco_recusa_troca_de_rodada` |
| A-15 | `test_rodadas_estoque_concorrencia.py::test_alteracao_do_estoque_espera_a_mudanca_de_etapa` |
| A-16 | `::test_reserva_concluida_antes_barra_a_reducao` |
| A-17 | `::test_duas_inclusoes_do_mesmo_produto` (×10) |
| A-18 | `test_rodadas_permissoes.py::test_estoque_so_para_administrador`, `::test_estoque_visitante_anonimo_vai_para_o_login` |
| A-19 | `test_rodadas_estoque.py::test_tela_somente_leitura_fora_de_interesse` |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- Produto de outro fornecedor é verificado **antes** de qualquer trava, comparando
  `produto.fornecedor_id` com `rodada.fornecedor_id` (senão a ausência de rodada ativa do outro
  fornecedor mascararia o erro); a trigger do banco repete a regra.
- `travar_estoque(rodada, produto)` trava o produto e depois o estoque, exige transação aberta
  (`TransactionManagementError`) e supõe que o chamador já fez `travar_condicoes`.
- `alterar_estoque` lê o total reservado com `total_reservado(produto, travar=True)` (parcelas
  travadas em ordem de sequência) e compara só depois de o limite igual ao atual ter retornado
  sem gravar, auditar ou enviar sinal.
- Auditoria de alteração: `{"estoque", "rodada", "produto", "anterior", "novo"}` com texto
  decimal ou `null`.
- Sinal na inclusão: `anterior=Decimal("0")` e `novo=<limite ou None>`, como na especificação.
- A tela re-renderiza com `role="alert"` para erros (status 200), e com 409 para
  `CondicoesCongeladas`; `produto` inexistente no `POST` de inclusão vira "Produto inválido." (200).

## Limitações de verificação

- A reserva real (E05) não existe: A-16 simula a reserva com a mesma ordem de travas
  (`travar_condicoes`, `travar_estoque`, `UPDATE` da parcela).
- A-15 e A-16 detectam a espera com `pg_stat_activity.wait_event_type = 'Lock'` no banco inteiro;
  outro processo esperando por trava no mesmo banco liberaria a thread antes da hora (não ocorre
  na suíte).
- `alocar_pendentes` ao aumentar o estoque é da E05; aqui só o sinal é provado.
- Telas verificadas pelo cliente de teste do Django, não por navegador.

## Revisão independente — 0ceb171 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

A-1 a A-19: isolamento de fornecedor, estoque por rodada, redução até a reserva, congelamento, rollback de receptor e concorrência cobertos e verdes. Reserva simulada anterior impede redução; inclusão duplicada tem dez repetições. Falha adicional na faixa do limite: E03-R01.

Verificação comum: `uv run pytest -q` — **1058 passed em 147,85 s**; ruff check limpo; ruff format — 238 arquivos; mypy — 193 arquivos sem erros; checks Django e migrações sem pendências. Os probes adicionais de fronteira terminaram em **8 failed, 8 passed em 4,36 s**, reproduzindo E03-R01. Não houve correção de produção ou testes pelo revisor.

Comandos completos, achados, reprodução, limites e parecer global estão em [E03-08/review.md](../E03-08/review.md), na seção de revisão independente deste SHA. Os relatos Red/Green anteriores foram conferidos com o diff e a cobertura; a execução Green é independente, a cronologia Red é evidência documentada pelo implementador.


## Correção E03-R01 — implementador (aguardando nova revisão independente)

Achado do revisor: entrada acima da capacidade das colunas `NUMERIC(12,2)`/`NUMERIC(12,3)` virava
HTTP 500 (`numeric field overflow`). Corrigido conforme a seção "Correção E03-R01" da spec.

- **Red:** com as primitivas só em andaime (constantes `0`, `cabe_*` sempre verdadeiro) e os
  testes de `tests/tecnicos/test_capacidade_decimal.py` e `test_rodadas_minimo.py` escritos:
  **37 falhas, 27 passando**. Os 8 casos do script de probes do revisor que excedem a
  capacidade falharam com `500` e `DataError('numeric field overflow')`, reproduzindo o achado;
  os demais falharam por `DID NOT RAISE` e por asserções de valores.
- **Green:** `apps/nucleo/valores.py` ganhou `MAIOR_DINHEIRO`, `MAIOR_QUANTIDADE` (derivadas de
  `CampoDinheiro` e `CampoQuantidade`), as mensagens de capacidade, `cabe_em_dinheiro` e
  `cabe_em_quantidade`; a regra entrou nos serviços depois das regras de sinal/mínimo e antes da
  compatibilidade: `_minimo` (E03-01/02), `_preco` (E03-03), `validar_incremento`,
  `validar_multiplo`, `validar_quantidade` (E03-03/06) e `_limite` do estoque (E03-05). Nenhuma
  função numérica existente mudou e nenhum `DataError` é capturado. Resultado: suíte completa
  **1104 passando**; `ruff check`, `ruff format --check`, `mypy --strict` e
  `makemigrations --check` limpos.
- **Testes:** `tests/tecnicos/test_capacidade_decimal.py` (A-18 a A-20 da E03-01, A-24 a A-28 da
  E03-03, A-20 e A-21 da E03-05, A-15 da E03-06 e o script de probes do revisor, literal: 16 casos,
  8 no limite com 302 e 8 acima com 200); A-19 da E03-02 em `test_rodadas_minimo.py`.
- **E03-R02:** os testes já cobrem a pré-condição corrigida (A-3: só a pendente de 2,0 →
  `multiplo`; A-14: produto completo → `quantidade`); nenhuma mudança de código.
- **Limite:** um texto com 30 dígitos é recusado pela conversão/formulário com a mensagem de
  formato (permitido pela spec); a exigência é erro de campo, nunca 500.
