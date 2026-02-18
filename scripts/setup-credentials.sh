#!/usr/bin/env bash
set -euo pipefail

# Setup script for Clawdia credentials
# Works on Mac, Ubuntu, and Raspberry Pi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VOLUME_NAME="clawdia_codex-auth"

echo "Clawdia Credential Setup"
echo "========================"
echo

# Step 1: Check/create .env file
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    if [[ -f "$PROJECT_DIR/.env.example" ]]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo "[+] Created .env from .env.example"
        echo "    Please edit .env with your Telegram bot token and user ID"
        echo
    else
        echo "[!] Warning: .env.example not found"
    fi
else
    echo "[OK] .env file exists"
fi

# Step 2: Create the Docker volume
if docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
    echo "[OK] Docker volume '$VOLUME_NAME' exists"
else
    docker volume create "$VOLUME_NAME"
    echo "[+] Created Docker volume '$VOLUME_NAME'"
fi

# Step 3: Copy Codex auth.json if available
CODEX_AUTH="$HOME/.codex/auth.json"
if [[ -f "$CODEX_AUTH" ]]; then
    echo "[+] Found Codex credentials at $CODEX_AUTH"
    echo "    Copying to Docker volume..."

    docker run --rm \
        -v "$VOLUME_NAME":/creds \
        -v "$HOME/.codex":/src:ro \
        alpine cp /src/auth.json /creds/

    echo "[OK] Credentials copied to volume"
else
    echo
    echo "[!] Codex credentials not found at $CODEX_AUTH"
    echo
    echo "    To authenticate with your ChatGPT plan:"
    echo "    1. Install Codex CLI: npm install -g @openai/codex"
    echo "    2. Run: codex login"
    echo "    3. Re-run this setup: make setup"
    echo
    echo "    Or set OPENAI_API_KEY in .env to use API key auth instead."
fi

echo
echo "Setup complete. Next steps:"
echo "  1. Edit .env with your Telegram credentials"
echo "  2. Run: make build && make up"
echo "  3. Check logs: make logs"
