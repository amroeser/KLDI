#!/usr/bin/env bash
set -euo pipefail

# Simple startup script for Windsurf project: starts backend (FastAPI+RQ worker) and frontend.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Export basic env vars
export PYTHONPATH="$ROOT_DIR"
export DATABASE_URL="sqlite:///./data/app.db"
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Start Redis if available, else assume already running
if command -v redis-server >/dev/null 2>&1; then
  redis-server --save "" --appendonly no --daemonize yes || true
fi

# Start backend (uvicorn) and worker and simple static file server for frontend

# Backend (Port 8001 freiräumen, falls belegt)
BACKEND_PORT=8001
if command -v lsof >/dev/null 2>&1; then
  EXISTING_BACKEND_PIDS=$(lsof -ti tcp:$BACKEND_PORT || true)
  if [ -n "${EXISTING_BACKEND_PIDS}" ]; then
    echo "Backend-Port $BACKEND_PORT ist belegt (PIDs: ${EXISTING_BACKEND_PIDS}), beende Prozesse..."
    kill ${EXISTING_BACKEND_PIDS} 2>/dev/null || true
    sleep 1
  fi
fi

uvicorn backend.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

# RQ worker
rq worker --with-scheduler --url redis://localhost:6379 &
WORKER_PID=$!

# Frontend (simple http.server auf erstem freien Port ab 5500)
FRONTEND_PORT=5500

if command -v lsof >/dev/null 2>&1; then
  for p in 5500 5501 5502 5503 5504; do
    # Wenn der Port belegt ist, versuchen wir, die Prozesse zu beenden
    EXISTING_PIDS=$(lsof -ti tcp:$p || true)
    if [ -n "${EXISTING_PIDS}" ]; then
      echo "Port $p ist belegt (PIDs: ${EXISTING_PIDS}), beende Prozesse..."
      kill ${EXISTING_PIDS} 2>/dev/null || true
      sleep 1
    fi

    # Prüfe erneut: falls jetzt frei, verwenden wir diesen Port
    if ! lsof -ti tcp:$p >/dev/null 2>&1; then
      FRONTEND_PORT=$p
      break
    fi
  done
fi

cd "$ROOT_DIR/frontend"
echo "Starte Frontend auf Port ${FRONTEND_PORT} (http://localhost:${FRONTEND_PORT}/index.html)"
python -m http.server "${FRONTEND_PORT}" &
FRONTEND_PID=$!

cd "$ROOT_DIR"

echo "Backend PID: $BACKEND_PID"
echo "Worker PID:  $WORKER_PID"
echo "Frontend PID: $FRONTEND_PID"

echo "Press Ctrl+C to stop all services."
trap 'kill $BACKEND_PID $WORKER_PID $FRONTEND_PID 2>/dev/null || true' INT TERM
wait
