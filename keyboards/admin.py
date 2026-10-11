from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    items = [("📊 Статистика", "adm:stats"), ("👥 Все пользователи", "adm:users:0"),
             ("📝 Все анкеты", "adm:profiles:0"), ("🔍 Поиск пользователя", "adm:search"),
             ("🚫 Заблокированные", "adm:blocked"), ("⚠️ Жалобы", "adm:reports"),
             ("📈 Воронка", "adm:funnel"), ("🕸 Связи", "adm:graph"),
             ("⏰ Активность", "adm:heat"), ("🚨 Фейки", "adm:fakes"),
             ("👁 Слова", "adm:watch"),
             ("📅 Когорты", "adm:cohorts"), ("🔗 Приглашения", "adm:invites"),
             ("📄 Экспорт в TXT", "adm:exp_txt"), ("📦 Экспорт в JSON", "adm:exp_json"),
             ("📣 Создать рассылку", "adm:bcast"), ("📋 История рассылок", "adm:bcast_hist"),
             ("📜 Журнал действий", "adm:logs"), ("🔒 Выйти из панели", "adm:logout")]
    for text, cb in items:
        b.add(InlineKeyboardButton(text=text, callback_data=cb))
    b.adjust(2)
    return b.as_markup()


def admin_back() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu"))
    return b.as_markup()


def pag_kb(prefix: str, page: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if page > 0:
        b.add(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}:{page-1}"))
    b.add(InlineKeyboardButton(text=f"{page+1}", callback_data="noop"))
    b.add(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}:{page+1}"))
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu"))
    b.adjust(3)
    return b.as_markup()


def user_card_kb(tid: int, banned: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🕵️ Портрет", callback_data=f"adm_u:portrait:{tid}"))
    b.add(InlineKeyboardButton(text="📄 Досье", callback_data=f"adm_u:dossier:{tid}"))
    b.add(InlineKeyboardButton(text="🕸 Круг", callback_data=f"adm_u:circle:{tid}"))
    b.add(InlineKeyboardButton(text="Скрыть анкету", callback_data=f"adm_u:hide:{tid}"))
    b.add(InlineKeyboardButton(text="Показать анкету", callback_data=f"adm_u:unhide:{tid}"))
    b.add(InlineKeyboardButton(text="Удалить анкету", callback_data=f"adm_u:del:{tid}"))
    if banned:
        b.add(InlineKeyboardButton(text="Разблокировать", callback_data=f"adm_u:unban:{tid}"))
    else:
        b.add(InlineKeyboardButton(text="Заблокировать", callback_data=f"adm_u:ban:{tid}"))
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu"))
    b.adjust(2)
    return b.as_markup()


def reports_kb(rid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="✅ Принять", callback_data=f"adm_r:ok:{rid}"))
    b.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_r:no:{rid}"))
    b.add(InlineKeyboardButton(text="👁 Скрыть анкету", callback_data=f"adm_r:hide:{rid}"))
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu"))
    b.adjust(2)
    return b.as_markup()
