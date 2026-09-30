#!/usr/bin/env bash
# Start Cloudflare Quick Tunnel for demo deployment
set -e

if command -v cloudflared &> /dev/null; then
    CLOUDFLARED_CMD="cloudflared"
else
    echo "ℹ️  Không tìm thấy binary cloudflared trên máy, tự động dùng qua npx..."
    CLOUDFLARED_CMD="npx --yes cloudflared"
fi

echo "=== Đang mở Cloudflare Tunnel cho Backend AI trên cổng 8000 ==="
echo "📌 Hãy copy URL dạng https://xxx.trycloudflare.com hiển thị bên dưới"
echo "   và dán vào mục 'Cài Đặt Kết Nối AI' trên giao diện web!"
echo "------------------------------------------------------------------"
$CLOUDFLARED_CMD tunnel --url http://127.0.0.1:8000

