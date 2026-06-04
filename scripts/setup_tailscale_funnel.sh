#!/usr/bin/env bash
# Run on your Linux box: expose Ollama to the HF Space via Tailscale Funnel.
# See ../DEPLOY.md § Remote Ollama via Tailscale Funnel.

set -euo pipefail

OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3:1b}"

echo "==> Checking Ollama on :${OLLAMA_PORT}..."
if ! curl -sf "http://127.0.0.1:${OLLAMA_PORT}/api/tags" >/dev/null; then
  echo "Start Ollama first: ollama serve  (or enable the systemd service)"
  exit 1
fi

echo "==> Pulling model ${OLLAMA_MODEL} (skip if already present)..."
ollama pull "${OLLAMA_MODEL}"

echo "==> Enabling Tailscale Funnel on port ${OLLAMA_PORT}..."
echo "    (Requires Tailscale v1.38+ and Funnel enabled for your tailnet.)"
tailscale funnel "${OLLAMA_PORT}"

echo ""
echo "Copy the HTTPS URL from the output above into HF Space secret OLLAMA_BASE_URL"
echo "Example: https://your-host.tail12345.ts.net"
echo "(No OLLAMA_API_KEY needed unless you add a bearer-auth proxy in front of Ollama.)"
echo ""
echo "Verify from another network:"
echo "  ./scripts/verify_ollama_remote.sh https://your-host.tail12345.ts.net"
