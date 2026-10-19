# E07-01 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§8.1, 15), infraestrutura v1.7 (4.1 a 4.5, 7, 9.2), `spec.md` e `acceptance.md` da fatia, E04-04 (precedente do simulador de WhatsApp) e AGENTS.md §§3, 6 e 7.

## Arquivos

- `apps/pagamentos/` (app novo, sem modelos nesta fatia): `provedor.py` com `SituacaoNoProvedor`, `NovaCobranca` (validação local), `PagamentoConsultado`, `CobrancaCriada`, `AvisoDoProvedor`, os quatro erros, o protocolo `Provedor` e `obter_provedor()`.
- `apps/simulador_pagamentos/` (app novo): `models.py` (`CobrancaSimulada`, `AvisoSimulado`) e `migrations/0001_initial.py`; `provedor.py` (`ProvedorSimulado`); `estado.py` (leitura e mudança do estado, assinatura, log); `plano.py` (plano de falhas no processo); `controle.py` (os controles dos testes).
- `config/settings/base.py` (dois apps em `INSTALLED_APPS`; `SEGREDO_AVISOS_SIMULADOR` lido do ambiente, sem padrão), `dev.py` e `test.py` (valor padrão só neles).
- `tests/conftest.py`: fixture `simulador_pagamentos` (reinicia o plano antes e depois do teste).
- Testes: `tests/tecnicos/test_pagamentos_simulador.py` (A-1 a A-14, A-17, A-18), `test_pagamentos_concorrencia.py` (A-15), `test_pagamentos_fronteiras.py` (A-16).

## Ciclo TDD

**Andaime (exceção técnica, sem comportamento testável):** os tipos, os erros, o protocolo, as duas tabelas com a migração, `obter_provedor()` e métodos neutros no simulador e nos controles (devolvem valores vazios; `reiniciar` zera o plano). Nenhuma validação, regra de idempotência nem aviso existia antes dos testes.

### Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pagamentos_simulador.py tests/tecnicos/test_pagamentos_concorrencia.py tests/tecnicos/test_pagamentos_fronteiras.py -q`: **35 failed, 2 passed**. Todas as falhas são por asserção (`DID NOT RAISE ...`, `assert 0 == 3`, `assert [] == [...]`, `assert <pendente> == <aprovado>`). Uma primeira leitura teve falhas por `ValueError`/`IndexError` ao desempacotar listas vazias nas preparações; as preparações foram tornadas assertivas (`assert len(...) == 3`) antes do Green e o Red acima é o da segunda leitura, anterior a todo código de produção.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_criar_cobranca_devolve_o_pagamento_pendente` | falhou (`assert False` em `id_externo.startswith("sim-")`) |
| A-2 | `test_a_mesma_chave_devolve_a_mesma_cobranca` | falhou (`assert 0 == 1` linhas) |
| A-3 | `test_pedido_invalido_e_recusado_antes_do_provedor` (10 casos), `test_expiracao_que_nao_e_futura_e_recusada` | falharam (`DID NOT RAISE` nos 10; `DID NOT RAISE RecusaDoProvedor`) |
| A-4 | `test_aprovacao_informada_depois` | falhou (`assert 0 == 1` avisos) |
| A-5 | `test_aprovacao_depois_do_vencimento_ou_do_cancelamento`, `test_recusar_e_expirar_so_a_partir_de_pendente` | falharam (`pendente == aprovado`; `DID NOT RAISE ValueError`) |
| A-6 | `test_cancelar_so_muda_a_pendente` | falhou (`pendente == cancelado`) |
| A-7 | `test_cancelamento_que_coincide_com_o_pagamento` | falhou (`pendente == aprovado`) |
| A-8 | `test_buscar_por_referencia` | falhou (`assert [] == ['', '']`) |
| A-9 | `test_identificador_desconhecido` | falhou (`DID NOT RAISE PagamentoNaoEncontrado`) |
| A-10 | `test_provedor_indisponivel` | falhou (`DID NOT RAISE ProvedorIndisponivel`) |
| A-11 | os três testes `tempo_esgotado...`, `falha_antes...`, `falhar_proximas_de_outra...` | falharam (`assert 0 == 1`, `DID NOT RAISE ProvedorIndisponivel`) |
| A-12 | `test_atraso_de_consistencia`, `..._vale_tambem_para_a_busca` | falharam (`pendente == aprovado`; `[] == [pendente]`) |
| A-13 | `test_avisos_atrasados_repetidos_fora_de_ordem_e_perdidos`, `test_avisos_pendentes_na_ordem_de_criacao`, `test_reemitir_aviso_nao_muda_a_situacao` | falharam (`assert 0 == 3` na preparação dos três avisos; `assert 0 == 2`) |
| A-14 | `test_verificacao_do_aviso`, `test_corpo_que_nao_e_json_com_assinatura_valida_e_invalido`, `test_verificacao_aceita_cabecalho_em_qualquer_caixa` | falharam (`DID NOT RAISE AvisoInvalido`; `assert 0 == 3`) |
| A-15 | `test_a_mesma_chave_em_duas_conexoes_cria_uma_cobranca_so` | falhou por asserção contra o andaime (Red anterior ao código de produção) |
| A-16 | `test_so_a_interface_e_o_proprio_simulador_importam_o_simulador`, `test_o_simulador_nao_importa_modelos_de_pagamentos` | **passaram no Red**: é propriedade de estrutura que o andaime já cumpria (só `apps/pagamentos/provedor.py` importa o simulador; ele não importa modelos de pagamentos); protegem contra regressão |
| A-17 | `test_o_log_nao_leva_dado_do_pedido` | falhou (`assert []`: nenhuma mensagem de operação) |
| A-18 | `test_a_mesma_sequencia_da_o_mesmo_resultado` | falhou (a primeira sequência já difere do esperado) |

