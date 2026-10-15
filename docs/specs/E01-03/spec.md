# E01-03 — Relógio do servidor e comparação de prazos

Fatia 3 de 5 da milestone **E01 — Fundação de engenharia**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Os prazos de fechamento (24h), pagamento (`T0 + 24h`), margem (`T0 + 48h`) e armazenamento (sete dias) dependem de uma fonte única de tempo no servidor e de regras de fronteira sem ambiguidade. Esta fatia cria essa fonte, as comparações de fronteira e o controle de relógio para os testes. As regras de cada prazo ficam nas etapas E06, E08 e E14.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §15 (tempo) | Prazos calculados no servidor, 24 horas decorridas inclusive de madrugada. Instantes armazenados de forma inequívoca e exibidos em America/Sao_Paulo. |
| Infraestrutura 4.3 (fronteiras) | Comparação em UTC. `T0 + 24h` exato já é bloqueado (intervalo aberto à direita). `date_approved = T0 + 48h` exato é aceito (limite inclusivo). |
| Infraestrutura 5 | Instantes em UTC, exibidos em America/Sao_Paulo. Prazos checados nas tarefas e em cada ação. |
| AGENTS.md §6 | Respeitar as fronteiras oficiais de 24h e 48h. |
| Infraestrutura 8 (T-1, T-2, T-4) | Testes de fronteira com precisão de milissegundos. |

## Escopo

**Dentro:**

- Função única para obter o instante atual no servidor, em UTC e com fuso.
- Funções de prazo: somar duração a um instante; testar "prazo encerrado" (limite exclusivo) e "até o limite" (limite inclusivo).
- Conversão para exibição em America/Sao_Paulo.
- Recusa de instantes sem fuso.
- Fixture de teste para congelar e avançar o relógio.
- Regra estática contra o uso de `datetime.now()` e `datetime.utcnow()` sem fuso.

**Fora:**

- Regras de cada prazo de negócio (E06, E08, E14).
- Normalização de horários vindos do provedor de pagamento (E07).
- Tarefas agendadas (Procrastinate) e seus atrasos (entram com a primeira fatia que agenda tarefas).

## Regras

- **Instante atual:** `agora()` devolve `datetime` com fuso UTC. O código de negócio usa só essa função para obter o instante atual.
- **Duração:** prazos em horas são somados como duração absoluta (`timedelta`), em UTC. Mudanças de horário de verão ou de fuso civil não alteram as 24 horas decorridas.
- **Prazo encerrado (limite exclusivo):** `prazo_encerrado(instante, limite)` é verdadeiro quando `instante >= limite`. Representa janelas `[início, limite)`, como a de pagamento.
- **Até o limite (inclusivo):** `ate_o_limite(instante, limite)` é verdadeiro quando `instante <= limite`. Representa a aceitação até `T0 + 48h`.
- **Precisão:** as comparações usam a precisão completa do `datetime`, sem arredondar. A precisão de milissegundos exigida pela infraestrutura fica coberta.
- **Exibição:** `no_fuso_da_operacao(instante)` converte para America/Sao_Paulo, sem alterar o instante.
- **Sem fuso:** qualquer função desta fatia recusa `datetime` sem fuso com uma exceção própria.
- **Persistência:** instantes gravados no Postgres (`timestamptz`) e relidos são iguais ao instante original em UTC.

## Interfaces

Módulo `apps/nucleo/tempo.py` (nomes ajustáveis pelo implementador, se mantidos o comportamento e os testes):

- `agora() -> datetime`
- `somar_horas(instante: datetime, horas: int) -> datetime`
- `prazo_encerrado(instante: datetime, limite: datetime) -> bool`
- `ate_o_limite(instante: datetime, limite: datetime) -> bool`
- `no_fuso_da_operacao(instante: datetime) -> datetime`
- `InstanteSemFuso(Exception)`

Fixture de pytest `relogio` em `tests/conftest.py`, com:

- `congelar(instante)`
- `avancar(duracao)`

Durante o teste, `agora()` reflete o relógio controlado.

## Invariantes

- `agora()` sempre tem fuso, e o fuso é UTC.
- `prazo_encerrado` e `ate_o_limite` não são complementares: no instante exatamente igual ao limite, os dois são verdadeiros. Cada regra de negócio escolhe a comparação que corresponde ao seu tipo de limite (exclusivo ou inclusivo).
- Nenhuma função desta fatia usa o relógio do banco (`now()` do Postgres).

## Casos-limite e concorrência

- Fronteira exata, 1 ms antes e 1 ms depois, nas duas comparações.
- Prazo de 24h que atravessa a meia-noite em America/Sao_Paulo.
- Instante gravado e relido do banco com microssegundos.
- Sem concorrência nesta fatia.

## Dependências e decisões em aberto

- Depende de E01-01 (CI).
- A regra estática contra `datetime.now()` sem fuso usa o conjunto `DTZ` do ruff, já disponível. Ela é acrescentada ao `pyproject.toml` nesta fatia.
- Sem decisões em aberto.
