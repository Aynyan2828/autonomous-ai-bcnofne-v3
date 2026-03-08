#!/bin/bash
# autonomous AI BCNOFNe system v3 (shipOS) - 起動＆Webhook連携スクリプト
#
# 前提: ngrok がインストールされ、認証トークンが設定されていること
#      sudo apt install jq (JSON解析用) がインストールされていること

# 1. shipOS コンテナの起動
echo "====================================="
echo " Starting shipOS Docker containers... "
echo "====================================="
docker compose pull
docker compose up -d --build

# 2. Ngrok の起動 (バックグラウンドでポート8001: line-gateway を公開)
echo "====================================="
echo " Starting Ngrok for LINE Webhook...  "
echo "====================================="
# 古いngrokプロセスをキル
pkill ngrok

# line-gateway (8001番ポート) を公開。ログは一時ファイルに捨てる
ngrok http 8001 > /dev/null 2>&1 &

# Ngrokがトンネルを確立するまで数秒待機
sleep 4

# 3. Webhook URLの取得と表示
WEBHOOK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')

if [ -n "$WEBHOOK_URL" ] && [ "$WEBHOOK_URL" != "null" ]; then
    echo ""
    echo "=========================================================="
    echo " [SUCCESS] Ngrok Tunnel Established!"
    echo " 以下のURLをLINE DevelopersのWebhook URLに設定してください："
    echo " -> ${WEBHOOK_URL}/webhook"
    echo "=========================================================="
else
    echo " "
    echo "[ERROR] NgrokのURL取得に失敗しました。"
    echo "ngrok が正しくインストール・設定されているか確認してください。"
fi

echo ""
echo "ログを確認するには: docker compose logs -f"
echo "終了するには: docker compose down && pkill ngrok"
