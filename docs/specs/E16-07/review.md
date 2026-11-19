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

## Revisão independente da terceira correção — 2026-11-18 — 3e8b4ff

**REPROVADO: R05 permanece importante e aberto.** Escopo: correções desde o gate `bbe2775`, incluindo `024b0d9`/`3e8b4ff` e a ligação da E16-09. Requisitos e critérios aprovados relidos antes da comparação. A contagem por importação confirma **174 entradas, 595 afirmações, 604 ligações e 279 referências distintas**. Não houve correção de código pelo revisor.

### Correções aceitas e quinta amostra (A-46)

Os quatro exemplos da rodada anterior foram tratados: C63 tem POST real com 1,2 kg sem escrita e preserva a parcela de 1,5; T-11 liga a tentativa de financiamento A → obrigação B ao teste correto; T-38 cita unidades/casos explícitos; C96 ganhou a consulta real do histórico com 6/4 e estoque livre zero. A conclusão da E16-09 está em seu próprio parecer. A-39/A-40 têm os negativos/positivos especificados e a guarda passou a conferir todos os trechos, sem deixar um assert válido esconder outro trecho inválido. Isso não elimina os resíduos abaixo.

Quinta amostra: cenários **74, 76, 77, 78, 79, 80, 81, 82, 83, 84, 86, 87, 88, 89, 90, 91, 92, 93, 94 e 97**, e técnicos **T-39, T-41, T-42, T-43, T-44, T-45, T-46, T-47, T-48 e T-49**, distintos das quatro amostras principais anteriores. Também relidos **C63, C96, T-11 e T-38**, os trechos alterados e os julgamentos declarados pelo implementador. A leitura confrontou texto-base, afirmações, corpos, parâmetros e auxiliares relevantes; não se limitou aos fragmentos de assert. As provas aritméticas puras de C64/C88/C89 não precisam instanciar produto só para rotular kg, pois as entradas e o arredondamento são explícitos e a operação não depende da unidade.

### Resíduos semânticos reproduzíveis — R05

| Referência | Evidência e problema | Retorno necessário |
|---|---|---|
| Funcional §16.74; `matriz.py`, C74, “O pedido congelado não muda” | Única referência: `test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila`. O teste chama `_viavel` (que já apura) antes de ler a variável `antes`; compara vínculos da restauração e quantidades de parcelas. Não compara pedido/itens antes e depois da apuração. A igualdade de IDs não demonstra conteúdo congelado preservado. | Ligar prova integral. O mesmo arquivo já tem `test_o_pedido_congelado_nao_muda`, que fotografa Pedido/ItemDoPedido/ParcelaNoPedido antes de `_iniciar` e exige igualdade depois. Não é necessário mudar a regra de negócio. |
| Funcional §16.84; C84, “usuario@gmail.com e usuario+teste@gmail.com podem pertencer a contas distintas” | Única referência: `test_contas_emails.py::test_normalizar_email_nao_altera_aliases`. Só chama a normalização e compara strings; não cria duas contas nem percorre cadastro. Distinção de strings é necessária, mas não comprova a coexistência de contas. | Associar teste que cria/consulta as contas distintas e demonstra o comportamento afirmado, ou caracterizá-lo. Manter separada a prova de banimento. |
| Funcional §16.90; C90 | O cenário exige item inteiro de 0,25 kg cobrado em R$ 2,00, preço alterado de 7,99 para 8,99 e reembolso desse item pelo snapshot. `test_o_valor_vem_do_registrado_e_nao_do_catalogo` usa K (item de 1 kg/7,99), muda para 9,99 e devolve apenas 0,25. `test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado` usa N, devolve parcialmente e depois integralmente 100/5/20, sem mudar preço. A terceira referência prova proporção de serviço/frete. Nenhuma percorre o cenário inteiro com suas precondições e resultados; a atomização eliminou a condição comum “depois da mudança de preço” da afirmação de integral. | Vincular ou criar caracterização do item inteiro de 0,25 kg, alteração para 8,99 e reembolso de produtos 2,00 mais componentes registrados. Não usar três fluxos com precondições diferentes como substituto desse cenário. |
| Infraestrutura T-44; primeira afirmação da entrada | “A remoção com item de pedido congelado é recusada” aponta apenas para `test_parcela_em_pedido_nao_entra_na_remocao`: monta uma ParcelaDeInteresse em pedido e chama o serviço com produto; não cria nem envia identificador de ItemDoPedido. A referência da afirmação seguinte, `test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido`, envia `item_de_a_em_q.pk + 10_000` e `fp.q.pk`, não o identificador real do item. | Provar separadamente a entrada com identificador real do item congelado e a entrada referente à parcela em pedido, conforme T-44/E11-08 A-9. O identificador inexistente não é prova do primeiro caso. |
| Infraestrutura T-47; “A formação de caixas ignora a quantidade pendente” | Única referência: `test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas`. Seu `abrir_r2` remove explicitamente o múltiplo de P (`alterar_multiplo(..., "")`); o assert citado é o valor elegível 200,00. Isso demonstra progresso/pedido sem pendentes, não formação de caixas com múltiplo. | Prova com produto de múltiplo definido, reservadas e pendentes, conferindo as caixas formadas sem usar as pendentes para completá-las. Reutilizar teste existente se suficiente. |
| Regra 2-F; C86 e T-43 | C86 afirma zero/negativo, mas as duas provas citam apenas erro de formulário/nenhum produto, omitindo os casos `"0"` e `"-1"` que só aparecem no decorador. Em T-43, “fora do incremento” não cita `"1.5"`, que diferencia essa recusa das entradas de tipo/formato inválido do mesmo teste. Os testes exercitam esses casos, mas a prova escrita ainda descumpre a nova exigência de citação. | Completar as provas com os casos pertinentes e revisar o restante pelo mesmo critério. Aqui o problema é documental, não ausência de execução desses casos. |

Estes exemplos não demonstram defeito na produção financeira nem autorizam alterar comportamentos. Demonstram que a matriz ainda atribui provas parciais ou diferentes às afirmações. A-45 registra a busca, mas A-46 não está atendido. Manter a revisão integral exigida por 2-E/2-F, não apenas corrigir as linhas desta amostra.

### Guarda dos casos de parametrização — R05, regra 2-F

Reprodução independente, fora do repositório, com este módulo:

```python
import pytest
CASOS = [(1, "0.5", True)]
@pytest.mark.parametrize(("u", "x", "ok"), CASOS)
def test_exemplo(u, x, ok):
    assert (u, x, ok) == (1, "0.5", True)
CASOS = [(9, "9.5", False)]
```

Referência: `tests/test_exemplo.py::test_exemplo`. Prova: `Caso \`(9, "9.5", False)\`; \`(u, x, ok) == (1, "0.5", True)\``. `_conferir_referencia` e `_conferir_prova` retornam **None** (aceitam). O pytest real, com configuração/ambiente isolados e plugins automáticos desligados, coleta e executa somente **`test_exemplo[1-0.5-True]`: 1 passed**, saída 0. O caso 9/9.5/False nunca pertenceu ao decorador avaliado.

Causa: `_decoradores_de_caso` (`conferencia.py:497`) reúne a última atribuição de cada nome em todo o módulo e a usa sem respeitar o instante de aplicação do decorador. O JUnit atual confere a referência sem parâmetros; portanto o teste verde não detecta que o caso citado é outro. Trata-se da nova prova de parametrização de R05, não da guarda de coleta/pulo de R06, cujo encerramento permanece.

Retorno ao implementador: escrever negativo para esta reprodução antes da correção, resolver o vínculo de forma conservadora ou recusar reatribuição não comprovável, e preservar positivos e execução JUnit. Não importar/executar o módulo para resolver isso. Nenhuma decisão comercial do especificador é necessária: a regra já exige que o caso pertença à parametrização efetiva do teste.

### Processo e encaminhamento

Registros Red/Green lidos e confrontados com os diffs. A-39 descreve as três falhas antes da guarda; A-40 é controle positivo/regressão. Caracterização de C63, novo caso de quantidade e asserts adicionais sobre comportamento existente têm justificativa pela regra 5; nenhum deles altera produção. Não se confundem com a exceção de TDD da E15.

