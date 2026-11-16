# E15-02 — Alertas operacionais e verificação periódica

Fatia 2 de 7 da milestone **E15 — Painel administrativo e alertas operacionais**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E15-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E15-01.

## Contexto e objetivo

Os alertas financeiros da E09-03 (`AlertaFinanceiro`, `abrir_alerta`, `resolver_alerta`, `alertas_abertos`) já cobrem oito dos dez itens da infraestrutura 3.6. Faltam "tarefa atrasada" e "falha de mensagem", além dos alertas herdados das E04 a E09.

Esta fatia:
- estende o mesmo mecanismo com **tipos operacionais**, que têm aviso e link próprios;
- cria a **verificação periódica** que abre e resolve esses alertas;
- entrega o primeiro tipo, `tarefa_atrasada`, a partir da E15-01.

As E15-03 e E15-04 só acrescentam verificações.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.6 | Alertas gerados por tarefas agendadas e enviados ao admin; inclui "tarefa atrasada". |
| Especificação §15, Operação | Logs e alertas para (...) tarefas atrasadas e falhas de comunicação. |
| Especificação §12 | Falha de mensagem não altera o estado; o site continua correto se um canal externo falhar. |
| E09-03 | Um alerta aberto por `(tipo, chave)`; só a abertura avisa; nenhum dado pessoal no alerta. |
| E15-01 | `situacao_das_tarefas`. |

## Escopo

**Dentro:**
- os tipos operacionais no mecanismo da E09-03;
- o evento de notificação `alerta_operacional`;
- o registro de verificações e a tarefa periódica `verificar_operacao`;
- o alerta `tarefa_atrasada`.

**Fora:**
- as demais verificações (E15-03 e E15-04);
- a ciência do administrador (E15-04);
- as telas (E15-05).

## Regras

### Tipos operacionais

1. **Mesmo modelo e mesmas funções.** Os tipos operacionais são novos valores de `TipoDeAlerta`, gravados em `AlertaFinanceiro`. Continuam valendo:
   - um aberto por par (a restrição `alerta_um_aberto_por_par`);
   - `abrir_alerta` e `resolver_alerta`, que exigem uma transação aberta;
   - a validação sem segredos.

   O nome do modelo não muda: ver "Decisões técnicas".
2. **Classificação.** Cada tipo operacional tem:
   - **gravidade** (`critico` ou `aviso`);
   - **título** e **corpo**, montados a partir de `dados`;
   - **link**, um nome de rota com argumentos tirados de `dados`;
   - **natureza**:
     - `condicao`: o alerta fica aberto enquanto a situação dura e é resolvido pela verificação;
     - `fato`: o alerta registra um acontecimento e é resolvido pela ciência do administrador (E15-04).
3. **Aviso.** Na abertura de um tipo operacional, `abrir_alerta` emite o evento novo `Evento.ALERTA_OPERACIONAL` ("alerta_operacional", rótulo "Alerta operacional"):
   - para cada administrador ativo;
   - com o título, o corpo e o link do tipo e a chave base `alerta_operacional:<pk>`;
   - pelos canais site e e-mail, só para administrador, como `ALERTA_FINANCEIRO`.

   Os testes existentes que transcrevem o catálogo de eventos (a matriz de canais da E04-01 e o conjunto de eventos do administrador do A-11 da E09-03) ganham a linha `alerta_operacional` (administrador; site e e-mail). É consequência desta regra: nenhuma asserção deles é removida.

   Os tipos financeiros continuam exatamente como hoje: evento `alerta_financeiro` e link `financeiro_resumo`. Sem administrador ativo: o alerta é aberto e o log registra a falta de destinatário, como hoje.
4. **Log.** Na abertura vai `logger.warning` (aviso) ou `logger.error` (crítico), com o tipo e a chave, sem `dados`.

### Verificação periódica

5. **Registro de verificações:** `registrar_verificacao(tipo, funcao)`. A função recebe o instante e devolve `dict[chave, dados]` com as ocorrências atuais.
   - Em tipo `condicao`, são as situações que valem agora.
   - Em tipo `fato`, são os fatos que ainda não têm alerta posterior a eles (regra da E15-04).
6. **`verificar_operacao_agora()`**, com `instante = agora()` lido uma vez. Para cada verificação registrada, na ordem de registro e **numa transação própria**:
   - abre o alerta de cada chave devolvida que não tem alerta aberto do par;
   - em tipo `condicao`, resolve, com o motivo "condição encerrada", os alertas abertos do tipo cuja chave não voltou;
   - se a verificação levantar exceção, a transação dela é desfeita: nenhum alerta do tipo é aberto nem resolvido naquela execução. O log registra o tipo e a classe do erro, e as demais verificações continuam.

   A função devolve quantos alertas **esta execução** abriu e quantos resolveu (correção E15-R02):
   - conta como aberto só o alerta que esta execução inseriu de fato. Quando outra execução concorrente gravou primeiro o alerta do par e o `UNIQUE` parcial recusou esta inserção, o par não conta. A leitura de "já aberto" feita antes da tentativa não decide a contagem;
   - conta como resolvido só o alerta que esta execução resolveu de fato (`resolver_alerta` devolveu o alerta). O que outra execução resolveu antes não conta;
   - em duas execuções concorrentes sobre a mesma situação, a soma dos abertos é igual ao número de alertas abertos novos no banco.

   A assinatura e o comportamento de `abrir_alerta` (E09-03) não mudam para os chamadores atuais. Como a verificação fica sabendo se a inserção foi feita é detalhe interno; por exemplo, uma função auxiliar que devolva `(alerta, criado)` e que `abrir_alerta` reaproveite.
