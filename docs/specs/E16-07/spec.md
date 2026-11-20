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

2-F. **Elementos concretos, casos de parametrização e devolução do cenário 96** (terceira correção E16-R05, revalidação de 2026-11-18 sobre de1111c e complemento do revisor).
   - **Elementos concretos da afirmação:** os valores, a unidade, o ator, a direção do lançamento, a interface e a tela que a afirmação nomeia têm de estar estabelecidos explicitamente no módulo do teste: no corpo, nos parâmetros ou numa função auxiliar do mesmo módulo. O valor padrão de uma fábrica (`tests/fabricas.py`) não conta. Exemplo: o `ProdutoFactory` cria kg sem que o teste diga nada, e isso não prova litros nem kg. Na leitura integral (regra 2-B), o implementador confere cada elemento nomeado e retira a ligação em que algum falta.
   - **Caso de parametrização:** a referência continua sem parâmetros (regra 1). Quando a prova depende de um caso de `pytest.mark.parametrize`, ela cita entre crases, além do trecho do assert (regra 2-D), o caso como está escrito no código, por exemplo `(Unidade.LITRO, "0.5", "1.2", False)`.
     - A conferência automática aceita esse trecho se ele estiver no decorador `parametrize` do teste ou numa constante do mesmo módulo que esse decorador usa pelo nome.
     - A prova tem de citar o caso quando a afirmação nomeia um valor ou uma unidade que só aparece nos parâmetros.
     - Um trecho que não está num assert, num `pytest.raises(...)` nem num desses lugares é acusado com a referência.
   - **Cenário 63** (funcional §16.63; infraestrutura §5, R-8):
     - **"inclusive pela API":** a aplicação não tem API separada. A arquitetura é Django com templates no servidor e HTMX, num único deploy, sem front separado (infraestrutura §2). A validação de quantidade vale "em toda adição ou alteração, inclusive pela API" (infraestrutura, item "Validação de quantidade" de R-8). A interface que materializa isso é a rota HTTP `POST /interesses/`, chamada diretamente, com os campos montados pelo teste e não pelo formulário da página. Essa rota já está especificada na E05-05, na tabela de respostas de `POST /interesses/`, e a E05-05 cita o cenário 63 "pela rota". Não se cria API nova;
     - **"1,2 kg é recusado pelo servidor":** produto em kg, preço R$ 12,00, incremento 0,5. A prova é pelo serviço `adicionar_interesse` com a entrada `"1.2"`, que levanta `QuantidadeInvalida` sem gravar parcela, citando o caso `(Unidade.KG, "0.5", "1.2", False)`;
     - **"a recusa de 1,2 kg vale também pela API":** o mesmo produto. Um comprador ativo faz `POST /interesses/` com `produto=<P>`, `quantidade=1.2` e `origem=carrinho`. A resposta é 200 com a página de origem e a mensagem do serviço (tabela da E05-05), e o teste confere que:
       - não há `ParcelaDeInteresse` desse comprador para o produto;
       - o total reservado do produto não mudou;
       - a resposta não traz a mensagem de sucesso "Interesse atualizado".

       Num segundo caso, o comprador já tem 1,5 reservado. O mesmo `POST` com `1.2` deixa o reservado em 1,5, com a parcela original sem alteração. Um teste com `1.5`, `"abc"` ou valor negativo não prova esta afirmação. Se nenhum teste existente fizer esse `POST`, entra a caracterização `test_cenario_63_rota_recusa_1_2_kg_sem_gravar` (regra 5);
     - **"1,5 kg é aceito por R$ 18,00":** essa afirmação continua separada. Ela é provada pelo caso `(Unidade.KG, "0.5", "1.5", True)`, com preço R$ 12,00 e o assert do subtotal `D("18.00")`, citando o caso.
   - **T-11** (infraestrutura §8, T-11; P-2):
     - **direção:** a afirmação "lançamento com recursos do fornecedor A para obrigação de B é recusado" fala de um lançamento cuja **origem** é uma conta de recursos de A e cujo **destino** é uma obrigação de B. A prova tem de tentar esse lançamento e conferir a recusa e a preservação dos saldos e da contagem de movimentos;
     - **teste que prova:** `tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso` faz isso nas tentativas `(T.FINANCIAMENTO_DE_OBRIGACAO, devida, obrigacao_com(m.rb, m.cb, m.x, numero=2))` e `(T.REPASSE, devida, obrigacao_de(m.fb, m.rb))`, com `pytest.raises(MovimentoProibido)` e `(_saldos(), MovimentoFinanceiro.objects.count()) == antes`. Ele passa a ser a referência dessa afirmação, e a prova cita a tentativa e os dois asserts;
     - **o que sai:** a ligação atual, `test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b`, sai dessa afirmação. Esse teste tenta um repasse **para A** com o saldo insuficiente de A, que é a outra metade do T-11. Ele pode continuar como prova da afirmação "o repasse a A é limitado ao valor liberado de A", que fica separada, com a sua própria prova;
     - **o que não muda:** não há regra financeira nova nem teste novo. É a correção da ligação.
   - **T-38** (infraestrutura §8, T-38; funcional §16.85):
     - **unidade como pré-condição:** cada uma das três afirmações de unidade (L, kg e unidade) aponta para um teste que define a unidade do produto explicitamente, por um parâmetro ou por um argumento da montagem. A prova cita o caso;
     - **litros:** o exemplo aprovado no §16.85 é incremento 0,5 L, com 1,5 L aceito e 1,2 L recusado. O `tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos` tem os casos `(Unidade.LITRO, "0.5", "1.5", True)` e `(Unidade.LITRO, "0.5", "1.2", False)`, que exercitam a validação contra o incremento num produto em litro. A prova cita os dois casos e os asserts `resumo.reservado == D(entrada)` e `pytest.raises(QuantidadeInvalida)`;
     - **kg e unidade:** valem as mesmas exigências, com `(Unidade.KG, "0.5", "1.2", False)` e `(Unidade.UNIDADE, "1", "2.5", False)` ou outros casos explícitos;
     - **o que sai:** o `test_catalogo_quantidades.py::test_quantidades_aceitas`, cujo produto é kg só pelo padrão da fábrica, sai das afirmações de unidade.
   - **Cenário 96, histórico do comprador:** a afirmação do histórico é obrigatória e fica na matriz, separada da do carrinho: "o histórico mostra Reservado: 6 e Pendente: 4, inclusive com o estoque zerado".
     - **qual é o histórico:** é a tela "Meus pedidos" (`GET /pedidos/`), a única que a especificação define como histórico do comprador (funcional §2 e §13: "Histórico de pedidos, pagamentos, estornos e retirada por item");
     - **o que falta:** hoje essa tela não mostra interesses, então falta implementação, e não só prova. Ela é especificada na fatia **E16-09** (`docs/specs/E16-09/`), com a decisão do responsável de 2026-11-18;
     - **ligação:** depois da E16-09, a afirmação aponta para o teste dela que percorre `GET /pedidos/`. Até lá, a entrada 96 fica pendente, e a E16-07 não pode ser aprovada.
   - **Revisão completa com o mesmo critério:** os pontos de C63, T-11 e T-38 são exemplos de três falhas que o implementador procura nas 174 entradas:
     - o valor da afirmação não aparece nos parâmetros;
     - a direção ou o sujeito estão invertidos;
     - a pré-condição vem do padrão de uma fábrica.

     O `review.md` registra, para cada falha, as entradas encontradas e corrigidas, ou "nenhuma além dos exemplos".
   - **Retificação:** o `review.md` registra que a linha "C96: completada" do registro anterior fica retificada para "pendente: depende da E16-09", sem apagar a linha antiga.

