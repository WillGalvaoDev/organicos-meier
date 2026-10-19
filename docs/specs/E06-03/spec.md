# E06-03 — Bloqueio pelo prazo nas ações

Fatia 3 de 7 da milestone **E06 — Fechamento e caixas**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

No fim do prazo, a tarefa da E06-05 passa a rodada a `fechamento_encerrado`. A tarefa pode atrasar alguns segundos ou minutos, mas as ações não podem esperar por ela: a partir do instante exato do prazo, nenhuma alteração de interesse é aceita, mesmo com a etapa gravada ainda como `fechamento` (§15).

Esta fatia entrega:

- uma regra única que diz se a rodada aceita interesses num instante;
- o uso dessa regra em todos os pontos da E05 que hoje decidem só pela etapa.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §5 | "Após o prazo de fechamento, alterações ficam bloqueadas até decisão administrativa." |
| Especificação §7 | Fechamento com prazo encerrado: "bloqueia alterações automaticamente". |
| Especificação §15 | "Bloqueios por prazo devem valer mesmo se um job atrasar: validar prazo também nas ações do usuário." |
| Infraestrutura 5 | "Prazos checados nas tarefas agendadas e em cada ação." |
| E01-03 | `prazo_encerrado(instante, limite)`: limite exclusivo (`instante >= limite`). |
| E05-01 | `travar_rodada_para_interesses` recebe da E06 a recusa do fechamento com prazo vencido. |
| E05-02, E05-05, E05-07 | A fila, as telas e a remoção por suspensão decidem pela etapa se a rodada aceita reservas. |
| E06-01 | `prazo_do_fechamento(rodada)`. |

## Escopo

**Dentro:**

- A função `aceita_interesses(rodada, instante)`.
- A recusa com o código `prazo_encerrado` em `travar_rodada_para_interesses`.
- A troca dos testes de etapa em `apps/interesses` pela função nova.

**Fora:**

- A mudança de etapa no fim do prazo e a remoção de excedentes (E06-05).
- O texto do prazo nas telas (E06-07). Aqui as telas só deixam de oferecer formulários.
- A remoção de pendentes (E05-03) e a remoção por suspensão (E05-07). As duas continuam valendo em qualquer etapa e em qualquer instante, como já especificado. Só a fila disparada pela suspensão passa a respeitar o prazo.
- O preço (E03-03 e E05-06), que não está entre as alterações de interesse.

## Decisões técnicas

- **Uma regra só.** Hoje, a decisão "a rodada aceita interesses?" está espalhada:
  - `travar_rodada_para_interesses` e `interesses_editaveis`, em `apps/rodadas/condicoes.py`;
  - `remover_interesses_do_comprador`, em `apps/interesses/servicos.py`;
  - `ETAPAS_QUE_ACEITAM`, em `apps/interesses/apresentacao.py`;
  - o cálculo de `editavel` do grupo, em `apps/interesses/consultas.py`.

  Todos passam a usar `aceita_interesses`. Assim, a fila (E05-02, por meio de `travar_rodada_para_interesses`), as operações do comprador (E05-01 e E05-03) e as telas (E05-05) mudam juntas.
- **O instante é lido uma vez por operação**, com `agora()`, depois das travas. Isso evita que duas partes da mesma transação discordem sobre o prazo.
- **Código novo, mesma mensagem.** A recusa por prazo usa o código `prazo_encerrado` em `InteressesBloqueados`, com a mesma mensagem: "Os interesses deste fornecedor não podem ser alterados nesta etapa.". As telas (E05-05) respondem 409 como para `etapa_bloqueada`. O código distinto serve para auditoria, testes e a E06-07.

## Regras

**Função** (`apps/rodadas/condicoes.py`):

```
aceita_interesses(rodada, instante) -> bool
```

- Verdadeiro com `rodada.etapa == interesse`.
- Verdadeiro com `rodada.etapa == fechamento` e `not prazo_encerrado(instante, prazo_do_fechamento(rodada))`.
- Falso em todos os outros casos.
- Uma rodada em `fechamento` sem prazo gravado viola a invariante da E06-01 e levanta `RuntimeError`, para não aceitar interesse sem prazo.

**`travar_rodada_para_interesses`** (E05-01), depois das travas do fornecedor e da rodada:

- sem rodada ativa: `sem_rodada_ativa`, como hoje;
- etapa fora de `interesse` e `fechamento`: `etapa_bloqueada`, como hoje;
- `fechamento` com o prazo encerrado em `agora()`: `prazo_encerrado`.

