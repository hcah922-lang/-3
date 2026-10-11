from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def gender_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Мужской", callback_data="pf:gender:male"))
    b.add(InlineKeyboardButton(text="Женский", callback_data="pf:gender:female"))
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="profile:back"))
    b.add(InlineKeyboardButton(text="❌ Отмена", callback_data="profile:cancel"))
    b.adjust(2)
    return b.as_markup()


def looking_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Мужчину", callback_data="pf:looking:male"))
    b.add(InlineKeyboardButton(text="Женщину", callback_data="pf:looking:female"))
    b.add(InlineKeyboardButton(text="Всех", callback_data="pf:looking:any"))
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="profile:back"))
    b.add(InlineKeyboardButton(text="❌ Отмена", callback_data="profile:cancel"))
    b.adjust(2)
    return b.as_markup()


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)],
                  [KeyboardButton(text="⏭ Пропустить")],
                  [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True, one_time_keyboard=True)


def phone_inline_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="⏭ Пропустить без номера", callback_data="profile:skip"))
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="profile:back"))
    b.add(InlineKeyboardButton(text="❌ Отмена", callback_data="profile:cancel"))
    b.adjust(1)
    return b.as_markup()


def city_geo_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Отправить местоположение", request_location=True)],
                  [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True, one_time_keyboard=True)


def city_inline_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="profile:back"))
    b.add(InlineKeyboardButton(text="❌ Отмена", callback_data="profile:cancel"))
    b.adjust(2)
    return b.as_markup()


def preview_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="✅ Опубликовать", callback_data="profile:publish"))
    b.add(InlineKeyboardButton(text="✏️ Изменить", callback_data="menu:edit"))
    b.add(InlineKeyboardButton(text="❌ Отмена", callback_data="profile:cancel"))
    b.adjust(2)
    return b.as_markup()


def edit_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in [("profile_name", "Имя"), ("age", "Возраст"), ("gender", "Пол"),
                       ("looking_for", "Предпочтения"), ("city", "Город"), ("bio", "Описание"),
                       ("interests", "Интересы"), ("photo", "Фото"), ("phone", "Телефон"),
                       ("zodiac", "Зодиак"), ("height", "Рост"), ("education", "Образование"),
                       ("job", "Работа"), ("languages", "Языки"), ("kids", "Дети"),
                       ("smoking", "Курение"), ("alcohol", "Алкоголь"), ("goal", "Цель"),
                       ("schedule", "График")]:
        b.add(InlineKeyboardButton(text=label, callback_data=f"edit:{key}"))
    b.add(InlineKeyboardButton(text="👁 Скрыть", callback_data="profile:hide"))
    b.add(InlineKeyboardButton(text="♻️ Показать", callback_data="profile:unhide"))
    b.add(InlineKeyboardButton(text="🗑 Удалить", callback_data="profile:delete"))
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    b.adjust(2)
    return b.as_markup()
