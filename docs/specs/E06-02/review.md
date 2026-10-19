# E06-02 — Revalidação independente — 2026-10-19

**Veredito desta fatia: APROVADO. Veredito final da E06: APROVADO sobre `e9434666368c517683020e13fceb8395cb5412e2`.**

Branch examinada: `e06-correcoes-especificacao`. A-1 a A-8: aprovação mantida; regressão dos avisos sem achados.

O [parecer consolidado](../E06-01/review.md) contém a matriz atualizada, encerramento de R01 a R05, análise dos registros de TDD, autorização do tratamento de R05, comandos, resultados e reprodução das mutações. Verificação independente: **1791 testes aprovados**, **15 provas originais aprovadas**, Ruff/formatação/mypy/migrações sem erros. Nenhum achado permanece aberto. A aprovação é desta versão; não declara que a branch foi integrada na main.

Este parecer substitui o veredito anterior para a versão examinada. O histórico abaixo permanece íntegro. Apenas documentos de revisão foram alterados pelo revisor.

---

## Histórico preservado — parecer anterior e registros

# E06-02 — Revisão independente — 2026-10-19

**Veredito desta fatia: APROVADO. Veredito global da E06: REPROVADO.**

Base: `main`, commit `2fbf143d082b37a1e8333a0736a310008e10e9ad`. A-1 a A-8: avisos do início, canais, destinatários, unicidade e atomicidade verificados. Nenhum achado local aberto.

O [parecer consolidado em E06-01](../E06-01/review.md) registra fontes, matriz das sete fatias, classificação, referências, passos de reprodução, limites e código completo das provas independentes. Suíte completa: **1772 passed**. Provas adicionais: **7 failed, 8 passed** (as falhas confirmam R01 a R04). Ruff, formatação, mypy e verificação de migrações passaram. Não houve alteração de produção nem de testes versionados pelo revisor.

Os registros do implementador abaixo são preservados como evidência histórica; não substituem o veredito independente acima. As correções e o gate de processo R05 exigem nova avaliação antes do encerramento da E06.

---

## Registro anterior preservado

# E06-02 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E04-01, E04-02, E05-R03 e E06-01.

## Arquivos

- `apps/rodadas/avisos.py` (novo): `avisar_fechamento_iniciado(rodada, ciclo, termina_em)`.
- `apps/rodadas/fechamento.py`: a chamada dentro de `iniciar_fechamento`, depois da auditoria.
- Testes: `tests/tecnicos/test_rodadas_fechamento_aviso.py` (A-1 a A-7) e, em `test_rodadas_fechamento_concorrencia.py`, o A-8. Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** `avisar_fechamento_iniciado` sem corpo, já chamada por `iniciar_fechamento`.

**Red (inclui a concorrência, antes do código).** `uv run pytest tests/tecnicos/test_rodadas_fechamento_aviso.py tests/tecnicos/test_rodadas_fechamento_concorrencia.py -k aviso -q`: **7 failed**, por asserção: `assert 0 == 1` e `assert [] == [7, 8]` (nenhum aviso emitido), `DID NOT RAISE RuntimeError` (A-4) e `assert [] == ['fechamento_iniciado:7:15']` (A-6). O A-8 (concorrência) também falhou por asserção, porque nenhum aviso era emitido. Passou já no Red o A-5 (mínimo zero, sem destinatários), por depender de ausência.

**Green.** `avisos.py` lê os compradores com parcela `ativa` e reserva num produto do estoque da rodada (consulta agregada, por id) e chama `emitir_evento_para_varios` com título, corpo e link da spec e `chave_base = fechamento_iniciado:<ciclo>`. Os três arquivos de fechamento: **28 passed**. Suíte completa: **1694 passed** (eram 1686). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

**A-8 e a trava.** Nenhuma trava nova foi escrita nesta fatia: a conta do comprador já é travada com `FOR NO KEY UPDATE` (E05-R03), e a emissão do aviso só pede `FOR KEY SHARE` na conta, compatível com ela. O teste fixa a intercalação como a spec descreve (a pausa fica dentro do serviço real do comprador, em `_travar_conta`; a transação do início trava o fornecedor e espera a barreira) e conferiu que as duas operações terminam, A recebe o aviso e a adição fica gravada já no fechamento.

## Decisões técnicas

- Destinatários: o mesmo conjunto que forma o valor elegível (parcelas `ativa` com reserva). Pendentes, suspensos, administrador e fornecedor não recebem.
- A data e a hora saem de `no_fuso_da_operacao(termina_em)`, nos formatos `%d/%m/%Y` e `%H:%M`.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_so_quem_tem_reserva_na_rodada_recebe_o_aviso` (`acceptance`) |
| A-2 | `test_envios_de_email_e_whatsapp_seguem_a_matriz` |
| A-3 | `test_varias_parcelas_e_produtos_geram_um_aviso` |
| A-4 | `test_falha_na_emissao_desfaz_o_inicio` |
| A-5 | `test_sem_destinatarios_nao_emite_nada` |
| A-6 | `test_novo_ciclo_gera_novo_aviso` (usa `simular_volta_para_interesse`) |
| A-7 | `test_titulo_cortado_em_150_caracteres` |
| A-8 | `test_aviso_do_inicio_nao_trava_com_a_conta_do_comprador_segura` |

## Limites da verificação

Serviços e Postgres reais, sem navegador. O envio efetivo por e-mail e WhatsApp é da E04-03 e da E04-04. Nenhuma mutação foi aplicada nesta fatia.
