# E03-03 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** app `apps.catalogo` (modelo `Produto` só com campos,
`Unidade`), funções e exceções de `quantidades.py` com corpo trivial, serviços, formulário, views
e filtro de template vazios, rotas, `ProdutoFactory`, migração `0001_initial`. Suíte antes do Red:
739 passando.

**Red** (`uv run pytest tests/tecnicos/test_catalogo_*.py`): **110 falhas, 10 passando**, todas as
falhas por asserção sobre comportamento ausente (valores devolvidos, `DID NOT RAISE`,
`200 == 302/409`, auditoria `0 == 1`, contexto de formulário ausente, banco sem restrição).
As 10 que já passavam são guardas: 403/redirecionamento das permissões (rotas do andaime já usam
`somente_administrador`), hierarquia das exceções, as cinco unidades, `validar_multiplo` vazio
(stub devolve `None`), preço igual sem auditoria, e dois testes de banco que só afirmam que o
`UPDATE` comum e o múltiplo divisível continuam permitidos (regressão das restrições).

**Green:** `models.py` (CHECKs `produto_incremento_positivo`, `produto_preco_minimo`,
`produto_multiplo_divisivel`), migração `0002_restricoes` (CHECKs + triggers de imutabilidade
de `fornecedor_id`/`unidade` e de exclusão, `imutavel.py`), `quantidades.py`, `servicos.py`,
`forms.py`, `views.py`, templates, filtro `quantidade_br`, lista de produtos no detalhe do
fornecedor. Resultado: `test_catalogo_*.py` 120 passando; suíte completa **860 passando**;
`ruff check`, `ruff format`, `mypy --strict`, `makemigrations --check` limpos.

**Ajustes durante o Green (erros do meu teste, não do código):** `test_edicao_invalida_nao_grava`
esperava erros de `nome` e `preco` juntos, mas o formulário só chama o serviço quando passa; o
teste foi dividido em dois casos (nome vazio; preço `0`), mantendo as mesmas garantias (200, erro
no campo, nada gravado, sem auditoria). Dois erros de lint/tipos (RUF002, atributo reverso) e
`FieldError` do CHECK (faltava `output_field`) foram corrigidos no código.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_catalogo_produtos.py::test_cadastro_grava_valores_exatos_e_audita` |
| A-2 | `test_catalogo_quantidades.py::test_incrementos_validos` |
| A-3 | `::test_incrementos_invalidos_no_servico`, `::test_incremento_invalido_na_tela`, `::test_criar_produto_recusa_incremento_float_ou_int` |
| A-4 | `::test_multiplo_valido_no_cadastro`, `::test_validar_multiplo_aceita_e_aceita_vazio` |
| A-5 | `::test_multiplo_invalido_no_cadastro`, `::test_servico_recusa_multiplo_invalido`, `::test_validar_multiplo_recusa` |
| A-6, A-7 | `::test_quantidades_aceitas`, `::test_quantidades_recusadas` (tabela da §4.2 e cenários 63/85/109) |
| A-8, A-9 | `::test_subtotal_com_um_unico_arredondamento`, `::test_subtotal_de_455_centavos`, `::test_subtotal_recusa_float_e_int` |
| A-10, A-11 | `test_catalogo_produtos.py::test_banco_recusa_valores_invalidos`, `::test_banco_recusa_troca_de_unidade_e_de_fornecedor_e_exclusao` |
| A-12 | `::test_edicao_ignora_unidade_fornecedor_e_incremento` |
| A-13 | `test_catalogo_condicoes.py::test_preco_muda_em_qualquer_etapa` (interesse, fechamento, pagamento) |
| A-14, A-15 | `::test_receptor_que_falha_desfaz_a_edicao_do_preco`, `::test_editar_so_a_descricao_nao_avisa_preco` |
| A-16, A-17 | `::test_alterar_e_remover_o_multiplo`, `::test_multiplo_invalido_em_interesse` |
| A-18 | `::test_multiplo_congelado_pela_rota_e_pelo_servico` (4 etapas congeladas, sem rodada, rodada terminada) |
| A-19, A-20 | `test_catalogo_produtos.py::test_produto_novo_com_rodada_em_fechamento_e_aceito`, `::test_marcar_indisponivel_so_grava_o_produto` |
| A-21 | `test_catalogo_concorrencia.py::test_duas_edicoes_de_preco_ficam_em_serie` (×10) |
| A-22 | `test_catalogo_permissoes.py` |
| A-23 | `test_catalogo_produtos.py::test_detalhe_do_fornecedor_lista_produtos_com_quantidades_formatadas`, `::test_edicao_mostra_quantidades_formatadas`, `test_catalogo_quantidades.py::test_formatacao_de_quantidade` |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- `criar_produto` levanta `IncrementoInvalido`/`MultiploInvalido` diretamente (nessa ordem) e
  `ValidationError` por campo para nome, descrição, unidade e preço; a tela converte tudo em erro
  de campo.
- `editar_produto(autor, produto, **campos)` aceita só `nome`, `descricao`, `preco`,
  `disponivel`; qualquer outro nome levanta `ValidationError`.
- O CHECK do múltiplo usa `MOD(multiplo, NULLIF(incremento, 0))` para não dar divisão por zero;
  `incremento > 0` tem restrição própria.
- Triggers: `BEFORE UPDATE ... WHEN (OLD IS DISTINCT FROM NEW)` deixa passar o `save()` comum do
  ORM, que reenvia as colunas com o mesmo valor; `BEFORE DELETE` recusa qualquer exclusão. O
  `flush` (TRUNCATE) dos testes de transação não dispara trigger de linha.
- Após cadastro, edição e alteração do múltiplo, a tela volta ao detalhe do fornecedor (onde a
  lista de produtos aparece); a especificação não define o destino.
- A edição geral usa a caixa "disponível" do HTML: ausente no `POST` significa `False`.
- Disponibilidade (D-1): só é gravada e exibida na lista de produtos; nenhuma outra regra a lê
  nesta fatia.

## Limitações de verificação

- A-19 prova que o cadastro é aceito com a rodada em `fechamento` e que a rodada não muda; "não
  está no estoque de nenhuma rodada" não é verificável aqui porque o estoque por rodada só existe
  na E03-05.
- Notificação e recálculo após `preco_alterado` são da E05; aqui só o sinal é provado.
- Telas verificadas pelo cliente de teste do Django, não por navegador.