2-G. **Auditoria exaustiva de cada ligação** (quarta correção E16-R05, revisão de 2026-11-18 sobre 3e8b4ff).
   - **Por que muda o método:** a revisão completa da regra 2-F procurou três falhas específicas, por script. A quinta amostra do revisor achou falhas de outro tipo (C74, C84, C90, T-44, T-47, C86 e T-43): a prova não estabelece o resultado afirmado, ou parte de outra situação. Um script não detecta isso. A partir desta correção, a revisão deixa de ser por tipo de falha e passa a ser a leitura de **cada ligação** da matriz, com o resultado registrado e conferido no CI. O registro do A-45 fica como histórico.
   - **Arquivo:** `tests/rastreabilidade/auditoria.py` define `AUDITORIA: dict[tuple[int | str, str, str], dict[str, str]]`.
     - **Chave:** `(entrada, afirmação, referência)`, com a entrada do mesmo tipo da chave da matriz (`74` ou `"T-44"`) e os dois textos idênticos aos da matriz.
     - **Valor:** os campos `preparacao`, `acao`, `resultado` e `veredito`, todos não vazios e com até 200 caracteres.
       - `preparacao`: a situação que o teste monta antes da ação, com os elementos concretos e onde estão (corpo, parâmetro ou auxiliar);
       - `acao`: a ação executada, a interface (serviço, rota e método) e o ator;
       - `resultado`: o que os asserts conferem, e, quando houver comparação, quando o estado "antes" foi lido;
       - `veredito`: `"íntegra"` ou `"corrigida: <o que mudou>"`, por exemplo `"corrigida: caracterização nova"` ou `"corrigida: religada"`.
   - **Uma linha por ligação:** as chaves de `AUDITORIA` são exatamente as ligações da matriz final, sem faltar nem sobrar. Uma ligação que não prova por inteiro sai da matriz, ainda que outra ligação da mesma afirmação prove. Ligação "complementar" parcial não existe. As ligações retiradas ficam listadas no `review.md`.
   - **As seis perguntas de cada ligação.** O veredito `"íntegra"` exige sim nas seis:
     - (a) **situação:** o teste monta as pré-condições da afirmação e do cenário de onde ela veio, inclusive a condição comum que a atomização separou (no C90, "depois da mudança de preço");
     - (b) **ação:** executa a ação afirmada, pela interface afirmada, com o ator e os identificadores reais. Um identificador inexistente não prova a recusa de um identificador existente (T-44);
     - (c) **resultado:** confere o resultado afirmado. Quando a afirmação diz que algo "não muda", o estado é lido antes da ação e comparado por conteúdo, não só por identificadores (C74);
     - (d) **objeto:** confere o objeto que a afirmação nomeia. Duas contas distintas não são duas strings distintas (C84), e as caixas formadas não são o progresso da rodada (T-47);
     - (e) **elementos concretos e casos:** valem a regra 2-F e a citação dos casos de parametrização. Isso inclui o caso que distingue a causa de uma recusa de outras recusas do mesmo teste (C86 e T-43);
     - (f) **causa da recusa:** num negativo, a recusa conferida é a da causa afirmada, e não uma recusa qualquer.
   - **Os resíduos apontados pelo revisor:**
     - **C74, "o pedido congelado não muda":** religar a `tests/tecnicos/test_apuracao_viavel.py::test_o_pedido_congelado_nao_muda`, que fotografa `Pedido`, `ItemDoPedido` e `ParcelaNoPedido` antes de `_iniciar` e exige igualdade depois. `test_unidades_da_caixa_invalidada_voltam_para_a_fila` sai dessa afirmação.
     - **C84, contas distintas:** a afirmação "`usuario@gmail.com` e `usuario+teste@gmail.com` podem pertencer a contas distintas" exige duas contas criadas pelo cadastro, ou pelo serviço de cadastro, com esses dois e-mails, e a consulta que mostra as duas como contas diferentes. Se nenhum teste existente faz isso, entra a caracterização `test_cenario_84_aliases_com_mais_sao_contas_distintas` (regra 5). `test_normalizar_email_nao_altera_aliases` sai dessa afirmação. A prova do banimento continua separada.
     - **C90, o cenário inteiro:**
       - montar um item de 0,25 kg a R$ 7,99/kg, cobrado R$ 2,00, com serviço e frete registrados;
       - mudar o preço do produto para R$ 8,99/kg depois da cobrança;
       - registrar uma ocorrência da quantidade inteira desse item;
       - conferir o reembolso de produtos de R$ 2,00, e o de serviço e frete proporcional sobre os valores registrados, sem usar 8,99.

       Cada afirmação atômica do C90 aponta para esse fluxo, com a condição "depois da mudança de preço" mantida. Se nenhum teste existente faz o fluxo inteiro, entra a caracterização `test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado` (regra 5). `test_o_valor_vem_do_registrado_e_nao_do_catalogo` (outro item e outro preço) e `test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado` (sem mudança de preço) saem das afirmações do C90 e podem continuar nas do C91, se as provarem por inteiro.
     - **T-44, as duas entradas recusadas, cada uma com a sua prova:**
       - **identificador real de um `ItemDoPedido` congelado:** `remover_pendente`, e a rota de remoção quando a afirmação nomeia a rota, recebe o `pk` do item existente e recusa. O pedido, os registros financeiros e as parcelas ficam iguais por conteúdo;
       - **parcela "em pedido":** a recusa da parcela que está em pedido, com o mesmo conferimento.

       `item_de_a_em_q.pk + 10_000` não prova nenhuma das duas. Faltando prova, entra caracterização (regra 5), seguindo a E11-08 A-9.
     - **T-47, a formação de caixas:**
       - o produto tem múltiplo definido, com reservadas e pendentes em quantidade suficiente para completar uma caixa a mais se as pendentes contassem;
       - a apuração forma só as caixas das reservadas, e as pendentes continuam na fila.

       `test_progresso_e_pedido_so_contam_as_reservadas`, que remove o múltiplo, sai dessa afirmação. Fica nas de progresso e pedido, se as provar.
     - **C86 e T-43:** as provas citam os casos que nomeiam: `"0"` e `"-1"` no C86, e o caso fora do incremento com `"1.5"` no T-43.
   - **Caracterizações:** as caracterizações novas seguem a regra 5. Quando passam na primeira execução, o `review.md` registra isso como caracterização de comportamento existente. Se alguma falhar por falta de comportamento, o implementador para e devolve ao especificador, sem corrigir a produção nesta fatia.
   - **Registro:** o `review.md` traz o método (leitura de cada ligação), o número de ligações lidas, de íntegras e de corrigidas por pergunta (a) a (f), as ligações retiradas, as caracterizações novas, as devoluções, a suíte completa e a saída de `conferir_execucao`.

