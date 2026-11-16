# E15-01 — Monitoramento das tarefas periódicas

Fatia 1 de 7 da milestone **E15 — Painel administrativo e alertas operacionais**. Agente 1 (especificador).

## Versões dos documentos-base

Especificação funcional v1.7 e infraestrutura v1.8 (29/10/2026). O texto de saída da milestone 15 cita a base v1.6/v1.7. As seções usadas aqui (especificação §13 e §15 "Operação"; infraestrutura 3.6, 5 e 7) não mudaram entre essas versões. O gate de especificação é feito pelo especificador, por decisão do responsável.

## Divisão da E15

| Fatia | Objetivo |
|---|---|
| E15-01 | Registro da execução de cada tarefa periódica e cálculo de "tarefa atrasada" |
| E15-02 | Alertas operacionais: tipos, aviso ao administrador e verificação periódica, com o alerta de tarefa atrasada |
| E15-03 | Atrasos de processamento por domínio: fechamento, pedido formal, conciliação, chamadas ao provedor e envios |
| E15-04 | Falhas de comunicação e do provedor: mensagens, chamadas que falharam, consultas divergentes, pagamentos sem horário ou sem pedido, avisos recusados em sequência; ciência do administrador |
| E15-05 | Painel do administrador (`administracao/`): alertas, ações necessárias, rodadas, mínimos, caixas pendentes, prazos encerrados e tarefas |
| E15-06 | Histórico de ações relevantes (auditoria) |
| E15-07 | Ponta a ponta |

Ordem: E15-01, depois E15-02, depois E15-03 e E15-04 (em qualquer ordem), depois E15-05 e por fim E15-07. A E15-06 não depende das outras e pode ser feita a qualquer momento.

## Contexto e objetivo

A infraestrutura 3.6 manda gerar alerta de **tarefa atrasada**, e a especificação §15 pede alertas para "tarefas atrasadas". Hoje nada registra quando cada tarefa periódica do Procrastinate terminou. Esta fatia:
- grava a última conclusão e a última falha de cada tarefa;
- calcula, a partir disso, quais tarefas estão atrasadas.

O alerta em si é da E15-02, e a exibição é da E15-05.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §15, Operação | Logs e alertas para (...) tarefas atrasadas. |
| Especificação §15, Tempo | Processamento retomável; bloqueios por prazo valem mesmo se um job atrasar. |
| Infraestrutura 3.6 | Alertas gerados por tarefas agendadas e enviados ao admin, inclusive "tarefa atrasada". |
| Infraestrutura 5 | Nenhum dado pessoal em logs. |
| Milestone 15, herdados E04, E06, E08 e E09 | Alerta de tarefa atrasada para `processar_envios_pendentes`, `encerrar_fechamentos_vencidos`, `bloquear_tentativas_vencidas`, `reconsultar_pagamentos_da_margem` e `conciliar_dias_pendentes`. |

## Escopo

**Dentro:**
- um app novo `apps/operacao`, sem dependência nova;
- o modelo do registro de execução;
- o catálogo das tarefas monitoradas;
- o envoltório que registra cada execução;
- a leitura da situação das tarefas.

**Fora:** abrir alertas (E15-02), as telas (E15-05) e o monitoramento externo do processo do worker (ver "Limitação").

## Modelo

`ExecucaoDaTarefa` (`apps/operacao`) tem um registro por tarefa. O registro é **mutável**, porque guarda estado operacional, e não dado financeiro ou de auditoria.

| Campo | Tipo | Observação |
|---|---|---|
| `nome` | texto até 60, `UNIQUE` | o nome da tarefa no Procrastinate |
| `monitorada_desde` | instante | quando o registro foi criado |
| `ultima_conclusao_em` | instante, nulo | a última execução que terminou sem exceção |
| `ultima_falha_em` | instante, nulo | a última execução que terminou com exceção |
| `ultimo_erro` | texto até 100 | só o nome da classe da exceção, nunca a mensagem |
| `falhas_seguidas` | inteiro ≥ 0 | as falhas desde a última conclusão |

## Catálogo das tarefas monitoradas

`TAREFAS_MONITORADAS` guarda, para cada tarefa, o nome, a descrição exibida, o intervalo esperado (o `cron` atual) e a tolerância:

| Nome | Descrição | Intervalo | Tolerância |
|---|---|---|---|
| `processar_envios_pendentes` | Envio de notificações | 1 min | 5 min |
| `processar_chamadas_ao_provedor` | Chamadas ao provedor de pagamentos | 1 min | 5 min |
| `encerrar_fechamentos_vencidos` | Encerramento dos fechamentos vencidos | 1 min | 5 min |
| `bloquear_tentativas_vencidas` | Bloqueio das cobranças depois do prazo de pagamento | 1 min | 5 min |
| `enviar_pedidos_formais` | Envio automático dos pedidos formais | 1 min | 5 min |
| `registrar_tarifas_pendentes` | Registro das tarifas do provedor | 10 min | 30 min |
| `verificar_invariante` | Verificação do invariante financeiro | 10 min | 30 min |
| `reconsultar_pagamentos_da_margem` | Reconsulta dos pagamentos na margem | 10 min | 30 min |
| `autorizar_devolucoes_do_cancelamento` | Devoluções dos cancelamentos | 10 min | 30 min |
| `conciliar_dias_pendentes` | Conciliação diária | 1 h | 3 h |

A E15-02 acrescenta a própria tarefa de verificação. Uma tarefa periódica criada em etapa futura entra no catálogo na mesma fatia que a cria.

## Regras

1. **Envoltório:** `execucao_monitorada(nome)` é um gerenciador de contexto que envolve o corpo de cada uma das dez tarefas periódicas acima, sem mudar o que elas fazem.
   - **Nome fora do catálogo:** `ValueError`, antes de executar o corpo.
   - **Corpo sem exceção:** grava `ultima_conclusao_em = agora()` e `falhas_seguidas = 0`.
   - **Corpo com exceção:** grava `ultima_falha_em = agora()`, `ultimo_erro` com o nome da classe e `falhas_seguidas + 1`. Depois **relança a mesma exceção**, para que o Procrastinate continue vendo a falha.
   - **Transação própria:** a gravação acontece depois do corpo, numa transação separada.
     - Se uma transação do corpo for desfeita, o registro não se perde.
     - Se a gravação do registro falhar, o resultado do corpo não muda. A falha vai para o log com o nome da tarefa e a classe do erro, sem dados pessoais.
2. **Criação:** o registro é criado na primeira gravação, com `monitorada_desde = agora()`. Duas primeiras execuções simultâneas criam um registro só: o `UNIQUE` decide, e quem perde relê o registro e o atualiza.
3. **Monotonia:** `ultima_conclusao_em` e `ultima_falha_em` nunca voltam no tempo. Uma gravação com instante anterior ao já gravado não o substitui.
4. **Situação das tarefas:** `situacao_das_tarefas(instante)` devolve, para cada tarefa do catálogo e na ordem do catálogo, o nome, a descrição, o intervalo, a tolerância, os campos do registro e o estado:
   - `sem_registro`: não há registro;
   - `atrasada`: `instante − referencia > tolerancia`. A `referencia` é `ultima_conclusao_em` ou, quando não há conclusão, `monitorada_desde`;
   - `em_dia`: os demais casos. No limite exato (`= tolerancia`), a tarefa está em dia.

   Quando a tarefa está atrasada, a função também devolve `atrasada_desde = referencia + tolerancia`.
5. **Sem dados pessoais:** o registro e o log guardam só o nome da tarefa, os instantes, a contagem e o nome da classe do erro.

## Interface

```python
@contextmanager
def execucao_monitorada(nome: str) -> Iterator[None]: ...

@dataclass(frozen=True)
class SituacaoDaTarefa:
    nome: str
    descricao: str
    intervalo: timedelta
    tolerancia: timedelta
    estado: str  # "em_dia" | "atrasada" | "sem_registro"
    monitorada_desde: datetime | None
    ultima_conclusao_em: datetime | None
    ultima_falha_em: datetime | None
    ultimo_erro: str
    falhas_seguidas: int
    atrasada_desde: datetime | None

def situacao_das_tarefas(instante: datetime) -> list[SituacaoDaTarefa]: ...
```

## Decisões técnicas

- **Registro próprio de execução, em vez das tabelas do Procrastinate.** As tabelas internas da biblioteca não são interface pública e mudam entre versões. O registro próprio é simples, testável e não depende do worker.
- **Tolerância de três a cinco intervalos.** Ela absorve um atraso normal da fila sem alarme falso e ainda avisa em minutos. Os valores são parâmetros operacionais, não regra comercial.
- **Falha não é atraso.** Uma tarefa que falha não conclui. Se continuar falhando, passa a atrasada pela regra 4. A última falha aparece no painel (E15-05) para diagnóstico.

## Limitação

Se o processo do worker parar por inteiro, nenhuma tarefa roda, inclusive a verificação da E15-02, e nenhum alerta é aberto. O painel (E15-05) calcula a situação na hora da leitura e mostra as tarefas atrasadas mesmo assim. Um aviso que não dependa do worker (monitor externo, como o de cron do Sentry, previsto na infraestrutura 2) fica registrado como herdado para a E16.

## Invariantes

- Há um registro por tarefa.
- O envoltório nunca engole a exceção do corpo nem muda o retorno dele.

## Dependências e decisões em aberto

- Depende das tarefas das E04, E06, E07, E08, E09, E12 e E13.
- Nenhuma decisão em aberto.
