#!/usr/bin/env bash
# One-shot: install, build the frontend, hand it to FastAPI, and start the server.
# Run from the repository root:  bash start.sh
set -euo pipefail

npm --prefix apps/web ci
npm --prefix apps/web run build

mkdir -p apps/api/static
cp -R apps/web/dist/. apps/api/static/

pip install -r apps/api/requirements.txt

cd apps/api
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
