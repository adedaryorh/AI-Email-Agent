# Grounded drafting agent

The sorting LangGraph invokes a bounded drafting workflow when a rule requests a draft or the user generates one. Knowledge and preferences are optional. Empty knowledge produces clarification-style replies when facts are missing, rather than inventing a policy.

## Owner-managed context

In **Knowledge**, paste trusted policy/FAQ text, edit it, or delete it. Retrieval is local lexical matching over overlapping text excerpts (1,500 characters, 1,200-character stride); no embedding service, file parser or URL fetch is involved. There is a 500-document limit and a 50,000-character limit per document. At most ten retrieved excerpts reach a run. Lexical retrieval is deliberately simple and can miss paraphrases or non-English terminology.

In **Preferences**, edit tone, language and curated corrections. Clearing preferences removes their text. Preference versions prevent lost updates. Messages and model suggestions never write preferences automatically.

## Execution and approval

Each run searches the knowledge base, then lets a structured planner choose from `search_knowledge`, `read_thread`, `request_clarification` and `finish`. The clarification tool only supplies a question to the draft writer. No tool sends mail, executes commands, follows URLs or changes preferences. Repeated calls, unknown tools, unknown citations and exhausted budgets stop the run. Failed runs are recorded and may be retried by the user; they do not create Gmail drafts.

Composition returns a body and source IDs. A separate model call checks for unsupported claims, unsafe requests, missing information and invented commitments. Failure leaves a pending draft that cannot be approved. Human editing reruns verification; regeneration repeats the workflow. Legacy drafts have no verification and must be edited or regenerated before approval.

Approval and send require a passing verification result tied to the exact body hash, current document versions and current preferences. The approval/send critical section excludes concurrent knowledge/preference changes. Editing revokes approval. Sending still requires an explicit human API/UI action, and uncertain sends cannot be retried automatically.

Model verification is fallible. It is an additional review aid, not a guarantee of factual correctness or a replacement for human approval. Read the draft and its retrieved source excerpts before approving. Retrieved sources shown in the UI include context considered by the model; `verification.citations` identifies source IDs selected by composition.

## Budgets and telemetry

- `AGENT_MAX_STEPS=4`: at most four planner calls, followed by one composition and one verification call. A planner exhausting all steps without finish/clarification fails.
- `AGENT_MAX_INPUT_CHARS=120000`: cumulative serialized input data across calls; exceeding it stops before the next model request. Prompts/schema overhead is not part of this counter.
- `AGENT_MAX_OUTPUT_TOKENS=2048`: per-call provider output limit for agent calls.
- `AGENT_TIMEOUT_SECONDS=180`: checked before and after model calls. Each model call has a timeout capped at 45 seconds or remaining time, with retries disabled. A Gmail read can extend elapsed time because it uses the Gmail client's separate timeout/retry policy; the next model call then stops if the run deadline has elapsed.

**Agent activity** shows tool summaries, outcomes, elapsed time, submitted character counts and token usage when supplied by the provider. It does not store chain-of-thought or raw email/model payloads. Character limits are not token counts or dollar billing caps. Set `LLM_INPUT_USD_PER_MILLION` and `LLM_OUTPUT_USD_PER_MILLION` to your model rates to display estimated per-call USD costs. Optional `AGENT_MAX_COST_USD` blocks calls whose conservative input-byte/output-token estimate would exceed the run budget; cost-budgeted runs stop if provider usage is missing. Prices are owner-configured and may omit provider-specific fees, so this is an estimated local guard, not a provider-enforced billing cap. Configure a provider account budget separately. Runs interrupted by a process crash may remain marked `running`; the next attempt under the operation lock marks the earlier record `interrupted`. It does not replay any send.

## APIs and migration

All endpoints use existing API-key or browser-session/CSRF authentication:

| Endpoint | Purpose |
| --- | --- |
| `GET/POST /api/v1/knowledge` | List/create documents |
| `PUT /api/v1/knowledge/{id}` | Update title/content using current `version` |
| `DELETE /api/v1/knowledge/{id}?version=N` | Delete current document version |
| `GET/PUT /api/v1/preferences` | Read/update instructions using current `version` (initially 0) |
| `GET /api/v1/agent/runs?offset=0&message_id=N` | List runs, optional message filter |
| `GET /api/v1/agent/runs/{id}` | Run detail and events |

Migration `0004` adds knowledge, preferences and execution tables plus draft sources/verification/run association. Run `make migrate` before using these features. The migration is authored but has not been executed locally against modern Alembic/Postgres in this restricted environment.

## Evaluation

`make eval-agent` runs 14 labeled synthetic extraction, verification and tool-policy cases against the configured real model. It exits unsuccessfully if overall accuracy is below 80% or any unsafe verification example is incorrectly accepted. `python -m app.evals.agent --predictions results.json` scores supplied predictions offline. The optional live CI job runs this beside the existing 28-case classification evaluation when credentials are available.

`tests/test_agent.py` exercises retrieval, source/preference invalidation, unknown tools/citations, repeated calls, budgets, clarification, verification failure and body tampering with deterministic fake models. These establish orchestration behavior, not real LLM accuracy. The synthetic live cases also do not substitute for a representative, consented inbox evaluation set.