**`interesses_editaveis(fornecedor)`:** leitura sem trava, que passa a usar `aceita_interesses(rodada, agora())`.

**`remover_interesses_do_comprador`** (E05-07): a fila só é atendida quando `aceita_interesses(rodada, agora())` é verdadeiro. A remoção das parcelas continua em qualquer etapa e em qualquer instante. Sem atendimento da fila, o estoque liberado fica livre até a E06-05 ou E06-06 decidirem o destino da rodada.

**Telas** (E05-05): carrinho e catálogo usam `aceita_interesses` para decidir se mostram o formulário de quantidade. Com o prazo encerrado, nenhum formulário de quantidade aparece. O formulário "Remover pendentes" continua, porque vale em qualquer etapa.

**Busca obrigatória:** o implementador procura em `apps/` todo uso de `Etapa.FECHAMENTO` (e de tuplas de etapas que o contenham) que decida se interesses são aceitos, e troca por `aceita_interesses`. A lista dos pontos trocados vai para o `review.md`.

## Ajuste autorizado nos testes existentes

Vários testes da E03 e da E05 colocam a rodada em `fechamento` pela fábrica ou por `update()`, sem ciclo nem prazo, porque a transição real ainda não existia. Com esta fatia, `aceita_interesses` levanta `RuntimeError` nesse estado, de propósito: uma rodada em `fechamento` sem prazo não é produzida por nenhum serviço.

Para não afrouxar a regra, os testes passam a dar um prazo à rodada. O ajuste é só de preparação; nenhuma asserção muda.

1. **Novo auxiliar** em `tests/apoio/ciclos.py`:

   ```
   dar_prazo_de_teste(rodada, termina_em=None) -> PrazoDoFechamento
   ```

   - Cria um `Ciclo` (número seguinte, mínimo do fornecedor) e uma linha de prazo `inicio`, com o administrador existente como autor.
   - `termina_em` padrão: `agora() + 24 h` para a etapa `fechamento` e `agora() − 1 min` para `fechamento_encerrado`.
2. **`cenario()`** de `tests/apoio/interesses.py` chama o auxiliar quando recebe `etapa` igual a `fechamento` ou `fechamento_encerrado`.
3. **Testes que fazem `update(etapa=fechamento)`** ou criam a rodada nessa etapa pela fábrica, e depois exercitam interesses, a fila, o carrinho ou o catálogo: chamam o auxiliar logo depois de mudar a etapa. Na E05, o `test_catalogo_comprador.py` é um caso conhecido.
4. **Testes que só testam condições congeladas** (`travar_condicoes`) não precisam do auxiliar e não devem recebê-lo. Por exemplo, `test_registro_fora_de_interesse_e_recusado`, da E03-07, confere que nenhum ciclo existe.

O implementador roda a suíte inteira depois da mudança de `aceita_interesses`. Cada teste que falhar com o `RuntimeError` desta regra recebe o auxiliar. Uma falha por outro motivo é investigada, e o teste não é ajustado. A lista dos testes ajustados vai para o `review.md`.

## Interfaces

- `apps/rodadas/condicoes.py`: `aceita_interesses`, o código `prazo_encerrado` e os ajustes de `travar_rodada_para_interesses` e `interesses_editaveis`.
- `apps/interesses/servicos.py`, `apresentacao.py` e `consultas.py`: o uso da função.

## Invariantes

- Nenhuma parcela é criada, reduzida, removida pelo comprador nem alocada pela fila numa rodada em `fechamento` a partir do instante do prazo.
- O resultado não depende de a tarefa da E06-05 já ter rodado.

## Casos-limite e concorrência

- **Fronteira:**
  - aceito em `prazo − 1 ms`;
  - recusado com `prazo_encerrado` exatamente em `prazo` e em `prazo + 1 ms` (limite exclusivo, E01-03).
- **Prorrogação** (E06-04): depois de uma prorrogação confirmada, vale o prazo novo. Uma ação recusada antes da prorrogação pode ser repetida e aceita depois.
- **Adição que chega ao fornecedor travado pela tarefa de encerramento:** quando ela obtém a trava, a etapa já é `fechamento_encerrado` (`etapa_bloqueada`) ou o prazo já venceu (`prazo_encerrado`). Nos dois casos, é recusada.
- **Rodada em `interesse`:** sem prazo e sem mudança de comportamento.

## Correção E06-R01 — retorno ao interesse entre as leituras da página (2026-10-19)

### Diagnóstico

