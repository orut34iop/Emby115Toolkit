#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PORT=8765
HOST=127.0.0.1
NO_OPEN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Port|--port)
      PORT="$2"
      shift 2
      ;;
    -BindAddress|--host)
      HOST="$2"
      shift 2
      ;;
    -NoOpen)
      NO_OPEN=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

BASE_URL="http://${HOST}:${PORT}"
OPEN_HOST="$HOST"
if [[ "$HOST" == "0.0.0.0" || "$HOST" == "::" ]]; then
  OPEN_HOST="127.0.0.1"
fi

if curl -s -f "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "Emby115Toolkit V2 WebUI is already running: ${BASE_URL}"
  [[ "$NO_OPEN" == false ]] && open "http://${OPEN_HOST}:${PORT}/"
  exit 0
fi

echo "Starting Emby115Toolkit V2 WebUI backend..."
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

$PYTHON main.py --serve-web --host "$HOST" --port "$PORT" &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT

for attempt in {1..60}; do
  if ! kill -0 $PID 2>/dev/null; then
    echo "WebUI backend exited early."
    exit 1
  fi
  if curl -s -f "${BASE_URL}/health" >/dev/null 2>&1; then
    echo "Emby115Toolkit V2 WebUI is ready: ${BASE_URL}"
    [[ "$NO_OPEN" == false ]] && open "http://${OPEN_HOST}:${PORT}/"
    wait $PID
    exit 0
  fi
  sleep 0.5
done

echo "Timed out waiting for WebUI health check: ${BASE_URL}/health"
exit 1
