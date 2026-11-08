# AI Email Agent — Python + Angular

Single-user Gmail automation built with FastAPI, LangGraph, SQLAlchemy and PostgreSQL. The Angular + TypeScript frontend lives in `apps/web`. It does not include Go, IMAP, RabbitMQ or Kubernetes.

## Browser app

The Angular app provides a password login, overview, messages, review queue, draft editor, rules, analytics, knowledge, preferences and agent execution history. See [docs/frontend.md](docs/frontend.md) for setup and session authentication.

```bash
.venv/bin/python scripts/setup_login.py
make migrate
make web-install
make web-dev
```

Open `http://localhost:4200` with the backend and worker running. `make up` also starts the frontend.

## Implemented

- Gmail OAuth with encrypted refresh tokens, expiring single-use state, and API-key authentication.
- Initial inbox sync covering all matching messages in the configured time window; incremental history sync with expired-history fallback.
- Durable database work queue with polling, Postgres operation locks, bounded retries, and manual retry.
- Structured classification into support, billing, sales, newsletter, personal, spam or other, with priority/confidence and versioned prompts.
- LangGraph review interrupts for low-confidence results, persisted human corrections, and Postgres checkpoints.
- Structured extraction of invoice numbers, dates, amounts, order IDs and requested actions.
- Rules CRUD and dry runs: label, archive, set priority, request a draft. Conditions use category, priority, sender, subject or extracted entities.
- Gmail labels, newsletter/spam archiving (never deletion), and high/urgent stars.
- Reply drafting with Gmail thread context and a configurable style template; edit, regenerate, approve, reject, explicit send and reconciliation endpoints.
- Optimistic draft versions, approval revoked on edits, and no automatic retry of ambiguous create/send calls.
- Audit records, status/category analytics, Prometheus status gauges, request throttling, configurable content retention, and opt-in LangSmith tracing.
- Docker Compose, Alembic migrations, unit/service tests, a PostgreSQL integration test and CI.
- Evaluation CLI with a 28-message synthetic seed dataset; see [evals/README.md](evals/README.md).

## Architecture

`api → services → repositories → models`; services call Gmail/LLM integrations. `container.py` wires dependencies. Graph nodes call services and checkpoint only IDs/status, not email bodies. PostgreSQL doubles as the durable work queue; Redis is not required at this scale.

| Directory | Responsibility |
| --- | --- |
| `app/api/` | HTTP routes, authentication, request validation |
| `app/services/` | Use cases, transaction boundaries, review and sending policy |
| `app/repositories/` | Database queries |
| `app/models/`, `app/schemas/` | ORM records and validated input/output types |
| `app/graph/` | Workflow topology, nodes and checkpoint lifecycle |
| `app/integrations/` | Gmail REST/OAuth/MIME and structured LLM calls |
| `app/workers/` | Polling, processing and retention command |
| `app/prompts/`, `app/evals/` | Versioned prompts and evaluation harness |
| `migrations/`, `deploy/`, `tests/` | Schema, deployment and checks |

Workflow: sync → classify → review when uncertain → extract → rules → Gmail actions → optional draft. Sending is a separate explicit API operation after approval; the sorting worker never sends mail.

## Start locally

Requirements: Python 3.12, uv, Docker Compose, a Google OAuth web client with Gmail API enabled, and an OpenAI or Anthropic key.

```bash
make install
.venv/bin/python scripts/init_env.py
# Edit .env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, provider API key.
# Read docs/privacy.md and set ALLOW_CLOUD_PROCESSING=true when ready.
docker compose -f deploy/docker-compose.yml up postgres -d
make migrate
make dev
# In a second terminal:
make worker
```

The API listens on `http://localhost:8080`; interactive API docs are at `/docs`. `scripts/init_env.py` generates fresh local secrets, uses file mode 0600, and refuses to overwrite an existing `.env`. Do not copy production tokens into development.

Register this Google OAuth redirect exactly:
`http://localhost:8080/api/v1/mailboxes/oauth/gmail/callback`.
Use your own Google account as a test user when the OAuth application is in test mode. The requested scope is `gmail.modify`, which is needed for labels, drafts and sending. Google consent/token restrictions still apply; reconnect if refresh access is revoked or expires.

### Connect and process

Set `API_KEY` in your shell to the value in `.env`. Call `GET /api/v1/mailboxes/connect/gmail` with `X-API-Key`, open the returned `auth_url` in your browser, and complete consent. The callback returns the mailbox ID. Then call `POST /api/v1/mailboxes/{id}/sync`, or wait for the worker. The sync endpoint queues work in Postgres; the worker must be running to process it.

### API routes

Protected routes accept `X-API-Key` for automation clients or a browser session with CSRF protection. Health/readiness and the signed OAuth callback remain public. See `docs/frontend.md` for the browser login/session/logout endpoints.

