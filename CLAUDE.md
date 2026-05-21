# TrackIt — context for future Claude sessions

Personal finance mono-repo: FastAPI backend reads bank emails from Gmail and
exposes spending/debt data to an Expo mobile client. The README has the
"how to run" steps; this file covers the **non-obvious things** and the
decisions that bite if you forget them.

## Sibling docs to consult before working

- **`ROADMAP.md`** — current MVP scope, "Now" priorities, open questions. **Always read first** before suggesting new features; don't propose work that isn't on the list.
- **`DECISIONS.md`** — ADRs with the rationale for each weird choice (OAuth server-side, Fernet, async SQLA, etc.). Read when about to refactor something architectural — there's likely a reason it's that way.
- **`PARSERS.md`** — per-bank email parser registry. Currently only **Itaú Colombia** is parsed (it's the user's primary bank — all income and outflow goes through it). Other accounts (Falabella, Nequi, Daviplata, cash) are "parking destinations" detected from Itaú's outbound transfer emails and tagged `category="transfer"` so they don't count as spending. Read this file before adding a new bank or touching transfer detection.

## Layout

```
backend/   FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic + Pydantic v2
mobile/    Expo SDK 54 + React Native 0.81 + TypeScript
docker-compose.yml   Postgres 16 + backend service
```

## Stack pinning

- Python 3.12; SQLAlchemy 2.0 async with `mapped_column` style.
- FastAPI deps inject `AsyncSession` via `app/api/deps.py` (`DbSession`, `CurrentUser`).
- JWT signed with HS256 (`python-jose`). OAuth tokens encrypted at rest with Fernet — always go through `encrypt_token`/`decrypt_token` in `app/core/security.py`, never store raw.
- All DB models: UUID PK (`default=uuid.uuid4`) + `created_at` with `server_default=func.now()`. Postgres `Enum` type for `provider_type` and `transaction_type` (registered as `provider_type` / `transaction_type` so Alembic can autogen).

## The OAuth flow (server-side — read this before touching auth code)

**Expo's `auth.expo.io` proxy was killed in SDK 48+.** `Google.useAuthRequest({ useProxy: true })` is dead in SDK 54. We do NOT use `expo-auth-session/providers/google` anymore. The flow is:

1. Mobile → `WebBrowser.openAuthSessionAsync(<API>/auth/google/start, "trackit://auth")`
2. Backend `/auth/google/start` → 307 to Google with scopes + state JWT
3. Google → `/auth/google/callback?code&state`
4. Backend exchanges code, verifies id_token, upserts `User`, issues app JWTs
5. Backend 307 → `trackit://auth?access_token=...&refresh_token=...`
6. Mobile parses the URL with `expo-linking`, calls `/auth/me` for the user object, persists session to SecureStore + Zustand.

**Gmail connect** uses the same shape but auth-gated: `POST /gmail/connect` (with Bearer token) returns `{auth_url}` containing a state JWT bound to `user_id`. Mobile opens it; backend `/gmail/callback` stores the encrypted tokens in `provider_connections`.

State CSRF: short-lived (10 min) JWT with `purpose`, `nonce`, `exp` — see `create_state_token` / `decode_state_token` in `app/core/security.py`. Reuse those, don't roll your own.

`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` live **only on the backend**. Mobile has NO Google client IDs — the `EXPO_PUBLIC_GOOGLE_CLIENT_ID_*` vars in `.env` are leftovers and unused.

## Mobile ↔ backend URL plumbing

Mobile resolves the API URL with this fallback chain (`mobile/src/services/api.ts:8` and `mobile/src/screens/LoginScreen.tsx`):

1. `Constants.expoConfig?.extra?.apiUrl` (from `mobile/app.json` → `extra.apiUrl`)
2. `process.env.EXPO_PUBLIC_API_URL` (from `.env` root)
3. hardcoded `http://localhost:8000`

Keep `app.json` `extra.apiUrl` and `.env`'s `EXPO_PUBLIC_API_URL` in sync — drift between them silently breaks the client.

After changing `extra.apiUrl`, run `npx expo start --clear` — Metro caches the manifest.

## Physical device testing — ngrok is required

Google rejects HTTP redirect URIs unless they're `localhost` / `127.0.0.1`. Your phone can't reach `localhost`, so:

1. `ngrok http 8000` (or a static domain via free ngrok account)
2. Update **all three** places with the new URL:
   - `.env` root: `API_BASE_URL=https://<id>.ngrok-free.app` AND `EXPO_PUBLIC_API_URL=...`
   - `mobile/app.json` → `extra.apiUrl`
3. Add **both** callbacks to the Web OAuth client in Google Cloud Console:
   - `https://<id>.ngrok-free.app/auth/google/callback`
   - `https://<id>.ngrok-free.app/gmail/callback`
4. `docker compose up -d backend` (recreates with the new env)
5. `npx expo start --clear` in `mobile/`

ngrok free tier without a reserved domain shows a "Visit Site" interstitial on first hit from a new browser session — user has to tap through it once. Use a static domain to avoid having to redo Cloud Console + envs every restart.

## What is implemented vs stub

Real (with logic):
- `GET /health`
- `GET /auth/google/start`, `GET /auth/google/callback`
- `GET /auth/me`, `POST /auth/refresh`
- `POST /gmail/connect`, `GET /gmail/callback`

Stubs (return empty / 501 / "not_implemented"):
- `POST /gmail/sync`
- `GET /transactions`, `GET /transactions/summary`
- `GET /debts`, `POST /debts`, `PATCH /debts/{id}`
- `app/parsers/base.py` — only the `EmailParser` ABC, no bank-specific parsers
- `app/integrations/gmail.py` — `GmailClient` raises `NotImplementedError`

When adding a bank parser, subclass `EmailParser` from `app/parsers/base.py`. `parse()` returns a `ParsedTransaction` dataclass — the route that consumes it has to map to the `Transaction` SQLA model and set `provider_connection_id`.

## Common commands

```bash
# DB only / full stack
docker compose up -d db
docker compose up -d backend

# Alembic
docker compose run --rm backend alembic revision --autogenerate -m "msg"
docker compose run --rm backend alembic upgrade head

# psql
docker compose exec db psql -U trackit -d trackit

# Mobile
cd mobile && npx expo start --clear
cd mobile && npx tsc --noEmit   # type-check only

# Logs
docker compose logs -f backend
```

## Secrets — generation

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"               # SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # FERNET_KEY
```

If `FERNET_KEY` is rotated, all rows in `provider_connections` become undecryptable. Plan a re-link flow before rotating in any real environment.

## Conventions / gotchas

- Don't return `User` ORM objects from routes — use `UserOut.model_validate(user)`.
- `Pydantic v2` requires `model_config = ConfigDict(from_attributes=True)` on response schemas that read ORM objects.
- `python-jose` is what we use for JWT — not PyJWT. They have different APIs.
- Pydantic `EmailStr` requires `pydantic[email]` (already in `pyproject.toml`); don't downgrade.
- When you add a new model, add it to `app/models/__init__.py` so Alembic's `env.py` sees it in `Base.metadata`.
- Custom URL scheme is `trackit` (set in `mobile/app.json` → `expo.scheme`). Deep-link return URLs from the backend MUST use this exact scheme.
