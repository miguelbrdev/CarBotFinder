"""Telegram Bot API notifier and message formatting."""

from __future__ import annotations

import html
import logging
import time

import httpx

from carbotfinder.errors import NotifyError
from carbotfinder.models import Listing

log = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
_SELLER_LABEL = {"private": "particular", "dealer": "profesional"}


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def format_listing(listing: Listing, search_name: str) -> str:
    """Render a listing as a short Telegram HTML message."""
    price = f"{_fmt_int(listing.price)} €" if listing.price is not None else "precio ?"
    year = str(listing.year) if listing.year is not None else "año ?"
    km = f"{_fmt_int(listing.km)} km" if listing.km is not None else "km ?"

    where = listing.province_raw or listing.province or "ubicación ?"
    if listing.city and listing.city.lower() != where.lower():
        where = f"{listing.city} ({where})"

    seller = _SELLER_LABEL.get(listing.seller_type or "", "vendedor ?")
    lines = [
        f"🚗 <b>{html.escape(listing.title.strip())}</b>",
        f"💶 {price}  ·  📅 {year}  ·  🛣 {km}",
        f"📍 {html.escape(where)}  ·  👤 {seller}  ·  {listing.portal}",
        f"🔗 {html.escape(listing.url)}",
        f"<i>búsqueda: {html.escape(search_name)}</i>",
    ]
    return "\n".join(lines)


def format_portal_error(portal: str, failures: int, error: str) -> str:
    return (
        f"⚠️ <b>{html.escape(portal)}</b> lleva {failures} ejecuciones fallando.\n"
        f"<code>{html.escape(error[:300])}</code>"
    )


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, client: httpx.Client | None = None) -> None:
        self._token = token
        self._chat_id = chat_id
        self._client = client or httpx.Client(timeout=15.0)

    def send(self, text: str) -> None:
        url = _API.format(token=self._token, method="sendMessage")
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        for attempt in range(2):
            try:
                response = self._client.post(url, json=payload)
            except httpx.HTTPError as exc:
                raise NotifyError(f"telegram network error: {exc}") from exc
            if response.status_code == 429 and attempt == 0:
                retry_after = _retry_after(response)
                log.warning("telegram rate limited, sleeping %.1fs", retry_after)
                time.sleep(retry_after)
                continue
            if response.status_code != 200:
                raise NotifyError(f"telegram HTTP {response.status_code}: {response.text[:200]}")
            body = response.json()
            if not body.get("ok"):
                raise NotifyError(f"telegram error: {body.get('description', body)}")
            return
        raise NotifyError("telegram: still rate limited after retry")


def _retry_after(response: httpx.Response) -> float:
    try:
        return float(response.json()["parameters"]["retry_after"])
    except (ValueError, KeyError, TypeError):
        return 2.0
