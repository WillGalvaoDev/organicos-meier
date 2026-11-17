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


---

## Revisão independente — agente 3 — 2026-11-17

Base avaliada: `52f8745870ebfa007ad6a94edf7f968ae472d04e`, branch
`e16-especificacoes`, diff contra `02f8e91`. Requisitos lidos antes do código:
AGENTS.md, especificação funcional v1.7, infraestrutura v1.8 e as oito specs e
acceptances da E16. Registros do implementador acima preservados integralmente.
A evidência global de execução está no parecer da E16-08 abaixo.

**Veredito da fatia: REPROVADO.**

### E16-R05 — Importante — matriz não comprova todas as afirmações

Referências: E16-07 regra 2 e A-11; `tests/rastreabilidade/matriz.py:18` (cenário 2)
e entrada `T-40`; funcional §16 cenário 2, infraestrutura §8 T-40.

Amostra independente: leitura do corpo de todas as referências dos **20 cenários**
1, 2, 3, 4, 6, 14, 24, 35, 45, 55, 65, 75, 85, 95, 105, 110, 113, 116, 117 e 119;
e dos **10 técnicos** T-1, T-4, T-8, T-12, T-17, T-24, T-30, T-40, T-50 e T-55.
Incluídos os cinco obrigatórios, com leitura de seus asserts; 113 comprova
2,00/2,00/2,00/1,99, 116 os números 2,00/0,10/0,40 e o acumulado, 117 os registros
separados e item preservado, T-12 a recusa de inicialização e T-17 a trigger e rotas.

Contraexemplos reproduzíveis por leitura das listas e dos corpos:

- Cenário 2 tem só `test_banido_ou_removido_nao_entra_pelo_google` e
  `test_banimento_ou_remocao_depois_do_pedido_bloqueia_o_uso`. Ambos cobrem banimento/
  remoção, não convite nem a preservação das restrições de suspensão. Existem testes
  de acesso sem conta e de conta suspensa em outros pontos, mas não estão na lista.
  A suspensão permite entrar para acompanhar pedidos: a prova necessária é que o
  login não contorne suas restrições, não que todo login seja proibido.
- T-40 pede **reembolso integral após mudar o preço**. A lista aponta para
  `test_integral_devolve_o_restante_de_cada_item_e_componente` (não muda preço) e
  `test_o_valor_vem_do_registrado_e_nao_do_catalogo` (muda preço, mas só reembolsa
  0,25 de 1,00). Nenhum exerce o integral após a mudança. Isso identifica uma lacuna
  de evidência da matriz, não afirma um defeito no cálculo financeiro.

Portanto A-11 não é atendido. Nomes de funções e comentários A-n não substituem as
asserções. Retorno: conferir semanticamente as 174 entradas e todas as afirmações,
completar referências existentes ou testes de caracterização onde necessário e
regenerar o documento. O novo teste 116 é uma caracterização justificada, permitida
pela regra 5; não exige a exceção de TDD concedida apenas ao commit da E15.

### E16-R06 — Importante — conferência aceita referências não executáveis no CI

Referências: E16-07 regra 3, A-1/A-3/A-4/A-6;
`tests/rastreabilidade/conferencia.py:26` e `:49`.

Prova independente em diretório temporário com `tests/test_exemplo.py`, passando a
referência para `_conferir_referencia(raiz, referencia)`. Nos três casos abaixo o
resultado foi `None` (aceito):

```python
class ForaDaColeta:
    def test_exemplo(self): pass
# referência: tests/test_exemplo.py::ForaDaColeta::test_exemplo
```

```python
import pytest
@pytest.mark.skipif(condition=True, reason="sempre")
def test_exemplo(): pass
# referência: tests/test_exemplo.py::test_exemplo
```

```python
import os, pytest
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="no CI")
def test_exemplo(): pass
# mesma referência; condição verdadeira no GitHub Actions
```

O contrato exige classe `Test*` e recusa de `skipif` sempre verdadeiro no CI.
O parser não valida prefixo da classe e só examina argumento posicional constante
do skipif. Retorno: cobrir esses negativos no validador AST, sem importar/executar
código arbitrário dos arquivos. Não se afirma que esses três exemplos estejam na
matriz atual; é a guarda requerida pela fatia que os aceita indevidamente.

A-2/A-5/A-7/A-8/A-9 têm cobertura coerente de chaves, duplicatas e documento gerado.
A-10 registra a caracterização 116, mas o levantamento de lacunas precisa ser
complementado por R05. O relato admite seleção heurística e leitura de apenas quatro
corpos: não sustenta cobertura integral. Registros TDD preservados.
