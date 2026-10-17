from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from carbotfinder.config import AppConfig, SearchConfig
from carbotfinder.models import Listing

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def search() -> SearchConfig:
    return SearchConfig(
        name="mx5-nc",
        make="Mazda",
        model="MX-5",
        year_min=2005,
        year_max=2015,
        price_max=14000,
        km_max=180000,
    )


@pytest.fixture
def config(search: SearchConfig) -> AppConfig:
    return AppConfig(searches=[search])


def make_listing(**overrides: object) -> Listing:
    base: dict[str, object] = {
        "portal": "fake",
        "id": "1",
        "title": "Mazda MX-5 2.0 NC",
        "url": "https://example.test/1",
        "price": 9000,
        "year": 2010,
        "km": 120000,
        "province": "madrid",
        "province_raw": "Madrid",
        "city": "Madrid",
        "published_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        "seller_type": "private",
    }
    base.update(overrides)
    return Listing(**base)  # type: ignore[arg-type]


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
