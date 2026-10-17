import json
from datetime import UTC, datetime

import httpx
import pytest
import respx

from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.portals import cochesnet
from carbotfinder.portals.cochesnet import (
    MAKES_URL,
    MODELS_URL,
    SEARCH_URL,
    CochesNet,
    build_body,
    parse,
    resolve_ids,
)
from tests.conftest import read_fixture


def test_parse_fixture() -> None:
    listings = parse(json.loads(read_fixture("cochesnet_search.json")))
    assert len(listings) == 3
    first = listings[0]
    assert first.key == "cochesnet:70282058"
    assert first.url == (
        "https://www.coches.net/mazda-mx-5-active-18-2p-gasolina-2006-en-valencia-70282058-covo.aspx"
    )
    assert first.price == 10900 and first.km == 157295 and first.year == 2008
    assert first.province == "valencia" and first.city == "Manises"
    assert first.published_at == datetime(2026, 7, 22, 16, 50, 10, tzinfo=UTC)
    assert first.seller_type == "dealer"
    assert first.reserved is True
    assert listings[2].seller_type == "private" and listings[2].reserved is False


def test_parse_bad_shape() -> None:
    with pytest.raises(PortalError):
        parse({"nope": 1})


def test_build_body(search: SearchConfig) -> None:
    body = build_body(search, 27, 237)
    assert body["filters"]["vehicles"] == [{"makeId": 27, "modelId": 237}]
    assert body["filters"]["price"] == {"from": None, "to": 14000}
    assert body["filters"]["km"] == {"from": None, "to": 180000}
    assert body["filters"]["year"] == {"from": 2005, "to": 2015}
    assert body["sort"] == {"order": "desc", "term": "relevance"}
    assert body["pagination"]["size"] >= 50


def test_known_ids_need_no_lookup(search: SearchConfig) -> None:
    with httpx.Client() as client:  # no respx: any request would fail
        assert resolve_ids(search, client) == (27, 237)


@respx.mock
def test_resolve_ids_via_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cochesnet, "_KNOWN_IDS", {})
    respx.get(MAKES_URL).mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": 1, "label": "ALFA ROMEO"}, {"id": 27, "label": "MAZDA"}]}
        )
    )
    respx.get(MODELS_URL).mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": 236, "label": "MX-30"}, {"id": 237, "label": "MX-5"}]}
        )
    )
    s = SearchConfig(name="x", make="mazda", model="mx5")
    with httpx.Client() as client:
        assert resolve_ids(s, client) == (27, 237)
    unknown = SearchConfig(name="y", make="Mazda", model="RX-8")
    with httpx.Client() as client, pytest.raises(PortalError, match="model 'RX-8' not found"):
        resolve_ids(unknown, client)


@respx.mock
def test_fetch_posts_with_adevinta_headers(search: SearchConfig) -> None:
    route = respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(200, text=read_fixture("cochesnet_search.json"))
    )
    with httpx.Client() as client:
        listings = CochesNet().fetch(search, client)
    assert len(listings) == 3
    request = route.calls.last.request
    assert request.headers["x-adevinta-channel"] == "web-desktop"
    assert request.headers["x-schibsted-tenant"] == "coches"
    assert json.loads(request.content)["filters"]["vehicles"] == [{"makeId": 27, "modelId": 237}]


@respx.mock
def test_fetch_reports_http_errors(search: SearchConfig) -> None:
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(400, json={"error": "Bad Request"}))
    with httpx.Client() as client, pytest.raises(PortalError, match="HTTP 400"):
        CochesNet().fetch(search, client)
