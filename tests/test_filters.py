from carbotfinder import filters
from carbotfinder.config import SearchConfig
from carbotfinder.geo import ISLAND_PROVINCES
from tests.conftest import make_listing

EXCL = frozenset(ISLAND_PROVINCES)


def test_accepts_matching_listing(search: SearchConfig) -> None:
    assert filters.check(make_listing(), search, EXCL).ok


def test_rejects_over_price(search: SearchConfig) -> None:
    result = filters.check(make_listing(price=14001), search, EXCL)
    assert not result.ok and "price" in (result.reason or "")


def test_rejects_missing_price(search: SearchConfig) -> None:
    assert filters.check(make_listing(price=None), search, EXCL).reason == "price_missing"


def test_rejects_year_out_of_range(search: SearchConfig) -> None:
    assert not filters.check(make_listing(year=2004), search, EXCL).ok
    assert not filters.check(make_listing(year=2016), search, EXCL).ok
    assert filters.check(make_listing(year=2005), search, EXCL).ok
    assert filters.check(make_listing(year=2015), search, EXCL).ok


def test_missing_year_and_km_pass(search: SearchConfig) -> None:
    assert filters.check(make_listing(year=None, km=None), search, EXCL).ok


def test_rejects_over_km(search: SearchConfig) -> None:
    assert not filters.check(make_listing(km=180001), search, EXCL).ok
    assert filters.check(make_listing(km=180000), search, EXCL).ok


def test_rejects_islands(search: SearchConfig) -> None:
    for island in ISLAND_PROVINCES:
        assert not filters.check(make_listing(province=island), search, EXCL).ok


def test_missing_province_passes(search: SearchConfig) -> None:
    assert filters.check(make_listing(province=None), search, EXCL).ok


def test_rejects_reserved_unless_allowed(search: SearchConfig) -> None:
    assert not filters.check(make_listing(reserved=True), search, EXCL).ok
    lenient = search.model_copy(update={"include_reserved": True})
    assert filters.check(make_listing(reserved=True), lenient, EXCL).ok


def test_seller_type_filter(search: SearchConfig) -> None:
    private_only = search.model_copy(update={"seller_types": ["private"]})
    assert not filters.check(make_listing(seller_type="dealer"), private_only, EXCL).ok
    assert filters.check(make_listing(seller_type=None), private_only, EXCL).ok


def test_title_exclude_is_whole_word(search: SearchConfig) -> None:
    s = search.model_copy(update={"title_exclude": ["NA", "NB", "ND"]})
    assert not filters.check(make_listing(title="Mazda MX-5 NB 1.8"), s, EXCL).ok
    assert not filters.check(make_listing(title="mazda mx5 nd skyactiv"), s, EXCL).ok
    # "NA" inside another word must not match
    assert filters.check(make_listing(title="Mazda MX-5 NC Kaminari"), s, EXCL).ok
    assert filters.check(make_listing(title="MX-5 NC-2 perfecto"), s, EXCL).ok


def test_title_include(search: SearchConfig) -> None:
    s = search.model_copy(update={"title_include": ["NC"]})
    assert filters.check(make_listing(title="Mazda MX-5 NC"), s, EXCL).ok
    assert not filters.check(make_listing(title="Mazda MX-5 2.0"), s, EXCL).ok


def test_apply_keeps_only_matches(search: SearchConfig) -> None:
    listings = [make_listing(id="a"), make_listing(id="b", price=20000), make_listing(id="c")]
    assert [x.id for x in filters.apply(listings, search, EXCL)] == ["a", "c"]
