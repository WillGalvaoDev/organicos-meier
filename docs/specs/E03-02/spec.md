# E03-02 — Rodadas, fase de interesse e alteração do mínimo

Fatia 2 de 8 da milestone **E03 — Fornecedores, catálogo e condições da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

As condições da rodada (mínimo, múltiplo, incremento e estoque) só podem ser alteradas na fase de interesse da rodada ativa do fornecedor. A partir do início do fechamento, ficam congeladas, inclusive para o administrador.

Esta fatia entrega:

1. a rodada, com as etapas do ciclo;
2. a regra de uma rodada ativa por fornecedor;
3. a abertura de rodada pelo administrador;
4. a **primitiva única de verificação da fase de interesse**, com a ordem de travas que todas as alterações de condição usam;
5. a primeira dessas alterações: o mínimo do fornecedor.

As transições entre etapas (fechamento, pagamento e as seguintes) não são desta etapa. Elas entram na E06 e nas etapas posteriores.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §4.1 | O mínimo monetário só pode ser alterado durante a fase de interesse da rodada ativa. |
| Especificação §4.3 | A rodada é de um único fornecedor. Uma rodada ativa por fornecedor. A rodada deixa de impedir outra quando os produtos são liberados para retirada. A rodada em interesse pode durar indefinidamente. |
| Especificação §4.4 | Mínimo, múltiplos, incremento e estoque só são alteráveis na fase de interesse. Congelados a partir do fechamento, inclusive para o administrador. Voltando a interesse, são alteráveis de novo. |
| Especificação §7 | Etapas: interesse, fechamento, fechamento com prazo encerrado, pagamento (com margem operacional e aptidão para apuração definidas pelo tempo a partir de `T0`), aguardando fornecedor, disponível para retirada, cancelada. |
| Especificação §13 | Administrador: mínimo editável só na fase de interesse. |
| Cenários §16 | 71 e 72, na parte do mínimo. |
| Infraestrutura 4.10 | O servidor recusa a alteração em qualquer outra etapa, inclusive para o admin. |
| Infraestrutura 4.3 | Margem e aptidão para apuração são intervalos de tempo contados de `T0`. |
| Infraestrutura 5 | `transaction.atomic` e `select_for_update` nas operações críticas. |
| Testes técnicos | T-23, na parte do mínimo. |

## Escopo

**Dentro:**

- App `apps.rodadas`, com o modelo `Rodada` e o enum `Etapa`.
- Serviço `abrir_rodada` e o sinal `rodada_aberta`.
- Primitiva `travar_condicoes(fornecedor)`, a exceção `CondicoesCongeladas` e a ordem de travas.
- Serviço `alterar_minimo` e a tela correspondente.
- Rodada ativa e botão de abertura no detalhe do fornecedor (E03-01).

**Fora:**

- Transições de etapa (E06 em diante) e cancelamento da rodada (etapa própria).
- Estoque por rodada (E03-05) e registro das condições do ciclo (E03-07).
- Reserva dos pendentes na abertura (`alocar_pendentes`, E05), que se conecta ao sinal `rodada_aberta`.

## Regras

**Etapas** (`Etapa`, valores gravados):

| Valor | Etapa funcional (§7) | Rodada ativa |
|---|---|---|
| `interesse` | Interesse | sim |
| `fechamento` | Fechamento | sim |
| `fechamento_encerrado` | Fechamento com prazo encerrado | sim |
| `pagamento` | Pagamento, margem operacional e apta para apuração final; as três se distinguem pelo tempo contado de `T0` (infraestrutura 4.3) | sim |
| `aguardando_fornecedor` | Aguardando fornecedor | sim |
| `disponivel_para_retirada` | Disponível para retirada | não |
| `cancelada` | Cancelada | não |

- **Valores fixados agora:** são os nomes funcionais da §7. As etapas seguintes podem acrescentar valores, mas não renomear nem remover estes.
- **Mudança de etapa:** nesta etapa, só a abertura cria uma rodada, sempre em `interesse`. Nenhuma rota desta etapa muda a etapa de uma rodada existente.

**Rodada** (`Rodada`):

- `fornecedor` (FK `PROTECT`);
- `etapa`;
- `aberta_em`, preenchido com `agora()`;
- `aberta_por` (FK para a conta do administrador, `PROTECT`).

**Uma rodada ativa por fornecedor:**

