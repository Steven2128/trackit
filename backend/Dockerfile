FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# docker-compose builds with INSTALL_DEV=true (pytest, ruff…); the hosted
# image (Render) skips dev tooling.
ARG INSTALL_DEV=false

COPY pyproject.toml ./
RUN pip install --upgrade pip \
 && if [ "$INSTALL_DEV" = "true" ]; then pip install -e ".[dev]"; else pip install -e .; fi

COPY . .

EXPOSE 8000

# Hosts like Render inject $PORT. Migrations run on every boot so a deploy
# never serves code ahead of its schema (`alembic upgrade head` is a no-op
# when already current). docker-compose overrides this with --reload.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