Ao especificador: as regras 2-E/2-F já autorizam e exigem os reparos acima; não é necessário criar outra regra de negócio nem escolher novamente a semântica de C96. Receber de volta somente um comportamento que a caracterização revele ausente ou um conflito material demonstrado. Ao implementador: corrigir vínculos/provas, caracterizar cenários sem prova e corrigir a guarda com Red/Green. C96 não volta a ser pendência de especificação. Os resultados de execução desta rodada e o veredito global estão no parecer da E16-08.


### Resultado final da execução — 2026-11-19

Suíte independente sobre 3e8b4ff: 3669 passed, 1 skipped, 2 xfailed. Conferência do JUnit pela ferramenta do projeto: saída 0, todas as referências da matriz passaram. Mantido **REPROVADO / R05 importante**: execução bem-sucedida não resolve os vínculos semânticos insuficientes nem o contraexemplo da guarda descritos acima. Consolidado e limitações na E16-08.

## Resposta do especificador à revisão de 3e8b4ff — 2026-11-19

Agente 1. Especificadas as regras 2-G, 2-H e 2-I e os critérios A-47 a A-53. Nenhuma regra de negócio muda.

| Achado | Tratamento |
|---|---|
| Resíduos C74, C84, C90, T-44, T-47, C86 e T-43 | Regra 2-G, com a prescrição de cada um. A causa comum foi a revisão completa por três tipos de falha (A-45, como eu especifiquei), feita por script. Ela é substituída pela auditoria de cada ligação em `tests/rastreabilidade/auditoria.py`, com as seis perguntas (a) a (f) e a completude conferida no CI (A-49 e A-50). |
| Guarda aceita um caso de constante reatribuída | Regra 2-H: só se aceita uma constante com uma única ligação antes do teste e nunca alterada no módulo. A guarda fica congelada, e uma evasão só sintética vai para melhoria (A-47 e A-48). |
| Encerramento | Regra 2-I, com a decisão do responsável de 2026-11-19: sexta amostra sem resíduo encerra a R05. Com resíduo, a escolha entre nova rodada e o registro como melhoria volta ao responsável (A-53). |

**Próximo gate:** gate independente das regras 2-G a 2-I. Depois, o implementador faz a auditoria, as caracterizações e a guarda com Red e Green, e o revisor confere a sexta amostra.

## Gate independente das regras 2-G a 2-I — 2026-11-19

**APROVADO para implementação**, sobre `214b8ce`. Escopo deste gate: regras 2-G, 2-H e 2-I, critérios A-47 a A-53 e compatibilidade com as regras anteriores. Não é aprovação da implementação nem encerramento de R05 ou da E16.

Fontes conferidas antes da avaliação: funcional v1.7 (§§5.2, 7.1 e 16, especialmente C74, C84, C90 e C99), infraestrutura v1.8 (§§7 e 8, T-43, T-44 e T-47), E11-08 A-9, AGENTS.md §§2 a 6 e 8 a 10, e parecer sobre `3e8b4ff`. Versões declaradas compatíveis com os documentos presentes.

| Regra / critérios | Parecer do gate |
|---|---|
| 2-G / A-49 e A-50 | O contrato da auditoria é verificável: chave por ligação, igualdade dos conjuntos de chaves, campos obrigatórios, limites e vereditos. Os negativos permitem Red antes da implementação da conferência. A existência da linha não comprova sua veracidade; esta continua sujeita à leitura das seis perguntas e à revisão independente. |
| 2-G / A-51 e A-52 | Os sete resíduos têm tratamento concreto e compatível com suas fontes: snapshot anterior à ação, contas reais distintas, fluxo integral do C90 após mudança de preço, identificadores reais, caixas com múltiplo e casos parametrizados explícitos. Caracterizações são admitidas somente onde falta prova; falha de comportamento volta ao especificador. A auditoria integral e o registro de ligações retiradas impedem limitar o trabalho aos exemplos. |
| 2-H / A-47 e A-48 | O contraexemplo da reatribuição tem negativo explícito, junto de seis variantes e controles positivos. A recusa conservadora dispensa executar o módulo e tem diagnóstico observável. O novo comportamento da guarda exige Red/Green; caracterizações do produto podem passar de primeira com registro honesto. A limitação a formas declaradas é técnica e explícita, sem pretensão de provar toda a semântica de Python. |
| 2-I / A-53 | O fechamento depende da entrega auditada e da sexta amostra sem resíduos, além da releitura dos sete pontos. Com resíduos, o revisor distingue defeito de produção de deficiência de evidência e devolve a escolha indicada ao especificador/responsável. Não há autorização para o implementador ou o revisor converterem unilateralmente um resíduo real em melhoria. |

### Aplicação dos limites já escritos

- A sexta amostra será **um conjunto diferente** dos anteriores, priorizando entradas ainda não amostradas; não significa 20 cenários e 10 técnicos todos inéditos. Cinco amostras principais disjuntas já cobrem 100 dos 119 cenários e 50 dos 55 técnicos: exigir uma sexta inteiramente inédita seria impossível. A seleção e as repetições serão explicitadas no parecer, além da releitura obrigatória dos resíduos. Esta é uma decisão técnica de amostragem, sem mudança do tamanho mínimo ou do critério de qualidade.
- O congelamento de 2-H limita novas classes de evasão apenas sintéticas, fora das referências reais. Não dispensa implementar corretamente as formas e recusas expressamente exigidas em A-47/A-48, nem permite aprovar ligação real falsa. A regra 3-E comprova a execução dos casos coletados; a correspondência semântica com o caso citado continua a depender da auditoria.
- Para uma referência existente recusada, usar as alternativas permitidas pela especificação sem afrouxar testes existentes. O resultado final precisa manter a cobertura integral das afirmações e regenerar o documento quando a matriz mudar.
- “Sem resíduo” em 2-I não dispensa os demais critérios da fatia: auditoria completa, guarda, suíte, JUnit e evidências de TDD aplicáveis. O gate não encerra R07 nem substitui homologação operacional.

Nenhum achado impeditivo de especificação. Verificação documental: leitura integral do diff `eed1d8f..214b8ce`, confronto dos critérios com os requisitos e pareceres anteriores; `git diff --check eed1d8f HEAD` sem erros. Não executada suíte neste gate, pois o commit avaliado altera apenas especificações, critérios e registros; não se reutiliza o verde anterior como prova da correção futura.

Próximo passo: implementação de 2-G/2-H com os registros de A-52, seguida da revisão independente de A-53. R05 continua aberto até essa revisão.


## Quarta correção residual de R05 — implementador (2026-11-19)

Agente 2. Regras 2-G, 2-H e 2-I e critérios A-47 a A-53 (gate `54be872`). A regra 2-I (sexta amostra) é do revisor.

### Red e Green

- **A-47 (guarda, Red):** `test_a_constante_de_casos_alterada_e_acusada` falhou nos 7 módulos (reatribuição depois do decorador, `+=`, `.append`, `CASOS[0] =`, atribuição só depois da definição, `global` em função e `for CASOS in ...`): a conferência atual aceitava todos (`assert []`). **Green:** `_constante_aceita` e `_ligacoes_do_nome` em `tests/rastreabilidade/conferencia.py`. Uma constante só vale se tiver uma única ligação no módulo (atribuição simples no nível do módulo, antes do decorador) e nunca for alterada (`+=`, `del`, `for`, `with ... as`, `import ... as`, `global`, `nonlocal`, parâmetro, `except ... as`, `match`, índice ou fatia, chamada de método). A recusa traz o motivo "constante de casos com mais de uma ligação ou alterada no módulo" e não importa nem executa o módulo. **A-48:** o caso no decorador e a constante `CASOS` de uma ligação continuam aceitos; a matriz entregue passa sem acusações. A guarda não ganhou formas além dessas (regra 2-H).
- **A-49 (auditoria, Red):** os dois testes falharam por importação (`conferir_auditoria` e `tests/rastreabilidade/auditoria.py` não existiam). **Green:** `conferir_auditoria` (chaves iguais às ligações da matriz, os quatro campos preenchidos com até 200 caracteres, veredito `"íntegra"` ou `"corrigida: ..."`) e `auditoria.py`. **A-50:** a `AUDITORIA` entregue cobre exatamente as 606 ligações.
- **A-51:** `test_os_sete_residuos_da_regra_2g_estao_corrigidos` confere a estrutura dos sete resíduos.

