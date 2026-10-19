# E06-06 — Verificação do mínimo e retorno para interesse

Fatia 6 de 7 da milestone **E06 — Fechamento e caixas**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Depois de remover os excedentes (E06-05), o encerramento verifica o mínimo com os valores que ficaram:

- **Atingido:** a rodada continua em `fechamento_encerrado` e aguarda a autorização do pagamento (E08).
- **Não atingido:** a rodada volta para interesse. As condições voltam a ser editáveis, a fila de pendentes é atendida com o estoque liberado, e os compradores são avisados.

Esta fatia entrega:

- a verificação dentro de `encerrar_fechamento`;
- o serviço `voltar_para_interesse`, que a E11 vai reutilizar com outro motivo;
- o aviso `retorno_para_interesse`;
- a troca de `simular_volta_para_interesse` (E03-07) pela transição real.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | Fechamento com prazo encerrado: "verifica mínimo. Se insuficiente, volta para interesse; se suficiente, aguarda autorização para pagamento." "O retorno por mínimo insuficiente é uma regra de falha, não uma autorização para nova cobrança." "Se o mínimo cair durante o fechamento, preservar o prazo original: aguardar até seu término." |
| Especificação §6.3 | Depois da remoção dos excedentes, "recalcular o mínimo". "Se o mínimo deixar de ser atendido, retornar para interesse conforme as regras da rodada." |
| Especificação §5.1 | "Se uma redução de preço derrubar o total elegível abaixo do mínimo ao término do fechamento, retornar para interesse." |
| Especificação §4.4 | Se a rodada voltar para interesse, as condições podem ser alteradas de novo, sem modificar os registros dos ciclos anteriores. |
| Especificação §5.2 | Os pendentes são atendidos "na abertura da fase de interesse e sempre que estoque é liberado". |
| Especificação §12 | "Retorno para interesse: motivo e situação de interesses e estornos." |
| Cenários §16 | 5 (a queda temporária do mínimo não muda o relógio), 9 e 73. |
| Infraestrutura 4.10 | Ciclos anteriores nunca são reescritos. Parcelas que entram num ciclo novo geram pedido novo (E08). |
| E03-07 | `simular_volta_para_interesse` é substituído pela transição real. |
| E04-01 | `retorno_para_interesse`: comprador, site e e-mail. Previsto também para a E11. |
| E05-02, E05-04 | `alocar_pendentes(fornecedor)` e `progresso_da_rodada(rodada).atingido`. |

## Escopo

**Dentro:**

- O passo 6 de `encerrar_fechamento` (E06-05).
- O serviço `voltar_para_interesse(rodada, *, motivo, destinatarios=None)` com o motivo `minimo_nao_atingido`.
- O aviso `retorno_para_interesse` desse motivo.
- A troca do auxiliar da E03-07.

**Fora:**

- O retorno por pagamentos insuficientes (§8.2, E11). A E11 acrescenta o próprio motivo, o tratamento de pedidos e estornos e o texto dela.
- A abertura do pagamento (E08).
- As telas (E06-07).

## Decisões técnicas

- **Mesmo número da cobrança.** A verificação usa `progresso_da_rodada(rodada).atingido`, lido depois da remoção dos excedentes, na mesma transação e com o preço vigente (E05-04). Uma redução de preço feita durante o fechamento entra no cálculo (§5.1).
- **Só no fim do prazo.** A verificação só acontece no encerramento. Uma queda do mínimo durante o fechamento não muda etapa nem prazo (§7, cenário 5).
- **O ciclo é histórico.** Voltar para interesse não apaga nem altera o ciclo, o prazo ou as condições registradas. O próximo início de fechamento registra um ciclo novo (E03-07).
- **Os interesses que sobraram continuam.** O retorno não remove nem reordena parcelas. As reservas mantidas no encerramento seguem na rodada, com a mesma sequência. A fila de pendentes é atendida em seguida, porque a fase de interesse recomeça e houve estoque liberado (§5.2).
- **Destinatários do aviso:** os compradores que tinham reserva na rodada no início do encerramento. `encerrar_fechamento` lê esse conjunto antes de remover os excedentes e o passa em `destinatarios`. Isso inclui quem perdeu toda a reserva para os excedentes: essa pessoa também participou do ciclo e precisa saber que a rodada recomeçou. Chamado sem `destinatarios`, o serviço usa os compradores com reserva no momento da chamada.
- **Sem estornos neste motivo.** No fechamento nada foi cobrado, e o aviso diz isso. A "situação de estornos" da §12 é "não há".
- **Sem o valor do mínimo no aviso.** O mínimo do fornecedor nunca é mostrado ao comprador (E03-08 e E05-05).

## Regras

**Passo 6 de `encerrar_fechamento`** (E06-05):

