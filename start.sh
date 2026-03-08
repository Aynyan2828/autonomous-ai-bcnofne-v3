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

# Get real LAN IP (exclude loopback and Tailscale 100.x)
LOCAL_IP=$(hostname -I | tr ' ' '\n' | grep -v '^100\.' | grep -v '^127\.' | head -n 1)
echo "FOUND LOCAL IP: ${LOCAL_IP}"

# Get Tailscale IP
TS_IP=""
if command -v tailscale &> /dev/null; then
    TS_IP=$(tailscale ip -4 2>/dev/null | head -n 1)
    if [ -n "$TS_IP" ]; then
        echo "FOUND TAILSCALE IP: ${TS_IP}"
    else
        echo "TAILSCALE IP NOT FOUND"
    fi
else
    echo "TAILSCALE NOT INSTALLED"
fi

# Update .env file with current IPs
if [ -f .env ]; then
    sed -i '/^HOST_IP=/d' .env
    sed -i '/^TAILSCALE_IP=/d' .env
    echo "HOST_IP=${LOCAL_IP:-NOT_FOUND}" >> .env
    echo "TAILSCALE_IP=${TS_IP:-NOT_FOUND}" >> .env
else
    echo "HOST_IP=${LOCAL_IP:-NOT_FOUND}" > .env
    echo "TAILSCALE_IP=${TS_IP:-NOT_FOUND}" >> .env
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
