#!/bin/bash
# Starts both the FastAPI backend (port 8000) and Next.js frontend (port 3000)

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv/bin"

echo "🚀 Starting Portfolio AI..."

# Backend
echo "  → Backend on http://localhost:8000"
"$VENV/uvicorn" backend.main:app --reload --port 8000 --host 0.0.0.0 &
BACKEND_PID=$!

# Install frontend deps if needed
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "  → Installing frontend dependencies..."
  (cd "$ROOT/frontend" && npm install --silent)
fi

# Frontend
echo "  → Frontend on http://localhost:3000"
(cd "$ROOT/frontend" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "✅ Running!"
echo "   Dashboard: http://localhost:3000"
echo "   API docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

cleanup() {
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "Stopped."
}
trap cleanup EXIT INT TERM
wait
