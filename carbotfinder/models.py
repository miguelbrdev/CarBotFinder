"""Normalised listing model shared by every portal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

SellerType = Literal["private", "dealer"]


@dataclass(slots=True)
class Listing:
    """One car ad, normalised across portals.

    ``province`` is the normalised form (see :mod:`carbotfinder.geo`) used for comparisons;
    ``province_raw`` keeps the portal's original text for display.
    Missing values are ``None``; filters decide how to treat them.
    """

    portal: str
    id: str
    title: str
    url: str
    price: int | None = None
    year: int | None = None
    km: int | None = None
    province: str | None = None
    province_raw: str | None = None
    city: str | None = None
    published_at: datetime | None = None
    seller_type: SellerType | None = None
    reserved: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def key(self) -> str:
        """Stable identity used for de-duplication in the state store."""
        return f"{self.portal}:{self.id}"
