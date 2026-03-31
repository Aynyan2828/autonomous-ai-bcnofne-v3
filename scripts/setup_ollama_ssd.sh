#!/bin/bash
# Ollama Model Path Setup for Raspberry Pi SSD
# This script sets the OLLAMA_MODELS environment variable to use an SSD partition.

NEW_MODELS_PATH="/mnt/ssd/AI/ai_models"

echo "============================================"
echo " Ollama SSD Setup Utility "
echo "============================================"
echo "Target Path: $NEW_MODELS_PATH"

# 1. Create the directory if it doesn't exist
if [ ! -d "$NEW_MODELS_PATH" ]; then
    echo "[1/3] Creating directory..."
    sudo mkdir -p "$NEW_MODELS_PATH"
    # Set owner to the current user so Ollama can write to it
    sudo chown -R $USER:$USER "$NEW_MODELS_PATH"
else
    echo "[1/3] Directory already exists."
fi

# 2. Configure systemd to use the new path
echo "[2/3] Configuring systemd override..."
SERVICE_OVERRIDE_DIR="/etc/systemd/system/ollama.service.d"
sudo mkdir -p "$SERVICE_OVERRIDE_DIR"

cat <<EOF | sudo tee "$SERVICE_OVERRIDE_DIR/override.conf" > /dev/null
[Service]
Environment="OLLAMA_MODELS=$NEW_MODELS_PATH"
EOF

# 3. Reload systemd and restart Ollama
echo "[3/3] Reloading and Restarting Ollama..."
sudo systemctl daemon-reload
sudo systemctl restart ollama

echo "============================================"
echo " Setup Complete! "
echo "============================================"
echo "Ollama is now configured to store models in $NEW_MODELS_PATH"
echo "Current models (on SSD):"
ollama list