2-H. **Guarda de parametrização conservadora e congelada** (quarta correção E16-R05, contraexemplo do revisor sobre `conferencia.py:497`).
   - **Constante aceita:** a conferência só aceita um caso citado de uma constante do módulo, usada pelo nome no `parametrize` do teste, quando todas estas condições valem:
     - o nome tem uma única ligação no módulo inteiro, que é uma atribuição simples (`=` ou anotada) no nível do módulo;
     - essa atribuição vem antes, em número de linha, da definição decorada;
     - em todo o resto do módulo o nome só aparece lido, nunca como alvo de atribuição, `+=`, `del`, `for`, `with ... as`, `import ... as`, `global`, `nonlocal`, índice ou fatia (`NOME[0] = ...`);
     - o nome nunca aparece como objeto de uma chamada de método (`NOME.append(...)`, `NOME.extend(...)`, `NOME.insert(...)` ou qualquer outra), porque a lista é lida pelo pytest só na coleta.
   - **O que é acusado:** qualquer outro caso, com a referência e o motivo "constante de casos com mais de uma ligação ou alterada no módulo". A guarda não importa nem executa o módulo.
   - **O que garante que o caso rodou:** com o caso preso estaticamente ao decorador efetivo, a regra 3-E fecha a execução. Ela exige que todos os casos `[...]` da referência tenham passado no JUnit.
   - **Congelamento:** a guarda não ganha formas novas além desta. A suficiência das provas é garantida pela auditoria da regra 2-G e pela leitura do revisor, e não por análise estática, que nunca prova semântica por completo.
     - Uma evasão que só exista em código sintético, fora das referências da matriz, fica fora do escopo da E16-07 e vai para `docs/melhorias.md`.
     - Uma evasão que ocorra numa referência real da matriz é um resíduo da R05.

2-I. **Critério de encerramento da R05** (decisão do responsável de 2026-11-19).
   - **Sexta amostra:** o revisor confere uma sexta amostra de pelo menos 20 cenários e 10 testes técnicos, escolhida por ele e diferente das cinco anteriores. Ele relê também as ligações dos sete resíduos da regra 2-G. Em cada ligação, compara a linha de `AUDITORIA` com o corpo do teste.
   - **Sem resíduo:** a R05 é encerrada.
   - **Com resíduo:**
     - o revisor lista cada resíduo e diz se algum deles indica defeito de produção;
     - um defeito de produção segue o fluxo normal (AGENTS.md §4.6);
     - para os demais, o especificador leva ao responsável a escolha entre duas opções. A primeira é uma nova rodada exaustiva. A segunda é corrigir os resíduos apontados e registrar o restante, sem defeito de produção, como melhoria em `docs/melhorias.md`, com a R05 encerrada depois da correção dos apontados;
     - nenhum agente faz essa escolha sozinho.

