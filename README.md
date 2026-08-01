# AI Email Automation Agent

Production-oriented email automation platform: Gmail/IMAP sync → AI classification
→ entity extraction → rule engine → AI-drafted replies → human review → send, with
full audit logging. See `docs/architecture.md` for the full technical design
(architecture, schema, API, pipeline, rule engine, security, deployment, roadmap).

## What's implemented right now (Phases 0–6)

- **Monorepo scaffold**: `apps/api` (Go/Gin), `apps/ai-service` (Python/FastAPI),
  `apps/web` (Next.js), `deploy/` (Docker Compose).
- **Database**: full Postgres schema (all tables from the design doc) as a runnable
  migration, applied by a small dependency-free `cmd/migrate` runner.
- **Go API**: Clean-Architecture layout (`domain` → `usecase` → `ports` ← `adapters`),
  JWT auth, tenant + RBAC, mailbox CRUD (IMAP + Gmail OAuth), structured `slog`
  logging, graceful shutdown, RabbitMQ topology auto-provisioned on boot (7 pipeline
  stages + DLQs), append-only audit log.
- **Gmail integration**: OAuth2 flow over raw `net/http` (no heavy Google SDK),
  AES-256-GCM token encryption at rest, REST client (profile/history/messages/send)
  with unit-tested MIME parsing, and a real sync worker.
- **Full AI pipeline, wired end to end and running**: classify → extract → rules →
  draft → review → send, each as its own idempotent RabbitMQ consumer
  (`internal/workers/{classify,extract,rule,draft,send}worker`), calling the real
  Python AI service via a Go HTTP client adapter (`internal/adapters/aiservice`).
- **Rule engine, now live**: evaluates real messages via a `FieldResolver` over
  classification + entities + thread + mailbox context; executes label/route/
  create-task/generate-draft/auto-send/trigger-webhook/set-priority/set-sla/
  archive/escalate actions; rules CRUD API + `/rules/:id/test` dry-run endpoint.
- **Review queue**: list/get/edit/approve/reject/regenerate/send-now, all wired to
  real drafts with a version-guarded edit path and an audit trail.
- **Automation**: tasks (generic escape hatch for future CRM/Slack/ticketing),
  outbound webhooks (HMAC-signed, delivery history recorded), SLA polling worker
  (auto-escalates overdue threads), scheduled-follow-up polling worker, template
  CRUD with `{{variable}}` rendering.
- **Search & analytics**: full-text message search (Postgres GIN index), an
  analytics overview (volume/category/priority/avg response time), SLA compliance,
  and agent-performance (approval/edit/reject rate) endpoints.
- **AI service**: FastAPI with `/v1/classify`, `/v1/extract`, `/v1/draft`, provider
  abstraction over OpenAI/Anthropic, versioned prompts with prompt-injection
  guardrails, strict Pydantic validation, unit-tested with a fake provider.
- **Frontend**: Next.js + Tailwind + shadcn-style primitives. Login/register,
  mailbox management (list, connect IMAP, connect Gmail, sync now), review queue,
  rules (JSON condition/action editor), templates, and analytics are all wired to
  the real API — no placeholders.
- **Hardening**: retry-with-backoff (30s/2m/10m) before dead-lettering on every
  pipeline stage, Redis-backed rate limiting (auth + AI-cost endpoints,
  live-verified), Prometheus metrics on both the API and worker (`/metrics`,
  live-verified), real Gmail label application (list-or-create + messages.modify),
  attachments (Gmail download → object storage → list/download API, with a
  path-traversal-guarded local storage adapter swappable for S3/GCS), auto-drafted
  follow-up replies (not just a task), Gmail Pub/Sub push notifications with real
  RS256 JWT signature verification against Google's JWKS (tested with actual
  generated keys, not mocked), an SMTP sender for non-Gmail mailboxes, an
  RLS-hardening migration (shipped as clearly-documented *optional* — see below),
  and a full k8s manifest set (Deployments, HPA, KEDA queue-depth autoscaling,
  ingress).
- **Docker Compose**: full local stack, `worker` now runs all 6 queue consumers
  plus both polling workers.

Everything **builds and its tests pass** (`go build ./...`, `go test ./...`,
`go vet ./...`, `pytest`, `npm run build` all green — 12 Go packages with test
suites: rule engine, draft state machine, template rendering, Gmail MIME parsing,
AES-GCM round-trip, router registration, retry/backoff header logic, rate-limit
middleware, local object storage incl. a path-escape attack test, Google push JWT
verification with real generated RSA keys against a local JWKS server, and SMTP
delivery against a local fake SMTP server).