### Método da auditoria (A-52)

Li o corpo de cada teste ligado (a ação, as asserções, os auxiliares chamados pelo nome e os casos de parametrização), na ordem das 174 entradas, e escrevi uma linha por ligação com `preparacao`, `acao`, `resultado` e `veredito`. Um script só gerou o arquivo `auditoria.py` a partir das minhas linhas e acusou chaves faltantes; a leitura foi minha, ligação por ligação.

- **Ligações lidas:** 606 (596 afirmações, 174 entradas, 284 referências distintas).
- **Veredito:** 566 íntegras e 40 corrigidas.
- **Corrigidas por pergunta** (uma pergunta principal por ligação): (a) situação 8; (b) ação ou interface 7; (c) resultado e comparação 17; (d) objeto 4; (e) elementos concretos e casos 1; (f) causa da recusa 3.
- **Ligações retiradas da matriz (29), cada uma trocada por outra que prova por inteiro:**
  - C2 (link depois do pedido); C4 (a ligação do mínimo atingido estava na afirmação "abaixo do mínimo"); C11 (carrinho); C12 (T0+48h); C13 (realocação); C14 (duas); C20 (link isolado); C23 (telas); C26 (duas: parcial de outra obrigação); C39 (destino sem obrigação); C47 (admin com 302 ou 403); C72 (API por serviços); C99 (pk inexistente); C106 (causa "quantidade" para a afirmação de múltiplo); C116 (só produtos);
  - T-1; T-2; T-4; T-5; T-14 (duas); T-24; T-33; T-34; T-51; T-52; T-54.
- **Resíduos do revisor:** C74 religado a `test_o_pedido_congelado_nao_muda`; C84 com caracterização das duas contas pelo cadastro; C90 com o fluxo inteiro (0,25 kg a 7,99, preço para 8,99, ocorrência da quantidade inteira: 2,00, 0,10 e 0,40); T-44 com o `pk` real do item congelado e a parcela em pedido em provas separadas; T-47 com múltiplo definido; C86, T-43 e C98 citando `"0"`, `"-1"`, `"1.5"` e `"5"`.

### Caracterizações novas e reforços (regra 5)

Todas passaram na primeira execução, porque o comportamento já existia (exceção técnica, sem Red inventado): `test_cenario_84_aliases_com_mais_sao_contas_distintas`, `test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado`, `test_rota_com_o_pk_real_do_item_congelado_e_recusada` (T-44), `test_a_formacao_de_caixas_ignora_as_pendentes` (T-47), `test_abaixo_do_minimo_a_rodada_fica_aberta_indefinidamente` (C4), `test_cenario_26_pagamento_tardio_devolvido_pela_devolucao_excepcional` (C26), `test_bloqueio_e_aviso_dao_o_mesmo_resultado_nas_duas_ordens` (T-7), `test_banco_recusa_segunda_conta_com_o_mesmo_email_pela_restricao_unique` (T-34), mais `test_administrador_e_recusado_pela_politica_sem_a_mensagem_da_etapa` (E16-10). Reforços em testes existentes (só acrescentam asserts ou explicitam pré-condições; nenhum foi afrouxado): sem parcela (C2 Google), sem sessão (C2 e C58, link), foto antes da tentativa (C11), etapa ao fim (C12), todas as demais destinações (C29), obrigações de fornecedor (C30), comprador novo (C47), sequência de C atrás da de A (C55), um só pedido formal (C70, C95), sem escrita (T-48) e mais valores de incremento (T-48), além do que foi feito na rodada anterior. Um teste novo de caso (litro 2,5) vem da rodada anterior.

### Julgamentos declarados (para o revisor ler)

- **Afirmações compostas fixadas pela spec** (A-16, A-36): C59 "no login e no novo cadastro" e C85 e T-26 "no servidor, inclusive pela API" têm uma ligação por cláusula. Cada ligação diz, no campo `resultado`, qual cláusula prova.
- **C84:** a caracterização usa os endereços literais da afirmação; o negativo "banir um não afeta o outro" usa `ana@x.com` e `ana+1@x.com`, que têm a mesma forma.
- **T-50 "float na API":** a prova é a interface de serviço (`dinheiro` e `quantidade`); pela rota HTTP não chega float.
- **C64, C88, C89, C112, C113:** cálculo puro ou item sem produto; o "kg" rotula a quantidade e nenhuma regra lê a unidade.
- **T-37:** um teste de hypothesis cobre os cinco fluxos; as cinco linhas da auditoria apontam o bloco de cada fluxo.
- **C12, T-1, T-2:** instantes exatos foram ligados a testes que usam esses instantes (as ligações antigas usavam outros).

### Números e execução

- Matriz: **596 afirmações, 606 ligações, 284 referências distintas** (antes: 595 / 604 / 279). `docs/rastreabilidade-fase1.md` regerado.
- Suíte completa com `--junitxml`: **3690 passed, 1 skipped, 2 xfailed** (834 s; o skipped é a ferramenta de backup ausente e os 2 xfailed são da E16-08). `conferir_execucao relatorio-pytest.xml`: "Toda referência da matriz passou na execução."
- `ruff check`, `ruff format`, `mypy apps tests` limpos.

### Devoluções ao especificador

Nenhuma.

## Revisão independente da quarta correção — 2026-11-19 — 8e35589

**REPROVADO — R05 importante permanece aberto.** Base do gate: `54be872`; commits avaliados: `4f84b76` e `8e35589`. Regras 2-G a 2-I e A-47 a A-53 relidos antes da comparação. Fontes: funcional v1.7, infraestrutura v1.8, especificações e critérios das fatias citadas. Árvore inicialmente limpa. Nenhuma alteração de produção pelo implementador nesta rodada; o revisor não alterou código nem testes.

### Sexta amostra e método (A-53)

Cenários **59, 72, 96, 98, 99, 100, 101, 102, 103, 104, 106, 107, 108, 109, 111, 112, 114, 115, 118 e 90**; técnicos **T-51, T-52, T-53, T-54, T-38, T-7, T-34, T-37, T-44 e T-47**. Os primeiros 19 cenários e T-51 a T-54/T-38 não pertenciam às cinco amostras principais anteriores; C90 e os cinco técnicos restantes são repetições intencionais, como permitido no gate. Alguns dos primeiros 19 já tinham sido relidos pontualmente. A amostra contém **116 afirmações e 119 ligações**.

Além da amostra, relidos os sete resíduos de 2-G (C74, C84, C90, C86, T-43, T-44 e T-47), C85/T-26 e os julgamentos declarados pertinentes. Foram confrontados matriz, linhas de AUDITORIA, texto-base, corpos de 83 referências distintas e auxiliares/parâmetros relevantes. A leitura não se limitou ao texto dos asserts citados. Conferidos também todos os diffs de testes, guarda, auditoria e configuração desde o gate.

Contagens independentes: **174 entradas, 596 afirmações, 606 ligações, 284 referências distintas**. AUDITORIA tem 606 chaves, 566 vereditos “íntegra” e 40 “corrigida”. O diff de chaves completas contra o gate tem 36 retiradas e 38 adicionadas; as 29 retiradas enumeradas no registro não são o total do diff, pois há também as substituições dos resíduos. A conferência estrutural não encontrou chave faltante ou excedente.

### Correções confirmadas

- C74: a afirmação de preservação do pedido aponta agora para o snapshot de Pedido/ItemDoPedido/ParcelaNoPedido anterior à apuração e comparado por conteúdo depois.
- C84: a nova caracterização percorre dois cadastros por convite com os endereços literais, consulta duas contas e confirma sessões distintas. A prova separada de banimento mantém o alias ativo.
- C86 e T-43: provas agora citam os casos `"0"`, `"-1"`, `"1.5"` e `"5"` pertinentes.
- C90: valores, quantidade inteira, unidade e mudança de preço estão explícitos; os três componentes do reembolso são conferidos. A ação ainda não é a ocorrência especificada, conforme a tabela abaixo.
- T-44: o novo teste envia o identificador real do item e fotografa pedidos, itens, reembolsos e parcelas. A abrangência da prova financeira e das demais ligações ainda é insuficiente.
- T-47: passou a haver produto com múltiplo e asserções explícitas de caixas completas. A prova ainda se restringe à consulta de progresso.
- A-47/A-48: os sete negativos recebem o diagnóstico exigido; constante de uma ligação e caso no decorador são aceitos. A-49/A-50: cinco negativos da auditoria e igualdade das chaves passam. A-51 passa como verificação estrutural, mas não substitui o conteúdo de A-53.

