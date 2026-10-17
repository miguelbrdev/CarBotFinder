"""Pure filtering of listings against a search. No I/O here.

Policy for missing data: a missing price rejects the listing (an ad without a price is not
actionable); a missing year, mileage, province or seller type passes, so an uncertain ad is
shown rather than silently dropped.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from carbotfinder.config import SearchConfig
from carbotfinder.models import Listing


@dataclass(frozen=True, slots=True)
class FilterResult:
    ok: bool
    reason: str | None = None

    @classmethod
    def accept(cls) -> FilterResult:
        return cls(True, None)

    @classmethod
    def reject(cls, reason: str) -> FilterResult:
        return cls(False, reason)


def _word_pattern(words: Iterable[str]) -> re.Pattern[str] | None:
    cleaned = [w.strip() for w in words if w.strip()]
    if not cleaned:
        return None
    alternatives = "|".join(re.escape(w) for w in cleaned)
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.IGNORECASE)


def check(
    listing: Listing, search: SearchConfig, excluded_provinces: frozenset[str]
) -> FilterResult:
    """Return whether ``listing`` satisfies ``search`` and, if not, the first failing rule."""
    if listing.reserved and not search.include_reserved:
        return FilterResult.reject("reserved")

    if listing.price is None:
        return FilterResult.reject("price_missing")
    if search.price_max is not None and listing.price > search.price_max:
        return FilterResult.reject(f"price {listing.price} > {search.price_max}")
    if search.price_min is not None and listing.price < search.price_min:
        return FilterResult.reject(f"price {listing.price} < {search.price_min}")

    if listing.year is not None:
        if search.year_min is not None and listing.year < search.year_min:
            return FilterResult.reject(f"year {listing.year} < {search.year_min}")
        if search.year_max is not None and listing.year > search.year_max:
            return FilterResult.reject(f"year {listing.year} > {search.year_max}")

    if listing.km is not None:
        if search.km_max is not None and listing.km > search.km_max:
            return FilterResult.reject(f"km {listing.km} > {search.km_max}")
        if search.km_min is not None and listing.km < search.km_min:
            return FilterResult.reject(f"km {listing.km} < {search.km_min}")

    if listing.province is not None and listing.province in excluded_provinces:
        return FilterResult.reject(f"province {listing.province} excluded")

    if listing.seller_type is not None and listing.seller_type not in search.seller_types:
        return FilterResult.reject(f"seller {listing.seller_type} not wanted")

    exclude = _word_pattern(search.title_exclude)
    if exclude is not None and exclude.search(listing.title):
        return FilterResult.reject("title matches exclude list")

    include = _word_pattern(search.title_include)
    if include is not None and not include.search(listing.title):
        return FilterResult.reject("title lacks required word")

    return FilterResult.accept()


def apply(
    listings: Iterable[Listing], search: SearchConfig, excluded_provinces: frozenset[str]
) -> list[Listing]:
    return [listing for listing in listings if check(listing, search, excluded_provinces).ok]
