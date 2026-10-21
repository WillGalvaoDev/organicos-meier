# E08-02 — Abertura do pagamento e pedidos congelados

Fatia 2 de 7 da milestone **E08 — Cobrança: abertura, congelamento e prazos**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Com o fechamento encerrado e o mínimo atingido, a rodada fica aguardando o administrador (E06-05). Ao autorizar o pagamento, ele informa o frete. O servidor então:

1. registra `T0`;
2. confere de novo as caixas e o mínimo, com os preços vigentes;
3. congela um pedido por comprador, com itens, caixas e valores;
4. avisa os compradores.

A partir daí, a composição do pedido não muda mais.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §6.3 | "Ao abrir pagamento, congelar a composição das caixas e registrar quais parcelas de cada comprador pertencem a cada caixa. Não redistribuir compradores entre caixas em razão de inadimplência." |
| Especificação §7, §7.1 | Pagamento inicia por ação administrativa, em `T0`, com frete informado e pedidos congelados. Não aceita novos compradores nem alterações. A composição é definitiva, e não há edição nem correção. O estado financeiro e operacional é registrado à parte. |
| Especificação §8.1 | "Antes de autorizar pagamento, validar mínimo e caixas, informar frete e calcular pedidos individuais. Gerar uma obrigação de pagamento por comprador e por rodada de fornecedor." |
| Especificação §5, §5.1 | Na fase de pagamento, o pedido é congelado e só é possível pagar ou não pagar. Pedidos que entraram em pagamento preservam o preço. "Se uma redução de preço derrubar o total elegível abaixo do mínimo ao término do fechamento, retornar para interesse." |
| Especificação §9, §12 | Valores congelados e componentes separados. Aviso "Abertura do pagamento": pedido congelado, discriminação de valores e prazo oficial de 24h, sem prorrogação. |
| Infraestrutura 4.3 | `T0` é o instante em que o administrador autoriza a abertura, gravado pelo servidor em UTC. |
| Infraestrutura 4.9 | Itens do pedido protegidos contra `UPDATE` e `DELETE` por trigger, sem rotas de edição. A tentativa de alteração é recusada e registrada. O estado fica em registros próprios. |
| Infraestrutura 4.12 | Preço unitário, quantidade e subtotal cobrado gravados no snapshot do pedido. |
| Cenários §16 | 11, 24 (com o simulador), 47, 65. |
| Testes técnicos | T-17. |
| Herdado da E04 | `pagamento_aberto` emitido na transação do fato, com chave derivada; o cenário 24 é repetido com o WhatsApp simulado falhando. |
| Herdado da E05 | A pendência de uma parcela `ativa` atendida em parte pela fila continua removível e atendível. O pedido usa o preço vigente na abertura, e o aviso de preço não alcança o que está em pedido. |
| Herdado da E06 | A abertura parte de `fechamento_encerrado`. O botão fica no bloco "Fechamento" da página de estoque. A divisão por sequência é a da E05-04. Também falta definir o efeito de uma alteração de preço antes da abertura. |

## Escopo

**Dentro:**

- Os modelos `AberturaDoPagamento`, `Pedido`, `ItemDoPedido`, `ParcelaNoPedido` e `SituacaoDoPedido`.
- O serviço `abrir_pagamento`.
- O botão e a rota no bloco "Fechamento".
- O aviso `pagamento_aberto`.
- A proteção dos pedidos contra alteração.

**Fora:**

- O pagamento em si (E08-03 e E08-04).
- Os prazos de 24 e 48 horas (E08-05).
- As telas do comprador para pagar (E08-03).
- A apuração (E11).

## Decisões técnicas

