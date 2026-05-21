"""Server-side Google OAuth 2.0 helpers (authorization-code flow)."""

from urllib.parse import urlencode

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105

# Standard scopes
SIGNIN_SCOPES = ["openid", "email", "profile"]
GMAIL_READONLY_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def build_authorization_url(
    *,
    scopes: list[str],
    state: str,
    redirect_uri: str,
    access_type: str = "online",
    prompt: str | None = None,
) -> str:
    if not settings.google_client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured")

    params: dict[str, str] = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": access_type,
        "include_granted_scopes": "true",
    }
    if prompt:
        params["prompt"] = prompt
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not configured")

    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)
    if response.status_code >= 400:
        raise ValueError(f"Google token exchange failed: {response.text}")
    return response.json()


def verify_id_token(id_token_jwt: str) -> dict:
    """Validate Google id_token signature + audience, return its claims."""
    return google_id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        settings.google_client_id,
    )
