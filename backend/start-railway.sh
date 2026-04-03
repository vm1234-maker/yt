#!/bin/sh
# Railway single-container: Celery worker + FastAPI (same image as docker-compose worker + api).
set -e
cd /app
export PYTHONPATH=/app
celery -A tasks worker --loglevel=info --concurrency=2 &
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
