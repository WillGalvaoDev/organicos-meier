# E06-02 — Aviso de início do fechamento

Fatia 2 de 7 da milestone **E06 — Fechamento e caixas**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Quando o fechamento começa, os compradores com interesse na rodada recebem o aviso `fechamento_iniciado` (E04-01), com fornecedor, etapa e prazo, sem pedido de confirmação (§12).

Esta fatia entrega:

- a emissão desse aviso dentro da transação de `iniciar_fechamento` (E06-01);
- o texto do aviso.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §12 | "Início do fechamento: fornecedor, etapa e prazo; não pedir confirmação de interesse." |
| Especificação §6.3 | No fim das 24 horas, as unidades que não completam caixa são removidas. |
| Especificação §15 | Datas exibidas no fuso da operação, America/Sao_Paulo. |
| E04-01 | `fechamento_iniciado`: destinatário comprador; canais site, e-mail e WhatsApp (este só com número e consentimento, E04-04). |
| E04-02 | `emitir_evento` e `emitir_evento_para_varios` na mesma transação do fato, com chave derivada do fato. |
| E05-R03 (E05-01) | A trava de conta é `FOR NO KEY UPDATE`. Quem grava notificação pede só `FOR KEY SHARE` na conta, o que é compatível com ela. |
| Milestone E06, herdado da E04 | Redigir título, corpo e link do aviso de `fechamento_iniciado`. |

## Escopo

**Dentro:**

- A emissão de `fechamento_iniciado` em `iniciar_fechamento`.
- O texto do aviso.

**Fora:**

- Avisos de prorrogação. A §12 não define esse evento, e "lembretes adicionais não foram definidos como regra obrigatória". O prazo novo aparece nas telas (E06-07).
- O envio por e-mail e WhatsApp, que é da E04-03 e da E04-04.

## Decisões técnicas

- **Destinatários:** os compradores com pelo menos uma parcela `ativa` com reserva maior que zero num produto do estoque da rodada, lidos depois da conferência do mínimo e antes do fim da transação.
  - É o mesmo conjunto que forma o valor elegível e as caixas (E05-04).
  - Quem só tem pendência não participa do ciclo (R-6) e não recebe o aviso.
- **Mesmo conteúdo para todos:** o aviso não depende do comprador. Por isso a emissão usa `emitir_evento_para_varios` (E04-02), com `chave_base = f"fechamento_iniciado:{ciclo.pk}"`. A chave de cada conta é `<chave_base>:<conta>`, gerada pela E04-02.
- **Sem confirmação:** o texto não pede resposta nem confirmação. Ele informa que alterações continuam permitidas até o prazo (§7).

## Regras

**Emissão** (`apps/rodadas/avisos.py`, chamada por `iniciar_fechamento` depois da auditoria do passo 6 da E06-01):

1. Lê os compradores destinatários por uma consulta agregada, ordenada por id da conta.
2. Sem destinatários, não emite nada.
3. Com destinatários, chama `emitir_evento_para_varios(Evento.FECHAMENTO_INICIADO, contas, titulo=..., corpo=..., link="/carrinho/", chave_base=...)`.
4. Uma falha na emissão desfaz o início do fechamento inteiro, porque é a mesma transação (E04-02).

**Texto:**

- `titulo`: `"Fechamento iniciado: " + fornecedor.nome`, cortado em 150 caracteres.
- `corpo`, em uma linha:

  ```
  A rodada de <fornecedor> entrou na etapa de fechamento. O prazo termina em <data> às <hora> (horário de Brasília). Até lá, você ainda pode alterar seus interesses, sem precisar confirmar nada. No fim do prazo, as unidades que não completarem caixa serão removidas.
  ```

  - `<data>` e `<hora>` saem de `no_fuso_da_operacao(termina_em)` (E01-03), nos formatos `%d/%m/%Y` e `%H:%M`, como nos convites (E02).
  - `<fornecedor>` é o nome do fornecedor. O corpo cabe em 2000 caracteres.
- `link`: `"/carrinho/"`.

## Interfaces

- `apps/rodadas/avisos.py`: `avisar_fechamento_iniciado(rodada, ciclo, termina_em)`.
- `apps/rodadas/fechamento.py`: a chamada dentro de `iniciar_fechamento`.

## Invariantes

- Cada início de fechamento gera no máximo um aviso por comprador destinatário.
- O aviso nasce e morre com o início do fechamento: a mesma transação.
- Nenhum aviso para conta de fornecedor, administrador ou comprador sem reserva na rodada.

## Casos-limite e concorrência

- **Comprador com várias parcelas e produtos:** recebe um aviso só.
- **Comprador suspenso:** não tem parcela `ativa`, porque a suspensão remove os interesses (E05-07), e não recebe o aviso.
- **Novo ciclo depois de um retorno ao interesse:** o ciclo novo tem outro id. Por isso a chave é outra, e os compradores recebem um aviso novo.
- **Início em paralelo com uma operação do comprador que segura a trava da conta:** a emissão pede só `FOR KEY SHARE` na conta, e as duas terminam (E05-R03).

## Dependências e decisões em aberto

- Depende de E04-01, E04-02, E04-04 e E06-01.
- Sem decisões em aberto.
