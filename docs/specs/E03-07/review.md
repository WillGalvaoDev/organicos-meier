# E03-07 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `0ceb171` (2026-10-16). E03 global: **REPROVADO**. Evidências históricas do implementador abaixo; revisão independente ao final.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** `Ciclo` e `CondicaoDoProdutoNoCiclo` só com campos
(`RegistroSoInsercao`, sem restrições nem triggers), `registrar_condicoes_do_ciclo` que devolve um
`Ciclo` vazio, `ciclo_vigente` que devolve `None`, auxiliares de teste
`tests/apoio/ciclos.py` (`simular_inicio_do_fechamento`, `simular_volta_para_interesse`) e
migração `0005_ciclos`. Suíte antes do Red: 983 passando.

**Red** (`uv run pytest tests/tecnicos/test_rodadas_ciclos*.py tests/tecnicos/test_condicoes_congeladas_matriz.py`):
**18 falhas, 36 passando**. Falhas: `DID NOT RAISE IntegrityError` (restrições e triggers),
`DID NOT RAISE CondicoesCongeladas` e `TransactionManagementError`, `assert None == 1`,
`assert None is not None`, `Ciclo.DoesNotExist`, `ValueError: Model instances passed to related
filters must be saved` (o `Ciclo()` do andaime não foi salvo) e concorrência sem efeito. Nota de
honestidade: as falhas por `ValueError` e `DoesNotExist` vêm do objeto vazio do andaime, não de uma
asserção sobre o resultado final.

Os 36 que já passavam: 35 são a **matriz consolidada A-9/A-10 (T-23, cenário 72)**, que por
desenho verifica o congelamento já implementado nas E03-02 a E03-06 (regressão consolidada; seu
valor é impedir que uma fatia futura reabra uma condição), mais A-3 (as condições voltam a ser
editáveis na volta para interesse, comportamento já existente).

**Green:** `apps/rodadas/ciclos.py` (`registrar_condicoes_do_ciclo`, `ciclo_vigente`), restrições
`ciclo_numero_unico`, `ciclo_numero_positivo`, `condicao_produto_unica` e a proteção de só
inserção por trigger (`instalar_protecao_so_insercao`) nas duas tabelas, migração
`0006_restricoes_dos_ciclos`. Resultado: arquivos da fatia 54 passando; suíte completa **1037
passando**; `ruff check`, `ruff format`, `mypy --strict`, `makemigrations --check` limpos.

**Ajuste depois do Green:** acrescentei ao teste A-1 a asserção `autor_tipo == "sistema"` (a
transição é do sistema); passou de imediato porque o código já usa `SISTEMA`.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_rodadas_ciclos.py::test_inicio_do_fechamento_registra_as_condicoes_vigentes` |
| A-2 (cenário 73) | `::test_cenario_73_ciclos_anteriores_nao_mudam` |
| A-3 (cenário 73) | `::test_condicoes_voltam_a_ser_editaveis_na_volta_para_interesse` |
| A-4 | `::test_ciclo_e_condicoes_so_aceitam_insercao_no_orm`, `::test_banco_recusa_alterar_ou_apagar_ciclo`, `::test_banco_recusa_alterar_ou_apagar_condicao` |
| A-5 | `::test_registro_fora_de_interesse_e_recusado`, `::test_segunda_chamada_no_mesmo_ciclo_e_recusada`, `::test_registro_de_rodada_antiga_e_recusado` |
| A-6 | `::test_registro_fora_de_transacao_falha` (`transaction=True`) |
| A-7 | `::test_ciclo_vigente` |
| A-8 | `::test_banco_recusa_segundo_ciclo_com_o_mesmo_numero`, `::test_banco_recusa_numero_zero_e_condicao_repetida` |
| A-9 (T-23, cenário 72) | `test_condicoes_congeladas_matriz.py::test_nenhuma_condicao_muda_fora_de_interesse` (5 condições × 6 situações; rota com e sem `HX-Request`, e serviço) |
| A-10 | `::test_preco_muda_nas_quatro_etapas_ativas` |
| A-11 | `test_rodadas_ciclos_concorrencia.py::test_fechamento_iniciado_primeiro_registra_o_minimo_anterior`, `::test_dois_inicios_simultaneos_geram_um_ciclo` |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- Auditoria `ciclo.registrar_condicoes` com autor `SISTEMA` (a transição não tem usuário na
  assinatura da especificação, `registrar_condicoes_do_ciclo(rodada)`).
- `registrar_condicoes_do_ciclo` usa `travar_condicoes` (que exige transação aberta e confere que
  a rodada travada é a recebida), trava os produtos da rodada por id e depois os estoques por
  `produto_id`, e relê o fornecedor sob a trava para gravar o mínimo vigente.
- O número do ciclo é o maior número da rodada mais 1, seguro pela trava da rodada; o
  `UNIQUE (rodada, numero)` é a defesa final.
- As condições são inseridas com `bulk_create` (a base `RegistroSoInsercao` só recusa alterar e
  apagar).
- Os auxiliares de `tests/apoio/ciclos.py` seguem o contrato da E06: travam fornecedor e rodada,
  chamam o serviço e gravam a etapa na mesma transação.

## Limitações de verificação

- A transição real para `fechamento` e a volta para `interesse` são da E06; os testes usam os
  auxiliares. A E06 deve passar pelos mesmos testes.
- Pedidos, caixas e cobranças vinculados ao ciclo ficam para E06 e E08.
- A-11 detecta a espera com `pg_stat_activity.wait_event_type = 'Lock'` no banco inteiro.
- A "margem" e a "aptidão para apuração" estão cobertas pela linha `pagamento`, como na
  especificação.

## Revisão independente — 0ceb171 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

A-1 a A-11: registro de condições atuais, ciclos anteriores preservados, proteção ORM/SQL, numeração e concorrência cobertos e verdes. A matriz T-23 cobre cinco operações × seis situações, pelas rotas normal/HTMX e pelos serviços; preço permanece editável nas quatro etapas ativas. Transições reais continuam na E06.

Verificação comum: `uv run pytest -q` — **1058 passed em 147,85 s**; ruff check limpo; ruff format — 238 arquivos; mypy — 193 arquivos sem erros; checks Django e migrações sem pendências. Os probes adicionais de fronteira terminaram em **8 failed, 8 passed em 4,36 s**, reproduzindo E03-R01. Não houve correção de produção ou testes pelo revisor.

Comandos completos, achados, reprodução, limites e parecer global estão em [E03-08/review.md](../E03-08/review.md), na seção de revisão independente deste SHA. Os relatos Red/Green anteriores foram conferidos com o diff e a cobertura; a execução Green é independente, a cronologia Red é evidência documentada pelo implementador.
