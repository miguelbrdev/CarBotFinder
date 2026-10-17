"""Helpers to pull server-rendered JSON blobs out of HTML pages and parse loose numbers."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any

from carbotfinder.errors import PortalError

_INITIAL_PROPS = re.compile(r"window\.__INITIAL_PROPS__\s*=\s*(.*?);\s*</script>", re.S)
_NEXT_DATA = re.compile(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_LD_JSON = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def extract_initial_props(portal: str, html: str) -> dict[str, Any]:
    """Adevinta sites (coches.net, milanuncios): ``window.__INITIAL_PROPS__ = JSON.parse(...)``."""
    match = _INITIAL_PROPS.search(html)
    if not match:
        raise PortalError(portal, "window.__INITIAL_PROPS__ not found in page")
    raw = match.group(1).strip()
    try:
        if raw.startswith("JSON.parse("):
            raw = json.loads(raw[len("JSON.parse(") : -1])
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise PortalError(portal, f"could not decode __INITIAL_PROPS__: {exc}") from exc
    if not isinstance(data, dict):
        raise PortalError(portal, "__INITIAL_PROPS__ is not an object")
    return data


def extract_next_data(portal: str, html: str) -> dict[str, Any]:
    """Next.js sites (AutoScout24, coches.com): ``<script id="__NEXT_DATA__">{...}</script>``."""
    match = _NEXT_DATA.search(html)
    if not match:
        raise PortalError(portal, "__NEXT_DATA__ not found in page")
    try:
        data = json.loads(match.group(1))
    except ValueError as exc:
        raise PortalError(portal, f"could not decode __NEXT_DATA__: {exc}") from exc
    if not isinstance(data, dict):
        raise PortalError(portal, "__NEXT_DATA__ is not an object")
    return data


def extract_ld_json(portal: str, html: str) -> list[Any]:
    """Return every decodable ``application/ld+json`` block (objects or lists) on the page."""
    blocks: list[Any] = []
    for match in _LD_JSON.finditer(html):
        try:
            blocks.append(json.loads(match.group(1)))
        except ValueError:
            continue
    if not blocks:
        raise PortalError(portal, "no application/ld+json block found in page")
    return blocks


def parse_int_text(text: object) -> int | None:
    """``"198.000 kms"`` -> 198000, ``"12.500 €"`` -> 12500, ``2004`` -> 2004."""
    if isinstance(text, bool):
        return None
    if isinstance(text, int | float):
        return int(text)
    if not isinstance(text, str):
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def slugify(text: str) -> str:
    """``"MX-5"`` -> ``"mx-5"``, ``"Citroën C4"`` -> ``"citroen-c4"``."""
    stripped = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


def fold(text: str) -> str:
    """Lower-case, accent-free form for loose key comparison (``"Año"`` -> ``"ano"``)."""
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in stripped if not unicodedata.combining(ch)).lower().strip()
