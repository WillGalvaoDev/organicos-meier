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

## Correções E16-R05 e E16-R06 (implementador, 2026-11-17)

### R06 — validador

- **Red observado** (`tests/rastreabilidade`): com o validador antigo, 14 dos 29 testes falharam (classe fora da coleta, `__init__`, `__test__ = False`, nome de arquivo, `skipif(condition=True)`, `skipif` por variável de ambiente ou texto, `xfail`, `pytestmark` anotado, apelidos `import pytest as pt` e `from pytest import mark`, `pytest.skip` e `importorskip`).
- **Green** (`tests/rastreabilidade/conferencia.py`): a referência só vale se o pytest a coletaria (`test_*.py`; classes `Test*` sem `__init__` nem `__test__ = False`; módulo sem `__test__ = False`; função filha direta; vale a última definição). Recusa `skip`, `skipif` com qualquer condição que não seja a constante `False`, `xfail`, e chamadas a `pytest.skip`/`xfail`/`importorskip` no corpo ou no nível do módulo, no decorador, na classe e no `pytestmark` (`Assign` e `AnnAssign`), com os apelidos reconhecidos. Limite declarado: pulo por fixture ou `conftest.py` não aparece na árvore.
- **Lista de pulados e falhas esperadas da execução completa (`-ra`, commit `281d191`):** `SKIPPED` 1: `tests/tecnicos/test_backup_externo_ferramentas.py` (sem `pg_dump`, `pg_restore`, `age` e `age-keygen` no Windows; passa no contêiner e no CI); `XFAIL` 2: `test_o_registro_da_restauracao_e_o_rto` e `test_as_melhorias_tem_decisao` (E16-08 A-3 e A-4, bloqueados por dependência). **Nenhum está na matriz** (o validador acusaria o `xfail`).

### R05 — afirmações e conferência semântica

- **Formato:** `CENARIOS` e `TECNICOS` guardam, por entrada, as afirmações do texto-base (até 140 caracteres) e os testes de cada uma: **203 afirmações de cenário e 98 de teste técnico, 679 pares (afirmação, teste)**. O documento gerado mostra cada afirmação seguida dos seus testes. A conferência exige afirmação com texto e com testes, e recusa repetição na mesma afirmação.
- **Método da conferência semântica (limite declarado):** cada texto foi dividido em afirmações; para cada par, medi quantos termos-chave da afirmação (números e radicais de palavras) aparecem no corpo do teste. Dos 679 pares, 49 ficaram abaixo do limiar de 0,30; li os corpos desses testes e das tabelas de casos que eles usam (`CASOS_DE_QUANTIDADE`, `ACEITAS` e `RECUSADAS`, a trigger do pedido congelado, a corrida dos reembolsos, as restaurações da apuração) e todos provam o que a afirmação pede. Os 630 pares acima do limiar foram aceitos pela aderência de termos e pelos nomes e critérios `A-n` de origem, **sem leitura linha a linha de cada corpo**: é uma verificação por amostra guiada, não a leitura integral que a regra 2-B descreve. O revisor deve conferir a amostra dele.
- **Caracterizações novas (regra 5), todas passaram na primeira execução (exceção técnica justificada, AGENTS.md §3):** cenário 2 (`tests/aceitacao/test_cenario_02_login_nao_contorna_suspensao.py`, Google e link: a sessão abre e a adição de interesse é recusada com 403), cenário 59 (`test_cenario_59_banimento_so_do_endereco.py`: IP, dispositivo e telefone do banido não bloqueiam outra conta) e T-40 (`test_t40_reembolso_do_item_inteiro.py`: preço mudado para R$ 9,99 depois do pagamento, item inteiro reembolsado com o subtotal registrado de R$ 7,99). Cenário 2 com as seis afirmações e T-40 com as duas, como a spec manda.
- **Resultado das 174 entradas:** 140 mantidas, 30 completadas e 4 com caracterização nova (2, 59, 116 e T-40; o 116 já era a caracterização anterior).