- **Nova conferência na abertura.** Entre o fim do fechamento e a abertura, as caixas e o mínimo podem mudar. A suspensão ou a remoção de um comprador tira as reservas dele (E05-07), e o preço continua alterável (§5.1). A especificação manda validar mínimo e caixas antes de autorizar (§8.1). Por isso, a abertura refaz, com as travas, os dois passos do encerramento (E06-05):
  1. a divisão por sequência, removendo e avisando o que não completa caixa;
  2. a verificação do mínimo, com os preços vigentes.

  Se o mínimo não for atingido, vale a regra de falha do §7 e do §5.1: a rodada volta para interesse, e nenhum pedido é criado. Com isso fica definido o efeito de uma alteração de preço antes da abertura (herança da E06): o novo preço entra no `T` e na verificação do mínimo da abertura.
- **Pedido e estado separados.** `AberturaDoPagamento`, `Pedido`, `ItemDoPedido` e `ParcelaNoPedido` só aceitam inserção, com a trigger da E01-04. A situação de cada pedido fica em `SituacaoDoPedido`, que é a única tabela alterável e muda só pelos serviços.
- **Parcela atendida em parte pela fila** (herança da E05). Uma parcela `ativa` pode ter, ao mesmo tempo, quantidade reservada e quantidade pendente (E05-02). Na abertura, a parte reservada vai para o pedido e fica registrada em `ParcelaNoPedido`. A parcela fica assim:
  - **sem pendente:** passa a `em_pedido`, com a reserva inalterada (como já previa a E05);
  - **com pendente:** passa a `pendente`, com reserva zero. A sequência continua a mesma, então a parte pendente segue na fila na posição original. A remoção (E05-03), a exibição separada (E05-05) e o atendimento da fila (E05-02) continuam valendo sem mudança, porque todos já tratam parcelas `pendente`.

  A quantidade congelada dessa parcela fica só no pedido, e não em `quantidade_reservada`. Durante o pagamento ninguém reserva nesta rodada, então a contagem de estoque não muda nada. Quando a apuração (E11) devolver uma rodada ao interesse, ela restaura as reservas dos pedidos antes de atender a fila.
- **Caixas numeradas por produto.** Num produto com múltiplo `m`, as unidades entram nas caixas pela ordem de `sequencia` das parcelas de todos os compradores: a caixa 1 recebe as primeiras `m`, a caixa 2 as seguintes, e assim por diante. Uma parcela que cruza o limite de uma caixa gera duas linhas em `ParcelaNoPedido`. Num produto sem múltiplo, `caixa` fica nulo.
- **Registro das tentativas de alteração.** Pelo ORM, a tentativa de alterar ou apagar um pedido levanta `RegistroImutavel`, e antes disso os modelos do pedido gravam um log `warning` `"Tentativa de alterar pedido congelado: <modelo> <id>"`. Por SQL direto, a trigger recusa a operação, e o próprio Postgres registra o erro no log dele.
- **Sem nova autenticação.** A infraestrutura (seção 2) exige nova autenticação para apuração, estornos, devoluções excepcionais, repasses, aportes e movimentações. A abertura não está nessa lista e segue o padrão do início do fechamento: `somente_administrador`.

## Regras

### Modelos (`apps/pedidos/models.py`)

**`AberturaDoPagamento`** (só inserção):

| Campo | Regra |
|---|---|
| `ciclo` | `OneToOne` com `rodadas.Ciclo`: uma abertura por ciclo |
| `rodada` | a rodada |
| `t0` | instante da abertura, `agora()` lido depois das travas |
| `frete` | `CampoDinheiro`, ≥ 0 |
| `total_produtos` | o `T`, maior que zero |
| `autor` | o administrador |

**`Pedido`** (só inserção):

- `abertura`, `comprador`, `produtos`, `servico`, `frete` e `total`;
- `UNIQUE (abertura, comprador)`;
- `CHECK total = produtos + servico + frete`, `produtos > 0`, `servico ≥ 0` e `frete ≥ 0`.

**`ItemDoPedido`** (só inserção):

- `pedido` e `produto`;
- cópia do produto na abertura: `nome`, `unidade`, `incremento` e `multiplo`;
- `preco_unitario`, `quantidade` e `subtotal`;
- `UNIQUE (pedido, produto)`;
- `CHECK quantidade > 0` e `subtotal ≥ 0`.

