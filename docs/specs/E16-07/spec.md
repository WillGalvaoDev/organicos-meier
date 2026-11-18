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
- testes novos só para cenários ou testes técnicos sem nenhum teste que os prove;
- a conferência pela execução real (`tests/rastreabilidade/conferir_execucao.py`) e as duas mudanças na etapa `pytest` do `.github/workflows/ci.yml` (regra 3-E).

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
2-E. **Afirmação atômica e prova integral** (segunda correção residual E16-R05, revalidação de 2026-11-18 sobre 9f4163b). A regra 2-D garante que a prova aponta um assert real. Ela não impede que uma afirmação composta seja "provada" por um teste que confere só uma das partes, como nos cenários 17, 20, 34 e 59 e em T-38. Para fechar isso:
   - **Afirmação atômica:** cada chave diz uma única coisa observável. Ao dividir o texto-base:
     - **enumeração:** uma afirmação por item. Exemplo: "não duplica pagamento, pedido, mensagem formal ou estorno" vira quatro afirmações;
     - **conjunção de efeitos:** uma afirmação por efeito. Exemplo: "bloqueia acesso e novo cadastro com o e-mail, mas mantém histórico e pedidos pagos" vira quatro afirmações;
     - **contraste:** "vale para X, mas não para Y" vira uma afirmação para X e outra para Y. Os exemplos de Y também se separam (alias com `+`, alias com pontos);
     - **lista de valores recusados ou aceitos:** uma afirmação por valor. Exemplo: "incremento zero, negativo ou com mais de 3 casas" vira três afirmações;
     - **resultado com qualificador:** "concluída sem duplicidade" vira "é concluída" e "não é duplicada";
     - **o que não se separa:** a condição fica junto do resultado dela. Exemplo: "depois de novo aporte, a devolução é concluída".
   - **Cobertura do texto:** cada oração do texto-base corresponde a pelo menos uma afirmação, e nenhuma fica de fora. O documento gerado (regra 4) mostra o texto e as afirmações lado a lado, o que permite essa leitura.
   - **Prova integral:** cada afirmação atômica precisa de pelo menos uma referência cujo teste faça as duas coisas:
     1. executar a ação ou a condição da afirmação. O webhook repetido é enviado; o novo cadastro com o e-mail é tentado; o login com o endereço em maiúsculas é tentado; o incremento zero é submetido;
     2. conferir com assert o resultado que a afirmação pede, e não um estado vizinho. Preservar a conta não prova que o acesso é recusado. Resolver o alerta não prova que a devolução foi concluída. Recusar um `float` não prova a recusa de um incremento negativo.
   - **Prova parcial:** uma referência que prova só parte de uma afirmação atômica não conta para ela e sai da lista. Ela pode continuar em outra afirmação que prove por inteiro.
   - **Sem afirmação parcialmente provada:** o `review.md` não pode declarar nenhuma afirmação "provada em parte". Se faltar prova integral, entra uma caracterização (regra 5), sem limite de quantidade. Se a caracterização falhar, é defeito e volta ao especificador (regra 5). Se o texto-base pedir algo que o produto não tem como exercitar, é dúvida de especificação: o implementador registra a afirmação e o motivo e devolve ao especificador, sem dar a entrada como concluída.
   - **Exemplos apontados na revalidação, que precisam ser corrigidos** (não bastam esses; a regra vale para as 174 entradas):
     - **cenário 17**, quatro afirmações:
       - **pagamento:** o webhook repetido não cria outro pagamento, destino nem quitação;
       - **pedido:** o webhook repetido não cria outro `Pedido` do comprador nem muda a situação dele;
       - **mensagem formal:** é o pedido formal enviado por e-mail ao fornecedor (funcional, seção 10). São dois testes, ambos com o webhook repetido enviado pelo mesmo caminho das caracterizações de 9f4163b:
         - (i) **depois do envio:** a rodada tem o resultado aprovado e o pedido formal já enviado. O webhook de um pagamento já confirmado da rodada chega de novo. Continua havendo um só `PedidoFormal` da rodada, com as mesmas linhas, nenhuma `TentativaDeEnvioDoPedidoFormal` nova e nenhum e-mail novo ao fornecedor;
         - (ii) **antes da aprovação:** o mesmo webhook chega duas vezes antes da aprovação. Na aprovação, é gerado um só `PedidoFormal`, com as quantidades de um único pagamento, e um só envio;
       - **estorno:** o webhook repetido depois da devolução não cria outro estorno;
     - **cenário 20**, quatro afirmações:
       - **acesso bloqueado:** depois da remoção, o login por senha, por Google e por link não abre sessão;
       - **novo cadastro bloqueado:** um novo convite ou cadastro com o mesmo e-mail, inclusive escrito com maiúsculas diferentes, é recusado e não cria conta;
       - **histórico mantido:** o administrador ainda consulta o histórico do removido, inclusive o financeiro;
       - **pedidos pagos mantidos:** o pedido pago continua com a situação de pago e consultável pelo administrador;
     - **cenário 34**, quatro afirmações:
       - a obrigação continua registrada pelo valor integral;
       - o sistema alerta;
       - **concluída:** depois do novo aporte, a devolução é processada até o fim. O estorno é concluído no simulador e a obrigação fica liquidada, com saldo devido zero;
       - **sem duplicidade:** repetir o acionamento da devolução depois da conclusão não cria outro estorno, não liquida outra vez e não debita a reserva de novo;
     - **cenário 59**, seis afirmações:
       - o endereço banido escrito com maiúsculas diferentes é recusado no login e num novo cadastro;
       - o alias com `+` não é afetado;
       - o alias com pontos não é afetado;
       - IP, dispositivo e telefone, uma afirmação cada, não são bloqueados;
     - **T-38:**
       - a validação contra o incremento vale para L, para kg e para unidade, uma afirmação cada;
       - o incremento é recusado com zero, com valor negativo e com mais de 3 casas, uma afirmação cada. A entrada tem o tipo aceito (`Decimal` ou o texto do formulário), para que a recusa seja do valor e não do tipo. Em cada caso, o produto não é criado;
       - o múltiplo incompatível é recusado no cadastro e na alteração em interesse, uma afirmação cada.
   - **Registro no `review.md`:**
     - por entrada, o resultado: "atomizada (n → m afirmações)", "completada" ou "caracterização nova";
     - os números da regra 2-D, atualizados;
     - a declaração de que nenhuma afirmação foi dada como provada em parte;
     - a lista das devoluções ao especificador, ou a frase "Nenhuma devolução".

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

