"""Parser tests for the HTML-based portals, using trimmed and anonymised real pages."""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.portals import autocasion, autoscout24, cochescom, milanuncios
from carbotfinder.portals._embedded import (
    extract_initial_props,
    extract_next_data,
    fold,
    parse_int_text,
    slugify,
)
from tests.conftest import read_fixture

# -- helpers ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("198.000 kms", 198000),
        ("12.500 €", 12500),
        (2004, 2004),
        ("", None),
        (None, None),
        (True, None),
    ],
)
def test_parse_int_text(raw: object, expected: int | None) -> None:
    assert parse_int_text(raw) == expected


def test_slugify_and_fold() -> None:
    assert slugify("MX-5") == "mx-5"
    assert slugify("Citroën C4 Picasso") == "citroen-c4-picasso"
    assert fold("Kilómetros") == "kilometros" and fold("Año") == "ano"


def test_extractors_fail_loudly() -> None:
    with pytest.raises(PortalError, match="__INITIAL_PROPS__ not found"):
        extract_initial_props("x", "<html></html>")
    with pytest.raises(PortalError, match="__NEXT_DATA__ not found"):
        extract_next_data("x", "<html></html>")


# -- milanuncios -----------------------------------------------------------------------------------


def test_milanuncios_parse() -> None:
    listings = milanuncios.parse(read_fixture("milanuncios_search.html"))
    assert len(listings) == 3
    first = listings[0]
    assert first.key == "milanuncios:619423781"
    assert first.url == "https://www.milanuncios.com/mazda-de-segunda-mano/mazda-mx5-619423781.htm"
    assert first.price == 8999 and first.year == 1998 and first.km == 180000
    assert first.province == "alicante" and first.province_raw == "Alicante"
    assert first.seller_type == "private"
    assert first.published_at == datetime(2026, 10, 12, 9, 23, 19, tzinfo=UTC)
    assert first.reserved is False
    assert listings[2].seller_type == "dealer" and listings[2].km == 157295


def test_milanuncios_url(search: SearchConfig) -> None:
    url, params = milanuncios.build_url(search)
    assert url == "https://www.milanuncios.com/mazda-de-segunda-mano/mx-5.htm"
    assert params["orden"] == "date" and params["hasta"] == 14000


# -- autoscout24 -----------------------------------------------------------------------------------


def test_autoscout24_parse() -> None:
    listings = autoscout24.parse(read_fixture("autoscout24_search.html"))
    assert len(listings) == 3
    first = listings[0]
    assert first.id.startswith("5bc62870")
    assert first.url.startswith("https://www.autoscout24.es/anuncios/mazda-mx-5")
    assert "Roadster" in first.title
    assert first.price == 12500 and first.km == 135000 and first.year == 2010
    assert first.province == "tarragona" and first.city == "Tarragona"
    assert first.seller_type == "private"
    assert first.published_at is None
    assert listings[1].province == "alicante"  # zip 03130
    assert listings[2].province == "lleida"  # zip 25300


def test_autoscout24_url(search: SearchConfig) -> None:
    url, params = autoscout24.build_url(search)
    assert url == "https://www.autoscout24.es/lst/mazda/mx-5"
    assert params["sort"] == "age" and params["desc"] == 1
    assert params["priceto"] == 14000 and params["kmto"] == 180000
    assert params["fregfrom"] == 2005 and params["fregto"] == 2015


# -- coches.com ------------------------------------------------------------------------------------


def test_cochescom_parse() -> None:
    listings = cochescom.parse(read_fixture("cochescom_search.html"))
    assert len(listings) == 3
    first = listings[0]
    assert first.key == "cochescom:OupIVfc4PHZ4"
    assert first.url == (
        "https://www.coches.com/coches-segunda-mano/ocasion-mazda-mx-5-131-rf-15-luxury.htm"
        "?id=OupIVfc4PHZ4"
    )
    assert first.title == "Mazda MX-5 RF 1.5 Luxury"
    assert first.price == 18761  # offer price preferred over list price
    assert first.km == 34438 and first.year == 2017
    assert first.province == "madrid"
    assert first.seller_type == "dealer"
    assert first.published_at == datetime(2026, 10, 7, 13, 19, 57, tzinfo=UTC)
    assert listings[2].province == "girona"


def test_cochescom_url(search: SearchConfig) -> None:
    assert (
        cochescom.build_url(search) == "https://www.coches.com/coches-segunda-mano/mazda-mx-5.htm"
    )


# -- autocasion ------------------------------------------------------------------------------------


def test_autocasion_parse() -> None:
    listings = autocasion.parse(read_fixture("autocasion_search.html"))
    assert len(listings) == 3
    first = listings[0]
    assert first.key == "autocasion:21376590"
    assert first.url == (
        "https://www.autocasion.com/coches-segunda-mano/mazda-mx-5-ocasion/"
        "1-5-97kw-132cv-origin-st-6ab3ddbeeed7b8-49132310-ref21376590"
    )
    assert first.title == "MAZDA MX-5 1.5 97kW (132CV) Origin ST"
    assert first.price == 23990 and first.year == 2020 and first.km == 89000
    assert first.province == "madrid" and first.city == "Majadahonda"
    assert first.seller_type == "dealer"


def test_autocasion_url(search: SearchConfig) -> None:
    url, params = autocasion.build_url(search)
    assert url == "https://www.autocasion.com/coches-segunda-mano/mazda-mx-5-ocasion"
    assert params == {"orden": "fecha"}


# -- fetch path shared behaviour -------------------------------------------------------------------


@respx.mock
def test_html_portal_fetch_detects_redirect(search: SearchConfig) -> None:
    respx.get(url__startswith="https://www.milanuncios.com/").mock(
        return_value=httpx.Response(301, headers={"location": "https://www.milanuncios.com/x"})
    )
    with httpx.Client() as client, pytest.raises(PortalError, match="unexpected redirect"):
        milanuncios.Milanuncios().fetch(search, client)
