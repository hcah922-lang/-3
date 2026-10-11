from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def card_kb(target_id: int, can_write: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="❤️ Нравится", callback_data=f"like:{target_id}"))
    b.add(InlineKeyboardButton(text="👎 Пропустить", callback_data=f"skip:{target_id}"))
    if can_write:
        b.add(InlineKeyboardButton(text="💬 Написать", callback_data=f"chat:{target_id}"))
    b.add(InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"block:{target_id}"))
    b.add(InlineKeyboardButton(text="⚠️ Пожаловаться", callback_data=f"report:{target_id}"))
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    b.adjust(2)
    return b.as_markup()


def report_reasons_kb(target_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in ["спам", "оскорбления", "мошенничество", "неподходящий контент", "фейк", "другое"]:
        b.add(InlineKeyboardButton(text=r, callback_data=f"report_go:{target_id}:{r}"))
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    b.adjust(2)
    return b.as_markup()
