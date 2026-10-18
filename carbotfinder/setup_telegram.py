"""``carbotfinder setup-telegram``: find your chat id and check the bot end to end.

The chat id is the step where first-time users get stuck (third-party "userinfo" bots are
unreliable). This asks the user to message their own bot, reads that message through
``getUpdates``, sends a test message back and stores both values in ``.env``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from carbotfinder.errors import NotifyError
from carbotfinder.notify.telegram import TelegramNotifier

_API = "https://api.telegram.org/bot{token}/{method}"
TEST_MESSAGE = "✅ CarBotFinder está conectado a este chat."


@dataclass(frozen=True)
class BotInfo:
    username: str
    first_name: str


@dataclass(frozen=True)
class ChatInfo:
    chat_id: str
    name: str


def _call(client: httpx.Client, token: str, method: str, **params: Any) -> Any:
    try:
        response = client.get(_API.format(token=token, method=method), params=params)
    except httpx.HTTPError as exc:
        raise NotifyError(f"telegram network error: {exc}") from exc
    if response.status_code == 401 or response.status_code == 404:
        raise NotifyError(
            f"telegram rejected the token (HTTP {response.status_code}): check it in @BotFather"
        )
    if response.status_code != 200:
        raise NotifyError(f"telegram HTTP {response.status_code}: {response.text[:200]}")
    body = response.json()
    if not body.get("ok"):
        raise NotifyError(f"telegram error: {body.get('description', body)}")
    return body["result"]


def get_me(client: httpx.Client, token: str) -> BotInfo:
    me = _call(client, token, "getMe")
    return BotInfo(username=str(me.get("username", "")), first_name=str(me.get("first_name", "")))


def latest_private_chat(updates: list[dict[str, Any]]) -> ChatInfo | None:
    """The chat of the most recent private message among ``updates``, if any."""
    for update in reversed(updates):
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") != "private" or "id" not in chat:
            continue
        name = " ".join(p for p in (chat.get("first_name"), chat.get("last_name")) if p)
        return ChatInfo(chat_id=str(chat["id"]), name=name or str(chat.get("username", "")))
    return None


def wait_for_chat(
    client: httpx.Client,
    token: str,
    *,
    timeout: float = 120.0,
    poll_interval: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> ChatInfo | None:
    """Poll ``getUpdates`` until a private message arrives or ``timeout`` seconds pass."""
    deadline = time.monotonic() + timeout
    while True:
        chat = latest_private_chat(_call(client, token, "getUpdates", limit=100))
        if chat is not None or time.monotonic() >= deadline:
            return chat
        sleep(poll_interval)


def update_env_file(path: Path, values: dict[str, str]) -> None:
    """Set ``KEY=value`` lines in a .env file, keeping every other line as it is."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    pending = dict(values)
    for i, line in enumerate(lines):
        key = line.partition("=")[0].strip()
        if not line.lstrip().startswith("#") and key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    lines.extend(f"{key}={value}" for key, value in pending.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_setup(
    token: str,
    *,
    env_path: Path | None,
    timeout: float = 120.0,
    client: httpx.Client | None = None,
    out: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
) -> ChatInfo | None:
    """Interactive flow. Returns the chat found (None on timeout); NotifyError on API errors."""
    client = client or httpx.Client(timeout=15.0)
    bot = get_me(client, token)
    out(f"Bot: {bot.first_name} (@{bot.username})")
    out(f"Now open https://t.me/{bot.username} in Telegram, press Start and send any message.")
    out(f"Waiting up to {int(timeout)} seconds...")
    chat = wait_for_chat(client, token, timeout=timeout, sleep=sleep)
    if chat is None:
        out("No message received. Make sure you wrote to that exact bot, then run this again.")
        return None
    out(f"Found chat {chat.chat_id} ({chat.name}). Sending a test message...")
    TelegramNotifier(token, chat.chat_id, client).send(TEST_MESSAGE)
    out("Test message sent. Check your phone.")
    if env_path is not None:
        update_env_file(env_path, {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat.chat_id})
        out(f"Saved TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to {env_path}")
    else:
        out(f"TELEGRAM_CHAT_ID={chat.chat_id}")
    return chat
