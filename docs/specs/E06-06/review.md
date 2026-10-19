# E06-06 — Revisão independente — 2026-10-19

**Veredito desta fatia: REPROVADO. Veredito global da E06: REPROVADO.**

Base: `main`, commit `2fbf143d082b37a1e8333a0736a310008e10e9ad`. A-1 a A-12 examinados. R04 (importante): com destinatarios omitido, o conjunto é calculado depois de alocar pendentes, incluindo quem não tinha reserva na chamada. A chamada principal por encerrar_fechamento, com destinatários explícitos, passou e não apresenta esse defeito.

O [parecer consolidado em E06-01](../E06-01/review.md) registra fontes, matriz das sete fatias, classificação, referências, passos de reprodução, limites e código completo das provas independentes. Suíte completa: **1772 passed**. Provas adicionais: **7 failed, 8 passed** (as falhas confirmam R01 a R04). Ruff, formatação, mypy e verificação de migrações passaram. Não houve alteração de produção nem de testes versionados pelo revisor.

Os registros do implementador abaixo são preservados como evidência histórica; não substituem o veredito independente acima. As correções e o gate de processo R05 exigem nova avaliação antes do encerramento da E06.

---

## Registro anterior preservado

# E06-06 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§4.4, 5.1, 5.2, 6.3, 7, 12), infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E03-07, E04-01, E04-02, E05-02, E05-04 e E06-05.

## Arquivos

- `apps/rodadas/fechamento.py`: a verificação do mínimo em `encerrar_fechamento`, `voltar_para_interesse`, `MOTIVOS_DE_RETORNO` e o código `fora_de_fechamento_encerrado`.
- `apps/rodadas/avisos.py`: `avisar_retorno_para_interesse` e a função pública `compradores_com_reserva` (antes privada).
- `tests/apoio/ciclos.py`: `simular_volta_para_interesse` agora usa a transição real (A-10); `tests/apoio/interesses.py` não mudou nesta fatia.
- Testes: `tests/tecnicos/test_rodadas_fechamento_retorno.py` (A-1 a A-9 e A-11) e, em `test_rodadas_fechamento_concorrencia.py`, A-12. Nenhuma migração.

## Ciclo TDD

**Andaime (exceção técnica):** `voltar_para_interesse` e `avisar_retorno_para_interesse` sem comportamento, `MOTIVOS_DE_RETORNO` e a mensagem do código novo.

**Red (inclui a concorrência, antes do código).** `uv run pytest tests/tecnicos/test_rodadas_fechamento_retorno.py -q`: **12 failed, 1 passed**, por asserção (`assert 'fechamento_encerrado' == Etapa.INTERESSE`, `DID NOT RAISE TransicaoRecusada/ValueError/RuntimeError/TransactionManagementError`, e `KeyError: 'valor_elegivel'` na auditoria do A-1). O A-12 (`test_adicao_que_espera_o_encerramento_entra_na_rodada_de_volta_ao_interesse`) falhou por asserção contra o andaime. Passou já no Red o A-4 (queda e recuperação do mínimo), porque o resultado esperado é o mesmo do andaime.

**Green.** Retorno, encerramento e concorrência: **39 passed**. Suíte completa: **1752 passed** (eram 1738). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- `encerrar_fechamento` lê os participantes antes dos excedentes, calcula `progresso_da_rodada(...).atingido` depois deles, chama `voltar_para_interesse` quando não atingido e só então grava a auditoria `rodada.encerrar_fechamento`, com `valor_elegivel`, `minimo` e `resultado`.
- `voltar_para_interesse` exige transação e motivo válido, trava fornecedor e rodada (reentrante), grava `interesse`, audita (SISTEMA), atende a fila (`alocar_pendentes`) e avisa os destinatários (por padrão, quem tem reserva agora).

## Ajuste autorizado nos testes existentes

`simular_volta_para_interesse` (`tests/apoio/ciclos.py`): `update(etapa=fechamento_encerrado)` seguido de `voltar_para_interesse(rodada, motivo="minimo_nao_atingido")`, numa transação. `test_rodadas_ciclos.py` não mudou e segue verde.

**Ajuste em teste meu da fatia anterior:** `test_uma_rodada_com_falha_nao_impede_as_outras` (E06-05 A-10) usava o mínimo padrão do fornecedor e, com a verificação nova, as rodadas voltariam para interesse. A spec da E06-05 parte de fornecedor **sem mínimo** ("F tem mínimo R$ 0,00"); o teste agora chama `sem_minimo(rodada)` em cada rodada. Só preparação, nenhuma asserção mudou.

## Decisões técnicas

- Os testes de preço e mínimo atualizam o `Fornecedor` por `update()` antes do início do fechamento, porque depois ele fica congelado.
- Nos testes de concorrência o relógio é o `monkeypatch` de `agora` em `apps.rodadas.fechamento`, fixo no prazo.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_minimo_atingido_aguarda_o_pagamento` (`acceptance`, cenário 9 suficiente) |
| A-2 | `test_minimo_nao_atingido_volta_para_interesse` (`acceptance`, cenário 9 insuficiente) |
| A-3 | `test_reducao_de_preco_so_derruba_no_fim_do_prazo` |
| A-4 | `test_a_queda_e_a_recuperacao_do_minimo_nao_mexem_no_prazo` (`acceptance`, cenário 5) |
| A-5 | `test_depois_do_retorno_as_condicoes_voltam_a_ser_editaveis` (`acceptance`, cenário 73) |
| A-6 | `test_o_estoque_liberado_vai_para_a_fila_no_retorno` |
| A-7 | `test_novo_fechamento_depois_do_retorno_gera_novo_ciclo` |
| A-8 | `test_so_o_fechamento_encerrado_volta_para_interesse` |
| A-9 | `test_motivo_desconhecido_e_erro`, `test_voltar_para_interesse_exige_transacao` |
| A-10 | `tests/tecnicos/test_rodadas_ciclos.py` (17 passed) |
| A-11 | `test_falha_no_aviso_de_retorno_desfaz_o_encerramento` |
| A-12 | `test_adicao_que_espera_o_encerramento_entra_na_rodada_de_volta_ao_interesse` |

## Limites da verificação

Postgres real, sem navegador. O retorno por pagamentos insuficientes (E11), a abertura do pagamento (E08) e as telas (E06-07) são de outras fatias. Nenhuma mutação foi aplicada nesta fatia.
