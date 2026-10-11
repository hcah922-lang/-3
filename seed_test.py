"""Тестовый второй пользователь для проверки с одного аккаунта.

Запуск:  python seed_test.py <ТВОЙ_TELEGRAM_ID>
Создаёт виртуального пользователя 999888777 с опубликованной анкетой,
который уже лайкнул тебя. Дальше с телефона: Смотреть анкеты -> лайк ему ->
взаимное совпадение -> чаты -> админка (портрет, досье, фейки...).

Убрать: заблокируй 999888777 в админке (карточка пользователя -> Заблокировать).
"""
import asyncio
import sys

from config import config
from database import Database

FAKE_ID = 999888777


async def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        print("Использование: python seed_test.py <ТВОЙ_TELEGRAM_ID>")
        return
    me = int(sys.argv[1])
    db = Database(config.DATABASE_PATH)
    await db.init()
    await db.upsert_user(FAKE_ID, "test_girl", "Тест", "Анкета", "ru")
    await db.save_draft(FAKE_ID, {
        "profile_name": "Алиса", "age": 22, "gender": "female", "looking_for": "any",
        "city": "Киев", "bio": "Тестовая анкета для проверки", "interests": "музыка",
        "photo_file_id": None, "photo_unique_id": None, "phone_number": None,
        "zodiac": "Лев", "job": "тестировщик",
    })
    await db.publish_profile(FAKE_ID)
    await db.add_like(FAKE_ID, me)
    print(f"Готово: фейк {FAKE_ID} опубликован и лайкнул {me}. "
          "Ставь ему лайк в боте — будет совпадение.")


if __name__ == "__main__":
    asyncio.run(main())
