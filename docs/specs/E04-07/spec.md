# E04-07 — Consulta administrativa dos envios e falhas

Fatia 7 de 7 da milestone **E04 — Notificações e comunicados**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Os envios e as tentativas ficam gravados (E04-02 a E04-05), mas o administrador ainda não tem onde vê-los. Esta fatia entrega a consulta, só de leitura, dos envios, das tentativas e das falhas. É a base que a E15 usa nos alertas de falhas de comunicação.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §12, Requisitos derivados | Registrar envio e falhas. |
| Especificação §13, Administrador | Falhas de comunicação; histórico de ações relevantes. |
| Especificação §14 | Notificação e comunicado: destinatários, canais, conteúdo e resultado de entrega. |
| Especificação §15, Operação | Logs e alertas para falhas de comunicação. |
| Infraestrutura 9.2, L-13 | A aceitação pelo SES não garante entrega. |
| E02-03 | Área administrativa com passkey. |

## Escopo

**Dentro:**

- Lista `/administracao/envios/`, com filtros.
- Detalhe `/administracao/envios/<id>/`, com as tentativas.
- Indicador de falhas na página inicial da área administrativa.

**Fora:**

- Reenvio manual de notificação. A retentativa automática (E04-03) é o mecanismo exigido. Os e-mails de acesso se refazem pelo próprio fluxo (E04-05), e o pedido formal tem botão próprio (E13).
- Alertas ativos e painel consolidado (E15).
- Exportação.

## Regras

**Lista** (`GET /administracao/envios/`, `somente_administrador`):

- **Ordem e paginação:** do mais recente para o mais antigo (`criado_em`, depois `id`), 50 por página (`?pagina=`).
- **Filtros** por parâmetros de `GET`, combináveis:
  - `situacao` (`pendente`, `enviado`, `falhou`, `cancelado`);
  - `canal` (`email`, `whatsapp`);
  - `tipo` (os valores de `Evento` e os três tipos de acesso).

  Um valor fora da lista é ignorado: a página mostra o filtro como "todos", sem erro.
- **Colunas:**
  - criado em, no fuso da operação;
  - tipo, com o rótulo legível;
  - canal;
  - destinatário: o nome da conta ou, no convite, o e-mail de destino;
  - situação, com os rótulos "Pendente", "Aceito pelo serviço", "Falhou" e "Cancelado";
  - tentativas;
  - a classe do último erro, quando houver.
- **Rótulo de "enviado":** "Aceito pelo serviço" vale para os dois canais. A aceitação não comprova entrega (L-13, no e-mail; no WhatsApp simulado, por coerência).
- **Topo:** a contagem de envios com `falhou` e um link para o filtro `situacao=falhou`.

**Detalhe** (`GET /administracao/envios/<id>/`, `somente_administrador`):

- Os campos do envio:
  - `assunto` e `corpo`; nos e-mails de acesso, o corpo aparece como "(não armazenado: contém link de acesso)";
  - para o WhatsApp, o número de destino não aparece, porque não é gravado;
  - `motivo_cancelamento`, quando houver.
- A notificação ligada, quando existir: título, evento e se foi lida.
- As tentativas, em ordem: número, início, fim, resultado e classe do erro.
- Id inexistente: 404.

**Indicador:** a página inicial da área administrativa (E02-03) mostra "Envios com falha: <n>", com link para a lista filtrada, quando `n > 0`.

**Consultas:**

- A lista não cai em N+1: o número de consultas não cresce com os envios da página (ver o critério A-6).
- O detalhe faz um número fixo de consultas.

**Acesso:** comprador e fornecedor recebem 403; anônimo é redirecionado para `/entrar/`, conforme a E02-03 e a E02-10.

## Interfaces

- `apps/notificacoes/consultas.py`: `envios_para_administracao(filtros)` e `contar_falhas()`.
- Views, templates e rotas, com política declarada.

## Invariantes

- A consulta é só de leitura: nenhuma rota desta fatia aceita `POST`.
- Nenhum token, link com token ou corpo de e-mail de acesso aparece, porque não existe no banco (E04-05).

## Casos-limite e concorrência

- **Sem envios:** "Nenhum envio registrado.".
- **Filtros combinados sem resultado:** "Nenhum envio com estes filtros.", com os filtros mantidos.
- **Envio pendente agendado:** mostra "Próxima tentativa: <data e hora>".
- **Sem concorrência crítica:** só leitura.

## Dependências e decisões em aberto

- Depende de E02-03, E04-03, E04-04 e E04-05.
- Sem decisões em aberto.