`aceita_interesses` decide a etapa pelo objeto recebido, mas busca o prazo com `prazo_do_fechamento`, que relê a etapa no banco e devolve `None` fora de `fechamento` e `fechamento_encerrado`. As duas leituras não são do mesmo momento:

1. a página (carrinho ou catálogo) lê a rodada em `fechamento`;
2. o encerramento (E06-05) confirma e, com o mínimo não atingido, devolve a rodada a `interesse` (E06-06);
3. `aceita_interesses` vê `fechamento` no objeto, `prazo_do_fechamento` vê `interesse` no banco e devolve `None`;
4. a regra trata o `None` como fechamento sem prazo e levanta `RuntimeError`, e a página responde 500.

A transição é legítima e o histórico de prazos existe. O erro é de coerência entre as leituras, não de dados. O revisor reproduziu o caso nas duas páginas. `interesses_editaveis` tem a mesma sequência (lê a rodada e depois chama a regra) e o mesmo defeito.

Eu não previ esse caso: a spec mandou usar `prazo_do_fechamento` dentro da regra sem dizer de que momento vinha a etapa.

### Regra

**Um único retrato da rodada.** A decisão usa a etapa do objeto recebido e o prazo do ciclo desse objeto, sem reler a etapa:

- **Função nova** em `apps/rodadas/fechamento.py`:

  ```
  prazo_do_ciclo(rodada) -> datetime | None
  ```

  Devolve o maior `termina_em` do ciclo vigente da rodada (`ciclo_vigente`, E03-07), sem consultar a etapa. Devolve `None` quando a rodada não tem ciclo ou quando o ciclo não tem linha de prazo.
- **`aceita_interesses(rodada, instante)`** troca `prazo_do_fechamento` por `prazo_do_ciclo`. O resto não muda:
  - verdadeiro com `rodada.etapa == interesse`;
  - com `rodada.etapa == fechamento`, `not prazo_encerrado(instante, prazo_do_ciclo(rodada))`;
  - com `fechamento` e `prazo_do_ciclo` igual a `None`, continua levantando `RuntimeError`. Esse é o fechamento realmente sem prazo, que nenhum serviço produz;
  - falso nas demais etapas.
- **`prazo_da_rodada`** (`apps/interesses/apresentacao.py`), que dá a linha do prazo do carrinho e do catálogo, também passa a usar `prazo_do_ciclo`, com a etapa do objeto. Assim, a linha do prazo e os formulários da mesma página descrevem o mesmo estado.

**Por que isso basta.** As linhas de prazo só recebem inserções (E06-01) e são gravadas na mesma transação que cria o ciclo e põe a rodada em `fechamento`. Quem leu a rodada em `fechamento` encontra o prazo desse ciclo, mesmo que a etapa já tenha mudado depois. Se a rodada entrou num ciclo novo nesse meio-tempo, o ciclo vigente é o novo, também com prazo. O `RuntimeError` só aparece quando a invariante foi de fato violada.

**Efeito na página.** A página mostra o estado que leu. No caso do diagnóstico, ela lê `fechamento` com o prazo vencido, não mostra formulário de quantidade e mostra "Prazo do fechamento encerrado em <data> às <hora>.". A página seguinte já mostra a rodada em `interesse`. Toda gravação continua decidida sob trava (`travar_rodada_para_interesses`), onde o objeto é o travado e o comportamento não muda.

**O que não muda:**

- `prazo_do_fechamento` (E06-01) continua com o mesmo contrato e os mesmos usos: telas do administrador, detalhe do fornecedor, prorrogação e encerramento. Nesses usos não há `RuntimeError` por leitura defasada.
- `aceita_interesses` continua importada pelo nome em `apps/interesses/consultas.py` e `apresentacao.py`. A prova do revisor substitui esse nome para intercalar o encerramento.
- Nenhuma exceção é capturada para mascarar o erro: o `RuntimeError` do fechamento sem prazo continua chegando a quem chamou.
- Os critérios A-1 a A-9.

### TDD

Os critérios A-10 a A-12 seguem Red → Green → Refactor, com as regras de prevenção da correção E05-R04 (E05-01). A prova `test_leitura_durante_retorno_nao_causa_500` do revisor de `2fbf143` (as duas origens) é o Red esperado no código atual (`RuntimeError`) e entra literalmente nos testes.

## Dependências e decisões em aberto

- Depende de E01-03, E05-01, E05-02, E05-05, E05-07 e E06-01.
- Sem decisões em aberto.
