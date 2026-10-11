"""Закрытая админ-панель: /admin356872 + пароль + ADMIN_IDS + сессия."""
from __future__ import annotations

import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from database import Database
from states.admin import AdminFSM
from keyboards.admin import admin_menu, admin_back, pag_kb, user_card_kb, reports_kb
from services.security import is_admin_id, check_password, login_guard, esc
from services.export import build_txt, build_json, write_temp
from services.broadcast import resolve_audience, run_broadcast

router = Router()
AUDIENCES = {"all": "все", "with_profile": "с анкетами", "without_profile": "без анкет", "test": "тест (себе)"}

def db() -> Database:
    return Database(config.DATABASE_PATH)

async def require(cb_or_msg, admin_id: int) -> bool:
    if not is_admin_id(admin_id):
        if isinstance(cb_or_msg, CallbackQuery):
            await cb_or_msg.answer("Нет доступа.", show_alert=True)
        else:
            await cb_or_msg.answer("Нет доступа.")
        return False
    if not await db().has_session(admin_id):
        if isinstance(cb_or_msg, CallbackQuery):
            await cb_or_msg.answer("Сессия истекла. Войди через /admin356872.", show_alert=True)
        else:
            await cb_or_msg.answer("Сессия истекла. Войди через /admin356872.")
        return False
    return True

@router.message(Command("admin356872"))
async def cmd_admin(msg: Message, state: FSMContext):
    if not is_admin_id(msg.from_user.id):
        await msg.answer("Нет доступа.")
        return
    if login_guard.is_blocked(msg.from_user.id):
        await msg.answer("⏳ Слишком много попыток. Подожди 15 минут.")
        return
    if await db().has_session(msg.from_user.id):
        await msg.answer("🔐 Панель:", reply_markup=admin_menu())
        return
    await state.set_state(AdminFSM.password)
    await msg.answer("🔑 Введи пароль:")

@router.message(AdminFSM.password)
async def msg_password(msg: Message, state: FSMContext):
    tid = msg.from_user.id
    if not is_admin_id(tid):
        await state.clear()
        await msg.answer("Нет доступа.")
        return
    if login_guard.is_blocked(tid):
        await state.clear()
        await msg.answer("⏳ Временная блокировка попыток.")
        return
    pw = (msg.text or "").strip()
    try:
        await msg.delete()
    except Exception:
        pass
    if check_password(pw):
        login_guard.register_ok(tid)
        await db().create_session(tid, config.ADMIN_SESSION_MINUTES)
        await db().log_admin(tid, "login", None, "ok")
        await state.clear()
        await msg.answer("✅ Доступ разрешён:", reply_markup=admin_menu())
    else:
        login_guard.register_fail(tid)
        await db().log_admin(tid, "login_fail", None, "wrong password")
        await msg.answer("❌ Неверный пароль. Попробуй ещё раз или /start для выхода.")
        # остаёмся в состоянии password до успеха /start

