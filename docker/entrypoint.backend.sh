#!/bin/bash
# Aegis backend container entrypoint.
# 1. Seed a few synthetic rogue processes in the background so the dashboard
#    has something to show.
# 2. Start uvicorn.

set -e

mkdir -p /app/logs

# Seed in the background; the script self-detaches.
/usr/local/bin/seed-rogue-demo &

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir /app/backend
