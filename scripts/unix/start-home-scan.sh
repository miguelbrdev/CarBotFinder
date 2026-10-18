#!/usr/bin/env sh
# Starts home-scan.sh in the background and remembers its PID so that
# stop-home-scan.sh can stop exactly that process. Output goes to state/home-scan.log.
# Arguments are passed through, e.g.: scripts/unix/start-home-scan.sh --portal wallapop
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PIDFILE="$ROOT/state/home-scan.pid"
LOGFILE="$ROOT/state/home-scan.log"

if [ -f "$PIDFILE" ]; then
    OLDPID="$(cat "$PIDFILE")"
    if kill -0 "$OLDPID" 2>/dev/null; then
        echo "Already running (PID $OLDPID). Run stop-home-scan.sh first."
        exit 1
    fi
    rm -f "$PIDFILE"
fi
if [ ! -f "$ROOT/.env" ]; then
    echo "Missing $ROOT/.env (run 'uv run carbotfinder setup-telegram' first)"
    exit 1
fi
mkdir -p "$ROOT/state"

nohup "$ROOT/scripts/unix/home-scan.sh" "$@" >>"$LOGFILE" 2>&1 &
echo $! >"$PIDFILE"
echo "Started CarBotFinder home scan (PID $(cat "$PIDFILE")). Log: $LOGFILE"
echo "Stop it with scripts/unix/stop-home-scan.sh"
