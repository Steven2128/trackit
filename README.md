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
