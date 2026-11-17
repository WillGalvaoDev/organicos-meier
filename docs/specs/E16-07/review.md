# E16-07 — Registro do implementador

Agente 2.

## Red (observado antes do código)

`uv run pytest -q tests/rastreabilidade`: erro de coleta, `ImportError: cannot import name 'matriz' from 'tests.rastreabilidade'` (o módulo da matriz, a conferência e o gerador não existiam; cobre A-1 a A-9).

## Green

- `tests/rastreabilidade/conferencia.py`: `conferir(cenarios, tecnicos, raiz)` devolve os problemas: chaves faltando ou sobrando, lista vazia, referência fora do formato, arquivo inexistente, função inexistente, função que não começa com `test_`, teste pulado (`skip`, `skipif` com condição constante verdadeira, `pytestmark` do módulo, classe) e referência repetida. Lê a árvore de sintaxe (`ast`); não importa nem roda nada. `conferir_documento` compara o documento versionado com o que o gerador produz agora.
- `tests/rastreabilidade/gerar.py` (`python -m tests.rastreabilidade.gerar [--saida CAMINHO]`): lê o texto de cada cenário (§16) e a regra de cada teste técnico (infraestrutura 8) na hora; um número sem texto levanta `ValueError`. O resumo tem até 100 caracteres (corta em 97 e acrescenta `...`).
- `tests/rastreabilidade/matriz.py`: 119 cenários (348 referências) e 55 testes técnicos (210 referências); `docs/rastreabilidade-fase1.md` gerado.
- `tests/rastreabilidade/test_matriz.py` (9 testes): **9 passed**.

## Como a matriz foi montada (para o revisor)

1. Levantamento automático fora do repositório: para cada `acceptance.md` das E01 a E14, as colunas "Origem" que citam "Cenário N" ou "T-N" foram cruzadas com os testes que levam o comentário `# A-n` nos arquivos listados na tabela de arquivos de cada especificação. As especificações E15-07 e E16 ficaram de fora porque usam numeração própria de cenários.
2. Cada item (174) foi revisado lendo o texto do cenário ao lado dos nomes dos testes candidatos; foram mantidos os de peso maior ou igual a 0,25 (no máximo 8 por item) e acrescentados à mão os que faltavam (`tests/aceitacao/test_cenario_29..34`, `test_cenarios_35_36_excepcional`, `test_cenarios_90_91_112_117_reembolso`, `test_cenarios_18_48_49_52_ocorrencias`, e alguns testes de T-20, T-28, T-33, T-40, T-41 e T-47, de 12, 55, 77 e 79).
3. Li o corpo dos testes da amostra do A-11 que o especificador citou: **113** (`test_cenario_113_quatro_parciais_somam_o_pago`, valores 2,00/2,00/2,00/1,99 e acumulado 7,99), **117** (quatro `Reembolso` separados e o item sem mudança, mais o `ItemReembolsado` com item, quantidade e valor do E10-02 A-1), **T-12** (web e worker não sobem em produção com o simulador) e **T-17** (`save`, `delete`, `update` e `delete` em lote recusados em cada modelo do pedido congelado). Não li o corpo dos demais: o revisor deve conferir a amostra dele.

## Lacunas (A-10)

Nenhuma outra, além de uma encontrada:

| Cenário | Lacuna | Teste novo | Resultado da primeira execução |
|---|---|---|---|
| 116 | Os testes existentes provavam a proporcionalidade com outros números (25,00/1,25/5,00). Nenhum conferia os números do cenário: parcial de R$ 2,00 → R$ 0,10 de serviço e R$ 0,40 de frete, num pedido de R$ 100,00/5,00/20,00. | `tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario` | **Passou** (1 passed). Teste de caracterização: o comportamento já existia (E10-02). **Exceção técnica justificada** (AGENTS.md §3), sem Red. |

Nenhum teste novo falhou: não há defeito a devolver ao especificador.

## Decisões e pontos para o revisor

1. **Módulo da conferência:** `tests/rastreabilidade/conferencia.py` (a spec não fixa o nome). O gerador recebe `--saida` para escrever fora de `docs/` (A-7).
2. **Documento gerado:** as colunas são `Cenário | Resumo | Testes` e `ID | Regra | Testes`; os testes de cada linha vão separados por `<br>`.
3. **Fidelidade da matriz:** o critério é "o teste exercita e confere o comportamento descrito" (regra 2). A seleção por nome e por critério citado é um filtro, não prova de cobertura integral de cada afirmação de cenários longos (por exemplo, 12, 19, 43, 67). Onde o cenário tem várias afirmações, a lista traz mais de um teste, mas o revisor deve conferir a amostra.
4. **Nenhum código de produção mudou.** Foram só `tests/rastreabilidade/`, o teste de caracterização e o documento gerado.

## Verificação

`uv run pytest -q tests/rastreabilidade tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py`: verde. Todas as 558 referências existem e nenhuma está pulada (conferido pelo teste A-1). `ruff` e `mypy` (554 arquivos) limpos. Suíte completa no fim da E16. Sem push, PR nem merge.
