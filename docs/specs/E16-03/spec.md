# E16-03 — Observabilidade: Sentry sem dados pessoais e monitor externo das tarefas

Fatia 3 de 8 da milestone **E16 — Homologação e encerramento da fase 1**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

A infraestrutura 2 prevê o Sentry, sem envio de dados pessoais, e um monitor de disponibilidade. A E15 deixou um herdado para a E16: os alertas operacionais dependem do worker. A verificação `verificar_operacao` é uma tarefa do Procrastinate, então, com o worker parado por inteiro, só o painel mostra o atraso.

Esta fatia:
- liga o Sentry em homologação e produção, com os dados pessoais removidos antes do envio;
- faz `verificar_operacao` e o backup diário (E16-04) mandarem check-ins ao monitor de cron do Sentry. Quando o check-in não chega, o Sentry avisa, mesmo com o worker e a aplicação inteiros fora do ar;
- deixa pronto o endereço que o monitor de disponibilidade consulta (`/saude/`, da E16-01).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 2 | Observabilidade: Sentry (sem envio de dados pessoais) e Better Stack (monitor de disponibilidade), mais os alertas da seção 3.6. |
| Infraestrutura 5 | Nenhum dado pessoal em logs nem no Sentry; minimizar o que é enviado para fora do país. |
| Especificação §15, Operação | Logs e alertas para tarefas atrasadas; segredos fora dos logs. |
| Milestone 16, herdado da E15 | Configurar um monitor externo independente do worker (por exemplo, o monitor de cron do Sentry) que avise quando `verificar_operacao` deixar de concluir. |
| E15-01 | `execucao_monitorada(nome)`: grava conclusão e falha de cada tarefa do catálogo e repassa a exceção. |

## Escopo

**Dentro:**
- a inicialização do Sentry;
- o filtro de dados pessoais;
- os check-ins de cron;
- as variáveis de ambiente.

**Fora:**
- a criação do projeto no Sentry, do monitor no Better Stack e das regras de aviso por e-mail (E16-08);
- rastreamento de desempenho (traces) e replay.

## Regras

### Inicialização

1. **Quando inicializa:** o Sentry é inicializado em `prod.py` com `SENTRY_DSN`, obrigatório em homologação e produção. Em `dev.py` e `test.py`, ele só é inicializado se `SENTRY_DSN` estiver definido. Sem DSN, nada é enviado e nenhuma chamada da regra 6 falha.
2. **Opções:**
   - `environment` = `AMBIENTE`;
   - `release` = `VERSAO_DA_APLICACAO`, quando definida (o Fly.io pode fornecer a referência da imagem);
   - `send_default_pii = False`;
   - `include_local_variables = False`;
   - `max_request_body_size = "never"`;
   - `traces_sample_rate = 0`;
   - integração com Django e com o `logging`: eventos a partir de `ERROR` e breadcrumbs a partir de `INFO`.
3. **Filtro de dados pessoais (`antes_de_enviar`, ligado a `before_send`):** em todo evento, antes do envio:
   - **requisição:** sobram só o método e o caminho da URL. Saem a query string, o corpo, os cookies e os cabeçalhos, exceto `User-Agent`. Sai também o endereço IP;
   - **usuário:** sobra só `id`. Saem e-mail, nome, nome de usuário e IP;
   - **mensagens:** endereços de e-mail e números de telefone que aparecem no texto da mensagem, da exceção ou do log são trocados por `[removido]`;
   - **contextos extras e tags:** valores com chave parecida com `senha`, `password`, `token`, `secret`, `segredo`, `chave`, `key`, `authorization`, `cookie`, `email` ou `whatsapp` são trocados por `[removido]`.

   Se o filtro levantar exceção, o evento é descartado: nunca é enviado sem filtro.
4. **Breadcrumbs (`antes_do_breadcrumb`, ligado a `before_breadcrumb`):**
   - os de consulta SQL são descartados (os parâmetros podem ter dados pessoais);
   - nos de requisição HTTP de saída, a URL perde a query string;
   - os demais passam pelo mesmo filtro de texto da regra 3, pela troca de tokens da regra 3-A e, no campo `data`, pelo filtro de chaves das regras 3 e 3-B (correção E16-R02).
3-A. **Credenciais no caminho** (correção E16-R02, revisão de 2026-11-17).
   - **Quais rotas:** as rotas com credencial de uso único no caminho são `entrar/link/<token>/`, `convite/<token>/` e `convite/<token>/google/`.
   - **A troca:** em qualquer texto do evento, o segmento do token é trocado por `[removido]` antes do envio. O resto do caminho é mantido: `/convite/[removido]/google/`.
   - **Onde vale:** `request.url`, `transaction`, mensagens, `logentry` (mensagem e parâmetros), valores e textos das exceções, breadcrumbs (mensagem e `data`), `extra`, `tags` e `contexts`. A troca vale para qualquer evento, venha ele da integração com o Django, do `logging` ou de `capture_event`.
   - **Uma constante só:** os padrões ficam em `ROTAS_COM_SEGREDO`, ao lado do filtro. O segmento é qualquer sequência sem `/`, `?`, `#` ou espaço.
   - **Nome da transação:** a integração com o Django usa `transaction_style="url"`, para que o nome da transação seja o padrão da rota (`/convite/{token}/`) e não o caminho concreto.
   - **Rota nova coberta:** um teste percorre o resolvedor de URLs do projeto. Toda rota com parâmetro cujo nome contém `token` precisa estar coberta por `ROTAS_COM_SEGREDO`, para que uma rota nova com token não fique esquecida.
