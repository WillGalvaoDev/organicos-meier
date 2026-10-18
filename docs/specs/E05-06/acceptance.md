# E05-06 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). O produto `P` é do fornecedor `X`, em kg, com incremento 0,25 e preço R$ 7,99. A rodada está em `interesse`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §5.1, §12 | positivo | A com parcelas de 0,25 e 0,5 de `P`; B com 1; C só com uma parcela `pendente` de 1; D sem parcela | `editar_produto(admin, P, preco="8.99")` | uma notificação `preco_alterado` para A e uma para B; nenhuma para C nem D; nenhum `Envio` (só site); o título de A é "Preço alterado: P"; o corpo de A é "O preço de P mudou de R$ 7,99 para R$ 8,99 por kg. Seu interesse reservado de 0,75 kg passa de R$ 5,99 para R$ 6,74."; link `/carrinho/` |
| A-2 | Spec da fatia | positivo | o estado do A-1 | altero o preço para R$ 9,99 | um segundo aviso para A e outro para B, com chaves diferentes das do A-1 (`preco_alterado:<id da auditoria>:<conta>`) |
| A-3 | E04-02 | positivo | a mesma entrada de auditoria e a mesma conta | chamo o receptor duas vezes com o mesmo `alteracao` | uma única notificação |
| A-4 | Cenário 72 | positivo | rodada em `fechamento`; A com 1 kg | altero o preço e A abre `/carrinho/` | o aviso emitido; "Subtotal: R$ 8,99" na linha de `P` |
| A-5 | Spec §5.1 | negativo | A com uma parcela `em_pedido` de `P`, e nenhuma outra | altero o preço | nenhuma notificação |
| A-6 | Spec da fatia | negativo | `P` sem parcelas | altero só a descrição; depois altero o preço | nenhuma notificação nos dois casos; o sinal não é enviado na edição só de descrição |
| A-7 | Spec da fatia | negativo | A com 1 kg; um `monkeypatch` faz `emitir_evento` levantar `RuntimeError` | `editar_produto(admin, P, preco="8.99")` | a exceção chega a quem chamou; o preço continua R$ 7,99; nenhuma auditoria `produto.alterar_preco`; nenhuma notificação |
| A-8 | Spec da fatia | positivo | A com 1 kg; produto de R$ 10,00 com nome de 150 caracteres e unidade `unidade` | altero o preço | o título tem 150 caracteres; a notificação é gravada sem `NotificacaoInvalida` |
| A-9 | Spec da fatia | positivo | — | inspeciono a chamada de `preco_alterado.send` com um receptor de teste | os argumentos `produto`, `anterior`, `novo` e `alteracao`, em que `alteracao` é a `EntradaAuditoria` com ação `produto.alterar_preco` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-9 | `tests/tecnicos/test_interesses_preco.py` |
| A-4 | também marcado `acceptance`, com o comentário `cenário 72` |