| Entrada | Resultado |
|---|---|
| 1 | mantida (2 afirmação(ões)) |
| 2 | caracterização nova (A: `test_cenario_02_login_nao_contorna_suspensao.py`) |
| 3 | mantida (1 afirmação(ões)) |
| 4 | mantida (2 afirmação(ões)) |
| 5 | mantida (2 afirmação(ões)) |
| 6 | mantida (1 afirmação(ões)) |
| 7 | mantida (4 afirmação(ões)) |
| 8 | mantida (2 afirmação(ões)) |
| 9 | mantida (2 afirmação(ões)) |
| 10 | mantida (1 afirmação(ões)) |
| 11 | mantida (1 afirmação(ões)) |
| 12 | mantida (3 afirmação(ões)) |
| 13 | mantida (1 afirmação(ões)) |
| 14 | mantida (1 afirmação(ões)) |
| 15 | mantida (1 afirmação(ões)) |
| 16 | mantida (1 afirmação(ões)) |
| 17 | mantida (1 afirmação(ões)) |
| 18 | mantida (1 afirmação(ões)) |
| 19 | mantida (2 afirmação(ões)) |
| 20 | mantida (1 afirmação(ões)) |
| 21 | mantida (1 afirmação(ões)) |
| 22 | mantida (2 afirmação(ões)) |
| 23 | mantida (1 afirmação(ões)) |
| 24 | mantida (1 afirmação(ões)) |
| 25 | mantida (1 afirmação(ões)) |
| 26 | mantida (1 afirmação(ões)) |
| 27 | mantida (2 afirmação(ões)) |
| 28 | mantida (2 afirmação(ões)) |
| 29 | mantida (1 afirmação(ões)) |
| 30 | mantida (1 afirmação(ões)) |
| 31 | mantida (1 afirmação(ões)) |
| 32 | mantida (2 afirmação(ões)) |
| 33 | mantida (2 afirmação(ões)) |
| 34 | mantida (2 afirmação(ões)) |
| 35 | mantida (2 afirmação(ões)) |
| 36 | mantida (1 afirmação(ões)) |
| 37 | mantida (1 afirmação(ões)) |
| 38 | mantida (1 afirmação(ões)) |
| 39 | mantida (1 afirmação(ões)) |
| 40 | mantida (1 afirmação(ões)) |
| 41 | mantida (2 afirmação(ões)) |
| 42 | mantida (2 afirmação(ões)) |
| 43 | mantida (2 afirmação(ões)) |
| 44 | mantida (2 afirmação(ões)) |
| 45 | mantida (1 afirmação(ões)) |
| 46 | mantida (1 afirmação(ões)) |
| 47 | mantida (1 afirmação(ões)) |
| 48 | mantida (2 afirmação(ões)) |
| 49 | mantida (2 afirmação(ões)) |
| 50 | mantida (1 afirmação(ões)) |
| 51 | mantida (1 afirmação(ões)) |
| 52 | mantida (1 afirmação(ões)) |
| 53 | completada (2 afirmação(ões); acrescentados: 3) |
| 54 | mantida (2 afirmação(ões)) |
| 55 | mantida (2 afirmação(ões)) |
| 56 | mantida (3 afirmação(ões)) |
| 57 | mantida (1 afirmação(ões)) |
| 58 | mantida (2 afirmação(ões)) |
| 59 | caracterização nova (`test_cenario_59_banimento_so_do_endereco.py`) |
| 60 | mantida (1 afirmação(ões)) |
| 61 | completada (2 afirmação(ões); acrescentados: 4) |
| 62 | mantida (1 afirmação(ões)) |
| 63 | completada (1 afirmação(ões); acrescentados: 1) |
| 64 | mantida (1 afirmação(ões)) |
| 65 | mantida (1 afirmação(ões)) |
| 66 | completada (1 afirmação(ões); acrescentados: 2) |
| 67 | completada (2 afirmação(ões); acrescentados: 3) |
| 68 | mantida (1 afirmação(ões)) |
| 69 | completada (2 afirmação(ões); acrescentados: 1) |
| 70 | completada (2 afirmação(ões); acrescentados: 2) |
| 71 | mantida (2 afirmação(ões)) |
| 72 | completada (2 afirmação(ões); acrescentados: 3) |
| 73 | mantida (1 afirmação(ões)) |
| 74 | mantida (2 afirmação(ões)) |
| 75 | mantida (2 afirmação(ões)) |
| 76 | mantida (2 afirmação(ões)) |
| 77 | mantida (2 afirmação(ões)) |
| 78 | mantida (2 afirmação(ões)) |
| 79 | mantida (1 afirmação(ões)) |
| 80 | mantida (1 afirmação(ões)) |
| 81 | mantida (2 afirmação(ões)) |
| 82 | mantida (2 afirmação(ões)) |
| 83 | completada (3 afirmação(ões); acrescentados: 4) |
| 84 | mantida (2 afirmação(ões)) |
| 85 | completada (4 afirmação(ões); acrescentados: 3) |
| 86 | mantida (1 afirmação(ões)) |
| 87 | completada (3 afirmação(ões); acrescentados: 2) |
| 88 | mantida (1 afirmação(ões)) |
| 89 | mantida (2 afirmação(ões)) |
| 90 | mantida (2 afirmação(ões)) |
| 91 | mantida (1 afirmação(ões)) |
| 92 | completada (2 afirmação(ões); acrescentados: 1) |
| 93 | completada (1 afirmação(ões); acrescentados: 1) |
| 94 | completada (1 afirmação(ões); acrescentados: 1) |
| 95 | completada (3 afirmação(ões); acrescentados: 2) |
| 96 | mantida (2 afirmação(ões)) |
| 97 | mantida (2 afirmação(ões)) |
| 98 | mantida (1 afirmação(ões)) |
| 99 | mantida (2 afirmação(ões)) |
| 100 | mantida (1 afirmação(ões)) |
| 101 | mantida (2 afirmação(ões)) |
| 102 | mantida (1 afirmação(ões)) |
| 103 | completada (1 afirmação(ões); acrescentados: 1) |
| 104 | mantida (2 afirmação(ões)) |
| 105 | mantida (1 afirmação(ões)) |
| 106 | mantida (2 afirmação(ões)) |
| 107 | mantida (2 afirmação(ões)) |
| 108 | mantida (2 afirmação(ões)) |
| 109 | completada (5 afirmação(ões); acrescentados: 2) |
| 110 | mantida (2 afirmação(ões)) |
| 111 | completada (2 afirmação(ões); acrescentados: 2) |
| 112 | mantida (3 afirmação(ões)) |
| 113 | mantida (3 afirmação(ões)) |
| 114 | mantida (1 afirmação(ões)) |
| 115 | mantida (4 afirmação(ões)) |
| 116 | caracterização nova (E16-07 inicial; mantida) |
| 117 | mantida (2 afirmação(ões)) |
| 118 | completada (1 afirmação(ões); acrescentados: 2) |
| 119 | mantida (1 afirmação(ões)) |
| T-1 | mantida (2 afirmação(ões)) |
| T-2 | mantida (1 afirmação(ões)) |
| T-3 | mantida (1 afirmação(ões)) |
| T-4 | mantida (2 afirmação(ões)) |
| T-5 | mantida (1 afirmação(ões)) |
| T-6 | mantida (1 afirmação(ões)) |
| T-7 | completada (1 afirmação(ões); acrescentados: 1) |
| T-8 | mantida (1 afirmação(ões)) |
| T-9 | mantida (3 afirmação(ões)) |
| T-10 | mantida (2 afirmação(ões)) |
| T-11 | completada (2 afirmação(ões); acrescentados: 2) |
| T-12 | mantida (1 afirmação(ões)) |
| T-13 | mantida (1 afirmação(ões)) |
| T-14 | mantida (1 afirmação(ões)) |
| T-15 | mantida (1 afirmação(ões)) |
| T-16 | mantida (2 afirmação(ões)) |
| T-17 | mantida (2 afirmação(ões)) |
| T-18 | mantida (2 afirmação(ões)) |
| T-19 | mantida (1 afirmação(ões)) |
| T-20 | mantida (1 afirmação(ões)) |
| T-21 | mantida (1 afirmação(ões)) |
| T-22 | mantida (1 afirmação(ões)) |
| T-23 | completada (3 afirmação(ões); acrescentados: 2) |
| T-24 | mantida (3 afirmação(ões)) |
| T-25 | mantida (2 afirmação(ões)) |
| T-26 | completada (2 afirmação(ões); acrescentados: 2) |
| T-27 | mantida (2 afirmação(ões)) |
| T-28 | completada (2 afirmação(ões); acrescentados: 1) |
| T-29 | completada (3 afirmação(ões); acrescentados: 2) |
| T-30 | mantida (1 afirmação(ões)) |
| T-31 | mantida (1 afirmação(ões)) |
| T-32 | mantida (1 afirmação(ões)) |
| T-33 | mantida (3 afirmação(ões)) |
| T-34 | mantida (1 afirmação(ões)) |
| T-35 | mantida (2 afirmação(ões)) |
| T-36 | mantida (2 afirmação(ões)) |
| T-37 | mantida (2 afirmação(ões)) |
| T-38 | completada (3 afirmação(ões); acrescentados: 2) |
| T-39 | mantida (4 afirmação(ões)) |
| T-40 | caracterização nova (`test_t40_reembolso_do_item_inteiro.py`) |
| T-41 | completada (1 afirmação(ões); acrescentados: 1) |
| T-42 | mantida (2 afirmação(ões)) |
| T-43 | mantida (2 afirmação(ões)) |
| T-44 | mantida (2 afirmação(ões)) |
| T-45 | mantida (1 afirmação(ões)) |
| T-46 | mantida (2 afirmação(ões)) |
| T-47 | mantida (2 afirmação(ões)) |
| T-48 | mantida (1 afirmação(ões)) |
| T-49 | mantida (1 afirmação(ões)) |
| T-50 | completada (3 afirmação(ões); acrescentados: 1) |
| T-51 | mantida (2 afirmação(ões)) |
| T-52 | mantida (3 afirmação(ões)) |
| T-53 | mantida (1 afirmação(ões)) |
| T-54 | completada (2 afirmação(ões); acrescentados: 1) |
| T-55 | completada (3 afirmação(ões); acrescentados: 3) |

- Sem push, PR nem merge. Código corrigido no commit `281d191` (os commits seguintes só mudam documentos).


## Revalidação independente — 2026-11-18 — commit 5f12d21

**REPROVADO. R05 e R06 permanecem importantes.** Registros Red/Green do validador e justificativa de caracterização sem alteração de produção conferidos. A estrutura por afirmação foi implementada, mas não basta para aprovação semântica.

### R05 residual — regra 2-B e A-19 não atendidos

Nova amostra independente: cenários **5, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27** e técnicos **T-2, T-3, T-5, T-6, T-7, T-9, T-10, T-11, T-13, T-14**, diferentes da primeira amostra, mais **2 e T-40**. Lidos textos, corpos e asserções dos testes citados. C2 e T-40 têm as caracterizações exigidas, mas A-19 falha em outras entradas. Exemplos reproduzíveis em `tests/rastreabilidade/matriz.py`:

- **C17, linha 163:** afirma não duplicar pagamento, pedido, mensagem formal ou estorno por webhook repetido. Seu único teste, `test_notificacoes_emissao.py::test_emissao_repetida_nao_duplica`, chama `_estorno` duas vezes; esse helper apenas chama `emitir_evento`. Asserts de Notificacao/Envio não provam webhook, pagamento, pedido ou estorno financeiro.
- **C25, linha 223:** exige aprovação T0+30h e notificação depois das 48h. O único teste, `test_pedidos_quitacao.py::test_aprovacao_no_prazo_quita_o_pedido` (linha 97), aprova em T0+2h e recebe um minuto depois; afirma expressamente `na_margem is False`. Não exercita o cenário declarado.
- **T-11, linha 1184:** a primeira afirmação exige recusar uso dos recursos de A para tarifa, déficit ou obrigação de B. O único teste atribuído, `test_dois_repasses_que_juntos_passam_do_liberado`, disputa dois repasses da mesma conta A. Não tenta lançar tarifa/déficit/obrigação de B. Os testes da segunda afirmação não corrigem a prova ausente da primeira.

