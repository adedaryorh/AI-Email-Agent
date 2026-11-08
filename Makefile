PY=.venv/bin/python
.PHONY: install dev worker migrate test lint up retention eval
install:
	uv venv --python 3.12
	uv pip install -e ".[dev]"
dev:
	.venv/bin/uvicorn app.main:app --reload --port 8080 --no-access-log
worker:
	$(PY) -m app.workers.poller
migrate:
	.venv/bin/alembic upgrade head
	$(PY) -m app.graph.checkpointer
test:
	$(PY) -m pytest -q
lint:
	.venv/bin/ruff check .
up:
	docker compose -f deploy/docker-compose.yml up --build
retention:
	$(PY) -m app.workers.retention
eval:
	$(PY) -m app.evals.run --dataset evals/seed.jsonl

.PHONY: verify
verify:
	bash scripts/verify_backend.sh

.PHONY: web-install web-dev web-build
web-install:
	cd apps/web && npm ci
web-dev:
	cd apps/web && npm start
web-build:
	cd apps/web && npm run build

.PHONY: eval-agent
eval-agent:
	$(PY) -m app.evals.agent --dataset evals/agent.jsonl
