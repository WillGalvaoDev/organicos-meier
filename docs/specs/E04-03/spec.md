# E04-03 — Envio por e-mail, tentativas e retentativa

Fatia 3 de 7 da milestone **E04 — Notificações e comunicados**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A fila da E04-02 guarda envios pendentes. Esta fatia entrega:

- o processamento da fila;
- o canal de e-mail;
- o registro de cada tentativa;
- a retentativa limitada;
- a tarefa periódica no Procrastinate, que já é dependência do projeto e entra agora em `INSTALLED_APPS`, como previsto no `README`.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §12, Requisitos derivados | Registrar envio e falhas; retentativa sem duplicação indevida; falha de mensagem não altera o estado financeiro. |
| Especificação §15, Operação | Logs e alertas para falhas de comunicação. |
| Infraestrutura 2 | Amazon SES para e-mail. Procrastinate (fila no Postgres) para tarefas periódicas, retomáveis e com travas no banco. |
| Infraestrutura 4.14 | Padrão de referência do projeto: no máximo três tentativas no total, com intervalos crescentes definidos na implementação. Cada tentativa registra número, horário, resultado e resposta. |
| Infraestrutura 9.2, L-13 | A aceitação da mensagem pelo SES não garante entrega. Falhas posteriores (bounce) não são detectadas sem integração adicional, que não foi incluída. |
| Infraestrutura 9.2 | Saída do sandbox do SES ainda a validar. |
| Infraestrutura 5 | Nenhum dado pessoal em logs. Histórico só de inserção. |
| README | Procrastinate instalado, entra em `INSTALLED_APPS` com a fatia que o usa, com testes antes. |

## Escopo

**Dentro:**

- Modelo `TentativaDeEnvio`, só de inserção.
- Canal de e-mail, `enviar_email`, sobre a API de e-mail do Django.
- Função `processar_envios`.
- Tarefa periódica do Procrastinate e o comando do *worker*.
- Configuração de SMTP lida do ambiente em produção, sem validar o SES.

**Fora:**

- O canal de WhatsApp (E04-04), que usa o mesmo processamento.
- A consulta administrativa dos envios (E04-07).
- Alertas consolidados e painel (E15).
- O ciclo de tentativas do pedido formal (E13), que tem regras próprias (infraestrutura 4.14) e só reaproveita `enviar_email`.
- Detecção de *bounce* do SES (L-13, fora do escopo aprovado).

## Decisões técnicas

- **Três tentativas no total,** com intervalos de 1 minuto depois da primeira falha e de 10 minutos depois da segunda. É o mesmo limite que a infraestrutura 4.14 fixou para o pedido formal; a especificação não fixa número para as notificações. Depois da terceira falha, o envio fica `falhou`, sem nova tentativa automática.
- **"Enviado" significa aceito pelo serviço de e-mail,** e não entregue (L-13). A interface usa "Aceito pelo serviço de e-mail".
- **Toda exceção do canal conta como falha,** sem distinguir falha temporária de definitiva. A API de e-mail do Django não oferece essa distinção de forma confiável, e o limite de três tentativas resolve os dois casos.
- **Pelo menos uma vez:** o envio é feito com a linha do `Envio` travada, e o resultado é gravado na mesma transação. Se o processo cair depois de o serviço aceitar a mensagem e antes da confirmação no banco, a tentativa é desfeita e o envio é repetido depois. Isso pode duplicar um e-mail num caso raro, e é uma limitação aceita: o SMTP não oferece chave de idempotência. Uma mensagem nunca deixa de ser tentada por causa de uma queda. A limitação fica registrada no `review.md`.
- **Sem dependência nova:** o SES tem interface SMTP, e o `EmailBackend` SMTP do Django basta. A escolha da biblioteca do SES e a saída do sandbox ficam para a homologação. Esta fatia não considera o SES validado.

## Regras

**Modelo `TentativaDeEnvio`** (`RegistroSoInsercao`, com a trigger da E01-04):

| Campo | Regra |
|---|---|
| `envio` | FK `PROTECT` |
| `numero` | 1, 2 ou 3; `UNIQUE (envio, numero)` |
| `iniciada_em` | `agora()` antes da chamada ao canal |
| `concluida_em` | `agora()` depois da chamada |
| `resultado` | `sucesso` ou `falha` |
| `erro` | vazio no sucesso. Na falha, só o nome da classe da exceção (por exemplo, `SMTPServerDisconnected`), com até 100 caracteres. Nunca a mensagem da exceção, que pode conter endereço ou conteúdo |

**Canal de e-mail** (`apps/notificacoes/canais.py`): `enviar_email(destino, assunto, corpo) -> None`.

- Envia com `EmailMessage(assunto, corpo, to=[destino]).send(fail_silently=False)`, pelo `EMAIL_BACKEND` configurado.
- Não captura exceções: quem chama decide.
- É a mesma função que a E13 usará para o pedido formal.

**Processamento** (`apps/notificacoes/processamento.py`): `processar_envios(*, limite=100) -> int`.

1. Repete até processar `limite` envios ou não restar envio elegível. Elegível é um envio `pendente` com `proxima_tentativa_em <= agora()`.
2. Cada envio é processado na sua própria `transaction.atomic()`:
   1. seleciona um envio elegível por `proxima_tentativa_em` e depois `id`, com `select_for_update(skip_locked=True)`. Um envio travado por outro processador é pulado;
   2. com `numero = tentativas + 1`, chama o canal do envio (`enviar_email` para `email`; `whatsapp` na E04-04);
   3. grava a `TentativaDeEnvio` e atualiza o envio:

      | Resultado | Atualização |
      |---|---|
      | sucesso | `situacao=enviado`, `tentativas=numero`, `concluido_em=agora()` |
      | falha, com `numero < 3` | `tentativas=numero`, `proxima_tentativa_em = agora() + intervalo[numero]` (1: 1 minuto; 2: 10 minutos) |
      | falha, com `numero = 3` | `situacao=falhou`, `tentativas=3`, `concluido_em=agora()` |

3. Uma exceção do canal nunca sai de `processar_envios`. Ela é registrada como falha, e o processamento segue para o próximo envio.
4. Devolve o número de tentativas feitas. O `limite` conta os envios retirados da fila, inclusive os cancelados sem tentativa (E04-04).
5. **Log:** na falha, um `logger.warning` com o id do envio, o número da tentativa e a classe do erro, sem destino nem conteúdo. Depois da terceira falha, um `logger.error` com os mesmos dados. É o gancho para os alertas da E15.

**Tarefa periódica** (`apps/notificacoes/tarefas.py`):

- `procrastinate.contrib.django` entra em `INSTALLED_APPS`, com as migrações da biblioteca.
- Uma tarefa `processar_envios_pendentes` chama `processar_envios()`. É periódica, a cada minuto (`cron "* * * * *"`), e usa `queueing_lock` para não empilhar execuções.
- O `README` passa a explicar como subir o *worker* localmente (`uv run python manage.py procrastinate worker`), ao lado do servidor de desenvolvimento. O `compose.yaml` não muda: hoje ele só tem o Postgres, e a aplicação roda fora dele.
- Os testes chamam `processar_envios` diretamente. Só um teste confere o registro da tarefa periódica e que ela chama `processar_envios`, sem subir *worker*.

**Configuração:**

- `base.py`: `EMAIL_TIMEOUT = 10` segundos, para que um servidor parado não segure a trava do envio indefinidamente.
- `prod.py`:
  - continua exigindo `EMAIL_BACKEND` e `DEFAULT_FROM_EMAIL` (E02-02);
  - passa a ler do ambiente as variáveis abaixo, com os segredos em `fly secrets` (infraestrutura 2):

    | Variável | Padrão |
    |---|---|
    | `EMAIL_HOST` | `localhost` |
    | `EMAIL_PORT` | `587` |
    | `EMAIL_USE_TLS` | `True` |
    | `EMAIL_HOST_USER` | texto vazio |
    | `EMAIL_HOST_PASSWORD` | texto vazio |

    Com usuário e senha vazios, o envio SMTP falha e entra no fluxo de tentativas, sem impedir o carregamento das configurações;
  - nenhuma credencial vai para o código, os logs ou o `README`.

## Interfaces

- `apps/notificacoes/models.py`: `TentativaDeEnvio`.
- `apps/notificacoes/canais.py`: `enviar_email`.
- `apps/notificacoes/processamento.py`: `processar_envios`, `MAXIMO_DE_TENTATIVAS = 3` e `INTERVALOS`.
- `apps/notificacoes/tarefas.py`: a tarefa periódica.
- `tests/apoio/email_falho.py`, ao lado do `BackendQueFalha` existente, ganha dois backends de e-mail para os testes:
  - `BackendComFalhas`: falha as N primeiras chamadas (N configurado pelo teste) e depois aceita, guardando as mensagens aceitas como o `locmem`;
  - `BackendQueFalhaPara`: falha só para os destinos configurados pelo teste e aceita os demais.

## Invariantes

- Nenhum envio tem mais de três tentativas.
- Cada tentativa gravada corresponde a exatamente uma chamada ao canal.
- Um envio concluído nunca volta a ser tentado.
- O processamento nunca altera notificação, pedido, pagamento nem qualquer dado fora de `Envio` e `TentativaDeEnvio`.

## Casos-limite e concorrência

- **Duas falhas e depois sucesso:** três tentativas registradas (falha, falha, sucesso), e `enviado`.
- **Três falhas:** `falhou`, e uma quarta chamada a `processar_envios`, mesmo muito depois, não tenta de novo.
- **Envio agendado para o futuro:** só é tentado quando `agora() >= proxima_tentativa_em`. O teste avança o relógio com `time_machine` para 59 s, 60 s e 61 s depois da falha.
- **Dois processadores simultâneos:** um envio é tentado uma única vez. O teste prova com uma thread que trava a linha do envio enquanto `processar_envios` roda em outra: a outra pula o envio travado e processa os demais.
- **Falha num envio não impede os seguintes:** com três envios, o primeiro falhando, os outros dois são enviados na mesma chamada.
- **`limite`:** com 5 elegíveis e `limite=2`, duas tentativas; os outros continuam pendentes.
- **Falha não afeta o fato:** uma notificação de `estorno` com o e-mail falhando três vezes continua visível na central, e a notificação não muda.

## Dependências e decisões em aberto

- Depende de E04-02.
- Sem decisões em aberto. A validação do SES (sandbox, L-13) continua pendente e não é considerada resolvida.