2-J. **Nova rodada exaustiva** (quinta correção E16-R05, sexta amostra do revisor sobre 8e35589; decisão do responsável de 2026-11-19 pela opção "nova rodada exaustiva" da regra 2-I).
   - **Por que a auditoria da regra 2-G deixou passar:** a sexta amostra achou linhas de `AUDITORIA` marcadas "íntegra" em cinco situações:
     - a ação descrita não era a ação executada. Um auxiliar com o motivo `ocorrencia_de_entrega` chama direto `reembolso_parcial`, sem registrar a ocorrência;
     - um teste sequencial estava ligado a uma afirmação de concorrência;
     - uma afirmação composta tinha uma ligação para cada cláusula;
     - o arranjo era de outro cenário;
     - a comparação "não muda" deixava de fora registros que a afirmação nomeia.

     As perguntas (a) a (f) continuam valendo. Esta regra acrescenta as perguntas (g) a (k) e um campo novo, que obriga a seguir a ação até a produção.
   - **Campo novo `caminho`:** toda linha de `AUDITORIA` ganha `caminho`, não vazio e com até 200 caracteres.
     - **Conteúdo:** os pontos de entrada de produção que a ação do teste efetivamente executa, seguindo os auxiliares do teste, separados por "; ".
     - **Formas aceitas (lista fechada, correção G2J-01 do gate):**

       | Forma | Uso | Conferência estática, pela árvore de sintaxe e sem importar |
       |---|---|---|
       | `apps.<módulo>.<função>` ou `apps.<módulo>.<Classe>.<método>` | função, método ou view do projeto | a função ou o método existe no arquivo `.py` correspondente em `apps/` |
       | `config.<módulo>.<função>` | função de `config/`, como `config.observabilidade.limpar_evento` | a função existe no arquivo correspondente em `config/` |
       | `modulo:<caminho pontuado>` | corpo de módulo executado ao carregar, como `modulo:config.settings.prod` (T-12) | o arquivo `.py` existe em `apps/` ou `config/` |
       | `comando:manage.py <subcomando>` | comando executado pelo ponto de entrada, como `comando:manage.py procrastinate worker` | `manage.py` existe na raiz. Quando o subcomando é do projeto, existe `apps/*/management/commands/<subcomando>.py` |
       | `rota:<MÉTODO> <caminho>` | rota cuja view é de uma dependência, como `rota:POST /entrar/` (allauth) | o caminho sem a barra inicial, até o primeiro parâmetro, aparece no começo de uma chamada `path(...)` de `config/urls.py` ou de um `urls.py` de `apps/` |
       | `banco:<nome>` | restrição ou trigger do Postgres, como `banco:conta_email_unico` | o nome aparece literalmente num arquivo `.py` de `apps/` (migração ou módulo de gatilhos) |
       | `fonte:<caminho relativo>` | inspeção estática de um artefato de produção, como a varredura de `float` do T-39 | o arquivo ou a pasta existe e não está em `tests/` nem em `docs/` |

       Uma rota cuja view é do projeto usa a primeira forma, com a view. Nenhuma forma aceita algo de `tests/`: auxiliares de teste nunca são produção.

       A regra 2-K estreita as conferências da primeira forma (só `def`), de `rota:` (texto igual e view de dependência) e de `banco:` (nome exato no catálogo). Ela também acrescenta a conferência do alcance pela execução. Onde esta tabela e a regra 2-K diferem, vale a regra 2-K.
     - **Existência estática e alcance efetivo:** o CI confere só que o ponto de entrada existe. Ele não confere que o teste o alcança. O alcance é da leitura humana (pergunta (g)): o implementador segue o auxiliar e o revisor confere na amostra. Indicar uma função que existe, mas que a ação não executa, é resíduo.
     - **Classificação antes do preenchimento:** o especificador conferiu que a lista cobre os tipos de ligação da matriz. A leitura dos módulos de teste ligados achou três que não importam `apps`:
       - `test_configuracao_pagamentos.py` (cenário 38 e T-12), que usa `modulo:` e `comando:`;
       - `test_varredura_float.py` (T-39), que usa `fonte:`;
       - `test_cenario_61_contas_independentes.py` (C61), que usa `rota:POST /entrar/` e as views do projeto que alcança.

       O implementador classifica as 606 linhas antes de preencher. Se alguma não couber em nenhuma forma, ele para e devolve ao especificador com a lista, sem forçar uma forma. Não se move nem se refatora produção para caber no formato.
   - **As cinco perguntas novas.** O veredito `"íntegra"` exige sim também nestas:
     - (g) **ação efetiva:** quando a afirmação nomeia uma ação de negócio (ocorrência, apuração, abertura do pagamento, cadastro, remoção, cancelamento), o `caminho` contém a função de produção dessa ação. Chamar o cálculo financeiro que a ação usaria, ou um auxiliar cujo nome ou motivo cita a ação, não prova a ação;
     - (h) **concorrência:** quando a afirmação diz "simultâneos", "concorrendo" ou "concorrente", o teste executa as operações em paralelo (`executar_em_paralelo`, E01-05). O resultado afirmado tem de sair do mecanismo que a afirmação nomeia. Quando a afirmação diz "em qualquer ordem", cada ordem é forçada sob concorrência: a primeira operação obtém a trava e a segunda fica comprovadamente esperando por ela antes de a primeira confirmar. Execução sequencial não prova concorrência;
     - (i) **cláusulas:** uma afirmação com mais de uma cláusula ("e", "nem", "inclusive", lista) é provada inteira por cada ligação. Se nenhum teste prova todas as cláusulas, o implementador atomiza a afirmação pela regra 2-E, sem perder a condição comum, e cada parte ganha a sua prova integral. Uma ligação por cláusula não é permitida;
     - (j) **arranjo do cenário:** numa entrada de cenário (1 a 119), cada número e cada ator do texto-base do cenário que a afirmação herda aparece no arranjo do teste. Isso inclui preço, quantidades, mínimo, quantidade reservada e pendente de cada comprador e valores cobrados. Um teste com outro arranjo prova uma regra geral parecida e sai da ligação. Os testes técnicos (`T-n`) seguem o texto da sua linha na infraestrutura;
     - (k) **"não muda":** a comparação cobre todos os registros que a afirmação nomeia, lidos antes da ação e comparados por conteúdo. Para "pedido e registros financeiros", são `Pedido`, `ItemDoPedido`, `ParcelaNoPedido`, `ObrigacaoComComprador`, `MovimentoFinanceiro` e `Reembolso`. Uma função auxiliar que lê só situação e quantidades não é prova de obrigação.
   - **Releitura de todas as linhas:** as 606 linhas são relidas com as onze perguntas, e não só as da sexta amostra. O campo `caminho` é preenchido em todas.
     - **Busca dirigida antes da entrega:** um script levanta candidatos e a leitura decide:
       - auxiliares de `tests/apoio/` que chamam funções financeiras com um motivo em texto;
       - afirmações com "simultâne", "concorr" ou "qualquer ordem";
       - números do texto-base de um cenário que não aparecem no módulo do teste ligado;
       - afirmações com "e", "nem" ou "inclusive" com mais de uma ligação.
     - **Registro:** o `review.md` traz o número de candidatos de cada busca e o resultado.
   - **Os resíduos da sexta amostra:**
     - **C90, C112 e C114, ocorrência real:**
       - a ação de ocorrência é `apps.pedidos.ocorrencias.registrar_ocorrencia`, chamada por um administrador ativo, com o item, a quantidade afetada, o tipo e o acionamento;
       - **C90:** item de 0,25 kg a R$ 7,99/kg, cobrado R$ 2,00, com serviço e frete registrados; o preço muda para R$ 8,99/kg antes da ocorrência. A ocorrência da quantidade inteira (0,25) gera o reembolso de 2,00 de produtos, 0,10 de serviço e 0,40 de frete, ligado à ocorrência registrada;
       - **C112:** item de 1,000 kg a R$ 7,99/kg, com subtotal 7,99; ocorrência de 0,25 kg com 2,00 de produtos. Na afirmação "uma mudança posterior do preço não altera o valor", o preço vai para R$ 9,99/kg depois, e o reembolso registrado continua 2,00;
       - **C114:** item de R$ 7,99 com ocorrência parcial real de 2,00; depois, o cancelamento da rodada com reembolso devolve para esse item exatamente 5,99. A ligação para `test_o_cancelamento_devolve_so_o_saldo_restante` (arranjo AE, 70,76) sai. A segunda afirmação do C114 só fica se for provada no mesmo arranjo do item de 7,99; senão sai, porque o §16.114 só fala do item;
       - a caracterização `test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado` passa a chamar `registrar_ocorrencia`, ou dá lugar a uma nova. As provas financeiras de `parcial(...)` continuam nas afirmações de cálculo que provarem por inteiro.
     - **T-47, formação de caixas pela abertura:**
       - a afirmação "a formação de caixas ignora a quantidade pendente" é provada por `apps.pedidos.abertura.abrir_pagamento`;
       - o produto tem múltiplo 10 (ou outro definido), com reservadas que completam k caixas e sobram r unidades, e pendentes em quantidade de pelo menos 10 − r, de modo que contá-las completaria a caixa k + 1. Exemplo: 15 reservadas e 5 pendentes formam 1 caixa, e não 2;
       - o teste confere as caixas efetivas das linhas congeladas (`caixa` das linhas do pedido), o destino das r unidades segundo a regra aprovada da abertura, e as pendentes, que continuam pendentes e na fila;
       - `test_a_formacao_de_caixas_ignora_as_pendentes`, que só consulta o progresso, sai dessa afirmação. Pode ficar na do cálculo do mínimo ou do progresso, se a provar.
     - **C99 e T-44, as duas entradas recusadas:**
       - **item congelado:** depois de `abrir_pagamento`, a rota de remoção de pendentes recebe o `pk` real do `ItemDoPedido` de A em cada campo de identificação que aceita. Ela recusa sem gravar, e a comparação da pergunta (k) dá igualdade. Um status 200 com o erro do formulário é a recusa da tabela da rota e não é defeito: o teste confere a ausência da mensagem de sucesso e de escrita;
       - **parcela "em pedido" real:** depois de `abrir_pagamento`, a parcela de A está em pedido e ligada a um item. `remover_pendente` recusa com `RemocaoAcimaDoPendente`, e a rota recusa com o identificador dessa parcela, com a mesma comparação. A parcela criada à mão em `EM_PEDIDO`, sem item, sai da ligação;
       - **trigger:** a afirmação "pedido, trigger e registros financeiros ficam inalterados" ganha, além da comparação (k), a prova de que a trigger de imutabilidade continua ativa depois da tentativa. Um `UPDATE` direto sobre o item congelado é recusado, como no T-17, e o `caminho` registra `banco:<nome da trigger>`;
       - `_estado` sai de toda prova de obrigação.
     - **T-34, recusa pela `UNIQUE` em concorrência:**
       - convite de comprador com `Ana@x.com` e convite de fornecedor com ` ana@x.com ` (o texto da T-34);
       - os dois `consumir_convite` passam da verificação de existência do e-mail antes de qualquer um inserir, sincronizados pelo apoio de concorrência da E01-05;
       - resultado: um sucesso, uma única conta, e a recusa do outro pela restrição `conta_email_unico`. Pode ser o `IntegrityError` com esse nome, ou a exceção de domínio em que o serviço o traduz, com esse `IntegrityError` como causa (`__cause__` ou `__context__`);
       - `test_banco_recusa_segunda_conta_com_o_mesmo_email_pela_restricao_unique`, sequencial, sai da afirmação de concorrência e pode ficar numa afirmação própria da restrição;
       - se o apoio de concorrência não conseguir sincronizar depois da verificação sem mudar a produção, o implementador para e devolve ao especificador.
     - **T-7, ordens forçadas, delimitadas pelo §8.3** (correção G2J-02 do gate):
       - **precedência:** a linha T-7 da infraestrutura resume ("o mesmo resultado em qualquer ordem"). O funcional §8.3 prevalece (AGENTS.md §2) e delimita esse resumo de duas formas:
         - uma aprovação até `T0 + 48h` notificada depois é aceita "desde que identificada na apuração";
         - um pagamento comunicado tardiamente "não autoriza editar pedidos já apurados".

         Por isso, a igualdade entre as ordens vale só dentro de um grupo de equivalência, e não para qualquer arranjo;
       - **grupo de equivalência:** o mesmo pedido, o mesmo pagamento, o mesmo horário de aprovação no provedor e a mesma informação consultável no provedor no instante em que cada operação a lê, em especial a reconsulta da apuração. Nesse grupo, para webhook × bloqueio de `T0 + 24h` e para webhook × apuração, as duas ordens são forçadas sob concorrência (pergunta (h)). O resultado final de pagamento, destino e situação do pedido é idêntico. Para webhook × apuração, é o caso da E11-01 A-15: aprovação identificável, Y `pago` e destino `quita` nas duas ordens;
       - **comportamento distinto, em afirmação própria:** a aprovação **não** identificada na apuração, com a reconsulta devolvendo "pendente", segue a E11-01 A-16. A apuração cancela Y por inadimplência, e o aviso posterior à decisão espera a trava. Y continua `cancelado`, com destino `devolucao`, a obrigação integral e o alerta `aprovado_no_prazo_depois_da_apuracao`, sem editar o pedido apurado. Essa afirmação continua ligada às provas aprovadas (`tests/tecnicos/test_apuracao_inicio.py`, testes dos A-15 e A-16 da E11-01) e não entra em nenhuma afirmação de igualdade;
       - **webhook × bloqueio:** o grupo de equivalência segue os critérios aprovados da E08-04 e da E08-05: a criação antes de `T0 + 24h` e o mesmo estado da cobrança no provedor. Se algum critério aprovado dessas fatias previr resultado diferente conforme a ordem, esse caso vira afirmação própria, como o do A-16. Se a leitura não permitir delimitar o grupo, o implementador para e devolve ao especificador;
       - **bloqueio × apuração:** o par entra se as regras de prazo permitirem que os dois atuem sobre o mesmo pedido no mesmo instante, com o mesmo grupo de equivalência. Se não permitirem, o `review.md` registra o porquê, com a referência do prazo;
       - **o que não muda:** quitação, prazos, cancelamento e devolução. Nenhuma regra financeira é alterada para obter igualdade;
       - os testes sequenciais ficam como prova de afirmações próprias de ordem sequencial, se existirem, ou saem.
     - **C59, atomização autorizada:** "o endereço banido com outras maiúsculas é recusado no login e no novo cadastro" vira duas afirmações, uma para o login e outra para o novo cadastro, cada uma com a sua prova atual. As demais afirmações do C59 não mudam.
     - **C85 e T-26, a rota:**
       - no C85, "as validações de quantidade ocorrem no servidor, inclusive pela API" é provada pela caracterização `test_cenario_85_rota_valida_as_quantidades_no_servidor`. Ela faz `POST /interesses/` direto com os cinco casos do §16.85 (L 0,5 com 1,5 e 1,2; unidade 1 com 2 e 2,5; kg 0,25 com 0,75), com a unidade explícita. Os aceitos ficam reservados com o valor, e os recusados não gravam;
       - `test_quantidades_recusadas` sai dessa afirmação e da afirmação "recusada pela API" do T-26, que fica com a rota.
     - **C104, o arranjo do cenário:**
       - produto de R$ 10,00, mínimo de R$ 100,00, A com 8 reservadas e C com 5 pendentes sem reserva: progresso elegível 80,00 e fechamento recusado por `minimo_nao_atingido`;
       - para "se a rodada chegar ao pagamento", o mesmo arranjo chega à abertura por um caminho já especificado que não converta as pendentes de C, como novas reservas de outro comprador até o mínimo. As pendentes de C não entram em pedido nem em cobrança e continuam na fila com 5;
       - os testes com o arranjo FP/R2 (C com 4 + 4) saem das afirmações do C104;
       - se nenhum caminho especificado levar esse arranjo ao pagamento sem converter as pendentes, o implementador para e devolve ao especificador.
   - **Caracterizações e devoluções:** valem a regra 5 e a regra 2-G. Se uma caracterização falhar por falta de comportamento, o implementador para e devolve, sem corrigir a produção.
   - **Retificação do registro da guarda (A-47):** o `review.md` retifica a frase "a conferência atual aceitava todos (`assert []`)", sem apagar o texto anterior. A versão-base `54be872` aceitava dois dos sete casos (reatribuição posterior e atribuição só posterior) e recusava cinco com o diagnóstico genérico. O implementador registra o comando e a saída que mostram isso, ou identifica o estado intermediário que de fato usou no Red.
   - **Registro:** o `review.md` traz:
     - o número de linhas relidas e o de corrigidas por pergunta (a) a (k);
     - as ligações retiradas e as afirmações atomizadas;
     - as caracterizações novas, com a primeira execução de cada uma;
     - o resultado da busca dirigida e a retificação acima;
     - as devoluções ao especificador ou "Nenhuma devolução";
     - as contagens da matriz, a suíte completa e a saída de `conferir_execucao`.
   - **Sétima amostra e encerramento:** vale a regra 2-I.
     - **A amostra:** o revisor confere uma sétima amostra de pelo menos 20 cenários e 10 testes técnicos, diferente das seis anteriores, e relê os resíduos da sexta.
     - **Sem resíduo:** a R05 é encerrada.
     - **Com resíduo:** a escolha da regra 2-I volta ao responsável.

