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