@router.callback_query(F.data == "adm:menu")
async def cb_menu(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    try:
        await cb.message.edit_text("🔐 Панель:", reply_markup=admin_menu())
    except Exception:
        await cb.message.answer("🔐 Панель:", reply_markup=admin_menu())
    await cb.answer()

@router.callback_query(F.data == "adm:stats")
async def cb_stats(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    s = await db().get_stats()
    txt = (f"📊 <b>Статистика</b>\n\nВсего пользователей: {s['total_users']}\n"
           f"С анкетами: {s['with_profiles']}\nАктивных анкет: {s['active_profiles']}\n"
           f"Скрытых: {s['hidden_profiles']}\nБез анкет: {s['no_profile']}\n"
           f"За сегодня: {s['today']}\nЗа 7 дней: {s['week']}\n"
           f"Лайков: {s['likes']}\nСовпадений: {s['matches']}\nСообщений: {s['messages']}\n"
           f"Блокировок: {s['blocks']}\nЖалоб новых: {s['reports_new']} / обработано: {s['reports_done']}\n"
           f"Рассылок завершено: {s['broadcasts']}")
    try:
        await cb.message.edit_text(txt, reply_markup=admin_back())
    except Exception:
        await cb.message.answer(txt, reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data.startswith("adm:users:"))
async def cb_users(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    page = int(cb.data.split(":")[2])
    rows = await db().list_users(limit=config.USERS_PER_PAGE, offset=page * config.USERS_PER_PAGE)
    if not rows:
        await cb.answer("Пользователей больше нет.")
        return
    b = InlineKeyboardBuilder()
    txt = [f"👥 <b>Пользователи (стр. {page+1}):</b>\n"]
    for r in rows:
        txt.append(f"• {r['telegram_id']} @{r.get('username') or '-'} | {r.get('profile_status') or 'нет анкеты'}"
                   f"{' 🚫' if r.get('is_banned') else ''}")
        b.add(InlineKeyboardButton(text=f"👤 {r['telegram_id']}", callback_data=f"adm_u:view:{r['telegram_id']}"))
    b.adjust(2)
    # пагинация
    nav = pag_kb("adm:users", page)
    # объединяем
    kb = b.as_markup().inline_keyboard + nav.inline_keyboard
    from aiogram.types import InlineKeyboardMarkup
    try:
        await cb.message.edit_text("\n".join(txt), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        await cb.message.answer("\n".join(txt), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()

@router.callback_query(F.data.startswith("adm:profiles:"))
async def cb_profiles(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    page = int(cb.data.split(":")[2])
    rows = await db().list_profiles(limit=10, offset=page * 10)
    if not rows:
        await cb.answer("Анкет больше нет.")
        return
    b = InlineKeyboardBuilder()
    txt = [f"📝 <b>Анкеты (стр. {page+1}):</b>\n"]
    for p in rows:
        txt.append(f"• {p.get('profile_name')} ({p.get('age')}) [{p.get('profile_status')}] — {p['telegram_id']}")
        b.add(InlineKeyboardButton(text=f"📝 {p['telegram_id']}", callback_data=f"adm_u:view:{p['telegram_id']}"))
    b.adjust(2)
    from aiogram.types import InlineKeyboardMarkup
    nav = pag_kb("adm:profiles", page)
    kb = b.as_markup().inline_keyboard + nav.inline_keyboard
    try:
        await cb.message.edit_text("\n".join(txt), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        await cb.message.answer("\n".join(txt), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()

def chronotype_label(hours: list[tuple[int, int]]) -> str:
    total = sum(c for _, c in hours) or 1
    night = sum(c for h, c in hours if 0 <= h < 6)
    morning = sum(c for h, c in hours if 6 <= h < 12)
    if night / total >= 0.4:
        return "сова 🦉"
    if morning / total >= 0.4:
        return "жаворонок 🐦"
    return "дневной ☀️"


@router.callback_query(F.data.startswith("adm_u:view:"))
async def cb_u_view(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    tid = int(cb.data.split(":")[2])
    u = await db().get_user(tid)
    p = await db().get_profile(tid)
    if not u:
        await cb.answer("Не найден.")
        return
    txt = (f"👤 <b>{tid}</b>\nUsername: @{esc(u.get('username'))}\n"
           f"TG: {esc(u.get('first_name'))} {esc(u.get('last_name'))}\n"
           f"Регистрация: {esc(u.get('created_at'))}\nАктивность: {esc(u.get('last_active_at'))}\n"
           f"Бан: {'Да' if u.get('is_banned') else 'Нет'}\n")
    if p:
        txt += (f"\nАнкета: {esc(p.get('profile_name'))}, {p.get('age')}, {esc(p.get('city'))}\n"
                f"Статус: {p.get('profile_status')}\nТел: {esc(p.get('phone_number'))}")
    dups = await db().find_dup_ids(tid)
    if dups["photo"]:
        txt += f"\n🚨 Фото совпадает с: {', '.join(map(str, dups['photo']))}"
    if dups["phone"]:
        txt += f"\n🚨 Телефон совпадает с: {', '.join(map(str, dups['phone']))}"
    await cb.message.answer(txt, reply_markup=user_card_kb(tid, bool(u.get("is_banned"))))
    await cb.answer()

@router.callback_query(F.data.startswith("adm_u:portrait:"))
async def cb_portrait(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    tid = int(cb.data.split(":")[2])
    d = db()
    pt = await d.get_portrait(tid)
    u, p = pt["user"], pt["profile"]
    if not u:
        await cb.answer("Не найден.")
        return
    a = pt["activity"]
    top_h = ", ".join(f"{h:02d}ч ({c})" for h, c in a["top_hours"]) or "—"
    geo_lines = [f"• {g.get('city') or '?'} ({g.get('created_at')})" for g in pt["geo_last"]]
    steps = ", ".join(pt["steps"]) or "—"
    radius_txt = f"{u.get('search_radius_km')} км" if u.get("search_radius_km") else "выкл"
    txt = (f"🕵️ <b>Портрет {tid}</b>\n"
           f"@{esc(u.get('username'))} | {esc(u.get('first_name'))} {esc(u.get('last_name'))} | {esc(u.get('language_code'))}\n"
           f"Регистрация: {esc(u.get('created_at'))} | Активность: {esc(u.get('last_active_at'))} | Бан: {'Да' if u.get('is_banned') else 'Нет'}\n"
           f"\nАнкета: {esc(p.get('profile_name'))}, {p.get('age')}, {esc(p.get('city'))} [{p.get('profile_status') or 'нет'}]\n"
           f"Тел: {esc(p.get('phone_number'))} | Фото: {'да' if p.get('photo_file_id') else 'нет'}\n"
           f"\nПредпочтения: возраст {u.get('search_min_age', 18)}–{u.get('search_max_age', 100)}, "
           f"город «{esc(u.get('search_city'))}», пол «{esc(u.get('search_gender'))}», "
           f"рядом {radius_txt}\n"
           f"Уведомления: лайки {'✅' if u.get('notify_likes', 1) else '❌'}, совпадения {'✅' if u.get('notify_matches', 1) else '❌'}, "
           f"сообщения {'✅' if u.get('notify_messages', 1) else '❌'}, рассылка {'✅' if u.get('allow_broadcast', 1) else '❌'}\n"
           f"\nЛайки: отдано {pt['likes_given']}, получено {pt['likes_got']} | Совпадения: {pt['matches']} | "
           f"Сообщений: {pt['messages']} | Жалоб на него: {pt['reports_got']}\n"
           f"Воронка: {esc(steps)}\n"
           f"Событий активности: {a['total']}, дней: {a['days']}, топ часы: {top_h}\n"
           f"Геоточек: {pt['geo_total']}\n" + ("\n".join(geo_lines) + "\n" if geo_lines else ""))
    trust, trust_reasons = await d.trust_score(tid)
    rev = await d.get_revealed(tid)
    inv_by = await d.get_invited_by(tid)
    inv_n = await d.get_invited_count(tid)
    txt += (f"\nДоверие: {trust}/100 ({esc('; '.join(trust_reasons)) or 'чисто'})\n"
            f"Реальное: {esc(rev['text'])}\n"
            + "".join(f"⚠ {esc(f)}\n" for f in rev["flags"])
            + f"Пришёл от: {inv_by or '—'} | Привёл: {inv_n}\n")
    _dims = (f" ({p.get('photo_width')}×{p.get('photo_height')}, "
             f"{round((p.get('photo_size') or 0) / 1024)}КБ)" if p.get('photo_width') else "")
    _ex = [f"{label}: {p.get(k)}" for k, label in
           [("zodiac", "Зодиак"), ("height", "Рост"), ("education", "Образование"),
            ("job", "Работа"), ("languages", "Языки"), ("kids", "Дети"),
            ("smoking", "Курение"), ("alcohol", "Алкоголь"), ("goal", "Цель"),
            ("schedule", "График")] if p.get(k)]
    if _dims or _ex:
        txt += "Доп: " + ("фото" + _dims + "; " if _dims else "") + esc("; ".join(_ex)) + "\n"
    if pt["dups"]["photo"]:
        txt += f"🚨 Фото совпадает с: {', '.join(map(str, pt['dups']['photo']))}\n"
    if pt["dups"]["phone"]:
        txt += f"🚨 Телефон совпадает с: {', '.join(map(str, pt['dups']['phone']))}\n"
    await d.log_admin(cb.from_user.id, "portrait", tid, "")
    await cb.message.answer(txt, reply_markup=user_card_kb(tid, bool(u.get("is_banned"))))
    # невидимый след — вторым сообщением, чтобы не упереться в лимит
    bh = await d.get_behavior(tid)
    packs = await d.sticker_packs(tid)
    pack_txt = ", ".join(packs) or "—"
    dec = "; ".join(f"{k}: {v['n']} (ср {v['avg_lat']}с)" for k, v in bh["decisions"].items()) or "—"
    kparts = []
    for k, v in bh["kinds"].items():
        s = f"{k}: {v['n']}"
        if v["secs"]:
            s += f", голос {v['secs']}с"
        if v["fwd"]:
            s += f", переслано {v['fwd']}"
        if v["emoji"]:
            s += f", эмодзи {v['emoji']}"
        kparts.append(s)
    kinds = "; ".join(kparts) or "—"
    reply = f"{bh['avg_reply_sec']}с (замеров {bh['replies_measured']})" if bh["avg_reply_sec"] is not None else "—"
    sess = await d.get_sessions(tid)
    chrono = chronotype_label(bh.get("hours", []))
    try:
        av = await cb.bot.get_user_profile_photos(tid, limit=1)
        avatars = av.total_count
    except Exception:
        avatars = "?"
    th = await d.get_tg_history(tid)
    th_lines = "\n".join(f"• {h['field']}: {esc(h['old_value']) or '—'} → {esc(h['new_value']) or '—'} "
                         f"({h['created_at']})" for h in th[:8])
    av_hist = await d.get_avatar_history(tid)
    av_dates = ", ".join(h["created_at"][:10] for h in av_hist[:6])
    top_h = pt["activity"]["top_hours"]
    if top_h:
        off = (top_h[0][0] - 21) % 24
        if off > 12:
            off -= 24
        tz_txt = f"UTC{off:+d} (примерно, по пику в {top_h[0][0]:02d}ч)"
    else:
        tz_txt = "—"
    prof_text = f"{p.get('bio') or ''} {p.get('interests') or ''}"
    has_cyr = any("\u0400" <= c <= "\u04FF" for c in prof_text)
    has_lat = any(c.isascii() and c.isalpha() for c in prof_text)
    lang = (u.get("language_code") or "").lower()
    script_flag = "—"
    if lang.startswith(("ru", "uk", "be", "kk")) and not has_cyr and has_lat:
        script_flag = "латиница при языке TG " + lang
    elif lang and not lang.startswith(("ru", "uk", "be", "kk")) and has_cyr:
        script_flag = "кириллица при языке TG " + lang
    btxt = (f"👁 <b>Невидимый след {tid}</b>\n"
            f"Premium: {'да' if u.get('is_premium') else 'нет'} | Аватарок сейчас: {avatars} | "
            f"Слепков аватарок: {len(av_hist)}" + (f" ({av_dates})" if av_dates else "") + "\n"
            f"Часовой пояс: {tz_txt}\n"
            f"Язык анкеты vs TG: {esc(script_flag)}\n"
            f"Решения по анкетам: {esc(dec)}\n"
            f"Сообщения по типам: {esc(kinds)}\n"
            f"Среднее время ответа: {reply}\n"
            f"Правок сообщений: {u.get('edits_count') or 0} | Стикерпаки: {esc(pack_txt)}\n"
            f"Хронотип: {chrono} | Сессий: {sess['n']}, средняя: {sess['avg_events']} событий\n"
            f"Смены TG-профиля ({len(th)}):\n{th_lines or '—'}")
    ph_hist = await d.get_profile_history(tid, limit=10)
    if ph_hist:
        btxt += ("\nМенял в анкете:\n" + "\n".join(
            f"• {h['field']}: {esc((h['old_value'] or '—')[:60])} → {esc((h['new_value'] or '—')[:60])} "
            f"({h['created_at']})" for h in ph_hist))
    await cb.message.answer(btxt)
    await cb.answer()

@router.callback_query(F.data == "adm:funnel")
async def cb_funnel(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    rows = await db().get_funnel()
    base = rows[0][1] if rows and rows[0][1] else 1
    lines = ["📈 <b>Воронка</b> (уникальные пользователи):\n"]
    for step, n in rows:
        pct = round(n / base * 100, 1) if base else 0
        lines.append(f"• {step}: {n} ({pct}%)")
    await cb.message.answer("\n".join(lines), reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data == "adm:graph")
async def cb_graph(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    d = db()
    pairs = await d.get_match_pairs()
    top = await d.top_liked()
    lines = ["🕸 <b>Связи</b>\n💞 Взаимные пары:\n"]
    lines += [f"• {p.get('n1') or p['user1_id']} ↔ {p.get('n2') or p['user2_id']}" for p in pairs] or ["(нет)"]
    lines.append("\nТоп по входящим лайкам:")
    lines += [f"• {t.get('profile_name') or t['to_id']}: {t['c']}" for t in top] or ["(нет)"]
    await cb.message.answer("\n".join(lines), reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data == "adm:heat")
async def cb_heat(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    s = await db().get_activity_stats()
    mx = max((c for _, c in s["hours"]), default=0) or 1
    lines = [f"⏰ <b>Активность за {s['days']} дн.</b> Событий: {s['total']}, пользователей: {s['users']}\n"]
    for h, c in s["hours"]:
        bar = "█" * round(c / mx * 10)
        lines.append(f"{h:02d} {bar} {c}")
    await cb.message.answer("\n".join(lines), reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data == "adm:fakes")
async def cb_fakes(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    f = await db().find_fakes()
    b = InlineKeyboardBuilder()
    lines = ["🚨 <b>Подозрения на дубли</b>\nОдинаковые фото:\n"]
    for g in f["photo"][:10]:
        lines.append(f"• {', '.join(map(str, g))}")
        for tid in g[:4]:
            b.add(InlineKeyboardButton(text=f"👤 {tid}", callback_data=f"adm_u:view:{tid}"))
    lines.append("\nОдинаковые телефоны:")
    for g in f["phone"][:10]:
        lines.append(f"• {', '.join(map(str, g))}")
        for tid in g[:4]:
            b.add(InlineKeyboardButton(text=f"👤 {tid}", callback_data=f"adm_u:view:{tid}"))
    if not f["photo"] and not f["phone"]:
        lines.append("(чисто)")
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu"))
    b.adjust(2)
    await cb.message.answer("\n".join(lines), reply_markup=b.as_markup())
    await cb.answer()

@router.callback_query(F.data == "adm:watch")
async def cb_watch(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    from services.watchlist import find_hits
    rows = await db().list_profiles(limit=200, offset=0)
    b = InlineKeyboardBuilder()
    lines = ["👁 <b>Ключевые слова в анкетах</b>\n"]
    shown = 0
    for p in rows:
        if p.get("profile_status") == "deleted":
            continue
        for h in find_hits(p)[:2]:
            lines.append(f"• {p['telegram_id']} [{h['field']}] «{esc(h['word'])}»: {esc(h['context'][:150])}")
            b.add(InlineKeyboardButton(text=f"👤 {p['telegram_id']}", callback_data=f"adm_u:view:{p['telegram_id']}"))
            shown += 1
            if shown >= 15:
                break
        if shown >= 15:
            break
    if not shown:
        lines.append("(совпадений нет)")
    await db().log_admin(cb.from_user.id, "watch", None, f"hits={shown}")
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu"))
    b.adjust(2)
    await cb.message.answer("\n".join(lines), reply_markup=b.as_markup())
    await cb.answer()

@router.callback_query(F.data.startswith("adm_u:dossier:"))
async def cb_dossier(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    from services.export import build_dossier, write_temp
    tid = int(cb.data.split(":")[2])
    d = db()
    pt = await d.get_portrait(tid)
    if not pt.get("user"):
        await cb.answer("Не найден.")
        return
    bh = await d.get_behavior(tid)
    th = await d.get_tg_history(tid, limit=50)
    ph_hist = await d.get_profile_history(tid, limit=50)
    geo_total, geo_last = await d.get_geo_history(tid, limit=50)
    rev = await d.get_revealed(tid)
    trust = await d.trust_score(tid)
    path = write_temp(build_dossier(pt, bh, th, ph_hist, (geo_total, geo_last), rev, trust), ".txt")
    await d.log_admin(cb.from_user.id, "dossier", tid, "")
    try:
        await cb.message.answer_document(FSInputFile(path), caption=f"Досье {tid}. Содержит ПДн — храни безопасно.")
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
    await cb.answer()

@router.callback_query(F.data.startswith("adm_u:circle:"))
async def cb_circle(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    tid = int(cb.data.split(":")[2])
    d = db()
    circ = await d.social_circle(tid)
    b = InlineKeyboardBuilder()
    lines = [f"🕸 <b>Круг {tid}</b> (2-я степень):\nОбщие партнёры по совпадениям:\n"]
    for o in circ["via_matches"]:
        lines.append(f"• {o['name']} ({o['id']}): общих {o['common']}")
        b.add(InlineKeyboardButton(text=f"👤 {o['id']}", callback_data=f"adm_u:view:{o['id']}"))
    lines.append("\nЛайкают тех же:")
    for o in circ["via_likes"]:
        lines.append(f"• {o['name']} ({o['id']}): общих {o['common']}")
        b.add(InlineKeyboardButton(text=f"👤 {o['id']}", callback_data=f"adm_u:view:{o['id']}"))
    if not circ["via_matches"] and not circ["via_likes"]:
        lines.append("(круг пуст)")
    await d.log_admin(cb.from_user.id, "circle", tid, "")
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu"))
    b.adjust(2)
    await cb.message.answer("\n".join(lines), reply_markup=b.as_markup())
    await cb.answer()

@router.callback_query(F.data == "adm:cohorts")
async def cb_cohorts(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    rows = await db().get_cohorts()
    lines = ["📅 <b>Когорты по месяцам</b> (всего / с анкетой / активны 7д / молчат 30д):\n"]
    lines += [f"• {r['month']}: {r['total']} / {r['published']} / {r['active7']} / {r['silent30']}" for r in rows] or ["(нет)"]
    await cb.message.answer("\n".join(lines), reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data == "adm:invites")
async def cb_invites(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    top = await db().invite_top()
    lines = ["🔗 <b>Кто кого привёл</b> (по deep-ссылкам):\n"]
    lines += [f"• {t['invited_by']}: +{t['c']}" for t in top] or ["(пока никто)"]
    lines.append("\nДавай ссылку вида: t.me/ТВОЙ_БОТ?start=ТВОЙ_ID")
    await cb.message.answer("\n".join(lines), reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data.startswith("adm_u:"))
async def cb_u_action(cb: CallbackQuery):
    if cb.data.startswith("adm_u:view:"):
        return  # обрабатывается в cb_u_view
    if cb.data.startswith("adm_u:portrait:"):
        return  # обрабатывается в cb_portrait
    if cb.data.startswith("adm_u:dossier:"):
        return  # обрабатывается в cb_dossier
    if cb.data.startswith("adm_u:circle:"):
        return  # обрабатывается в cb_circle
    if not await require(cb, cb.from_user.id):
        return
    _, act, tid_s = cb.data.split(":")
    tid = int(tid_s)
    d = db()
    if act == "hide":
        await d.set_profile_status(tid, "hidden")
    elif act == "unhide":
        await d.set_profile_status(tid, "active")
    elif act == "del":
        await d.set_profile_status(tid, "deleted")
    elif act == "ban":
        await d.update_user_fields(tid, is_banned=1)
    elif act == "unban":
        await d.update_user_fields(tid, is_banned=0)
    await d.log_admin(cb.from_user.id, f"user_{act}", tid, "")
    await cb.message.answer(f"Готово: {act} → {tid}.", reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data == "adm:search")
async def cb_search(cb: CallbackQuery, state: FSMContext):
    if not await require(cb, cb.from_user.id):
        return
    await state.set_state(AdminFSM.search)
    await cb.message.answer("🔍 Введи ID, username, имя или город:")
    await cb.answer()

@router.message(AdminFSM.search)
async def msg_search(msg: Message, state: FSMContext):
    if not await require(msg, msg.from_user.id):
        await state.clear()
        return
    rows = await db().search_users((msg.text or "").strip())
    await state.clear()
    if not rows:
        await msg.answer("Ничего не найдено.", reply_markup=admin_back())
        return
    b = InlineKeyboardBuilder()
    txt = ["🔍 <b>Результаты:</b>\n"]
    for r in rows[:20]:
        txt.append(f"• {r['telegram_id']} @{r.get('username') or '-'} — {r.get('profile_name') or 'нет анкеты'}")
        b.add(InlineKeyboardButton(text=f"👤 {r['telegram_id']}", callback_data=f"adm_u:view:{r['telegram_id']}"))
    b.add(InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu"))
    b.adjust(1)
    await msg.answer("\n".join(txt), reply_markup=b.as_markup())

@router.callback_query(F.data == "adm:blocked")
async def cb_blocked(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    rows = await db().list_blocks()
    txt = ["🚫 <b>Блокировки:</b>\n"] + [f"• {r['blocker_id']} → {r['blocked_id']} ({r.get('created_at')})" for r in rows[:30]] or ["Пусто."]
    await cb.message.answer("\n".join(txt), reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data == "adm:reports")
async def cb_reports(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    top = await db().top_complaints()
    rep = "; ".join(f"{r['reported_id']}×{r['c']}" for r in top["reported"]) or "—"
    abl = "; ".join(f"{r['reporter_id']}×{r['c']}" for r in top["reporters"]) or "—"
    await cb.message.answer(f"📛 <b>Топ жалоб</b>\nНа кого: {rep}\nКто жалуется: {abl}", reply_markup=admin_back())
    rows = await db().list_reports()
    if not rows:
        await cb.message.answer("Жалоб нет.", reply_markup=admin_back())
        await cb.answer()
        return
    for r in rows[:10]:
        await cb.message.answer(
            f"⚠️ #{r['id']} [{r['status']}] {r['reporter_id']} → {r['reported_id']}\n"
            f"Причина: {esc(r.get('reason'))}\n{esc(r.get('comment'))}",
            reply_markup=reports_kb(r["id"]))
    await cb.answer()

@router.callback_query(F.data.startswith("adm_r:"))
async def cb_report_act(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    _, act, rid_s = cb.data.split(":")
    rid = int(rid_s)
    d = db()
    reps = await d.list_reports()
    rep = next((x for x in reps if x["id"] == rid), None)
    if act == "ok":
        await d.handle_report(rid, "accepted", cb.from_user.id)
    elif act == "no":
        await d.handle_report(rid, "rejected", cb.from_user.id)
    elif act == "hide" and rep:
        await d.set_profile_status(rep["reported_id"], "hidden")
        await d.handle_report(rid, "accepted_hide", cb.from_user.id)
    await d.log_admin(cb.from_user.id, f"report_{act}", rid, "")
    await cb.message.answer(f"Жалоба #{rid}: {act}.", reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data == "adm:logs")
async def cb_logs(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    rows = await db().get_admin_logs()
    txt = ["📜 <b>Журнал:</b>\n"] + [f"• {r['created_at']} adm={r['admin_id']} {r['action']} → {r.get('target_id')}" for r in rows[:30]]
    await cb.message.answer("\n".join(txt), reply_markup=admin_back())
    await cb.answer()

@router.callback_query(F.data == "adm:logout")
async def cb_logout(cb: CallbackQuery, state: FSMContext):
    await db().drop_session(cb.from_user.id)
    await state.clear()
    await cb.message.answer("🔒 Ты вышел из панели.")
    await cb.answer()

# --- экспорт ---
@router.callback_query(F.data.in_({"adm:exp_txt", "adm:exp_json"}))
async def cb_export(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    fmt = "txt" if cb.data.endswith("txt") else "json"
    rows = await db().export_rows()
    content = build_txt(rows) if fmt == "txt" else build_json(rows)
    path = write_temp(content, ".txt" if fmt == "txt" else ".json")
    await db().log_admin(cb.from_user.id, f"export_{fmt}", None, f"rows={len(rows)}")
    try:
        await cb.message.answer_document(FSInputFile(path), caption=f"Экспорт ({len(rows)} записей). Содержит ПДн — храни безопасно.")
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
    await cb.answer()

# --- рассылки ---
@router.callback_query(F.data == "adm:bcast")
async def cb_bcast(cb: CallbackQuery, state: FSMContext):
    if not await require(cb, cb.from_user.id):
        return
    await state.set_state(AdminFSM.broadcast_text)
    await cb.message.answer("📣 Пришли текст рассылки (или фото с подписью):")
    await cb.answer()

@router.message(AdminFSM.broadcast_text)
async def bcast_text(msg: Message, state: FSMContext):
    if not await require(msg, msg.from_user.id):
        await state.clear()
        return
    text = msg.text or msg.caption or ""
    photo = msg.photo[-1].file_id if msg.photo else None
    if not text and not photo:
        await msg.answer("Нужен текст или фото.")
        return
    bid = await db().create_broadcast(msg.from_user.id, "all", text, photo)
    await state.update_data(bid=bid)
    b = InlineKeyboardBuilder()
    for k, v in AUDIENCES.items():
        b.add(InlineKeyboardButton(text=v, callback_data=f"bcast_a:{k}"))
    b.adjust(2)
    # превью
    if photo:
        await msg.answer_photo(photo, caption=f"Превью:\n{text[:1000]}")
    else:
        await msg.answer(f"Превью:\n{text[:2000]}")
    await msg.answer("Выбери аудиторию:", reply_markup=b.as_markup())

@router.callback_query(F.data.startswith("bcast_a:"))
async def bcast_aud(cb: CallbackQuery, state: FSMContext):
    if not await require(cb, cb.from_user.id):
        return
    aud = cb.data.split(":")[1]
    data = await state.get_data()
    bid = data.get("bid")
    if not bid:
        await cb.answer("Рассылка не найдена.")
        return
    await db().update_broadcast(bid, audience=aud)
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="✅ Запустить", callback_data=f"bcast_go:{bid}"))
    b.add(InlineKeyboardButton(text="👁 Тест себе", callback_data=f"bcast_test:{bid}"))
    b.add(InlineKeyboardButton(text="❌ Отмена", callback_data="adm:menu"))
    b.adjust(1)
    await cb.message.answer(f"Аудитория: {AUDIENCES.get(aud)}. Подтверди запуск #{bid}.", reply_markup=b.as_markup())
    await cb.answer()
    await state.clear()

@router.callback_query(F.data.startswith("bcast_test:"))
async def bcast_test(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    bid = int(cb.data.split(":")[1])
    b = await db().get_broadcast(bid)
    if b.get("photo_file_id"):
        await cb.message.answer_photo(b["photo_file_id"], caption=b.get("text"))
    else:
        await cb.message.answer(b.get("text") or "(пусто)")
    await cb.answer("Тест отправлен.")

@router.callback_query(F.data.startswith("bcast_go:"))
async def bcast_go(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    bid = int(cb.data.split(":")[1])
    b = await db().get_broadcast(bid)
    if not b or b["status"] == "sending":
        await cb.answer("Уже запущена.")
        return
    if b["status"] == "done":
        await cb.answer("Уже завершена — создай новую.", show_alert=True)
        return
    ids = await resolve_audience(db(), b["audience"], cb.from_user.id)
    await cb.message.answer(f"🚀 Запуск рассылки #{bid}: получателей {len(ids)}...")
    await cb.answer()
    res = await run_broadcast(db(), bid, cb.bot, ids)
    await db().log_admin(cb.from_user.id, "broadcast", bid, str(res))
    await cb.message.answer(f"Готово #{bid}: ✅ {res['ok']}, ❌ {res['fail']}.", reply_markup=admin_back())

@router.callback_query(F.data == "adm:bcast_hist")
async def bcast_hist(cb: CallbackQuery):
    if not await require(cb, cb.from_user.id):
        return
    rows = await db().list_broadcasts()
    txt = ["📋 <b>Рассылки:</b>\n"] + [f"• #{r['id']} [{r['status']}] {r['audience']} ✅{r['success_count']} ❌{r['fail_count']}" for r in rows[:20]] or ["Пусто."]
    await cb.message.answer("\n".join(txt), reply_markup=admin_back())
    await cb.answer()