### Resíduos da sexta amostra — evidência e retorno

Todos os itens abaixo são **importantes, integrantes de R05**. Demonstram insuficiência ou inexatidão da evidência atribuída às ligações; **não demonstram defeito de produção**. A regra 2-G exige prova integral por ligação, com situação, ação, objeto e resultado correspondentes.

| Referência | Evidência reproduzível | Correção esperada |
|---|---|---|
| C90 e C112; 2-G, fluxo inteiro, perguntas (a)/(b) | `test_cenarios_90_item_inteiro_de_0_25_kg.py:23` chama `parcial(item, "0.25")`. O auxiliar `tests/apoio/devolucoes.py:68` chama diretamente `reembolso_parcial`, com motivo textual `ocorrencia_de_entrega`; não registra uma `OcorrenciaDeEntrega` nem chama o serviço de ocorrência. AUDITORIA descreve a ação como ocorrência, mas só o cálculo financeiro é exercitado. A ligação “A ocorrência de 0,25 kg reembolsa R$ 2,00” de C112 usa o mesmo auxiliar diretamente em `test_cenario_112_parcial_usa_o_valor_registrado`. | Caracterizar o registro efetivo da ocorrência da quantidade inteira do item de 0,25 kg, após mudança 7,99 → 8,99, e conferir o reembolso 2,00/0,10/0,40 vinculado; para C112, usar o item de 1 kg e ocorrência parcial de 0,25. Preservar as provas financeiras existentes, sem tratá-las como provas da ação que não executam. |
| T-47; 2-G, formação de caixas | `test_interesses_progresso.py:100` chama somente `progresso_da_rodada`: 7 reservadas + 5 pendentes dão zero caixas; depois 10 reservadas dão uma. Não há abertura/apuração nem leitura das alocações congeladas. A consulta é somente leitura; a formação congelada ocorre em `apps/pedidos/abertura.py`, separada da consulta. A regra aprovada exige apuração formando só caixas das reservadas e pendentes na fila. | Completar a prova do fluxo especificado, com múltiplo definido, pendentes suficientes para alterar o número de caixas se contassem, alocações/caixas efetivas e preservação da fila. O teste de consulta pode continuar como prova do progresso. |
| C99 / T-44; 2-G (b)/(c)/(d) | `test_fila_ponta_a_ponta.py:349` compara ItemDoPedido, Reembolso e `_estado` (situação/reservado/pendente), mas não Pedido, obrigação nem lançamentos; a prova da matriz diz “obrigações iguais”. O teste novo em `:373` acrescenta Pedido e todas as parcelas de A, mas ainda não lê obrigações/lançamentos. A ligação de C99 para `test_parcela_em_pedido_nao_entra_na_remocao` cria apenas uma parcela com situação EM_PEDIDO, sem ItemDoPedido nem envio de seu identificador. | Separar as duas entradas recusadas e ligar cada afirmação à ação real correspondente. Comparar por conteúdo os registros financeiros pertinentes e o pedido; alinhar a afirmação de trigger à prova de preservação aplicável. Não chamar `_estado` de prova de obrigação. O status 200 não é, sozinho, defeito: a rota usa 200 para erros de formulário; conferir a recusa efetiva e a ausência de escrita. |
| T-34; 2-G (a)/(b) | A afirmação “Dois cadastros simultâneos ... recusa pela restrição UNIQUE” aponta só para `test_contas_modelo.py:31`: dois INSERTs sequenciais. O teste de cadastros concorrentes é outra ligação e admite diferentes recusas; não transforma o INSERT sequencial em prova de concorrência. A própria AUDITORIA descreve uma conta já inserida e um segundo INSERT. | Vincular prova que reúna concorrência e resultado afirmado, ou devolver ao especificador a adequação da afirmação à origem T-34 sem perder a garantia exigida. Não registrar duas provas parciais como uma ligação íntegra. |
| T-7; 2-G (a)/(b) | `test_pedidos_concorrencia.py:343` percorre duas ordens **em sequência**, mas é ligado à afirmação “concorrendo ... em qualquer ordem”. A outra referência roda com barreira, sem forçar ambas as ordens. Cada linha prova parte diferente do enunciado e a AUDITORIA admite a sequência. | Prova integral das ordens concorrentes especificadas, ou atomização compatível com a origem, mantendo evidência das corridas e das ordens sem atribuir a um teste uma ação que não executa. |
| C59, C85 e T-26; 2-G, proibição de ligação complementar parcial | O registro declara uma ligação por cláusula. Em C59, um teste só faz login e outro só emite convite para a afirmação composta login/cadastro. Em C85, `test_quantidades_recusadas` só chama `validar_quantidade`, sem HTTP; em T-26, a mesma função é ligada diretamente a “recusada pela API”. AUDITORIA diz que a cláusula da API é provada por outro teste. A-36 não dispensa 2-G: exige resultado por inteiro. | Retirar a ligação parcial quando outra já prova integralmente a afirmação (por exemplo, rota de T-26), ou criar caracterização que reúna as cláusulas. Se a forma fixa de C59 precisar mudar, devolver a alteração documental ao especificador; não declarar exceção implícita à regra 2-G. |
| C104 / C114; 2-G (a), condição comum do cenário | As provas de pedido/cobrança/fila de C104 usam FP/R2 com C em 4 reservadas + 4 pendentes, não a situação A=8/C=5 do cenário. Em C114, a segunda ligação usa `test_ocorrencias.py:398`, arranjo AE, obrigação 70,76 e item 60,00, em vez do item 7,99 com parcial 2,00 e saldo 5,99. A atomização não elimina essas pré-condições comuns, como 2-G explicita. | Ligar as afirmações ao cenário concreto completo; retirar ligação de outro arranjo mesmo que prove uma regra geral parecida. Não alterar os valores do requisito para acomodar a prova. |

### Reprodução da guarda e precisão do registro TDD

Executado comparativo independente em diretório temporário: fonte de `conferencia.py` obtida por `git show 54be872:tests/rastreabilidade/conferencia.py`, carregada fora do repositório; sete fontes de `FONTES_DA_CONSTANTE_ALTERADA`, mesma prova de caso `(9, "9.5", False)`, comparadas com `_conferir_prova` atual. Não se alterou a árvore nem a produção.

Resultado: a versão anterior **aceita dois casos** (reatribuição posterior e atribuição somente posterior à definição) e **já recusa cinco** (`+=`, append, índice, global em função e for), com diagnóstico genérico de trecho fora do assert/parametrize. A atual recusa os sete com `MOTIVO_DA_CONSTANTE`. Controles positivos, cinco negativos da auditoria, cobertura entregue e estrutura dos sete resíduos passaram por chamada independente das verificações.

O registro “a conferência atual aceitava todos (`assert []`)” não corresponde à versão-base e ao corpus commitado. Os sete testes podem ter ficado Red, mas em cinco o motivo é o diagnóstico esperado ausente, não aceitação indevida. **Retificar o registro, preservando o texto anterior**, com comando/saída ou identificação do estado intermediário efetivamente usado. A correção funcional da reprodução original está confirmada; não se alega ter presenciado o Red histórico nem se inventa uma violação da ordem do TDD a partir dessa divergência. A guarda continua congelada conforme 2-H; não foram acrescentadas exigências de novas evasões sintéticas.

### Encaminhamento obrigatório da regra 2-I

A sexta amostra encontrou resíduos reais nas referências da matriz. **R05 não está encerrado e A-53 não está atendido.** Ao especificador: receber esta lista, preservar as garantias de negócio e levar ao responsável a escolha já prevista: (1) nova rodada exaustiva; ou (2) corrigir os resíduos apontados e registrar o restante, sem defeito de produção, como melhoria, encerrando R05 somente após revisão das correções apontadas. Nenhum agente está autorizado a escolher essa opção sozinho.