2-K. **Correção dos resíduos da sétima amostra e encerramento da R05** (sexta correção E16-R05; revisão independente de `3eb24be`, resíduos R05-J1 a R05-J7; decisão do responsável de 2026-11-20 pela segunda opção da regra 2-I).
   - **A decisão e o efeito sobre a regra 2-J:**
     - o responsável escolheu "corrigir os resíduos apontados e registrar o restante, sem defeito de produção, como melhoria";
     - deixa de ser exigida a releitura de todas as linhas com as onze perguntas (regra 2-J, item "Releitura de todas as linhas", e o A-63 nessa parte). Ela fica registrada como a melhoria M-15 em `docs/melhorias.md`;
     - continuam valendo: as perguntas (a) a (k) para toda linha de `AUDITORIA` que esta correção criar ou alterar, o campo `caminho` em todas as linhas e as correções da regra 2-J que o revisor já confirmou;
     - a sétima amostra (A-64) está feita. Não há oitava amostra. O encerramento segue o item "Revisão e encerramento" abaixo.
   - **R05-J1, registro fiel:** o implementador acrescenta ao `review.md` uma retificação do registro de `3eb24be`, sem apagar o texto anterior. Ela diz:
     - que a rodada da regra 2-J não releu o corpo de cada uma das 606 linhas com as perguntas (a) a (k);
     - o que foi feito de fato: o alcance estático até a profundidade 4, as buscas dirigidas e a leitura dos candidatos;
     - que os números de "relidas" e "corrigidas por pergunta" daquele registro valem só para as linhas lidas de fato;
     - que, pela decisão de 2026-11-20, o restante vai para a M-15. A rodada exaustiva não é declarada concluída.
   - **R05-J2, alcance conferido pela execução:** a existência estática não prova o alcance, e a geração automática pôs no `caminho` pontos que a ação não executa. Por isso, o alcance das formas de função e de rota passa a ser conferido por uma execução instrumentada dos testes ligados. Isso não é uma forma nova da guarda da regra 2-H, que continua congelada. Uma evasão desse registro que só exista em código sintético, fora das referências da matriz, vai para `docs/melhorias.md`.
     - **Registro do alcance** (`tests/rastreabilidade/alcance.py`, plugin do pytest):
       - fica ativo só com a opção `--registrar-alcance=<arquivo.json>`. Sem a opção, não instala nada e a suíte normal não muda;
       - para cada teste coletado (cada caso parametrizado é um `nodeid` próprio), registra o que roda nas fases de preparação (`setup`) e de execução (`call`), em todas as threads: as que já existem (`threading.setprofile_all_threads`), as novas (`threading.setprofile`) e a principal (`sys.setprofile`). No fim de cada fase, restaura o perfil anterior;
       - registra duas coisas. Os **pontos** são cada função ou método executado (evento `call`) cujo arquivo está em `apps/` ou `config/`, com o nome `<módulo pontuado do arquivo>.<co_qualname>`, como `apps.contas.adaptadores.AdaptadorContaSocial.pre_social_login`. As **requisições** são cada requisição recebida pelo handler do Django (sinal `request_started`), como `"<MÉTODO> <PATH_INFO>"`;
       - grava `{nodeid: {"pontos": [...], "requisicoes": [...]}}`, em ordem e sem repetição;
       - não importa nem altera nada de `apps/` ou `config/` além de observar a execução, e não usa dependência nova.
     - **Conferência do alcance** (`tests/rastreabilidade/conferir_alcance.py`):
       - a função pura `conferir_alcance(auditoria, registro) -> list[str]` devolve os problemas;
       - o comando `python -m tests.rastreabilidade.conferir_alcance --executar <arquivo.json>` roda o pytest num subprocesso, só com as referências distintas da matriz e com o plugin ativo. Depois confere o arquivo e sai com 0 só se não houver problema, imprimindo cada um;
       - **casos:** uma referência `arquivo::nome` (ou `arquivo::Classe::nome`) corresponde ao `nodeid` igual a ela e a cada `nodeid` que começa por ela seguido de `[`. Uma referência sem nenhum `nodeid` registrado é acusada ("referência sem registro de alcance");
       - **pontos de função:** cada ponto das duas primeiras formas (`apps.` e `config.`) precisa estar nos pontos de **cada** caso da referência;
       - **rotas:** cada `rota:<MÉTODO> <caminho>` precisa de pelo menos uma requisição, em cada caso, com o mesmo método e um `PATH_INFO` que case por inteiro com o caminho. Um parâmetro `<conversor:nome>` do caminho casa com um segmento não vazio sem `/`;
       - as formas `modulo:`, `comando:` e `fonte:` não são conferidas pela execução e continuam com a conferência estática e a leitura. A forma `banco:` passa a ser conferida pelo catálogo (R05-J7);
       - cada problema traz a chave, a referência, o caso e o ponto: `<chave> <referência> [<caso>]: ponto não executado: <ponto>`.
     - **CI:** o `ci.yml` ganha o passo `uv run python -m tests.rastreabilidade.conferir_alcance --executar alcance.json`, depois do passo da regra 3-E e com o mesmo banco. Ele acompanha a matriz em toda mudança futura.
     - **Correção das linhas:** a conferência roda sobre as 612 linhas entregues. Cada ponto acusado sai do `caminho` ou é trocado pelo ponto que a ação de fato executa. Toda linha alterada é relida com as perguntas (a) a (k), e o veredito passa a `"corrigida: ..."`. Se, sem o ponto, a linha deixar de ter um ponto que prove a ação da afirmação (pergunta (g)), a ligação sai ou a afirmação ganha uma prova, pela regra 2-G. Nunca se altera produção, nem se desliga cache ou se muda o teste só para fazer um ponto aparecer.
     - **Função executada em subprocesso:** um ponto que só roda num subprocesso não aparece no registro. A linha usa a forma do que o subprocesso executa (`modulo:` ou `comando:`), como no T-12.
     - **Casos já apontados:**
       - **Google** (as ligações de `test_sem_conta_e_sem_convite_nao_cria_nada` e `test_banido_ou_removido_nao_entra_pelo_google`, em todas as entradas em que aparecem, inclusive C2, C82, C83, T-24 e T-35): `rota:POST /entrar/` sai. Entra `apps.contas.adaptadores.AdaptadorContaSocial.pre_social_login`, mais algum outro método do adaptador real que a ação execute. A rota de teste `/teste/retorno-google/` nunca entra no `caminho`, porque é de `tests/apoio/urls.py`;
       - **C105 e T-48** (`test_incremento_compativel_e_aceito`): `apps.fornecedores.views.detalhe` e `apps.fornecedores.views.lista` saem, porque o POST sem `follow=True` não executa o destino do `Location`. Fica `apps.catalogo.views.incremento`, com o serviço que essa view chama, se registrado;
       - **as 46 ocorrências de `rota:`:** são relidas uma a uma. A rota só fica quando a requisição faz parte da ação que a afirmação nomeia, como o login recusado, a saída ou a recuperação de acesso. Um login ou uma saída feitos só para preparar o cliente saem do `caminho`, mesmo que apareçam no registro.
     - **Sem repetição:** um ponto não aparece duas vezes no mesmo `caminho`. A conferência estática acusa a repetição.
     - **Conferência estática da forma `rota:`:** a conferência por prefixo aceitava `rota:GET /`, que casa com toda rota, e `rota:POST /ent`. Ela passa a exigir duas coisas:
       - o caminho sem a barra inicial é **igual** ao texto do primeiro argumento de uma chamada `path(...)` de `config/urls.py` ou de um `urls.py` de `apps/`, com os parâmetros escritos como no texto, como em `rota:GET /convite/<str:token>/`;
       - o segundo argumento dessa chamada é uma view de dependência, ou seja, um nome (ou atributo de um nome) importado de um módulo fora de `apps` e `config`, como `allauth_views.login`.

       Um `include(...)`, uma view do projeto (que usa a primeira forma) ou uma rota só de `tests/apoio/urls.py` são recusados. Os textos de `re_path(...)` não valem para a forma `rota:`.
   - **R05-J3, C2 "Link sem conta não recebe e-mail nem abre sessão":**
     - em `test_email_sem_conta_tem_a_mesma_resposta_e_nao_envia` (`tests/tecnicos/test_contas_link_de_acesso.py`), o cliente usado no pedido do e-mail sem conta fica numa variável. Depois do pedido, o teste confere que a sessão desse cliente não tem `_auth_user_id`, além da resposta, dos links e da caixa de saída que já confere;
     - essa mudança acrescenta uma asserção a um teste existente. Ela é uma caracterização (regra 5): se passar na primeira execução, o `review.md` registra a exceção técnica. Se falhar, o implementador para e devolve, sem corrigir a produção;
     - a linha da `AUDITORIA` deixa de dizer "não confere a ausência de sessão" e é relida com (a) a (k).
   - **R05-J4, C45 "pagamentos, repasses, devoluções e demais registros financeiros anteriores continuam consultáveis e inalterados" (funcional §16.45):**
     - **arranjo:** uma rodada com um pedido X pago e quitado, apuração e aprovação do resultado, e três registros anteriores ao cancelamento, criados pelas ações de produção:
       - o pagamento aprovado de X;
       - um repasse registrado por `apps.pedidos.repasse.registrar_repasse`;
       - uma devolução anterior: uma ocorrência de entrega de X registrada por `apps.pedidos.ocorrencias.registrar_ocorrencia`, com reembolso pontual e o estorno concluído no simulador.

       Depois, o cancelamento da rodada pelo serviço ou pela rota de produção, nos dois casos, com reembolso e sem reembolso (parametrizado);
     - **"inalterados":** antes do cancelamento, o teste lê por conteúdo (`values()`, todos os campos, por `pk`) todas as linhas existentes destes modelos. Depois do cancelamento e depois de processar as tarefas que ele agenda, relê as mesmas `pk` e exige igualdade:
       - `PagamentoNoProvedor` dos pagamentos aprovados. Só `ultima_consulta_em` fica de fora, porque o cancelamento consulta o provedor antes de decidir e essa data registra a consulta;
       - `ConsultaDoPagamento`, `AvisoRecebido`, `DestinoDoPagamento`, `MovimentoFinanceiro`, `TransferenciaFinanceira`, `ObrigacaoComComprador`, `Reembolso`, `ItemReembolsado`, `ParcelaDeDevolucao`, `HistoricoDaDevolucao`, `ApuracaoNoLivro`, `PedidoApurado`, `ApuracaoFinal`, `AprovacaoDoResultado`, `Pedido`, `ItemDoPedido` e `ParcelaNoPedido`;
       - `SituacaoDoPedido` e `TentativaDePagamento` dos pedidos pagos.

       As linhas novas que o cancelamento cria (a obrigação e a parcela do reembolso, os movimentos e o histórico) são permitidas e ficam fora da igualdade. As cobranças não pagas, que o cancelamento cancela por regra aprovada, não são "pagamentos anteriores" e ficam fora;
     - **"consultáveis":** depois do cancelamento, o administrador consulta pelas telas aprovadas e vê cada registro anterior, identificado pelo valor e pela identificação do registro:
       - o recebimento do pagamento e o repasse em `GET /administracao/financeiro/movimentos/`;
       - a devolução anterior em `GET /administracao/financeiro/devolucoes/` e no detalhe dela;
     - **ligações:** as duas afirmações do C45 passam a apontar para a prova nova (uma por afirmação, ou um teste que prove as duas por inteiro). `test_cancelamento_depois_da_aprovacao_do_resultado` e `test_cenario_45_os_registros_anteriores_continuam_consultaveis_depois_do_cancelamento` saem do C45 se não provarem a afirmação por inteiro. Elas podem continuar nas afirmações que provam;
     - **devolução:** se uma regra aprovada impedir o arranjo, como o repasse antes do cancelamento ou a ocorrência depois da apuração, ou se o cancelamento mudar por regra aprovada um campo de um registro anterior da lista, o implementador para e devolve ao especificador com a referência e a saída do teste. Ele não tira o campo nem o modelo da comparação por conta própria.
   - **R05-J5, comparações de imutabilidade:**
     - **T-7, afirmação do A-16 da E11-01** (`test_aviso_espera_a_apuracao_que_ja_cancelou_y`). As asserções atuais ficam, e o teste acrescenta:
       - antes da corrida, a leitura por conteúdo de `Pedido`, `ItemDoPedido` e `ParcelaNoPedido` de Y. Depois das duas operações, a releitura dá igualdade;
       - depois das duas operações: um único `ApuracaoFinal` e um único `ApuracaoNoLivro` do ciclo, com `pedidos_pagos` 1 e `pedidos_nao_pagos` 1; os `PedidoApurado` são só o de X; nenhum `PedidoApurado` de Y. Isso separa a decisão da apuração do aviso posterior, que não cria nem muda registro de apuração;
     - **T-55, "Snapshot inalterado"** (`test_tokens_distintos_em_paralelo_se_executam_em_sequencia`). As asserções atuais ficam, e o teste acrescenta:
       - antes das duas chamadas paralelas, a leitura por conteúdo, do banco, do `PedidoFormal` e das suas `LinhaDoPedidoFormal`. Depois, a releitura dá igualdade;
       - os dois e-mails têm o corpo igual ao `corpo` relido do banco depois das chamadas, e não ao da instância em memória;
     - as duas são caracterizações (regra 5), com a primeira execução registrada.
   - **R05-J6, só funções e métodos na primeira forma:**
     - a forma `apps.<módulo>.<função>` aceita só um `def` (ou `async def`) no nível do módulo. A forma `apps.<módulo>.<Classe>.<método>` aceita só um `def` escrito diretamente no corpo da classe. Valem as mesmas regras para `config.`;
     - são recusados: uma classe sozinha (como `apps.pagamentos.provedor.NovaCobranca`), uma atribuição ou constante do módulo, um atributo de classe que não é `def`, um método herdado que não está escrito na classe citada, e mais de dois nomes depois do módulo. A recusa diz "não é função nem método";
     - as 24 ocorrências de classe em 18 linhas (`CompradorACobrar`, `ItemACobrar` e `NovaCobranca`) saem. Entra a função ou o método que a ação executa com elas, segundo o registro do alcance, como a função de cálculo que recebe `CompradorACobrar` ou o método do provedor que recebe `NovaCobranca`;
     - a lista de formas não é ampliada.
   - **R05-J7, nome real da restrição ou trigger:**
     - **a incompatibilidade:** a forma `banco:` exigia o nome completo e conferia a presença literal do nome nos `.py`. Os nomes das triggers são montados em tempo de migração, como `f"{nome_tabela}_so_insercao"` em `apps/nucleo/so_insercao.py` ou `f"{nome_tabela}_papel_imutavel"` em `apps/contas/papel_imutavel.py`. Por isso, o nome completo não aparece literalmente, e um fragmento ou o nome da tabela passava na conferência;
     - **a nova conferência:** `banco:<nome>` vale só se `<nome>` for, no banco de testes migrado, o nome exato de um destes objetos:
       - uma restrição (`pg_constraint.conname`);
       - um índice único (`pg_class.relname` de um índice com `pg_index.indisunique`);
       - uma trigger não interna (`pg_trigger.tgname` com `tgisinternal = false`).

       O nome de uma tabela, de uma função, de uma coluna ou um fragmento não vale. A leitura do catálogo fica numa função `nomes_do_banco()` em `tests/rastreabilidade/`, usada por um teste com `django_db`. A conferência recebe esse conjunto como argumento obrigatório, sem um valor padrão que pule a forma `banco:`;
     - **a construção:** o `review.md` registra, para cada nome `banco:` usado, a função de produção que o monta e a migração que a chama. Por exemplo, `pedidos_itemdopedido_so_insercao` vem de `apps.nucleo.so_insercao.instalar_protecao_so_insercao("pedidos_itemdopedido")`, chamada em `apps/pedidos/migrations/0002_restricoes.py`;
     - **as linhas:** `banco:pedidos_itemdopedido` passa a `banco:pedidos_itemdopedido_so_insercao` (C99, T-17 e T-44), e `banco:papel_imutavel` passa a `banco:contas_conta_papel_imutavel` (C62), se o catálogo confirmar esses nomes. `banco:conta_email_unico` continua;
     - nem as migrations nem os nomes do banco mudam.
   - **Registro:** o `review.md` traz:
     - a retificação do R05-J1;
     - a saída de `conferir_alcance --executar` antes da correção das linhas (os pontos acusados, por tipo) e depois (zero problemas);
     - a lista das linhas alteradas, cada uma relida com (a) a (k), com o veredito novo;
     - as ligações retiradas e as afirmações atomizadas;
     - as caracterizações novas ou acrescidas, com a primeira execução;
     - o Red e o Green das conferências novas (alcance, primeira forma, rota e banco);
     - a construção de cada nome `banco:`;
     - as devoluções ao especificador ou "Nenhuma devolução";
     - as contagens da matriz, a suíte completa, a saída de `conferir_execucao` e a de `conferir_alcance`.
   - **Revisão e encerramento:**
     - o revisor confere:
       - os sete resíduos R05-J1 a R05-J7 corrigidos;
       - as conferências mecânicas verdes, executadas por ele;
       - as linhas alteradas nesta correção, por amostra escolhida por ele, com as perguntas (a) a (k);
       - os testes novos ou alterados;
       - nenhuma mudança em `apps/` ou `config/`;
     - um achado numa linha ou num teste criado ou alterado nesta correção é resíduo da correção e volta ao implementador;
     - um achado novo numa linha não alterada, sem defeito de produção, vai para a M-15 e não reabre a R05;
     - um defeito de produção segue o fluxo normal (AGENTS.md §4.6);
     - com as correções aprovadas, a R05 é encerrada.

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
- **Auditoria por ligação, conferida no CI (regra 2-G).** Cada rodada por amostra achou resíduos de tipos novos, e cada busca por tipo deixou os outros tipos de fora. Uma linha por ligação torna a completude verificável por máquina (as chaves batem com a matriz) e a qualidade verificável por amostra do revisor (a linha bate com o corpo). O dicionário em Python segue o padrão da matriz e não traz dependência nova.
- **Guarda conservadora e congelada (regra 2-H).** Resolver qual valor uma constante tem no momento do decorador exigiria executar o módulo. Recusar a constante com mais de uma ligação ou alterada troca a aceitação indevida pela recusa a mais, que é visível e se resolve escrevendo o caso no próprio decorador. Congelar a guarda encerra a corrida entre formas novas e contraexemplos sintéticos.
- **Caminho de produção na auditoria (regra 2-J).** O veredito "íntegra" da regra 2-G foi dado a ações que o teste não executava, porque a linha descrevia o nome do auxiliar. Registrar o ponto de entrada de produção alcançado obriga a seguir o auxiliar e torna a pergunta (g) verificável na leitura do revisor. A lista fechada de formas cobre funções, corpo de módulo, comandos, rotas de dependências, banco e inspeção estática, porque nem toda prova correta passa por uma função de `apps/` (o T-12 carrega `config.settings.prod`). A existência é conferida por máquina; o alcance, pela leitura.
- **Critério de encerramento combinado antes (regra 2-I).** Ele evita rodadas sem fim e deixa com o responsável a escolha que não é técnica.
- **Alcance pela execução instrumentada (regra 2-K).** A leitura humana do alcance falhou duas vezes. A geração automática do `caminho` pôs pontos que existem mas não rodam. Registrar o que roda, com `sys.setprofile` e o sinal `request_started`, torna o alcance verificável por máquina sem dependência nova e sem tocar a produção. A distinção entre preparação e ação continua sendo da leitura. "Em cada caso" é mais estrito que "em algum caso" e corresponde à regra 3-E, que exige todos os casos.
- **`banco:` pelo catálogo (regra 2-K).** Os nomes das triggers são montados em tempo de migração. Ler o catálogo do banco migrado prova o nome real, enquanto procurar o texto nos `.py` aceita fragmentos. Ler o catálogo não executa produção além das migrações que o banco de testes já aplica.
- **Exceção de `ultima_consulta_em` no C45.** O cancelamento consulta o provedor antes de decidir, por regra aprovada, e a data da consulta é um registro dessa consulta, não do pagamento. Todos os outros campos do pagamento são comparados.
- **Defeito encontrado não é corrigido aqui.** A fatia é de evidência. Corrigir comportamento sem especificação mudaria escopo (AGENTS.md §3).

