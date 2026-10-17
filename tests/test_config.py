from pathlib import Path

import pytest

from carbotfinder.config import AppConfig, SearchConfig, load_config, load_telegram_credentials
from carbotfinder.errors import ConfigError

ROOT = Path(__file__).resolve().parents[1]


def test_example_config_is_valid() -> None:
    config = load_config(ROOT / "config.example.yaml")
    assert config.searches[0].name == "mx5-nc"
    assert config.excluded_provinces_for(config.searches[0]) == frozenset(
        {"baleares", "las palmas", "santa cruz de tenerife"}
    )
    assert "wallapop" in config.portals_for(config.searches[0])


def test_search_overrides(search: SearchConfig) -> None:
    custom = search.model_copy(
        update={"portals": ["wallapop"], "excluded_provinces": ["Illes Balears", "Ceuta"]}
    )
    config = AppConfig(searches=[custom])
    assert config.portals_for(custom) == ["wallapop"]
    assert config.excluded_provinces_for(custom) == frozenset({"baleares", "ceuta"})


def test_rejects_unknown_portal() -> None:
    with pytest.raises(ValueError, match="unknown portals"):
        SearchConfig(name="x", make="a", model="b", portals=["ebay"])


def test_rejects_bad_ranges() -> None:
    with pytest.raises(ValueError, match="year_min"):
        SearchConfig(name="x", make="a", model="b", year_min=2010, year_max=2005)


def test_missing_file() -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config("does-not-exist.yaml")


def test_invalid_yaml_reports_path(tmp_path: Path) -> None:
    bad = tmp_path / "c.yaml"
    bad.write_text("searches: [ {name: x, make: a, model: b, portals: [nope]} ]", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid config"):
        load_config(bad)


def test_credentials_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    config = AppConfig(searches=[SearchConfig(name="x", make="a", model="b")])
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        load_telegram_credentials(config.telegram)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t0k")
    creds = load_telegram_credentials(config.telegram)
    assert (creds.token, creds.chat_id) == ("t0k", "42")
