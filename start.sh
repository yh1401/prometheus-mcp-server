#!/bin/bash
# Start script for Prometheus MCP Server Extended

cd "$(dirname "$0")"

echo "============================================"
echo "  Prometheus MCP Server Extended"
echo "============================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "[INFO] .env not found, using .env.example"
    cp .env.example .env
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "[INFO] Installing dependencies..."
pip install -q -r requirements.txt

# Start server
echo "[INFO] Starting server..."
echo ""
echo "Server will be available at:"
echo "  - API: http://localhost:8000"
echo "  - Docs: http://localhost:8000/docs"
echo "  - Health: http://localhost:8000/api/v1/metrics/health"
echo ""
echo "Press Ctrl+C to stop"
echo "============================================"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload