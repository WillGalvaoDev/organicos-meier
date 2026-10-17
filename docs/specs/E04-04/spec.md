# E04-04 — Canal externo simulado (WhatsApp) e falha isolada

Fatia 4 de 7 da milestone **E04 — Notificações e comunicados**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O WhatsApp real é da fase 3 (infraestrutura 7). O cenário 24 ("Falha no WhatsApp não desfaz pagamento nem impede que a notificação e o estado correto apareçam no site") faz parte do critério de saída da fase 1, que roda contra simuladores.

Esta fatia entrega:

- o canal de WhatsApp atrás de uma interface substituível;
- a única implementação da fase 1: um simulador determinístico, que nunca fala com a Meta;
- as regras de número e consentimento;
- a prova de que a falha do canal externo fica isolada.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §3.2 | Recebimento por WhatsApp exige número cadastrado e aceitação opcional do usuário. |
| Especificação §12, Canais | WhatsApp: somente com número e consentimento de recebimento; não presumir SMS. |
| Especificação §12, Requisitos derivados | O estado exibido no site continua correto mesmo se um canal externo falhar. |
| Cenários §16 | 24. |
| Infraestrutura 2 | Meta WhatsApp Cloud API, templates *utility*, opt-in registrado. Fase 3. |
| Infraestrutura 7, fase 3 | Falha no WhatsApp nunca altera estado financeiro nem a notificação no site. |
| AGENTS.md §6, §7 | Integrações externas por interfaces substituíveis, com simulação determinística e tratamento explícito de falhas. Não implementar antecipadamente fases posteriores. |
| E02-09 | `telefone` em E.164 e `whatsapp_consentido_em`; `CHECK` de consentimento só com telefone. |
| E04-01 a E04-03 | Matriz de canais, emissão e processamento. |

## Escopo

**Dentro:**

- A interface `CanalWhatsApp` e as implementações `CanalWhatsAppDesligado` e `CanalWhatsAppSimulado`.
- A configuração `CANAL_WHATSAPP` e a recusa de iniciar em produção com o simulador.
- A criação dos envios de WhatsApp na emissão e a nova verificação de consentimento no envio.
- A prova do cenário 24, com um fato de teste no lugar do pagamento.

**Fora:**

- A integração real com a Meta, os templates e a conta comercial (fase 3).
- SMS (a §12 manda não presumir).
- O cenário 24 com pagamento real do simulador de pagamentos. Ele fica herdado pela E08, que confirma pagamentos e emite `pagamento_confirmado`.

## Decisões técnicas

- **Desligado por padrão:**
  - `CANAL_WHATSAPP` vale `desligado` em `base.py` e `prod.py`, e `simulado` em `dev.py` e `test.py`;
  - não existe valor para o canal real nesta fase. Ele chega na fase 3, com especificação própria.
- **Produção recusa o simulador,** pelo mesmo princípio do simulador de pagamentos (A3, cenário 38): mensagens simuladas em produção dariam a falsa impressão de que o aviso saiu.
  - Se `prod.py` receber `CANAL_WHATSAPP=simulado` do ambiente, o carregamento das configurações levanta `ImproperlyConfigured`.
  - Qualquer valor fora de `desligado` e `simulado` também levanta, em qualquer ambiente.
- **Com o canal desligado,** nenhum envio de WhatsApp é criado. Não fica uma fila de mensagens que nunca vai sair.
- **O conteúdo da mensagem simulada** é `titulo + " " + ORIGEM_PUBLICA + link`, ou só o título quando não há link. Os templates *utility* reais são da fase 3.

## Regras

**Interface** (`apps/notificacoes/whatsapp.py`):

- `class CanalWhatsApp(Protocol)`, com o método `enviar(numero_e164: str, texto: str) -> None`. A falha levanta `FalhaNoCanalExterno`.
- `obter_canal_whatsapp() -> CanalWhatsApp`: devolve a implementação conforme `CANAL_WHATSAPP`. O processamento e a emissão nunca importam uma implementação diretamente.

**`CanalWhatsAppDesligado`:**

- `enviar` levanta `FalhaNoCanalExterno("canal desligado")`.
- Na prática não é chamado, porque nenhum envio é criado com o canal desligado.

**`CanalWhatsAppSimulado`:**

- Mantém, no processo, uma lista das mensagens aceitas (`numero`, `texto`, `instante`) e um plano de falhas configurável pelos testes:
  - `falhar_sempre()`;
  - `falhar_proximas(n)`;
  - `normalizar()`.
