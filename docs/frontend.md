# Angular workspace

The TypeScript frontend lives in `apps/web` and uses Angular 22 standalone components, lazy routes, signals and typed HttpClient calls. The package lock is committed with pinned direct dependency versions. No API key, provider credential or refresh token is embedded in the browser build. The existing Python backend remains the AI service.

## Local setup

Use Node 22.22.3 or newer in the 22.x line (the local build used 22.23.3), or a supported newer Node version listed in `apps/web/package.json`.

First configure the backend:

```bash
make install
# Only if .env does not exist:
.venv/bin/python scripts/init_env.py
.venv/bin/python scripts/setup_login.py
# Set Google/LLM credentials and data-sharing choices in .env.
docker compose -f deploy/docker-compose.yml up postgres -d
make migrate
make dev
```

`make migrate` must apply migration 0003 for browser sessions. In two additional terminals:

```bash
make worker
```

```bash
make web-install
make web-dev
```

Open `http://localhost:4200` and sign in with the username/password you configured. The dev proxy forwards `/api/` to FastAPI at `127.0.0.1:8080`, so there is no cross-origin credential sharing or CORS setup. Keep `FRONTEND_ORIGIN=http://localhost:4200`. Use the exact hostname `localhost`, not `127.0.0.1`, in the browser unless you also update this setting.

## Docker

`make up` now includes the Angular frontend behind Nginx at `http://localhost:4200`. Nginx serves the static build, supports deep links and proxies `/api/` to FastAPI. It disables access logs to avoid logging OAuth authorization codes, sets security headers and does not expose any environment file to the browser.

For deployment behind TLS, set `APP_ENV=production`, `FRONTEND_ORIGIN=https://your-exact-host`, and the Google callback URL for that host. Configure TLS at your reverse proxy. Cookies are `Secure` in production; serving production mode over plain HTTP will intentionally prevent browser sessions from working.

## Browser authentication

Run `scripts/setup_login.py` locally to set the single-user account. It stores only a salted scrypt password hash in `.env`; the plaintext password is entered privately and not printed. Restart the API after changing it. The login is separate from Google OAuth and the existing automation API key.

Login creates a random, opaque HttpOnly session cookie. Only a SHA-256 digest of its token is stored in Postgres. Sessions expire after eight hours by default, are revoked on logout, and are invalidated by a password/username change. Mutating browser requests require the session-bound `X-XSRF-TOKEN` header; Angular supplies it from its readable CSRF cookie. Login requires a custom request header and validates any browser Origin against `FRONTEND_ORIGIN`. Failed login attempts are throttled. Both the login throttle and general limiter are process-local; add proxy-level limits before scaling API replicas.

Existing service clients can still use `X-API-Key`. Do not put that key in Angular configuration or localStorage. The UI stores user identity in memory, not credentials in browser storage.

## Screens

- Overview: actual message/review/draft counts, recent mail and mailbox connections.
- Mailboxes: Gmail connection link, sync requests, last-sync status and refresh.
- Messages: paginated status filters, filtering of the current page, message body, extracted entities, classifications, action history, retry and draft creation.
- Review: paginated uncertain classifications with category/priority override and graph resume.
- Drafts: paginated status filters, editing, regeneration, rejection, versioned approval, explicit send confirmation and uncertain-outcome reconciliation. Unsaved edits block approval/send and prompt before navigating away.
- Rules: CRUD, enabled/order controls, JSON conditions/actions, validation feedback and a saved-rule dry run.
- Analytics: counts and category bars based on stored data. No fabricated sample metrics or trends.

Empty, loading, validation, network and stale-version states are handled explicitly. Email content renders as text; the app does not inject email HTML. Responsive navigation includes mobile sign-out and keyboard focus/skip controls.

## Verification

```bash
cd apps/web
npm ci
npm run typecheck
npm test
npm run build
```

Six Node-based controller tests use Angular's actual injection and signals with fake API responses. They cover unsaved draft edits, version handling, uncertain sends, stale responses, duplicate submission and session restore/logout. These do not render components or replace browser end-to-end testing.

Local TypeScript checks, production build and all six frontend controller tests passed. The expanded Python subset passed 47 tests, including eight browser-auth tests. Browser/visual checks could not run because this environment rejects local listening sockets (`listen EPERM`). Docker and the full Postgres/migration/live-provider checks remain blocked as recorded in `docs/verification.md`.

`make verify` includes a disposable web container and an app-shell/API-proxy smoke check. It requires Docker and package-network access. CI includes the TypeScript, controller-test and production-build commands.
