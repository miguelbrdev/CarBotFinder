from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import httpx
import pytest

from carbotfinder.config import AppConfig, SearchConfig
from carbotfinder.errors import NotifyError, PortalBlocked
from carbotfinder.models import Listing
from carbotfinder.notify import ConsoleNotifier
from carbotfinder.portals.base import Portal
from carbotfinder.runner import run_once
from carbotfinder.state import State
from tests.conftest import make_listing

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class FakePortal(Portal):
    name = "fake"
    listings: ClassVar[list[Listing]] = []
    error: ClassVar[Exception | None] = None

    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        if self.error:
            raise self.error
        return list(self.listings)


class FailingNotifier(ConsoleNotifier):
    def send(self, text: str) -> None:
        raise NotifyError("down")


@pytest.fixture
def env(tmp_path: Path, search: SearchConfig) -> tuple[AppConfig, State, httpx.Client]:
    custom = search.model_copy(
        update={"portals": ["wallapop"]}
    )  # name is irrelevant: factory below
    config = AppConfig(searches=[custom])
    state = State(tmp_path / "s.sqlite")
    return config, state, httpx.Client()


def factory(_name: str) -> Portal:
    return FakePortal()


def test_notifies_new_matches_and_dedups(env: tuple[AppConfig, State, httpx.Client]) -> None:
    config, state, client = env
    FakePortal.error = None
    FakePortal.listings = [make_listing(id="a"), make_listing(id="b", price=99999)]
    notifier = ConsoleNotifier()

    report = run_once(config, state, notifier, client, seed=False, now=NOW, portal_factory=factory)
    assert report.notified == 1 and len(notifier.sent) == 1
    assert report.stats[0].fetched == 2 and report.stats[0].matched == 1

    report = run_once(config, state, notifier, client, seed=False, now=NOW, portal_factory=factory)
    assert report.notified == 0 and len(notifier.sent) == 1


def test_seed_mode_only_notifies_recent(env: tuple[AppConfig, State, httpx.Client]) -> None:
    config, state, client = env
    FakePortal.error = None
    FakePortal.listings = [
        make_listing(id="old", published_at=NOW - timedelta(hours=5)),
        make_listing(id="fresh", published_at=NOW - timedelta(minutes=30)),
        make_listing(id="unknown", published_at=None),
    ]
    notifier = ConsoleNotifier()
    report = run_once(config, state, notifier, client, now=NOW, portal_factory=factory)  # auto seed
    assert report.seed_mode
    assert len(notifier.sent) == 1 and "fresh" not in notifier.sent[0]  # title does not carry id
    assert state.has("fake:old") and state.has("fake:fresh") and state.has("fake:unknown")

    # second run is no longer seed mode and sees nothing new
    report = run_once(config, state, notifier, client, now=NOW, portal_factory=factory)
    assert not report.seed_mode and report.notified == 0


def test_failed_notification_is_retried_next_run(
    env: tuple[AppConfig, State, httpx.Client],
) -> None:
    config, state, client = env
    FakePortal.error = None
    FakePortal.listings = [make_listing(id="a")]
    run_once(config, state, FailingNotifier(), client, seed=False, now=NOW, portal_factory=factory)
    assert not state.has("fake:a")
    ok = ConsoleNotifier()
    run_once(config, state, ok, client, seed=False, now=NOW, portal_factory=factory)
    assert len(ok.sent) == 1 and state.has("fake:a")


def test_portal_error_is_isolated_and_alerted(
    env: tuple[AppConfig, State, httpx.Client],
) -> None:
    config, state, client = env
    FakePortal.listings = []
    FakePortal.error = PortalBlocked("fake", "403")
    notifier = ConsoleNotifier()
    for _ in range(3):
        report = run_once(
            config, state, notifier, client, seed=False, now=NOW, portal_factory=factory
        )
        assert report.errors and "403" in (report.errors[0].error or "")
    # alert sent exactly once after the third consecutive failure
    assert len(notifier.sent) == 1 and "fake" in notifier.sent[0]
    run_once(config, state, notifier, client, seed=False, now=NOW, portal_factory=factory)
    assert len(notifier.sent) == 1  # within the 6h min interval
    FakePortal.error = None


def test_unexpected_exception_is_isolated(env: tuple[AppConfig, State, httpx.Client]) -> None:
    config, state, client = env
    FakePortal.listings = []
    FakePortal.error = KeyError("parser broke")
    report = run_once(
        config, state, ConsoleNotifier(), client, seed=False, now=NOW, portal_factory=factory
    )
    assert report.errors and "parser broke" in (report.errors[0].error or "")
    FakePortal.error = None
