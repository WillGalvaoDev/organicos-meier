# E16-07 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Execução:** `pytest tests/rastreabilidade/`. Os casos negativos usam matrizes de teste montadas no próprio teste e passadas à função de conferência, que é reaproveitável.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regras 1 e 3 | positivo | a matriz entregue | conferir | as chaves de `CENARIOS` são exatamente 1 a 119 e as de `TECNICOS` exatamente `T-1` a `T-55`; todas as listas não vazias; todas as referências válidas. **Red esperado:** o módulo não existe |
| A-2 | Regra 3 | negativo | uma matriz de teste sem o cenário 42; com um cenário 120; com `T-56` | conferir | falha citando 42 como faltante, 120 como sobrando e `T-56` como sobrando |
| A-3 | Regra 3 | negativo | referências para um arquivo inexistente, para uma função que não existe no arquivo e para uma função que não começa com `test_` | conferir | falha citando cada referência e o motivo |
| A-4 | Regra 3 | negativo | uma referência para um teste com `@pytest.mark.skip` | conferir | falha citando a referência |
| A-5 | Regra 3 | negativo | uma lista com a mesma referência duas vezes | conferir | falha citando a duplicata |
| A-6 | Regra 3 | positivo | uma referência `arquivo::TestClasse::test_metodo` existente | conferir | aceita |
| A-7 | Regra 4 | positivo | a matriz entregue | `python -m tests.rastreabilidade.gerar` num diretório temporário | o documento com as duas tabelas; a linha do cenário 6 com o resumo começando por "Produto de R$ 10,00, múltiplo 12 e 18 unidades"; a linha de `T-12` com a regra `A3` |
| A-8 | Regra 4 | negativo | o documento versionado alterado à mão (uma linha a menos) | rodar o teste | falha dizendo que o documento está desatualizado |
| A-9 | Regra 4 | negativo | uma matriz de teste com o cenário 999 | gerar | erro citando 999 sem texto nos documentos-base |
| A-10 | Regra 5 | positivo | o `review.md` da fatia | ler | a lista das lacunas encontradas e dos testes novos, com o resultado da primeira execução de cada um. Sem lacuna, a frase "Nenhuma lacuna: todos os cenários e testes técnicos já tinham teste." |
| A-11 | Regra 2 | positivo | a matriz entregue | o revisor confere uma amostra de pelo menos 20 cenários e 10 testes técnicos, incluindo 113, 116, 117, T-12 e T-17 | cada teste citado exercita e confere o comportamento descrito. Critério de revisão, com o resultado registrado no parecer |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-9 | `tests/rastreabilidade/test_matriz.py` |
| A-10 e A-11 | `docs/specs/E16-07/review.md` (registro do implementador e parecer do revisor) |