**`ParcelaNoPedido`** (só inserção):

- `item`, `parcela` (`interesses.ParcelaDeInteresse`), `caixa` (inteiro ≥ 1 ou nulo) e `quantidade > 0`;
- `UNIQUE (item, parcela, caixa)`, com nulos iguais (`nulls_distinct=False`).

**`SituacaoDoPedido`** (alterável só pelos serviços):

| Campo | Regra |
|---|---|
| `pedido` | `OneToOne` |
| `situacao` | `aguardando_pagamento`, `pago` ou `cancelado` |
| `quitado_por` | `pagamentos.PagamentoNoProvedor`, nulo; único |
| `quitado_em` | nulo |
| `cancelado_em` | nulo |
| `motivo_do_cancelamento` | `suspensao`, `remocao_da_conta` ou vazio |

`CHECK`s:

- `pago` ⇔ `quitado_por` e `quitado_em` preenchidos;
- `cancelado` ⇔ `cancelado_em` e motivo preenchidos;
- `aguardando_pagamento` sem nenhum dos quatro.

As transições são das fatias E08-04 e E08-06. A E11 acrescenta as suas.

As quatro tabelas só de inserção recebem `instalar_protecao_so_insercao`.

### Serviço (`apps/pedidos/abertura.py`)

```
abrir_pagamento(autor: Conta | None, rodada: Rodada, frete: Decimal) -> ResultadoDaAbertura
```

`ResultadoDaAbertura` tem `abertura: AberturaDoPagamento | None` e `etapa_final` (`pagamento` ou `interesse`).

1. Sem administrador, `PermissionDenied`, sem gravar nada.
2. `frete` inválido (não `Decimal`, negativo, mais de duas casas ou além da capacidade de `CampoDinheiro`): `ValueError`.
3. Numa transação, com as travas nesta ordem:
   - fornecedor;
   - rodada;
   - os produtos da rodada, por id;
   - em cada produto, o estoque e as parcelas, pela divisão da E06-05.
4. A rodada precisa estar em `fechamento_encerrado`. Senão, `TransicaoRecusada("fora_de_fechamento_encerrado_para_pagamento")`, com a mensagem "Só uma rodada com o fechamento encerrado pode abrir o pagamento.".
5. `T0 = agora()`, lido depois das travas.
6. Antes de qualquer gravação, guarda os compradores com reserva, que são os destinatários de um eventual retorno.
7. **Divisão:** refaz a divisão por sequência das parcelas `ativa` (`_divisao_dos_excedentes`). O que sai é avisado com `excedentes_removidos`, no momento "abertura do pagamento":
   - corpo: "Na abertura do pagamento da rodada de <fornecedor>, <q> <unidade> de <produto> não completaram caixa e foram removidas do seu interesse. Continuam no seu interesse: <q> <unidade>.";
   - chave: `excedentes_removidos:abertura:<ciclo>:<produto>:<comprador>`.

   O aviso do fim do fechamento continua com o texto e a chave atuais.
8. **Mínimo:** `progresso_da_rodada` com os preços vigentes. Se não for atingido:
   - `voltar_para_interesse(rodada, motivo="minimo_nao_atingido_na_abertura", destinatarios=<os do passo 6>)`. O motivo é acrescentado a `MOTIVOS_DE_RETORNO`, com o corpo "A rodada de <fornecedor> voltou para a fase de interesse porque o mínimo do fornecedor não foi atingido na abertura do pagamento. Os interesses que continuam reservados seguem na rodada, e você pode alterá-los. Nada foi cobrado neste ciclo, então não há estornos.";
   - auditoria `rodada.abrir_pagamento` com `resultado` `retorno_para_interesse`;
   - devolve `etapa_final` `interesse`, sem abertura.
