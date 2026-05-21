import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]
STATE_TOKEN_TYPE = "state"
STATE_TOKEN_DEFAULT_TTL = timedelta(minutes=10)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(_now().timestamp()),
        "exp": int((_now() + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid_token") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise ValueError("wrong_token_type")
    return payload


def create_state_token(
    claims: dict[str, Any],
    expires_in: timedelta = STATE_TOKEN_DEFAULT_TTL,
) -> str:
    payload: dict[str, Any] = {
        **claims,
        "type": STATE_TOKEN_TYPE,
        "nonce": secrets.token_urlsafe(16),
        "iat": int(_now().timestamp()),
        "exp": int((_now() + expires_in).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_state_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid_state") from exc

    if payload.get("type") != STATE_TOKEN_TYPE:
        raise ValueError("not_a_state_token")
    return payload


def _fernet() -> Fernet:
    if not settings.fernet_key:
        raise RuntimeError(
            "FERNET_KEY is not configured. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            'print(Fernet.generate_key().decode())"`'
        )
    return Fernet(settings.fernet_key.encode())


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("invalid_ciphertext") from exc
