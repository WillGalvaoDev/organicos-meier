# E03-02 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** app `apps.rodadas` (modelo `Rodada` só com campos,
`Etapa`, `ETAPAS_ATIVAS`, sinal), stubs de `abrir_rodada`, `travar_condicoes`, `alterar_minimo`,
views vazias, rotas, `RodadaFactory`, migração `0001_initial`. Suíte antes do Red: 702 passando.

**Red** (`uv run pytest tests/tecnicos/test_rodadas_*.py`): **34 falhas, 3 passando**. Todas as
falhas são de asserção sobre comportamento ausente: `DID NOT RAISE RodadaAtivaExistente` (5),
`DID NOT RAISE CondicoesCongeladas` (4), `assert 200 == 409` (5), `assert 200 == 302` (3),
`DID NOT RAISE IntegrityError` (índice), `DID NOT RAISE RuntimeError` (receptor),
`DID NOT RAISE TransactionManagementError`, `DID NOT RAISE PermissionDenied`,
`DID NOT RAISE ValidationError`, `assert None is not None`, auditoria `0 == 1`/`0 == 2`, e
concorrência sem efeito. As 3 que já passavam são guardas de regressão: 403/redirecionamento de
`test_rodadas_permissoes.py` (as rotas do andaime já usam `somente_administrador`).
Ajustes de teste durante o Red (erros do teste, não do código): A-3 tinha asserção fraca (passava
no stub) e foi reforçada (`pk is not None`, duas rodadas); o teste A-10 criava um segundo
administrador (há um único por restrição do banco).

**Green:** `rodada_ativa_unica_por_fornecedor` (índice único parcial, migração `0002_restricoes`);
`travar_condicoes`; `abrir_rodada`; `alterar_minimo`; views `abrir` e `minimo`; formulário
`FormularioMinimo`; templates. Resultado: `test_rodadas_*.py` 37 passando; suíte completa
**739 passando**; `ruff check`, `ruff format`, `mypy --strict` e `makemigrations --check` limpos.

**Refactor:** apenas `constraints` como tupla (RUF012) após o Green; suíte verde.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_rodadas_abertura.py::test_abertura_cria_rodada_em_interesse_e_audita` |
| A-2 | `::test_recusa_quando_ja_ha_rodada_ativa` (5 etapas), `::test_recusa_pela_rota_mostra_a_mensagem` |
| A-3 | `::test_abre_quando_a_ultima_rodada_terminou` |
| A-4 | `::test_banco_recusa_segunda_rodada_ativa` |
| A-5 | `test_rodadas_concorrencia.py::test_duas_aberturas_simultaneas_geram_uma_rodada` (×10) |
| A-6, A-7 | `test_rodadas_abertura.py::test_receptor_que_falha_desfaz_a_abertura`, `::test_receptor_e_chamado_uma_vez_dentro_da_transacao` |
| A-8 (cenário 71) | `test_rodadas_minimo.py::test_altera_o_minimo_em_interesse_e_audita` |
| A-9 (cenário 72, T-23) | `::test_minimo_congelado_pela_rota`, `::test_minimo_congelado_pelo_servico` |
| A-10 | `::test_sem_rodada_ativa_recusa_pela_rota_e_pelo_servico` |
| A-11 | `::test_minimo_invalido_e_erro_de_formulario`, `::test_servico_recusa_valor_invalido` |
| A-12, A-13 | `::test_mesmo_valor_nao_grava_nem_audita`, `::test_get_fora_de_interesse_mostra_mensagem_sem_formulario` |
| A-14 | `test_rodadas_concorrencia.py::test_alteracao_do_minimo_espera_a_mudanca_de_etapa` |
| A-15 | `::test_duas_alteracoes_simultaneas_ficam_em_serie` |
| A-16 | `test_rodadas_abertura.py::test_travar_condicoes_fora_de_transacao_falha` (`transaction=True`) |
| A-17 | `test_rodadas_permissoes.py` |
| A-18 | `test_rodadas_minimo.py::test_comprador_nao_pode_ser_autor` |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- `abrir_rodada` trava só o fornecedor (e não precisa travar rodada: a checagem de rodada ativa
  ocorre sob a trava do fornecedor); o índice parcial é a defesa final. Ordem global mantida:
  fornecedor → rodada.
- `travar_condicoes` detecta transação por `connection.in_atomic_block`.
- `alterar_minimo` valida o valor antes de abrir a transação (erro de valor tem precedência sobre
  fase só quando o valor é inválido); depois trava e relê.
- A auditoria grava o mínimo como texto decimal (`str(Decimal)`, duas casas).
- `abrir` aceita só `POST` (`require_POST`, depois do controle de administrador).
- A tela do mínimo preenche o campo com o valor atual (vírgula decimal) e mostra a mensagem
  única, sem formulário, quando não há rodada em `interesse` (GET) ou o serviço recusa (POST, 409).

## Limitações de verificação

- A-14 usa `pg_stat_activity.wait_event_type = 'Lock'` em todo o banco de teste; outro processo
  esperando por trava no mesmo banco poderia liberar a espera cedo (não ocorre na suíte).
- Não há transições de etapa nesta fatia: etapas posteriores são criadas pela fábrica.
- Não executei navegador; as telas foram verificadas pelo cliente de teste do Django.