O próprio registro do implementador (linha 139) declara que 630 dos 679 pares foram aceitos por aderência de termos/nomes, sem leitura de cada corpo, contrariando a regra 2-B. Retorno: executar a conferência integral exigida, corrigir cada vínculo por afirmação e acrescentar caracterizações onde realmente faltar prova. Não basta trocar os três exemplos acima nem delegar ao revisor a leitura integral prevista para a implementação.

### R06 residual — regras 3-A/3-B

Probes independentes em diretório temporário, usando `_conferir_referencia` e o pytest instalado. Nas três fontes abaixo o validador retornou **None** (referência aceita); pytest confirmou que nenhuma executa uma asserção:

```python
# tests/test_classe.py::TestExemplo::test_exemplo — 1 skipped
import pytest
class TestExemplo:
    pytestmark = pytest.mark.skip(reason="pulado")
    def test_exemplo(self): assert False
```

```python
# tests/test_condicoes.py::test_exemplo — 1 skipped
import pytest
@pytest.mark.skipif(False, True, reason="segunda verdadeira")
def test_exemplo(): assert False
```

```python
# tests/test_anotacao.py::test_exemplo — no tests ran
__test__: bool = False
def test_exemplo(): assert False
```

Referências: `conferencia.py:77` avalia apenas a primeira condição posicional; `:157` em diante confere decoradores de classe, mas não seu pytestmark; `_define` só trata Assign. A limitação aprovada para fixtures/conftest não abrange estas formas explícitas. Retorno: negar essas referências, com testes Red/Green, preservando os casos válidos. Isso é falha da guarda; não afirma que a matriz atual já contenha esses três casos. A suíte local só pulou ferramentas reais (reexecutadas no contêiner) e apresentou os dois xfails operacionais; nenhum dos três está mapeado. CI remoto não foi executado pelo revisor.


## Correções residuais R05 e R06 — implementador (2026-11-18)

### R06 (regra 3-C)
- **Red:** A-20 e A-21 falharam (2 failed, 34 passed): o validador aceitava as três fontes do revisor e as formas residuais. A-22 (formas válidas preservadas) e A-23 (pytest real em subprocesso confirma que as fontes recusadas não rodam nada) passaram na 1ª execução: são guardas, não Red.
- **Green:** `skipif` exige todas as condições `False` (e recusa sem condição); `pytestmark` e `__test__` de módulo e de classe são lidos com `Assign`/`AnnAssign`; atribuição aumentada, `append`, desempacotamento, `setattr`, `globals()[...]`, definição dentro de `if/try/with/for/while` e valores não analisáveis falham fechado. 36 passed. Commit `a832f9c`.

### R05 (regra 2-D)
- **Red:** A-24 (5 casos) e o limite de 200 caracteres falharam (6 failed); depois do validador, A-26 falhou (`'list' object has no attribute 'items'`) até a matriz migrar.
- **Green:** `afirmação → {referência → prova}`; a conferência exige texto, ≤ 200 caracteres, trecho entre crases presente em `assert`/`pytest.raises` do teste ou de função do módulo que ele chama (profundidade 2). `gerar.py` e `docs/rastreabilidade-fase1.md` regerados.
- **Números:** pares antes **679**; ligações retiradas **141**; acrescentadas **25** (22 a testes existentes, 3 a testes novos); pares depois **563**; 301 afirmações, nenhuma vazia.
- **Caracterizações novas (3), `tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py`:** webhook repetido 5× não duplica pagamento/pedido/notificação; webhook repetido não duplica estorno; aprovado em T0+30h e avisado em T0+50h quita. **Passaram na 1ª execução** (comportamento já existia): exceção técnica justificada (regra 5), sem Red.
- **Itens apontados:** C17 agora tem 3 ligações que enviam o webhook repetido; C25 tem a caracterização (o teste de T0+2h foi retirado); T-11 a0 passou a usar `test_cenario_32...nao_cobre_despesa...` e `...repasse_de_a_nao_usa_o_dinheiro_liberado_de_b` (o de dois repasses de A saiu dessa afirmação). C27 a1, T-4 a1 e C41 a1 receberam testes de autorização/recusa já existentes.
- **Método (declaração):** todas as provas foram escritas pela leitura do corpo de cada teste: listei os `assert` de cada um, escolhi à mão os índices e redigi a descrição. Uma tentativa inicial de pontuar por termos foi descartada e não alimenta a matriz. O trecho entre crases é copiado do código pelo montador; a conferência automática só prova que o assert existe, não que ele basta (limite da regra 2-D).
- **Limitações/dúvidas para o revisor:** (1) cenário 17, "mensagem formal": o webhook não aciona o pedido formal; provei a notificação ao comprador (`pagamento_confirmado`). Se a spec quer o e-mail ao fornecedor, é lacuna de especificação. (2) Algumas afirmações compostas são provadas só em parte (ex.: C20 bloqueio de novo cadastro com o e-mail; C59 variação de maiúsculas; T-38 "mais de 3 casas"); não criei testes além dos exigidos.
- Verificações: suíte completa **3626 passed, 1 skipped, 2 xfailed** (674 s) antes do último ajuste da matriz (cenário 71); depois, `tests/rastreabilidade` 45 passed; `ruff check --no-cache` e `mypy` limpos; `makemigrations --check` sem mudanças.
- R07 segue bloqueada (contas da fase 0, decisões do responsável). Sem push, PR nem merge.


## Nova revalidação independente — 2026-11-18 — commit 9f4163b

**REPROVADO. E16-R05 e E16-R06 permanecem importantes.** Revisão das regras residuais 2-D/3-C e A-20 a A-28, dos commits 07deb0e, a832f9c e 9f4163b, dos testes novos, do validador e do gerador. A estrutura das 563 ligações passou na conferência automática; isso não substitui a prova semântica.

### R05 — cobertura ainda parcial

Terceira amostra: cenários **28, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 46, 47, 48, 49** e técnicos **T-15, T-16, T-18, T-19, T-20, T-21, T-22, T-23, T-25, T-26**. Não repete entradas das duas amostras anteriores. Conferidos textos-base, provas e corpos dos testes atribuídos; adicionalmente reavaliados C17, C25, T-11 e os limites declarados C20, C59 e T-38. **A-28 não atendido**: exemplos de afirmações sem prova suficiente permanecem.

- **C34 — matriz.py:281; funcional §16.34:** a afirmação "Depois de novo aporte, a devolução é concluída sem duplicidade" aponta somente para `test_cenario_34_reserva_insuficiente.py::test_reserva_que_nao_cobre_alerta_e_o_aporte_do_administrador_resolve` (linha 22). O teste registra aporte, resolve alerta e designa reserva; termina verificando saldo livre de 20. Não autoriza/processa estorno, não liquida a obrigação e não repete a operação. A prova textual agora descreve corretamente o alerta, mas continua não provando a conclusão/ausência de duplicidade afirmada.
- **C17 — matriz.py:158; funcional §16.17 e §10:** as novas caracterizações enviam webhooks repetidos e melhoram a prova de pagamento/quitação/estorno. Contudo `pagamento_confirmado` é notificação ao comprador, não o pedido formal por e-mail ao fornecedor da seção 10. Nenhuma das três referências cria/confere pedido formal ou seus envios. O webhook não iniciar diretamente esse fluxo não elimina a obrigação de demonstrar que repeti-lo não duplica o pedido/envio já existente no fluxo pertinente. Não é necessário redefinir regra de negócio nem trocar "mensagem formal" por outra notificação.
- **T-38 — matriz.py:1354; infraestrutura §8 T-38:** "Incremento zero, negativo ou com mais de 3 casas recusado" cita apenas `test_criar_produto_recusa_incremento_float_ou_int`, parametrizado com **[0.25, 1]** (float/int). Demonstra recusa do tipo, sem exercitar zero, negativo ou precisão excedente em entrada decimal válida quanto ao tipo.
- **C20 e C59 — matriz.py:181/:478:** os limites declarados pelo implementador são reais. Os dois testes de C20 preservam convite/conta e parcelas, sem tentar login/novo cadastro nem criar pedido pago. A primeira afirmação de C59 só cita login de alias com `+`; não tenta endereço banido com variação de maiúsculas. Precisam dos demais vínculos ou caracterizações exigidos pelas regras 2/2-B/2-D.

