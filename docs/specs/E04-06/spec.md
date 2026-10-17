# E04-06 — Comunicados do administrador

Fatia 6 de 7 da milestone **E04 — Notificações e comunicados**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O administrador é o único responsável pelos comunicados. Um comunicado administrativo é uma mensagem para todos os usuários compradores, pelos canais aplicáveis. O comprador consulta os comunicados no site.

Esta fatia entrega:

- a publicação, sem duplicidade;
- a distribuição pelos canais da matriz (E04-01);
- o histórico do administrador;
- a página de comunicados do comprador.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Administrador: único responsável por comunicados. |
| Especificação §12, Eventos | Comunicado administrativo: mensagem para todos os usuários compradores pelos canais aplicáveis. |
| Especificação §12, Requisitos derivados | Registrar envio e falhas; retentativa sem duplicação indevida. |
| Especificação §13 | Comprador: notificações, regras, endereço e comunicados. Administrador: comunicados gerais e histórico de ações relevantes. |
| Especificação §14 | Notificação e comunicado: destinatários, canais, conteúdo e resultado de entrega. Auditoria: autor, ação, momento. |
| Infraestrutura 5 | Auditoria só de inserção. `UNIQUE` em chaves de idempotência. |
| E04-01, E04-02 | Evento `comunicado` (site, e-mail e WhatsApp); `emitir_evento_para_varios`. |

## Escopo

**Dentro:**

- Modelo `Comunicado`.
- Serviço `publicar_comunicado`.
- Tela administrativa de publicação e histórico.
- Página `/comunicados/` do comprador.

**Fora:**

- Edição, remoção ou agendamento de comunicados: os documentos não preveem.
- Comunicados para contas de fornecedor: a §12 fala só em compradores.
- Regras de funcionamento e endereço de retirada (E14), que a §13 lista ao lado dos comunicados.
- Os avisos de cada etapa, que são eventos próprios da matriz.

## Decisões técnicas

**Quem são "todos os usuários compradores":**

- **Entram:** as contas com papel comprador e situação `ativa` ou `suspensa`, no momento da publicação. A conta suspensa continua sendo usuária: ela entra no site, consulta listas e pedidos pagos (§2) e pode ter retirada ou estorno pendente, que um comunicado pode afetar.
- **Ficam fora:** as contas `removida`. A remoção bloqueia o acesso de forma definitiva e bane o e-mail (§2), e um aviso a quem não pode mais entrar seria uma mensagem desnecessária (§12).

**Destinatários fixados na publicação:**

- Quem se cadastrar depois não recebe notificação nem e-mail do comunicado antigo.
- A página `/comunicados/` mostra todos os comunicados publicados a qualquer comprador que acesse, porque o comunicado é uma informação geral.

**Comunicado imutável:** um comunicado publicado não muda nem é apagado. É o registro do que foi dito, e o conteúdo é o mesmo das notificações e dos envios. Uma correção é um comunicado novo.

**Sem duplicidade por duplo clique:** o formulário leva um token de requisição único (`uuid4`), gravado com `UNIQUE`, no mesmo padrão do reenvio do pedido formal (infraestrutura 4.14). Uma requisição repetida com o mesmo token não publica de novo.

## Regras

**Modelo `Comunicado`** (`RegistroSoInsercao`, com trigger):

| Campo | Regra |
|---|---|
| `titulo` | de 1 a 150 caracteres, espaços das pontas removidos |
| `mensagem` | de 1 a 2000 caracteres, espaços das pontas removidos; quebras de linha preservadas |
| `autor` | FK `PROTECT` para a conta do administrador |
| `publicado_em` | `agora()` |
| `token` | `UUIDField`, `UNIQUE` |
| `destinatarios` | inteiro: o número de contas que receberam a notificação |

O limite da mensagem é o mesmo do `corpo` da notificação (E04-01), porque a mensagem é o corpo da notificação.

**Publicação** (`publicar_comunicado(autor, *, titulo, mensagem, token) -> tuple[Comunicado, bool]`):

