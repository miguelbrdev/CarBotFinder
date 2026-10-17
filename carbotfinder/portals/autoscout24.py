"""AutoScout24.es: Next.js listing page with ``__NEXT_DATA__``; filters and sorting in the URL.

Verified 2026-10-17. The listing has no publication date, so de-duplication relies on ids and
seed mode cannot tell fresh ads apart (they are marked seen silently on the first run).
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from carbotfinder import http
from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.geo import province_display, province_from_postal_code
from carbotfinder.models import Listing, SellerType
from carbotfinder.portals._embedded import extract_next_data, parse_int_text, slugify
from carbotfinder.portals.base import Portal, register

NAME = "autoscout24"
BASE_URL = "https://www.autoscout24.es"
_SLUG_OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {}
_SELLER: dict[str, SellerType] = {"privateseller": "private", "dealer": "dealer"}
_REGISTRATION = re.compile(r"(\d{4})")


def build_url(search: SearchConfig) -> tuple[str, dict[str, str | int | float]]:
    key = (search.make.lower(), search.model.lower())
    make_slug, model_slug = _SLUG_OVERRIDES.get(key, (slugify(search.make), slugify(search.model)))
    url = f"{BASE_URL}/lst/{make_slug}/{model_slug}"
    params: dict[str, str | int | float] = {
        "atype": "C",  # cars
        "cy": "E",  # Spain
        "ustate": "N,U",  # new + used
        "sort": "age",
        "desc": 1,
    }
    if search.price_max is not None:
        params["priceto"] = search.price_max
    if search.price_min is not None:
        params["pricefrom"] = search.price_min
    if search.km_max is not None:
        params["kmto"] = search.km_max
    if search.km_min is not None:
        params["kmfrom"] = search.km_min
    if search.year_min is not None:
        params["fregfrom"] = search.year_min
    if search.year_max is not None:
        params["fregto"] = search.year_max
    return url, params


def parse(html: str) -> list[Listing]:
    data = extract_next_data(NAME, html)
    try:
        listings = data["props"]["pageProps"]["listings"]
    except (KeyError, TypeError) as exc:
        raise PortalError(NAME, f"unexpected page shape: missing {exc}") from exc
    return [listing for item in listings if (listing := _to_listing(item)) is not None]


def _build_title(title: str, make: str, version: str) -> str:
    """``("Mazda MX-5", "Mazda", "MX-5 Roadster 2.0 Sportive Sportive")`` ->
    ``"Mazda MX-5 Roadster 2.0 Sportive"``."""
    base = version.strip() or title.strip()
    if make and not base.lower().startswith(make.lower()):
        base = f"{make} {base}"
    words: list[str] = []
    for word in base.split():
        if not words or words[-1].lower() != word.lower():
            words.append(word)
    return " ".join(words)


def _to_listing(item: dict[str, Any]) -> Listing | None:
    item_id = item.get("id")
    path = item.get("url")
    if not item_id or not path:
        return None
    vehicle = item.get("vehicle") or {}
    location = item.get("location") or {}
    seller = item.get("seller") or {}
    registration = str((item.get("tracking") or {}).get("firstRegistration") or "")
    year_match = _REGISTRATION.search(registration)
    title = _build_title(
        str(item.get("title") or ""),
        str(vehicle.get("make") or ""),
        str(vehicle.get("modelVersionInput") or ""),
    )
    zip_code = location.get("zip")
    return Listing(
        portal=NAME,
        id=str(item_id),
        title=title,
        url=f"{BASE_URL}{path}" if str(path).startswith("/") else str(path),
        price=parse_int_text((item.get("price") or {}).get("priceRaw")),
        year=int(year_match.group(1)) if year_match else None,
        km=parse_int_text(vehicle.get("mileageInKm")),
        province=province_from_postal_code(zip_code),
        province_raw=province_display(province_from_postal_code(zip_code)),
        city=location.get("city"),
        published_at=None,
        seller_type=_SELLER.get(str(seller.get("type") or "").lower()),
        reserved=False,
        raw=item,
    )


@register
class AutoScout24(Portal):
    name = NAME

    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        url, params = build_url(search)
        response = http.get(client, NAME, url, params=params)
        return parse(response.text)
