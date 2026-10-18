from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from carbotfinder.errors import NotifyError
from carbotfinder.setup_telegram import (
    TEST_MESSAGE,
    latest_private_chat,
    run_setup,
    update_env_file,
)

TOKEN = "123:ABC"
API = f"https://api.telegram.org/bot{TOKEN}"
PRIVATE = {
    "message": {"chat": {"id": 42, "type": "private", "first_name": "Ana", "last_name": "P"}}
}
GROUP = {"message": {"chat": {"id": -7, "type": "group", "title": "x"}}}


def test_latest_private_chat_prefers_most_recent_private_message() -> None:
    older = {"message": {"chat": {"id": 1, "type": "private", "username": "old"}}}
    chat = latest_private_chat([older, PRIVATE, GROUP])
    assert chat is not None and chat.chat_id == "42" and chat.name == "Ana P"
    assert latest_private_chat([GROUP]) is None
    assert latest_private_chat([]) is None


def test_update_env_file_replaces_keys_and_keeps_the_rest(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\nTELEGRAM_BOT_TOKEN=old\nOTHER=1\n", encoding="utf-8")
    update_env_file(env, {"TELEGRAM_BOT_TOKEN": "new", "TELEGRAM_CHAT_ID": "42"})
    assert env.read_text(encoding="utf-8") == (
        "# comment\nTELEGRAM_BOT_TOKEN=new\nOTHER=1\nTELEGRAM_CHAT_ID=42\n"
    )


def test_update_env_file_creates_missing_file(tmp_path: Path) -> None:
    env = tmp_path / "sub" / ".env"
    env.parent.mkdir()
    update_env_file(env, {"TELEGRAM_CHAT_ID": "42"})
    assert env.read_text(encoding="utf-8") == "TELEGRAM_CHAT_ID=42\n"


@respx.mock
def test_run_setup_finds_chat_sends_test_and_writes_env(tmp_path: Path) -> None:
    respx.get(f"{API}/getMe").mock(
        return_value=httpx.Response(
            200, json={"ok": True, "result": {"username": "my_bot", "first_name": "My Bot"}}
        )
    )
    updates = respx.get(f"{API}/getUpdates")
    updates.side_effect = [
        httpx.Response(200, json={"ok": True, "result": []}),
        httpx.Response(200, json={"ok": True, "result": [GROUP, PRIVATE]}),
    ]
    send = respx.post(f"{API}/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    sleeps: list[float] = []
    out: list[str] = []
    env = tmp_path / ".env"

    chat = run_setup(
        TOKEN, env_path=env, client=httpx.Client(), out=out.append, sleep=sleeps.append
    )

    assert chat is not None and chat.chat_id == "42"
    assert sleeps == [2.0]  # one empty poll, then the message arrived
    assert send.calls[0].request.content and b"42" in send.calls[0].request.content
    assert TEST_MESSAGE.encode() in send.calls[0].request.content
    assert env.read_text(encoding="utf-8") == f"TELEGRAM_BOT_TOKEN={TOKEN}\nTELEGRAM_CHAT_ID=42\n"
    assert any("@my_bot" in line for line in out)


@respx.mock
def test_run_setup_times_out_without_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(f"{API}/getMe").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"username": "b"}})
    )
    respx.get(f"{API}/getUpdates").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": []})
    )
    respx.post(f"{API}/sendMessage").mock(return_value=httpx.Response(200, json={"ok": True}))
    clock = iter([0.0, 0.0, 10.0])  # start, first poll, second poll past the deadline
    monkeypatch.setattr("carbotfinder.setup_telegram.time.monotonic", lambda: next(clock))
    env = tmp_path / ".env"

    chat = run_setup(
        TOKEN,
        env_path=env,
        timeout=5,
        client=httpx.Client(),
        out=lambda _: None,
        sleep=lambda _: None,
    )

    assert chat is None and not env.exists()


@respx.mock
def test_run_setup_rejects_bad_token() -> None:
    respx.get(f"{API}/getMe").mock(return_value=httpx.Response(401, json={"ok": False}))
    with pytest.raises(NotifyError, match="rejected the token"):
        run_setup(TOKEN, env_path=None, client=httpx.Client(), out=lambda _: None)
