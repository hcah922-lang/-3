"""Рассылка с rate-limit и учётом ошибок."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from config import config
from database import Database

SendFn = Callable[[int, str], Awaitable[bool]]


async def resolve_audience(db: Database, audience: str, admin_id: int) -> list[int]:
    if audience == "test":
        return [admin_id]
    if audience == "with_profile":
        return await db.get_all_user_ids(only_active_profile=True)
    if audience == "without_profile":
        return await db.get_all_user_ids(only_without_profile=True)
    return await db.get_all_user_ids()


async def run_broadcast(db: Database, bid: int, bot, audience_ids: list[int]) -> dict[str, int]:
    b = await db.get_broadcast(bid)
    if not b or b["status"] == "sending":
        return {"ok": 0, "fail": 0, "skipped": True}
    await db.update_broadcast(bid, status="sending")
    ok = fail = 0
    text = b.get("text") or ""
    photo = b.get("photo_file_id")
    for uid in audience_ids:
        try:
            u = await db.get_user(uid)
            if not u or u.get("is_banned") or not u.get("allow_broadcast", 1):
                fail += 1
                continue
            if photo:
                await bot.send_photo(uid, photo, caption=text[:1024] if text else None)
            else:
                await bot.send_message(uid, text)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(max(config.BROADCAST_DELAY, 0.05))
    from datetime import datetime, timezone
    await db.update_broadcast(bid, status="done", success_count=ok, fail_count=fail,
                              finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return {"ok": ok, "fail": fail}
