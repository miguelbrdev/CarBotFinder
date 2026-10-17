from datetime import UTC, datetime, timedelta
from pathlib import Path

from carbotfinder.state import State
from tests.conftest import make_listing


def test_seen_roundtrip(tmp_path: Path) -> None:
    with State(tmp_path / "s.sqlite") as state:
        assert state.is_empty()
        listing = make_listing()
        assert not state.has(listing.key)
        state.add(listing, search="mx5", notified=True)
        assert state.has(listing.key)
        assert not state.is_empty()
        assert state.count() == 1
        state.add(listing, search="mx5", notified=True)  # idempotent
        assert state.count() == 1


def test_state_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "s.sqlite"
    with State(path) as state:
        state.add(make_listing(id="x"), search="mx5", notified=False)
    with State(path) as state:
        assert state.has("fake:x")


def test_portal_health_counters(tmp_path: Path) -> None:
    now = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)
    with State(tmp_path / "s.sqlite") as state:
        assert state.record_failure("wallapop", "boom") == 1
        assert state.record_failure("wallapop", "boom") == 2
        state.record_success("wallapop")
        assert state.record_failure("wallapop", "boom") == 1

        assert state.should_alert("wallapop", timedelta(hours=6), now)
        state.mark_alerted("wallapop", now)
        assert not state.should_alert("wallapop", timedelta(hours=6), now + timedelta(hours=5))
        assert state.should_alert("wallapop", timedelta(hours=6), now + timedelta(hours=6))
