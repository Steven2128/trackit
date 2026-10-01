# TrackIt

Personal finance app that reads bank emails from Gmail and tracks expenses.
Mono-repo with a FastAPI backend, an Expo (React Native + TypeScript) mobile
client, and a PostgreSQL 16 database running via Docker Compose.

## Stack

- **Backend:** FastAPI, Python 3.12, SQLAlchemy 2.0 async, asyncpg, Alembic,
  Pydantic v2, JWT (python-jose), Fernet (cryptography), google-auth.
- **Mobile:** Expo + React Native (TypeScript), React Query, Zustand,
  React Navigation, Axios, expo-secure-store, expo-auth-session.
- **DB:** PostgreSQL 16 (Docker Compose).

## Repo layout

```
trackit/
├── backend/      FastAPI service + Alembic migrations
├── mobile/       Expo app
├── docker-compose.yml
├── .env.example  Copy to .env before booting anything
└── README.md
```

## Prerequisites

- Docker Desktop (or Docker Engine 24+) with Compose v2
- Python 3.12 (only needed if you want to run Alembic from the host)
- Node.js 20+ and npm 10+
- An iOS or Android device with Expo Go, or a configured simulator

## 1. Generate secrets

```bash
# JWT signing key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Fernet key for encrypting OAuth tokens at rest
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the values into your `.env` (see next step).

## 2. Configure environment

```bash
cp .env.example .env
# Edit .env and paste the two generated keys, plus your Google OAuth credentials.
```

## 3. Boot the database and backend

```bash
docker compose up -d db
docker compose up -d backend
```

The API is now reachable at <http://localhost:8000>. Visit
<http://localhost:8000/docs> for the auto-generated Swagger UI and
<http://localhost:8000/health> for a liveness check.

## 4. Run the initial migration

From inside the backend container:

```bash
docker compose exec backend alembic upgrade head
```

Or from the host (after `pip install -e backend` in a virtualenv):

```bash
cd backend
alembic upgrade head
```

You should see four tables created: `users`, `provider_connections`,
`transactions`, `debts`.

## 5. Start the mobile app

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with Expo Go, or press `i` / `a` for the iOS/Android
simulator. Make sure `EXPO_PUBLIC_API_URL` in `.env` points to a host
that the device can reach (for physical devices on the same Wi-Fi, use
your machine's LAN IP instead of `localhost`).

## Deploy (Render + Neon, free)

Pushing to `master` deploys automatically once CI passes. Rationale in
`DECISIONS.md` → ADR-008. One-time setup:

1. **Neon** (neon.tech) → new project, region *AWS us-east-1*. Copy the
   **direct** connection string (turn off "Connection pooling") — it looks
   like `postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require`.
   Paste it as-is; the backend converts it for asyncpg.
2. **Render** (render.com) → *New → Blueprint* → pick this GitHub repo. It
   reads `render.yaml` and asks for the `sync: false` values:
   - `DATABASE_URL` — the Neon string.
   - `SECRET_KEY`, `FERNET_KEY` — reuse your local ones if you migrate data
     (step 5), otherwise generate new ones.
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ITAU_STATEMENT_PDF_PASSWORD`, `RESEND_API_KEY` — same as `.env`.
   - `API_BASE_URL` — the service URL, e.g. `https://trackit-api.onrender.com`.
   - `CRON_SECRET` — `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
3. **Google Cloud Console** → OAuth Web client → add redirect URIs
   `<API_BASE_URL>/auth/google/callback` and `<API_BASE_URL>/gmail/callback`.
   Also move the OAuth consent screen from *Testing* to *In production* —
   in Testing, refresh tokens expire after 7 days and Gmail sync dies.
4. **GitHub** → repo Settings → Secrets and variables → Actions: secret
   `CRON_SECRET` (same value as Render) and variable `API_URL` (= `API_BASE_URL`).
5. *(Optional, do it right after step 1 — before Render's first deploy
   creates empty tables)* copy local data to Neon, using the psql inside
   the local db container:
   ```bash
   docker compose exec -T db pg_dump -U trackit -d trackit --no-owner --no-acl > dump.sql
   docker compose exec -T db psql "<neon connection string>" < dump.sql
   ```
6. **Mobile**: set `mobile/app.json` → `extra.apiUrl` and `.env`'s
   `EXPO_PUBLIC_API_URL` to the Render URL, then `npx expo start --clear`.

Free-tier caveat: the API sleeps after ~15 min idle, so the first request
after a while takes ~1 min. Scheduled jobs run from
`.github/workflows/cron.yml` (also runnable by hand from the Actions tab).

## Troubleshooting

- **`alembic upgrade head` hangs or errors with `connection refused`** —
  Postgres might still be booting. Wait for `docker compose ps` to show
  `db` as `healthy` and retry.
- **Mobile can't reach the backend** — `localhost` on a physical phone
  refers to the phone itself. Replace `EXPO_PUBLIC_API_URL` with your
  machine's LAN IP (e.g. `http://192.168.1.42:8000`).
- **`FERNET_KEY` errors at startup** — the key must be a URL-safe base64
  32-byte value. Regenerate with the snippet above and paste it verbatim.

## Useful commands

```bash
# Tail backend logs
docker compose logs -f backend

# Open a psql shell
docker compose exec db psql -U trackit -d trackit

# Stop everything
docker compose down

# Wipe the database (destructive)
docker compose down -v
```