9. **Congelamento:**
   - lê as parcelas `ativa` com reserva maior que zero, por produto e por `sequencia`;
   - numera as caixas e monta, por comprador, um `ItemACobrar` por produto, com o preço vigente e a soma das reservas;
   - chama `calcular_cobranca` (E08-01);
   - grava a `AberturaDoPagamento`, os `Pedido`s, os `ItemDoPedido`s, as `ParcelaNoPedido`s e uma `SituacaoDoPedido` `aguardando_pagamento` por pedido;
   - muda cada parcela congelada para `em_pedido` ou para `pendente`, como nas Decisões técnicas.
10. **Etapa:** a rodada passa a `pagamento`.
11. **Auditoria `rodada.abrir_pagamento`** (autor), com:
    - `rodada`, `ciclo` e `t0` em ISO 8601 UTC;
    - `frete` e `total_produtos`, como texto;
    - `pedidos`, a quantidade;
    - `removidas`, como no encerramento;
    - `resultado` `pagamento`.
12. **Aviso `pagamento_aberto`**, um por pedido, para o comprador:
    - título: "Pagamento aberto: <fornecedor>";
    - corpo: "Seu pedido da rodada de <fornecedor> foi congelado. Produtos: R$ <P>. Serviço: R$ <S>. Frete: R$ <F>. Total: R$ <total>. Pague até <dd/mm/aaaa> às <HH:MM> (horário de Brasília). Esse prazo de 24 horas não é prorrogado.";
    - link: `/pedidos/<id>/`;
    - chave: `pagamento_aberto:<pedido>:<comprador>`.

    O prazo mostrado é `T0 + 24h` (E08-05), no fuso da operação.
13. Devolve a abertura, com `etapa_final` `pagamento`.

Tudo acontece numa transação: uma falha desfaz a abertura inteira.

### Tela

**Bloco "Fechamento" da página de estoque (E06-07):**

- **Em `fechamento_encerrado`:** mostra o formulário "Abrir pagamento", com o campo "Frete total (R$)" (texto com vírgula, lido por `ler_decimal_digitado(…, 2)`) e o botão "Abrir pagamento".
- **Em `pagamento`:** mostra o `T0`, o fim do prazo de pagamento e o fim da margem, no fuso da operação. A E08-05 acrescenta a situação dos pedidos.

**Rota** `POST /administracao/rodadas/<pk>/pagamento/abrir/`, nome `rodadas_pagamento_abrir`, com `somente_administrador` e `require_POST`. As respostas são:

| Caso | Resposta |
|---|---|
| sucesso | redireciona para a página de estoque com "Pagamento aberto. Prazo: <dd/mm/aaaa> às <HH:MM> (horário de Brasília)." |
| retorno por mínimo | redireciona com o aviso "O mínimo não foi atingido na abertura do pagamento. A rodada voltou para a fase de interesse." |
| frete inválido | 400, com a página e o erro no campo: "Informe o frete em reais, com até duas casas decimais, por exemplo 40,00." |
| `TransicaoRecusada` | 409, com a mensagem |

Não existe rota, formulário nem tela que altere `T0`, o frete, um pedido ou um item depois da abertura.

## Interfaces

- `apps/pedidos/models.py`: os cinco modelos, com a migração e as triggers.
- `apps/pedidos/abertura.py`: `abrir_pagamento` e `ResultadoDaAbertura`.
- `apps/rodadas/avisos.py`: `avisar_excedentes_removidos` ganha o argumento `momento` (`fim_do_fechamento` ou `abertura_do_pagamento`). `avisar_retorno_para_interesse` passa a receber o motivo.
- `apps/rodadas/fechamento.py`: o motivo `minimo_nao_atingido_na_abertura`.
- `apps/rodadas/views.py`, o template e `config/urls.py`: o formulário e a rota.

## Invariantes