- Índice único parcial em `fornecedor` para etapas ativas, isto é, diferentes de `disponivel_para_retirada` e `cancelada`.
- É a última defesa contra a concorrência. O serviço também verifica antes.

**Abertura** (`abrir_rodada(autor, fornecedor) -> Rodada`):

1. Exige o administrador; caso contrário, `PermissionDenied`.
2. Em `transaction.atomic()`, trava a linha do fornecedor (`select_for_update`).
3. Se o fornecedor já tem rodada ativa, levanta `RodadaAtivaExistente` com a mensagem "Este fornecedor já tem uma rodada ativa.".
4. Cria a rodada em `interesse`.
5. Envia `rodada_aberta(rodada=...)` dentro da transação. Um receptor que falhe desfaz a abertura.
6. Grava a auditoria `rodada.abrir` com `{"rodada": <id>, "fornecedor": <id>}`.

**Primitiva de condições** (`travar_condicoes(fornecedor) -> Rodada`, em `apps/rodadas/condicoes.py`):

- Exige transação aberta. Fora de `transaction.atomic()`, levanta `TransactionManagementError`, que é o comportamento de `select_for_update`.
- Trava, nesta ordem, a linha do fornecedor e a linha da rodada ativa dele.
- Levanta `CondicoesCongeladas` quando:
  - não há rodada ativa (código interno `sem_rodada_ativa`);
  - a rodada ativa não está em `interesse` (código interno `fora_de_interesse`).
- Se não levantar, devolve a rodada travada.
- A mensagem de `CondicoesCongeladas` é sempre "As condições da rodada só podem ser alteradas na fase de interesse.".
- Toda alteração de mínimo, múltiplo, incremento ou estoque, nesta etapa e nas seguintes, chama `travar_condicoes` antes de ler o valor atual e de gravar.

**Sem rodada ativa:**

- A alteração de condição é recusada. É a leitura literal da especificação §4.1 e §4.4: "durante a fase de interesse da rodada ativa".
- Para mudar uma condição entre rodadas, o administrador abre a rodada seguinte, que nasce em interesse.
- O cadastro inicial (fornecedor na E03-01, produto na E03-03) não é alteração e não passa por esta regra.

**Ordem global de travas** (vale para a E03 e para as etapas que alteram estoque, parcelas ou etapa):

1. fornecedor;
2. rodada;
3. produto;
4. estoque da rodada;
5. parcelas de interesse, em ordem de `sequencia`.

Uma operação trava só o que usa, sempre nessa ordem. Isso evita impasse entre alterações de condição, reservas (E05) e transições de etapa (E06).

**Contrato para as transições** (registrado também na milestone E06):

- Toda mudança de etapa trava o fornecedor e a rodada, nessa ordem, antes de gravar a nova etapa.
- Assim, uma alteração de condição e uma mudança de etapa se serializam. A alteração que obtiver a trava depois de uma mudança para fora de `interesse` é recusada.

**Alteração do mínimo** (`alterar_minimo(autor, fornecedor, novo) -> Fornecedor`):

1. Exige o administrador.
2. Em `transaction.atomic()`, chama `travar_condicoes(fornecedor)`.
3. Valida `novo` com as regras do campo (E03-01).
4. Grava só `minimo` (`update_fields`).
5. Grava a auditoria `fornecedor.alterar_minimo` com `{"fornecedor": <id>, "anterior": "<valor>", "novo": "<valor>"}`, valores em texto decimal.
6. Valor igual ao atual: não grava nem audita.

**Telas:**

- **Detalhe do fornecedor:** mostra a rodada ativa (etapa e abertura) ou "Sem rodada ativa".
- **Abrir rodada:** `POST /administracao/fornecedores/<id>/rodadas/abrir/`, com o botão no detalhe, oferecido só sem rodada ativa. Redireciona para o detalhe com a mensagem de sucesso ou com a da recusa.
- **Mínimo:** `GET` e `POST /administracao/fornecedores/<id>/minimo/`.
  - O formulário aparece só com a rodada ativa em interesse.
  - O `POST` recusado por `CondicoesCongeladas` responde **409**, com a mensagem única, e nada é gravado.
  - O `GET` fora de interesse mostra a mensagem, sem formulário, com status 200.
- **Políticas:** todas as rotas usam `somente_administrador` (E02-03) e declaram política (E02-10).

## Interfaces

