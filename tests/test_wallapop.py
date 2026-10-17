import json
from datetime import UTC, datetime

import httpx
import pytest
import respx

from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalBlocked, PortalError
from carbotfinder.portals.wallapop import SEARCH_URL, Wallapop, build_params, parse
from tests.conftest import read_fixture


def test_parse_fixture() -> None:
    listings = parse(json.loads(read_fixture("wallapop_search.json")))
    assert len(listings) == 3
    first = listings[0]
    assert first.portal == "wallapop"
    assert first.id == "p618n9w9kxz5"
    assert first.key == "wallapop:p618n9w9kxz5"
    assert first.url.startswith("https://es.wallapop.com/item/mazda-mx-5-nbfl")
    assert first.price == 8200
    assert first.year == 2004
    assert first.km == 118500
    assert first.province == "barcelona" and first.province_raw == "Barcelona"
    assert first.city == "Bellaterra"
    assert first.published_at == datetime.fromtimestamp(1792242391919 / 1000, tz=UTC)
    assert first.seller_type is None
    assert first.reserved is False
    assert listings[1].reserved is True
    assert listings[2].province == "malaga" and listings[2].year == 2011


def test_parse_rejects_bad_shape() -> None:
    with pytest.raises(PortalError, match="unexpected response shape"):
        parse({"data": {}})


def test_build_params(search: SearchConfig) -> None:
    params = build_params(search)
    assert params["category_ids"] == 100
    assert params["brand"] == "Mazda" and params["model"] == "MX-5"
    assert params["max_sale_price"] == 14000 and params["max_km"] == 180000
    assert params["order_by"] == "newest"
    assert "min_sale_price" not in params


@respx.mock
def test_fetch_sends_expected_query(search: SearchConfig) -> None:
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, text=read_fixture("wallapop_search.json"))
    )
    with httpx.Client() as client:
        listings = Wallapop().fetch(search, client)
    assert len(listings) == 3
    request = route.calls.last.request
    assert request.headers["accept"] == "application/json"
    assert "category_ids=100" in str(request.url)
    assert "max_sale_price=14000" in str(request.url)


@respx.mock
def test_fetch_raises_blocked_on_403(search: SearchConfig) -> None:
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(403, text="forbidden"))
    with httpx.Client() as client, pytest.raises(PortalBlocked):
        Wallapop().fetch(search, client)
