# Verification record — 2026-11-07

Passed locally:

- 39 tests across `test_api`, `test_automation`, `test_sync`, `test_gmail_client`, `test_gmail_contracts`, `test_security`, `test_parser`, `test_evals` and `test_recovery`.
- Python compilation of all application, migration, test and setup-script modules.
- OpenAPI schema generation (24 paths).
- Docker Compose configuration validation with no environment interpolation.
- Git whitespace check.

The tests exercised real SQLAlchemy/SQLite services and real FastAPI routing with fake Gmail/LLM integrations. They did not access a real mailbox or send mail. Available installed/cached packages supplied the offline verification environment (Python 3.12, SQLAlchemy 2.0.51, Pydantic 2.13.5). The project's full dependency installation was blocked by package-index DNS/network access.

HTTP tests needed a verification-only periodic asyncio timer because cross-thread event-loop wakeups timed out in this sandbox, including in a minimal asyncio reproducer with no application code. This workaround did not replace application behavior, assertions, or routing and is not included in production code.

Outstanding checks:

- Full LangGraph workflow tests, including persisted interrupt/resume and the new extraction/rules/draft graph path.
- Alembic migration/model comparison with a modern Alembic installation.
- Real Postgres integration test and advisory-lock behavior across processes.
- Ruff lint, dependency lock resolution, and Docker image build.
- Live Gmail OAuth, Gmail actions/drafts, LLM evaluation and an explicitly approved send to a controlled test recipient.

Run `make install`, `make lint`, and `make test` in an environment with package-index access. Set `TEST_POSTGRES_URL` to a disposable Postgres database to include the integration test. CI is configured to run the full test suite, lint and Postgres check; it has not been run from this workspace. The seed evaluation corpus is synthetic and does not establish inbox accuracy.

## Follow-up verification attempt

Re-ran the available suite after adding six Gmail contract/reconciliation tests: **39 passed in 3.06 seconds**. Shell syntax, Python compilation, both Compose configurations and Git whitespace checks passed.

Retried installing the complete dependency set; package-index DNS resolution still failed. Docker access returned permission denied for its Unix socket. A separately initialized disposable Postgres 18 instance also failed to start because this environment prohibits binding a Unix-domain socket. No project `.env`, Gmail OAuth credentials or provider API keys were present. These are blockers, not passing checks; no live email was sent.

Added `make verify`, backed by `scripts/verify_backend.sh` and `deploy/docker-compose.test.yml`. On a machine with Docker/package-network access it builds production and test images, starts a disposable Postgres/migration/API/worker stack, runs Ruff and the entire pytest suite, then makes read-only HTTP smoke requests against the real running API. Test credentials are disposable and the project `.env` is never loaded. The temporary Compose project is cleaned up on exit. CI includes this command as a separate Docker job.

A second PostgreSQL integration test checks that advisory locks survive service commits and exclude a separate Python process, then become available after release. This test and the disposable Docker verification runner are authored but have not executed here.

## Angular frontend and browser authentication

Added the Angular/TypeScript workspace and pinned npm lockfile. Production compilation and TypeScript checking passed. Six controller tests passed using real Angular injection/signals and fake API responses; these are not DOM or visual tests. The Python subset expanded to **47 passing tests**, including password hashing, credential validation, login throttling, session cookies, CSRF checks, expiry, credential rotation and logout revocation.

A local browser-preview attempt failed with `listen EPERM` at `127.0.0.1:4200`. No browser screenshot or browser end-to-end result is claimed. Migration 0003 adds `web_sessions`; its live PostgreSQL migration check remains blocked with the rest of that suite. Docker verification now includes the frontend image and a read-only Nginx app-shell/API-proxy smoke check; it has not run here.

## Grounded agent additions

Current local result: **67 Python tests passed** across the earlier offline suite plus agent safety/retrieval/budget tests and authenticated knowledge/preferences/timeline API tests. **9 Angular controller tests passed**; TypeScript checking and the production Angular build passed (308.06 kB initial raw bundle). The additional evaluation scorer was tested with explicit predictions; no live-model accuracy is claimed.

Added migration 0004, bounded tool orchestration, knowledge/preference CRUD, source-version invalidation, body-bound verification, execution records, three Angular pages and 14 synthetic live evaluation cases. The same dependency/network/socket constraints still prevent modern Alembic/Postgres/LangGraph integration checks, Ruff, Docker runtime checks and browser E2E/visual inspection. The complete CI suite and live Gmail/provider evaluation still need execution outside this environment.

Final follow-up checks include conservative estimated cost guards, missing-usage failure, interrupted-run recovery and approval revocation after a failed edited-draft verification. Human edits now receive their own timeline record. Python compilation, both Compose configurations, shell syntax and Git whitespace checks passed.
