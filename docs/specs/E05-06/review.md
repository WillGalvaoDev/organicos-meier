# E05-06 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E03-03, E04-01, E04-02 e E05-01.

## Arquivos

- `apps/interesses/avisos.py` (novo): `avisar_preco_alterado`, conectado em `apps/interesses/apps.py` com `dispatch_uid`.
- `apps/catalogo/servicos.py` (`editar_produto`) e `apps/catalogo/sinais.py`: o argumento `alteracao` no sinal `preco_alterado`.
- Teste: `tests/tecnicos/test_interesses_preco.py` (A-1 a A-9). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** `avisar_preco_alterado` com a assinatura final e corpo vazio, ainda sem conexão ao sinal.

**Red.** `uv run pytest tests/tecnicos/test_interesses_preco.py -q`: **7 failed, 2 passed**, por asserção (`assert 0 == 1` nos avisos, `assert [] == ['preco_alterado:...']`, `DID NOT RAISE RuntimeError`, e a ausência de `alteracao` no sinal). Passaram já no Red o A-5 (parcela `em_pedido`) e o A-6 (edição só de descrição e produto sem parcelas), porque dependem de ausência. Antes do Green troquei, nos testes A-8 e A-9, um desempacotamento e um acesso por chave por asserções explícitas, para a falha do Red ser por asserção.

**Green.** Mesmo arquivo: **9 passed**. Suíte completa: **1603 passed** (eram 1594). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

## Decisões técnicas

- O receptor usa uma consulta agregada (`values("comprador_id").annotate(Sum(...))`, ordenada por conta) mais uma leitura em lote das contas; emite com `emitir_evento` uma vez por comprador, porque o conteúdo é diferente para cada um.
- Os subtotais do aviso usam `calcular_subtotal(preco, reservado total)`; o corpo usa o filtro `reais` e `formatar_quantidade`, exatamente como a spec.
- `editar_produto` guarda o retorno de `registrar_auditoria("produto.alterar_preco")` e o passa no sinal. Os receptores existentes da E03-03 já aceitam argumentos extras (`**kw`).
- A-3 foi exercitado com o aviso real emitido por `editar_produto` seguido de duas chamadas diretas ao receptor com a mesma entrada de auditoria, dentro de uma transação.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_so_quem_tem_reserva_e_avisado` |
| A-2 | `test_cada_alteracao_gera_o_seu_aviso` |
| A-3 | `test_mesmo_fato_nao_duplica` |
| A-4 | `test_preco_alterado_no_fechamento_atinge_o_carrinho` (`acceptance`, cenário 72) |
| A-5 | `test_parcela_em_pedido_nao_e_avisada` |
| A-6 | `test_sem_parcelas_e_edicao_so_de_descricao_nao_avisam` |
| A-7 | `test_falha_na_emissao_desfaz_a_alteracao` |
| A-8 | `test_titulo_cortado_em_150_caracteres` |
| A-9 | `test_o_sinal_leva_a_entrada_de_auditoria` |

## Limites da verificação

Cliente HTTP do Django e Postgres reais, sem navegador. O aviso é só no site (matriz da E04-01). O retorno ao interesse quando o valor elegível cai abaixo do mínimo é da E06.
