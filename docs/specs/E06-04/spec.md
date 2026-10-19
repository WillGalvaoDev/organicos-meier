# E06-04 — Prorrogação do fechamento

Fatia 4 de 7 da milestone **E06 — Fechamento e caixas**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O administrador pode prorrogar o prazo do fechamento (§7, §13, cenário 28). Os documentos-base dizem que a prorrogação segue "as regras existentes", mas não definem quanto, quantas vezes nem até quando. Esta fatia fixa essas regras pela leitura mais estrita do texto, sem criar restrições comerciais novas, e entrega o serviço `prorrogar_fechamento`.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | "O administrador pode prorrogar o prazo de fechamento e os demais prazos conforme as regras existentes [...]. Toda intervenção deve ser auditada. Nenhuma intervenção pode reescrever pagamentos concluídos, apagar histórico ou cobrar valor adicional." Fechamento com prazo encerrado: "bloqueia alterações automaticamente, remove excedentes de caixas e verifica mínimo". |
| Especificação §7 | "Se o mínimo cair durante o fechamento, preservar o prazo original: aguardar até seu término." |
| Especificação §13 | Administrador: "prorrogação (exceto prazo de pagamento e margem operacional)". |
| Cenários §16 | 5 (a queda do mínimo não estende o relógio) e 28 ("Continua podendo prorrogar o fechamento conforme as regras existentes"). |
| Infraestrutura, tabela de conflitos | "Prorrogação: pagamento e margem improrrogáveis. Fechamento e demais prazos seguem as regras existentes." |
| E01-03 | Instantes com fuso; `prazo_encerrado` com limite exclusivo. |
| E06-01 | `PrazoDoFechamento`, com a linha `prorrogacao`; prazo vigente igual ao maior `termina_em` do ciclo. |

## Escopo

**Dentro:**

- O serviço `prorrogar_fechamento` e os códigos novos de `TransicaoRecusada`.

**Fora:**

- O formulário e o botão (E06-07).
- O aviso aos compradores: a §12 não define evento de prorrogação (E06-02). O prazo novo aparece no carrinho (E06-07).
- A prorrogação dos prazos de pagamento e de margem, que é proibida (P-7). Ela é tratada na E08, que cria esses prazos.

## Decisões técnicas

Cada regra abaixo decorre do texto dos documentos-base.

- **Prorrogar só estende.** "Prorrogar" é adiar o fim do prazo. Um prazo novo igual ou anterior ao vigente é recusado. Não existe encurtamento.
- **Só antes do fim do prazo.** Quando o prazo termina, a rodada "bloqueia alterações automaticamente, remove excedentes de caixas e verifica mínimo" (§7). Prorrogar depois disso exigiria desfazer a remoção dos excedentes e reabrir alterações, o que nenhum documento autoriza. Por isso, a prorrogação exige:
  - a rodada em `fechamento`;
  - `agora()` antes do prazo vigente, mesmo que a tarefa de encerramento ainda não tenha rodado (E06-03).
- **Sem limite de vezes nem de duração.** Os documentos-base não limitam, e um limite seria regra comercial nova. Cada prorrogação é auditada e grava uma linha nova de prazo, então o histórico completo fica preservado.
- **Instante informado pelo administrador.** O serviço recebe o novo fim como instante com fuso (`datetime` aware). Um `datetime` sem fuso levanta `InstanteSemFuso` (E01-03): é erro de programação. A tela da E06-07 converte o horário de São Paulo digitado.
- **A queda do mínimo não prorroga** (§7, cenário 5). Nada no sistema prorroga sozinho: só a ação do administrador.

## Regras

**Serviço** (`apps/rodadas/fechamento.py`):

```
prorrogar_fechamento(autor, rodada, novo_termino) -> datetime
```

Numa única `transaction.atomic()`:

1. Exige o administrador. Caso contrário, `PermissionDenied`.
2. Trava o fornecedor e a rodada, nessa ordem (E03-02), e relê a rodada.
3. Com a rodada informada diferente da ativa do fornecedor, ou fora de `fechamento`, levanta `TransicaoRecusada("fora_de_fechamento")`.
4. Lê o prazo vigente. Com `prazo_encerrado(agora(), prazo)`, levanta `TransicaoRecusada("prazo_encerrado")`.
5. Com `novo_termino <= prazo`, levanta `TransicaoRecusada("prazo_nao_posterior")`.
6. Cria `PrazoDoFechamento(origem="prorrogacao", termina_em=novo_termino, autor=autor)` no ciclo vigente.
7. Audita `rodada.prorrogar_fechamento`, com objeto igual à rodada e com `rodada`, `ciclo`, `anterior` e `novo` (ISO 8601 em UTC).
8. Devolve o novo prazo.

**Mensagens novas de `TransicaoRecusada`:**

| Código | Mensagem |
|---|---|
| `fora_de_fechamento` | "Só um fechamento em andamento pode ser prorrogado." |
| `prazo_encerrado` | "O prazo deste fechamento já terminou e não pode mais ser prorrogado." |
| `prazo_nao_posterior` | "O novo prazo precisa ser posterior ao prazo atual, <data> às <hora>." |

`<data>` e `<hora>` saem do prazo vigente em America/Sao_Paulo, nos formatos `%d/%m/%Y` e `%H:%M`.

**Efeito:** `prazo_do_fechamento` passa a devolver o novo instante. A partir daí, valem para ele:

- o bloqueio das ações (E06-03);
- o encerramento pela tarefa (E06-05).

**O que não muda:** o ciclo, as condições congeladas, as parcelas e os avisos já emitidos.

## Interfaces

- `apps/rodadas/fechamento.py`: `prorrogar_fechamento` e os três códigos.

## Invariantes

- O prazo vigente de um ciclo só cresce.
- Nenhuma prorrogação é aceita a partir do instante do prazo vigente.
- Toda prorrogação tem uma linha de prazo e uma auditoria, na mesma transação.

## Casos-limite e concorrência

- **Fronteira:**
  - aceita em `prazo − 1 ms`;
  - recusada em `prazo` e em `prazo + 1 ms`, mesmo com a etapa ainda `fechamento`.
- **Prorrogações sucessivas:** de 24 h para 48 h e depois para 72 h. O prazo vigente é o último, e há três linhas de prazo.
- **Prorrogação em paralelo com a tarefa de encerramento, perto do prazo:** as duas travam o fornecedor.
  - Se a prorrogação confirma antes, a tarefa relê o prazo novo e não encerra.
  - Se a tarefa confirma antes, a prorrogação encontra `fechamento_encerrado` e recebe `fora_de_fechamento`.
- **Duas prorrogações em paralelo:**
  - para o mesmo instante: a segunda recebe `prazo_nao_posterior`;
  - para instantes diferentes: vale a ordem de confirmação. A segunda só é aceita se for posterior à primeira.

## Correção E06-R03 — instantes da auditoria em UTC (2026-10-19)

### Diagnóstico

A regra 7 pede `anterior` e `novo` em ISO 8601 em UTC. O serviço grava `novo_termino.isoformat()` com o fuso recebido. Com `2026-11-04T01:30:00-03:00`, a auditoria guarda esse texto, e não `2026-11-04T04:30:00+00:00`. O instante é o mesmo e o prazo gravado no banco está certo; o desvio é só na representação do registro auditável. `anterior` sai do banco e já vem em UTC.

### Regra

- `anterior` e `novo` são gravados como `instante.astimezone(UTC).isoformat()`, no formato `AAAA-MM-DDTHH:MM:SS+00:00` (com `.ffffff` só quando houver microssegundos).
- A normalização vale para qualquer fuso recebido. O valor devolvido pelo serviço e a linha de prazo gravada não mudam: continuam sendo o mesmo instante.
- A auditoria `rodada.iniciar_fechamento` (E06-01) já grava `termina_em` a partir do valor calculado em UTC e não muda.

### TDD

O critério A-12 segue Red → Green → Refactor. A prova `test_prorrogacao_audita_utc` do revisor de `2fbf143` é o Red esperado no código atual e entra literalmente nos testes.

## Dependências e decisões em aberto

- Depende de E01-03, E03-02, E06-01 e E06-03.
- Sem decisões em aberto. As regras de "só estende", "só antes do fim" e "sem limite" são decisões técnicas derivadas dos documentos-base e podem ser revistas pelo responsável.
