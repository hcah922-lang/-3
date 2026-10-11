"""Модерация: жалобы и блокировки."""
from __future__ import annotations
from database import Database

REPORT_REASONS = ["спам", "оскорбления", "мошенничество", "неподходящий контент", "фейк", "другое"]


async def file_report(db: Database, reporter: int, reported: int, reason: str, comment: str = "") -> int:
    if reason not in REPORT_REASONS:
        reason = "другое"
    return await db.add_report(reporter, reported, reason, comment[:500])
