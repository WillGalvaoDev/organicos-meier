# E06-01 — Início do fechamento e prazo de 24 horas

Fatia 1 de 7 da milestone **E06 — Fechamento e caixas**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A rodada nasce em `interesse` (E03-02) e lá pode ficar indefinidamente. Quando o mínimo elegível é atingido, o administrador pode iniciar o fechamento. A partir desse instante:

- correm 24 horas de prazo;
- as condições da rodada ficam congeladas (E03-02 e E03-07);
- o ciclo registra os valores vigentes (E03-07).

Esta fatia entrega:

- o serviço `iniciar_fechamento`;
- o registro do prazo, que só aceita inserção e já prevê a prorrogação (E06-04);
- a leitura `prazo_do_fechamento`.

O aviso aos compradores fica na E06-02, e o botão na tela, na E06-07.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | Fechamento: "Inicia por ação administrativa quando mínimo elegível é atendido. Prazo de 24h a partir da autorização. Aceita alterações e novos compradores." Interesse: "Atingir o mínimo apenas habilita o administrador a iniciar fechamento." Toda intervenção é auditada. |
| Especificação §4.4 | A partir do início do fechamento, mínimo, múltiplos, incremento e estoque ficam congelados, inclusive para o administrador. Cada ciclo registra os valores vigentes no início do seu fechamento. |
| Especificação §6.1, §5.2 | O mínimo é monetário e só conta o elegível reservado. Pendentes não contam. |
| Especificação §15 | Prazos calculados no servidor, 24 horas decorridas, inclusive de madrugada. Instantes armazenados de forma inequívoca. |
| Cenários §16 | 4, 5 (início e prazo), 72, 104 e 107. |
| Infraestrutura 4.10, 4.14 e 5 | Condições gravadas no ciclo no início do fechamento; prazos checados nas tarefas e nas ações; instantes em UTC. |
| Infraestrutura 8 | T-23 (pela transição real) e T-47 (o mínimo ignora pendentes). |
| E01-03 | `agora()`, `somar_horas` e `prazo_encerrado`, com limite exclusivo. |
| E03-02 | Toda mudança de etapa trava o fornecedor e a rodada, nessa ordem. |
| E03-07 | `registrar_condicoes_do_ciclo` e a gravação de `fechamento` acontecem na mesma transação e com as mesmas travas. Os auxiliares `simular_*` são substituídos pelas transições reais. |
| E05-04 | `progresso_da_rodada(rodada).atingido` é o mesmo número que a E08 usa como `T`. |

## Escopo

**Dentro:**

- O modelo `PrazoDoFechamento`.
- Os serviços `iniciar_fechamento` e `prazo_do_fechamento`, e a exceção `TransicaoRecusada`.
- A troca de `simular_inicio_do_fechamento` (testes da E03-07) pelo serviço real.

**Fora:**

- O aviso `fechamento_iniciado` (E06-02).
- O bloqueio das ações pelo prazo (E06-03).
- A prorrogação (E06-04).
- O encerramento (E06-05 e E06-06).
- As telas (E06-07).

## Decisões técnicas

- **Prazo num registro só de inserção.** O `Ciclo` (E03-07) só aceita inserção, e o prazo muda com a prorrogação (E06-04). Por isso o prazo fica em `PrazoDoFechamento`, uma linha por definição de prazo:
  - uma linha `inicio`, criada aqui;
  - uma linha `prorrogacao` a cada prorrogação.

  O prazo vigente é o maior `termina_em` do ciclo vigente. Assim, o histórico das prorrogações fica gravado sem `UPDATE`.
- **O instante da autorização é o do ciclo.** O prazo é `somar_horas(ciclo.iniciado_em, 24)`, com o `iniciado_em` gravado por `registrar_condicoes_do_ciclo` na mesma transação. Os dois instantes não divergem.
- **Mínimo conferido depois das travas.** `registrar_condicoes_do_ciclo` trava o fornecedor, a rodada, os produtos e os estoques. A conferência do mínimo vem depois:
  - Toda operação de interesse trava o fornecedor primeiro (E05-01), e a edição de preço trava o produto (E03-03). Então nenhuma reserva nem preço muda entre a conferência e a gravação de `fechamento`.
  - Se o mínimo não for atingido, a transação inteira é desfeita, inclusive o ciclo recém-registrado.
- **Rodada sem produtos ou com mínimo zero:** a única exigência dos documentos-base é o mínimo elegível atingido (§7). Com mínimo zero, `atingido` é verdadeiro (E05-04), e o início é aceito. Não crio exigência adicional, como a de ter pelo menos uma reserva.

## Regras

**Modelo** (`apps/rodadas/models.py`):

```
PrazoDoFechamento(RegistroSoInsercao)
  ciclo         FK Ciclo (PROTECT, related_name="prazos")
  termina_em    DateTimeField
  origem        "inicio" | "prorrogacao"
  autor         FK Conta (PROTECT)
  registrado_em DateTimeField, default agora
```

- `UNIQUE (ciclo)` quando `origem = "inicio"`: uma única linha de início por ciclo.
- `CHECK` de `origem` dentro dos dois valores.
- Os triggers de só inserção seguem o padrão da E01-04, como no `Ciclo`.

**Serviço** (`apps/rodadas/fechamento.py`):

```
iniciar_fechamento(autor, rodada) -> Ciclo
prazo_do_fechamento(rodada) -> datetime | None
```

**`iniciar_fechamento`,** numa única `transaction.atomic()`:

1. Exige o administrador. Caso contrário, levanta `PermissionDenied`.
2. Chama `registrar_condicoes_do_ciclo(rodada)` (E03-07), que trava o fornecedor, a rodada, os produtos e os estoques. Se ela levantar `CondicoesCongeladas`, levanta `TransicaoRecusada`:
   - com o código `sem_rodada_ativa`, quando é esse o código recebido;
   - com o código `fora_de_interesse` nos outros casos, inclusive quando a rodada informada não é mais a ativa.
3. Lê `progresso_da_rodada(rodada)` (E05-04). Com `atingido` falso, levanta `TransicaoRecusada("minimo_nao_atingido")`.
4. Grava `etapa = fechamento` (`update_fields`).
5. Cria o `PrazoDoFechamento` com `origem="inicio"`, `termina_em = somar_horas(ciclo.iniciado_em, 24)` e o autor.
6. Audita `rodada.iniciar_fechamento`, com objeto igual à rodada e com `rodada`, `ciclo`, `termina_em` (ISO 8601 em UTC), `valor_elegivel` e `minimo` (texto decimal).
7. Devolve o ciclo.

Qualquer recusa desfaz tudo: o ciclo, o prazo e a auditoria.

**`TransicaoRecusada(codigo)`** fica em `apps/rodadas/fechamento.py`, com o atributo `mensagem`. As mensagens desta fatia são:

| Código | Mensagem |
|---|---|
| `sem_rodada_ativa` | "Este fornecedor não tem rodada ativa." |
| `fora_de_interesse` | "O fechamento só pode começar com a rodada em interesse." |
| `minimo_nao_atingido` | "O fechamento só pode começar com o mínimo elegível atingido." |

A E06-04 acrescenta outros códigos à mesma exceção.

**`prazo_do_fechamento(rodada)`:**

- Com a rodada em `fechamento` ou `fechamento_encerrado`, devolve o maior `termina_em` do ciclo vigente (`ciclo_vigente`, E03-07).
- Nas demais etapas, devolve `None`.
- Leitura sem trava, só para as telas e para a tarefa escolherem candidatas. Quem decide relê sob trava.

**Nada é automático.** Atingir o mínimo não inicia o fechamento (cenário 4). Nenhuma tarefa nem receptor chama `iniciar_fechamento`.

**Troca dos auxiliares da E03-07.**

- `simular_inicio_do_fechamento(rodada)`, em `tests/apoio/ciclos.py`, passa a chamar `iniciar_fechamento(<administrador>, rodada)`. O administrador é o que a fábrica já cria.
- Para que o mínimo de R$ 150,00 e depois de R$ 200,00 seja atingido, `_cenario()` de `tests/tecnicos/test_rodadas_ciclos.py` ganha uma parcela `ativa` de um comprador no produto `Q` (sem múltiplo e sem limite), com valor de pelo menos R$ 300,00 ao preço do produto.
- São os dois únicos ajustes autorizados nesses arquivos. Todas as asserções da E03-07 continuam como estão.
- `simular_volta_para_interesse` é tratado na E06-06.

## Interfaces

- `apps/rodadas/models.py`: `PrazoDoFechamento` e a migração com triggers e restrições.
- `apps/rodadas/fechamento.py`: `iniciar_fechamento`, `prazo_do_fechamento`, `TransicaoRecusada` e a constante `HORAS_DO_FECHAMENTO = 24`.
- `tests/apoio/ciclos.py` e o `_cenario()` de `tests/tecnicos/test_rodadas_ciclos.py`: os ajustes autorizados acima.

## Invariantes

- Toda rodada em `fechamento` tem um ciclo vigente com exatamente uma linha de prazo `inicio`.
- `termina_em` da linha `inicio` é exatamente 24 horas depois de `ciclo.iniciado_em`.
- Nenhum fechamento começa com o valor elegível abaixo do mínimo vigente.
- Nenhuma linha de `PrazoDoFechamento` é alterada nem apagada.

## Casos-limite e concorrência

- **Cenário 4:** com o valor elegível acima do mínimo e sem ação do administrador, a rodada continua em `interesse` indefinidamente.
- **Cenário 104:** R$ 10,00, mínimo R$ 100,00, A com 8 reservados e C com 5 pendentes. O início é recusado com `minimo_nao_atingido`, e nada é gravado.
- **Exatamente no mínimo** (R$ 100,00 elegível com mínimo R$ 100,00): aceito.
- **Horário de verão e madrugada:** o prazo é somado em UTC. Um início às 23:30 de São Paulo termina às 23:30 do dia seguinte.
- **Início repetido:** a segunda chamada encontra a rodada em `fechamento` e recebe `fora_de_interesse`, sem novo ciclo.
- **Início em paralelo com uma redução que derruba o mínimo:** as duas se serializam pelo fornecedor.
  - Se a redução confirma antes, o início é recusado.
  - Se o início confirma antes, a redução acontece no fechamento, que aceita alterações (§7). A queda do mínimo não muda o prazo (cenário 5).
- **Início em paralelo com uma alteração de condição** (mínimo ou estoque): serializados pelo fornecedor (E03-02). A alteração que chega depois é recusada com `CondicoesCongeladas`.
- **Início em paralelo com uma alteração de preço:** serializados pela trava do produto. O mínimo é conferido com o preço confirmado.

## Dependências e decisões em aberto

- Depende de E01-03, E01-04, E03-02, E03-07 e E05-04.
- Sem decisões em aberto.
