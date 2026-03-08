#!/bin/bash
# shipOS v3 (autonomous AI BCNOFNe system) - Startup Script
#
# Requirements:
# - ngrok installed and authtoken configured
# - jq installed (sudo apt install jq)
# - tailscale installed (optional)

# 1. IP Address Discovery
echo "====================================="
echo " Exploring Network for IPs...        "
echo "====================================="

# Get Tailscale IP separately
TS_IP=$(tailscale ip -4 2>/dev/null | head -n 1)
if [ -z "$TS_IP" ]; then
    TS_IP="NOT_FOUND"
fi
echo "FOUND TAILSCALE IP: ${TS_IP}"

# Get LAN IP (exclude 100.x Tailscale, 172.x Docker, 127.x loopback)
LOCAL_IP=$(hostname -I | tr ' ' '\n' | grep -v '^100\.' | grep -v '^172\.' | grep -v '^127\.' | head -n 1)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="NOT_FOUND"
fi
echo "FOUND LOCAL IP: ${LOCAL_IP}"

# Update .env file with current IPs
if [ -f .env ]; then
    sed -i '/^HOST_IP=/d' .env
    sed -i '/^TAILSCALE_IP=/d' .env
    echo "HOST_IP=${LOCAL_IP}" >> .env
    echo "TAILSCALE_IP=${TS_IP}" >> .env
else
    echo "HOST_IP=${LOCAL_IP}" > .env
    echo "TAILSCALE_IP=${TS_IP}" >> .env
fi

# 2. Restart Containers
echo "====================================="
echo " Starting shipOS Docker containers... "
echo "====================================="
docker compose down
docker compose pull
docker compose up -d --build

# 3. Ngrok Startup for LINE Webhook
echo "====================================="
echo " Starting Ngrok for LINE Webhook...  "
echo "====================================="
pkill ngrok
sleep 1
ngrok http 8001 > /dev/null 2>&1 &
sleep 5

# 4. Display Webhook URL
WEBHOOK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')

if [ -n "$WEBHOOK_URL" ] && [ "$WEBHOOK_URL" != "null" ]; then
    echo ""
    echo "=========================================================="
    echo " [SUCCESS] Ngrok Tunnel Established!"
    echo " Webhook URL for LINE Developers console:"
    echo " -> ${WEBHOOK_URL}/webhook"
    echo "=========================================================="
else
    echo ""
    echo "[ERROR] Failed to get Ngrok URL."
fi

echo ""
echo "To view logs: docker compose logs -f"
echo "To shutdown: docker compose down && pkill ngrok"
