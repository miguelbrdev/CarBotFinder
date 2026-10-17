"""coches.net: internal JSON gateway used by the web app (``web.gw.coches.net``).

Verified 2026-10-17. ``POST /search`` needs the ``x-adevinta-channel`` / ``x-schibsted-tenant``
headers and numeric make/model ids (names alone return nothing). Only ``relevance`` sorting is
accepted, so filters are pushed server-side and the page size is large enough to cover every
matching ad in one request for a normal search.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from carbotfinder import http
from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.geo import normalise_province
from carbotfinder.models import Listing
from carbotfinder.portals._embedded import fold, parse_int_text, parse_iso_datetime
from carbotfinder.portals.base import Portal, register

log = logging.getLogger(__name__)

NAME = "cochesnet"
SITE_URL = "https://www.coches.net"
API_URL = "https://web.gw.coches.net"
SEARCH_URL = f"{API_URL}/search"
MAKES_URL = f"{API_URL}/makes"
MODELS_URL = f"{API_URL}/models"
CARS_CATEGORY_ID = 2500
PAGE_SIZE = 100
_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": SITE_URL,
    "Referer": f"{SITE_URL}/",
    "x-adevinta-channel": "web-desktop",
    "x-schibsted-tenant": "coches",
}
# Known ids, so the common case needs no lookup requests. Keys are (make, model) folded.
_KNOWN_IDS: dict[tuple[str, str], tuple[int, int]] = {
    ("mazda", "mx5"): (27, 237),
}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(text))


def build_body(search: SearchConfig, make_id: int, model_id: int) -> dict[str, Any]:
    filters: dict[str, Any] = {
        "categories": {"category1Ids": [CARS_CATEGORY_ID]},
        "vehicles": [{"makeId": make_id, "modelId": model_id}],
    }
    if search.price_min is not None or search.price_max is not None:
        filters["price"] = {"from": search.price_min, "to": search.price_max}
    if search.km_min is not None or search.km_max is not None:
        filters["km"] = {"from": search.km_min, "to": search.km_max}
    if search.year_min is not None or search.year_max is not None:
        filters["year"] = {"from": search.year_min, "to": search.year_max}
    return {
        "pagination": {"page": 1, "size": PAGE_SIZE},
        "sort": {"order": "desc", "term": "relevance"},
        "filters": filters,
    }


def parse(payload: dict[str, Any]) -> list[Listing]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise PortalError(NAME, "unexpected response shape: missing items")
    return [listing for item in items if (listing := _to_listing(item)) is not None]


def _to_listing(item: dict[str, Any]) -> Listing | None:
    item_id = item.get("id")
    path = item.get("url")
    if not item_id or not path:
        return None
    price = item.get("price") or {}
    location = item.get("location") or {}
    province = location.get("mainProvince") or item.get("mainProvince")
    published = parse_iso_datetime(item.get("publishedDate")) or parse_iso_datetime(
        item.get("creationDate")
    )
    return Listing(
        portal=NAME,
        id=str(item_id),
        title=str(item.get("title") or "").strip(),
        url=f"{SITE_URL}{path}" if str(path).startswith("/") else str(path),
        price=parse_int_text(price.get("amount")),
        year=parse_int_text(item.get("year")),
        km=parse_int_text(item.get("km")),
        province=normalise_province(province),
        province_raw=province,
        city=location.get("cityLiteral"),
        published_at=published,
        seller_type="dealer" if item.get("isProfessional") else "private",
        reserved=bool(price.get("hasReservation", False)),
        raw=item,
    )


def resolve_ids(search: SearchConfig, client: httpx.Client) -> tuple[int, int]:
    key = (_key(search.make), _key(search.model))
    if key in _KNOWN_IDS:
        return _KNOWN_IDS[key]
    makes = _get_items(client, MAKES_URL, {"categoryId": CARS_CATEGORY_ID})
    make_id = _match(makes, key[0])
    if make_id is None:
        raise PortalError(NAME, f"make {search.make!r} not found in coches.net makes list")
    models = _get_items(client, MODELS_URL, {"categoryId": CARS_CATEGORY_ID, "makeId": make_id})
    model_id = _match(models, key[1])
    if model_id is None:
        raise PortalError(NAME, f"model {search.model!r} not found for make {search.make!r}")
    _KNOWN_IDS[key] = (make_id, model_id)
    log.info("%s: resolved %s/%s to ids %s/%s", NAME, search.make, search.model, make_id, model_id)
    return make_id, model_id


def _get_items(client: httpx.Client, url: str, params: dict[str, int]) -> list[dict[str, Any]]:
    response = http.get(client, NAME, url, params=params, headers=_HEADERS)
    try:
        items = response.json()["items"]
    except (ValueError, KeyError, TypeError) as exc:
        raise PortalError(NAME, f"unexpected lookup response from {url}: {exc}") from exc
    return [i for i in items if isinstance(i, dict)]


def _match(items: list[dict[str, Any]], wanted: str) -> int | None:
    for item in items:
        label = item.get("label") or item.get("name") or ""
        if _key(str(label)) == wanted and isinstance(item.get("id"), int):
            return int(item["id"])
    return None


@register
class CochesNet(Portal):
    name = NAME

    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        make_id, model_id = resolve_ids(search, client)
        body = build_body(search, make_id, model_id)
        try:
            response = client.post(SEARCH_URL, json=body, headers=_HEADERS)
        except httpx.HTTPError as exc:
            raise PortalError(NAME, f"network error: {exc}") from exc
        if http.looks_blocked(response):
            raise PortalError(NAME, f"blocked (HTTP {response.status_code})")
        if response.status_code != 200:
            raise PortalError(NAME, f"HTTP {response.status_code}: {response.text[:120]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise PortalError(NAME, f"non-JSON response: {response.text[:120]!r}") from exc
        return parse(payload)
