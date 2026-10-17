"""Orchestrates one scan: fetch -> filter -> de-duplicate -> notify, per search and portal."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx

from carbotfinder import filters
from carbotfinder.config import AppConfig, SearchConfig
from carbotfinder.errors import CarBotError, NotifyError
from carbotfinder.models import Listing
from carbotfinder.notify import Notifier
from carbotfinder.notify.telegram import format_listing, format_portal_error
from carbotfinder.portals import Portal, get_portal
from carbotfinder.state import State

log = logging.getLogger(__name__)

PortalFactory = Callable[[str], Portal]


@dataclass(slots=True)
class PortalStats:
    search: str
    portal: str
    fetched: int = 0
    matched: int = 0
    new: int = 0
    notified: int = 0
    error: str | None = None


@dataclass(slots=True)
class RunReport:
    seed_mode: bool
    stats: list[PortalStats] = field(default_factory=list)

    @property
    def notified(self) -> int:
        return sum(s.notified for s in self.stats)

    @property
    def errors(self) -> list[PortalStats]:
        return [s for s in self.stats if s.error]

    def summary(self) -> str:
        lines = [f"seed_mode={self.seed_mode}"]
        for s in self.stats:
            status = (
                f"ERROR {s.error}"
                if s.error
                else (f"fetched={s.fetched} matched={s.matched} new={s.new} notified={s.notified}")
            )
            lines.append(f"[{s.search}/{s.portal}] {status}")
        return "\n".join(lines)


def run_once(
    config: AppConfig,
    state: State,
    notifier: Notifier,
    client: httpx.Client,
    *,
    only_portals: Sequence[str] | None = None,
    only_searches: Sequence[str] | None = None,
    seed: bool | None = None,
    now: datetime | None = None,
    portal_factory: PortalFactory = get_portal,
) -> RunReport:
    now = now or datetime.now(UTC)
    seed_mode = seed if seed is not None else state.is_empty()
    if seed_mode:
        log.info(
            "seed mode: only listings published within the last %dh will be notified",
            config.defaults.seed_window_hours,
        )
    seed_cutoff = now - timedelta(hours=config.defaults.seed_window_hours)
    report = RunReport(seed_mode=seed_mode)

    for search in config.searches:
        if only_searches and search.name not in only_searches:
            continue
        excluded = config.excluded_provinces_for(search)
        for portal_name in config.portals_for(search):
            if only_portals and portal_name not in only_portals:
                continue
            stats = PortalStats(search=search.name, portal=portal_name)
            report.stats.append(stats)
            try:
                listings = portal_factory(portal_name).fetch(search, client)
            except CarBotError as exc:
                _handle_portal_failure(config, state, notifier, portal_name, str(exc), now)
                stats.error = str(exc)
                continue
            except Exception as exc:
                log.exception("%s: unexpected error", portal_name)
                _handle_portal_failure(config, state, notifier, portal_name, repr(exc), now)
                stats.error = repr(exc)
                continue

            state.record_success(portal_name)
            stats.fetched = len(listings)
            matched = filters.apply(listings, search, excluded)
            stats.matched = len(matched)
            _log_rejections(listings, search, excluded)

            for listing in matched:
                if state.has(listing.key):
                    continue
                stats.new += 1
                should_notify = not seed_mode or _is_recent(listing, seed_cutoff)
                if should_notify:
                    try:
                        notifier.send(format_listing(listing, search.name))
                    except NotifyError as exc:
                        log.error("notification failed for %s: %s", listing.key, exc)
                        continue  # not persisted -> retried next run
                    stats.notified += 1
                state.add(listing, search=search.name, notified=should_notify, now=now)
    log.info("run finished")
    return report


def _is_recent(listing: Listing, cutoff: datetime) -> bool:
    if listing.published_at is None:
        return False
    published = listing.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return published >= cutoff


def _log_rejections(
    listings: Sequence[Listing], search: SearchConfig, excluded: frozenset[str]
) -> None:
    if not log.isEnabledFor(logging.DEBUG):
        return
    for listing in listings:
        result = filters.check(listing, search, excluded)
        if not result.ok:
            log.debug("reject %s (%s): %s", listing.key, listing.title[:50], result.reason)


def _handle_portal_failure(
    config: AppConfig,
    state: State,
    notifier: Notifier,
    portal: str,
    error: str,
    now: datetime,
) -> None:
    failures = state.record_failure(portal, error)
    log.error("%s failed (%d consecutive): %s", portal, failures, error)
    threshold = config.defaults.error_alert_after_failures
    interval = timedelta(hours=config.defaults.error_alert_min_interval_hours)
    if failures >= threshold and state.should_alert(portal, interval, now):
        try:
            notifier.send(format_portal_error(portal, failures, error))
            state.mark_alerted(portal, now)
        except NotifyError as exc:
            log.error("could not send error alert: %s", exc)
