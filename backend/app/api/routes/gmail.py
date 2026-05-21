import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import (
    create_state_token,
    decode_state_token,
    encrypt_token,
)
from app.models.provider_connection import ProviderConnection, ProviderType
from app.services.google_oauth import (
    GMAIL_READONLY_SCOPES,
    build_authorization_url,
    exchange_code_for_tokens,
    verify_id_token,
)

router = APIRouter(prefix="/gmail", tags=["gmail"])
log = logging.getLogger(__name__)

GMAIL_CALLBACK_PATH = "/gmail/callback"


def _gmail_redirect_uri() -> str:
    return f"{settings.api_base_url.rstrip('/')}{GMAIL_CALLBACK_PATH}"


class GmailConnectStartRequest(BaseModel):
    return_scheme: str | None = None


class GmailConnectStartResponse(BaseModel):
    auth_url: str


@router.post("/connect", response_model=GmailConnectStartResponse)
async def gmail_connect_start(
    payload: GmailConnectStartRequest,
    current_user: CurrentUser,
) -> GmailConnectStartResponse:
    scheme = payload.return_scheme or settings.mobile_return_scheme
    state = create_state_token(
        {
            "purpose": "gmail",
            "user_id": str(current_user.id),
            "return_scheme": scheme,
        }
    )
    try:
        url = build_authorization_url(
            scopes=GMAIL_READONLY_SCOPES,
            state=state,
            redirect_uri=_gmail_redirect_uri(),
            access_type="offline",
            prompt="consent",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return GmailConnectStartResponse(auth_url=url)


@router.get("/callback")
async def gmail_callback(code: str, state: str, db: DbSession) -> RedirectResponse:
    try:
        claims = decode_state_token(state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state token",
        ) from exc

    if claims.get("purpose") != "gmail":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token has the wrong purpose",
        )

    try:
        user_id = uuid.UUID(claims["user_id"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token missing or invalid user_id",
        ) from exc

    try:
        tokens = await exchange_code_for_tokens(code, _gmail_redirect_uri())
    except (ValueError, RuntimeError) as exc:
        log.warning("Google token exchange failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google token exchange failed",
        ) from exc

    access_token_value = tokens.get("access_token")
    refresh_token_value = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")
    id_token_jwt = tokens.get("id_token")

    if not access_token_value:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google response missing access_token",
        )

    provider_email = None
    if id_token_jwt:
        try:
            idinfo = verify_id_token(id_token_jwt)
            provider_email = idinfo.get("email")
        except ValueError:
            log.warning("Gmail callback: could not verify id_token, leaving provider_email empty")

    if not provider_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine the connected Gmail address",
        )

    expires_at = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    existing = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.user_id == user_id,
            ProviderConnection.provider_type == ProviderType.gmail,
            ProviderConnection.provider_email == provider_email,
        )
    )
    connection = existing.scalar_one_or_none()

    if connection is None:
        if not refresh_token_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Google did not return a refresh_token. Revoke the existing grant at "
                    "https://myaccount.google.com/permissions and try again."
                ),
            )
        connection = ProviderConnection(
            user_id=user_id,
            provider_type=ProviderType.gmail,
            provider_email=provider_email,
            access_token_encrypted=encrypt_token(access_token_value),
            refresh_token_encrypted=encrypt_token(refresh_token_value),
            expires_at=expires_at,
        )
        db.add(connection)
    else:
        connection.access_token_encrypted = encrypt_token(access_token_value)
        if refresh_token_value:
            connection.refresh_token_encrypted = encrypt_token(refresh_token_value)
        connection.expires_at = expires_at

    await db.commit()

    scheme = claims.get("return_scheme") or settings.mobile_return_scheme
    deep_link = f"{scheme}://gmail-connected?{urlencode({'status': 'ok', 'email': provider_email})}"
    return RedirectResponse(deep_link, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def gmail_sync(current_user: CurrentUser) -> dict[str, str]:
    return {"status": "not_implemented", "endpoint": "POST /gmail/sync"}