### Green

Os três arquivos: **37 passed**. Suíte completa: **1828 passed** (eram 1791). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Decisões técnicas (derivadas da spec)

- **Identificadores derivados da chave primária.** `id_externo` (`sim-<pk>`) e `id_evento` (`sim-ev-<pk>`) são propriedades da chave sequencial, e não colunas: assim são sequenciais, únicos e livres de corrida, sem segunda gravação. `sim-` seguido de algo que não seja o inteiro canônico é desconhecido (`PagamentoNaoEncontrado`).
- **Idempotência.** Primeiro a leitura da chave; sem ela, a inserção dentro de um savepoint; em `IntegrityError` (outra conexão criou a mesma chave), relê a existente. "Mesmos dados" compara referência, valor, descrição, meio e `expira_em`. A chave existente é devolvida mesmo que o `expira_em` já tenha passado (a repetição de uma criação antiga não vira `expiracao_invalida`).
- **Plano no processo, incluindo o atraso de consistência.** O plano guarda a situação anterior à última mudança (gravada em toda mudança) e as consultas atrasadas restantes; a consulta consome uma só quando há situação anterior para mostrar. A criação e o cancelamento devolvem sempre o estado real do provedor.
- **`aprovar_no_cancelamento`** é guardado no plano (processo), como o resto dos controles de teste; sem `em`, aprova em `agora()` no cancelamento. `em` anterior a `criado_em` é `ValueError` já na chamada.
- **Controles de situação** não passam pelo plano de falhas; só as cinco operações da interface passam.
- **`entregar_avisos`:** o receptor é um parâmetro obrigatório até a E07-05; sem ele, `RuntimeError`. O contador `entregas` sobe depois de cada chamada ao receptor.
- **Segredo sem padrão em `base.py`;** o simulador recusa assinar ou verificar com segredo vazio (`RuntimeError`). A decisão para `prod.py` é da E07-02.
- **Log:** `"Simulador de pagamentos: <operação> <id_externo>"` em `apps.simulador_pagamentos`; a busca por referência não registra a referência.

## Conflito do critério A-4 com a regra de `em`

O A-4 aprova a "cobrança do A-1" (criada às 13:00) com `em` = 12:59:30, mas a regra de `aprovar` e o A-5 mandam `ValueError` quando `em` é anterior a `criado_em`. O teste cria a cobrança às 12:50 e aprova em 12:59:30 com o relógio em 13:10, que preserva o que o critério quer provar (aprovação informada depois, com `em` no passado, `consultado_em` 13:10). Registro para o especificador; nenhum teste foi enfraquecido.

## Mapeamento dos critérios

Ver a tabela do Red: cada critério tem os testes listados, todos no `test_pagamentos_simulador.py`, exceto A-15 (`test_pagamentos_concorrencia.py`) e A-16 (`test_pagamentos_fronteiras.py`). Os marcadores `acceptance` ficam no A-1.

## Limites da verificação

Postgres real, sem rede. O simulador não foi exercitado por um worker como processo separado. A mutação não foi aplicada nesta fatia. Os receptores dos avisos (E07-05), o registro dos pagamentos (E07-03) e a configuração por ambiente (E07-02) são de outras fatias.
