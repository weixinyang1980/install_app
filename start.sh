#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
(cd "$ROOT/backend" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8765) &
(cd "$ROOT/admin" && [ -d node_modules ] || npm install; npm run dev) &
(cd "$ROOT/desktop" && [ -d node_modules ] || npm install; npm run dev) &
wait