- Uma abertura por ciclo.
- Um pedido por comprador e por abertura.
- Depois da abertura, nenhum registro de `AberturaDoPagamento`, `Pedido`, `ItemDoPedido` ou `ParcelaNoPedido` muda nem some, nem por SQL direto.
- Toda parcela congelada aparece em `ParcelaNoPedido` com a quantidade reservada que tinha depois da divisão. A soma por item é a `quantidade` do item.
- Num produto com múltiplo, cada caixa tem exatamente `m` unidades.
- O `T` da abertura é igual ao valor elegível do progresso, calculado sob as mesmas travas e com os mesmos preços.

## Casos-limite e concorrência

- **Comprador suspenso entre o fim do fechamento e a abertura:** a reserva dele já saiu (E05-07). A divisão refeita remove o que deixou de completar caixa, e o mínimo é conferido de novo.
- **Preço reduzido antes da abertura**, derrubando o mínimo: a rodada volta para interesse.
- **Preço alterado ao mesmo tempo que a abertura:** a abertura trava os produtos.
  - Se o preço foi gravado antes, o pedido já usa o preço novo.
  - Se foi gravado depois, o pedido fica com o preço anterior. O aviso de preço não alcança ninguém, porque as parcelas congeladas não estão mais `ativa`.
- **Duas aberturas ao mesmo tempo:** a segunda espera a trava, vê a rodada em `pagamento` e recebe `TransicaoRecusada`. A restrição única do ciclo é a segunda barreira.
- **Interesse depois da abertura:** recusado como hoje, porque a etapa `pagamento` não aceita interesses (E05-01).
- **Remoção de pendente depois da abertura:** continua permitida, porque só toca a parte pendente (Q-5).

## Dependências e decisões em aberto

- Depende de E01-04, E04-02, E05-01 a E05-07, E06-05 a E06-07 e E08-01.
- Sem decisões em aberto.

## Correção E08-R04 — pedido de valor zero (2026-10-21)

Origem: parecer do agente 3 sobre `2714a6a` (`docs/specs/E08-01/review.md`, R04).

### Diagnóstico

A §4.2 aceita incrementos de até três casas, e a §9 arredonda cada subtotal uma única vez, com `ROUND_HALF_UP`. Juntas, elas permitem um item de valor zero. Por exemplo, 0,001 kg de um produto de R$ 0,01/kg dá R$ 0,00001, e o subtotal arredondado é R$ 0,00.

- **Um item zero ao lado de outros itens.** O pedido sai com um item de graça.
- **Todos os itens do comprador zerados.** O pedido fica com `produtos = 0`, e a restrição `pedido_produtos_positivo` derruba a abertura inteira, com `IntegrityError` e resposta 500.

A especificação não dizia como tratar esse caso, e a solução não podia ser deduzida. Por isso o ponto ficou bloqueado por decisão.

### Decisão do responsável pelo projeto (2026-10-21)

**Restringir no cadastro.** Um produto só é aceito se a menor quantidade que o comprador pode escolher já custar pelo menos R$ 0,01 depois do arredondamento:

```
preco × incremento ≥ R$ 0,005
```

Como toda quantidade aceita é um múltiplo positivo do incremento (§4.2), nenhum subtotal pode arredondar para zero. Assim, nenhum item e nenhum pedido pode valer zero, e a abertura não precisa de um fluxo para o pedido zero. Fica proibido:

- criar uma cobrança mínima;
- descartar a quantidade;
- marcar o pedido como pago.

A regra só existe por causa do arredondamento da §9 e não muda o preço nem o incremento de nenhum produto válido.

### Regras

Valem em `apps/catalogo`. A comparação é feita em `Decimal` exato, e a fronteira é inclusiva: R$ 5,00 com incremento 0,001 dá R$ 0,005 e é aceito.

