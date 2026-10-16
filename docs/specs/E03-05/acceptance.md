# E03-05 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As parcelas são criadas pela `ParcelaFactory` (E03-04). Rodadas em etapas posteriores a `interesse` são criadas pela `RodadaFactory`. Os testes de concorrência usam `django_db(transaction=True)`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §4.3 | positivo | uma rodada em `interesse` e dois produtos do fornecedor | o administrador inclui um com limite `10` e o outro sem limite | dois `EstoqueDaRodada`, com `10.000` e nulo; duas auditorias `estoque.incluir`; a tela mostra "sem limite" no segundo |
| A-2 | Spec §4.3 | positivo | um fornecedor com uma rodada `disponivel_para_retirada` que tinha estoque de `X`, e uma rodada nova em `interesse` | consulto o estoque da rodada nova | nenhum produto incluído; o estoque da rodada antiga não mudou |
| A-3 | Spec §4.3 | negativo | um produto do fornecedor `G` e a rodada do fornecedor `F` | incluo pelo serviço; noutro teste, insiro por SQL direto | `ValidationError` pelo serviço; o banco recusa pela trigger |
| A-4 | Spec da fatia | negativo | um produto já incluído | incluo de novo | `ValidationError` com a mensagem; um único registro |
| A-5 | Cenário 71 | positivo | limite 10 e parcelas `ativa` com 6 reservados no total | altero para `8` e depois para `6` | aceito nos dois; auditorias `estoque.alterar` com `anterior` e `novo` corretos |
| A-6 | Cenário 71, T-23 | negativo | o mesmo estoque com 6 reservados | altero para `5` | `EstoqueAbaixoDoReservado`, com a mensagem citando `6`; limite inalterado; nenhuma auditoria; nenhum sinal |
| A-7 | Cenário 71 | negativo | estoque sem limite com 6 reservados | altero para `4` | `EstoqueAbaixoDoReservado`; continua sem limite |
| A-8 | Spec da fatia | positivo | estoque com limite 10 | altero para sem limite | aceito; sinal com `anterior=10` e `novo=None` |
| A-9 | Cenário 72, T-23 | negativo | rodada em `fechamento`, `fechamento_encerrado`, `pagamento` e `aguardando_fornecedor`, um caso por etapa | incluo um produto e altero um estoque, pela rota e pelo serviço | 409 com a mensagem única pela rota; `CondicoesCongeladas` pelo serviço; nada gravado; nenhuma auditoria |
| A-10 | Spec da fatia | negativo | uma rodada antiga `disponivel_para_retirada` e o mesmo fornecedor com rodada nova em `interesse` | altero o estoque da rodada antiga | `CondicoesCongeladas`; nada gravado |
| A-11 | Spec da fatia | positivo | um receptor de teste de `estoque_alterado` | incluo um produto e depois altero o estoque | o receptor é chamado duas vezes, dentro da transação, com `anterior` e `novo` corretos |
| A-12 | Spec da fatia | negativo | um receptor de `estoque_alterado` que levanta erro | altero o estoque | limite inalterado; nenhuma auditoria |
| A-13 | Spec da fatia | positivo | limite 10, 6 reservados; e um produto sem limite | chamo `estoque_livre` | `4.000` e `None` |
| A-14 | Spec da fatia | negativo | o banco | `UPDATE` direto de `limite` para `-1`; de `produto_id`; `DELETE` | o banco recusa os três |
| A-15 | Spec §4.4 | concorrência | rodada em `interesse` | uma thread trava fornecedor e rodada, grava `fechamento` e só confirma depois de ver a outra conexão esperando por trava; `alterar_estoque` corre em outra thread | `CondicoesCongeladas`; limite inalterado |
| A-16 | Spec §4.4, Infra 4.10 | concorrência | limite 10, 6 reservados | uma thread simula uma reserva: trava fornecedor, rodada, produto e estoque, sobe a reserva de uma parcela para chegar a 8 reservados no total e só confirma depois de ver `alterar_estoque(7)` esperando por trava | `EstoqueAbaixoDoReservado`; limite 10; total reservado 8 |
| A-17 | Spec da fatia | concorrência | um produto fora da rodada | duas inclusões em paralelo, repetidas 10 vezes | em todas: um único `EstoqueDaRodada`; uma inclusão com sucesso e a outra recusada |
| A-18 | Spec §2, §15 | negativo | um comprador e uma conta de fornecedor autenticados; um visitante anônimo | `GET` da tela e `POST` de incluir e de alterar | 403 para os autenticados; anônimo redirecionado para `/entrar/`; nada gravado |
| A-19 | Spec da fatia | positivo | rodada em `fechamento` | abro a tela de estoque | 200, só leitura, sem formulários |
| A-20 | E03-R01 | negativo e limite | rodada em `interesse`, dois produtos do fornecedor fora da rodada e um receptor de teste em `estoque_alterado` | `incluir_produto_na_rodada` com limite `999999999.999` para o primeiro; com `1000000000.000` para o segundo, pelo serviço e pela rota | o primeiro é incluído; o segundo levanta `ValidationError` com "O valor máximo aceito é 999999999,999."; a rota responde 200 com a mensagem; o segundo continua fora da rodada; nenhuma auditoria nem sinal da recusa |
| A-21 | E03-R01 | negativo e limite | um estoque com limite 10 e o receptor do A-20 | `alterar_estoque` com `999999999.999`; depois, com `1000000000.000` pelo serviço e pela rota | o primeiro é aceito, auditado e sinalizado; o segundo é recusado com a mensagem de capacidade; a rota responde 200; o limite continua `999999999.999`; nenhuma auditoria nem sinal da recusa |
| A-22 | E03-R03 | negativo | um estoque com limite 10 e um produto fora da rodada; a rodada em `fechamento` e, noutro caso, uma rodada antiga (`disponivel_para_retirada`) com o fornecedor já em outra rodada em `interesse`; um receptor de teste em `estoque_alterado` | `incluir_produto_na_rodada` e `alterar_estoque` com `Decimal("1000000000.000")`, `Decimal("-1")` e `"abc"` | `CondicoesCongeladas` em todos, nunca `ValidationError`; nenhum estoque novo; limite 10; nenhuma auditoria nem sinal |
| A-23 | E03-R04 | negativo | rodada em `interesse` com os produtos `P` e `Q` fora da rodada e um receptor de teste em `estoque_alterado` | incluo `P` com `1000000000,000`, depois com `-1` e depois com `abc` | 200 nos três; dentro do `<form>` de inclusão de `P`: `value` com o texto enviado e a mensagem da recusa correspondente; o `<form>` de `Q` sem `value` preenchido e sem mensagem; `P` continua fora da rodada; nenhuma auditoria nem sinal |
| A-24 | E03-R04 | negativo | rodada em `interesse` com os estoques `E1` (limite 10, 6 reservados) e `E2` (limite 7); o receptor do A-23 | altero `E1` com `1000000000,000`, depois com `5` (abaixo do reservado) e depois com `abc` | 200 nos três; dentro do `<form>` de alteração de `E1`: `value` com o texto enviado e a mensagem correspondente, inclusive "O estoque não pode ficar abaixo da quantidade já reservada (6)."; a coluna de limite de `E1` continua 10; o `<form>` de `E2` com `value="7"` e sem mensagem; nenhuma auditoria nem sinal. Com o limite `"><b>x</b>`, a resposta traz o texto escapado (`&quot;&gt;&lt;b&gt;`) e nenhum `<b>x</b>` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-14, A-19 | `tests/tecnicos/test_rodadas_estoque.py` |
| A-15 a A-17 | `tests/tecnicos/test_rodadas_estoque_concorrencia.py` (marcador `concorrencia`) |
| A-18 | `tests/tecnicos/test_rodadas_permissoes.py` |
| A-5 a A-7 (cenário 71); A-9 (cenário 72, T-23) | também marcados `acceptance` e `tecnico`, com os números no comentário |
| A-20, A-21 | `tests/tecnicos/test_capacidade_decimal.py` (marcador `tecnico`) |
| A-22 | `tests/tecnicos/test_rodadas_estoque.py` |
| A-23, A-24 | `tests/tecnicos/test_rodadas_estoque.py`, com o probe `test_estoque_preserva_entrada_rejeitada` do revisor incluído literalmente |
