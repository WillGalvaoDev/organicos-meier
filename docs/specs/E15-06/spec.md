# E15-06 — Histórico de ações relevantes

Fatia 6 de 7 da milestone **E15 — Painel administrativo e alertas operacionais**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E15-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E15-01.

## Contexto e objetivo

A §13 pede ao administrador o "histórico de ações relevantes", e a §7 diz que toda intervenção deve ser auditada. As etapas anteriores gravam essas ações em `EntradaAuditoria` (E01-04, só inserção), mas nenhuma tela as mostra. Esta fatia cria a consulta, só de leitura.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, administrador | Comunicados gerais e histórico de ações relevantes. |
| Especificação §7 | Toda intervenção deve ser auditada; nenhuma intervenção apaga histórico. |
| Infraestrutura 5 | Auditoria só aceita inserção; dados pessoais mínimos. |
| E01-04 | `EntradaAuditoria`: autor (tipo e id em texto), ação, momento, motivo, alterações, objeto (tipo e id). |

## Escopo

**Dentro:** a página `administracao/historico/` e o link no painel (E15-05, regra 11).

**Fora:**
- exportação;
- alteração de qualquer entrada;
- a tradução das ações para textos de negócio (ver "Decisões técnicas").

## Regras

1. **Rota:** `GET administracao/historico/` (nome `historico_acoes`), com `somente_administrador`. `POST`: 405. Comprador e fornecedor: 403. Anônimo: login.
2. **Lista:** todas as `EntradaAuditoria`, da mais nova para a mais antiga (`momento` desc, depois `pk` desc), com 50 por página (`?pagina=`, `Paginator.get_page`). Colunas:
   - **Data e hora**, em Brasília, `dd/mm/aaaa hh:mm:ss`;
   - **Autor:**
     - "Sistema" quando `autor_tipo = sistema`;
     - o nome da `Conta` quando o id existe;
     - senão, "Conta <id>";
   - **Ação:** o código gravado (por exemplo, `rodada.abrir_pagamento`);
   - **Objeto:** "<objeto_tipo> <objeto_id>";
   - **Motivo:** ou "—";
   - **Alterações:** uma linha "<chave>: <valor>" por chave de primeiro nível, com o valor em JSON compacto, sempre escapado pelo template.
3. **Filtros** (GET, combináveis, preservados na paginação):
   - **`acao`:** valor exato, escolhido numa lista das ações distintas já gravadas, em ordem alfabética;
   - **`autor`:** "sistema" ou o pk de uma conta de administrador; a lista mostra "Sistema" e os administradores pelo nome;
   - **`de` e `ate`:** datas `aaaa-mm-dd`, inclusivas, interpretadas como dias de Brasília (de 00:00 do `de` até o fim do `ate`).

   Um filtro com valor inválido (ação fora da lista, autor que não é "sistema" nem administrador, data malformada, `de` maior que `ate`) é **ignorado**. A página mostra "Filtro inválido ignorado: <nome do filtro>." e responde 200.

3-A. **Limites de entrada (correção E15-R05).** Nenhum valor recebido nos filtros ou em `pagina` pode levantar exceção nem dar resposta diferente de 200. Valem as formas exatas abaixo; qualquer outra é inválida e segue a regra 3.
   - **`autor`:** "sistema", ou só dígitos ASCII `0`–`9`, sem sinal, espaço ou separador, com o primeiro dígito diferente de zero e no máximo 18 dígitos. Isso cabe sempre no pk (`BigAutoField`). Depois disso, precisa ser o pk de uma conta de administrador. Exemplos inválidos: `²`, `١٢` (dígitos não ASCII), `+1`, `-1`, ` 1`, `0`, `01`, `1e3` e 19 ou mais dígitos.
   - **`de` e `ate`:** exatamente `aaaa-mm-dd`, com dígitos ASCII, e uma data que existe no calendário. `date.fromisoformat` só é chamado depois de conferido o formato. Exemplos inválidos: `2026-11-18T00:00`, `20261118`, `2026-11-18 ` (com espaço), `２０２６-11-18` e `2026-02-30`.
   - **Limites do calendário:** os limites do período são instantes de Brasília. O inferior é 00:00 do `de`, e o superior é o fim do `ate`, ambos inclusivos. Quando o instante não pode ser representado, o limite correspondente não é aplicado, sem erro e sem aviso. É o caso do fim de `9999-12-31`, que não tem dia seguinte, e de um limite que em UTC sai do intervalo de `datetime`. Assim, `ate=9999-12-31` lista tudo até o fim, e `de=0001-01-01` lista desde o começo.
   - **`pagina`:** como hoje, `Paginator.get_page`: texto não numérico dá a primeira página, e número além do fim dá a última.
4. **Sem resultado:** "Nenhuma ação encontrada.".
5. **Só leitura:** a página não grava nada, nem auditoria de leitura.
6. **Link no painel:** "Histórico de ações" na navegação do painel (E15-05, regra 11).

## Decisões técnicas

- **Código da ação, sem tradução.** Os códigos são estáveis e já descrevem a ação (`rodada.cancelar`, `devolucao.autorizar`). Um dicionário de rótulos teria de acompanhar cada etapa, e um código sem rótulo apareceria em branco. O filtro por ação torna a lista navegável.
- **Todas as entradas.** As etapas só auditam ações relevantes: intervenções do administrador e decisões do sistema com efeito comercial ou financeiro. Filtrar por uma lista própria de "relevantes" esconderia registros sem critério da especificação.
- **Nome da conta na hora da leitura.** A auditoria não copia dados pessoais (E01-04). O nome vem da conta atual e, se a conta não existir, fica só o id.

## Invariantes

- Nenhuma escrita em `EntradaAuditoria` ou em qualquer outra tabela.
- Nenhum HTML vindo das alterações é interpretado.

## Dependências e decisões em aberto

- Depende da E01-04 e da E15-05 (link).
- Nenhuma decisão em aberto.
