# Operations and failure handling

## Queue and retries

Messages are durably stored before processing. The worker processes `new`, `processing` and eligible `failed` records; a restart can resume a saved graph node. Postgres advisory locks serialize work on each message and each mailbox, including manual retry/review requests. Locks are held on a dedicated connection across service commits and are released on disconnect. SQLite's fallback locks are only process-local and are not suitable for deployed workers.

A processing failure stores its error type, increments attempts and schedules exponential backoff from `RETRY_BASE_SECONDS` to at most one hour. After `MAX_PROCESSING_ATTEMPTS`, it remains failed for inspection. Use the messages detail endpoint and audit history, fix the cause, then call `POST /messages/{id}/retry`. The endpoint resets attempts and retries synchronously. Gmail reads and idempotent updates have bounded retries; model clients also retry transient failures. OAuth exchange and draft creation/sending are not blindly retried.

Classification, extraction, rule plans and successful Gmail action application are persisted and reused during graph replay. Gmail label/star/archive operations are set operations and can safely be repeated if the remote call succeeded before a local commit failed. Audit flags avoid duplicates once the local transaction has committed. This is not a distributed exactly-once guarantee.

Initial sync exhausts all matching inbox pages before advancing its history cursor. The configured time window applies on first connection and expired-history fallback. No message-count cap silently discards the rest of that window. Mail arriving mid-sync is picked up from the pre-list history cursor on a later cycle. This version only tracks new inbox arrivals, not every later Gmail label change.

## Draft approval and uncertain outcomes

Draft generation saves an intent record before calling Gmail. A replay finds that record and does not create another draft. Creating/updating/sending states left by a crash and `*_unknown` states require operator review. The API reports these states in the response body; HTTP 200 does not mean an uncertain send succeeded. Poll/read the draft record and inspect its status.

Edits and regeneration invalidate approval. Approve the exact returned version, then explicitly call send with the new version. Sending supplies the approved raw MIME content to Gmail rather than trusting edits made in Gmail's UI after approval. No sorting rule or worker can send automatically. Rejection does not delete the remote draft, so the owner can still act on it directly in Gmail.

For an uncertain creation/update, locate the corresponding draft in the connected Gmail account and call `/drafts/{id}/reconcile` with `version` and `gmail_draft_id`. The service verifies the thread and restores local content using an idempotent update, returning the draft to pending approval.

For an uncertain send, inspect Gmail Sent. If it succeeded, provide `version` and `gmail_message_id`. The service verifies the SENT label, thread and deterministic Message-ID for that draft/version. It then records the send without sending again. If delivery cannot be proven, the draft stays blocked: this version deliberately has no force-resend endpoint. Manual Gmail action may be needed after investigating. Never retry an uncertain send automatically.

## Checks and observability

Health checks report process and database readiness. `/api/v1/metrics` exposes durable message/draft status gauges and requires the API key; configure Prometheus to send that header. `/analytics` includes latest-classification category counts. These are basic operational counts, not latency/SLA dashboards. Worker logs contain record IDs and error types, not email bodies. Add a proxy/global rate limiter before running multiple API processes.

Migrations run before both services. `python -m app.graph.checkpointer` initializes LangGraph's tables once in the migration job, avoiding simultaneous API/worker setup races. Back up Postgres and the encryption key separately. Do not use `docker compose down -v` if you intend to retain mail, rules and approvals.

## Verification status

Unit/service checks can use SQLite and fake Gmail/model clients. The full suite also tests actual LangGraph interrupt/resume behavior and, when `TEST_POSTGRES_URL` is set, a real Postgres checkpoint resumed through a new connection. The latter needs the LangGraph, psycopg and modern Alembic packages. Local package-index access was unavailable during implementation, so those checks and live provider tests must run in CI or a properly installed local environment before deployment.
