"""Shared HTTP client: browser-like headers, timeouts, retries and block detection."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping

import httpx

from carbotfinder.errors import PortalBlocked, PortalError

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

_BLOCK_MARKERS = ("captcha-delivery.com", "_Incapsula_Resource", "cf-chl-", "Just a moment...")
_RETRY_BACKOFF_SECONDS = (1.0, 3.0)


def make_client(timeout: float = 20.0) -> httpx.Client:
    return httpx.Client(
        http2=True,
        headers=DEFAULT_HEADERS,
        timeout=httpx.Timeout(timeout),
        follow_redirects=False,
    )


def looks_blocked(response: httpx.Response) -> bool:
    if response.status_code in (403, 429):
        return True
    if "x-datadome" in response.headers or "datadome" in response.headers.get("set-cookie", ""):
        return True
    head = response.text[:4000]
    return any(marker in head for marker in _BLOCK_MARKERS)


def get(
    client: httpx.Client,
    portal: str,
    url: str,
    *,
    params: Mapping[str, str | int | float] | None = None,
    headers: Mapping[str, str] | None = None,
    retries: int = 2,
) -> httpx.Response:
    """GET with retries on transient failures. Raises PortalBlocked/PortalError on bad outcomes."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            last_error = exc
            log.warning("%s: network error on attempt %d: %s", portal, attempt + 1, exc)
        else:
            if looks_blocked(response):
                raise PortalBlocked(portal, f"blocked (HTTP {response.status_code}) at {url}")
            if 300 <= response.status_code < 400:
                target = response.headers.get("location", "?")
                raise PortalError(
                    portal, f"unexpected redirect {response.status_code} -> {target} from {url}"
                )
            if response.status_code >= 500:
                last_error = PortalError(portal, f"HTTP {response.status_code} at {url}")
                log.warning("%s: server error on attempt %d: %s", portal, attempt + 1, last_error)
            elif response.status_code != 200:
                raise PortalError(portal, f"HTTP {response.status_code} at {url}")
            else:
                return response
        if attempt < retries:
            time.sleep(_RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)])
    raise PortalError(portal, f"giving up after {retries + 1} attempts: {last_error}")