- `apps/rodadas/models.py`: `Etapa`, `ETAPAS_ATIVAS` e `Rodada`.
- `apps/rodadas/servicos.py`: `abrir_rodada` e `RodadaAtivaExistente`.
- `apps/rodadas/sinais.py`: `rodada_aberta`.
- `apps/rodadas/condicoes.py`: `travar_condicoes` e `CondicoesCongeladas` (com o atributo `codigo`).
- `apps/fornecedores/servicos.py`: `alterar_minimo`.
- Views, formulários e rotas acima.
- `tests/fabricas.py`: `RodadaFactory`, com parâmetro de etapa. Os testes das etapas posteriores a `interesse` criam a rodada já na etapa desejada pela fábrica, porque as transições ainda não existem.

## Invariantes

- No máximo uma rodada ativa por fornecedor, garantido pelo índice parcial.
- Nenhuma alteração de condição é gravada fora da fase de interesse da rodada ativa, inclusive pelo administrador e por chamada direta ao serviço.
- Toda alteração de condição passa por `travar_condicoes`.

## Casos-limite e concorrência

- **Fornecedor sem rodada:** alterar o mínimo é recusado (409); abrir rodada é aceito.
- **Rodada `disponivel_para_retirada` ou `cancelada`:** não conta como ativa, e uma nova rodada pode ser aberta.
- **Duas aberturas simultâneas para o mesmo fornecedor:** uma rodada criada e a outra recusada com `RodadaAtivaExistente`. A serialização vem da trava do fornecedor; o índice é a defesa final.
- **Alteração do mínimo concorrendo com uma mudança de etapa** que respeita o contrato acima: se a mudança confirmar primeiro, a alteração é recusada. O teste reproduz a mudança com uma thread que trava fornecedor e rodada, grava `fechamento` e só confirma depois de ver a outra conexão esperando por trava (`pg_stat_activity.wait_event_type = 'Lock'`).
- **Duas alterações do mínimo simultâneas:** as duas são gravadas em sequência, e o valor final é o da última a obter a trava. Há duas auditorias, cada uma com o `anterior` correto, o que prova a leitura sob trava.

## Correção E03-R01 — revisão da especificação em 2026-10-16

A regra comum está na seção de mesmo título da E03-01.

### Regra

- `alterar_minimo` aplica a regra de capacidade de dinheiro ao novo mínimo, depois da verificação da fase e antes de qualquer escrita (ordem fixada pela correção E03-R03 abaixo).
- Na recusa:
  - o mínimo anterior é mantido;
  - não há auditoria `fornecedor.alterar_minimo`;
  - a rota responde 200 com o erro no campo `minimo`.
- Em qualquer etapa fora de interesse, a resposta continua sendo 409 com `CondicoesCongeladas`, e o valor não é gravado. O teste da capacidade usa uma rodada em `interesse`.
- Ajuste E03-R03 (2026-10-16): a versão anterior deste item permitia validar o valor "antes de abrir a transação" e dizia que a ordem não mudava o resultado observável. Isso estava errado, porque a validação antes da fase faz um valor inválido responder 200 numa fase congelada. A ordem obrigatória está na correção E03-R03.

### Testes obrigatórios

- Critério A-19, com Red observado antes do código.

## Correção E03-R03 — revisão da especificação em 2026-10-16

Esta seção define a regra geral de precedência da fase. As seções de mesmo título nas E03-03, E03-05, E03-06 e E03-07 aplicam a regra às rotas de cada fatia.

### Diagnóstico

- `alterar_minimo` limpa o valor antes de `travar_condicoes`. Com a rodada em `fechamento`, `fechamento_encerrado`, `pagamento` ou `aguardando_fornecedor`, um mínimo acima da capacidade levanta `ValidationError`. A view trata isso como erro de validação comum e responde 200 com o formulário editável, quando o exigido é 409. O mínimo não é gravado, então o defeito é de contrato, não de integridade.
- O mesmo defeito existe, sem ter sido reproduzido pelo revisor, em mais quatro pontos:
  - `incluir_produto_na_rodada` e `alterar_estoque` (`apps/rodadas/estoque.py`) validam o limite antes de `travar_condicoes`;
  - as views de mínimo, múltiplo, incremento e estoque validam o formulário (`is_valid()`) antes de qualquer verificação da fase, então um texto mal formado (`abc`) numa fase congelada também responde 200.
- Minha falha na especificação: a correção E03-R01 desta fatia permitia validar "antes de abrir a transação" e dizia que a ordem não mudava o resultado observável.

### Regra

**A fase prevalece sobre o valor.** Numa rota ou serviço que altera condição da rodada, a ordem das recusas é:

1. permissão (`PermissionDenied`; a política da rota já cobre a view);
2. identidade dos objetos, sem relação com o valor digitado: id inexistente (404) e, na inclusão de estoque, produto de outro fornecedor (`ValidationError`, como hoje);
3. **fase:** fora da fase de interesse da rodada ativa, `CondicoesCongeladas`, com 409 na rota;
4. **valor:** formato, casas, sinal, mínimo, capacidade e, por último, compatibilidade (múltiplo, incremento, reservado).

Fora da fase de interesse, o valor enviado nunca é avaliado. A resposta é a mesma para um valor válido, mal formado, negativo, zero, acima da capacidade ou vazio.

**Rotas e serviços alcançados:**

| Condição | Serviço | Rota `POST` |
|---|---|---|
| mínimo | `alterar_minimo` | `/administracao/fornecedores/<id>/minimo/` |
| múltiplo | `alterar_multiplo` | `/administracao/produtos/<id>/multiplo/` |
| incremento | `alterar_incremento` | `/administracao/produtos/<id>/incremento/` |
| inclusão no estoque | `incluir_produto_na_rodada` | `/administracao/rodadas/<id>/estoque/incluir/` |
| alteração do estoque | `alterar_estoque` | `/administracao/estoque/<id>/alterar/` |

**Nos serviços:**

- A validação do valor acontece dentro de `transaction.atomic()`, depois de `travar_condicoes` e da conferência da rodada (inclusão e alteração de estoque). `alterar_multiplo` e `alterar_incremento` já seguem essa ordem e não mudam.
- Os helpers de limpeza (`_minimo`, `_limite`, `validar_*`) e as mensagens não mudam. Só muda o ponto em que são chamados.
- A trava continua sendo a autoridade: a fase é verificada com as linhas travadas, então uma mudança de etapa confirmada antes é sempre vista (contrato da E03-02).

**Nas views:**

- No `POST`, antes de validar o formulário, a view verifica a fase sem trava. Se não estiver em interesse, responde 409 com a mensagem única `MENSAGEM` e sem formulário editável, pelo mesmo template e caminho que já usa para `CondicoesCongeladas`.
- Uma função de leitura nova em `apps/rodadas/condicoes.py`, sem trava, faz essa verificação:
  - `condicoes_editaveis(fornecedor) -> bool`: `True` se e somente se o fornecedor tem rodada em `interesse`. Serve para mínimo, múltiplo e incremento.
  - para o estoque, a verificação é sobre a rodada da rota: `rodada.etapa == Etapa.INTERESSE`. Uma rodada em interesse é sempre a ativa do fornecedor, pelo índice único da E03-02.
- Essa leitura sem trava só serve para escolher a resposta quando nada será gravado. Se ela disser "editável", o serviço ainda trava e verifica de novo. Uma mudança de etapa que confirme entre as duas leituras é recusada pelo serviço, com 409.
- O `GET` não muda.
- O 409 vale também com o cabeçalho `HX-Request: true`, como na matriz da E03-07.

**Na fase de interesse,** tudo continua como antes: erro de valor responde 200, com a mensagem no campo e o valor digitado de volta (E03-01, correção E03-R01).

### Testes obrigatórios

- Os probes complementares do revisor (`docs/specs/E03-08/review.md`, seção "Probes complementares reproduzíveis", revalidação de `2e7bbcc`) entram literais na suíte:
  - `test_minimo_excedente_fora_de_interesse_responde_409` em `tests/tecnicos/test_condicoes_congeladas_matriz.py`;
  - `test_estoque_preserva_entrada_rejeitada` em `tests/tecnicos/test_rodadas_estoque.py` (correção E03-R04 da E03-05).
- Critérios A-20 e A-21 desta fatia e A-12 e A-13 da E03-07, com Red observado antes do código.

### O que não fazer

- Não remover nem afrouxar a validação de capacidade ou de formato para fazer os testes passarem.
- Não decidir a fase só pela leitura sem trava: o serviço continua travando e verificando.
- Não avaliar o valor antes da fase em nenhum dos cinco serviços.
- Não criar uma mensagem nova para a fase congelada: é `MENSAGEM`, a mesma de `CondicoesCongeladas`.
- Não mudar o tratamento dos campos não congelados (nome, e-mail, prazo, frete e preço), que não dependem de fase.

## Dependências e decisões em aberto

- Depende de E03-01.
- Sem decisões em aberto.
