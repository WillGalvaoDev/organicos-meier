# E16-07 — Rastreabilidade dos cenários 1 a 119 e dos testes T-1 a T-55

Fatia 7 de 8 da milestone **E16 — Homologação e encerramento da fase 1**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

O critério de saída da fase 1 (infraestrutura 7) exige:
- os cenários 1 a 119 da especificação (§16) passando contra o simulador;
- os testes técnicos T-1 a T-55 (infraestrutura 8) passando, com evidência do ciclo Red → Green → Refactor.

As especificações das E01 a E15 citam todos os cenários e testes técnicos nas colunas "Origem" dos critérios. Os testes, porém, citam só parte deles: 87 cenários e 35 testes técnicos aparecem por número no código. Ninguém consegue hoje dizer, sem ler 110 especificações, que teste prova cada cenário.

Esta fatia cria:
- uma matriz versionada, cenário → testes;
- a conferência automática de que todo cenário e todo teste técnico têm pelo menos um teste existente;
- o documento gerado que o relatório final (E16-08) usa como evidência.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 7, critério de saída | Cenários 1 a 119 e T-1 a T-55 passando contra o simulador, com evidência do ciclo TDD. |
| Infraestrutura 8 | A tabela T-1 a T-55. |
| Especificação §16 | Os cenários 1 a 119. |
| AGENTS.md §8 | Requisitos e critérios referenciados e atendidos. |

## Escopo

**Dentro:**
- o módulo da matriz;
- o teste de cobertura da matriz;
- o gerador do documento e o documento `docs/rastreabilidade-fase1.md`;
- testes novos só para cenários ou testes técnicos sem nenhum teste que os prove.

**Fora:**
- reescrever testes existentes;
- mudar comportamento de produção. Um cenário que falhe por defeito real vira achado, devolvido ao especificador, e não correção silenciosa nesta fatia.

## Regras

1. **Matriz:** `tests/rastreabilidade/matriz.py` define:
   - `CENARIOS: dict[int, list[str]]`, com as chaves exatamente de 1 a 119;
   - `TECNICOS: dict[str, list[str]]`, com as chaves exatamente de `T-1` a `T-55`.

   Cada valor é uma lista não vazia de referências `caminho/do/arquivo.py::nome_do_teste` ou `caminho::Classe::nome_do_teste`, relativas à raiz do repositório, sem parâmetros. A matriz é escrita à mão, a partir das colunas "Origem" dos `acceptance.md` e da leitura dos testes.
2. **O que conta como prova:** um teste prova um cenário quando exercita o comportamento observável descrito nele, como positivo ou negativo, e confere o resultado que o cenário pede.
   - Um cenário com várias afirmações pode precisar de mais de um teste. A lista inclui todos os necessários para cobrir cada afirmação.
   - Um teste citado só porque toca no mesmo módulo não conta.
2-A. **Afirmações explícitas** (correção E16-R05, revisão de 2026-11-17).
   - **Formato:** os valores de `CENARIOS` e `TECNICOS` passam a ser `dict[str, list[str]]`. Cada chave é uma afirmação verificável do texto-base, com até 140 caracteres, escrita a partir dele, e o valor é a lista de testes que provam aquela afirmação.
   - **Todas as afirmações:** um texto com N afirmações tem N chaves.
   - **Repetição:** o mesmo teste pode aparecer em afirmações diferentes, mas não duas vezes na mesma.
   - **Conferência:** a da regra 3 passa a exigir pelo menos uma afirmação por entrada, cada uma com texto não vazio e lista não vazia. A regra de duplicata vale dentro de cada afirmação.
   - **Documento:** na coluna dos testes, o documento da regra 4 mostra cada afirmação seguida dos testes dela.
2-B. **Conferência semântica integral:**
   - o implementador lê o corpo (preparação, ação e asserções) de todos os testes citados nas 174 entradas e confirma, em cada afirmação, que algum assert confere o resultado pedido;
   - o `review.md` registra o resultado de cada entrada: "mantida", "completada" (com as referências acrescentadas) ou "caracterização nova" (com o teste da regra 5);
   - nome de função e comentário `A-n` não bastam como prova.
2-C. **Lacunas já apontadas pelo revisor:**
   - **Cenário 2** ("Login por Google ou link não contorna convite, suspensão ou banimento."): seis afirmações, uma para cada combinação dos canais Google e link com cada restrição:
     - sem conta (sem convite), o canal não cria conta nem abre sessão;
     - com conta suspensa, o canal abre sessão, mas a restrição da suspensão continua: o comprador não consegue adicionar interesse (especificação, seção 2);
     - com conta banida ou removida, o canal não abre sessão.
   - **T-40** ("Reembolso do item inteiro depois de mudança de preço no catálogo usa o subtotal do snapshot. A soma da devolução integral bate com os valores cobrados registrados."):
     - duas afirmações;
     - a primeira precisa de um teste que mude o preço do produto no catálogo **depois** do pagamento, reembolse o item **inteiro** e confira que o valor devolvido é o subtotal registrado, diferente do novo preço vezes a quantidade;
     - se nenhum teste existente fizer isso, entra o teste de caracterização `test_t40_reembolso_do_item_inteiro_depois_de_mudar_o_preco` (regra 5).

