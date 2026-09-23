#!/usr/bin/env bash
set -euo pipefail

redis-server --daemonize yes
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

adapter_pid=""
if [[ "${ORCHESTRATOR_ADAPTER_ENABLED:-false}" == "true" ]]; then
  if [[ -z "${ORCHESTRATOR_BOT_TOKEN:-}" ]]; then
    echo "ORCHESTRATOR_ADAPTER_ENABLED=true requires ORCHESTRATOR_BOT_TOKEN" >&2
    exit 1
  fi
  python manage.py run_instagram_orchestrator_adapter &
  adapter_pid=$!
fi

daphne_pid=""
daphne -b 0.0.0.0 -p "${PORT:-8002}" back_redes_sociales.asgi:application &
daphne_pid=$!

cleanup() {
  kill -TERM "$daphne_pid" 2>/dev/null || true
  if [[ -n "$adapter_pid" ]]; then
    kill -TERM "$adapter_pid" 2>/dev/null || true
  fi
}
trap cleanup TERM INT EXIT

if [[ -n "$adapter_pid" ]]; then
  wait -n "$daphne_pid" "$adapter_pid"
else
  wait "$daphne_pid"
fi
