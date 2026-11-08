"""Read-only smoke checks against the disposable test API, never a real inbox."""
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main(base_url):
    key = os.environ["API_KEY"]
    for path in ("healthz", "readyz", "mailboxes", "messages", "review", "rules", "drafts", "analytics", "metrics"):
        request = Request(f"{base_url}/api/v1/{path}", headers={"X-API-Key": key})
        with urlopen(request, timeout=10) as response:
            assert response.status == 200, path
            payload = response.read()
            if path != "metrics":
                json.loads(payload)
        print(f"PASS {path}")
    try:
        with urlopen(f"{base_url}/api/v1/messages", timeout=10):
            raise AssertionError("Protected route accepted unauthenticated request")
    except HTTPError as exc:
        assert exc.code == 401, exc.code
    print("PASS unauthenticated request rejected")
    if os.environ.get("WEB_SMOKE_URL"):
        web = os.environ["WEB_SMOKE_URL"].rstrip("/")
        with urlopen(f"{web}/login", timeout=10) as response:
            assert b"<app-root>" in response.read(), "Angular app shell missing"
        with urlopen(f"{web}/api/v1/healthz", timeout=10) as response:
            assert json.loads(response.read())["status"] == "ok", "Frontend API proxy failed"
        print("PASS Angular app shell and same-origin API proxy")


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"))