2-D. **Prova escrita por referência** (correção residual E16-R05, revalidação de 2026-11-18). A conferência por aderência de termos não atende à regra 2-B. Para que a leitura integral fique verificável:
   - **Formato:** cada afirmação passa a mapear cada referência para a sua prova: `dict[str, dict[str, str]]` (afirmação → {referência → prova}). A prova é um texto de até 200 caracteres que diz o que o teste prepara e o que o assert confere, em relação à afirmação.
   - **Trecho literal:** a prova contém, entre crases, pelo menos um trecho copiado literalmente do código. O trecho precisa estar dentro de um `assert` ou de um `pytest.raises(...)`:
     - da própria função de teste;
     - ou de uma função do mesmo módulo que ela chama pelo nome.
   - **Conferência automática:** a da regra 3 confere, lendo a árvore de sintaxe e o texto do arquivo, que cada prova tem texto, que tem o trecho entre crases e que o trecho aparece num desses lugares. Prova vazia, sem trecho ou com trecho que não está num assert é acusada com a referência.
   - **O limite:** a conferência automática prova que o implementador abriu o corpo e apontou um assert real. Ela não prova que o assert basta para a afirmação: isso continua sendo a leitura do implementador (regra 2-B) e a amostra do revisor (A-19).
   - **Exemplos já apontados, que precisam ser corrigidos** (não bastam esses três; a correção vale para todas as 679 ligações):
     - **cenário 17:** o webhook repetido não duplica pagamento, pedido, mensagem formal nem estorno, e cada parte precisa de um teste que **envie o webhook repetido**. Um teste que só chama `emitir_evento` duas vezes não prova webhook, pagamento, pedido nem estorno;
     - **cenário 25:** um teste com a aprovação em `T0 + 30h` e a notificação recebida depois de `T0 + 48h`, com o resultado que o cenário pede. Se nenhum existir, entra uma caracterização (regra 5);
     - **T-11**, primeira afirmação: um teste que tente usar os recursos do fornecedor A para tarifa, déficit ou obrigação de B e confira a recusa. Dois repasses da própria conta A não provam isso.
   - **Ligação sem prova:** é retirada da afirmação. Se a afirmação ficar sem nenhuma, entra uma caracterização (regra 5). Se a caracterização falhar, é defeito e volta ao especificador.
   - **Registro no `review.md`:**
     - os números: pares antes e depois, ligações retiradas, ligações acrescentadas e caracterizações novas;
     - a declaração de que todas as provas foram escritas pela leitura do corpo, sem classificação automática por termos.

3. **Conferência automática:** `tests/rastreabilidade/test_matriz.py` verifica que:
   - as chaves são exatamente as da regra 1, sem faltar nem sobrar;
   - cada referência aponta para um arquivo existente em `tests/` e para uma função `test_*` (ou método numa classe `Test*`) definida nele. A conferência é feita lendo a árvore de sintaxe do arquivo, sem importar nem rodar o teste;
   - a referência é coletável pelo pytest e não é pulada nem falha por expectativa (regras 3-A e 3-B);
   - nenhuma referência se repete na mesma lista.
3-A. **Coleta** (correção E16-R06, revisão de 2026-11-17). A referência só vale se o pytest a coletaria com a configuração do projeto (`pyproject.toml`, sem `python_files`, `python_classes` ou `python_functions` próprios):
   - o arquivo se chama `test_*.py` ou `*_test.py`;
   - cada classe da cadeia começa com `Test`, não define `__init__` e não tem `__test__ = False`;
   - o módulo não tem `__test__ = False`;
   - a função começa com `test_` e é filha direta do módulo ou da última classe da cadeia;
   - se o mesmo nome for definido mais de uma vez no mesmo corpo, vale a última definição, como no Python.
