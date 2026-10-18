#!/usr/bin/env sh
# One pass over the home portals (milanuncios, Autocasión), then exit: a manual refresh.
# New matching ads are sent to Telegram and recorded in the state file.
# Override the portals with arguments, e.g.: scripts/unix/refresh-home-scan.sh --portal wallapop
set -eu
cd "$(dirname "$0")/../.."

if [ "$#" -gt 0 ]; then
    PORTALS="$*"
else
    PORTALS="--portal milanuncios --portal autocasion"
fi

if command -v uv >/dev/null 2>&1; then
    UV="uv"
elif command -v python3 >/dev/null 2>&1; then
    UV="python3 -m uv"
else
    UV="python -m uv"
fi

# shellcheck disable=SC2086
exec $UV run carbotfinder run $PORTALS