1. Exige o administrador; caso contrário, `PermissionDenied`.
2. Valida título e mensagem; um erro levanta `ValidationError` por campo.
3. Em `transaction.atomic()`:
   1. se já existe comunicado com o `token`, devolve `(existente, False)` sem gravar nada. Com conteúdo diferente, a resposta é a mesma: o token identifica o pedido, e não o texto;
   2. seleciona os compradores `ativa` e `suspensa`, em ordem de `pk`, e conta-os;
   3. grava o comunicado já com `destinatarios` igual a essa contagem. Como o comunicado é só de inserção, o número é conhecido antes do `INSERT`. A corrida entre duas requisições com o mesmo token é resolvida pelo `UNIQUE`: a segunda espera a primeira e recebe o existente, sem emitir nada;
   4. chama `emitir_evento_para_varios(Evento.COMUNICADO, contas, titulo=titulo, corpo=mensagem, link="/comunicados/", chave_base=f"comunicado:{id}")`. O retorno precisa ser igual a `destinatarios`; se não for, levanta `RuntimeError` e a transação inteira é desfeita, porque isso só aconteceria por defeito;
   5. grava a auditoria `comunicado.publicar` com `{"comunicado": <id>, "destinatarios": <n>}`, sem título nem mensagem.
4. Devolve `(comunicado, True)`.
5. A distribuição por e-mail e WhatsApp segue a fila (E04-03, E04-04). Uma falha de canal externo não desfaz a publicação.

**Tela administrativa** (`/administracao/comunicados/`, `somente_administrador`):

- **`GET`:**
  - formulário com título e mensagem e um campo oculto `token` com um `uuid4` novo;
  - abaixo, o histórico, do mais recente para o mais antigo, 30 por página: data e hora no fuso da operação, título, autor e número de destinatários;
  - para cada comunicado, a contagem dos envios por situação e canal (por exemplo, "e-mail: 98 aceitos, 2 com falha"), lida de `Envio` pela chave `comunicado:<id>:%`;
  - a lista não pode cair em N+1 (ver o critério A-12).
- **`POST`:**
  - válido: redireciona para a mesma tela, com a mensagem "Comunicado publicado para <n> compradores.";
  - token repetido: redireciona com a mensagem "Este comunicado já tinha sido publicado.", sem publicar de novo;
  - inválido: 200 com os erros por campo e os valores digitados.
- **Antes de enviar:** a tela mostra o número de compradores que vão receber ("Será enviado para <n> compradores."), calculado no `GET`.

**Página do comprador** (`/comunicados/`, política `comprador`, que inclui o suspenso):

- Todos os comunicados, do mais recente para o mais antigo, 30 por página.
- Cada um com título, data e hora, mensagem com escape automático e quebras de linha, e a âncora `id="c<id>"`.
- Sem o autor e sem o número de destinatários.
- Sem comunicados: "Nenhum comunicado publicado.".
- Fornecedor e administrador: 403. Anônimo: redirecionamento para `/entrar/`.
- `/inicio/` do comprador ganha o link "Comunicados".

## Interfaces

- `apps/notificacoes/models.py`: `Comunicado`.
- `apps/notificacoes/comunicados.py`: `publicar_comunicado`.
- Views, formulário, templates e rotas, com política declarada.

## Invariantes

- Um token gera no máximo um comunicado.
- Cada comprador ativo ou suspenso na publicação recebe exatamente uma notificação do comunicado. Nenhuma conta removida, de fornecedor ou de administrador recebe.
- Um comunicado nunca muda nem é apagado.

## Casos-limite e concorrência

- **Sem nenhum comprador:** o comunicado é publicado com `destinatarios = 0` e aparece na página.
- **Duas publicações simultâneas com o mesmo token:** um comunicado e uma distribuição. A segunda recebe `(existente, False)`.
- **Duas publicações com tokens diferentes e o mesmo texto:** dois comunicados. É a decisão do administrador, e não duplicidade técnica.
- **Comprador suspenso depois da publicação:** continua com a notificação recebida.
- **Mensagem com HTML:** exibida escapada no site; no e-mail, vai em texto simples (E04-02).
- **Compradores com e sem consentimento de WhatsApp:** só os com consentimento recebem envio de WhatsApp (E04-04).

## Dependências e decisões em aberto

- Depende de E02-03, E02-08, E04-02, E04-03 e E04-04.
- Sem decisões em aberto. A inclusão das contas suspensas e a exclusão das removidas são decisões técnicas derivadas da §2 e podem ser revistas pelo responsável.
