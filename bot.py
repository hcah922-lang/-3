"""Точка входа Dating Bot (aiogram 3.x)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, Message

from config import config
from database import Database


class UserMiddleware(BaseMiddleware):
    """Автоматический upsert пользователя, активность и воронка при каждом апдейте."""

    def __init__(self, db: Database):
        self.db = db

    async def __call__(self, handler: Callable[[TelegramObject, dict], Awaitable[Any]],
                       event: TelegramObject, data: dict) -> Any:
        user = data.get("event_from_user")
        if user is not None:
            try:
                await self.db.upsert_user(user.id, user.username, user.first_name,
                                          user.last_name, user.language_code,
                                          getattr(user, "is_premium", None))
            except Exception as e:
                logging.warning("upsert failed: %s", e)
            try:
                await self.db.log_activity(user.id)
            except Exception as e:
                logging.warning("activity failed: %s", e)
            try:
                if isinstance(event, Message) and (event.text or "").startswith("/start"):
                    await self.db.log_funnel(user.id, "start")
            except Exception as e:
                logging.warning("funnel failed: %s", e)
        return await handler(event, data)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        config.validate()
    except ValueError as e:
        print(f"❌ {e}\nСкопируй .env.example в .env и заполни значения.")
        return
    db = Database(config.DATABASE_PATH)
    await db.init()
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(UserMiddleware(db))
    dp.callback_query.outer_middleware(UserMiddleware(db))

    from handlers import start, profile, discovery, likes, matches, chat, settings, admin
    # admin вторым: команда /admin356872 должна срабатывать даже внутри FSM-состояний
    dp.include_routers(start.router, admin.router, profile.router, discovery.router, likes.router,
                       matches.router, chat.router, settings.router)

    print("🤖 Dating Bot запущен. Останови: Ctrl+C")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