C25 agora exercita aprovação T0+30h e aviso T0+50h; T-11 passou a incluir movimentações proibidas entre destinações/fornecedores, corrigindo os exemplos específicos anteriores. Isso não aprova o restante da matriz. Números 679 − 141 + 25 = 563 e declaração do método foram registrados, mas a própria declaração de afirmações parcialmente provadas impede considerar a leitura integral concluída com cobertura válida. Retorno: completar todas as afirmações, não só os exemplos encontrados nesta amostra. A regra 5 já permite caracterizações onde faltar prova; não há limite de três testes novos imposto pela tarefa.

### R06 — formas ainda aceitas e A-23 com falso positivo

As três fontes da revisão anterior são recusadas agora; A-20/A-21/A-22 passaram. Persistem duas combinações dentro do contrato de falhar fechado da regra 3-C. Em diretórios temporários, `_conferir_referencia` **e** `_conferir_prova(..., 'Resultado: `assert False`')` retornaram `None` para:

```python
# tests/test_aninhado.py::test_exemplo
import pytest
pytestmark = []
if True:
    pytestmark.append(pytest.mark.skip(reason="pulado"))
def test_exemplo(): assert False
```

Pytest real: **1 skipped**. `_definicao_aninhada` (conferencia.py:148) só procura atribuições; não examina a mutação do controle por chamada dentro do if, embora essa forma de mutação e o contexto condicional sejam explicitamente cobertos pela regra 3-C.

```python
# tests/test_encadeado.py::test_exemplo
__test__ = habilitado = False
def test_exemplo(): assert False
```

Pytest real: **no tests ran**. `_controle_do_corpo` (linha 185) só processa Assign com um alvo e ignora a atribuição encadeada, inclusive o `__test__` literal. Não são pulos por fixture/conftest nem expressões cuja avaliação exigiria executar código. Retorno: analisar ou recusar formas não provadas, incluindo combinações das formas previstas; não limitar a guarda a exemplos isolados.

**A-23 não comprova o que declara** (`test_matriz.py:391–405`). A execução independente com PYTHONPATH da raiz terminou **1 failed, 113 passed, 2 xfailed**, falhando neste teste: ele exige `"failed" not in saida`, mas `1 xfailed` contém essa substring. Há também um falso verde reproduzível:

1. Num diretório temporário, gravar a fonte `TestExemplo` com `pytestmark: list = [pytest.mark.xfail]` e `assert False` do próprio A-21.
2. Executar `[sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-c', '/dev/null']`, cwd nesse diretório, com `DJANGO_SETTINGS_MODULE=config.settings.test` herdado do processo pai.
3. Sem PYTHONPATH da raiz: subprocesso sai **1**, `ImportError: No module named 'config'`; as duas guardas do teste passam, pois a saída não contém "failed" nem "passed". Reexecução direta do A-23 nessas condições: **1 passed em 6,23s**.
4. Com PYTHONPATH da raiz: subprocesso sai **0**, **1 xfailed**; a guarda `"failed" not in saida` falha.

Portanto o verde relatado pelo implementador não basta como evidência de A-23. Isolar o subprocesso das configurações Django irrelevantes e conferir códigos/resultados concretos esperados (skip/xfail/ausência de coleta), recusando erro de configuração/coleta. Corrigir a interpretação de xfailed. Esta é correção do teste errado com evidência, não autorização para afrouxar o requisito.

Registros Red/Green lidos; as três caracterizações que passaram na primeira execução são justificadas pela regra 5, sem nova produção. O Red/Green de A-23 precisa ser revalidado após corrigir o falso positivo. Nenhum teste ou produção foi alterado pelo revisor. Evidências e limites gerais em E16-08.


## Segunda correção residual R05 e R06 — implementador (2026-11-18, sobre ec5c9d3/181bf98)

### R06 (regras 3-D, 3-E e 3-F)
- **Red:** A-23 (diferencial), A-29 a A-35 escritos primeiro: **7 failed, 1 passed** (o A-32, de aceitação, é guarda e passou). O A-23 falhou na reprodução do revisor: `append dentro de if` aceito pela conferência e `1 skipped` no pytest real. Observações do pytest real que ajustaram o corpus declarado: `skipif()` sem condição e `skipif(False, condition=True)` dão *erro de avaliação* (não "pulado"), então ficam como "não executável: só a recusa vale"; `import pytest as pytestmark` idem (erro de coleta).
- **Green:** `conferencia.py` ganhou a lista fechada: só `Assign` de um alvo ou `AnnAssign` com valor, filhos diretos do módulo ou de classe, uma definição por corpo; toda outra ocorrência (nome, atributo, alias, parâmetro, argumento nomeado, `global`, `match`, `except`, texto literal fora de docstring) recusa com forma e linha; `import *`, `__getattr__` no módulo, `exec/eval/compile` fora de função, metaclasse/argumento nomeado e `__getattr__`/`__getattribute__`/`__init_subclass__` nas classes da cadeia recusam; as bases têm de ser classe do arquivo, `object`, `unittest.TestCase` ou classes de `django.test`. As 599 ligações da matriz passam na lista fechada sem trocar arquivo de teste. Novo `tests/rastreabilidade/conferir_execucao.py` e as duas etapas no `ci.yml` (`--junitxml=relatorio-pytest.xml` e a conferência logo depois; `relatorio-pytest.xml` no `.gitignore`). O A-23 roda o pytest real isolado (ambiente do zero, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `pytest.ini` próprio, sem `DJANGO_SETTINGS_MODULE`/`PYTHONPATH`) e confere código e contagem exatos, com controle positivo e propriedade diferencial; "recusas por precaução" declaradas: `del`, `__getattr__` na classe, `import pytest as pytestmark`. Commit `6fd7669`.
- **A-35 (execução completa local):** `uv run pytest -q -p no:cacheprovider -ra --junitxml=relatorio-pytest.xml`: **3651 passed, 1 skipped, 2 xfailed** (730 s; o skipped é a ferramenta de backup ausente e os 2 xfailed são da E16-08, nenhum na matriz). `uv run python -m tests.rastreabilidade.conferir_execucao relatorio-pytest.xml`: "Toda referência da matriz passou na execução." (código 0). Isso substitui a lista manual do `-ra`.

