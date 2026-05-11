"""Basic smoke tests — keep these fast and CI-friendly."""
import os
import tempfile

import pytest

# Use a temp DB before importing the module
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DB_PATH"] = _TMP.name
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy:token")

from src import database as db  # noqa: E402


@pytest.mark.asyncio
async def test_subscribe_flow():
    await db.init_db()

    added = await db.add_subscriber(123, "alice")
    assert added is True

    added_again = await db.add_subscriber(123, "alice")
    assert added_again is False  # already subscribed

    count = await db.count_active()
    assert count == 1

    await db.remove_subscriber(123)
    count = await db.count_active()
    assert count == 0


@pytest.mark.asyncio
async def test_state_kv():
    await db.init_db()
    await db.set_state("foo", "bar")
    assert await db.get_state("foo") == "bar"
    await db.set_state("foo", "baz")
    assert await db.get_state("foo") == "baz"
    assert await db.get_state("missing") is None


@pytest.mark.asyncio
async def test_check_history():
    await db.init_db()
    await db.record_check("primary", available=False, message="no slots", duration_ms=1234)
    await db.record_check("primary", available=True, message="found!", duration_ms=987)

    rows = await db.recent_checks(10)
    assert len(rows) >= 2

    stats = await db.check_stats(hours=24)
    assert stats["total"] >= 2
    assert stats["hits"] >= 1
