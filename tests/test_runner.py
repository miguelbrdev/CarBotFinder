from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from carbotfinder.config import AppConfig, SearchConfig
from carbotfinder.errors import NotifyError, PortalBlocked
from carbotfinder.models import Listing
from carbotfinder.notify import ConsoleNotifier
from carbotfinder.portals.base import Portal
from carbotfinder.runner import RunReport, run_once
from carbotfinder.state import State
from tests.conftest import make_listing

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class FakePortal(Portal):
    """Instance-scoped stand-in for a portal: no shared state between tests."""

    name = "fake"

    def __init__(self, listings: list[Listing], error: Exception | None = None) -> None:
        self.listings = listings
        self.error = error

    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        if self.error:
            raise self.error
        return list(self.listings)


class FailingNotifier(ConsoleNotifier):
    def send(self, text: str) -> None:
        raise NotifyError("down")


@dataclass
class Harness:
    """Everything a runner test needs, wired to one FakePortal instance."""

    config: AppConfig
    state: State
    client: httpx.Client
    portal: FakePortal
    notifier: ConsoleNotifier = field(default_factory=ConsoleNotifier)

    def run(
        self, *, seed: bool | None = False, notifier: ConsoleNotifier | None = None
    ) -> RunReport:
        return self.run_with(notifier or self.notifier, seed=seed)

    def run_with(self, notifier: ConsoleNotifier, *, seed: bool | None = False) -> RunReport:
        return run_once(
            self.config,
            self.state,
            notifier,
            self.client,
            seed=seed,
            now=NOW,
            portal_factory=lambda _name: self.portal,
        )


@pytest.fixture
def harness(tmp_path: Path, search: SearchConfig) -> Iterator[Callable[..., Harness]]:
    """Factory fixture: ``harness(listings=[...], error=...)`` builds an isolated run harness."""
    # The configured portal name is irrelevant: portal_factory always returns the fake.
    config = AppConfig(searches=[search.model_copy(update={"portals": ["wallapop"]})])
    state = State(tmp_path / "s.sqlite")
    client = httpx.Client()

    def build(listings: list[Listing] | None = None, error: Exception | None = None) -> Harness:
        return Harness(config, state, client, FakePortal(listings or [], error))

    yield build
    state.close()
    client.close()


def test_notifies_new_matches_and_dedups(harness: Callable[..., Harness]) -> None:
    h = harness(listings=[make_listing(id="a"), make_listing(id="b", price=99999)])

    report = h.run()
    assert report.notified == 1 and len(h.notifier.sent) == 1
    assert report.stats[0].fetched == 2 and report.stats[0].matched == 1

    report = h.run()
    assert report.notified == 0 and len(h.notifier.sent) == 1


def test_seed_mode_only_notifies_recent(harness: Callable[..., Harness]) -> None:
    h = harness(
        listings=[
            make_listing(id="old", published_at=NOW - timedelta(hours=5)),
            make_listing(id="fresh", published_at=NOW - timedelta(minutes=30)),
            make_listing(id="unknown", published_at=None),
        ]
    )
    report = h.run(seed=None)  # empty state -> automatic seed mode
    assert report.seed_mode
    assert len(h.notifier.sent) == 1
    assert all(h.state.has(f"fake:{i}") for i in ("old", "fresh", "unknown"))

    report = h.run(seed=None)  # state is populated now -> normal mode, nothing new
    assert not report.seed_mode and report.notified == 0


def test_failed_notification_is_retried_next_run(harness: Callable[..., Harness]) -> None:
    h = harness(listings=[make_listing(id="a")])
    h.run_with(FailingNotifier())
    assert not h.state.has("fake:a")

    h.run()
    assert len(h.notifier.sent) == 1 and h.state.has("fake:a")


def test_portal_error_is_isolated_and_alerted(harness: Callable[..., Harness]) -> None:
    h = harness(error=PortalBlocked("fake", "403"))
    for _ in range(3):
        report = h.run()
        assert report.errors and "403" in (report.errors[0].error or "")
    # alert sent exactly once, after the third consecutive failure
    assert len(h.notifier.sent) == 1 and "fake" in h.notifier.sent[0]

    h.run()
    assert len(h.notifier.sent) == 1  # still inside the minimum alert interval


def test_unexpected_exception_is_isolated(harness: Callable[..., Harness]) -> None:
    h = harness(error=KeyError("parser broke"))
    report = h.run()
    assert report.errors and "parser broke" in (report.errors[0].error or "")
    assert "ERROR" in report.summary()
