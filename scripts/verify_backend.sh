#!/usr/bin/env bash
# Disposable integration stack; never reads .env or connects to the user's DB.
set -euo pipefail
cd "$(dirname "$0")/.."
project="email-agent-check-$(id -u)-$$"
compose=(docker compose -p "$project" -f deploy/docker-compose.test.yml)
cleanup() {
    status=$?
    trap - EXIT
    if [ "$status" -ne 0 ]; then
        "${compose[@]}" logs --no-color || true
    fi
    "${compose[@]}" down --volumes --remove-orphans || true
    exit "$status"
}
trap cleanup EXIT
"${compose[@]}" config --quiet
"${compose[@]}" build
"${compose[@]}" up -d --wait --wait-timeout 120 api worker web
"${compose[@]}" run --rm tests
