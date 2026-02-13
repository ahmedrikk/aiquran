#!/bin/bash
# Quran-Talk Startup Script (Noor AI Frontend Edition)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FRONTEND_DIR="$SCRIPT_DIR/sacred-scroll-ai-main"

echo "🕌 ═══════════════════════════════════════════════"
echo "   Quran-Talk - Islamic Scholar AI (Noor AI)"
echo "═══════════════════════════════════════════════════"

# Check venv
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama not running! Start it with: ollama serve"
    exit 1
fi

echo ""
echo "Starting services..."
echo ""

# Start Backend (background)
echo "📚 [1/2] Starting Backend (port 8000)..."
uvicorn backend:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 3

# Start Frontend (foreground)
echo "🌐 [2/2] Starting Noor AI Frontend (port 8080)..."
echo ""
echo "════════════════════════════════════════════════════"
echo "  ✅ Backend running on http://localhost:8000"
echo "  ✅ Frontend running on http://localhost:8080"
echo ""
echo "  Open in your browser:"
echo "    👉  http://localhost:8080"
echo "════════════════════════════════════════════════════"
echo ""

# Trap to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

wait
