"""Google OAuth2 over raw httpx (no Google SDK)."""

import time
from urllib.parse import urlencode

import httpx

from app.core.exceptions import ExternalServiceError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def build_auth_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # force a refresh_token every time
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _post_token(data: dict, http: httpx.Client | None = None) -> dict:
    if http:
        resp = http.post(TOKEN_URL, data=data)
    else:
        with httpx.Client(timeout=15) as client:
            resp = client.post(TOKEN_URL, data=data)
    if resp.status_code >= 400:
        raise ExternalServiceError(f"Google token endpoint error: {resp.status_code}")
    return resp.json()


def exchange_code(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    http: httpx.Client | None = None,
) -> dict:
    return _post_token(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        http,
    )


class TokenProvider:
    """Refreshes and caches a short-lived access token from a refresh token."""

    def __init__(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        http: httpx.Client | None = None,
    ):
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http
        self._access_token: str | None = None
        self._expires_at = 0.0

    def __call__(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token
        data = _post_token(
            {
                "refresh_token": self._refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            },
            self._http,
        )
        self._access_token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._access_token