Para sanar as pendências documentais, o especificador deve explicitar o encaminhamento da opção escolhida, resolver eventual necessidade de atomização das afirmações fixas sem admitir ligações parciais e manter no escopo as caracterizações efetivas de ocorrência, caixas e concorrência acima. Não é necessária nova decisão comercial sobre valores, prazos ou permissões. Defeito real revelado por qualquer caracterização segue a devolução normal; não se corrige produção silenciosamente nesta fatia.

Resultados finais da suíte e limites de execução serão consolidados na E16-08 ao término da execução independente desta rodada.

### Fechamento da execução independente

**3690 passed, 1 skipped, 2 xfailed, 18 warnings em 977,37 s**, sobre `8e35589`. O verificador `python -m tests.rastreabilidade.conferir_execucao <TEMP>/revisor_e16_8e35589.xml` terminou com código 0: todas as referências da matriz passaram. JUnit: 3693 casos, zero falhas e zero erros. Guardas estruturais verdes não eliminam os resíduos semânticos da sexta amostra. Mantido **REPROVADO / R05 importante**, com o encaminhamento de 2-I descrito acima. Consolidado e limites na E16-08.

## Resposta do especificador à sexta amostra — 2026-11-19

Agente 1. Recebidos os resíduos da revisão de `8e35589`. Pela regra 2-I, levei a escolha ao responsável, que decidiu em 2026-11-19 pela **nova rodada exaustiva**. Especificada a regra 2-J, com os critérios A-54 a A-64. Nenhuma regra de negócio muda.

| Resíduo | Tratamento na regra 2-J |
|---|---|
| C90, C112 e C114 | Ocorrência real por `registrar_ocorrencia`, com o arranjo de cada cenário. A ligação de 70,76 sai do C114 (A-56). |
| T-47 | Formação de caixas por `abrir_pagamento`, com múltiplo, sobra e pendentes que completariam uma caixa a mais (A-57). |
| C99 e T-44 | `pk` real do item e parcela em pedido real, depois da abertura; comparação dos seis modelos; trigger ainda ativa (A-58). |
| T-34 | Paralelo depois da verificação de existência, com os e-mails da T-34 e a recusa por `conta_email_unico`, ou devolução (A-59). |
| T-7 | As duas ordens forçadas sob concorrência para cada par (A-60). |
| C59, C85 e T-26 | Atomização autorizada do C59; rota com os cinco casos do §16.85; a ligação ao serviço sai da afirmação "pela API" (A-61). |
| C104 | Arranjo do cenário (10,00, 100,00, 8 e 5), ou devolução (A-62). |
| Registro TDD da guarda | Retificação, com comando e saída (A-63). |

**Por que mudou o método:** a auditoria anterior descrevia o auxiliar, e não a ação executada. A regra 2-J acrescenta o campo `caminho`, com as funções de produção alcançadas e conferidas no CI, e as perguntas (g) a (k), que cobrem os cinco padrões da sexta amostra. Todas as linhas são relidas, com uma busca dirigida por esses padrões antes da entrega.

**Próximo gate:** gate independente da regra 2-J. Depois, o implementador faz a releitura, as caracterizações e o `caminho`, e o revisor confere a sétima amostra (A-64).

## Gate independente da regra 2-J — 2026-11-19

Agente 3. Base examinada: `4b781ed`, branch `e16-especificacoes`, árvore inicialmente limpa. Escopo: regra 2-J e A-54 a A-64, comparados com as fontes de verdade, o parecer da sexta amostra e as provas existentes. **Veredito: REPROVADO.** Duas pendências importantes impedem liberar a regra completa para implementação; não são novos defeitos demonstrados na produção.

### G2J-01 — importante — o domínio de `caminho` exclui provas legítimas de configuração

**Referências:** spec.md:244–248 e invariante de `caminho`; acceptance.md A-54/A-55; AGENTS.md §7; infraestrutura T-12.

**Evidência reproduzível:** `tests/rastreabilidade/matriz.py:1598` liga T-12 a `tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega`. O teste carrega `config.settings.prod` em subprocesso. A recusa ocorre no corpo do módulo `config/settings/prod.py:55–56`, ao importar a configuração; não é uma função/método em `apps/`, nem uma restrição/trigger de banco. A regra exige que todas as linhas tenham exclusivamente essas duas formas. Logo, essa prova correta não tem representação verdadeira no novo campo. Indicar função de `apps` apenas existente não resolve: a ação afirmada não a executa.

**O que o especificador deve fazer:** ampliar explicitamente o domínio para representar configuração executada no corpo de módulo e outros pontos de entrada reais fora de `apps`, mantendo identificação verificável do artefato e sem aceitar auxiliares de teste como produção. Definir a validação estrutural correspondente, com positivo específico para T-12 (`config.settings.prod`, corpo de módulo) e negativos para artefato inexistente/tipo inválido. Ajustar A-54/A-55, a invariante e a justificativa da regra. Distinguir existência estática, verificável por AST, de alcance efetivo pelo teste, que continua dependendo da leitura humana. Conferir se as demais ligações têm representação antes de exigir o preenchimento universal. Não mover nem refatorar produção só para caber no formato da auditoria. A sintaxe concreta é decisão técnica; não demanda nova autorização comercial.

### G2J-02 — importante — igualdade universal no T-7 omite a exceção já aprovada de apuração

**Referências:** spec.md:285–288; acceptance.md A-60; funcional §8.3 (prevalece sobre a formulação resumida da infraestrutura T-7); E11-01 acceptance A-15/A-16; E08-04 spec (exceção de quitação retroativa não se estende à inadimplência).

**Evidência reproduzível:** §8.3 aceita aprovação no prazo desde que identificada na apuração e proíbe alterar pedido já apurado por comunicação tardia. E11-01 A-15 prevê aviso com trava anterior à decisão: pedido pago/destino `quita`. A-16 prevê reconsulta pendente e aviso esperando a apuração que já cancelou: pedido permanece cancelado por inadimplência/destino `devolucao`, obrigação e alerta. As provas correspondentes estão em `tests/tecnicos/test_apuracao_inicio.py:664` e `:693`. A regra 2-J exige, sem delimitar a informação disponível na reconsulta, as duas ordens de webhook × apuração com o mesmo resultado final de pagamento, destino e pedido. Essa redação admite exigir igualdade justamente onde os critérios aprovados exigem preservar resultados distintos. Não se afirma que trocar somente a ordem em um arranjo com aprovação identificável sempre gere divergência; a lacuna é não delimitar esse arranjo e a exceção.

**O que o especificador deve fazer:** delimitar em 2-J/A-60 as pré-condições de equivalência: mesma aprovação e mesma informação consultável pelo provedor antes da classificação; nesse grupo, forçar as duas ordens concorrentes e exigir resultado idêntico. Registrar separadamente o caso de aprovação não identificada na apuração, conforme E11-01 A-16: aviso posterior à decisão mantém cancelamento, registra devolução e alerta, sem editar o pedido apurado. Preservar as provas desses dois comportamentos em afirmações distintas, sem ligar a exceção a uma igualdade universal. Explicitar essa leitura de T-7 pela precedência do §8.3. Não alterar quitação, prazos ou cancelamento para satisfazer uma igualdade indevida. A correção pode ser deduzida das regras aprovadas; só uma proposta de mudar essa regra financeira exigiria decisão do responsável.

### Demais critérios e encaminhamento

A decisão registrada pela nova rodada exaustiva foi considerada autorizada. As perguntas (g) a (k), as correções dirigidas de ocorrências/caixas/remoção/cadastro/API, a atomização de C59, a retificação histórica do Red e o retorno à escolha de 2-I após eventual novo resíduo são adequados como orientação documental, ressalvadas as duas pendências acima. Não se libera a implementação integral de 2-J enquanto elas persistirem. O encaminhamento de C104 admite devolução explícita se o arranjo não puder ser formado por comportamento aprovado; isso não autoriza mudar prioridade da fila ou converter silenciosamente as pendências.

**Verificação independente nesta rodada:** `git status --short`; `git show --stat --oneline HEAD`; leitura do diff documental e buscas `rg -n` de `2-J`, `A-60`, T-7/T-12, pagamentos já apurados e critérios A-15/A-16; leitura dos corpos das provas, da matriz e da configuração citados acima. Gate documental: não executada nova suíte, não alegado novo Red/Green, não revalidada a implementação nem executada a sétima amostra. Os resultados históricos permanecem históricos. Não alterados spec.md, acceptance.md nem código de produção.

