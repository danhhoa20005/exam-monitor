#!/usr/bin/env bash
# Run all backend unit and integration tests
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR/backend"

echo "=== Running VisionGuard AI Test Suite ==="
python3 -m pytest tests/ -v