3-B. **Pulos e falhas esperadas** (correção E16-R06).
   - **Onde se procura:** na função, em cada classe da cadeia e no `pytestmark` do módulo, seja `Assign` ou `AnnAssign`, com um valor só ou com lista ou tupla.
   - **O que recusa a referência:**
     - `skip`, em qualquer forma;
     - `skipif` com qualquer condição, posicional ou `condition=`, inclusive em texto. A única exceção é a constante literal `False`. A conferência não executa código e não sabe avaliar uma condição como `os.environ.get("CI") == "true"`, que pode ser verdadeira no CI. Por isso, um teste que pula fora do CI não serve de evidência na matriz. A matriz cita só testes que sempre rodam;
     - `xfail`, em qualquer forma: um teste com falha esperada não prova o comportamento;
     - chamadas a `pytest.skip(...)`, `pytest.xfail(...)` e `pytest.importorskip(...)` no corpo da função de teste ou no nível do módulo, fora de funções.
   - **Formas reconhecidas:** `pytest.mark.<marca>`, com ou sem chamada; `<apelido>.mark.<marca>`, com `import pytest as <apelido>`; `mark.<marca>`, com `from pytest import mark`; e `skip`, `xfail` e `importorskip` importados de `pytest`.
   - **Limite declarado:** o pulo feito por fixture ou por `conftest.py` não é visto pela árvore de sintaxe. Para cobri-lo, o `review.md` registra a lista de testes pulados ou com falha esperada da última execução completa do CI (saída de `-ra`) e confirma que nenhum está na matriz.

3-C. **Formas residuais** (correção residual E16-R06, revalidação de 2026-11-18). A conferência passa a **falhar fechada**: o que a árvore de sintaxe não consegue provar que roda é recusado. Em particular:
   - **`pytestmark` de classe:** o `pytestmark` definido no corpo de qualquer classe da cadeia é examinado como o do módulo. Isso vale para `Assign` e `AnnAssign`, com um valor só ou com lista ou tupla.
   - **`skipif` com várias condições:** o pytest pula quando qualquer condição é verdadeira. A referência só é aceita se **todas** as condições, posicionais ou `condition=`, forem a constante literal `False`. Um `skipif` sem condição também é recusado.
   - **`__test__`:** examinado no módulo e em cada classe da cadeia, como `Assign` ou `AnnAssign`. Só a constante literal `True` é aceita. Outro valor, inclusive um nome ou uma expressão, recusa a referência.
   - **Atribuição que não se pode analisar:** recusa a referência qualquer outra forma de definir `pytestmark` ou `__test__` no módulo ou na classe:
     - atribuição aumentada (`pytestmark += ...`);
     - chamada de método (`pytestmark.append(...)`);
     - `setattr`;
     - `globals()[...]`;
     - desempacotamento em tupla;
     - definição dentro de `if`, `try` ou `with` no nível do módulo ou da classe.
   - **Motivo citado:** a mensagem de recusa diz a forma encontrada (por exemplo, "pytestmark da classe TestExemplo com skip").

4. **Documento gerado:** `python -m tests.rastreabilidade.gerar` escreve `docs/rastreabilidade-fase1.md` com duas tabelas:
   - "Cenários (§16)": número, um resumo de até 100 caracteres tirado do texto do cenário e os testes;
   - "Testes técnicos (infraestrutura 8)": ID, a regra e os testes.

   O teste da regra 3 também confere que o arquivo versionado é idêntico ao que o gerador produz agora. Se a matriz mudar sem regenerar, o teste falha. O resumo é lido dos documentos-base no momento da geração, e um número sem texto correspondente falha a geração.
5. **Lacunas:** quando nenhum teste existente prova um cenário ou teste técnico (regra 2), o implementador escreve um teste novo contra o simulador, com o número do cenário no nome do teste, como os de `tests/aceitacao/`.
   - O teste é de caracterização, porque o comportamento já existe. Se passar na primeira execução, isso é registrado no `review.md` como exceção técnica justificada (AGENTS.md §3), com a lista das lacunas.
   - Se falhar, é defeito: o implementador para, registra e devolve ao especificador, sem corrigir dentro desta fatia.
6. **Execução:** a matriz não muda a seleção de testes da suíte. Todos os testes referenciados rodam na suíte normal do CI. O teste da regra 3 roda com ela.

## Decisões técnicas

- **Matriz em Python, conferida pela árvore de sintaxe.** Um dicionário versionado é fácil de revisar no diff e de checar no CI. Ler a árvore de sintaxe evita depender da coleta completa do pytest e não executa nada. Marcadores em centenas de testes espalhariam a informação e seriam mais difíceis de auditar.
- **Documento gerado e conferido.** O relatório final precisa de uma tabela legível. Gerar o documento a partir da matriz e conferir a igualdade no CI evita que o documento e a matriz divirjam.
- **Defeito encontrado não é corrigido aqui.** A fatia é de evidência. Corrigir comportamento sem especificação mudaria escopo (AGENTS.md §3).

## Invariantes

- Cada cenário de 1 a 119 e cada teste técnico de T-1 a T-55 tem pelo menos um teste existente, não pulado, na matriz.
- O documento gerado corresponde à matriz.
- Nenhum código de produção muda nesta fatia.

## Dependências e decisões em aberto

- Depende das E01 a E15.
- Nenhuma dependência nova.
- Nenhuma decisão em aberto.
