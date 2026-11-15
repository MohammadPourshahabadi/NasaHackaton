#!/usr/bin/env bash
# One-shot setup for the Aboard website on a fresh Ubuntu 22.04/24.04 server (for example a Google Cloud VM).
# Installs Ollama + Llama 3.2 3B, runs the Aboard web server as a service, and serves it with HTTPS via Caddy.
#
# Usage (on the server, from the repository folder):
#   sudo bash website/deploy/setup.sh your-domain.com      # with a domain (HTTPS certificate is automatic)
#   sudo bash website/deploy/setup.sh                       # no domain yet: plain http://SERVER-IP
set -euo pipefail

DOMAIN="${1:-}"
MODEL="${ABOARD_OLLAMA_MODEL:-llama3.2:3b}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_USER="${SUDO_USER:-$(whoami)}"

echo "==> Aboard setup in $REPO (user $RUN_USER, domain '${DOMAIN:-none}')"

echo "==> 1/5 System packages"
apt-get update -y
apt-get install -y python3 python3-pil curl ca-certificates debian-keyring debian-archive-keyring apt-transport-https gnupg

echo "==> 2/5 Ollama and the $MODEL model (about 2 GB, a few minutes)"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
systemctl enable --now ollama
for i in $(seq 1 30); do curl -fs http://127.0.0.1:11434/api/tags >/dev/null && break; sleep 2; done
ollama pull "$MODEL"

echo "==> 3/5 Aboard web service"
cat > /etc/systemd/system/aboard-web.service <<EOF
[Unit]
Description=Aboard website (NASA Space Apps 2026)
After=network-online.target ollama.service
Wants=ollama.service

[Service]
User=$RUN_USER
WorkingDirectory=$REPO/website
Environment=ABOARD_OLLAMA_MODEL=$MODEL
Environment=PYTHONIOENCODING=utf-8
ExecStart=/usr/bin/python3 -B $REPO/website/server.py --host 127.0.0.1 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now aboard-web
systemctl restart aboard-web

echo "==> 4/5 Caddy web server (HTTPS)"
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y && apt-get install -y caddy
fi
SITE="${DOMAIN:-:80}"
if [ -n "$DOMAIN" ]; then SITE="$DOMAIN, www.$DOMAIN"; fi
cat > /etc/caddy/Caddyfile <<EOF
$SITE {
    encode gzip
    reverse_proxy 127.0.0.1:8080 {
        flush_interval -1
    }
}
EOF
systemctl enable --now caddy
systemctl reload caddy || systemctl restart caddy

echo "==> 5/5 Check"
sleep 3
curl -fs http://127.0.0.1:8080/api/health && echo
IP="$(curl -fs -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip 2>/dev/null || curl -fs https://api.ipify.org || true)"
echo
echo "Done. Aboard is running."
if [ -n "$DOMAIN" ]; then
  echo "  Open https://$DOMAIN  (point the domain's A record to $IP first; the certificate appears within a minute after DNS works)"
else
  echo "  Open http://$IP"
fi
echo "  Logs:    journalctl -u aboard-web -f"
echo "  Update:  git pull && sudo systemctl restart aboard-web"
