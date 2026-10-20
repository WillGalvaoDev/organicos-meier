# E08-01 — Registro do implementador (2026-10-20)

Status: implementada; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: `spec.md` e `acceptance.md` desta fatia, AGENTS.md e as regras de prevenção da E05-R04 e da E06-R05.

## Arquivos

- `apps/pedidos/` (app novo, em `INSTALLED_APPS`): `apps.py` e `calculo.py` (`ItemACobrar`, `CompradorACobrar`, `ItemCobrado`, `CobrancaDoComprador`, `TAXA_DE_SERVICO`, `calcular_cobranca`). Sem modelos.
- `tests/apoio/varredura_float.py` (código de teste): varredura pela árvore de sintaxe.
- `tests/tecnicos/test_pedidos_calculo.py` (A-1 a A-10 e A-12) e `tests/tecnicos/test_varredura_float.py` (A-11).

## Andaime (exceção técnica)

Antes do Red: o app `apps.pedidos` (sem comportamento), a assinatura e os tipos de `calcular_cobranca` com corpo que devolve lista vazia, e `varrer_arquivo` que devolve lista vazia. Não há comportamento testável nesse andaime; ele só deixa os testes importáveis, para a falha ser por asserção.

## Red (arquivos inteiros, sem `-k`)

`uv run pytest tests/tecnicos/test_pedidos_calculo.py tests/tecnicos/test_varredura_float.py -q`: **27 failed, 3 passed**.

| Critério | Teste | Resultado no Red |
|---|---|---|
| A-1 | `test_cobranca_rateia_o_frete_pelos_produtos` | falhou: `ValueError: not enough values to unpack` (o resultado era a lista vazia) |
| A-2 | `test_subtotal_arredondado_por_item` | falhou: o resultado era a lista vazia (desempacotamento) |
| A-3 | `test_produtos_soma_os_subtotais_ja_arredondados` | falhou: o resultado era a lista vazia (desempacotamento) |
| A-4 | `test_subtotal_e_arredondado_uma_vez_so` | falhou: o resultado era a lista vazia (desempacotamento) |
| A-5 | `test_centavo_do_frete_vai_ao_menor_comprador_no_empate` | falhou: `[] != [3.34, 3.33, 3.33]` |
| A-6 | `test_frete_pelo_maior_resto` | falhou: `[] != [0.00, 0.00, 0.05]` |
| A-7 | `test_resultado_nao_depende_da_ordem_da_entrada` | falhou: `assert []` |
| A-8, A-9 | `test_frete_zero`, `test_servico_arredonda_meio_centavo_para_cima` | falharam: o resultado era a lista vazia (asserção ou desempacotamento) |
| A-10 | `test_frete_invalido_e_recusado` (7), `test_preco_invalido_e_recusado`, `test_quantidade_invalida_e_recusada` (4), `test_quantidade_float_e_recusada`, `test_estruturas_invalidas_sao_recusadas` | falharam: `DID NOT RAISE ValueError` |
| A-12 | `test_cobranca_aleatoria_respeita_as_invariantes` | falhou: `assert 0 == 19` (comprimento do resultado) |
| A-11 | `test_a_varredura_acusa_float_com_arquivo_e_linha` | falhou: `assert [] == [(1, 'literal float'), ...]` |
| A-11 | `test_modulos_de_dinheiro_nao_usam_float`, `test_a_varredura_cobre_os_modulos_e_ignora_as_migracoes`, `test_a_varredura_nao_acusa_inteiros_decimais_nem_anotacoes` | **passaram no Red**: controles. Com a varredura vazia os módulos "estão limpos" por definição, e a cobertura da lista de arquivos não depende da varredura. Protegem contra regressão; a prova positiva de que a varredura enxerga `float` é o teste do arquivo temporário, que falhou. |

## Green e verificações

- Os dois arquivos: **30 passed**.
- `ruff check`, `ruff format --check` e `mypy .` sem erros. A varredura nova não encontrou `float` nos oito conjuntos de módulos do A-11.
- A suíte completa é rodada ao final da milestone e registrada na última fatia.

## Decisões técnicas

- O maior resto é calculado em `Decimal` exato (`frete * P / T` sem arredondamento intermediário); o truncamento usa `ROUND_DOWN` a centavos, e o desempate é por `comprador_id`.
- Os validadores de preço, quantidade e frete exigem `Decimal` (nunca `float` nem `bool`) e recusam excesso de casas sem arredondar.
- A semente do A-12 é `20261102`; `random.Random` leva `noqa: S311` porque é teste com semente fixa.

## Limites da verificação

Função pura: sem banco, rede ou navegador. Nenhuma mutação aplicada.
