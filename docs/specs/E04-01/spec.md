# E04-01 — Catálogo de eventos e central de notificações no site

Fatia 1 de 7 da milestone **E04 — Notificações e comunicados**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O perfil do site é o canal de notificações que nunca depende de serviço externo. A especificação exige que o estado exibido no site continue correto mesmo quando um canal externo falha.

Esta fatia entrega:

- o catálogo dos eventos da §12, com os canais de cada um;
- o registro da notificação no site;
- a central em que cada conta lê e marca as próprias notificações;
- o contador de não lidas.

A emissão pelas etapas (E04-02) e os envios externos (E04-03 e E04-04) vêm depois.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Comprador consulta seu histórico e notificações. Restrições verificadas no servidor. |
| Especificação §12, Canais | Perfil do site: central de notificações do usuário. E-mail: avisos operacionais. WhatsApp: só com número e consentimento. |
| Especificação §12, Eventos | Tabela de eventos e conteúdo. "A distribuição exata de cada evento entre e-mail e WhatsApp deve ser configurada na especificação técnica para evitar mensagens desnecessárias. Lembretes adicionais não foram definidos como regra obrigatória." |
| Especificação §12, Requisitos derivados | O estado exibido no site continua correto mesmo se um canal externo falhar. |
| Especificação §11 | Liberação de retirada gera avisos por e-mail, perfil do site e WhatsApp para quem optou. |
| Especificação §5.1 | Mudança de preço: notificação no perfil do site. |
| Especificação §13 | Comprador: notificações e comunicados. |
| Especificação §14 | Notificação e comunicado: destinatários, canais, conteúdo e resultado de entrega. |
| Infraestrutura 5 | Auditoria e históricos só de inserção. Nenhum dado pessoal em logs. |
| E02-09 | Preferência de notificação por e-mail sempre ativa; WhatsApp só com consentimento registrado. |
| E02-10 | Política de acesso obrigatória por rota. |

## Escopo

**Dentro:**

- App `apps.notificacoes`, com `Evento`, `Canal` e `CANAIS_POR_EVENTO`.
- Modelo `Notificacao` e as triggers de proteção.
- Central `/notificacoes/`, marcação de lida e contador no cabeçalho.
- Fábrica `NotificacaoFactory` em `tests/fabricas.py`.

**Fora:**

- Emissão pelas etapas, idempotência e envios externos (E04-02 a E04-04).
- O conteúdo de cada evento. Ele é redigido pela etapa que emite o evento (E05 em diante), com os dados que só ela tem.
- Comunicados (E04-06).
- Alertas operacionais consolidados (E15).

## Decisões técnicas

**Matriz de canais** (a §12 delega esta definição à especificação técnica, e a infraestrutura v1.7 não a fixou):

| `Evento` | Origem na §12 | Destinatário | Site | E-mail | WhatsApp | Etapa que emite |
|---|---|---|---|---|---|---|
| `preco_alterado` | Alteração de preço de item no carrinho | comprador | sim | não | não | E05 |
| `fechamento_iniciado` | Início do fechamento | comprador | sim | sim | sim | E06 |
| `excedentes_removidos` | Remoção de excedentes de caixa | comprador | sim | sim | não | E06 |
| `pagamento_aberto` | Abertura do pagamento | comprador | sim | sim | sim | E08 |
| `pagamento_confirmado` | Pagamento confirmado | comprador | sim | sim | não | E08 |
| `itens_cancelados` | Cancelamento por inadimplência ou caixa incompleta | comprador | sim | sim | não | E11 |
| `retorno_para_interesse` | Retorno para interesse | comprador | sim | sim | não | E11 |
| `estorno` | Estorno | comprador | sim | sim | não | E10 |
| `previsao_de_entrega_alterada` | Alteração de previsão de entrega | comprador | sim | sim | não | E13 |
| `retirada_liberada` | Liberação de retirada | comprador | sim | sim | sim | E14 |
| `rodada_cancelada` | Cancelamento administrativo | comprador | sim | sim | sim | E12 |
| `comunicado` | Comunicado administrativo | comprador | sim | sim | sim | E04-06 |
| `falha_no_pedido_formal` | Falha no envio do pedido formal | administrador | sim | sim | não | E13 |

Critérios usados na matriz:

