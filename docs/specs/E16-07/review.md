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