| Onde | Quando recusa | Erro e mensagem |
|---|---|---|
| `criar_produto` | `preco × incremento < 0,005`, depois das validações próprias de preço e incremento | `ValidationError({"preco": [...]})`: "Com este preço e este incremento, a menor quantidade custaria menos de R$ 0,01. Aumente o preço ou o incremento." |
| `editar_produto` (mudança de preço, em qualquer etapa) | o preço novo, com o incremento atual do produto travado, dá menos de 0,005 | o mesmo `ValidationError`, com a mesma mensagem. Nada é gravado: sem `produto.editar`, sem `produto.alterar_preco` e sem `preco_alterado`. |
| `alterar_incremento` | o incremento novo, com o preço atual do produto travado, dá menos de 0,005. É a última recusa, depois de fase, valor, quantidades em uso e múltiplo. | `IncrementoIncompativel("centavo")`: "Com este incremento, a menor quantidade custaria menos de R$ 0,01 ao preço atual." |
| Banco | qualquer gravação que viole a regra | `CHECK (preco * incremento >= 0.005)`, com o nome `produto_menor_quantidade_custa_um_centavo` e a migração correspondente |

Nas telas, as mensagens aparecem nos formulários de produto e de incremento pelo caminho de erro que já existe (`_erros_do_servico` e `form.add_error`), sem rota nova.

A fase 1 não tem dados de produção, então a migração não precisa corrigir registros antigos. Testes antigos cujo arranjo use uma combinação recusada recebem dados válidos. Essa mudança só é permitida quando o teste não trata da regra. O implementador lista cada teste ajustado no registro, com o valor antigo e o novo.

### Efeito na abertura

O caminho da abertura não muda. A restrição `pedido_produtos_positivo` continua como segunda barreira e passa a ser inalcançável com dados aceitos.

A prova R04 do revisor criava o produto pela fábrica, sem passar pelo serviço. Com a decisão, essa criação passa a ser recusada pelo `CHECK`. O cenário é substituído pelos critérios A-22 a A-27. Destes, o A-26 abre o pagamento com a menor combinação aceita e confere a abertura inteira, os outros compradores e o rateio.

### Fora do escopo

- **A §4.2 da especificação funcional.** O especificador não altera documentos de regra de negócio. A decisão fica registrada aqui, e incluí-la na §4.2 cabe ao responsável pelo projeto.
- **A E03.** Ela não é reaberta: a regra entra nos serviços do catálogo como consequência desta correção.

## Correção E08-R06 — evidência de TDD (2026-10-21)

Origem: parecer do agente 3 sobre `2714a6a`, R06. Esta seção vale para toda a E08. Os outros `spec.md` só remetem a ela.

### Diagnóstico

Dois grupos de critérios não têm Red válido comprovado antes do código de produção.

1. **E08-02 A-4 e A-11.** O registro do implementador diz:
   - o primeiro Red não falhou pelo comportamento;
   - o Red válido foi obtido depois, com o "andaime trocado de volta", isto é, sem a base de só inserção, sem as restrições, sem a migração `0002` e com o serviço vazio.

   Isso mostra que os testes detectam a ausência dessas proteções. Não mostra que a falha veio antes da implementação.
2. **Critérios de concorrência:** E08-02 A-20 e A-21, E08-03 A-19, E08-04 A-16 e A-17, e E08-06 A-11.
   - Os Reds registrados foram contra serviços vazios: o teste falhou porque não havia abertura, tentativa, destino ou cancelamento.
   - A prevenção da E05-R04 (E05-01) exige outra sequência: o comportamento funcional verde sem a proteção, depois o Red da corrida e só então a trava.
   - Um Red pela ausência de todo o comportamento não demonstra esse ciclo.

O E08-05 A-20 é um controle já verde sobre a quitação herdada e está corretamente declarado assim. Ele não entra nesta correção.

### Tratamento — decisão do responsável pelo projeto (2026-10-21)

É o mesmo tratamento das correções E05-R04 (2026-10-18) e E06-R05 (2026-10-19), escolhido de novo para a E08. Ele não vira dispensa automática para as próximas etapas.

1. **Procurar a evidência que existe.** Para cada critério dos dois grupos, o implementador procura evidência de um Red válido anterior ao código de produção. Servem:
   - commits locais;
   - logs guardados com data;
   - saídas registradas no momento.

   Se encontrar, registra a referência exata (hash, arquivo de log e trecho), e o critério sai da lista. Não vale uma execução nova, nem um andaime recriado, nem uma inferência sobre a ordem.
