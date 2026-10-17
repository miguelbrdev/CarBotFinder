"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from carbotfinder import __version__
from carbotfinder.config import load_config, load_telegram_credentials
from carbotfinder.errors import CarBotError
from carbotfinder.http import make_client
from carbotfinder.notify import ConsoleNotifier, Notifier
from carbotfinder.notify.telegram import TelegramNotifier
from carbotfinder.runner import run_once
from carbotfinder.state import State

DEFAULT_STATE = "state/seen.sqlite"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines); does not override existing variables."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="carbotfinder", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="scan portals once (or in a loop) and notify new matches")
    run.add_argument("-c", "--config", default="config.yaml", help="path to config.yaml")
    run.add_argument("--state", default=None, help=f"SQLite state path (default {DEFAULT_STATE})")
    run.add_argument(
        "--dry-run", action="store_true", help="print notifications instead of sending"
    )
    run.add_argument(
        "--seed", action="store_true", help="force seed mode (mark as seen, mostly silent)"
    )
    run.add_argument(
        "--no-seed", action="store_true", help="disable automatic seed mode on empty state"
    )
    run.add_argument(
        "--portal", action="append", default=None, help="only this portal (repeatable)"
    )
    run.add_argument(
        "--search", action="append", default=None, help="only this search (repeatable)"
    )
    run.add_argument(
        "--interval",
        type=int,
        default=0,
        metavar="SECONDS",
        help="keep running every N seconds (for a PC/Raspberry); 0 = run once",
    )
    run.add_argument("-v", "--verbose", action="count", default=0, help="-v info, -vv debug")
    return parser


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING if verbosity == 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _run(args: argparse.Namespace) -> int:
    _load_dotenv(Path(".env"))
    config = load_config(args.config)
    notifier: Notifier
    if args.dry_run:
        notifier = ConsoleNotifier()
    else:
        creds = load_telegram_credentials(config.telegram)
        notifier = TelegramNotifier(creds.token, creds.chat_id)

    state_path = args.state or os.environ.get("CARBOT_STATE_PATH", DEFAULT_STATE)
    seed: bool | None = True if args.seed else (False if args.no_seed else None)

    with State(state_path) as state, make_client() as client:
        while True:
            report = run_once(
                config,
                state,
                notifier,
                client,
                only_portals=args.portal,
                only_searches=args.search,
                seed=seed,
            )
            print(report.summary())
            seed = False if seed else seed  # seed only applies to the first iteration
            if args.interval <= 0:
                break
            time.sleep(args.interval)
    return 0


def _force_utf8_console() -> None:
    """Windows consoles default to a legacy code page that cannot print the emoji we log."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        if args.command == "run":
            return _run(args)
    except CarBotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    parser.error(f"unknown command {args.command}")


if __name__ == "__main__":
    sys.exit(main())