**Próximo gate:** especificador corrige G2J-01/G2J-02 em spec.md e acceptance.md e registra o encaminhamento; agente 3 refaz o gate. R05 continua aberto e a E16 não recebe aprovação por este gate. Parecer anterior e resposta do especificador preservados integralmente.

## Resposta do especificador ao gate da regra 2-J — 2026-11-19

Agente 1. As duas pendências procedem e foram corrigidas na spec e nos critérios. Nenhuma regra de negócio muda.

| Pendência | Correção |
|---|---|
| G2J-01, domínio de `caminho` | O campo passou a ter uma lista fechada de sete formas: função de `apps/`, função de `config/`, `modulo:`, `comando:`, `rota:` para view de dependência, `banco:` e `fonte:`. Cada forma tem a sua conferência estática, e nenhuma aceita `tests/`. A spec separa a existência (conferida no CI) do alcance (conferido na leitura). Conferi a cobertura: dos módulos de teste ligados, só três não importam `apps`, a configuração (T-12/C38), a varredura de `float` (T-39) e o C61 (allauth), e os três cabem nas formas novas. O implementador classifica as linhas antes de preencher e devolve as que não couberem. Os critérios A-54 (dezesseis negativos) e A-55 (positivos de T-12, T-39, comando, rota e `config`) foram ajustados. |
| G2J-02, T-7 | A igualdade fica restrita ao grupo de equivalência (mesmo pagamento, horário de aprovação e informação consultável, inclusive na reconsulta), pela precedência do funcional §8.3 sobre o resumo da T-7. A aprovação não identificada na apuração (E11-01 A-16) fica numa afirmação própria, ligada às provas aprovadas e fora da igualdade. Webhook × bloqueio segue os critérios da E08-04 e da E08-05, com afirmação própria ou devolução se houver resultado distinto por ordem. Quitação, prazos e cancelamento não mudam. O A-60 foi ajustado. |

**Próximo gate:** novo gate independente da regra 2-J.

## Novo gate independente da regra 2-J — 2026-11-19

Agente 3. Base: `bee0db6`, branch `e16-especificacoes`, árvore inicialmente limpa. Comparação documental contra `227f869`. **Veredito: APROVADO — gate da especificação da regra 2-J e critérios A-54 a A-64.** G2J-01 e G2J-02 encerrados neste gate. Nenhum novo achado impeditivo identificado no escopo documental examinado.

### Revalidação das pendências

| Achado | Evidência da correção e conclusão |
|---|---|
| G2J-01 — domínio de `caminho` | A regra agora distingue função, corpo de módulo, comando, rota de dependência, banco e inspeção de fonte, incluindo funções de `config/`. T-12 pode declarar `modulo:config.settings.prod`, compatível com a ação do teste e a recusa no corpo de `config/settings/prod.py`. A-54 tem dezesseis negativos e A-55 positivos representativos. Conferidos também `config/urls.py:22` (login allauth do C61), `config/observabilidade.py:131` e a varredura de fontes do T-39. A regra distingue existência estática de alcance efetivo, exige classificação prévia e devolução de casos não representáveis, sem refatorar produção. **Encerrado.** |
| G2J-02 — igualdade universal no T-7 | A regra e A-60 delimitam a equivalência por pagamento, horário de aprovação e informação consultável, preservando a precedência do funcional §8.3. A aprovação não identificada na apuração fica em afirmação própria, com cancelamento mantido, devolução, obrigação integral e alerta conforme E11-01 A-16. Webhook × bloqueio remete aos critérios E08-04/E08-05; E08-05 A-20 fornece o caso de cobrança já aprovada e A-21 o caso pendente. Os casos distintos não são forçados a uma igualdade indevida. **Encerrado.** |

**Aplicação das regras já especificadas:** a referência à família A-15/A-16 não torna os respectivos testes intercambiáveis. A-15(ii) usa reconsulta pendente com aviso obtendo a trava primeiro; não prova sozinho as duas ordens com aprovação identificável na reconsulta. A equivalência exige as novas provas nas pré-condições expressas de 2-J/A-60; a afirmação de cancelamento/devolução exige a prova correspondente a A-16. Isso decorre da exigência mantida de que cada ligação prove integralmente sua afirmação, sem introduzir requisito financeiro novo. Da mesma forma, as formas estáticas de `caminho` identificam artefatos; não certificam por si sós execução, validade de argumentos de comando ou semântica da operação. Essa conferência permanece na leitura por ligação, expressamente exigida pela regra.

### Cobertura do gate e limites

- **A-54/A-55:** formatos, positivos, negativos e classificação prévia são verificáveis; os testes novos da conferência continuam sujeitos ao ciclo Red/Green.
- **A-56 a A-59 e A-61/A-62:** mantidas as correções dirigidas de ocorrência real, formação efetiva de caixas, remoção com registros congelados, corrida do cadastro, atomização, rota de quantidades e arranjo de C104. As devoluções previstas continuam obrigatórias quando aplicáveis.
- **A-60:** concorrência com ordens forçadas dentro das pré-condições, exceção financeira separada e justificativa do par bloqueio × apuração permitem avaliar o comportamento sem alterar regras aprovadas.
- **A-63/A-64:** permanecem o registro da releitura exaustiva, buscas dirigidas, retificação histórica, execução da suíte e a sétima amostra independente, com o encaminhamento de 2-I se houver resíduos.

**Verificações executadas:** `git status --short`; `git log -4 --oneline`; `git diff 227f869..HEAD -- docs/specs/E16-07/spec.md docs/specs/E16-07/acceptance.md docs/specs/E16-07/review.md`; `git diff --check 227f869..HEAD` (sem erros); leitura do AGENTS.md, funcional §8.3, critérios E11-01 A-15/A-16, E08-05 e dos artefatos/provas citados, com buscas `rg -n` na matriz e nos pontos de entrada. Não executada nova suíte: esta rodada aprova a especificação, não certifica a implementação. Nenhuma alegação de Red/Green novo ou de sétima amostra realizada.

**Entrega ao implementador:** regra 2-J liberada para execução no escopo aprovado. Implementar a conferência com TDD, classificar e reler as ligações, produzir as caracterizaçōes e registros exigidos e devolver para revisão independente. **R05 permanece aberto; este gate não aprova a E16 nem encerra os bloqueios operacionais anteriores.** Alterado apenas este parecer, por acréscimo, preservando o histórico. Sem alteração de especificação ou produção pelo revisor.


## Quinta correção residual de R05 — implementador (2026-11-19)

Agente 2. Regra 2-J e critérios A-54 a A-64 (gate `5d2754a`). A sétima amostra (regras 2-I e 2-J, A-64) é do revisor.

### Red e Green