1. Antes da remoção dos excedentes (passo 3), lê os compradores com parcela `ativa` e reserva maior que zero nos produtos da rodada. Esse é o conjunto `participantes`.
2. Depois dos avisos de excedentes, calcula `progresso = progresso_da_rodada(rodada)`.
3. Com `progresso.atingido` falso, chama `voltar_para_interesse(rodada, motivo="minimo_nao_atingido", destinatarios=participantes)`, e `etapa_final` é `interesse`.
4. Com `progresso.atingido` verdadeiro, nada mais muda, e `etapa_final` é `fechamento_encerrado`.
5. A auditoria `rodada.encerrar_fechamento` (passo 4 da E06-05) passa a ser gravada depois desta verificação. Ela ganha os campos:
   - `valor_elegivel` e `minimo`, em texto decimal;
   - `resultado`: `aguardando_pagamento` ou `retorno_para_interesse`.

**Serviço** (`apps/rodadas/fechamento.py`):

```
voltar_para_interesse(rodada, *, motivo, destinatarios=None) -> None
```

1. Exige transação aberta (`TransactionManagementError`).
2. `motivo` precisa ser de `MOTIVOS_DE_RETORNO`, que nesta fatia contém só `minimo_nao_atingido`. Caso contrário, levanta `ValueError`.
3. Trava o fornecedor e a rodada, nessa ordem. É reentrante: dentro do encerramento, as travas já são da transação. Com a rodada fora de `fechamento_encerrado`, levanta `TransicaoRecusada("fora_de_fechamento_encerrado")`, com a mensagem "Só uma rodada com o fechamento encerrado pode voltar para interesse.".
4. Grava `etapa = interesse` (`update_fields`).
5. Audita `rodada.voltar_para_interesse`, com autor `SISTEMA`, objeto igual à rodada e com `rodada`, `ciclo` e `motivo`.
6. Chama `alocar_pendentes(fornecedor)` (E05-02).
7. Emite o aviso abaixo para os destinatários.

**Aviso** (`apps/rodadas/avisos.py`): o conteúdo é o mesmo para todos, então a emissão usa `emitir_evento_para_varios` (E04-02), com `chave_base = f"retorno_para_interesse:{ciclo.pk}"`.

- `titulo`: `"Rodada de volta ao interesse: " + fornecedor.nome`, cortado em 150 caracteres.
- `corpo`, em uma linha:

  ```
  A rodada de <fornecedor> voltou para a fase de interesse porque o mínimo do fornecedor não foi atingido no fim do fechamento. Os interesses que continuam reservados seguem na rodada, e você pode alterá-los. Nada foi cobrado neste ciclo, então não há estornos.
  ```

- `link`: `"/carrinho/"`.
- Sem destinatários, nada é emitido.

**Troca do auxiliar da E03-07** (`tests/apoio/ciclos.py`):

- `simular_volta_para_interesse(rodada)` passa a fazer, numa transação:
  1. `update(etapa=fechamento_encerrado)`, que representa o encerramento;
  2. a chamada de `voltar_para_interesse(rodada, motivo="minimo_nao_atingido")`.
- É o único ajuste autorizado nesse arquivo nesta fatia. As asserções de `tests/tecnicos/test_rodadas_ciclos.py` não mudam.

## Interfaces

- `apps/rodadas/fechamento.py`: o passo 6, `voltar_para_interesse`, `MOTIVOS_DE_RETORNO` e o código `fora_de_fechamento_encerrado`.
- `apps/rodadas/avisos.py`: `avisar_retorno_para_interesse`.
- `tests/apoio/ciclos.py`: o ajuste autorizado.

## Invariantes

- Nenhuma rodada fica em `fechamento_encerrado` com o mínimo não atingido depois do encerramento.
- Nenhuma rodada volta para interesse antes do fim do prazo pela regra do mínimo.
- O retorno não altera ciclo, prazo, condições registradas nem a sequência de nenhuma parcela.
- Total reservado ≤ estoque, também depois do atendimento da fila no retorno.

## Casos-limite e concorrência

- **Cenário 9, insuficiente:** mínimo R$ 150,00 e, depois dos excedentes, R$ 120,00 elegíveis. A rodada volta para interesse, e os participantes recebem o aviso.
- **Cenário 9, suficiente:** mínimo R$ 100,00 e R$ 120,00 elegíveis. A rodada fica em `fechamento_encerrado`, sem aviso de retorno.
- **Excedentes derrubam o mínimo:** antes do encerramento, o valor bruto passa do mínimo, mas o elegível não. A rodada volta para interesse, e o aviso vai também para quem perdeu tudo.
- **Preço reduzido no fechamento** (§5.1): a redução derruba o elegível abaixo do mínimo, e a rodada volta no fim do prazo, não antes.
- **Queda e recuperação** (cenário 5): o mínimo cai e volta durante o fechamento. A rodada fica em `fechamento_encerrado` no fim do prazo.
- **Cenário 73:** depois do retorno, `alterar_minimo` e `alterar_estoque` são aceitos, e o ciclo anterior continua com os valores originais.
- **Pendentes no retorno:** C tem 3 pendentes, e os excedentes liberaram estoque. C recebe a reserva na mesma transação do retorno.
- **Novo fechamento depois do retorno:** gera um ciclo novo, com número seguinte, novo prazo e novo aviso `fechamento_iniciado` (E06-02).

## Dependências e decisões em aberto

- Depende de E03-07, E04-01, E04-02, E05-02, E05-04 e E06-05.
- Sem decisões em aberto.
