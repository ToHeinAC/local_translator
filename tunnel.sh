#!/bin/bash
# Expose KI-Übersetzer (port 8530) via a Cloudflare Quick Tunnel (no account needed).
# Copied from local_summarizer/tunnel.sh (commit 68e1b01), adapted to this app's port, paths
# and base path (/trns/).
#
# App and tunnel run in their own session (setsid) and ignore SIGHUP (nohup), so
# both survive closing the terminal. Stop them with `./tunnel.sh stop`.

PORT=8560
LOG=/tmp/translator-tunnel.log
APP_LOG=/tmp/translator-app.log
URL_FILE=/tmp/translator-app-url.txt
CONFIG=~/.cloudflared/config.yml
CRED_FILE=~/.cloudflared/5bc36850-dc39-48be-81ab-fd15f8071bd0.json

APP_PATTERN="streamlit run src/app/ui.py --server.port $PORT"
TUNNEL_PATTERN="cloudflared tunnel --url http://localhost:$PORT"

if [ "$1" = "stop" ]; then
  echo "Stopping KI-Übersetzer and its tunnel (port $PORT)..."
  pkill -f "$TUNNEL_PATTERN" 2>/dev/null || true
  pkill -f "$APP_PATTERN" 2>/dev/null || true
  rm -f "$URL_FILE"
  echo "Stopped."
  exit 0
fi

echo "Starting Cloudflare Quick Tunnel for KI-Übersetzer (port $PORT)"
echo "=================================================================="

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found. Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 1
fi

# Start the app if nothing is listening on PORT yet.
# setsid gives it its own session (no controlling terminal), nohup makes it
# ignore SIGHUP. Together, closing this terminal cannot kill it.
if ! lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "App not running — starting KI-Übersetzer on port $PORT..."
  setsid nohup uv run streamlit run src/app/ui.py --server.port "$PORT" --server.headless true \
    < /dev/null > "$APP_LOG" 2>&1 &
  echo "  App logs: $APP_LOG"
  for i in $(seq 1 30); do
    lsof -ti:"$PORT" >/dev/null 2>&1 && break
    sleep 1
  done
else
  echo "App already running on port $PORT."
fi

# Targeted cleanup of any stale tunnel for THIS port (leaves other tunnels alone)
echo "Cleaning up existing tunnel for port $PORT..."
pkill -f "$TUNNEL_PATTERN" 2>/dev/null || true
sleep 2

# Move named-tunnel config + creds aside to force TRUE quick-tunnel mode
CONFIG_BACKUP=""
CRED_BACKUP=""
if [ -f "$CONFIG" ]; then
  CONFIG_BACKUP="${CONFIG}.quickbackup"
  mv "$CONFIG" "$CONFIG_BACKUP"
  echo "Temporarily moved config.yml"
fi
if [ -f "$CRED_FILE" ]; then
  CRED_BACKUP="${CRED_FILE}.quickbackup"
  mv "$CRED_FILE" "$CRED_BACKUP"
  echo "Temporarily moved tunnel credentials"
fi

# Always restore config files (idempotent)
restore_config() {
  [ -n "$CONFIG_BACKUP" ] && [ -f "$CONFIG_BACKUP" ] && mv "$CONFIG_BACKUP" "$CONFIG"
  [ -n "$CRED_BACKUP" ]   && [ -f "$CRED_BACKUP" ]   && mv "$CRED_BACKUP" "$CRED_FILE"
}

# Start the quick tunnel, detached the same way (both streams to log)
echo "Starting tunnel..."
setsid nohup cloudflared tunnel --url "http://localhost:$PORT" < /dev/null > "$LOG" 2>&1 &

# Give it time to register, then restore config
sleep 8
restore_config
echo "Restored config.yml / credentials"

TUNNEL_PID=$(pgrep -f "$TUNNEL_PATTERN" | head -1)

# Extract URL (retry a few extra seconds in case it is slow)
URL=""
for i in $(seq 1 10); do
  URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)
  [ -n "$URL" ] && break
  sleep 1
done

# Detached watchdog: stop the tunnel once the app stops listening on PORT.
# The tunnel PID is passed as an argument, not embedded as a pkill pattern —
# otherwise the watchdog's own command line would match and it would kill itself.
if [ -n "$TUNNEL_PID" ]; then
  setsid nohup bash -c '
    port=$1; tunnel_pid=$2; url_file=$3
    while lsof -ti:"$port" >/dev/null 2>&1; do sleep 3; done
    kill "$tunnel_pid" 2>/dev/null
    rm -f "$url_file"
  ' _ "$PORT" "$TUNNEL_PID" "$URL_FILE" < /dev/null >> "$LOG" 2>&1 &
fi

echo ""
echo "============================================================"
if [ -n "$URL" ]; then
  URL="$URL/trns/"  # the app is served under baseUrlPath = "trns"
  echo "$URL" > "$URL_FILE"
  echo "TUNNEL READY"
  echo ""
  echo "  Public URL: $URL"
  echo ""
  echo "  (saved to $URL_FILE)"
else
  echo "URL not found. Last 20 log lines:"
  tail -20 "$LOG"
fi
echo "============================================================"
echo "  Tunnel PID: ${TUNNEL_PID:-?} | Log: $LOG"
echo "  App + tunnel keep running after this terminal closes."
echo "  Stop both with: ./tunnel.sh stop"
echo "  (the tunnel also stops on its own once port $PORT closes)"
echo ""
