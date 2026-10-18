"""Telegram Bot API notifier and message formatting."""

from __future__ import annotations

import html
import logging
import time
from typing import Any

import httpx

from carbotfinder.errors import NotifyError
from carbotfinder.models import Listing

log = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
_SELLER_LABEL = {"private": "particular", "dealer": "profesional"}


def _esc(text: str) -> str:
    """Telegram HTML only needs <, > and & escaped; quotes are fine outside tags."""
    return html.escape(text, quote=False)


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

    seller = _SELLER_LABEL.get(listing.seller_type or "")
    place_parts = [f"📍 {_esc(where)}"]
    if seller:
        place_parts.append(f"👤 {seller}")
    place_parts.append(listing.portal)
    lines = [
        f"🚗 <b>{_esc(listing.title.strip())}</b>",
        f"💶 {price}  ·  📅 {year}  ·  🛣 {km}",
        "  ·  ".join(place_parts),
        f"🔗 {_esc(listing.url)}",
        f"<i>búsqueda: {_esc(search_name)}</i>",
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

    def check(self) -> str:
        """Verify token and chat id up front; returns ``@bot -> chat`` for logging.

        Without this a wrong token or chat id only surfaces the first time an ad matches,
        which may be days later and is easy to miss.
        """
        me = self._get("getMe")
        chat = self._get("getChat", chat_id=self._chat_id)
        who = chat.get("username") or chat.get("title") or chat.get("first_name") or self._chat_id
        return f"@{me.get('username', '?')} -> {who}"

    def _get(self, method: str, **params: str) -> dict[str, Any]:
        url = _API.format(token=self._token, method=method)
        try:
            response = self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise NotifyError(f"telegram network error: {exc}") from exc
        is_json = response.headers.get("content-type", "").startswith("application/json")
        body = response.json() if is_json else {}
        if response.status_code in (401, 404) and method == "getMe":
            raise NotifyError(
                "telegram rejected the bot token (check TELEGRAM_BOT_TOKEN in @BotFather)"
            )
        if not body.get("ok"):
            detail = body.get("description") or f"HTTP {response.status_code}"
            hint = (
                " (check TELEGRAM_CHAT_ID; write to the bot first)" if method == "getChat" else ""
            )
            raise NotifyError(f"telegram {method}: {detail}{hint}")
        result: dict[str, Any] = body["result"]
        return result

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