3-D. **Lista fechada de ocorrências** (segunda correção residual E16-R06, revalidação de 2026-11-18 sobre 9f4163b). A regra 3-C listava formas proibidas. As combinações que ficaram de fora mostram que essa lista não fecha: `pytestmark.append(...)` dentro de um `if` e o encadeamento `__test__ = habilitado = False` passaram. A regra 3-C passa a ser aplicada pelo contrário: há uma lista de formas aceitas, e tudo o que não está nela é recusado.
   - **Ocorrência:** em qualquer ponto do arquivo, em qualquer profundidade, inclusive dentro de funções, classes, compreensões e lambdas, é ocorrência de `pytestmark` ou `__test__`:
     - um nome (`ast.Name`) com esse identificador, em qualquer contexto: leitura, escrita ou `del`;
     - um atributo (`ast.Attribute`) com esse nome;
     - um alias de importação (`import`/`from ... import`), pelo nome ou pelo `as`;
     - uma função ou classe com esse nome;
     - um parâmetro de função ou lambda;
     - um argumento nomeado (`f(pytestmark=...)`);
     - `global` ou `nonlocal` com esse nome;
     - um nome capturado em `match`, `except ... as` ou `with ... as`;
     - um texto literal (inclusive dentro de f-string) que contenha o identificador como palavra. A exceção são as docstrings de módulo, classe e função.
   - **Únicas ocorrências aceitas:** uma instrução que seja filha direta do corpo do módulo ou do corpo de uma classe, em uma destas formas:
     - `Assign` com exatamente um alvo, que é o nome `pytestmark` ou `__test__`;
     - `AnnAssign` com esse nome como alvo e com valor.

     O valor segue as regras 3-B e 3-C: em `pytestmark`, uma marca reconhecida ou uma lista ou tupla de marcas reconhecidas; em `__test__`, só a constante literal `True`.
   - **Uma definição por corpo:** cada controle é definido no máximo uma vez em cada corpo. Uma segunda definição recusa a referência.
   - **Recusa:** qualquer outra ocorrência no arquivo recusa a referência. A mensagem diz a forma e a linha, por exemplo "pytestmark lido em chamada de método dentro de if (linha 4)" ou "__test__ em atribuição encadeada (linha 2)". A regra vale em qualquer ponto do arquivo, mesmo fora da cadeia da referência, porque a conferência não executa código para saber o que alcança o teste.
   - **Formas que trazem nomes ou atributos sem escrevê-los:** recusam a referência:
     - `from ... import *`;
     - `__getattr__` definido no nível do módulo;
     - nas classes da cadeia: argumento nomeado na definição da classe (por exemplo, `metaclass=`) ou definição de `__getattr__`, `__getattribute__` ou `__init_subclass__`;
     - `exec`, `eval` ou `compile` chamados fora de funções.
   - **Herança:** o pytest lê `pytestmark` e `__test__` pela herança da classe. Por isso, cada base de uma classe da cadeia deve ser uma destas:
     - uma classe definida no mesmo arquivo, que entra na cadeia e é conferida pelas regras 3-A a 3-D (marcas, `__test__`, `__init__`);
     - `object`;
     - `unittest.TestCase` ou as classes de teste de `django.test` (`SimpleTestCase`, `TestCase`, `TransactionTestCase`, `LiveServerTestCase`), importadas desses módulos.

     Uma base importada de outro lugar, ou uma expressão, recusa a referência.
   - **Testes existentes:** a regra se aplica só aos arquivos referenciados na matriz. Se um deles for recusado, o implementador troca a referência por um teste que prove a afirmação (regra 2-E) ou faz uma caracterização (regra 5). Não reescreve o arquivo existente.
