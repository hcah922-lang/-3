"""Создание и редактирование анкеты."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from config import config
from database import Database
from states.profile import ProfileFSM
from keyboards.main import back_menu, cancel_kb, skip_back_cancel
from keyboards.profile import (gender_kb, looking_kb, phone_request_kb, phone_inline_kb,
                                 city_geo_kb, city_inline_kb, preview_kb, edit_menu_kb)
from services.security import esc, profile_text
from services.geo import forward_city, reverse_city

router = Router()


def valid_city(value: str) -> str | None:
    """Проверка названия города. Возвращает нормализованное имя или None."""
    import re
    v = (value or "").strip()
    if len(v) < 2 or len(v) > 100:
        return None
    if not re.fullmatch(r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґ'’\-\s.]+", v):
        return None
    letters = [c for c in v if c.isalpha()]
    if len(letters) < 2:
        return None
    return "-".join(p[:1].upper() + p[1:].lower() if p else "" for p in v.split("-"))
ORDER = ["name", "age", "gender", "looking_for", "city", "bio", "interests", "photo", "phone"]
PROMPTS = {
    "name": "Как тебя называть? (до 50 символов)",
    "age": "Сколько тебе лет? (только 18+)",
    "gender": "Какой у тебя пол?",
    "looking_for": "Кого ты хочешь найти?",
    "city": "В каком городе ты живёшь? Напиши название или нажми «📍 Отправить местоположение» — город проверим онлайн.",
    "bio": "Расскажи немного о себе (до 1000 символов). Можно пропустить.",
    "interests": "Какие у тебя интересы? (до 500 символов). Можно пропустить.",
    "photo": "Добавь фотографию. Отправь фото или нажми «Пропустить».",
    "phone": "Хочешь указать номер телефона? Это необязательно.\nНажми «📱 Отправить контакт», чтобы поделиться номером, или «⏭ Пропустить».\nНомер будет виден только тебе в разделе «Моя анкета».",
}
STATE_BY_FIELD = {"name": ProfileFSM.name, "age": ProfileFSM.age, "gender": ProfileFSM.gender,
                  "looking_for": ProfileFSM.looking_for, "city": ProfileFSM.city, "bio": ProfileFSM.bio,
                  "interests": ProfileFSM.interests, "photo": ProfileFSM.photo, "phone": ProfileFSM.phone,
                  "extra": ProfileFSM.extra}

# дополнительные поля анкеты: все необязательные, свободный текст
EXTRA = [
    ("zodiac", "Знак зодиака", "Твой знак зодиака?"),
    ("height", "Рост", "Твой рост в см? Например 175."),
    ("education", "Образование", "Какое у тебя образование?"),
    ("job", "Работа", "Кем работаешь?"),
    ("languages", "Языки", "Какими языками владеешь?"),
    ("kids", "Дети", "Есть ли дети?"),
    ("smoking", "Курение", "Куришь?"),
    ("alcohol", "Алкоголь", "Как относишься к алкоголю?"),
    ("goal", "Цель", "Что ищешь здесь?"),
    ("schedule", "График", "Когда удобно общаться?"),
]


async def ask_extra(msg_or_cb, state: FSMContext):
    data = await state.get_data()
    idx = data.get("extra_idx", 0)
    if idx >= len(EXTRA):
        await ask_field(msg_or_cb, state, "photo")
        return
    key, label, prompt = EXTRA[idx]
    await state.set_state(ProfileFSM.extra)
    text = f"{prompt}\n(Дополнительно {idx + 1}/{len(EXTRA)}. Можно пропустить.)"
    kb = skip_back_cancel()
    if hasattr(msg_or_cb, "message") and hasattr(msg_or_cb, "data"):
        try:
            await msg_or_cb.message.edit_text(text, reply_markup=kb)
        except Exception:
            await msg_or_cb.message.answer(text, reply_markup=kb)
        await msg_or_cb.answer()
    else:
        await msg_or_cb.answer(text, reply_markup=kb)


def db() -> Database:
    return Database(config.DATABASE_PATH)


async def ask_field(msg_or_cb, state: FSMContext, field: str):
    kb = None
    if field == "gender":
        kb = gender_kb()
    elif field == "looking_for":
        kb = looking_kb()
    elif field in ("bio", "interests", "city", "name", "age"):
        kb = skip_back_cancel()
    elif field == "photo":
        kb = skip_back_cancel()
    await state.set_state(STATE_BY_FIELD[field])
    text = PROMPTS[field]
    if field == "phone":
        # reply-кнопку контакта нельзя отредактировать в старом сообщении —
        # всегда шлём новое + инлайн-кнопки пропуска/назад/отмены
        if hasattr(msg_or_cb, "message") and hasattr(msg_or_cb, "data"):
            await msg_or_cb.message.answer(text, reply_markup=phone_request_kb())
            await msg_or_cb.message.answer("Или выбери действие кнопкой ниже:",
                                           reply_markup=phone_inline_kb())
            await msg_or_cb.answer()
        else:
            await msg_or_cb.answer(text, reply_markup=phone_request_kb())
            await msg_or_cb.answer("Или выбери действие кнопкой ниже:",
                                   reply_markup=phone_inline_kb())
        return
    if field == "city":
        # кнопка геолокации — тоже reply-клавиатура, шлём новым сообщением
        if hasattr(msg_or_cb, "message") and hasattr(msg_or_cb, "data"):
            await msg_or_cb.message.answer(text, reply_markup=city_geo_kb())
            await msg_or_cb.message.answer("Или вернись назад:", reply_markup=city_inline_kb())
            await msg_or_cb.answer()
        else:
            await msg_or_cb.answer(text, reply_markup=city_geo_kb())
            await msg_or_cb.answer("Или вернись назад:", reply_markup=city_inline_kb())
        return
    if hasattr(msg_or_cb, "message") and hasattr(msg_or_cb, "data"):
        try:
            await msg_or_cb.message.edit_text(text, reply_markup=kb)
        except Exception:
            await msg_or_cb.message.answer(text, reply_markup=kb)
        await msg_or_cb.answer()
    else:
        if field == "phone":
            await msg_or_cb.answer(text, reply_markup=phone_request_kb())
        else:
            await msg_or_cb.answer(text, reply_markup=kb)


async def show_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    p = {"profile_name": data.get("profile_name"), "age": data.get("age"), "gender": data.get("gender"),
         "looking_for": data.get("looking_for"), "city": data.get("city"), "bio": data.get("bio"),
         "interests": data.get("interests")}
    txt = profile_text(p) + "\n\nОпубликовать анкету?"
    await state.set_state(ProfileFSM.preview)
    photo = data.get("photo_file_id")
    if photo:
        try:
            await message.answer_photo(photo, caption=txt, reply_markup=preview_kb())
            return
        except Exception:
            pass
    await message.answer(txt, reply_markup=preview_kb())


@router.callback_query(F.data == "menu:create")
async def cb_create(cb: CallbackQuery, state: FSMContext):
    d = db()
    prof = await d.get_profile(cb.from_user.id)
    if prof and prof.get("profile_status") == "active":
        await cb.answer("У тебя уже есть опубликованная анкета. Смотри раздел «Моя анкета».", show_alert=True)
        return
    await begin_creation(cb.message, state)
    await cb.answer()


async def begin_creation(msg: Message, state: FSMContext):
    """Принудительный вход: сразу первый вопрос, без меню."""
    await state.clear()
    await state.set_data({})
    await msg.answer("👋 Сначала создай анкету — без неё дальше нельзя.")
    await ask_field(msg, state, "name")


@router.callback_query(F.data == "menu:my")
async def cb_my(cb: CallbackQuery):
    d = db()
    p = await d.get_profile(cb.from_user.id)
    if not p or p.get("profile_status") == "deleted":
        await cb.answer("Анкеты пока нет. Создай её!", show_alert=True)
        return
    txt = profile_text(p) + f"\n\nСтатус: {p.get('profile_status')}"
    if p.get("phone_number"):
        txt += f"\nТелефон: {esc(p.get('phone_number'))} (виден только тебе)"
    try:
        if p.get("photo_file_id"):
            await cb.message.answer_photo(p["photo_file_id"], caption=txt)
        else:
            await cb.message.answer(txt)
    except Exception:
        await cb.message.answer(txt)
    await cb.answer()


@router.callback_query(F.data == "menu:edit")
async def cb_edit_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    d = db()
    p = await d.get_profile(cb.from_user.id)
    if not p:
        await cb.answer("Сначала создай анкету.", show_alert=True)
        return
    try:
        await cb.message.edit_text("✏️ Что изменить?", reply_markup=edit_menu_kb())
    except Exception:
        await cb.message.answer("✏️ Что изменить?", reply_markup=edit_menu_kb())
    await cb.answer()


# --- FSM шаги ---
@router.message(ProfileFSM.name)
async def step_name(msg: Message, state: FSMContext):
    v = (msg.text or "").strip()
    if not v or len(v) > config.MAX_PROFILE_NAME_LENGTH:
        await msg.answer("Имя от 1 до 50 символов. Попробуй ещё раз.", reply_markup=skip_back_cancel())
        return
    await state.update_data(profile_name=v)
    await db().save_draft(msg.from_user.id, await state.get_data())
    await db().log_funnel(msg.from_user.id, "name")
    await ask_field(msg, state, "age")


@router.message(ProfileFSM.age)
async def step_age(msg: Message, state: FSMContext):
    try:
        age = int((msg.text or "").strip())
    except ValueError:
        await msg.answer("Введи возраст числом.", reply_markup=skip_back_cancel())
        return
    if age < config.MIN_AGE:
        await msg.answer("⛔ Извини, бот только для 18+. Анкета не может быть опубликована.",
                         reply_markup=back_menu())
        await state.clear()
        return
    if age > config.MAX_AGE:
        await msg.answer("Введи реальный возраст (18–100).", reply_markup=skip_back_cancel())
        return
    await state.update_data(age=age)
    await db().save_draft(msg.from_user.id, await state.get_data())
    await db().log_funnel(msg.from_user.id, "age")
    await ask_field(msg, state, "gender")


@router.callback_query(F.data.startswith("pf:gender:"))
async def step_gender(cb: CallbackQuery, state: FSMContext):
    g = cb.data.split(":")[-1]
    data = await state.get_data()
    # режим одиночного редактирования
    if data.get("edit_field") == "gender":
        await db().update_profile_fields(cb.from_user.id, gender=g)
        await state.clear()
        await cb.message.answer("✅ Пол обновлён.", reply_markup=back_menu())
        await cb.answer()
        return
    cur = await state.get_state()
    if cur != ProfileFSM.gender:
        await cb.answer()
        return
    await state.update_data(gender=g)
    await db().save_draft(cb.from_user.id, await state.get_data())
    await db().log_funnel(cb.from_user.id, "gender")
    await ask_field(cb, state, "looking_for")


@router.callback_query(F.data.startswith("pf:looking:"))
async def step_looking(cb: CallbackQuery, state: FSMContext):
    v = cb.data.split(":")[-1]
    data = await state.get_data()
    if data.get("edit_field") == "looking_for":
        await db().update_profile_fields(cb.from_user.id, looking_for=v)
        await state.clear()
        await cb.message.answer("✅ Предпочтения обновлены.", reply_markup=back_menu())
        await cb.answer()
        return
    cur = await state.get_state()
    if cur != ProfileFSM.looking_for:
        await cb.answer()
        return
    await state.update_data(looking_for=v)
    await db().save_draft(cb.from_user.id, await state.get_data())
    await db().log_funnel(cb.from_user.id, "looking_for")
    # need message obj for next prompt
    await ask_field(cb, state, "city")


@router.message(ProfileFSM.city)
async def step_city(msg: Message, state: FSMContext):
    d = db()
    if msg.location:
        # добровольная геолокация: город определяем онлайн, точные координаты другим не показываем
        rev = await reverse_city(msg.location.latitude, msg.location.longitude)
        if not rev:
            await msg.answer("Не вышло определить город по геолокации. Напиши город текстом.",
                             reply_markup=city_geo_kb())
            return
        norm = valid_city(rev["city"])
        if not norm:
            await msg.answer(f"Сервис вернул странное название («{rev['city']}»). Напиши город текстом.",
                             reply_markup=city_geo_kb())
            return
        await state.update_data(city=norm, latitude=rev["lat"], longitude=rev["lon"])
        await d.save_draft(msg.from_user.id, await state.get_data())
        await d.log_geo(msg.from_user.id, rev["lat"], rev["lon"], norm)
        await d.log_funnel(msg.from_user.id, "city")
        await msg.answer(f"📍 Город: {norm}. Точные координаты сохранены и никому не показываются.",
                         reply_markup=ReplyKeyboardRemove())
        await ask_field(msg, state, "bio")
        return
    raw = (msg.text or "").strip()
    if raw.lower() in ("❌ отмена", "отмена", "/cancel"):
        await state.clear()
        await msg.answer("Заполнение отменено. Черновик сохранён.", reply_markup=ReplyKeyboardRemove())
        await msg.answer("Напиши /start, чтобы начать сначала.", reply_markup=back_menu())
        return
    geo = await forward_city(raw)
    if geo and "error" in geo:
        # нет сети — принимаем по формату, без координат
        norm = valid_city(raw)
        if not norm:
            await msg.answer("Проверь название: только буквы, пробелы и дефис, 2–100 символов.",
                             reply_markup=city_geo_kb())
            return
        await state.update_data(city=norm, latitude=None, longitude=None)
        await d.save_draft(msg.from_user.id, await state.get_data())
        await d.log_funnel(msg.from_user.id, "city")
        await msg.answer("⚠️ Нет связи с проверкой городов — приняли по названию.",
                         reply_markup=ReplyKeyboardRemove())
        await ask_field(msg, state, "bio")
        return
    if not geo:
        await msg.answer("Такой город не найден. Проверь написание или отправь местоположение кнопкой 📍.",
                         reply_markup=city_geo_kb())
        return
    norm = valid_city(geo["city"]) or valid_city(raw)
    await state.update_data(city=norm, latitude=geo["lat"], longitude=geo["lon"])
    await d.save_draft(msg.from_user.id, await state.get_data())
    await d.log_funnel(msg.from_user.id, "city")
    await msg.answer(f"Город подтверждён: {norm}.", reply_markup=ReplyKeyboardRemove())
    await ask_field(msg, state, "bio")


@router.message(ProfileFSM.bio)
async def step_bio(msg: Message, state: FSMContext):
    v = (msg.text or "").strip()[: config.MAX_BIO_LENGTH]
    await state.update_data(bio=v or None)
    await db().save_draft(msg.from_user.id, await state.get_data())
    await db().log_funnel(msg.from_user.id, "bio")
    await ask_field(msg, state, "interests")


@router.message(ProfileFSM.interests)
async def step_interests(msg: Message, state: FSMContext):
    v = (msg.text or "").strip()[: config.MAX_INTERESTS_LENGTH]
    await state.update_data(interests=v or None)
    await db().save_draft(msg.from_user.id, await state.get_data())
    await db().log_funnel(msg.from_user.id, "interests")
    await state.update_data(extra_idx=0)
    await ask_extra(msg, state)


@router.message(ProfileFSM.extra)
async def step_extra(msg: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("extra_idx", 0)
    if idx >= len(EXTRA):
        await ask_field(msg, state, "photo")
        return
    key = EXTRA[idx][0]
    t = (msg.text or "").strip()
    if t.lower() in ("❌ отмена", "отмена", "/cancel"):
        await state.clear()
        await msg.answer("Заполнение отменено. Черновик сохранён.", reply_markup=back_menu())
        return
    val = None if t.lower() in ("⏭ пропустить", "пропустить", "⏭", "-") else t[:100]
    await state.update_data(**{key: val, "extra_idx": idx + 1})
    await db().save_draft(msg.from_user.id, await state.get_data())
    await ask_extra(msg, state)


@router.message(ProfileFSM.photo)
async def step_photo(msg: Message, state: FSMContext):
    if msg.photo:
        pic = msg.photo[-1]
        await state.update_data(photo_file_id=pic.file_id, photo_unique_id=pic.file_unique_id,
                                photo_width=pic.width, photo_height=pic.height,
                                photo_size=pic.file_size)
        await db().save_draft(msg.from_user.id, await state.get_data())
        await db().log_funnel(msg.from_user.id, "photo")
        await ask_field(msg, state, "phone")
    else:
        await msg.answer("Пришли фотографию или нажми «Пропустить».", reply_markup=skip_back_cancel())


@router.message(ProfileFSM.phone)
async def step_phone(msg: Message, state: FSMContext):
    d = db()
    if msg.contact:
        if msg.contact.user_id and msg.contact.user_id != msg.from_user.id:
            await msg.answer("Это чужой контакт. Нажми «📱 Отправить контакт» со своим номером или «⏭ Пропустить».",
                             reply_markup=phone_request_kb())
            return
        await state.update_data(phone_number=msg.contact.phone_number)
        await d.save_draft(msg.from_user.id, await state.get_data())
        await d.log_funnel(msg.from_user.id, "phone")
        await msg.answer("Номер сохранён.", reply_markup=ReplyKeyboardRemove())
        await show_preview(msg, state)
        return
    t = (msg.text or "").strip().lower()
    if t in ("⏭ пропустить", "пропустить", "/skip", "далее", "без номера", "⏭"):
        await msg.answer("Пропускаем номер.", reply_markup=ReplyKeyboardRemove())
        await d.log_funnel(msg.from_user.id, "phone")
        await show_preview(msg, state)
        return
    if t in ("❌ отмена", "отмена", "/cancel"):
        await state.clear()
        await msg.answer("Заполнение отменено. Черновик сохранён.", reply_markup=ReplyKeyboardRemove())
        await msg.answer("Напиши /start, чтобы начать сначала.", reply_markup=back_menu())
        return
    await msg.answer("Нажми «📱 Отправить контакт», чтобы поделиться номером, или «⏭ Пропустить».",
                     reply_markup=phone_request_kb())
    await msg.answer("Или выбери действие кнопкой ниже:", reply_markup=phone_inline_kb())


# --- служебные кнопки FSM ---
@router.callback_query(F.data.in_({"profile:skip", "pf:skip"}))
async def fsm_skip(cb: CallbackQuery, state: FSMContext):
    cur = await state.get_state()
    mapping = {ProfileFSM.bio: "bio", ProfileFSM.interests: "interests",
               ProfileFSM.photo: "photo", ProfileFSM.phone: "phone",
               ProfileFSM.city: None, ProfileFSM.name: None, ProfileFSM.age: None}
    # bio/interests/photo/phone можно пропустить
    if cur == ProfileFSM.bio:
        await state.update_data(bio=None)
        await db().save_draft(cb.from_user.id, await state.get_data())
        await db().log_funnel(cb.from_user.id, "bio")
        await ask_field(cb, state, "interests")
    elif cur == ProfileFSM.interests:
        await state.update_data(interests=None)
        await db().save_draft(cb.from_user.id, await state.get_data())
        await db().log_funnel(cb.from_user.id, "interests")
        await state.update_data(extra_idx=0)
        await ask_extra(cb, state)
    elif cur == ProfileFSM.extra:
        data = await state.get_data()
        idx = data.get("extra_idx", 0)
        if idx < len(EXTRA):
            await state.update_data(**{EXTRA[idx][0]: None, "extra_idx": idx + 1})
            await db().save_draft(cb.from_user.id, await state.get_data())
        await ask_extra(cb, state)
    elif cur == ProfileFSM.photo:
        await db().log_funnel(cb.from_user.id, "photo")
        await ask_field(cb, state, "phone")
    elif cur == ProfileFSM.phone:
        await db().log_funnel(cb.from_user.id, "phone")
        try:
            await cb.message.answer("Пропускаем номер.", reply_markup=ReplyKeyboardRemove())
        except Exception:
            pass
        await show_preview(cb.message, state)
        await cb.answer()
    else:
        await cb.answer("Этот шаг нельзя пропустить.", show_alert=True)


@router.callback_query(F.data.in_({"profile:back", "pf:back"}))
async def fsm_back(cb: CallbackQuery, state: FSMContext):
    cur = await state.get_state()
    if cur == ProfileFSM.extra:
        data = await state.get_data()
        idx = data.get("extra_idx", 0)
        if idx <= 1:
            await ask_field(cb, state, "interests")
        else:
            await state.update_data(extra_idx=idx - 1)
            await ask_extra(cb, state)
        return
    if cur == ProfileFSM.photo:
        await state.update_data(extra_idx=len(EXTRA) - 1)
        await ask_extra(cb, state)
        return
    seq = [ProfileFSM.name, ProfileFSM.age, ProfileFSM.gender, ProfileFSM.looking_for,
           ProfileFSM.city, ProfileFSM.bio, ProfileFSM.interests, ProfileFSM.photo, ProfileFSM.phone]
    if cur not in seq:
        await cb.answer()
        return
    i = seq.index(cur)
    if i == 0:
        await cb.answer("Это первый шаг.", show_alert=True)
        return
    prev = ORDER[i - 1]
    await ask_field(cb, state, prev)


@router.callback_query(F.data == "profile:cancel")
async def fsm_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    d = db()
    prof = await d.get_profile(cb.from_user.id)
    if prof and prof.get("profile_status") == "active":
        try:
            await cb.message.answer("Заполнение отменено.", reply_markup=back_menu())
        except Exception:
            pass
        await cb.answer()
        return
    try:
        await cb.message.answer("Без анкеты дальше нельзя. Начинаем сначала.")
    except Exception:
        pass
    await cb.answer()
    await begin_creation(cb.message, state)


@router.callback_query(F.data == "profile:publish")
async def cb_publish(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("profile_name") or not data.get("age"):
        await cb.answer("Заполни имя и возраст.", show_alert=True)
        return
    if (data.get("age") or 0) < 18:
        await cb.answer("Только 18+.", show_alert=True)
        return
    d = db()
    await d.save_draft(cb.from_user.id, data)
    await d.publish_profile(cb.from_user.id)
    await d.log_funnel(cb.from_user.id, "published")
    try:
        ph = await cb.bot.get_user_profile_photos(cb.from_user.id, limit=5)
        for p in ph.photos:
            await d.log_avatar(cb.from_user.id, p[-1].file_unique_id)
    except Exception:
        pass
    await state.clear()
    await cb.message.answer("🎉 Анкета опубликована!", reply_markup=back_menu())
    await cb.answer()


# --- одиночное редактирование ---
@router.callback_query(F.data.startswith("edit:"))
async def cb_edit_field(cb: CallbackQuery, state: FSMContext):
    field = cb.data.split(":", 1)[1]
    await state.update_data(edit_field=field)
    await state.set_state(ProfileFSM.edit_value)
    hints = {"profile_name": "Введи новое имя:", "age": "Введи новый возраст (18+):",
             "city": "Введи новый город:", "bio": "Введи новое описание:",
             "interests": "Введи новые интересы:", "phone": "Пришли контакт или «-» чтобы удалить номер.",
             "gender": "Выбери пол:", "looking_for": "Кого искать?",
             "photo": "Пришли новое фото.",
             "zodiac": "Новый знак зодиака («-» — убрать):", "height": "Новый рост («-» — убрать):",
             "education": "Новое образование («-» — убрать):", "job": "Новая работа («-» — убрать):",
             "languages": "Новые языки («-» — убрать):", "kids": "Дети («-» — убрать):",
             "smoking": "Курение («-» — убрать):", "alcohol": "Алкоголь («-» — убрать):",
             "goal": "Новая цель («-» — убрать):", "schedule": "Новый график («-» — убрать):"}
    kb = None
    if field == "gender":
        kb = gender_kb()
    elif field == "looking_for":
        kb = looking_kb()
    await cb.message.answer(hints.get(field, "Введи новое значение:"), reply_markup=kb or back_menu())
    await cb.answer()


@router.message(ProfileFSM.edit_value)
async def edit_value_msg(msg: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field")
    d = db()
    if field == "age":
        try:
            age = int((msg.text or "").strip())
        except ValueError:
            await msg.answer("Введи возраст числом.")
            return
        if age < 18:
            await msg.answer("Только 18+.")
            return
        await d.update_profile_fields(msg.from_user.id, age=age)
    elif field == "photo":
        if not msg.photo:
            await msg.answer("Пришли фотографию.")
            return
        pic = msg.photo[-1]
        await d.update_profile_fields(msg.from_user.id, photo_file_id=pic.file_id,
                                      photo_unique_id=pic.file_unique_id,
                                      photo_width=pic.width, photo_height=pic.height,
                                      photo_size=pic.file_size)
    elif field == "phone":
        if msg.contact:
            if msg.contact.user_id and msg.contact.user_id != msg.from_user.id:
                await msg.answer("Чужой контакт не принимается.")
                return
            await d.update_profile_fields(msg.from_user.id, phone_number=msg.contact.phone_number)
        elif (msg.text or "").strip() == "-":
            await d.update_profile_fields(msg.from_user.id, phone_number=None)
        else:
            await msg.answer("Пришли контакт кнопкой или «-» для удаления.")
            return
    elif field in ("profile_name", "bio", "interests", "zodiac", "height", "education",
                     "job", "languages", "kids", "smoking", "alcohol", "goal", "schedule"):
        v = (msg.text or "").strip()[:200] or None
        v = None if v == "-" else v
        await d.update_profile_fields(msg.from_user.id, **{field: v})
    elif field == "city":
        geo = await forward_city(msg.text or "")
        if geo and "error" not in geo:
            norm = valid_city(geo["city"]) or valid_city(msg.text or "")
            await d.update_profile_fields(msg.from_user.id, city=norm,
                                          latitude=geo["lat"], longitude=geo["lon"])
        else:
            norm = valid_city(msg.text or "")
            if not norm:
                if geo is None:
                    await msg.answer("Такой город не найден. Проверь написание.")
                else:
                    await msg.answer("Нет связи с проверкой городов и название не похоже на город.")
                return
            await d.update_profile_fields(msg.from_user.id, city=norm)
    else:
        await msg.answer("Для пола/предпочтений используй кнопки выше.")
        return
    await state.clear()
    await msg.answer("✅ Сохранено.", reply_markup=back_menu())


@router.callback_query(F.data == "profile:hide")
async def cb_hide(cb: CallbackQuery):
    await db().set_profile_status(cb.from_user.id, "hidden")
    await cb.message.answer("Анкета скрыта.", reply_markup=back_menu())
    await cb.answer()


@router.callback_query(F.data == "profile:unhide")
async def cb_unhide(cb: CallbackQuery):
    await db().set_profile_status(cb.from_user.id, "active")
    await cb.message.answer("Анкета снова видна.", reply_markup=back_menu())
    await cb.answer()


@router.callback_query(F.data == "profile:delete")
async def cb_delete(cb: CallbackQuery):
    await db().set_profile_status(cb.from_user.id, "deleted")
    await cb.message.answer("Анкета удалена.", reply_markup=back_menu())
    await cb.answer()