| Route | Purpose |
| --- | --- |
| `GET /api/v1/healthz`, `GET /api/v1/readyz` | Process health / database readiness |
| `GET /api/v1/mailboxes` | Connected accounts |
| `GET /api/v1/mailboxes/connect/gmail` | Start OAuth |
| `POST /api/v1/mailboxes/{id}/sync` | Fetch and persist new mail |
| `GET /api/v1/messages`, `GET /api/v1/messages/{id}` | Messages, extraction, action plan and audit history |
| `POST /api/v1/messages/{id}/retry` | Reset attempts and retry a failed/interrupted message |
| `GET /api/v1/review` | Pending classifications |
| `POST /api/v1/review/{id}/resolve` | Resume with `{ "category": "billing", "priority": "high" }` |
| `GET/POST /api/v1/rules` | List/create rules |
| `GET/PUT/DELETE /api/v1/rules/{id}` | Read/update/delete rule |
| `POST /api/v1/rules/{id}/test` | Side-effect-free test with `{ "message_id": 1 }` |
| `GET /api/v1/drafts`, `GET /api/v1/drafts/{id}` | Draft review queue/detail |
| `POST /api/v1/drafts/for-message/{id}` | Generate and save a Gmail draft |
| `PATCH /api/v1/drafts/{id}` | Edit `{ "version": 1, "body": "Revised text" }` |
| `POST /api/v1/drafts/{id}/regenerate` | Generate a replacement; revokes approval |
| `POST /api/v1/drafts/{id}/approve` | Approve current content |
| `POST /api/v1/drafts/{id}/reject` | Reject; Gmail draft remains available |
| `POST /api/v1/drafts/{id}/send` | Explicitly send approved content |
| `POST /api/v1/drafts/{id}/reconcile` | Resolve an uncertain remote result |
| `GET /api/v1/analytics`, `GET /api/v1/metrics` | Counts and Prometheus gauges |

Approve/reject/regenerate/send take `{ "version": N }`. Always use the version returned by the previous request. Edits and decisions advance the version. A stale version returns HTTP 409. Repeating a successful send returns the sent record without sending again.

Example rule:

```json
{
  "name": "Draft billing replies",
  "enabled": true,
  "position": 100,
  "definition": {
    "conditions": [
      {"field": "category", "op": "eq", "value": "billing"},
      {"field": "entities.invoice_numbers", "op": "exists"}
    ],
    "actions": [
      {"type": "label", "value": "AI/Invoice"},
      {"type": "set_priority", "value": "high"},
      {"type": "draft"}
    ]
  }
}
```

All conditions must match. Rules run in ascending position then ID. Labels accumulate; archive/draft flags are additive; the last matching priority action wins. A stored action plan is a snapshot: editing rules does not retroactively change already processed messages. Custom labels must start with `AI/`. There are no send, delete or arbitrary webhook actions.

## Deployment and operations

```bash
make up
# Scheduled maintenance (run daily through your scheduler):
docker compose -f deploy/docker-compose.yml --profile maintenance run --rm retention
```

Compose runs migrations and checkpoint setup before API/worker startup, binds development ports to localhost, and runs app containers as a non-root user. Use managed secrets, production Postgres credentials, TLS/reverse proxy, and `APP_ENV=production` for deployment. Production configuration rejects weak-length API/signing keys, SQLite, and HTTP OAuth redirects. Keep one API process for the built-in in-memory request limiter, or enforce a shared limit at the proxy. Checkpoints and locks require Postgres for multi-process deployment; SQLite is for tests only.

See [docs/operations.md](docs/operations.md) for retries, ambiguous send reconciliation and recovery, and [docs/privacy.md](docs/privacy.md) for storage/redaction/tracing policy.

## Checks and limitations

```bash
make test
make lint
make verify  # disposable Docker/Postgres stack, full suite + running API smoke checks
make eval  # live LLM calls; requires credentials and explicit cloud consent
# Optional disposable Postgres database for integration tests:
TEST_POSTGRES_URL=postgresql+psycopg://postgres:postgres@localhost:5432/emailagent_test make test
```

The PostgreSQL test uses a temporary schema and drops it afterward. CI provides a dedicated Postgres service. Live evaluation is optional and explicitly skipped if its provider secret is absent.

See [docs/verification.md](docs/verification.md) for the exact local checks and outstanding verification. The implementation has been service-tested offline; live Gmail/LLM behavior and the full LangGraph/Postgres suite require verification in an environment with all dependencies. No production accuracy claim is made. Dependencies have version constraints but no resolved lockfile yet; generate and commit a lockfile when package-index access is available.

Not included: autonomous sending, IMAP/SMTP, Pub/Sub push, multi-tenancy, attachment downloads, tasks/webhooks, SLA automation or Kubernetes. These remain outside the single-user Gmail backend scope. Spam classification only processes inbox mail; it does not scan the Gmail Spam folder or move messages into it.

## Grounded agent workflow

The Angular app now includes **Knowledge**, **Preferences** and **Agent activity**. Draft generation retrieves source excerpts, uses bounded read-only tool selection and independently verifies the reply. Draft review shows sources and findings. Failed verification, changed source documents or changed preferences block approval/sending until the draft is corrected or regenerated. Sending remains a separate human action.

Run `make migrate` for migration **0004**. See [docs/agent.md](docs/agent.md) for tool boundaries, configuration, API contracts, evaluation commands and remaining limits. `make eval-agent` runs labeled synthetic extraction/verification/tool-policy checks using the configured provider; it incurs live model calls.
