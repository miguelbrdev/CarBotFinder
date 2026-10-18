#!/usr/bin/env sh
# Runs CarBotFinder in the foreground until Ctrl+C.
# Default portals: the ones that block GitHub's IPs. Override with arguments,
# e.g.: scripts/unix/home-scan.sh --portal wallapop
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
exec $UV run carbotfinder run $PORTALS --interval 300 -v
