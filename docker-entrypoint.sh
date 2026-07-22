#!/bin/sh
# Container entrypoint: migrate (when not SQLite create_all) then serve.
set -eu
BOOTSTRAP="${SCHEMA_BOOTSTRAP:-}"
DB_URL="${DATABASE_URL:-sqlite:///./ragnar.db}"

case "$DB_URL" in
  postgresql*|postgres*)
    echo "Running alembic upgrade head…"
    alembic upgrade head || echo "alembic failed (continuing) — check DATABASE_URL"
    ;;
  *)
    if [ "$BOOTSTRAP" = "alembic" ]; then
      echo "Running alembic upgrade head…"
      alembic upgrade head || true
    fi
    ;;
esac

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