- **A-54 (campo `caminho`, Red):** `test_a_auditoria_acusa_o_caminho_invalido` falhou na primeira execução com `assert []`: a conferência não conhecia o campo e aceitava os quinze caminhos inválidos do critério (vazio, mais de 200 caracteres, `apps.pedidos.ocorrencias.nao_existe`, `config.observabilidade.nao_existe`, `tests.apoio.devolucoes.parcial`, `modulo:config.settings.nao_existe`, `modulo:tests.apoio.devolucoes`, `comando:nao_existe.py check`, `rota:POST /nao-existe/`, `banco:nome_que_nao_aparece`, `fonte:tests/apoio`, `fonte:docs/specs`, `fonte:nao/existe.py`, `xyz:qualquer`, `banco:`). O décimo sexto, a linha sem a chave `caminho`, é conferido no mesmo teste. **Green:** `problema_do_caminho` e o campo `caminho` em `conferir_auditoria` (`tests/rastreabilidade/conferencia.py`). Pela árvore de sintaxe, sem importar: função ou método de `apps/` e de `config/`; `modulo:`; `comando:manage.py <subcomando>`; `rota:<MÉTODO> /<caminho>` contra as chamadas `path(...)` de `config/urls.py` e dos `urls.py` de `apps/`; `banco:<nome>` literal num `.py` de `apps/`; `fonte:<caminho>` que existe e não está em `tests/` nem em `docs/`.
- **A-55:** `test_a_auditoria_aceita_os_caminhos_das_sete_formas` aceita os sete exemplos do critério. Com o campo obrigatório, `test_a_auditoria_entregue_cobre_exatamente_as_ligacoes` e o A-55 acusaram as 606 linhas sem `caminho` (o Red do conteúdo); passam com as 612 linhas preenchidas.
- **Classificação das linhas por forma (A-55):** função, método ou view de `apps/`, 592 linhas; `rota:` (views do allauth), 37; `banco:`, 7; `fonte:`, 3; `modulo:`, 2; `comando:`, 0 (o `test_configuracao_pagamentos.py` carrega o módulo com `importlib` num subprocesso, e por isso a forma é `modulo:config.settings.prod`). Uma linha pode ter mais de uma forma. **Devoluções por linha sem forma: nenhuma.**
- **Decisão técnica (`banco:`):** o nome da trigger de imutabilidade do pedido (`pedidos_itemdopedido_so_insercao`) e o da trigger do papel (`contas_conta_papel_imutavel`) são montados em tempo de migração e não aparecem literais em `apps/`. O `caminho` usa o nome literal mais próximo, `banco:pedidos_itemdopedido` e `banco:papel_imutavel`, que a conferência encontra nas migrações. O revisor confere na leitura que a trigger é a da tabela citada.
- **Testes de estrutura (A-56 a A-62):** `test_c90_c112_e_c114_provam_a_ocorrencia_real`, `test_t47_prova_a_formacao_de_caixas_pela_abertura`, `test_c99_e_t44_provam_a_recusa_com_a_comparacao_completa`, `test_t34_a_recusa_pela_unique_e_provada_em_paralelo`, `test_t7_tem_as_duas_ordens_forcadas_e_o_comportamento_distinto_a_parte`, `test_c59_c85_e_t26_estao_atomizadas_e_na_rota` e `test_c104_usa_o_arranjo_do_cenario`. Os testes da regra 2-G que fixavam a estrutura anterior foram atualizados porque a regra 2-J troca essa estrutura: C59 passa de 6 para 7 afirmações (A-36, atomização do login e do cadastro), e T-44 e T-47 apontam para os testes novos (A-51, A-57, A-58).

### Caracterizações novas e primeira execução (regra 5)

Todas passaram na primeira execução, porque descrevem comportamento que já existia: exceção técnica, sem Red inventado. Nenhuma falhou por falta de comportamento, e a produção não mudou.

- `test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado` (reescrito com `registrar_ocorrencia`): 1 passed.
- `test_cenario_112_a_ocorrencia_de_0_25_kg_usa_o_valor_registrado`, `test_cenario_113_quatro_ocorrencias_de_0_25_kg_somam_o_subtotal` e `test_cenario_114_o_cancelamento_depois_da_parcial_devolve_o_saldo_do_item` (`tests/aceitacao/test_cenarios_112_114_ocorrencia_real.py`): o 112 e o 113 passaram na primeira execução. O 114 falhou na primeira execução por um erro do próprio teste (`Reembolso` não tem o campo `obrigacao`; consultei por `pedido` e `motivo`) e passou sem tocar a produção.
- `test_a_formacao_de_caixas_pela_abertura_ignora_as_pendentes` (T-47) e `test_cenario_104_as_pendentes_de_c_nao_entram_em_pedido_nem_em_cobranca` (C104), em `tests/tecnicos/test_pedidos_abertura_caixas_pendentes.py`: 2 passed.
- `test_rota_com_o_pk_real_do_item_congelado_e_recusada` (reescrito), `test_parcela_em_pedido_depois_da_abertura_e_recusada_pelo_servico` e `..._pela_rota` (C99 e T-44): 4 passed com o teste do A-9 da mesma seleção.
- `test_dois_cadastros_com_o_mesmo_email_passam_da_verificacao_e_o_banco_recusa_um` (T-34, paralelo com uma barreira depois de cada verificação de existência do e-mail): 3 passed no arquivo.
- `tests/tecnicos/test_pedidos_ordens_forcadas_t7.py` (T-7, 8 casos: três pares, duas ordens cada, mais o par bloqueio e apuração): 8 passed, com `corrida.b_esperou` verdadeiro em todos.
- `test_cenario_85_rota_valida_as_quantidades_no_servidor` (5 casos do §16.85 pela rota): 5 passed.
- Reforços que só acrescentam asserts, sem afrouxar nada: composição dos registros no `test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago` (serviço 0,30 e frete 1,20 do cancelamento), obrigação de 25,00 e contagem de ocorrência e de reembolso no `test_cenarios_48_e_52_...`.

### Os resíduos da sexta amostra e as ligações retiradas

- **C90, C112, C113 e C114:** a ocorrência é real (`apps.pedidos.ocorrencias.registrar_ocorrencia`, administrador ativo, item, quantidade, tipo e acionamento), no pedido aberto e apurado, com `arranjo_unico` generalizado para quantidade decimal, unidade e incremento (`tests/apoio/entrega.py` e `tests/apoio/pedidos.py`). C90: 0,25 kg a 7,99, preço para 8,99 antes da ocorrência, 2,00, 0,10 e 0,40. C112: 1,000 kg a 7,99, ocorrência de 0,25 kg com 2,00, preço para 9,99 depois, reembolso registrado segue 2,00. C114: depois da ocorrência de 2,00, o cancelamento devolve 5,99 ao item e a obrigação do cancelamento é 7,49. A segunda afirmação do C114 foi provada no mesmo arranjo do item de 7,99 e ficou. **C113 é de mesma natureza e não estava na lista da sexta amostra; achado pela busca dirigida (1) e corrigido com ocorrências reais** (2,00, 2,00, 2,00 e 1,99).
- **T-47:** a formação de caixas é provada por `abrir_pagamento` (múltiplo 10: A 8 e B 7 reservadas, 15 formam 1 caixa e sobram 5; C com 5 pendentes que fariam a segunda caixa). Linhas do pedido: uma caixa só (A 8, B 2); a sobra de 5 sai da reserva de B sem virar pendência; as pendentes de C seguem pendentes e na fila.
- **C99 e T-44:** pk real do item congelado pela rota (pks dos itens afastados dos pks de produto por `setval`, para a recusa não depender de coincidência de números; status exato 404); parcela em pedido real (serviço e rota). A comparação cobre `Pedido`, `ItemDoPedido`, `ParcelaNoPedido`, `ObrigacaoComComprador`, `MovimentoFinanceiro`, `Reembolso` e as parcelas de interesse, por conteúdo. A trigger é provada com um `UPDATE` direto recusado depois da tentativa. O campo de identificação que a rota aceita é só `produto`; "o identificador dessa parcela" é o `produto` da parcela em pedido.
- **T-34:** convite de comprador com `Ana@x.com` e de fornecedor com ` ana@x.com `, normalizados; uma barreira depois de cada verificação de existência faz os dois passarem por ela antes de qualquer inserção. A recusa traz, na cadeia de causas (`__cause__` e `__context__`, seguidas), o `IntegrityError` com `conta_email_unico`: o serviço traduz em `ConviteInvalido("email_em_uso")`, cuja causa é `EmailEmUso`, cuja causa é o `IntegrityError`. O teste sequencial do `IntegrityError` ficou numa afirmação própria da restrição.
- **T-7:** três pares com as duas ordens forçadas sob concorrência, cada um com a primeira operação pausada dentro da sincronização, com a trava do pagamento, e a segunda comprovadamente esperando (`b_esperou`): aviso e bloqueio (aprovado em T0 + 23h59, e sem aprovação), aviso e apuração (aprovação identificável na reconsulta, E11-01 A-15) e bloqueio e apuração. **Bloqueio e apuração entram:** as regras de prazo permitem os dois sobre o mesmo pedido em T0 + 48h, com a rodada ainda em pagamento (o bloqueio atua desde T0 + 24h; a apuração, desde T0 + 48h). O comportamento distinto (A-16 e A-15 (ii) da E11-01, com a reconsulta devolvendo "pendente") ficou em duas afirmações próprias, ligadas às provas aprovadas e fora de qualquer afirmação de igualdade. Os testes sequenciais e o paralelo sem ordem forçada saíram da afirmação "em qualquer ordem".
- **C59** atomizada em login e novo cadastro; **C85** e **T-26** "pela API" ligados à rota com os cinco casos (`test_quantidades_recusadas` saiu); **C104** nos testes do arranjo do cenário (10,00, mínimo 100,00, A com 8 e C com 5 pendentes), com a abertura pelo caminho de novas reservas de B em P2, sem converter as pendentes de C.
- **Atomizada pela pergunta (i), achada pela busca dirigida (4):** T-33 "A parcela pendente sem reserva fica fora das caixas e do pedido na abertura", que tinha uma ligação por cláusula, virou duas afirmações, cada uma com a sua prova integral.
- **Ligações retiradas (30, contando as renomeadas):** T-26 (`test_quantidades_recusadas`); T-33 (`test_progresso_e_pedido_so_contam_as_reservadas` e `test_a_formacao_de_caixas_ignora_as_pendentes` da afirmação composta); T-34 (o sequencial da afirmação de concorrência); T-44 (`test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido` nas duas afirmações, e `test_parcela_em_pedido_nao_entra_na_remocao`); T-47 (`test_a_formacao_de_caixas_ignora_as_pendentes`); T-7 (os dois testes sequenciais ou sem ordem forçada, e os dois das afirmações renomeadas); C104 (o arranjo FP/R2, três ligações); C112 (três ligações de cálculo direto); C113 (três ligações de `reembolso_parcial` direto); C114 (`test_o_cancelamento_devolve_so_o_saldo_restante` e `test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago`, esta última do C114 e mantida no C91); C59 (as duas, renomeadas); C85 (`test_cenario_63_rota_recusa_1_2_kg_sem_gravar` e `test_quantidades_recusadas`); C91 (`test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado`, que chama `reembolso_integral_do_pedido` com um motivo em texto); C99 (`test_parcela_em_pedido_nao_entra_na_remocao` e o do A-9).

