"""Wallapop: undocumented JSON search API used by the web app.

Verified 2026-10-17: ``GET https://api.wallapop.com/api/v3/search`` answers plain requests with
``category_ids=100`` (cars) and structured car attributes. Year filters are not honoured
server-side, so everything is re-checked locally by :mod:`carbotfinder.filters`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from carbotfinder import http
from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.geo import normalise_province
from carbotfinder.models import Listing
from carbotfinder.portals.base import Portal, register

NAME = "wallapop"
SEARCH_URL = "https://api.wallapop.com/api/v3/search"
ITEM_URL = "https://es.wallapop.com/item/{slug}"
CARS_CATEGORY_ID = 100
# Centre of Spain; a 1000 km radius covers the whole peninsula.
_MADRID = (40.4168, -3.7038)
_HEADERS = {"Accept": "application/json", "X-DeviceOS": "0"}


def build_params(search: SearchConfig) -> dict[str, str | int | float]:
    """Wallapop expects the brand/model spelled as on the site (e.g. ``Mazda`` / ``MX-5``)."""
    params: dict[str, str | int | float] = {
        "source": "search_box",
        "category_ids": CARS_CATEGORY_ID,
        "brand": search.make,
        "model": search.model,
        "order_by": "newest",
        "latitude": _MADRID[0],
        "longitude": _MADRID[1],
        "distance_in_km": 1000,
    }
    if search.price_max is not None:
        params["max_sale_price"] = search.price_max
    if search.price_min is not None:
        params["min_sale_price"] = search.price_min
    if search.km_max is not None:
        params["max_km"] = search.km_max
    if search.km_min is not None:
        params["min_km"] = search.km_min
    return params


def parse(payload: dict[str, Any]) -> list[Listing]:
    try:
        items = payload["data"]["section"]["payload"]["items"]
    except (KeyError, TypeError) as exc:
        raise PortalError(NAME, f"unexpected response shape: missing {exc}") from exc
    return [listing for item in items if (listing := _to_listing(item)) is not None]


def _to_listing(item: dict[str, Any]) -> Listing | None:
    slug = item.get("web_slug")
    item_id = item.get("id")
    if not slug or not item_id:
        return None
    attrs = item.get("type_attributes") or {}
    location = item.get("location") or {}
    price = (item.get("price") or {}).get("amount")
    created = item.get("created_at")
    region = location.get("region2") or location.get("region")
    return Listing(
        portal=NAME,
        id=str(item_id),
        title=str(item.get("title") or "").strip(),
        url=ITEM_URL.format(slug=slug),
        price=round(price) if isinstance(price, int | float) else None,
        year=_to_int(attrs.get("year")),
        km=_to_int(attrs.get("km")),
        province=normalise_province(region),
        province_raw=region,
        city=location.get("city"),
        published_at=(
            datetime.fromtimestamp(created / 1000, tz=UTC)
            if isinstance(created, int | float)
            else None
        ),
        seller_type=None,  # not exposed by the search endpoint
        reserved=bool((item.get("reserved") or {}).get("flag", False)),
        raw=item,
    )


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


@register
class Wallapop(Portal):
    name = NAME

    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        response = http.get(client, NAME, SEARCH_URL, params=build_params(search), headers=_HEADERS)
        try:
            payload = response.json()
        except ValueError as exc:
            raise PortalError(NAME, f"non-JSON response: {response.text[:120]!r}") from exc
        return parse(payload)
