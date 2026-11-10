#!/usr/bin/env bash
# Run all backend unit and integration tests
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR/backend"

if [ -f "$DIR/backend/.venv/bin/pytest" ]; then
    PYTEST="$DIR/backend/.venv/bin/pytest"
elif command -v pytest &> /dev/null; then
    PYTEST="pytest"
else
    PYTEST="python3 -m pytest"
fi

echo "=== Running VisionGuard AI Test Suite ==="
PYTHONPATH=. $PYTEST tests/ -v

