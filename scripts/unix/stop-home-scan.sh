#!/usr/bin/env sh
# Stops the process started by start-home-scan.sh.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PIDFILE="$ROOT/state/home-scan.pid"

if [ ! -f "$PIDFILE" ]; then
    echo "CarBotFinder home scan is not running."
    exit 0
fi
PID="$(cat "$PIDFILE")"
if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PIDFILE"
    echo "CarBotFinder home scan is not running (stale pid file removed)."
    exit 0
fi
# home-scan.sh exec's into uv, which runs python: stop the whole group politely, then firmly.
pkill -TERM -P "$PID" 2>/dev/null || true
kill -TERM "$PID" 2>/dev/null || true
sleep 1
pkill -KILL -P "$PID" 2>/dev/null || true
kill -KILL "$PID" 2>/dev/null || true
rm -f "$PIDFILE"
echo "Stopped CarBotFinder home scan (PID $PID)."
