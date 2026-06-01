import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from googleapiclient.errors import HttpError
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
from app.services.email_sync import sync_provider_connection
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


class SyncResponse(BaseModel):
    processed: int
    created: int
    skipped_duplicate: int
    skipped_no_parser: int
    skipped_parser_returned_none: int
    errors: int
    last_sync_at: datetime | None


@router.post("/sync", response_model=SyncResponse)
async def gmail_sync(
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(
        default=None,
        ge=1,
        le=365,
        description="Only used on the first sync; subsequent runs resume from last_sync_at.",
    ),
    max_messages: int = Query(default=None, ge=1, le=2000),
) -> SyncResponse:
    existing = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.user_id == current_user.id,
            ProviderConnection.provider_type == ProviderType.gmail,
        )
    )
    connection = existing.scalars().first()
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no_gmail_connection",
        )

    lookback = days if days is not None else settings.gmail_sync_default_lookback_days
    limit = (
        max_messages if max_messages is not None else settings.gmail_sync_max_messages
    )

    try:
        result = await sync_provider_connection(
            db,
            connection,
            fallback_lookback_days=lookback,
            max_messages=limit,
        )
    except HttpError as exc:
        log.warning("Gmail API error during sync: %s", exc)
        if exc.resp.status in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="gmail_reauth_required",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="gmail_api_error",
        ) from exc
    except ValueError as exc:
        # decrypt_token raises ValueError if the ciphertext is corrupt or the
        # FERNET_KEY was rotated since the tokens were stored.
        log.warning("Gmail sync token decrypt failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="gmail_reauth_required",
        ) from exc

    return SyncResponse(
        processed=result.processed,
        created=result.created,
        skipped_duplicate=result.skipped_duplicate,
        skipped_no_parser=result.skipped_no_parser,
        skipped_parser_returned_none=result.skipped_parser_returned_none,
        errors=result.errors,
        last_sync_at=result.last_sync_at,
    )