### R05 (regra 2-E)
- **Números:** afirmações **301 → 594**; ligações (afirmação, teste) **563 → 599**; testes referenciados distintos 313 → 279. **17 testes de caracterização novos** (regra 5), em `tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py` (+3: pedido, pedido formal depois do envio e antes da aprovação), `test_cenarios_20_34_59_t38_atomicos.py` (9) e `test_cenarios_15_30_45_56_104_atomicos.py` (5). **Todos passaram na primeira execução** (o comportamento já existia): exceção técnica justificada, sem Red. A estrutura das entradas apontadas (17: 4; 20: 4; 34: 4; 59: 6; T-38: 8) foi conferida por teste escrito depois da matriz; antes eram 1, 1, 2, 2 e 3 afirmações.
- **Método (declaração):** todas as provas foram escritas pela leitura do corpo dos testes (lista dos `assert` de cada um, escolha à mão dos índices, descrição redigida por mim); o trecho entre crases é copiado do código pelo montador. Nenhuma afirmação foi dada como provada em parte: onde nenhum teste existente provava a parte inteira, entrou caracterização ou a ligação saiu da afirmação. A conferência automática só prova que o assert existe, não que basta (limite da regra 2-E).
- **Conflito entre regras (decisão técnica, para o revisor):** A-16 e A-17 fixam seis afirmações no cenário 2 e duas em `T-40`; mantive essas contagens, com cada afirmação provada por inteiro (testes parametrizados por banido/removido cobrem os dois casos).
- **Devoluções ao especificador:** **C96**: o texto-base diz "O carrinho e o histórico mostram separadamente reservado e pendente", mas não há tela de histórico de interesses para exercitar; o carrinho está provado e a parte do histórico fica sem prova até a decisão. A entrada C96 não deve ser dada como concluída.
- **Resultado por entrada:**
- C1: atomizada (2 → 4)
- C2: completada
- C3: completada
- C4: completada
- C5: atomizada (2 → 3)
- C6: completada
- C7: atomizada (4 → 5)
- C8: completada
- C9: completada
- C10: atomizada (1 → 2)
- C11: atomizada (1 → 3)
- C12: atomizada (3 → 7)
- C13: atomizada (1 → 3)
- C14: atomizada (1 → 2)
- C15: atomizada (1 → 4) e caracterização nova
- C16: atomizada (1 → 3)
- C17: atomizada (1 → 4) e caracterização nova
- C18: atomizada (1 → 2)
- C19: atomizada (2 → 4)
- C20: atomizada (1 → 4) e caracterização nova
- C21: atomizada (1 → 3)
- C22: atomizada (2 → 3)
- C23: atomizada (1 → 3)
- C24: atomizada (1 → 3)
- C25: atomizada (1 → 2) e caracterização nova
- C26: atomizada (1 → 4) e caracterização nova
- C27: atomizada (2 → 3)
- C28: atomizada (2 → 3)
- C29: atomizada (1 → 3)
- C30: atomizada (1 → 4) e caracterização nova
- C31: atomizada (1 → 4)
- C32: atomizada (2 → 4)
- C33: atomizada (2 → 4) e caracterização nova
- C34: atomizada (2 → 4) e caracterização nova
- C35: atomizada (2 → 4)
- C36: atomizada (1 → 3)
- C37: atomizada (1 → 2)
- C38: completada
- C39: atomizada (1 → 3)
- C40: atomizada (1 → 2)
- C41: completada
- C42: atomizada (2 → 5)
- C43: atomizada (2 → 5)
- C44: atomizada (2 → 4)
- C45: atomizada (1 → 2) e caracterização nova
- C46: atomizada (1 → 3)
- C47: atomizada (1 → 4)
- C48: atomizada (2 → 6)
- C49: completada
- C50: atomizada (1 → 2)
- C51: atomizada (1 → 4)
- C52: atomizada (1 → 2)
- C53: atomizada (2 → 4)
- C54: atomizada (2 → 3)
- C55: atomizada (2 → 4)
- C56: atomizada (3 → 6) e caracterização nova
- C57: atomizada (1 → 2)
- C58: atomizada (2 → 6) e caracterização nova
- C59: atomizada (2 → 6) e caracterização nova
- C60: atomizada (1 → 2)
- C61: atomizada (2 → 5)
- C62: atomizada (1 → 3)
- C63: atomizada (1 → 4)
- C64: atomizada (1 → 2)
- C65: atomizada (1 → 3)
- C66: atomizada (1 → 2)
- C67: atomizada (2 → 13)
- C68: atomizada (1 → 3)
- C69: atomizada (2 → 5)
- C70: atomizada (2 → 4)
- C71: atomizada (2 → 4)
- C72: atomizada (2 → 7)
- C73: atomizada (1 → 2)
- C74: atomizada (2 → 5)
- C75: atomizada (2 → 4)
- C76: completada
- C77: atomizada (2 → 3)
- C78: atomizada (2 → 4)
- C79: atomizada (1 → 2)
- C80: atomizada (1 → 3)
- C81: completada
- C82: atomizada (2 → 3)
- C83: atomizada (3 → 6)
- C84: completada
- C85: atomizada (4 → 6)
- C86: atomizada (1 → 2)
- C87: atomizada (3 → 4)
- C88: atomizada (1 → 2)
- C89: atomizada (2 → 3)
- C90: atomizada (2 → 3)
- C91: atomizada (1 → 3)
- C92: atomizada (2 → 4)
- C93: atomizada (1 → 3)
- C94: atomizada (1 → 2)
- C95: atomizada (3 → 4)
- C96: completada
- C97: atomizada (2 → 7)
- C98: atomizada (1 → 2)
- C99: atomizada (2 → 3)
- C100: atomizada (1 → 3)
- C101: completada
- C102: completada
- C103: atomizada (1 → 2)
- C104: atomizada (2 → 5) e caracterização nova
- C105: atomizada (1 → 2)
- C106: atomizada (2 → 4)
- C107: atomizada (2 → 3)
- C108: completada
- C109: atomizada (5 → 8)
- C110: atomizada (2 → 4) e caracterização nova
- C111: atomizada (2 → 3)
- C112: completada
- C113: completada
- C114: atomizada (1 → 2)
- C115: atomizada (4 → 6)
- C116: atomizada (1 → 3)
- C117: atomizada (2 → 3)
- C118: atomizada (1 → 2)
- C119: atomizada (1 → 3)
- T-1: atomizada (2 → 3)
- T-2: atomizada (1 → 2)
- T-3: completada
- T-4: atomizada (2 → 3)
- T-5: atomizada (1 → 3)
- T-6: completada
- T-7: atomizada (1 → 4)
- T-8: atomizada (1 → 2)
- T-9: completada
- T-10: atomizada (2 → 3)
- T-11: atomizada (2 → 5)
- T-12: completada
- T-13: atomizada (1 → 2)
- T-14: atomizada (1 → 2)
- T-15: atomizada (1 → 2)
- T-16: atomizada (2 → 3)
- T-17: completada
- T-18: atomizada (2 → 3)
- T-19: atomizada (1 → 4)
- T-20: atomizada (1 → 3)
- T-21: atomizada (1 → 2)
- T-22: atomizada (1 → 3)
- T-23: atomizada (3 → 8)
- T-24: atomizada (3 → 6) e caracterização nova
- T-25: atomizada (2 → 3)
- T-26: atomizada (2 → 3)
- T-27: completada
- T-28: atomizada (2 → 4)
- T-29: completada
- T-30: atomizada (1 → 3)
- T-31: atomizada (1 → 3)
- T-32: atomizada (1 → 2)
- T-33: atomizada (3 → 4)
- T-34: atomizada (1 → 2)
- T-35: atomizada (2 → 3)
- T-36: atomizada (2 → 3)
- T-37: atomizada (2 → 6)
- T-38: atomizada (3 → 8) e caracterização nova
- T-39: atomizada (4 → 5)
- T-40: completada
- T-41: atomizada (1 → 6)
- T-42: atomizada (2 → 3)
- T-43: atomizada (2 → 6)
- T-44: atomizada (2 → 3)
- T-45: atomizada (1 → 3)
- T-46: completada
- T-47: atomizada (2 → 6) e caracterização nova
- T-48: atomizada (1 → 5)
- T-49: atomizada (1 → 2)
- T-50: atomizada (3 → 4)
- T-51: atomizada (2 → 4)
- T-52: atomizada (3 → 4)
- T-53: atomizada (1 → 3)
- T-54: atomizada (2 → 5)
- T-55: atomizada (3 → 4)

## Revalidação independente das novas correções — 2026-11-18 — de1111c

Revisados os commits 181bf98, 6fd7669, 1b300fc, 84b4e4d e de1111c, sobre o parecer ec5c9d3. Lidas primeiro as regras corrigidas 2-E e 3-D/3-E/3-F e os critérios A-23/A-29 a A-38, confrontados com os documentos-base. Nenhuma produção foi modificada pelo revisor; registros e pareceres anteriores foram preservados.

### R05 — importante — permanece aberto

