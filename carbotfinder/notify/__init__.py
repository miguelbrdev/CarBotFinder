"""Notification backends."""

from __future__ import annotations

from typing import Protocol


class Notifier(Protocol):
    def send(self, text: str) -> None:
        """Deliver an HTML-formatted message. Raises NotifyError on failure."""
        ...


class ConsoleNotifier:
    """Prints messages instead of sending them (used by --dry-run)."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, text: str) -> None:
        self.sent.append(text)
        print("--- notification ---")
        print(text)