- **Site em todos os eventos:** é o único canal que não depende de serviço externo (§12).
- **E-mail em todos, menos o preço:**
  - a §12 chama o e-mail de canal dos avisos operacionais, e a E02-09 deixou a preferência de e-mail sempre ativa;
  - na mudança de preço, a §5.1 exige só o site, e o preço pode mudar várias vezes na mesma rodada. Mandar e-mail a cada mudança seria a "mensagem desnecessária" que a §12 manda evitar.
- **WhatsApp só nos eventos com prazo ou ação imediata,** e sempre condicionado ao número e ao consentimento:
  - a liberação de retirada, que a §11 exige expressamente;
  - o início do fechamento e a abertura do pagamento, ambos com janela de 24 horas;
  - o cancelamento administrativo;
  - o comunicado, que vai "pelos canais aplicáveis".

  A mensagem de WhatsApp tem custo por envio (infraestrutura 10), o que reforça a escolha.
- **Convite:** fica fora do catálogo de notificações, porque o destinatário ainda não tem conta. Ele vai só por e-mail e é registrado como e-mail de acesso (E04-05).
- **Pedido formal ao fornecedor:** também fica fora. É um e-mail para o endereço do pedido, com ciclo próprio de tentativas (infraestrutura 4.14, E13).
- **Lembretes:** nenhum evento de lembrete é criado (§12: "Lembretes adicionais não foram definidos como regra obrigatória").
- **A matriz é dado, não regra espalhada:** ela é um dicionário único, `CANAIS_POR_EVENTO`, e um teste a compara com a tabela acima. Mudar um canal exige mudar o dicionário e o teste, e nada mais.

**Notificação congelada:** título, corpo e link são gravados quando a notificação é criada. Uma mudança posterior de preço, etapa ou cadastro não altera notificações já emitidas (§14: "sem perda de histórico").

**Leitura explícita:** abrir a central não marca nada como lido. A conta marca cada notificação, ou todas de uma vez. Assim o contador nunca zera sem ação da pessoa.

## Regras

**Enumerações** (`apps/notificacoes/eventos.py`):

- `Evento` (`TextChoices`): os 13 valores da matriz, com rótulos em português ("Alteração de preço", "Início do fechamento" etc.).
- `Canal` (`TextChoices`): `site`, `email`, `whatsapp`.
- `CANAIS_POR_EVENTO: dict[Evento, frozenset[Canal]]`, exatamente como a matriz.
- `DESTINATARIO_POR_EVENTO: dict[Evento, Papel]`: `administrador` para `falha_no_pedido_formal` e `comprador` para os demais.

**Modelo `Notificacao`:**

| Campo | Regra |
|---|---|
| `conta` | FK para `Conta`, `PROTECT` |
| `evento` | `Evento` |
| `titulo` | de 1 a 150 caracteres |
| `corpo` | de 1 a 2000 caracteres |
| `link` | opcional: caminho relativo do site, como `/catalogo/3/`, com até 500 caracteres |
| `chave` | de 1 a 200 caracteres, `UNIQUE`; é a chave de idempotência (E04-02) |
| `criada_em` | `agora()` |
| `lida_em` | nulo até ser marcada |

- `CHECK` no banco para `evento` dentro dos valores, `titulo` e `corpo` não vazios, e `link` nulo ou começando por `/` sem começar por `//`.
- Índice em `(conta, lida_em, criada_em)` para a central e o contador.

**Proteção no banco** (triggers, padrão da E01-04):

- `DELETE` recusado.
- `UPDATE` recusado, exceto quando a única mudança é `lida_em` passando de nulo para um instante. Marcar de novo uma notificação já lida, desmarcar ou alterar qualquer outro campo é recusado.
- No ORM, a tentativa de salvar outros campos ou de apagar levanta `RegistroImutavel` (E01-04), antes de chegar ao banco.

**Criação interna:** `criar_notificacao(conta, evento, *, titulo, corpo, link=None, chave) -> Notificacao`, em `apps/notificacoes/servicos.py`, valida os campos e grava. As validações ficam numa função compartilhada, `validar_notificacao(conta, evento, *, titulo, corpo, link, chave)`, que a gravação em lote da E04-02 também usa. Assim nenhuma notificação é gravada sem as mesmas regras. As etapas nunca chamam `criar_notificacao` diretamente: usam `emitir_evento` ou `emitir_evento_para_varios` (E04-02). Validações:

- `evento` dentro de `Evento`;
- `titulo`, `corpo` e `chave` nos limites;
- `link` com a regra do `CHECK`;
- papel da `conta` igual a `DESTINATARIO_POR_EVENTO[evento]`.

