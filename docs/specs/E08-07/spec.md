# E08-07 — Tela do simulador de pagamentos

Fatia 7 de 7 da milestone **E08 — Cobrança: abertura, congelamento e prazos**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Na fase 1 não há dinheiro real. Em desenvolvimento e em homologação, alguém precisa fazer o papel de quem paga o Pix. Esta fatia entrega uma tela do administrador que opera o simulador: aprovar, recusar ou expirar uma cobrança e entregar os avisos pendentes.

A tela usa os mesmos controles dos testes (E07-01). Ela só existe com o simulador configurado.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 7, fase 1 | Plataforma completa com simulador, que reproduz aprovação, recusa, expiração, atrasos e duplicidade. |
| AGENTS.md §7 | É proibido iniciar a aplicação em produção com o simulador habilitado. |
| Herdado da E07 | Especificar a tela do simulador para desenvolvimento e homologação (aprovar, recusar, expirar e entregar avisos), visível só com o simulador ativo. |
| E07-01, E07-02, E07-05 | Controles do simulador, recusa em produção e `receber_aviso` como receptor padrão de `entregar_avisos`. |

## Escopo

**Dentro:**

- A página de cobranças simuladas.
- As três ações sobre uma cobrança.
- A entrega dos avisos pendentes.

**Fora:**

- O plano de falhas: indisponibilidade, falha nas próximas chamadas e atraso de consistência. Ele fica no processo e só os testes o usam (E07-01).
- O aviso repetido e a aprovação no cancelamento, que são controles só de teste.

## Decisões técnicas

- **Código dentro do simulador.** As views ficam em `apps/simulador_pagamentos/views.py`, e as rotas são incluídas em `config/urls.py`. Assim, a varredura do E07-01 A-16 continua valendo: em `apps/`, só a interface e o próprio simulador importam o simulador.
- **Só com o simulador configurado.** Com `PROVEDOR_PAGAMENTOS` diferente de `simulador`, as rotas respondem 404. Na fase 1, o único provedor aceito é o simulador, e a produção nunca sobe com ele (E07-02). Por isso, na prática, a tela só aparece em desenvolvimento, testes e homologação. A verificação garante que ela some quando a fase 2a trocar o provedor.
- **Só o administrador.** A tela usa `somente_administrador`. Na homologação, quem testa como comprador pede ao administrador que aprove.
- **Aprovar agora.** A tela aprova com o instante atual. Aprovações com horário escolhido ficam só nos testes.

## Regras

**Rotas** (`somente_administrador`; 404 sem o simulador configurado):

| Método e caminho | Nome | Ação |
|---|---|---|
| `GET /administracao/simulador-pagamentos/` | `simulador_pagamentos_lista` | a lista |
| `POST /administracao/simulador-pagamentos/<id_externo>/aprovar/` | `simulador_pagamentos_aprovar` | `controle.aprovar(id_externo)` |
| `POST /administracao/simulador-pagamentos/<id_externo>/recusar/` | `simulador_pagamentos_recusar` | `controle.recusar(id_externo)` |
| `POST /administracao/simulador-pagamentos/<id_externo>/expirar/` | `simulador_pagamentos_expirar` | `controle.expirar(id_externo)` |
| `POST /administracao/simulador-pagamentos/avisos/entregar/` | `simulador_pagamentos_entregar` | `controle.entregar_avisos()`, com o receptor padrão |

**Página da lista:**

- o título "Simulador de pagamentos" e o aviso "Ambiente de teste. Nenhum dinheiro real é movimentado.";
- as cobranças, da mais recente à mais antiga, com:
  - `id_externo` e referência;
  - valor em reais;
  - situação por extenso;
  - criada em, vence em e aprovada em, no fuso da operação;
- em cada cobrança, os botões permitidos na situação:
  - "Aprovar" em `pendente`, `cancelado` e `expirado` (E07-01);
  - "Recusar" e "Expirar" só em `pendente`;
- "Entregar avisos pendentes (<n>)", com a quantidade de `avisos_pendentes()`.

**Respostas das ações:**

| Caso | Resposta |
|---|---|
| sucesso | redireciona para a lista com "Cobrança <id_externo> aprovada." (ou "recusada.", "expirada.") |
| entrega de avisos | redireciona com "<n> aviso(s) entregue(s)." |
| `ValueError` do controle (situação que não permite a ação) | 409, com a lista e "A cobrança <id_externo> não pode ser <aprovada/recusada/expirada> na situação atual." |
| `PagamentoNaoEncontrado` | 404 |
| `GET` nas rotas de ação | 405 |

**Auditoria:** cada ação grava `simulador.<acao>` (autor), com o `id_externo` ou a quantidade de avisos. Nenhum dado pessoal.

## Interfaces

- `apps/simulador_pagamentos/views.py`, `urls.py` e o template.
- `config/urls.py`: a inclusão das rotas.

## Invariantes

- Sem o simulador configurado, nenhuma das rotas existe para o usuário (404).
- A tela não muda nada que os controles da E07-01 não mudariam.
- Os avisos entregues passam pelo mesmo caminho do provedor: verificação, registro e consulta (E07-05).

## Dependências e decisões em aberto

- Depende de E02-10, E07-01, E07-02, E07-05 e E08-03.
- Sem decisões em aberto.
