"""Exception types."""

from __future__ import annotations


class CarBotError(Exception):
    """Base class for all project errors."""


class ConfigError(CarBotError):
    """Invalid or missing configuration."""


class PortalError(CarBotError):
    """A portal could not be fetched or parsed. Isolated per portal by the runner."""

    def __init__(self, portal: str, message: str) -> None:
        super().__init__(f"{portal}: {message}")
        self.portal = portal
        self.message = message


class PortalBlocked(PortalError):
    """The portal answered with an anti-bot block (403/429/challenge page)."""


class NotifyError(CarBotError):
    """A notification could not be delivered."""
