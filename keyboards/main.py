from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="💘 Смотреть анкеты", callback_data="menu:browse"))
    b.add(InlineKeyboardButton(text="📝 Создать анкету", callback_data="menu:create"))
    b.add(InlineKeyboardButton(text="👤 Моя анкета", callback_data="menu:my"))
    b.add(InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="menu:edit"))
    b.add(InlineKeyboardButton(text="❤️ Мои лайки", callback_data="menu:likes"))
    b.add(InlineKeyboardButton(text="💞 Мои совпадения", callback_data="menu:matches"))
    b.add(InlineKeyboardButton(text="💬 Мои чаты", callback_data="menu:chats"))
    b.add(InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"))
    b.add(InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"))
    b.adjust(2)
    return b.as_markup()


def back_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="❌ Отмена", callback_data="profile:cancel"))
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    b.adjust(2)
    return b.as_markup()


def skip_back_cancel(prefix: str = "profile") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"{prefix}:skip"))
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data=f"{prefix}:back"))
    b.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}:cancel"))
    b.adjust(2)
    return b.as_markup()
