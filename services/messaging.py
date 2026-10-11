"""Проверка права на переписку и пересылка через бота."""
from __future__ import annotations
from database import Database


async def can_chat(db: Database, a: int, b: int) -> tuple[bool, str]:
    if a == b:
        return False, "Нельзя писать самому себе."
    u = await db.get_user(b)
    if not u or u.get("is_banned"):
        return False, "Пользователь недоступен."
    if await db.is_blocked_between(a, b):
        return False, "Общение заблокировано."
    if not await db.has_match(a, b):
        return False, "Переписка доступна только после взаимного совпадения."
    return True, ""