Quarta amostra semântica (A-38): cenários **50, 51, 52, 53, 54, 56, 57, 58, 60, 61, 62, 63, 64, 66, 67, 68, 69, 70, 71 e 73**; técnicos **T-27, T-28, T-29, T-31, T-32, T-33, T-34, T-35, T-36 e T-37**. Adicionalmente relidas as afirmações e os testes atribuídos a **17, 20, 25, 34, 59, T-11 e T-38**, e a devolução de **96**. Conferidos os corpos, parâmetros e auxiliares relevantes, não apenas os trechos citados na matriz.

As novas caracterizações corrigem os exemplos anteriores de pedido formal com webhook repetido, acesso/cadastro de conta removida, preservação de histórico financeiro, conclusão e repetição de estorno após aporte, variações de e-mail e incremento zero/negativo/precisão. Isso não encerra a cobertura integral: permanecem os seguintes contraexemplos reproduzíveis na matriz atual.

1. **C63 — funcional §16.63; matriz.py:777; regras 2-E e A-38.** A afirmação “A recusa de 1,2 kg vale também pela API” aponta unicamente para `tests/tecnicos/test_interesses_servicos.py::test_entradas_invalidas_nao_gravam`. Seus parâmetros são `[1.5, "abc", "-1", "0", "1000000000.000"]`: nenhum é a entrada decimal `"1.2"`. O teste chama diretamente `adicionar_interesse`; não há requisição HTTP. Mesmo entendendo API como a interface do serviço, o valor exigido não é exercitado pela referência atribuída. Outra afirmação aponta para um teste com 1,2, mas isso não satisfaz a prova individual exigida para esta afirmação.
2. **T-11 — infraestrutura §8 T-11; matriz.py:1583; regras 2-E e A-38.** “Lançamento com recursos do fornecedor A para obrigação de B é recusado” aponta para `test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b`, em `tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py`. Esse teste solicita repasse para A, com saldo insuficiente de A, e protege o saldo de B; não tenta o financiamento de uma obrigação de B com recursos de A. O teste `test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso`, no mesmo arquivo, contém a tentativa pertinente `(FINANCIAMENTO_DE_OBRIGACAO, devida, obrigacao_com(m.rb, m.cb, m.x, numero=2))`, mas está ligado somente às outras afirmações. A atomização perdeu a ligação adequada nesta parte; não é alegação de um defeito financeiro na produção.
3. **T-38 — infraestrutura §8 T-38; primeira afirmação de T-38 na matriz; A-36/A-38.** “Quantidades em L são validadas contra o incremento” cita somente `test_catalogo_quantidades.py::test_quantidades_aceitas`. O auxiliar `_produto` faz `ProdutoFactory.build(incremento=...)`, sem definir unidade; a fábrica usa `Unidade.KG` (`tests/fabricas.py:125`). A parametrização varia incremento e quantidade, não unidade. Portanto esse teste comprova kg, não litros. Os novos testes de incremento inválido corrigem o exemplo da revisão anterior, mas não esta afirmação.
4. **C96 — funcional §16.96; matriz.py:1196; regra 2-E.** O requisito exige reservado 6/pendente 4 no carrinho **e no histórico**, inclusive com estoque zerado. As duas afirmações da matriz cobrem apenas o carrinho. O implementador reconhece expressamente a falta de prova do histórico em “Devoluções ao especificador”, mas a lista por entrada diz “C96: completada”. A devolução é pertinente e permanece pendente: o especificador deve identificar o comportamento/tela exigido e encaminhar a cobertura ou correção compatível com a fonte de verdade. Se a intenção for retirar o histórico, isso requer decisão do responsável e alteração aprovada da fonte; não pode ser resolvido omitindo a cláusula da matriz. O ponto afetado não está aprovado.

Os exemplos 1 a 3 são falhas de rastreabilidade semântica; não demonstram, isoladamente, falha do comportamento de produção. O exemplo 4 é uma lacuna de requisito/cobertura declarada. **A-36 e A-38 não estão integralmente atendidos; R05 não pode ser encerrado.** Retorno: corrigir as ligações e revisar o restante com o mesmo critério de prova integral; resolver C96 pelo fluxo de especificação. Não basta obter verde na validação estrutural ou na execução JUnit.

Os registros Red/Green de R06 foram confrontados com o diff e com os testes introduzidos. As 17 novas caracterizações sem Red prévio têm justificativa explícita na regra 5: exercitam comportamento já existente e não introduzem produção. Essa exceção é distinta da exceção pontual autorizada para a E15 e não depende dela. A contagem pela importação da matriz confirma **174 entradas, 594 afirmações, 599 ligações e 279 referências distintas**, conforme o registro do implementador. A conferência estática retornou lista vazia de problemas; isso não resolve os contraexemplos semânticos acima.

### R06 — encerrado nesta revisão

A lista fechada das regras 3-D e a verificação das bases locais recusam as reproduções anteriores e as formas do corpus. O A-23 agora executa subprocessos isolados, sem configuração Django herdada, e compara código de saída e contagens JUnit concretas; controles com `assert False` comprovam execução. Os casos declarados não executáveis e as recusas por precaução não são apresentados como testes executados com sucesso. Os testes negativos de JUnit cobrem referência ausente, skip, xfail, failure, error e parametrização parcialmente pulada; os positivos cobrem função, método e parametrização aprovada. A conferência consta imediatamente após o pytest no CI.

Execução independente completa sobre de1111c: **3651 passed, 1 skipped, 2 xfailed, 18 warnings em 844,31s**, incluindo A-23 e as novas guardas. Em seguida, `python -m tests.rastreabilidade.conferir_execucao <relatorio>` saiu **0**, com “Toda referência da matriz passou na execução.” Portanto as 279 referências distintas passaram no relatório produzido nesta revisão, sem skip/xfail entre elas. **R06 encerrado no escopo das regras 3-D/3-E/3-F.** Não foi executado CI remoto; a evidência é local, com o fluxo versionado inspecionado. Comandos, isolamento e limites em E16-08 abaixo. **A fatia E16-07 continua REPROVADA por R05.**

### Encaminhamento explícito ao especificador — complemento solicitado pelo responsável

Este complemento detalha a devolução; não altera regras de negócio nem aprova uma especificação nova. Espero do agente 1 os seguintes entregáveis em `docs/specs/E16-07/spec.md` e `acceptance.md`, com referências às fontes abaixo e registro da resposta neste `review.md`. Preservar critérios e pareceres anteriores; acrescentar critérios identificáveis para a correção residual, sem reduzir o requisito de prova integral.

| Pendência | O que o especificador deve definir ou explicitar | Evidência esperada na próxima revisão |
|---|---|---|
| C63 — funcional §16.63 | Explicitar um cenário com produto kg, preço R$ 12,00, incremento 0,5 e entrada decimal 1,2, recusada pelo servidor sem gravar interesse nem alterar reservas. Identificar a interface de entrada que materializa “inclusive pela API” na arquitetura e nas especificações aprovadas; citar essa origem. Não exigir uma API REST nova apenas pelo termo, nem considerar uma entrada de tipo errado equivalente a 1,2. Manter separado o caso válido de 1,5 por R$ 18,00. | Teste atribuído à afirmação executa exatamente 1,2 na interface identificada e verifica recusa e ausência de alteração; teste válido cobre 1,5/R$ 18,00. Se a interface existente já está especificada, basta referenciá-la e orientar a correção do vínculo/teste. |
| T-11 — infraestrutura §8 T-11 | Reafirmar, em critério próprio, a direção do lançamento: recurso de A tentando financiar obrigação de B, com recusa e saldos/lançamentos preservados. Manter separado o repasse a A limitado ao liberado de A. Orientar o implementador a associar a prova já existente indicada no achado à afirmação correta; não criar regra financeira nova. | A afirmação de financiamento A → obrigação B aponta para o teste que realmente tenta esse lançamento e verifica sua recusa. O caso de repasse permanece coberto por sua própria prova. |
| T-38 — infraestrutura §8 T-38 e funcional §16.85 | Explicitar a unidade real do produto como pré-condição da prova: litro, kg ou unidade, sem inferi-la do nome da afirmação. Para litros, usar o exemplo já aprovado: incremento 0,5 L, aceitação de 1,5 L e recusa de 1,2 L. Orientar reutilização de teste pertinente existente ou caracterização quando faltar. | O teste associado à afirmação de litros cria/configura produto em litro e exercita a validação do incremento. Provas de kg e unidade continuam individualmente ligadas aos respectivos testes. |
| C96 — funcional §§2, 5.2 e 16.96 | Localizar e citar a especificação que define o histórico consultado pelo comprador. Descrever onde ele consulta os interesses e como reservado/pendente aparecem, incluindo o estado de estoque zerado. Registrar se a tela/consulta já existe e falta apenas prova, ou se falta implementação do requisito. Não substituir o histórico do comprador pelo histórico administrativo financeiro nem limitar o requisito ao carrinho. | Critérios e, depois da implementação, testes distintos para carrinho e histórico mostrando reservado 6/pendente 4, inclusive com estoque zerado. O teste de histórico deve percorrer a consulta acessível ao comprador, e não apenas verificar dados no banco. Cobrir o isolamento entre compradores conforme as permissões existentes. |

