import pytest

from carbotfinder.geo import ISLAND_PROVINCES, normalise_province, province_from_postal_code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Madrid", "madrid"),
        ("  Comunidad de Madrid ", "madrid"),
        ("Illes Balears", "baleares"),
        ("Islas Baleares", "baleares"),
        ("Palma de Mallorca", "baleares"),
        ("Las Palmas de Gran Canaria", "las palmas"),
        ("Sta. Cruz de Tenerife", "santa cruz de tenerife"),
        ("Santa Cruz de Tenerife", "santa cruz de tenerife"),
        ("A Coruña", "a coruna"),
        ("La Coruña", "a coruna"),
        ("Gerona", "girona"),
        ("Vizcaya", "bizkaia"),
        ("Provincia de Sevilla", "sevilla"),
        ("Cataluña", "cataluna"),
        ("", None),
        (None, None),
    ],
)
def test_normalise_province(raw: str | None, expected: str | None) -> None:
    assert normalise_province(raw) == expected


def test_islands_are_canonical() -> None:
    for island in ISLAND_PROVINCES:
        assert normalise_province(island) == island


@pytest.mark.parametrize(
    ("postal", "expected"),
    [
        ("28001", "madrid"),
        ("07001", "baleares"),
        ("35000", "las palmas"),
        ("38001", "santa cruz de tenerife"),
        ("08193", "barcelona"),
        ("43007", "tarragona"),
        ("51001", "ceuta"),
        ("abc", None),
        ("", None),
        (None, None),
    ],
)
def test_province_from_postal_code(postal: str | None, expected: str | None) -> None:
    assert province_from_postal_code(postal) == expected
