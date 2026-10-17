from __future__ import annotations

import os
from pathlib import Path

import pytest

from carbotfinder.cli import _load_dotenv, build_parser


def test_load_dotenv_sets_missing_keeps_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nTELEGRAM_BOT_TOKEN='abc:123'\nTELEGRAM_CHAT_ID = \"42\"\nNOT_A_LINE\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "already-set")

    _load_dotenv(env)

    assert os.environ["TELEGRAM_BOT_TOKEN"] == "abc:123"
    assert os.environ["TELEGRAM_CHAT_ID"] == "already-set"


def test_load_dotenv_ignores_missing_file(tmp_path: Path) -> None:
    _load_dotenv(tmp_path / "nope.env")  # no exception


def test_parser_defaults() -> None:
    args = build_parser().parse_args(["run"])
    assert args.config == "config.yaml"
    assert args.dry_run is False and args.seed is False and args.interval == 0
    assert args.portal is None and args.search is None


def test_parser_repeatable_filters() -> None:
    args = build_parser().parse_args(
        ["run", "--portal", "wallapop", "--portal", "cochesnet", "-vv"]
    )
    assert args.portal == ["wallapop", "cochesnet"] and args.verbose == 2
