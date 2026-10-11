import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


def get_admin_ids() -> list[int]:
    """Получает список ID администраторов из переменной окружения."""
    raw = os.getenv("ADMIN_IDS", "")
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


class Config:
    """Конфигурация бота."""

    # Основные настройки
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = get_admin_ids()
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "356872")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/bot.db")

    # Админ-сессия
    ADMIN_SESSION_MINUTES: int = int(os.getenv("ADMIN_SESSION_MINUTES", "30"))

    # Рассылки
    BROADCAST_DELAY: float = float(os.getenv("BROADCAST_DELAY", "0.05"))

    # Константы бота
    ADMIN_COMMAND: str = "/admin356872"
    MIN_AGE: int = 18
    MAX_AGE: int = 100
    MAX_BIO_LENGTH: int = 1000
    MAX_INTERESTS_LENGTH: int = 500
    MAX_PROFILE_NAME_LENGTH: int = 50
    MAX_CITY_LENGTH: int = 100

    # Пагинация
    USERS_PER_PAGE: int = 10
    PROFILES_PER_PAGE: int = 1

    # Лимиты
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_BLOCK_MINUTES: int = 15

    @classmethod
    def validate(cls) -> None:
        """Проверяет обязательные настройки."""
        if not cls.BOT_TOKEN or cls.BOT_TOKEN == "PUT_YOUR_NEW_BOT_TOKEN_HERE":
            raise ValueError("BOT_TOKEN не задан в .env")
        if not cls.ADMIN_IDS:
            raise ValueError("ADMIN_IDS не задан в .env")
        if cls.ADMIN_PASSWORD == "CHANGE_THIS_PASSWORD":
            print("⚠️ ВНИМАНИЕ: Используется пароль по умолчанию! Измените ADMIN_PASSWORD в .env")


config = Config()