Qualquer violação levanta `NotificacaoInvalida` com o nome do campo, sem gravar. Essas violações são erro de programação de quem emite, e não erro de formulário.

**Central** (`GET /notificacoes/`, política `autenticada` da E02-10):

- **Conteúdo:** só as notificações da conta da sessão, da mais recente para a mais antiga, 30 por página (`?pagina=<n>`). Uma página inexistente mostra a última.
- **Cada item:**
  - título, corpo (com quebras de linha preservadas e escape automático) e data e hora no fuso da operação (`no_fuso_da_operacao`, formato `dd/mm/aaaa HH:MM`);
  - o link, quando existir, como "Ver detalhes";
  - a marcação "Nova" quando não lida, e o botão "Marcar como lida".
- **Topo:** o botão "Marcar todas como lidas", quando houver alguma não lida.
- **Sem notificações:** "Você não tem notificações.".
- **Quem acessa:** comprador (ativo ou suspenso), fornecedor e administrador. Cada um vê só as suas.

**Marcar como lida** (`POST /notificacoes/<id>/lida/`, política `autenticada`):

- Notificação de outra conta, ou inexistente: 404, com o mesmo corpo nos dois casos. Nada muda.
- Já lida: não muda `lida_em` e redireciona do mesmo jeito (operação idempotente).
- Não lida: grava `lida_em = agora()` com `update_fields=["lida_em"]` e redireciona para `/notificacoes/`, preservando `?pagina=` quando enviado.
- `GET` responde 405.
- Com `HX-Request: true`, devolve só o fragmento do item atualizado, com status 200.

**Marcar todas** (`POST /notificacoes/lidas/`, política `autenticada`): um único `UPDATE` das notificações não lidas da conta, com `lida_em = agora()`. Redireciona para `/notificacoes/`.

**Contador** (processador de contexto em `apps/notificacoes/contexto.py`, registrado nas configurações):

- Para conta autenticada, `notificacoes_nao_lidas` é o número de não lidas, calculado com uma única consulta.
- Para anônimo, o processador não consulta o banco.
- `base.html` mostra, para conta autenticada, o link "Notificações" para `/notificacoes/` e, quando houver não lidas, o número entre parênteses: "Notificações (3)".

**Auditoria:** a leitura e a marcação não geram auditoria. São ações da própria conta sobre os próprios avisos, sem efeito comercial.

## Interfaces

- `apps/notificacoes/eventos.py`: `Evento`, `Canal`, `CANAIS_POR_EVENTO` e `DESTINATARIO_POR_EVENTO`.
- `apps/notificacoes/models.py`: `Notificacao`.
- `apps/notificacoes/servicos.py`: `criar_notificacao`, `validar_notificacao` e `NotificacaoInvalida`.
- `apps/notificacoes/contexto.py`: o processador de contexto.
- Views, templates (`notificacoes/central.html` e o fragmento do item) e rotas, com política declarada.
- Migrações com `CHECK`s e triggers.
- `tests/fabricas.py`: `NotificacaoFactory`.

## Invariantes

- Toda conta vê só as próprias notificações, inclusive por id direto.
- O conteúdo de uma notificação nunca muda depois de gravado. Só `lida_em` muda, uma única vez.
- Nenhuma notificação é apagada.
- O destinatário de cada evento tem o papel definido na matriz.

## Casos-limite e concorrência

- **Duas marcações simultâneas da mesma notificação:** as duas respondem com sucesso, e `lida_em` é o da primeira que confirmou. A segunda vê a notificação já lida e não grava, porque a gravação é condicional (`UPDATE ... WHERE lida_em IS NULL`).
- **"Marcar todas" concorrendo com uma notificação nova:** a nova pode ficar não lida. Isso é correto, porque ela não existia quando a ação foi pedida.
- **Link com `//exemplo.com` ou `https://...`:** recusado (`NotificacaoInvalida` e `CHECK`), para que nenhum aviso aponte para fora do site.
- **Corpo com HTML:** exibido escapado.
- **Conta suspensa:** continua vendo e marcando as próprias notificações (política `autenticada`).
- **Conta removida:** não acessa nada (E02-08). Suas notificações ficam gravadas.

## Dependências e decisões em aberto

- Depende de E01-03 (tempo), E01-04 (registros protegidos), E02-01 (contas) e E02-10 (políticas).
- Sem decisões em aberto. A matriz de canais é uma decisão técnica delegada pela §12 e pode ser ajustada pelo responsável sem mudança de código além do dicionário e do teste.
