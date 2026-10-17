"""Autocasión: classic server-rendered HTML cards (``<article class="anuncio">``), dealer stock.

Verified 2026-10-17. Each card carries ``data-ad`` (id), a link, ``<h2>`` title,
``<p class="precio">`` and a ``<ul class="supplementary">`` with year, fuel, mileage, province
and town. A JSON-LD block duplicates part of it but lacks the province, so the cards are the
source of truth.
"""

from __future__ import annotations

import html as html_lib
import re

import httpx

from carbotfinder import http
from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.geo import normalise_province
from carbotfinder.models import Listing
from carbotfinder.portals._embedded import parse_int_text, slugify
from carbotfinder.portals.base import Portal, register

NAME = "autocasion"
BASE_URL = "https://www.autocasion.com"
_SLUG_OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {}

_ARTICLE = re.compile(r'<article[^>]*class="[^"]*\banuncio\b[^"]*"[^>]*>(.*?)</article>', re.S)
_AD_ID = re.compile(r'data-ad="(\d+)"')
_LINK = re.compile(r'<a\s+href="([^"]+)"')
_TITLE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
_PRICE = re.compile(r'<p class="precio">(.*?)</p>', re.S)
_SUPPLEMENTARY = re.compile(r'<ul class="supplementary">(.*?)</ul>', re.S)
_LI = re.compile(r"<li([^>]*)>(.*?)</li>", re.S)
_TAGS = re.compile(r"<[^>]+>")
_YEAR = re.compile(r"^\s*(19|20)\d{2}\s*$")


def build_url(search: SearchConfig) -> tuple[str, dict[str, str | int | float]]:
    key = (search.make.lower(), search.model.lower())
    make_slug, model_slug = _SLUG_OVERRIDES.get(key, (slugify(search.make), slugify(search.model)))
    url = f"{BASE_URL}/coches-segunda-mano/{make_slug}-{model_slug}-ocasion"
    return url, {"orden": "fecha"}


def _text(fragment: str) -> str:
    return html_lib.unescape(_TAGS.sub(" ", fragment)).strip()


def parse(html: str) -> list[Listing]:
    articles = _ARTICLE.findall(html)
    if not articles and "supplementary" not in html and "anuncio" not in html:
        raise PortalError(NAME, "no listing cards found in page")
    return [listing for article in articles if (listing := _to_listing(article)) is not None]


def _to_listing(article: str) -> Listing | None:
    id_match = _AD_ID.search(article)
    link_match = _LINK.search(article)
    title_match = _TITLE.search(article)
    if not (id_match and link_match and title_match):
        return None
    price_match = _PRICE.search(article)
    price = parse_int_text(_text(price_match.group(1)).split("€")[0]) if price_match else None

    year: int | None = None
    km: int | None = None
    city: str | None = None
    others: list[str] = []
    supplementary = _SUPPLEMENTARY.search(article)
    for attrs, body in _LI.findall(supplementary.group(1)) if supplementary else []:
        text = _text(body)
        if not text:
            continue
        if "municipio" in attrs:
            city = text
        elif _YEAR.match(text) and year is None:
            year = int(text)
        elif "km" in text.lower():
            km = parse_int_text(text)
        else:
            others.append(text)
    # supplementary order is: year, fuel, km, province[, town] -> province is the last leftover
    province = others[-1] if len(others) >= 2 else None

    path = html_lib.unescape(link_match.group(1))
    return Listing(
        portal=NAME,
        id=id_match.group(1),
        title=_text(title_match.group(1)),
        url=f"{BASE_URL}{path}" if path.startswith("/") else path,
        price=price,
        year=year,
        km=km,
        province=normalise_province(province),
        province_raw=province,
        city=city,
        published_at=None,
        seller_type="dealer"
        if "con-concesionario" in article[:400] or "concesionario" in article
        else "private",
        reserved=False,
        raw={"article": article[:2000]},
    )


@register
class Autocasion(Portal):
    name = NAME

    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        url, params = build_url(search)
        response = http.get(client, NAME, url, params=params)
        return parse(response.text)
