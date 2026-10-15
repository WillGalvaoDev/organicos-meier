# E01-05 — Utilitário de testes de concorrência

Fatia 5 de 5 da milestone **E01 — Fundação de engenharia**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Reservas, fila, caixas, pagamentos, devoluções e envios exigem testes de corrida com transações reais (AGENTS.md §6). Esta fatia cria um utilitário de teste que executa operações em paralelo, cada uma com sua conexão ao Postgres, de forma determinística e sem travar a suíte. Os testes de corrida das etapas seguintes usarão esse utilitário.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| AGENTS.md §6 | Operações críticas transacionais. Testar corridas relevantes em estoque, fila, pedidos, pagamentos e estornos. |
| Especificação §15 | Transações ou mecanismo equivalente para estoque, fila, caixas e congelamento. |
| Infraestrutura 5 e testes T-6, T-7, T-21, T-31, T-45, T-49, T-53, T-55 | Testes de concorrência com `select_for_update` e transações reais. |
| pyproject.toml | Marcador `concorrencia` já declarado. |

## Escopo

**Dentro:**

- Função de teste que executa N operações em paralelo, cada uma em sua thread e com sua própria conexão ao banco.
- Barreira de sincronização que as operações podem usar para forçar um ponto de encontro, por exemplo depois de ler e antes de gravar.
- Coleta de resultados e de exceções de cada operação.
- Tempo limite: a execução falha com erro claro em vez de travar a suíte.
- Fechamento das conexões abertas pelas threads ao final.
- Dois testes de demonstração que provam que o utilitário detecta uma corrida real e confirma a correção com trava.

**Fora:**

- Testes de corrida de negócio (ficam nas etapas E05 em diante).
- Paralelismo entre processos (`pytest-xdist`).

## Regras

- **Isolamento:** cada operação roda em uma thread própria, com conexão própria ao Postgres. O teste chamador precisa usar banco transacional (`django_db(transaction=True)`) e o marcador `concorrencia`.
- **Início sincronizado:** todas as operações começam juntas, liberadas por uma barreira de início.
- **Barreira interna:** a operação pode receber uma barreira para um segundo ponto de encontro definido pelo teste.
- **Resultado:** para cada operação, devolve o valor retornado ou a exceção levantada, na mesma ordem das operações passadas.
- **Tempo limite:** se alguma operação não terminar dentro do limite (padrão definido pelo implementador e configurável), a função falha com uma exceção própria que identifica a operação pendente.
- **Conexões:** ao final, com sucesso, erro ou tempo esgotado, as conexões abertas pelas threads são fechadas, e testes seguintes não herdam conexões abertas.

## Interfaces

Módulo de testes `tests/apoio/concorrencia.py` (nomes ajustáveis pelo implementador, se mantidos o comportamento e os testes):

- `executar_em_paralelo(*operacoes, tempo_limite=...) -> list[Resultado]`
- `Resultado`, com `valor` ou `excecao`.
- `TempoEsgotado(Exception)`.
- Cada operação é uma função que recebe a barreira interna.

## Invariantes

- O utilitário não altera o comportamento transacional da operação: cada operação controla as próprias transações.
- Nenhuma exceção de thread é perdida.
- A suíte nunca fica travada por causa do utilitário.

## Casos-limite e concorrência

- **Demonstração de corrida (sem trava):** duas operações leem um contador com valor 0, encontram-se na barreira interna e gravam `valor + 1`. O resultado final é 1, a atualização perdida esperada. O teste afirma esse resultado, o que prova que o utilitário reproduz a corrida de forma determinística.
- **Demonstração de correção (com trava):** duas operações incrementam o mesmo contador com `select_for_update` dentro de `transaction.atomic`, sem barreira interna. O resultado final é 2 em todas as repetições.
- **Exceção em uma operação:** uma operação levanta erro e a outra termina. O utilitário devolve a exceção da primeira e o valor da segunda.
- **Tempo limite:** uma operação espera numa barreira que nunca é completada. O utilitário levanta `TempoEsgotado` dentro do limite configurado.

## Dependências e decisões em aberto

- Depende de E01-01 (CI, com Postgres real).
- O modelo de contador usado nas demonstrações fica no app só de testes `tests/apoio` (definido na spec da E01-02).
- Sem decisões em aberto.
