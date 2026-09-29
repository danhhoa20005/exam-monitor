#!/usr/bin/env bash
# Start VisionGuard AI FastAPI Backend
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR/backend"

echo "=== Starting VisionGuard AI Backend on http://127.0.0.1:8000 ==="
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --reload