3-B. **Nomes e identificação pessoal por chave** (correção E16-R02).
   - **Chaves cobertas:** além das chaves da regra 3, são trocados por `[removido]` os valores cuja chave tenha um segmento exatamente igual a `nome`, `name`, `username`, `usuario`, `telefone`, `phone`, `celular`, `cpf`, `endereco`, `address` ou `ip`. A chave vai para minúsculas e é dividida por `_`, `-` e `.`; assim, `first_name`, `nome_completo` e `telefone_do_comprador` são cobertas, e `pedido` e `id_externo` não são.
   - **Onde vale:** em `extra`, `tags`, `contexts` e no `data` dos breadcrumbs.
   - **Exceção:** os contextos técnicos do SDK `runtime`, `os` e `trace` ficam de fora, porque o nome do interpretador e do sistema não identificam ninguém.
   - **O que não muda:** `user` continua só com `id` (regra 3), e só o cabeçalho `User-Agent` é mantido. `Referer`, `X-Forwarded-For`, `Authorization` e `Cookie` saem.
3-C. **Prova no envelope:** os critérios desta correção conferem o texto serializado do envelope inteiro, com todos os itens, e não só o dicionário do evento.

5. **Ambiente de teste:** nenhum teste da suíte envia eventos para fora. Os testes usam um transporte em memória.

### Monitor de cron (herdado da E15)

6. **Tarefas monitoradas por fora:** a constante `MONITORES_EXTERNOS` associa nome da tarefa à configuração do monitor no Sentry:

   | Tarefa | `schedule` (crontab, UTC) | `checkin_margin` | `max_runtime` |
   |---|---|---|---|
   | `verificar_operacao` | `*/5 * * * *` | 10 min | 5 min |
   | `backup_diario` (E16-04) | `0 6 * * *` | 120 min | 60 min |

   O slug do monitor é o nome da tarefa com `_` trocado por `-` (`verificar-operacao`, `backup-diario`).
7. **Check-ins:** `execucao_monitorada(nome)` (E15-01), quando `nome` está em `MONITORES_EXTERNOS`, envia:
   - um check-in `in_progress` ao começar;
   - `ok` ao concluir;
   - `error` quando o corpo levanta exceção, que continua sendo repassada como hoje.

   Os check-ins levam `monitor_config` (com `timezone = "UTC"`), para que o Sentry crie ou atualize o monitor sem cadastro manual.
8. **Falha do monitor não afeta a tarefa:** erro no envio de um check-in (rede, SDK) é registrado no log com a classe do erro e não muda o resultado da tarefa nem o registro de `ExecucaoDaTarefa`.
9. **Catálogo:** as tarefas fora de `MONITORES_EXTERNOS` não mandam check-in. Os alertas internos da E15 continuam valendo para todas.

### Monitor de disponibilidade

10. O monitor do Better Stack consulta `GET https://<app>.fly.dev/saude/` (E16-01) a cada 3 minutos e avisa o responsável por e-mail quando a resposta não é 200. A configuração é feita na E16-08 e registrada em `docs/operacao/homologacao.md`. Esta fatia não tem código para isso: o critério dela é a rota da E16-01.

## Decisões técnicas

- **`sentry-sdk`.** É o cliente oficial, já previsto na infraestrutura 2. O monitor de cron do próprio Sentry atende ao herdado da E15 sem outro serviço: o check-in que deixa de chegar é detectado pelo Sentry, fora do Fly.io. Dependência nova, com necessidade demonstrada.
- **Só duas tarefas por fora.** O monitor externo existe para o caso que os alertas internos não cobrem: o worker inteiro parado. Se a verificação operacional conclui, ela já acusa o atraso das outras tarefas (E15-02). O backup entra porque roda uma vez por dia e é a garantia de recuperação. Mais monitores custariam cota sem ganho de detecção.
- **Margem de 10 minutos para a verificação.** Somada ao intervalo de 5 minutos, dá cerca de 15 minutos, a mesma tolerância da E15-01.
- **Descartar o evento quando o filtro falha.** Perder um evento é melhor do que mandar um dado pessoal para fora do país (infraestrutura 5).

## Invariantes

- Nenhum e-mail, telefone, nome, cookie, token (inclusive o de convite ou de link no caminho da URL), corpo de requisição ou parâmetro SQL sai para o Sentry.
- O resultado das tarefas e o registro da E15-01 não dependem do Sentry.

## Dependências e decisões em aberto

- Depende da E16-01 (`prod.py`), da E15-01 (`execucao_monitorada`) e, para `backup_diario`, da E16-04. A linha do backup entra em `MONITORES_EXTERNOS` junto com a tarefa.
- Nova dependência: `sentry-sdk`.
- Nenhuma decisão em aberto. A M-13 deixa de ser melhoria e passa a ser o achado E16-R02, corrigido pelas regras 3-A a 3-C. Na correção, o implementador registra o encerramento na seção "Reclassificação pelo revisor" de `docs/melhorias.md`, com o commit.
