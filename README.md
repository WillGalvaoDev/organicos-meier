# Orgânicos Méier

**English** · [Português](README.pt-BR.md)

An invite-only group-buying platform for organic produce. Buyers register interest in each supplier's round; the round closes, orders are frozen and charged, and the products are picked up at a single address. Built for a real operation (about 100 buyers, 50 suppliers and one administrator) and as a portfolio project.

---

## Part 1 — Current status

<!-- STATUS:BEGIN — update on every merge into main (AGENTS.md §10) -->

| | |
|---|---|
| **Last updated** | 2026-10-29, with PR #81 (E09) |
| **Phase** | Phase 1: complete platform running against a payment **simulator**. No real money and no production deployment yet. |
| **Progress** | 9 of 16 stages delivered (E01–E09), 65 slices, each approved by an independent review |
| **Last stage delivered** | E09 — Ledger, reserve and reconciliation (PR #81) |
| **Next stage** | E10 — Refunds (not started) |
| **Test suite** | 2,433 tests passing; ruff, mypy (strict) and migration checks clean; CI green on `main` |
| **Open blockers** | None |
| **Non-blocking improvements** | 8 open (1 closed) recorded in [`docs/melhorias.md`](docs/melhorias.md), reviewed at the end of Phase 1 |

**Works today (with the simulator):**

- Invitations, sign-up, sign-in (password, email link, Google), admin passkeys, moderation and bans.
- Suppliers, catalog, rounds with minimums, fractional quantities and stock.
- Notifications on the site and by email, with a queue and retries.
- Buyer interests and reservations without overselling, and the waiting queue.
- Round closing: a 24-hour deadline, extensions and removal of surplus.
- Payment provider interface and a deterministic simulator. It produces delays, duplicates and failures, and webhooks are idempotent.
- Payment opening with frozen orders, Pix charges and the `T0`/`T0 + 24h`/`T0 + 48h` timeline. Late or duplicate payments go to refund, and a lost-response recovery cancels charges left without an attempt.
- Double-entry ledger with immutable movements segregated by destination (custody, supplier obligation, freight, service revenue, reserve), the administrator's reserve with its coverage, buyer obligations, the financial invariant checked every 10 minutes and the daily reconciliation against the provider, with alerts.

**Not built yet:** refunds (E10), final settlement and the pending queue (E11), round cancellation (E12), the formal order and supplier payout (E13), pickup and delivery issues (E14), the admin dashboard and alerts (E15), and homologation (E16). Real Pix (Phase 2a), cards (Phase 2b) and WhatsApp (Phase 3) come after Phase 1.

| Stage | Scope | Status |
|---|---|---|
| E01 | Engineering foundation | ✅ Delivered |
| E02 | Identity, invitations and access | ✅ Delivered |
| E03 | Suppliers, catalog and round conditions | ✅ Delivered |
| E04 | Notifications and announcements | ✅ Delivered |
| E05 | Interests, reservations and progress | ✅ Delivered |
| E06 | Closing and boxes | ✅ Delivered |
| E07 | Payment simulator and integration | ✅ Delivered |
| E08 | Charging: opening, frozen orders and deadlines | ✅ Delivered |
| E09 | Ledger, reserve and reconciliation | ✅ Delivered |
| E10 | Refunds | ⏳ Next |
| E11 | Final settlement and pending queue | — |
| E12 | Round cancellation | — |
| E13 | Formal order, payout and supplier portal | — |
| E14 | Receiving, delivery issues, pickup and disposal | — |
| E15 | Admin dashboard and operational alerts | — |
| E16 | Homologation and Phase 1 closing | — |

<!-- STATUS:END -->

---

## Part 2 — Technical overview

### What makes this project interesting

The domain is small, but the money rules are strict. The platform takes payments from many buyers, keeps them apart by purpose (the supplier's goods, the service fee, the freight and the reserve) and must never lose, double-count or refund twice. Most of the engineering effort goes into **correctness under concurrency and failure**.

- **Exact money.** Every amount is `Decimal`, and each subtotal is rounded once with `ROUND_HALF_UP`. A static check fails the build if `float` appears in money code. Freight is split by the largest-remainder method with a deterministic tie-break.
- **Immutable records.** Frozen orders, items and audit entries can only be inserted: the ORM refuses updates and deletes. For frozen orders, PostgreSQL triggers block them as well.
- **Concurrency as a requirement.** Critical operations are transactional and take row locks (`SELECT … FOR UPDATE`) in a documented global order. Races in stock, queues, orders and payments are tested with real parallel transactions against PostgreSQL. Deadlocks found in review are reproduced first and then fixed.
- **Time boundaries.** Payment deadlines (`T0 + 24h`, `T0 + 48h`) are inclusive and decided on the server, never by the order in which webhooks arrive. Tests run on a controlled clock.
- **The provider is the source of truth.** Payments sit behind a replaceable `Provedor` interface. Webhooks only trigger a query to the provider. Outgoing calls are stored in a table and retried with backoff, under idempotency keys. Before an irreversible decision, the system queries the provider again. A lost response is recovered by searching the provider for the order's reference, so a charge is never created twice.
- **Deterministic simulator.** In Phase 1 the only provider is a simulator with its own database alias. It reproduces delayed, repeated and out-of-order webhooks, approvals at the exact boundaries, duplicate payments and API outages. The application refuses to start in production with the simulator enabled.

### How it is developed

The project follows a written contract ([`AGENTS.md`](AGENTS.md)) with **mandatory Test-Driven Development** and three separate roles, played by AI coding agents under a human project owner:

1. **Specifier.** Splits each stage into small vertical slices. For each slice it writes `spec.md` (rules, states, errors, permissions, invariants, edge cases) and `acceptance.md` (testable scenarios, including negative and concurrency cases), traced to the source documents.
2. **Implementer.** Writes each test first and records the failure for the expected reason (Red). Then writes the minimum code (Green) and refactors. It keeps evidence of every cycle.
3. **Independent reviewer.** Checks each criterion against the code and tests and runs its own probes and mutations. It also checks the Red-before-Green evidence, then approves or rejects. Passing tests alone never mean approval.

Business decisions belong only to the project owner. Ambiguities are escalated, not assumed. Every slice keeps its trail in [`docs/specs/<id>/`](docs/specs): the spec, the acceptance criteria and the review with its evidence. TDD deviations are recorded openly, never rewritten. Improvements that don't block a delivery go to a central log for a final review.

Source documents (Portuguese): [functional specification](organicos-meier-especificacao-funcional.md) v1.6 and [infrastructure and phases](organicos-meier-infraestrutura.md) v1.7.

**Repository rules:** `main` is protected. Every change goes through a pull request, and the CI job `verificacoes` must pass: `ruff check`, `ruff format --check`, `mypy` in strict mode and the full `pytest` suite against PostgreSQL 17.

### Technology

| Layer | In use | Planned |
|---|---|---|
| Language | Python 3.12, typed (mypy strict, django-stubs) | — |
| Web | Django 5.2, server-rendered templates | HTMX for partial updates |
| Auth | django-allauth: password, email link, Google, MFA, passkeys (WebAuthn), re-authentication for sensitive actions | — |
| Database | PostgreSQL 17 (Docker locally, service container in CI) | Neon Postgres, São Paulo region, with point-in-time recovery |
| Background jobs | Procrastinate: a Postgres-backed queue and periodic tasks, no Redis | — |
| Payments | Provider interface and deterministic simulator | Mercado Pago: Pix (Phase 2a), cards via Checkout Pro (Phase 2b) |
| Email | Django email backend through a queue with retries | Amazon SES |
| Hosting | — | Fly.io (São Paulo), separate web and worker instances; Cloudflare R2 for files and encrypted backups; Sentry |
| Messaging | Simulated external channel | WhatsApp Cloud API (Phase 3) |
| Testing | pytest, pytest-django, Hypothesis (property-based), factory-boy, time-machine, real-transaction concurrency helpers | — |
| Tooling | uv (locked dependencies), ruff, mypy, Docker Compose, GitHub Actions | — |

### Codebase layout

```
config/                     Django settings per environment (dev, test, prod), urls, wsgi
apps/nucleo/                technical core: money values, time, audit, insert-only records
apps/contas/                accounts, roles, invitations, sign-in, moderation and bans
apps/fornecedores/          suppliers
apps/catalogo/              products, units, increments and prices
apps/rodadas/               supplier rounds, stages, minimums and stock
apps/interesses/            buyer interests, reservations and the waiting queue
apps/notificacoes/          site notifications, email queue and announcements
apps/pagamentos/            provider interface, payment records, outgoing calls, webhooks
apps/simulador_pagamentos/  deterministic payment simulator (Phase 1 only)
apps/pedidos/               payment opening, frozen orders, charges, settlement and deadlines
apps/financeiro/            ledger, reserve, buyer obligations, invariant and reconciliation
templates/ static/          server-rendered pages
tests/aceitacao/            acceptance scenarios from the functional specification
tests/tecnicos/             technical tests (T-n), including concurrency
tests/apoio/                test-only app: clock, concurrency harness, factories and helpers
docs/specs/                 spec, acceptance criteria and review for every slice
docs/melhorias.md           non-blocking improvements, reviewed at the end of Phase 1
```

The code is about 16,000 lines of application Python and 35,000 lines of tests. The identifiers follow the Brazilian Portuguese domain language.

### Running locally

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker Desktop and Git.

```powershell
docker compose up -d db          # PostgreSQL 17 on localhost:5433
copy .env.example .env           # set SECRET_KEY
uv sync                          # creates .venv with app and test dependencies
uv run python manage.py migrate
uv run pytest                    # full suite
uv run ruff check . ; uv run ruff format --check . ; uv run mypy .
```

Background tasks (the email queue, payment calls, deadlines and margin re-queries) run in the Procrastinate worker:

```powershell
uv run python manage.py procrastinate worker
```

Without the worker, emails and provider calls stay pending, while the on-site notifications still work. In production, SMTP settings come from the environment (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`), with secrets in `fly secrets`.

> Local databases created before E02-01 or E03-01 must be recreated (`docker compose down -v`, `docker compose up -d db`, `uv run python manage.py migrate`), because those slices added required fields.

### Recorded technical exception

The initial scaffolding (configuration, database, tooling and documentation templates) has no business behavior, so it was created without a Red → Green cycle, as `AGENTS.md` §3 allows. Libraries such as django-allauth and Procrastinate enter `INSTALLED_APPS` only together with the slice that uses them, with tests written first. This way no route, such as a public sign-up, exists without a specification.
