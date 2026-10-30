# Orgânicos Méier

[English](README.md) · **Português**

Plataforma de compras coletivas de produtos orgânicos, com acesso por convite. Os compradores registram interesse na rodada de cada fornecedor. A rodada fecha, os pedidos são congelados e cobrados, e os produtos são retirados num único endereço. Feita para uma operação real (cerca de 100 compradores, 50 fornecedores e um administrador) e também como projeto de portfólio.

---

## Parte 1 — Estado atual

<!-- ESTADO:INICIO — atualizar a cada merge na main (AGENTS.md §10) -->

| | |
|---|---|
| **Última atualização** | 2026-10-30, com o PR #83 (E10) |
| **Fase** | Fase 1: plataforma completa rodando contra um **simulador** de pagamentos. Ainda sem dinheiro real e sem implantação em produção. |
| **Progresso** | 10 de 16 etapas entregues (E01–E10), 72 fatias, cada uma aprovada por revisão independente |
| **Última etapa entregue** | E10 — Devoluções (PR #83) |
| **Próxima etapa** | E11 — Apuração final e fila de pendentes (não iniciada) |
| **Suíte de testes** | 2.644 testes passando; ruff, mypy (estrito) e verificação de migrações limpos; CI verde na `main` |
| **Bloqueadores abertos** | Nenhum |
| **Melhorias não impeditivas** | 8 abertas (1 encerrada) registradas em [`docs/melhorias.md`](docs/melhorias.md), revistas no fim da fase 1 |

**Funciona hoje (com o simulador):**

- Convites, cadastro, login (senha, link por e-mail, Google), passkeys do administrador, moderação e banimento.
- Fornecedores, catálogo, rodadas com mínimo, quantidades fracionárias e estoque.
- Notificações no site e por e-mail, com fila e novas tentativas.
- Interesses e reservas dos compradores sem sobrevenda, e a fila de pendentes.
- Fechamento da rodada: prazo de 24h, prorrogação e remoção de excedentes.
- Interface do provedor de pagamentos e simulador determinístico. Ele reproduz atrasos, duplicidade e falhas, e os avisos (webhooks) são idempotentes.
- Abertura do pagamento com pedidos congelados, cobrança Pix e a linha do tempo `T0`/`T0 + 24h`/`T0 + 48h`. Pagamentos tardios ou duplicados vão para devolução, e a recuperação de resposta perdida cancela cobranças que ficaram sem tentativa.
- Livro-razão de partidas dobradas, com movimentos imutáveis e segregados por destinação (custódia, obrigação com o fornecedor, frete, receita do serviço, reserva), a reserva do administrador e suas coberturas, as obrigações com compradores, o invariante financeiro verificado a cada 10 minutos e a conciliação diária com o provedor, com alertas.
- Devoluções: reembolso parcial proporcional por item, serviço e frete, e devolução integral do pedido; estornos pelo provedor simulado com idempotência, nova tentativa segura e tratamento da conclusão tardia; conciliação dos estornos; devolução excepcional confirmada pelo administrador com comprovante; avisos de estorno e as telas do administrador e do comprador. O simulador também reproduz estornos e contestações.

**Ainda não construído:** a apuração final e a fila de pendentes (E11), o cancelamento da rodada (E12), o pedido formal e o repasse ao fornecedor (E13), a retirada e as ocorrências de entrega (E14), o painel administrativo e os alertas (E15) e a homologação (E16). Pix real (fase 2a), cartões (fase 2b) e WhatsApp (fase 3) vêm depois da fase 1.

| Etapa | Escopo | Estado |
|---|---|---|
| E01 | Fundação de engenharia | ✅ Entregue |
| E02 | Identidade, convites e acesso | ✅ Entregue |
| E03 | Fornecedores, catálogo e condições da rodada | ✅ Entregue |
| E04 | Notificações e comunicados | ✅ Entregue |
| E05 | Interesses, reservas e progresso | ✅ Entregue |
| E06 | Fechamento e caixas | ✅ Entregue |
| E07 | Simulador de pagamentos e integração | ✅ Entregue |
| E08 | Cobrança: abertura, congelamento e prazos | ✅ Entregue |
| E09 | Livro-razão, reserva e conciliação | ✅ Entregue |
| E10 | Devoluções | ✅ Entregue |
| E11 | Apuração final e fila de pendentes | ⏳ Próxima |
| E12 | Cancelamento da rodada | — |
| E13 | Pedido formal, repasse e portal do fornecedor | — |
| E14 | Recebimento, ocorrências, retirada e descarte | — |
| E15 | Painel administrativo e alertas operacionais | — |
| E16 | Homologação e encerramento da fase 1 | — |

<!-- ESTADO:FIM -->

---

## Parte 2 — Visão técnica

### O que torna o projeto interessante

O domínio é pequeno, mas as regras de dinheiro são rígidas. A plataforma recebe pagamentos de muitos compradores e os separa por destinação (mercadoria do fornecedor, taxa de serviço, frete e reserva). Ela nunca pode perder, contar em dobro ou devolver duas vezes. A maior parte do esforço de engenharia está na **correção sob concorrência e falhas**.

- **Dinheiro exato.** Todo valor é `Decimal`, e cada subtotal é arredondado uma única vez com `ROUND_HALF_UP`. Uma verificação estática reprova o build se aparecer `float` no código de valores. O frete é rateado pelo maior resto, com desempate determinístico.
- **Registros imutáveis.** Pedidos congelados, itens e auditoria só aceitam inserção: o ORM recusa alteração e exclusão. Nos pedidos congelados, triggers do PostgreSQL também bloqueiam essas operações.
- **Concorrência como requisito.** As operações críticas são transacionais e travam linhas (`SELECT … FOR UPDATE`) numa ordem global documentada. Corridas em estoque, fila, pedidos e pagamentos são testadas com transações paralelas reais no PostgreSQL. Impasses encontrados na revisão são primeiro reproduzidos e só depois corrigidos.
- **Fronteiras de tempo.** Os prazos de pagamento (`T0 + 24h`, `T0 + 48h`) são inclusivos e decididos no servidor, nunca pela ordem de chegada dos webhooks. Os testes rodam com relógio controlado.
- **O provedor é a fonte da verdade.** Os pagamentos ficam atrás de uma interface `Provedor` substituível. Um aviso (webhook) só dispara uma consulta ao provedor. As chamadas de saída ficam numa tabela e são repetidas com intervalo crescente, sob chaves de idempotência. Antes de uma decisão irreversível, o sistema consulta o provedor de novo. Uma resposta perdida é recuperada com uma busca no provedor pela referência do pedido, e a cobrança nunca é criada duas vezes.
- **Simulador determinístico.** Na fase 1, o único provedor é um simulador com banco próprio. Ele reproduz webhooks atrasados, repetidos e fora de ordem, aprovações exatamente nas fronteiras, pagamentos duplicados e API fora do ar. A aplicação se recusa a iniciar em produção com o simulador habilitado.

### Como é desenvolvido

O projeto segue um contrato escrito ([`AGENTS.md`](AGENTS.md)), com **Test-Driven Development obrigatório** e três papéis separados, exercidos por agentes de IA sob um responsável humano pelo projeto:

1. **Especificador.** Divide cada etapa em fatias verticais pequenas. Para cada fatia, escreve o `spec.md` (regras, estados, erros, permissões, invariantes, casos-limite) e o `acceptance.md` (cenários testáveis, inclusive negativos e de concorrência), com rastreabilidade aos documentos-base.
2. **Implementador.** Escreve cada teste antes e registra a falha pelo motivo esperado (Red). Depois escreve o mínimo de código (Green) e refatora. Guarda a evidência de cada ciclo.
3. **Revisor independente.** Confere cada critério contra o código e os testes e roda provas e mutações próprias. Também confere a evidência de Red antes do Green e então aprova ou reprova. Testes verdes, sozinhos, nunca significam aprovação.

As decisões de negócio cabem só ao responsável pelo projeto. Ambiguidades são escaladas, nunca presumidas. Cada fatia guarda a sua trilha em [`docs/specs/<id>/`](docs/specs): a especificação, os critérios de aceitação e a revisão com as evidências. Desvios de TDD são registrados abertamente, nunca reescritos. Melhorias que não impedem uma entrega vão para um registro central, revisto no fim.

Documentos-base: [especificação funcional](organicos-meier-especificacao-funcional.md) v1.6 e [infraestrutura e fases](organicos-meier-infraestrutura.md) v1.7.

**Regras do repositório:** a `main` é protegida. Toda mudança entra por pull request, e o job de CI `verificacoes` precisa passar: `ruff check`, `ruff format --check`, `mypy` em modo estrito e a suíte completa do `pytest` contra o PostgreSQL 17.

### Tecnologias

| Camada | Em uso | Planejado |
|---|---|---|
| Linguagem | Python 3.12, tipado (mypy estrito, django-stubs) | — |
| Web | Django 5.2, templates renderizados no servidor | HTMX para atualizações parciais |
| Autenticação | django-allauth: senha, link por e-mail, Google, MFA, passkeys (WebAuthn), nova autenticação antes de ações sensíveis | — |
| Banco | PostgreSQL 17 (Docker no ambiente local, contêiner de serviço no CI) | Neon Postgres, região São Paulo, com restauração a qualquer momento |
| Tarefas | Procrastinate: fila e tarefas periódicas dentro do Postgres, sem Redis | — |
| Pagamentos | Interface do provedor e simulador determinístico | Mercado Pago: Pix (fase 2a), cartões via Checkout Pro (fase 2b) |
| E-mail | Backend de e-mail do Django com fila e novas tentativas | Amazon SES |
| Hospedagem | — | Fly.io (São Paulo), instâncias separadas de web e worker; Cloudflare R2 para arquivos e backups criptografados; Sentry |
| Mensagens | Canal externo simulado | WhatsApp Cloud API (fase 3) |
| Testes | pytest, pytest-django, Hypothesis (testes baseados em propriedades), factory-boy, time-machine, utilitários de concorrência com transações reais | — |
| Ferramentas | uv (dependências travadas), ruff, mypy, Docker Compose, GitHub Actions | — |

### Organização do código

```
config/                     settings por ambiente (dev, test, prod), urls, wsgi
apps/nucleo/                núcleo técnico: valores, tempo, auditoria, registros só de inserção
apps/contas/                contas, papéis, convites, login, moderação e banimento
apps/fornecedores/          fornecedores
apps/catalogo/              produtos, unidades, incrementos e preços
apps/rodadas/               rodadas, etapas, mínimo e estoque
apps/interesses/            interesses, reservas e fila de pendentes
apps/notificacoes/          notificações no site, fila de e-mails e comunicados
apps/pagamentos/            interface do provedor, registro dos pagamentos, chamadas, avisos
apps/simulador_pagamentos/  simulador determinístico de pagamentos (só na fase 1)
apps/pedidos/               abertura do pagamento, pedidos congelados, cobrança, quitação e prazos
apps/financeiro/            livro-razão, reserva, obrigações com compradores, invariante e conciliação
templates/ static/          telas renderizadas no servidor
tests/aceitacao/            cenários de aceitação da especificação funcional
tests/tecnicos/             testes técnicos (T-n), inclusive de concorrência
tests/apoio/                app só de testes: relógio, concorrência, fábricas e utilitários
docs/specs/                 especificação, critérios de aceitação e revisão de cada fatia
docs/melhorias.md           melhorias não impeditivas, revistas no fim da fase 1
docs/referencias/           referências de apoio (padrões da API do Mercado Pago para o simulador)
```

O código tem cerca de 16 mil linhas de Python de aplicação e 35 mil de testes. Os nomes seguem a linguagem do domínio, em português.

### Ambiente de desenvolvimento

Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker Desktop e Git.

```powershell
docker compose up -d db          # PostgreSQL 17 em localhost:5433
copy .env.example .env           # ajuste SECRET_KEY
uv sync                          # cria .venv com dependências da aplicação e dos testes
uv run python manage.py migrate
uv run pytest                    # suíte completa
uv run ruff check . ; uv run ruff format --check . ; uv run mypy .
```

As tarefas em segundo plano (fila de e-mails, chamadas ao provedor, prazos e reconsulta da margem) rodam no *worker* do Procrastinate:

```powershell
uv run python manage.py procrastinate worker
```

Sem o *worker*, os e-mails e as chamadas ao provedor ficam pendentes, mas as notificações do site continuam funcionando. Em produção, o SMTP vem do ambiente (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`), com os segredos em `fly secrets`.

> Bancos locais criados antes da E02-01 ou da E03-01 precisam ser recriados (`docker compose down -v`, `docker compose up -d db`, `uv run python manage.py migrate`), porque essas fatias acrescentaram campos obrigatórios.

### Exceção técnica registrada

A estrutura inicial (configuração, banco, ferramentas e modelos de documentação) não tem comportamento de negócio. Por isso foi criada sem o ciclo Red → Green, como permite o `AGENTS.md` §3. Bibliotecas como django-allauth e Procrastinate só entram em `INSTALLED_APPS` junto com a fatia que as usa, com testes escritos antes. Assim nenhuma rota, como um cadastro público, existe sem especificação.