7. **Tarefa periódica:** `verificar_operacao`, com `cron="*/5 * * * *"` e `queueing_lock`. Ela é envolvida por `execucao_monitorada` e entra no catálogo da E15-01 com a descrição "Verificação operacional", intervalo 5 min e tolerância 15 min.
8. **Registros que faltam:** no começo de cada execução, `verificar_operacao_agora()` cria o `ExecucaoDaTarefa` de cada tarefa do catálogo que ainda não tem registro, com `monitorada_desde = instante`. Assim, uma tarefa que nunca rodou passa a atrasada depois da tolerância (E15-01, regra 4).

### Alerta `tarefa_atrasada`

9. **Condição:** cada tarefa com estado `atrasada` em `situacao_das_tarefas(instante)`.
   - **Chave:** o nome da tarefa.
   - **Dados:** `tarefa`, `descricao`, `referencia` (ISO, a última conclusão ou o início do monitoramento), `atrasada_desde` (ISO), `intervalo_minutos`.
   - **Gravidade:** aviso.
   - **Natureza:** condição.
   - **Título:** "Tarefa atrasada".
   - **Corpo:**
     - com conclusão anterior: "A tarefa <descrição> não conclui desde <referência em Brasília, dd/mm/aaaa hh:mm>. Ela deveria rodar a cada <n> minuto(s).";
     - sem conclusão: "A tarefa <descrição> não tem execução concluída desde <referência>. Ela deveria rodar a cada <n> minuto(s).".
   - **Link:** `painel_administracao`.
10. **A verificação não se acusa (correção E15-R01):** a verificação de `tarefa_atrasada` ignora a própria tarefa `verificar_operacao`. Ela nunca abre, nem mantém aberto, alerta com a chave `verificar_operacao`, mesmo quando o registro da tarefa está atrasado no instante da verificação.
    - **Motivo:** o envoltório da E15-01 só grava a conclusão no fim da execução. Na retomada, depois de mais de 15 minutos sem verificação, o registro lido durante a própria execução ainda está atrasado, e um alerta nesse momento seria falso: a verificação está rodando.
    - **Sem mudança no estado:** `situacao_das_tarefas` continua devolvendo `verificar_operacao` com o estado real, e o atraso dela aparece no painel (E15-05, regra 9) e no monitor externo (herdado para a E16).
    - **Resolução:** um alerta aberto com essa chave (por exemplo, gravado antes desta correção) é resolvido pela regra 6, com "condição encerrada", porque a chave não volta.

## Interface

```python
class Natureza(StrEnum):
    CONDICAO = "condicao"
    FATO = "fato"

def registrar_verificacao(tipo: str, funcao: Callable[[datetime], dict[str, dict[str, Any]]]) -> None: ...
def verificar_operacao_agora() -> tuple[int, int]: ...  # (abertos, resolvidos)
def link_do_alerta(alerta: AlertaFinanceiro) -> str: ...  # URL do tipo (financeiro ou operacional)
def natureza_do_alerta(alerta: AlertaFinanceiro) -> str | None: ...  # None para os financeiros
```

## Decisões técnicas

- **Um mecanismo de alertas, sem renomear o modelo.** A infraestrutura 3.6 trata todos os alertas como uma lista só ao administrador. Reaproveitar `AlertaFinanceiro` mantém a abertura única por par, a resolução, a ordenação e a validação já aprovadas. Renomear a tabela só traria migração e risco, sem efeito observável.
- **Evento próprio.** Assim a notificação do administrador não chama de "financeiro" um atraso de tarefa, e os canais ficam configuráveis separadamente (§12).
- **Verificação a cada 5 minutos, uma transação por verificação.** É mais rápido que as tolerâncias de 5 minutos da E15-01 e isola as falhas. Resolver alertas quando a verificação falhou poderia esconder um problema real.

## Invariantes

- Os alertas financeiros não mudam de comportamento.
- Nenhum comprador ou fornecedor recebe `alerta_operacional`.
- No máximo um alerta aberto por `(tipo, chave)`.

## Dependências e decisões em aberto

- Depende da E15-01, da E09-03 e da E04-02 (`emitir_evento_para_varios`).
- Nenhuma decisão em aberto.
