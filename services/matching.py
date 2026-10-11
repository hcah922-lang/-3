"""Логика лайков и совпадений."""
from __future__ import annotations
from database import Database


async def process_like(db: Database, from_id: int, to_id: int) -> dict[str, bool]:
    if from_id == to_id:
        return {"new": False, "match": False}
    if await db.is_blocked_between(from_id, to_id):
        return {"new": False, "match": False, "blocked": True}
    is_new = await db.add_like(from_id, to_id)
    mutual = await db.has_like(to_id, from_id)
    matched = False
    if mutual:
        matched = await db.create_match(from_id, to_id)
        # если уже был матч — считаем совпадением для уведомления только при создании
    return {"new": is_new, "match": matched or (mutual and True)}
