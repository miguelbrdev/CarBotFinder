"""Configuration models and loader (YAML + environment)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from carbotfinder.errors import ConfigError
from carbotfinder.geo import ISLAND_PROVINCES, normalise_province
from carbotfinder.models import SellerType

ALL_PORTALS: tuple[str, ...] = (
    "wallapop",
    "cochesnet",
    "milanuncios",
    "autoscout24",
    "cochescom",
    "autocasion",
)


def _all_seller_types() -> list[SellerType]:
    return ["private", "dealer"]


class TelegramConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id_env: str = "TELEGRAM_CHAT_ID"


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    excluded_provinces: list[str] = Field(default_factory=lambda: sorted(ISLAND_PROVINCES))
    seed_window_hours: int = Field(default=2, ge=0)
    portals: list[str] = Field(default_factory=lambda: list(ALL_PORTALS))
    error_alert_after_failures: int = Field(default=3, ge=1)
    error_alert_min_interval_hours: int = Field(default=6, ge=0)

    @field_validator("portals")
    @classmethod
    def _known_portals(cls, value: list[str]) -> list[str]:
        unknown = [p for p in value if p not in ALL_PORTALS]
        if unknown:
            raise ValueError(f"unknown portals: {unknown}; valid: {list(ALL_PORTALS)}")
        return value


class SearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    make: str
    model: str
    year_min: int | None = None
    year_max: int | None = None
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    km_min: int | None = Field(default=None, ge=0)
    km_max: int | None = Field(default=None, ge=0)
    title_exclude: list[str] = Field(default_factory=list)
    title_include: list[str] = Field(default_factory=list)
    seller_types: list[SellerType] = Field(default_factory=_all_seller_types)
    include_reserved: bool = False
    portals: list[str] | None = None
    excluded_provinces: list[str] | None = None

    @field_validator("portals")
    @classmethod
    def _known_portals(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unknown = [p for p in value if p not in ALL_PORTALS]
        if unknown:
            raise ValueError(f"unknown portals: {unknown}; valid: {list(ALL_PORTALS)}")
        return value

    @model_validator(mode="after")
    def _ranges(self) -> SearchConfig:
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ValueError("year_min must be <= year_max")
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_min > self.price_max
        ):
            raise ValueError("price_min must be <= price_max")
        if self.km_min is not None and self.km_max is not None and self.km_min > self.km_max:
            raise ValueError("km_min must be <= km_max")
        if not self.seller_types:
            raise ValueError("seller_types must not be empty")
        return self


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    defaults: Defaults = Field(default_factory=Defaults)
    searches: list[SearchConfig]

    @model_validator(mode="after")
    def _unique_names(self) -> AppConfig:
        names = [s.name for s in self.searches]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate search names: {names}")
        if not self.searches:
            raise ValueError("at least one search is required")
        return self

    def portals_for(self, search: SearchConfig) -> list[str]:
        return list(search.portals if search.portals is not None else self.defaults.portals)

    def excluded_provinces_for(self, search: SearchConfig) -> frozenset[str]:
        raw = (
            search.excluded_provinces
            if search.excluded_provinces is not None
            else self.defaults.excluded_provinces
        )
        normalised = (normalise_province(p) for p in raw)
        return frozenset(p for p in normalised if p)


class TelegramCredentials(BaseModel):
    token: str
    chat_id: str


def load_config(path: str | Path) -> AppConfig:
    file = Path(path)
    if not file.is_file():
        raise ConfigError(f"config file not found: {file}")
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {file}: {exc}") from exc
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid config in {file}:\n{exc}") from exc


def load_telegram_credentials(config: TelegramConfig) -> TelegramCredentials:
    token = os.environ.get(config.token_env, "").strip()
    chat_id = os.environ.get(config.chat_id_env, "").strip()
    missing = [
        name
        for name, value in ((config.token_env, token), (config.chat_id_env, chat_id))
        if not value
    ]
    if missing:
        raise ConfigError(f"missing environment variables: {', '.join(missing)}")
    return TelegramCredentials(token=token, chat_id=chat_id)
