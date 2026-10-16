# E03-03 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Telas testadas com o administrador autenticado por passkey (dublê da E02-03). Rodadas em etapas posteriores a `interesse` são criadas pela `RodadaFactory`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §4.2 | positivo | um fornecedor | o administrador cadastra "Banana" em `kg`, incremento `0,25`, preço `7,99`, múltiplo vazio | produto gravado com `Decimal("0.250")`, `Decimal("7.99")` e múltiplo nulo; auditoria `produto.criar` |
| A-2 | Cenário 110, T-50, R-8 | positivo | `validar_incremento` | chamo com `"1"`, `"2"`, `"0.25"`, `"0.5"` e `"0.001"` | os `Decimal` correspondentes |
| A-3 | Cenários 86, 110, T-38, T-50 | negativo | `validar_incremento` e o formulário de cadastro | entrada `"0"`, `"-1"`, `"0.0001"`, `"abc"`, `0.25` (`float`) e `1` (`int`) | `IncrementoInvalido` no serviço e erro no campo pela tela, em cada caso; nenhum produto criado |
| A-4 | Cenários 87, 111, R-2, T-26, T-38 | positivo | o cadastro | (a) múltiplo 1 com incremento 0,25; (b) 12 com 2 | aceito nos dois |
| A-5 | Cenários 66, 87, 111, R-2, T-26, T-38 | negativo | o cadastro | (a) múltiplo 1 com incremento 0,3; (b) 5 com 2; (c) múltiplo 0; (d) múltiplo -12 | `MultiploInvalido`; erro no campo; nada criado |
| A-6 | Cenários 63, 85, 109, T-26, T-38 | positivo | produtos da tabela de casos-limite da spec | chamo `validar_quantidade` com cada valor da coluna "Aceito" e com 1,5 kg no produto de incremento 0,5 | o `Decimal` correspondente em cada caso |
| A-7 | Cenários 63, 85, 109, T-26, T-38 | negativo | os mesmos produtos | chamo `validar_quantidade` com cada valor da coluna "Recusado", com 1,2 nos produtos de incremento 0,5, com `0`, `-1`, `"0.2501"` e com `float` | `QuantidadeInvalida` (ou `QuantidadeRecusada`) em cada caso |
| A-8 | Cenários 63, 64, T-26, §9 | positivo | `calcular_subtotal` | chamo com `(12.00, 1.5)`, `(12.99, 0.35)`, `(7.99, 0.25)` e `(2.50, 0.25)`, todos em `Decimal` | `18.00`, `4.55` (455 centavos), `2.00` e `0.63` |
| A-9 | Infra 4.12 | negativo | `calcular_subtotal` | chamo com `float` em qualquer argumento | `ValorInvalido` |
| A-10 | Spec da fatia | negativo | o banco | `UPDATE` direto de `incremento` para 0; de `preco` para 0; de `multiplo` para 1 com incremento 0,3 | o banco recusa os três (`CHECK`) |
| A-11 | Spec da fatia | negativo | um produto | `UPDATE` direto de `unidade` e de `fornecedor_id`; `DELETE` direto | o banco recusa os três (trigger) |
| A-12 | Spec da fatia | negativo | um produto em `kg` | `POST` de edição geral com `unidade=unidade`, `fornecedor=<outro>` e `incremento=1`, além de um nome novo | o nome muda; unidade, fornecedor e incremento não mudam |
| A-13 | Spec §5.1, cenário 72 | positivo | um produto com a rodada do fornecedor em `interesse`, `fechamento` e `pagamento`, um caso por etapa, e um receptor de teste de `preco_alterado` | o administrador muda o preço de `10,00` para `12,50` | preço gravado; auditoria `produto.alterar_preco` com `anterior "10.00"` e `novo "12.50"`; o receptor é chamado uma vez dentro da transação |
| A-14 | Spec da fatia | negativo | um receptor de `preco_alterado` que levanta erro | mudo o preço | preço inalterado; nenhuma auditoria |
| A-15 | Spec da fatia | positivo | um produto | edito só a descrição | o receptor de `preco_alterado` não é chamado; auditoria `produto.editar` com `campos == ["descricao"]` |
| A-16 | Spec §4.2, cenário 87 | positivo | um produto com incremento 0,25, múltiplo 1 e a rodada em `interesse` | altero o múltiplo para 2 e depois o removo (vazio) | múltiplo `2.000` e depois nulo; duas auditorias `produto.alterar_multiplo` |
| A-17 | Cenário 87, R-2 | negativo | o mesmo produto em `interesse` | altero o múltiplo para `0,9` | erro de formulário; múltiplo inalterado; nenhuma auditoria |
| A-18 | Cenários 72, 87, T-23 | negativo | o mesmo produto com a rodada em `fechamento`, `fechamento_encerrado`, `pagamento` e `aguardando_fornecedor`, e sem rodada ativa | altero o múltiplo pela rota e pelo serviço | 409 com a mensagem única; `CondicoesCongeladas`; múltiplo inalterado; nenhuma auditoria |
| A-19 | Spec da fatia | positivo | a rodada do fornecedor em `fechamento` | cadastro um produto novo | aceito; o produto não está no estoque de nenhuma rodada |
| A-20 | Spec §4.2 | positivo | um produto | marco `disponivel=False` | gravado, com auditoria `produto.editar` com `campos == ["disponivel"]`; nenhuma outra tabela alterada |
| A-21 | Spec da fatia | concorrência | um produto com preço 10,00 | duas edições de preço em paralelo (11,00 e 12,00), repetidas 10 vezes | em todas: duas auditorias `produto.alterar_preco`, e o `anterior` da segunda é o `novo` da primeira |
| A-22 | Spec §2, §15 | negativo | um comprador e uma conta de fornecedor autenticados; um visitante anônimo | `GET` e `POST` em cada rota desta fatia | 403 para os autenticados; anônimo redirecionado para `/entrar/`; nada criado nem alterado |
| A-23 | Spec da fatia | positivo | produtos com quantidades `0.250`, `1.000` e `1.500` | exibo na tela | `0,25`, `1` e `1,5` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-2 a A-9 | `tests/tecnicos/test_catalogo_quantidades.py` (marcador `tecnico`, com os comentários `T-26`, `T-38`, `T-50`) |
| A-1, A-10 a A-12, A-19, A-20, A-23 | `tests/tecnicos/test_catalogo_produtos.py` |
| A-13 a A-18 | `tests/tecnicos/test_catalogo_condicoes.py` |
| A-21 | `tests/tecnicos/test_catalogo_concorrencia.py` (marcador `concorrencia`) |
| A-22 | `tests/tecnicos/test_catalogo_permissoes.py` |
| A-6, A-7 (cenários 63, 85, 109); A-3 (86, 110); A-4, A-5 (66, 87, 111); A-13 (72); A-18 (72, 87) | também marcados `acceptance`, com os números no comentário |