3-E. **Conferência pela execução real** (segunda correção residual E16-R06). A árvore de sintaxe não vê pulos feitos em tempo de execução, como fixture, `conftest.py` ou decorador. A conferência manual do `-ra` (regra 3-B) passa a ser automática:
   - **CI:** a etapa `pytest` do `.github/workflows/ci.yml` passa a gravar `--junitxml=relatorio-pytest.xml`. Logo depois, uma etapa roda `python -m tests.rastreabilidade.conferir_execucao relatorio-pytest.xml`.
   - **O que confere:** cada referência da matriz corresponde a pelo menos um `testcase` do relatório. A correspondência é pelo módulo em notação de pontos, pela classe, se houver, e pelo nome, com ou sem o sufixo de parametrização `[...]`. Todos os `testcase` dessa referência têm de ter passado, sem `skipped`, `failure` nem `error`. Referência sem `testcase` ou com qualquer resultado diferente de passado falha a etapa, com a referência e o resultado.
   - **Fora do CI:** o módulo é uma função reaproveitável. Ela recebe o caminho do relatório e a matriz, para os testes de aceitação usarem relatórios montados por eles.
   - **Registro:** o `review.md` registra a execução completa local com `--junitxml` e a saída da conferência. Esse registro substitui a lista manual do `-ra` da regra 3-B.
   - **A conferência estática continua:** ela falha cedo e sem banco. A da execução é a rede final.