## Invariantes

- Cada cenário de 1 a 119 e cada teste técnico de T-1 a T-55 tem pelo menos um teste existente, não pulado, na matriz.
- Cada afirmação é atômica e tem pelo menos um teste que executa a ação dela e confere o resultado dela por inteiro (regra 2-E).
- Toda referência da matriz passou na última execução completa do CI (regra 3-E).
- A conferência estática só aceita uma referência cujo arquivo tenha apenas as formas da lista fechada (regra 3-D).
- O documento gerado corresponde à matriz.
- Cada ligação da matriz tem exatamente uma linha em `AUDITORIA`, e cada linha, uma ligação (regra 2-G).
- Cada linha de `AUDITORIA` nomeia no `caminho` pontos de entrada de produção que existem, numa das formas da lista fechada (regra 2-J), sem repetição. Cada ponto de função e de rota é executado em cada caso da referência (regra 2-K). Cada `banco:` é o nome exato de uma restrição, de um índice único ou de uma trigger não interna do banco migrado.
- Nenhum código de produção muda nesta fatia.

## Dependências e decisões em aberto

- Depende das E01 a E15 e, para a afirmação do histórico do cenário 96, da E16-09 (regra 2-F).
- Nenhuma dependência nova.
- O critério de encerramento da R05 foi decidido pelo responsável em 2026-11-19 (regra 2-I). Depois da sexta amostra, o responsável escolheu a nova rodada exaustiva (regra 2-J). Se a sétima amostra achar resíduos, a escolha da regra 2-I volta ao responsável.
- A sétima amostra achou os resíduos R05-J1 a R05-J7, sem defeito de produção. Em 2026-11-20, o responsável escolheu a segunda opção da regra 2-I: corrigir os apontados (regra 2-K) e registrar o restante como a melhoria M-15.
- Nenhuma outra decisão em aberto.