**Live-verified, not just compiled**: installed real Postgres/Redis/RabbitMQ in the
build sandbox plus a stub AI service, and drove a synthetic support email through
the *entire* pipeline — sync → classify (real 0.92-confidence "support" result) →
extract (real entity) → rules (matched, requested a draft) → draft (AI-generated
reply with template context) → review queue → approve+send-now → send (failed
gracefully on the expected "no Gmail credential" case, dead-lettered cleanly). Found
and fixed two real bugs this way (unsafe scanning of nullable `body_html`/`subject`/
`department` columns) that static checks alone would not have caught. Also
live-verified: rate limiting (11th login attempt in a minute correctly returned 429
with a real Redis TTL), `/metrics` returning real incremented Prometheus counters,
and the production Next.js build rendering actual page content against the live API.
All 7 k8s manifests validated for YAML correctness (no live cluster available in
this sandbox to `kubectl apply` against).

## Not yet implemented (see `docs/architecture.md` roadmap, and inline TODOs)

- **IMAP sync (read side)** — SMTP *sending* for non-Gmail mailboxes is implemented
  and tested (`internal/adapters/smtpsender`), but fetching mail via IMAP
  (FETCH/IDLE, folder/UID handling, MIME parsing parity with the Gmail adapter) is
  a substantially larger protocol surface that's intentionally left undone rather
  than shipped partially working. Gmail is the only provider that actually syncs
  mail today.
- **Full OpenTelemetry distributed tracing** — Prometheus metrics (throughput,
  per-stage latency, failure counts) are wired and live-verified, but there's no
  cross-service trace-span propagation; a deliberate scope trade-off given the
  added dependency weight full OTel would bring.
- **RLS enforcement wiring** — the policies exist as a migration
  (`migrations/optional/0002_rls.sql`) but aren't applied automatically and aren't
  connected to a per-request Postgres session variable; enabling them without that
  wiring would silently return zero rows from every query, so the migration is
  shipped separately with the exact wiring steps documented in its header comment
  rather than half-enabled.
- Rules page uses a JSON editor for conditions/actions rather than a visual
  drag-and-drop builder (same underlying data shape either way).
- IMAP mailbox SMTP credentials aren't modeled in the schema yet (only OAuth
  credentials for Gmail) — `smtpsender.Config` exists and is tested, but isn't
  wired into `sendworker` for IMAP-provider mailboxes until that credential
  storage is added.
- k8s: no migration Job manifest, NetworkPolicies, PodDisruptionBudgets, or service
  mesh — see `deploy/k8s/README.md`'s "Not included" section.
- Secrets-manager integration (Vault/AWS Secrets Manager sync) — k8s manifests
  document the expected secret keys but don't automate syncing them.
- Chaos testing.

## Running locally

```bash
cp deploy/env/.env.example deploy/env/.env.example   # edit in place: set JWT_SECRET, OPENAI_API_KEY, etc.
make dev                                              # docker compose up --build
```

This starts Postgres/Redis/RabbitMQ, runs migrations once, then boots the Go API
(`:8080`), the idle worker, the AI service (`:8000`), and the web app (`:3000`).

- API: `http://localhost:8080/api/v1` (health at `/healthz`, readiness at `/readyz`)
- AI service docs: `http://localhost:8000/docs`
- Web app: `http://localhost:3000`
- RabbitMQ management UI: `http://localhost:15672` (guest/guest)

### Running components individually (without Docker)

```bash
# Go API — requires local Postgres/Redis/RabbitMQ or the compose infra services
cd apps/api
go run ./cmd/migrate ./migrations
go run ./cmd/api

# Python AI service
cd apps/ai-service
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/uvicorn app.main:app --reload

# Web
cd apps/web
npm install
npm run dev
```

### Tests

```bash
make test   # go test ./... (apps/api) + pytest (apps/ai-service)
```

## A note on `apps/api/go.mod`

This repo was scaffolded in a network-sandboxed build environment without access to
`proxy.golang.org`, so `go.mod` contains several `replace` directives pointing
`golang.org/x/*` and a couple of transitive/test-only dependencies at their GitHub
mirrors (plus one tiny local stub module, `apps/api/vendorstubs/rsc-pdf`, for a
docs-only dependency of a dependency that isn't reachable via vanity import
redirection). None of this is required on a normal machine with full internet
access — `go build`/`go test` work as-is via the replace directives, but feel free to
`GOPROXY=https://proxy.golang.org go mod tidy` to drop them if you'd rather have a
clean upstream `go.mod`.

## Design doc

The complete 10-section technical design (architecture, folder structure, DB schema,
REST API, pipeline, agent workflow, rule engine, security model, deployment
architecture, and phase-by-phase roadmap) lives in `docs/architecture.md`.
# AI-Email-Agent