- **Determinístico:** sem aleatoriedade e sem rede.
- **Isolamento entre testes:** `tests/apoio` oferece uma fixture que reinicia o simulador antes e depois de cada teste.
- **Log em desenvolvimento:** `"WhatsApp simulado: envio <id do envio> aceito"`, sem número nem texto.

**Emissão** (amplia `emitir_evento` e `emitir_evento_para_varios` da E04-02). Para eventos com `whatsapp` na matriz, cria um `Envio` `whatsapp` pendente quando, no momento da emissão, todas estas condições valem:

- `CANAL_WHATSAPP` não é `desligado`;
- a conta tem `telefone`;
- a conta tem `whatsapp_consentido_em` preenchido.

O `Envio` de WhatsApp:

- tem `destino` vazio, porque o número é lido no envio;
- tem `corpo` com o texto da mensagem simulada definido nas decisões técnicas;
- tem `chave` igual a `f"{notificacao.chave}:whatsapp"`.

**Processamento** (amplia `processar_envios` da E04-03), para `canal=whatsapp`:

1. Relê a conta do envio sem trava. Se, nesse momento, ela não tiver telefone ou consentimento, o envio fica `cancelado` com `motivo_cancelamento="sem_consentimento"` e `concluido_em`, sem tentativa e sem chamar o canal. A revogação do consentimento (E02-09) vale para mensagens ainda não enviadas.
2. Se `CANAL_WHATSAPP` passou a `desligado` depois da emissão, o envio fica `cancelado` com `motivo_cancelamento="canal_desligado"`.
3. Caso contrário, chama `obter_canal_whatsapp().enviar(conta.telefone, envio.corpo)`, com as mesmas tentativas, intervalos e registros da E04-03.
4. A `TentativaDeEnvio` não grava o número.

**Isolamento da falha** (cenário 24):

- O fato que emitiu o evento é confirmado na transação dele, antes de qualquer envio. O envio de WhatsApp roda depois, em `processar_envios`, numa transação própria, e só altera `Envio` e `TentativaDeEnvio`.
- Por isso, mesmo com o WhatsApp falhando sempre:
  - o fato continua confirmado;
  - a notificação continua na central, com o conteúdo emitido;
  - o e-mail do mesmo evento segue o próprio fluxo;
  - nenhuma exceção chega a quem emitiu.
- O teste do cenário 24 usa um fato de teste, como uma tabela de `tests/apoio`, gravado na mesma transação da emissão de `pagamento_confirmado`. A E08 repete o cenário com o pagamento real do simulador de pagamentos.

## Interfaces

- `apps/notificacoes/whatsapp.py`: `CanalWhatsApp`, `CanalWhatsAppDesligado`, `CanalWhatsAppSimulado`, `FalhaNoCanalExterno` e `obter_canal_whatsapp`.
- `config/settings/*.py`: `CANAL_WHATSAPP` e a verificação no carregamento.
- `tests/apoio`: a fixture do simulador e a tabela de fato de teste do cenário 24.

## Invariantes

- Nenhum envio de WhatsApp é criado ou tentado para uma conta sem telefone e consentimento.
- Em produção, o simulador nunca está ativo.
- Uma falha do canal externo nunca altera nada fora de `Envio` e `TentativaDeEnvio`.

## Casos-limite e concorrência

- **Consentimento revogado entre a emissão e o envio:** o envio é cancelado sem tentativa, e o e-mail do mesmo evento não é afetado.
- **Telefone trocado entre a emissão e o envio, com o consentimento mantido:** usa o número atual. O consentimento é da conta (E02-09), e o número em uso é o que a pessoa cadastrou por último.
- **Revogação confirmada enquanto uma tentativa já está em curso:** a tentativa em curso não é interrompida. A verificação vale no início de cada tentativa, e as seguintes já veem a revogação. A pessoa pode receber, no máximo, a mensagem que já estava saindo.
- **Evento sem WhatsApp na matriz** (por exemplo, `estorno`) para uma conta com consentimento: nenhum envio de WhatsApp.
- **Emissão repetida com a mesma chave:** nenhum envio novo, em nenhum canal (E04-02).
- **Falha em duas tentativas e sucesso na terceira:** `enviado`, com três tentativas registradas e uma mensagem na lista do simulador.

## Dependências e decisões em aberto

- Depende de E02-09, E04-02 e E04-03.
- Sem decisões em aberto. As pendências da Meta (conta comercial, templates e tarifas) continuam abertas e não são consideradas resolvidas.
