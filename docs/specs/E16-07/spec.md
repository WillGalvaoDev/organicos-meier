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
3. **Conferência automática:** `tests/rastreabilidade/test_matriz.py` verifica que:
   - as chaves são exatamente as da regra 1, sem faltar nem sobrar;
   - cada referência aponta para um arquivo existente em `tests/` e para uma função `test_*` (ou método numa classe `Test*`) definida nele. A conferência é feita lendo a árvore de sintaxe do arquivo, sem importar nem rodar o teste;
   - nenhuma referência aponta para teste marcado com `skip`, ou com `skipif` sempre verdadeiro no CI;
   - nenhuma referência se repete na mesma lista.
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
