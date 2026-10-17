"""Retry, back-off and block-detection behaviour of the shared HTTP helper."""

from __future__ import annotations

import httpx
import pytest
import respx

from carbotfinder import http
from carbotfinder.errors import PortalBlocked, PortalError

URL = "https://portal.test/search"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Capture back-off sleeps instead of waiting."""
    sleeps: list[float] = []
    monkeypatch.setattr(http.time, "sleep", sleeps.append)
    return sleeps


@pytest.fixture
def client() -> httpx.Client:
    with http.make_client() as c:
        yield c


@respx.mock
def test_returns_response_on_200(client: httpx.Client) -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="ok"))
    assert http.get(client, "p", URL).text == "ok"


@respx.mock
def test_retries_server_errors_then_succeeds(client: httpx.Client, no_sleep: list[float]) -> None:
    route = respx.get(URL)
    route.side_effect = [httpx.Response(503), httpx.Response(502), httpx.Response(200, text="ok")]
    assert http.get(client, "p", URL).text == "ok"
    assert route.call_count == 3
    assert no_sleep == [1.0, 3.0]  # exponential-ish back-off between attempts


@respx.mock
def test_gives_up_after_max_retries(client: httpx.Client) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(500))
    with pytest.raises(PortalError, match="giving up after 3 attempts"):
        http.get(client, "p", URL)
    assert route.call_count == 3


@respx.mock
def test_retries_network_errors(client: httpx.Client) -> None:
    route = respx.get(URL)
    route.side_effect = [httpx.ConnectError("boom"), httpx.Response(200, text="ok")]
    assert http.get(client, "p", URL).text == "ok"
    assert route.call_count == 2


@respx.mock
def test_does_not_retry_client_errors(client: httpx.Client) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(PortalError, match="HTTP 404"):
        http.get(client, "p", URL)
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        pytest.param(httpx.Response(403), id="403"),
        pytest.param(httpx.Response(429), id="429"),
        pytest.param(httpx.Response(200, headers={"x-datadome": "1"}), id="datadome-header"),
        pytest.param(
            httpx.Response(200, text="<a href='https://geo.captcha-delivery.com/'>"), id="captcha"
        ),
        pytest.param(
            httpx.Response(200, text="<script src='/_Incapsula_Resource'>"), id="incapsula"
        ),
    ],
)
def test_detects_anti_bot_blocks(client: httpx.Client, response: httpx.Response) -> None:
    route = respx.get(URL).mock(return_value=response)
    with pytest.raises(PortalBlocked):
        http.get(client, "p", URL)
    assert route.call_count == 1  # blocks are never retried


@respx.mock
def test_redirect_is_an_error(client: httpx.Client) -> None:
    respx.get(URL).mock(return_value=httpx.Response(301, headers={"location": "https://x/y"}))
    with pytest.raises(PortalError, match="unexpected redirect 301 -> https://x/y"):
        http.get(client, "p", URL)


def test_client_sends_browser_headers_and_no_manual_encoding(client: httpx.Client) -> None:
    assert client.headers["user-agent"].startswith("Mozilla/5.0")
    assert client.headers["accept-language"].startswith("es-ES")
    # httpx must negotiate Accept-Encoding itself (it cannot decode brotli without extras)
    assert "br" not in client.headers.get("accept-encoding", "")
