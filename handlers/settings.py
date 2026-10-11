"""Настройки пользователя."""
from __future__ import annotations
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from config import config
from database import Database
from keyboards.main import back_menu
from keyboards.profile import city_geo_kb
from services.geo import reverse_city

router = Router()

class SetFSM(StatesGroup):
    age_range = State()
    city = State()
    geo = State()

def db() -> Database:
    return Database(config.DATABASE_PATH)

def settings_kb(u: dict) -> object:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text=f"Лайки: {'✅' if u.get('notify_likes',1) else '❌'}", callback_data="set:t:likes"))
    b.add(InlineKeyboardButton(text=f"Совпадения: {'✅' if u.get('notify_matches',1) else '❌'}", callback_data="set:t:matches"))
    b.add(InlineKeyboardButton(text=f"Сообщения: {'✅' if u.get('notify_messages',1) else '❌'}", callback_data="set:t:messages"))
    b.add(InlineKeyboardButton(text=f"Рассылка: {'✅' if u.get('allow_broadcast',1) else '❌'}", callback_data="set:t:broadcast"))
    b.add(InlineKeyboardButton(text=f"Возраст: {u.get('search_min_age',18)}–{u.get('search_max_age',100)}", callback_data="set:age"))
    b.add(InlineKeyboardButton(text=f"Город: {u.get('search_city') or 'любой'}", callback_data="set:city"))
    b.add(InlineKeyboardButton(text=f"Пол: {u.get('search_gender') or 'любой'}", callback_data="set:gender"))
    r = u.get("search_radius_km")
    b.add(InlineKeyboardButton(text=f"📍 Рядом: {f'{r} км' if r else 'выкл'}", callback_data="set:radius"))
    b.add(InlineKeyboardButton(text="📍 Обновить геолокацию", callback_data="set:geo"))
    b.add(InlineKeyboardButton(text="🗑 Удалить анкету", callback_data="set:del_profile"))
    b.add(InlineKeyboardButton(text="🧨 Удалить все данные", callback_data="set:del_all"))
    b.add(InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"))
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    b.adjust(2)
    return b.as_markup()

@router.callback_query(F.data == "menu:settings")
async def cb_settings(cb: CallbackQuery):
    d = db()
    me = await d.get_profile(cb.from_user.id)
    if not me or me.get("profile_status") != "active":
        await cb.message.answer("⚠️ Сначала создай анкету — нажми «📝 Создать анкету».", reply_markup=back_menu())
        await cb.answer()
        return
    u = await d.get_user(cb.from_user.id) or {}
    try:
        await cb.message.edit_text("⚙️ <b>Настройки</b>", reply_markup=settings_kb(u))
    except Exception:
        await cb.message.answer("⚙️ <b>Настройки</b>", reply_markup=settings_kb(u))
    await cb.answer()

@router.callback_query(F.data.startswith("set:t:"))
async def cb_toggle(cb: CallbackQuery):
    kind = cb.data.split(":")[2]
    d = db()
    u = await d.get_user(cb.from_user.id) or {}
    mapping = {"likes": "notify_likes", "matches": "notify_matches", "messages": "notify_messages", "broadcast": "allow_broadcast"}
    col = mapping[kind]
    await d.update_user_fields(cb.from_user.id, **{col: 0 if u.get(col, 1) else 1})
    u2 = await d.get_user(cb.from_user.id) or {}
    try:
        await cb.message.edit_reply_markup(reply_markup=settings_kb(u2))
    except Exception:
        pass
    await cb.answer("Сохранено.")

@router.callback_query(F.data == "set:age")
async def cb_age(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SetFSM.age_range)
    await cb.message.answer("Введи диапазон возраста через дефис, например 20-35:")
    await cb.answer()

@router.message(SetFSM.age_range)
async def msg_age(msg: Message, state: FSMContext):
    try:
        a, b = msg.text.replace(" ", "").split("-")
        a, b = int(a), int(b)
        assert 18 <= a <= b <= 100
    except Exception:
        await msg.answer("Формат: 20-35 (18–100).")
        return
    await db().update_user_fields(msg.from_user.id, search_min_age=a, search_max_age=b)
    await state.clear()
    await msg.answer(f"Возраст {a}–{b} сохранён.", reply_markup=back_menu())

@router.callback_query(F.data == "set:city")
async def cb_city(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SetFSM.city)
    await cb.message.answer("Введи город для поиска или «-» чтобы сбросить:")
    await cb.answer()

@router.message(SetFSM.city)
async def msg_city(msg: Message, state: FSMContext):
    import re
    v = (msg.text or "").strip()
    if v != "-":
        if len(v) < 2 or len(v) > 100 or not re.fullmatch(r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґ'’\-\s.]+", v):
            await msg.answer("Такой город не похож на настоящий: только буквы, пробелы и дефис, 2–100 символов. Введи ещё раз или «-».")
            return
        v = "-".join(p[:1].upper() + p[1:].lower() if p else "" for p in v.split("-"))
    else:
        v = None
    await db().update_user_fields(msg.from_user.id, search_city=v)
    await state.clear()
    await msg.answer("Город сохранён.", reply_markup=back_menu())

@router.callback_query(F.data == "set:radius")
async def cb_radius(cb: CallbackQuery):
    d = db()
    u = await d.get_user(cb.from_user.id) or {}
    steps = [None, 10, 25, 50, 100]
    try:
        nxt = steps[(steps.index(u.get("search_radius_km")) + 1) % len(steps)]
    except ValueError:
        nxt = 10
    if nxt is None:
        import aiosqlite
        async with aiosqlite.connect(config.DATABASE_PATH) as c:
            await c.execute("UPDATE users SET search_radius_km=NULL WHERE telegram_id=?", (cb.from_user.id,))
            await c.commit()
    else:
        await d.update_user_fields(cb.from_user.id, search_radius_km=nxt)
    u2 = await d.get_user(cb.from_user.id) or {}
    try:
        await cb.message.edit_reply_markup(reply_markup=settings_kb(u2))
    except Exception:
        pass
    await cb.answer(f"Радиус: {f'{nxt} км' if nxt else 'выкл'}")


@router.callback_query(F.data == "set:geo")
async def cb_geo(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SetFSM.geo)
    await cb.message.answer("📍 Нажми «📍 Отправить местоположение» или отправь «-», чтобы стереть координаты.",
                            reply_markup=city_geo_kb())
    await cb.answer()


@router.message(SetFSM.geo)
async def msg_geo(msg: Message, state: FSMContext):
    d = db()
    if msg.location:
        rev = await reverse_city(msg.location.latitude, msg.location.longitude)
        if not rev:
            await msg.answer("Не вышло определить город. Попробуй ещё раз.", reply_markup=city_geo_kb())
            return
        await d.update_profile_fields(msg.from_user.id, latitude=rev["lat"], longitude=rev["lon"],
                                      city=rev["city"])
        await d.log_geo(msg.from_user.id, rev["lat"], rev["lon"], rev["city"])
        await state.clear()
        await msg.answer(f"📍 Геолокация обновлена ({rev['city']}). Точные координаты никому не показываются.",
                         reply_markup=ReplyKeyboardRemove())
        return
    if (msg.text or "").strip() == "-":
        import aiosqlite
        async with aiosqlite.connect(config.DATABASE_PATH) as c:
            await c.execute("UPDATE profiles SET latitude=NULL, longitude=NULL WHERE telegram_id=?",
                            (msg.from_user.id,))
            await c.commit()
        await state.clear()
        await msg.answer("Координаты стёрты.", reply_markup=ReplyKeyboardRemove())
        return
    await msg.answer("Отправь местоположение кнопкой 📍 или «-».", reply_markup=city_geo_kb())


@router.callback_query(F.data == "set:gender")
async def cb_gender(cb: CallbackQuery):
    d = db()
    u = await d.get_user(cb.from_user.id) or {}
    cur = u.get("search_gender")
    nxt = {"male": "female", "female": None, None: "male"}.get(cur, "male")
    # None хранится как NULL — сбросим через прямой SQL
    if nxt is None:
        import aiosqlite
        async with aiosqlite.connect(config.DATABASE_PATH) as c:
            await c.execute("UPDATE users SET search_gender=NULL WHERE telegram_id=?", (cb.from_user.id,))
            await c.commit()
    else:
        await d.update_user_fields(cb.from_user.id, search_gender=nxt)
    u2 = await d.get_user(cb.from_user.id) or {}
    try:
        await cb.message.edit_reply_markup(reply_markup=settings_kb(u2))
    except Exception:
        pass
    await cb.answer()

@router.callback_query(F.data == "set:del_profile")
async def cb_del_p(cb: CallbackQuery):
    await db().set_profile_status(cb.from_user.id, "deleted")
    await cb.message.answer("Анкета удалена и исключена из поиска.", reply_markup=back_menu())
    await cb.answer()

@router.callback_query(F.data == "set:del_all")
async def cb_del_all(cb: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder as B
    b = B()
    b.add(InlineKeyboardButton(text="✅ Да, удалить всё", callback_data="set:del_all_yes"))
    b.add(InlineKeyboardButton(text="❌ Нет", callback_data="menu:main"))
    b.adjust(1)
    await cb.message.answer("⚠️ Удалить анкету и данные профиля? Это необратимо.", reply_markup=b.as_markup())
    await cb.answer()

@router.callback_query(F.data == "set:del_all_yes")
async def cb_del_all_yes(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await db().wipe_user_data(cb.from_user.id)
    # пересоздаём базовую запись чтобы бот продолжал работать
    from aiogram.types import User as TgUser
    u = cb.from_user
    await db().upsert_user(u.id, u.username, u.first_name, u.last_name, u.language_code)
    await cb.message.answer("Все данные удалены.", reply_markup=back_menu())
    await cb.answer()