2. **Registrar a não conformidade.** Para os critérios que ficarem, o implementador acrescenta ao `review.md` da fatia uma seção "Não conformidade de TDD" com:
   - os critérios;
   - o que aconteceu, por exemplo: "Red obtido contra andaime recriado depois do código; sem Red observado antes do código de produção" ou "Red só pela ausência do serviço; sem o ciclo verde sem trava → Red da corrida → trava";
   - o tratamento aplicado;
   - a confirmação ou correção das causas abaixo.

   O registro anterior é preservado sem edição, e nenhum texto pode dar a entender que houve Red nesses critérios.
3. **Provar a sensibilidade por mutação.** É uma prova por critério, com o título "sensibilidade (mutação), não Red". A mutação retira só a proteção que o critério descreve, e não o comportamento inteiro. Exemplos:

   | Critério | Mutação |
   |---|---|
   | E08-02 A-4 | congelar a parcela inteira como `em_pedido`, ignorando a parte pendente |
   | E08-02 A-11 | duas mutações, uma por caminho: retirar a recusa do ORM (a base de só inserção) de um dos modelos; retirar a trigger de um dos modelos |
   | E08-02 A-20 | reler a rodada sem `select_for_update` em `abrir_pagamento` |
   | E08-02 A-21 | ler os produtos sem trava na abertura |
   | E08-03 A-19 | ler a `SituacaoDoPedido` sem trava em `pedir_pagamento` |
   | E08-04 A-16 | decidir o destino sem travar a `SituacaoDoPedido` |
   | E08-04 A-17 | decidir sem reler, sob a trava, se o pagamento já tem destino |
   | E08-06 A-11 | nenhuma: o critério foi reescrito pela correção E08-R02 e ganha um Red real (E08-06). O texto antigo entra só no registro da não conformidade (passo 2). |

   Para cada mutação, o registro traz:
   - o trecho mudado e o comando, com arquivos inteiros e sem `-k`;
   - a falha por asserção (tempo esgotado ou erro de infraestrutura não servem);
   - a mutação desfeita e o teste verde.

   Se uma mutação razoável não fizer o teste falhar, o implementador registra isso como limite do teste e propõe o reforço do teste, sem mudar o critério.
4. **Correções com Red real.** Os critérios novos das correções E08-R01 a E08-R05 seguem Red → Green → Refactor com as regras de prevenção. Isso inclui o E08-06 A-11 reescrito.

Os passos 2 e 3 são o tratamento definitivo dos critérios antigos.

### Causas prováveis, a confirmar pelo implementador

1. **O Green foi maior que o mínimo.** As travas entraram junto com o comportamento funcional. Nenhum teste em falha exigia essas travas naquele momento.
2. **A tabela de cobertura não separava os tipos de critério.** Ela não distinguia o critério de concorrência do funcional, então um Red pela ausência do serviço pareceu suficiente.
3. **O andaime dependia dos testes.** No A-4 e no A-11, os testes só foram corrigidos depois que o andaime já tinha sido substituído.

### Prevenção (soma-se às da E05-R04 e da E06-R05)

- **Concorrência com duas linhas no registro.** A tabela de cobertura do Red registra cada critério de concorrência em duas linhas:
  - o "verde funcional sem a proteção", com o comando;
  - o "Red da corrida", com a falha observada.

  A trava só é escrita depois da segunda linha.
- **Teste corrigido depois do andaime.** Se um teste precisar de correção depois que o andaime foi substituído, o implementador para e registra o fato antes de seguir (Red tardio, E06-R05). Não volta a montar o andaime.

### Complemento da segunda revisão (2026-10-21)

O responsável pelo projeto estendeu este tratamento ao E08-06 A-11 reescrito, que antes estava excluído (passo 3). A regra e a prevenção adicional estão em `docs/specs/E08-06/spec.md`, na seção "Correção E08-R06, segunda revisão".