3-F. **Prova do A-23 pelo pytest real** (segunda correção residual E16-R06). O teste que confirma as recusas com o pytest tinha dois problemas:
   - aceitava erro de configuração como sucesso: sem `PYTHONPATH`, o subprocesso parava com `ImportError` e a guarda passava;
   - falhava com um `xfailed` legítimo, porque procurava o texto `failed`, que aparece dentro de `xfailed`.

   Ele passa a ser um teste diferencial, com isolamento e resultado concreto:
   - **Isolamento:**
     - cada fonte roda num diretório temporário próprio, com um `pytest.ini` contendo só `[pytest]`;
     - o comando é `[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", <esse pytest.ini>, "--rootdir", <o diretório>, "--junitxml", <arquivo no diretório>]`. `/dev/null` não existe no Windows;
     - o ambiente do subprocesso é montado do zero: só `PATH`, `SYSTEMROOT`, `TEMP`, `TMP`, `HOME` e `USERPROFILE` que existirem no processo pai, mais `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Não leva `DJANGO_SETTINGS_MODULE` nem `PYTHONPATH`. As fontes só importam `pytest`.
   - **Resultado concreto:**
     - cada fonte declara o resultado esperado: "pulado", "falha esperada", "não coletado" ou, no controle, "falhou";
     - o teste confere o código de saída exato: 0 para pulado e falha esperada, 5 para não coletado e 1 para o controle;
     - confere também a contagem exata por resultado, lida do relatório JUnit ou da linha final com fronteira de palavra (`xfailed` não é `failed`);
     - não se usa busca de trecho na saída;
     - qualquer outro código de saída (2, 3 ou 4), um `error` no relatório ou um erro de importação falham o teste, com a saída anexada.
   - **Corpo das fontes:** todas as fontes do corpus têm `assert False` no corpo do teste. Assim, "falhou" prova que o teste rodou, e qualquer outro resultado prova que ele não rodou ou que a falha foi mascarada.
   - **Controle positivo:** as fontes aceitas do A-22, com o corpo trocado por `assert False`, têm de dar código 1 e exatamente um `failed`. Isso prova que o ambiente do subprocesso coleta e executa. Um ambiente quebrado não passa mais por verde.
   - **Propriedade diferencial:** para cada fonte do corpus (A-20, A-21, A-22 e A-29 a A-31), a conferência estática aceita a referência se, e somente se, o pytest real dá exatamente um `failed`.
     - Se a conferência aceita e o pytest não roda o teste, é aceitação indevida.
     - Se a conferência recusa e o pytest roda o teste, a recusa é a mais e precisa estar prevista na regra 3-D. As formas da regra 3-D que o pytest executaria, como uma leitura inofensiva de `pytestmark`, entram numa lista declarada de "recusas por precaução". Para elas, a propriedade exige só a recusa.
   - **Red e Green:** o `review.md` registra o Red do novo A-23 contra a conferência atual, que aceita as duas fontes da revalidação e o pytest não as executa, e o Green depois da regra 3-D.

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
- **Lista fechada mais execução real (regras 3-D e 3-E).** Uma lista de formas proibidas nunca fecha: cada revisão achou combinações novas. Aceitar só as formas declarativas simples e recusar todo o resto troca o risco de aceitação indevida pelo de recusa a mais, que é visível e se resolve trocando a referência. O relatório JUnit do CI cobre o que a árvore não vê (fixture, `conftest.py`, decorador), sem dependência nova, porque `--junitxml` é do próprio pytest e a leitura usa `xml.etree` da biblioteca padrão.
- **Atomicidade (regra 2-E).** A prova parcial nasce de afirmações compostas. Dividir o texto em afirmações atômicas torna a leitura do revisor binária: cada afirmação está provada ou não está.
- **Defeito encontrado não é corrigido aqui.** A fatia é de evidência. Corrigir comportamento sem especificação mudaria escopo (AGENTS.md §3).

## Invariantes

- Cada cenário de 1 a 119 e cada teste técnico de T-1 a T-55 tem pelo menos um teste existente, não pulado, na matriz.
- Cada afirmação é atômica e tem pelo menos um teste que executa a ação dela e confere o resultado dela por inteiro (regra 2-E).
- Toda referência da matriz passou na última execução completa do CI (regra 3-E).
- A conferência estática só aceita uma referência cujo arquivo tenha apenas as formas da lista fechada (regra 3-D).
- O documento gerado corresponde à matriz.
- Nenhum código de produção muda nesta fatia.

## Dependências e decisões em aberto

- Depende das E01 a E15.
- Nenhuma dependência nova.
- Nenhuma decisão em aberto.