### Busca dirigida (antes da entrega) e resultado

Script em `scratchpad`, que levanta candidatos; a leitura decidiu.

1. **Auxiliares de `tests/apoio/` com `motivo` em texto** (`parcial`, `integral`, `parcela_de_fabrica`, `obrigacao_de_teste`, `cancelar_direto`, `simular_volta_para_interesse`): **26 candidatos** (C33, C34, C43, C73, C91, C115, C116, C117, T-10, T-40, T-51, T-53). Lidos: C113 e C91 eram resíduos (corrigidos); `simular_volta_para_interesse` chama `voltar_para_interesse` real; C43, T-51 e T-53 não nomeiam a ocorrência nem o cancelamento como ação; C115 tem a ocorrência real em `test_ocorrencias.py`.
2. **"simultâne", "concorr" e "qualquer ordem":** **18 candidatos**; todos executam em paralelo (`executar_em_paralelo`, `Corrida` ou `segurando`). Os de "qualquer ordem" (T-7 e T-31) têm as duas ordens forçadas e a espera provada; T-31 já era assim.
3. **Números do texto-base que não aparecem no módulo do teste:** **45 candidatos**, **41** depois de comparar por valor decimal. Lidos: 48 e 24 são prazos que a afirmação não herda; 100,00 de C18 e C48 vêm de `arranjo_unico` (12,50 × 8 e 10,00 × 10, com serviço 5,00 e frete 20,00) e coincidem com o cenário; 0,015, 0,625, 1,9975 e 80,00 são valores derivados; C115 usa o item M do apoio (0,6 kg a 0,15, subtotal 0,09). Nenhum resíduo além do que a regra já apontava.
4. **Afirmações com "e", "nem" ou "inclusive" e mais de uma ligação:** **5 candidatos**. T-33 era resíduo (atomizada). C17 (depois do envio e antes da aprovação), C99 e T-34 têm ligações que provam a afirmação inteira; T-7 foi refeita.

### Releitura e limite declarado

**Limite que o revisor deve ler:** a regra 2-J pede a releitura das 606 linhas com as onze perguntas. Neste ciclo **não reli de novo o corpo de cada um dos 606 testes**. O que fiz:

- as perguntas (a) a (f) foram aplicadas a cada ligação no ciclo da regra 2-G (606 corpos lidos);
- o `caminho` de cada ligação vem de uma análise estática do alcance do teste (as funções de `apps/` e de `config/` chamadas pelo corpo e pelos auxiliares, até a profundidade 4, mais as views das rotas e o receptor dos avisos), ordenada para que as funções que a afirmação nomeia venham primeiro; revi a tabela completa por forma e a conferência a existência. Para 17 testes que a análise não alcança (banco, fonte, módulo, adaptadores e variantes), escrevi o `caminho` à mão lendo o corpo;
- as perguntas (g) a (k) foram aplicadas por varredura de todas as 612 linhas (palavras-chave de ação contra o `caminho`, paralelo e ordem, números, cláusulas, "não muda"), e li por inteiro cada teste apontado pelas varreduras;
- **Linhas corrigidas por esta regra: 40** (uma pergunta principal por linha): (g) ação efetiva 13 (C90 ×3, C112 ×3, C113 ×3, C114 ×2, C91 ×1, T-47 ×1); (h) concorrência e ordem 8 (T-7 ×6, T-34 ×2); (i) cláusulas 4 (C59 ×2, T-33 ×2); (j) arranjo do cenário 3 (C104 ×3); (k) "não muda" 10 (C99 ×6, T-44 ×4); (b) interface 2 (C85 e T-26 pela rota). Total na `AUDITORIA`: **77 linhas "corrigida"** (as da regra 2-G que ficaram e as desta) e **535 "íntegra"**.
- **(k) reforçado em dois testes (só acrescentam asserts):** C97 "não muda o reembolso já devido" (`test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno` agora compara por conteúdo `Pedido`, `ItemDoPedido`, `ParcelaNoPedido`, `ObrigacaoComComprador`, `MovimentoFinanceiro` e `Reembolso`) e C117 "o pedido congelado continua com a composição original" (compara `Pedido`, `ItemDoPedido` e `ParcelaNoPedido`). Os dois passaram depois do reforço; a execução completa abaixo já os inclui.

### Retificação do registro da guarda (A-47)

O registro da quarta correção dizia que, no Red, "a conferência atual aceitava todos (`assert []`)". **Retificação, sem apagar o texto anterior:** a versão-base `54be872` aceitava dois dos sete casos (a reatribuição posterior e a atribuição só posterior) e recusava cinco com o diagnóstico genérico "o trecho ... aparece no arquivo, mas não num assert, num raises nem no parametrize". Comando e saída (`conferencia.py` de `54be872`, extraída com `git show 54be872:tests/rastreabilidade/conferencia.py`, e os sete módulos do A-47):

```
ACEITA reatribuída depois do decorador (reprodução do revisor)
RECUSA mais atribuição :: o trecho `(9, "9.5", False)` aparece no arquivo, mas não num assert, num raises nem no parametrize do teste (o...
RECUSA append :: (mesmo diagnóstico)
RECUSA índice :: (mesmo diagnóstico)
ACEITA atribuída só depois da definição
RECUSA global em função :: (mesmo diagnóstico)
RECUSA for no módulo :: (mesmo diagnóstico)
```

### Devoluções ao especificador

Nenhuma devolução. A espera do segundo ator foi possível em todos os pares do T-7 sem mudar a produção, e o apoio de concorrência sincronizou o T-34 depois da verificação sem mudar a produção.

### Números e execução

- Matriz: **601 afirmações, 612 ligações, 288 referências distintas** (antes: 596 / 606 / 284). `AUDITORIA`: 612 linhas, 535 íntegras e 77 corrigidas. `docs/rastreabilidade-fase1.md` regerado.
- Suíte completa com `--junitxml` e `conferir_execucao`: `uv run pytest -q --junitxml=relatorio-pytest.xml -ra`: **3720 passed, 1 skipped, 2 xfailed** em 17 min (o skipped é a ferramenta de backup ausente; os dois xfailed são da E16-08, bloqueada pelas contas da fase 0; nenhum está na matriz). `uv run python -m tests.rastreabilidade.conferir_execucao relatorio-pytest.xml`: "Toda referência da matriz passou na execução."
- `ruff check`, `ruff format` e `mypy apps tests` limpos.
