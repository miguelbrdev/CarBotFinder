"""Portal interface and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import httpx

from carbotfinder.config import SearchConfig
from carbotfinder.errors import PortalError
from carbotfinder.models import Listing


class Portal(ABC):
    """One source of listings.

    Subclasses implement ``fetch`` (network) on top of a pure ``parse`` function so the
    parser can be unit-tested with recorded fixtures.
    """

    name: ClassVar[str]

    @abstractmethod
    def fetch(self, search: SearchConfig, client: httpx.Client) -> list[Listing]:
        """Return the most recent listings for ``search`` (first page, newest first)."""


_REGISTRY: dict[str, type[Portal]] = {}


def register(cls: type[Portal]) -> type[Portal]:
    _REGISTRY[cls.name] = cls
    return cls


def get_portal(name: str) -> Portal:
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise PortalError(name, f"portal not implemented; available: {sorted(_REGISTRY)}") from None


def available_portals() -> list[str]:
    return sorted(_REGISTRY)


def slug_for(
    portal: str, table: dict[tuple[str, str], tuple[str, str]], search: SearchConfig
) -> tuple[str, str]:
    """Look up portal-specific (make, model) slugs; fail loudly when unknown."""
    key = (search.make.strip().lower(), search.model.strip().lower())
    try:
        return table[key]
    except KeyError:
        raise PortalError(
            portal,
            f"no slug mapping for make/model {search.make!r}/{search.model!r};"
            f" add it to the portal's slug table",
        ) from None
