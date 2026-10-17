import httpx
import pytest
import respx

from carbotfinder.errors import NotifyError
from carbotfinder.notify.telegram import TelegramNotifier, format_listing
from tests.conftest import make_listing


def test_format_listing_escapes_and_formats() -> None:
    text = format_listing(make_listing(title="MX-5 <NC> & co", price=11999, km=98000), "mx5")
    assert "MX-5 &lt;NC&gt; &amp; co" in text
    assert "11.999 €" in text
    assert "98.000 km" in text
    assert "Madrid" in text
    assert "particular" in text
    assert "https://example.test/1" in text


def test_format_listing_handles_missing() -> None:
    text = format_listing(
        make_listing(
            price=None,
            year=None,
            km=None,
            province=None,
            province_raw=None,
            city=None,
            seller_type=None,
        ),
        "mx5",
    )
    assert "precio ?" in text and "año ?" in text and "km ?" in text and "ubicación ?" in text
    assert "👤" not in text  # unknown seller type is simply omitted


def test_format_listing_keeps_apostrophes() -> None:
    text = format_listing(make_listing(city="Santa Cristina D'Aro", province_raw="Girona"), "mx5")
    assert "Santa Cristina D'Aro (Girona)" in text


@respx.mock
def test_send_ok() -> None:
    route = respx.post("https://api.telegram.org/botT/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    TelegramNotifier("T", "42").send("hola")
    assert route.called
    body = route.calls.last.request.content
    assert b'"chat_id": "42"' in body or b'"chat_id":"42"' in body


@respx.mock
def test_send_error_raises() -> None:
    respx.post("https://api.telegram.org/botT/sendMessage").mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "chat not found"})
    )
    with pytest.raises(NotifyError, match="400"):
        TelegramNotifier("T", "42").send("hola")


@respx.mock
def test_send_retries_once_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("carbotfinder.notify.telegram.time.sleep", lambda _s: None)
    route = respx.post("https://api.telegram.org/botT/sendMessage")
    route.side_effect = [
        httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 1}}),
        httpx.Response(200, json={"ok": True}),
    ]
    TelegramNotifier("T", "42").send("hola")
    assert route.call_count == 2
