"""milanuncios: server-rendered listing page with ``window.__INITIAL_PROPS__``.

Verified 2026-10-17. ``orden=date`` and ``hasta`` (max price) are honoured in the URL; mileage and
year filters are applied locally.
"""

from __future__ import annotations

from typing import Any

import httpx

from carbotfinder import http
from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.geo import normalise_province
from carbotfinder.models import Listing, SellerType
from carbotfinder.portals._embedded import (
    extract_initial_props,
    fold,
    parse_int_text,
    parse_iso_datetime,
    slugify,
)
from carbotfinder.portals.base import Portal, register

NAME = "milanuncios"
BASE_URL = "https://www.milanuncios.com"
# (make, model) lower-case -> (make_slug, model_slug) when slugify() is not enough.
_SLUG_OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {}
_SELLER: dict[str, SellerType] = {"private": "private", "professional": "dealer"}


def build_url(search: SearchConfig) -> tuple[str, dict[str, str | int | float]]:
    key = (search.make.lower(), search.model.lower())
    make_slug, model_slug = _SLUG_OVERRIDES.get(key, (slugify(search.make), slugify(search.model)))
    url = f"{BASE_URL}/{make_slug}-de-segunda-mano/{model_slug}.htm"
    params: dict[str, str | int | float] = {"orden": "date", "fromSearch": 1}
    if search.price_max is not None:
        params["hasta"] = search.price_max
    if search.price_min is not None:
        params["desde"] = search.price_min
    return url, params


def parse(html: str) -> list[Listing]:
    data = extract_initial_props(NAME, html)
    try:
        ads = data["adListPagination"]["adList"]["ads"]
    except (KeyError, TypeError) as exc:
        raise PortalError(NAME, f"unexpected page shape: missing {exc}") from exc
    return [listing for ad in ads if (listing := _to_listing(ad)) is not None]


def _to_listing(ad: dict[str, Any]) -> Listing | None:
    ad_id = ad.get("id")
    path = ad.get("url")
    if not ad_id or not path:
        return None
    tags = {fold(str(t.get("type", ""))): t.get("text") for t in ad.get("tags") or []}
    location = ad.get("location") or {}
    province = (location.get("province") or ad.get("province") or {}).get("name")
    city = (location.get("city") or ad.get("city") or {}).get("name")
    price = ((ad.get("price") or {}).get("cashPrice") or {}).get("value")
    reserved_flag = str(ad.get("isReserved") or "").upper()
    return Listing(
        portal=NAME,
        id=str(ad_id),
        title=str(ad.get("title") or "").strip(),
        url=f"{BASE_URL}{path}" if path.startswith("/") else str(path),
        price=parse_int_text(price),
        year=parse_int_text(tags.get("ano")),
        km=parse_int_text(tags.get("kilometros")),
        province=normalise_province(province),
        province_raw=province,
        city=city,
        published_at=parse_iso_datetime(ad.get("publishDate")),
        seller_type=_SELLER.get(str(ad.get("sellerType") or "").lower()),
        reserved=reserved_flag not in ("", "RELEASED"),
        raw=ad,
    )


@register
class Milanuncios(Portal):
    name = NAME

    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        url, params = build_url(search)
        response = http.get(client, NAME, url, params=params)
        return parse(response.text)