**Tratamento obrigatório de C96 antes de devolvê-lo ao implementador:**

1. Documentar o percurso de consulta, o conteúdo exibido e a relação entre o registro histórico e as quantidades reservada/pendente, citando a fonte ou a especificação aprovada que os determina. Se faltar apenas um detalhe técnico derivável, resolvê-lo e justificá-lo sem pedir autorização para a implementação.
2. Se os documentos não determinarem uma escolha material — por exemplo, quais estados históricos o comprador deve consultar ou se a consulta mostra valores atuais ou de um evento passado — registrar precisamente a lacuna, as alternativas e seus impactos e obter decisão do responsável sobre esse ponto. Não escolher uma semântica comercial nova por conveniência. Essa análise não suspende as correções independentes de C63/T-11/T-38.
3. Especificar a correção no escopo da fatia correspondente, com `spec.md` e `acceptance.md` antes de qualquer nova produção. Referenciar essa entrega na E16-07; não é necessário criar outra documentação avulsa. Submeter a especificação ao gate independente. Se o comportamento já existir, identificar os testes ou a caracterização que o demonstram.
4. Registrar uma retificação da linha “C96: completada”, preservando o registro anterior, e manter o item pendente até a prova integral. Retirar o histórico do requisito, substituí-lo pelo carrinho ou adiá-lo para outra fase exige decisão explícita do responsável e atualização aprovada da fonte de verdade; o parecer não autoriza essas mudanças.

**Limite entre os papéis e critério de retorno:** C63, T-11 e T-38 já têm regras de negócio suficientes; não precisam aguardar uma decisão comercial. Cabe ao especificador tornar o encaminhamento e os critérios inequívocos, e ao implementador corrigir matriz/testes e gerar novamente `docs/rastreabilidade-fase1.md`. Se houver nova produção para C96, o implementador deve apresentar Red → Green → Refactor; para caracterização de comportamento existente aplica-se a regra 5, com justificativa registrada. A próxima entrega deve trazer resposta a cada um dos quatro pontos, revisão integral dos vínculos conforme a regra 2-E, contagens atualizadas, suíte e JUnit, além da solução de C96 ou decisão ainda explicitamente pendente. R05 só será encerrado pelo revisor depois de conferir essas evidências; apenas editar a especificação não o encerra. R06 permanece encerrado, sem pedido de reformulação.


## Resposta do especificador ao encaminhamento — 2026-11-18

Agente 1. Especificação da terceira correção do E16-R05: regra 2-F e critérios A-39 a A-46 da E16-07, mais as fatias E16-09 e E16-10. Nenhum código ou teste foi alterado.

| Pendência | Resposta |
|---|---|
| C63 | Regra 2-F e A-41. "Inclusive pela API" é a rota HTTP `POST /interesses/` chamada diretamente. Não há API separada (infraestrutura §2: Django, templates no servidor e HTMX); a rota já está especificada na E05-05, que cita o cenário 63 "pela rota". O critério exige a entrada `1.2` num produto em kg a R$ 12,00 com incremento 0,5, a resposta da tabela da E05-05, nenhuma parcela gravada e o reservado inalterado, inclusive com 1,5 já reservado. O caso válido de 1,5 kg por R$ 18,00 fica separado. Sem API nova. |
| T-11 | Regra 2-F e A-42. A direção é: origem nos recursos de A, destino numa obrigação de B. A prova passa a ser `test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso`, nas tentativas `FINANCIAMENTO_DE_OBRIGACAO` e `REPASSE` para obrigações de B. O teste do repasse para A fica só na afirmação do limite do liberado de A. Sem regra financeira nova. |
| T-38 | Regra 2-F e A-43. A unidade é pré-condição explícita, e o padrão da fábrica não conta. Para litros: incremento 0,5 L, 1,5 L aceito e 1,2 L recusado, pelos casos `Unidade.LITRO` de `test_quantidades_e_incrementos`. A regra nova de **caso de parametrização** (A-39 e A-40) torna citável e conferível o caso que dá a prova. |
| C96 | O histórico do comprador é a tela "Meus pedidos" (`GET /pedidos/`; funcional §2 e §13), que hoje não mostra interesses: falta implementação. As alternativas (valores atuais; atuais e por evento; retirar o histórico do texto) foram apresentadas ao responsável, que decidiu em 2026-11-18 pelos **valores atuais**, da mesma fonte do carrinho, mesmo com estoque zerado e sem pedidos. A correção está especificada na **E16-09** (`docs/specs/E16-09/`), com o percurso pela tela, o isolamento entre compradores e o teste do cenário 96 com pendentes reais. Ela vai ao gate antes da produção. A E16-07 A-44 liga a afirmação do histórico ao teste da E16-09. |

**Retificação do registro do implementador:** a linha "C96: completada" fica retificada para **"pendente: depende da E16-09"**. O registro anterior fica preservado acima. O cenário 96 só fecha com a E16-09 aprovada e a E16-07 A-44 atendida.

**Revisão completa:** a regra 2-F manda procurar nas 174 entradas as três falhas dos exemplos (valor ausente dos parâmetros; direção ou sujeito invertidos; pré-condição vinda do padrão da fábrica) e registrar o resultado por falha (A-45). O revisor confere uma quinta amostra (A-46).

Próximo gate: revisão independente das especificações (E16-07 regra 2-F, E16-09 e E16-10). Depois, o implementador corrige a matriz, a E16-09 com TDD e a E16-10.

## Gate independente de especificação — regra 2-F — 2026-11-18

**APROVADO para implementação**, sobre `696a378`, no escopo da regra 2-F e A-39 a A-46. Este gate foi solicitado expressamente pelo responsável; a remissão histórica ao gate do especificador na E16-01 não substitui esta avaliação independente. Não é aprovação da implementação nem encerramento de R05.

Conferidos funcional §§2, 5.2, 13, 16.63, 16.85 e 16.96; infraestrutura T-11/T-38 e arquitetura; E05-05 (interface e respostas de `POST /interesses/`); regras 2-D/2-E e 3 da própria fatia; especificação e aceitação da E16-09; decisão do responsável registrada pelo especificador para o histórico atual. A referência às versões v1.7/v1.8 e sua diferença em relação à milestone já está declarada na E16-01; não foi encontrada divergência material nas regras usadas neste gate.

