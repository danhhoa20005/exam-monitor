#!/usr/bin/env bash
# Start Cloudflare Quick Tunnel for demo deployment
set -e

if ! command -v cloudflared &> /dev/null; then
    echo "[ERROR] cloudflared is not installed."
    echo "Install with Homebrew: brew install cloudflared"
    exit 1
fi

echo "=== Starting Cloudflare Quick Tunnel for backend on port 8000 ==="
cloudflared tunnel --url http://localhost:8000
