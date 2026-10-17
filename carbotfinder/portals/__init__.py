"""Portal implementations. Importing this package registers every portal."""

from __future__ import annotations

from carbotfinder.portals import (  # noqa: F401  (import for side effect: registration)
    autocasion,
    autoscout24,
    cochescom,
    cochesnet,
    milanuncios,
    wallapop,
)
from carbotfinder.portals.base import Portal, available_portals, get_portal

__all__ = ["Portal", "available_portals", "get_portal"]
