#!/bin/sh
# Seed the database if it's empty, then start the app
set -eu

/app/.venv/bin/python -m scripts.seed_db
exec /app/.venv/bin/python -m backend
