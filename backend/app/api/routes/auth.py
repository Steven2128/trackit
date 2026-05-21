import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_state_token,
    decode_state_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import AccessToken, TokenRefreshRequest
from app.schemas.user import UserOut
from app.services.google_oauth import (
    SIGNIN_SCOPES,
    build_authorization_url,
    exchange_code_for_tokens,
    verify_id_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)

AUTH_CALLBACK_PATH = "/auth/google/callback"


def _auth_redirect_uri() -> str:
    return f"{settings.api_base_url.rstrip('/')}{AUTH_CALLBACK_PATH}"


@router.get("/google/start")
async def google_login_start(return_scheme: str | None = None) -> RedirectResponse:
    scheme = return_scheme or settings.mobile_return_scheme
    state = create_state_token({"purpose": "auth", "return_scheme": scheme})
    try:
        url = build_authorization_url(
            scopes=SIGNIN_SCOPES,
            state=state,
            redirect_uri=_auth_redirect_uri(),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/callback")
async def google_login_callback(
    code: str,
    state: str,
    db: DbSession,
) -> RedirectResponse:
    try:
        claims = decode_state_token(state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state token",
        ) from exc

    if claims.get("purpose") != "auth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token has the wrong purpose",
        )

    try:
        tokens = await exchange_code_for_tokens(code, _auth_redirect_uri())
    except (ValueError, RuntimeError) as exc:
        log.warning("Google token exchange failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google token exchange failed",
        ) from exc

    id_token_jwt = tokens.get("id_token")
    if not id_token_jwt:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google response missing id_token",
        )

    try:
        idinfo = verify_id_token(id_token_jwt)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify Google id_token",
        ) from exc

    email = idinfo.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google id_token missing email claim",
        )

    name = idinfo.get("name")
    picture = idinfo.get("picture")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=email, name=name, picture=picture)
        db.add(user)
    else:
        if name and user.name != name:
            user.name = name
        if picture and user.picture != picture:
            user.picture = picture

    await db.commit()
    await db.refresh(user)

    subject = str(user.id)
    access = create_access_token(subject)
    refresh = create_refresh_token(subject)

    scheme = claims.get("return_scheme") or settings.mobile_return_scheme
    deep_link = f"{scheme}://auth?{urlencode({'access_token': access, 'refresh_token': refresh})}"
    return RedirectResponse(deep_link, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)


@router.post("/refresh", response_model=AccessToken)
async def refresh_access_token(payload: TokenRefreshRequest) -> AccessToken:
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc

    subject = claims.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing subject",
        )

    return AccessToken(access_token=create_access_token(subject))
