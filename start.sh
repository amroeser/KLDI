#!/usr/bin/env bash
set -euo pipefail

# Simple startup script for Windsurf project: starts backend (FastAPI+RQ worker) and frontend.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Load environment variables from .env if present (for ports, API keys, etc.)
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Export basic env vars
export PYTHONPATH="$ROOT_DIR"
export DATABASE_URL="sqlite:///./data/app.db"
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
# Use async Redis/RQ queue so POST /runs returns immediately with a Run ID
export USE_ASYNC_QUEUE=1

# Start Redis if available, else assume already running
if command -v redis-server >/dev/null 2>&1; then
  redis-server --save "" --appendonly no --daemonize yes || true
fi

# Start backend (uvicorn) and worker and simple static file server for frontend

# Backend-Port aus ENV oder Default (8101)
BACKEND_PORT=${BACKEND_PORT:-8101}
if command -v lsof >/dev/null 2>&1; then
  EXISTING_BACKEND_PIDS=$(lsof -ti tcp:$BACKEND_PORT || true)
  if [ -n "${EXISTING_BACKEND_PIDS}" ]; then
    echo "Backend-Port $BACKEND_PORT ist belegt (PIDs: ${EXISTING_BACKEND_PIDS}), beende Prozesse..."
    kill ${EXISTING_BACKEND_PIDS} 2>/dev/null || true
    sleep 1

    # Wenn der Port immer noch belegt ist (z.B. durch uvicorn-Childprozesse), härter nachfassen
    if lsof -ti tcp:$BACKEND_PORT >/dev/null 2>&1; then
      REMAINING_PIDS=$(lsof -ti tcp:$BACKEND_PORT || true)
      if [ -n "${REMAINING_PIDS}" ]; then
        echo "Backend-Port $BACKEND_PORT weiterhin belegt (PIDs: ${REMAINING_PIDS}), erzwinge Kill..."
        kill -9 ${REMAINING_PIDS} 2>/dev/null || true
        sleep 1
      fi
    fi
  fi
fi

uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

# RQ worker
rq worker --with-scheduler --url redis://localhost:6379 &
WORKER_PID=$!

# Frontend (simple http.server auf erstem freien Port ab FRONTEND_PORT_BASE)
FRONTEND_PORT_BASE=${FRONTEND_PORT_BASE:-5500}
FRONTEND_PORT=$FRONTEND_PORT_BASE

if command -v lsof >/dev/null 2>&1; then
  for p in $(seq "$FRONTEND_PORT_BASE" "$((FRONTEND_PORT_BASE + 4))"); do
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

# Export Ports/Origin für Backend (CORS) und Frontend-Konfiguration
export BACKEND_PORT
export FRONTEND_PORT
export FRONTEND_ORIGIN="http://localhost:${FRONTEND_PORT}"

# Frontend-Konfigdatei erzeugen (wird von app.js gelesen)
cat > "$ROOT_DIR/frontend/config.js" <<EOF
window.API_BASE = 'http://localhost:${BACKEND_PORT}';
window.FRONTEND_ORIGIN = 'http://localhost:${FRONTEND_PORT}';
EOF

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
