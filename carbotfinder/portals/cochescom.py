"""coches.com: Next.js listing page with ``__NEXT_DATA__`` (mostly dealer stock).

Verified 2026-10-17. Protected by Imperva/Incapsula but served plain HTML to a browser-like GET.
Ad URLs are taken from the page's anchors (``...htm?id=<visibleId>``) with a constructed fallback.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

import httpx

from carbotfinder import http
from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.geo import normalise_province
from carbotfinder.models import Listing, SellerType
from carbotfinder.portals._embedded import (
    extract_next_data,
    parse_int_text,
    parse_iso_datetime,
    slugify,
)
from carbotfinder.portals.base import Portal, register

NAME = "cochescom"
BASE_URL = "https://www.coches.com"
_SLUG_OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {}
_AD_LINK = re.compile(r'href="([^"]*\?id=([A-Za-z0-9_-]+))"')


def build_url(search: SearchConfig) -> str:
    key = (search.make.lower(), search.model.lower())
    make_slug, model_slug = _SLUG_OVERRIDES.get(key, (slugify(search.make), slugify(search.model)))
    return f"{BASE_URL}/coches-segunda-mano/{make_slug}-{model_slug}.htm"


def parse(html: str) -> list[Listing]:
    data = extract_next_data(NAME, html)
    try:
        ads = data["props"]["pageProps"]["classifieds"]["classifiedList"]
    except (KeyError, TypeError) as exc:
        raise PortalError(NAME, f"unexpected page shape: missing {exc}") from exc
    links = {visible_id: html_lib.unescape(href) for href, visible_id in _AD_LINK.findall(html)}
    return [listing for ad in ads if (listing := _to_listing(ad, links)) is not None]


def _to_listing(ad: dict[str, Any], links: dict[str, str]) -> Listing | None:
    visible_id = ad.get("visibleId") or ad.get("id")
    if not visible_id:
        return None
    make = str((ad.get("make") or {}).get("name") or "").strip()
    model = str((ad.get("model") or {}).get("name") or "").strip()
    version = str((ad.get("version") or {}).get("name") or "").strip()
    title = " ".join(part for part in (make.title(), model, version) if part)

    offer = (ad.get("priceOffer") or {}).get("amount")
    list_price = (ad.get("price") or {}).get("amount")
    price = parse_int_text(offer) if offer else parse_int_text(list_price)

    province = (ad.get("currentProvince") or {}).get("name")
    year = parse_int_text((ad.get("registration") or {}).get("year"))
    url = links.get(str(visible_id))
    if url is None:
        slug = slugify(f"{make} {model}")
        url = f"{BASE_URL}/coches-segunda-mano/ocasion-{slug}.htm?id={visible_id}"
    elif url.startswith("/"):
        url = f"{BASE_URL}{url}"
    seller: SellerType = "dealer" if ad.get("dealer") or ad.get("dealerId") else "private"
    return Listing(
        portal=NAME,
        id=str(visible_id),
        title=title,
        url=url,
        price=price,
        year=year,
        km=parse_int_text((ad.get("mileage") or {}).get("amount")),
        province=normalise_province(province),
        province_raw=province,
        city=None,
        published_at=parse_iso_datetime(ad.get("createdAt")),
        seller_type=seller,
        reserved=False,
        raw=ad,
    )


@register
class CochesCom(Portal):
    name = NAME

    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        response = http.get(client, NAME, build_url(search))
        return parse(response.text)