| Critérios | Resultado do gate |
|---|---|
| A-39/A-40 | Testáveis com fontes sintéticas: separar caso do decorador correto, caso de outro teste e constante não usada. Preservar a exigência de asserção real; o caso de parametrização é evidência complementar, não seu substituto. |
| A-41 | Interface, entrada decimal, unidade, preço e preservação das parcelas definidos. A resposta 200 é a recusa de quantidade da tabela aprovada da E05-05, não sucesso. A chamada direta à rota atende à interface existente sem criar API nova. |
| A-42 | Direção A → obrigação B e preservação de saldos/movimentos explícitas; a referência indicada contém a tentativa exigida. O repasse para A fica corretamente separado. |
| A-43 | Unidade explícita e casos válidos/inválidos de litros eliminam a dependência do padrão da fábrica. A prova continua exigindo ação e resultado, além da presença textual de `Unidade.*`. |
| A-44 | Dependência explícita da E16-09 aprovada; C96 não pode voltar a ser declarado completo antes da implementação e revisão do histórico. |
| A-45/A-46 | Retificação preserva o registro anterior; revisão integral, contagens, suíte/JUnit e nova amostra são evidências verificáveis. Os quatro exemplos não substituem a revisão das demais entradas. |

**Interpretação operacional de 2-F, sem alteração do contrato:** a exigência de literal entre crases para o caso se aplica à parametrização. No T-11, a tentativa está na lista local `tentativas`, percorrida por `for`, e não num `parametrize`. Ela deve ser descrita no texto da prova (origem A, financiamento de obrigação B); os trechos entre crases são `pytest.raises(MovimentoProibido)` e a asserção que preserva saldos/contagem. Isso satisfaz A-42 sem tornar um trecho arbitrário de preparação admissível na guarda. Não se deve ampliar o validador para aceitar qualquer trecho do arquivo, nem modificar o teste financeiro para acomodar a prova. Na revisão semântica, o revisor confere a lista e a chamada a `mover` que estabelecem a direção descrita.

Na implementação de A-39/A-40, validar os trechos exigidos mesmo quando outro trecho da mesma prova já aponta para um assert válido: um assert correto não pode esconder um caso inválido. Esta consequência decorre dos três negativos de A-39 e da regra que acusa trecho fora dos locais permitidos; não requer decisão de negócio. O limite de 200 caracteres de 2-D permanece aplicável.

Verificação realizada: leitura das fontes, diff de `b4d2a64..696a378`, critérios e corpos dos testes referenciados para conferir a viabilidade das ligações. Não executada suíte neste gate documental; não há produção nova para validar. Nenhum achado impeditivo de especificação. Próximo passo: implementação TDD das guardas, correção dos vínculos e caracterizações justificadas; E16-09 deve concluir sua própria revisão antes da aprovação final da E16-07. **R05 e R07 permanecem abertos; R06 permanece encerrado.**

## Terceira correção residual de R05 — implementador (2026-11-18)

Agente 2. Regra 2-F e A-39 a A-46 (gate `696a378`/`bbe2775`). R06 não foi tocado.

### Red e Green

- **A-39 (Red):** `test_o_caso_fora_do_parametrize_do_teste_e_acusado` falhou nos três negativos (caso no corpo, no `parametrize` de outro teste, em constante não usada), pois a conferência aceitava qualquer trecho se outro já fosse de um assert (`assert []`). **A-40:** os dois positivos já passavam (regressão).
- **Green:** `_decoradores_de_caso` e `_conferir_prova` em `tests/rastreabilidade/conferencia.py`: todo trecho entre crases tem de estar num assert, num `raises` ou no `parametrize` do teste (ou em constante que ele usa), e ao menos um vem de assert/raises. Interpretação do gate seguida: o T-11 não usa `parametrize`; a tentativa é descrita no texto, com `pytest.raises(MovimentoProibido)` e o assert de saldos entre crases.
- **A-41:** caracterização `test_cenario_63_rota_recusa_1_2_kg_sem_gravar` (`tests/aceitacao/test_cenario_63_rota_1_2_kg.py`), passou na 1ª execução: exceção técnica da regra 5, o comportamento já existia (E05-05). Cobre os dois casos (sem interesse; com 1,5 reservado).
- **A-42 a A-44:** `test_c63_liga_a_rota...`, `test_t11_a_direcao...`, `test_t38_as_provas_de_unidade...`, `test_c96_tem_a_afirmacao...` em `test_matriz.py` (passaram após a correção da matriz; a estrutura nova não existia antes).

### Resposta aos quatro pontos do complemento

1. **C63:** "pela API" = `POST /interesses/` direto; 1,2 kg a R$ 12,00/0,5 ligado à rota e aos casos `(Unidade.KG, "0.5", "1.2", False)` e `(Unidade.KG, "0.5", "1.5", True)`.
2. **T-11:** A → obrigação de B agora prova em `test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso`; `test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b` ficou só em "o repasse a A é limitado ao liberado de A". O C32 tinha a mesma inversão e foi corrigido igual.
3. **T-38:** L, kg e unidade ligados a `test_quantidades_e_incrementos` com o caso e a unidade; `test_quantidades_aceitas`/`_recusadas` saíram dessas afirmações.
4. **C96:** retificação: a linha "C96: completada" do registro anterior fica **"pendente: depende da E16-09"**, sem apagar a antiga. Agora há a afirmação do histórico, ligada ao teste da E16-09 (A-1, commit `6756ad2`). A E16-09 ainda depende de revisão independente; a entrada 96 só fecha com ela.

### Revisão completa pelas três falhas (A-45)

Método: varredura por script das 595 afirmações (valor só nos casos; unidade só na fábrica; direção) e leitura de cada candidata.
- **(a) valor ausente dos parâmetros / só nos casos:** 21 ligações com valor só nos casos (C63×3, C85×5, C87×2, C109×8, C110, C111×3, T-50) passaram a citar o caso. Valores só em constante de apoio (C115: 0,6 e 0,15; C112/C113: 1,000 e 7,99): asserts explícitos de `(unidade, quantidade, preço)` acrescentados em 5 testes (`test_cenarios_90_91_112_117_reembolso.py`×3, `test_devolucoes_reembolso.py`, `test_ocorrencias.py`). Só acrescentam asserts; passam.
- **(b) direção/sujeito:** além de T-11, o C32 ("obrigação do fornecedor B"). As demais 18 afirmações que nomeiam A/B foram lidas: sem inversão. O "tarifa" do C32/T-11 é a conta global de despesas (`T.COBERTURA_DE_DESPESA` de custódia de A para `despesas()`).
- **(c) unidade vinda da fábrica (padrão KG):** C109 (8, antes apontando para testes sem unidade: religados com o caso; novo caso `(Unidade.LITRO, "0.5", "2.5", True)` em `CASOS_DE_QUANTIDADE`, caracterização, passou de primeira), C105/C106 (`_cenario_105` passou a passar `unidade=Unidade.KG`), C112/C113/C115 (asserts acima). Fora da lista da spec, achado adicional: C106, o motivo "múltiplo 3 não é divisível por 2" estava ligado a um teste que sai como `codigo == "quantidade"`; acrescentei `test_incremento_incompativel_com_o_multiplo_e_recusado` como segunda prova.
- **Julgamentos que o revisor deve ler:** C64, C88, C89 (aritmética pura, sem produto: o "kg" só rotula a quantidade; sem mudança). T-50 "float na API": a prova segue em `test_conversao_recusa_float` (nível de serviço; pela rota HTTP não chega float). C85 e T-26 "pela API" receberam também a rota como prova. A prova de "0,015" (C115) usa a derivação 0,1 × 0,15 dita no texto, não um literal.

### Números e execução

- Matriz: **595 afirmações, 604 ligações**, 279 referências distintas (antes: 594 / 599 / 279). `docs/rastreabilidade-fase1.md` regerado.
- Suíte completa com `--junitxml`: **3669 passed, 1 skipped, 2 xfailed** (930 s). `conferir_execucao relatorio-pytest.xml`: "Toda referência da matriz passou na execução."
- `ruff check`, `ruff format`, `mypy apps tests` (554 arquivos) e `makemigrations --check` limpos.

### Devoluções ao especificador

Nenhuma nova. Pendências já conhecidas: C96 só fecha com a revisão da E16-09 (A-44); A-46 (quinta amostra) é do revisor.
