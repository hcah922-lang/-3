"""Просмотр анкет, блокировки, жалобы."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import config
from database import Database, now_ts
from keyboards.discovery import card_kb, report_reasons_kb
from keyboards.main import back_menu
from services.security import profile_text, esc
from services.messaging import can_chat
from services.moderation import file_report
from services.geo import haversine_km

router = Router()

# время показа карточки (viewer, target) -> timestamp; для замера раздумий
_shown: dict[tuple[int, int], float] = {}

def db() -> Database:
    return Database(config.DATABASE_PATH)


async def find_card(d: Database, viewer_id: int) -> dict | None:
    """Обычная лента или фильтр «рядом», если задан радиус и есть координаты."""
    me = await d.get_profile(viewer_id)
    u = await d.get_user(viewer_id)
    radius = (u or {}).get("search_radius_km")
    lat = (me or {}).get("latitude")
    lon = (me or {}).get("longitude")
    if radius and lat is not None and lon is not None:
        for batch in range(6):
            feed = await d.get_feed(viewer_id, limit=20, offset=batch * 20)
            if not feed:
                return None
            for p in feed:
                if p.get("latitude") is None or p.get("longitude") is None:
                    continue
                if haversine_km(lat, lon, p["latitude"], p["longitude"]) <= radius:
                    p["_dist"] = round(haversine_km(lat, lon, p["latitude"], p["longitude"]), 1)
                    return p
        return None
    feed = await d.get_feed(viewer_id, limit=1, offset=0)
    return feed[0] if feed else None


async def show_one(cb: CallbackQuery, offset: int = 0):
    d = db()
    me = await d.get_profile(cb.from_user.id)
    if not me or me.get("profile_status") != "active":
        await cb.answer("Сначала создай и опубликуй анкету.", show_alert=True)
        return
    u = await d.get_user(cb.from_user.id) or {}
    radius = u.get("search_radius_km")
    if radius and (me.get("latitude") is None or me.get("longitude") is None):
        await cb.message.answer("📍 Ты включил поиск рядом, но геолокация не задана. "
                                "Обнови её в настройках или при создании анкеты.",
                                reply_markup=back_menu())
        await cb.answer()
        return
    p = await find_card(d, cb.from_user.id)
    if not p:
        txt = ("Рядом никого не нашлось. Расширь радиус в настройках."
               if radius else "Анкеты закончились. Попробуй изменить фильтры в настройках.")
        try:
            await cb.message.edit_text(txt, reply_markup=back_menu())
        except Exception:
            await cb.message.answer(txt, reply_markup=back_menu())
        await cb.answer()
        return
    _shown[(cb.from_user.id, p["telegram_id"])] = now_ts()
    ok, _ = await can_chat(d, cb.from_user.id, p["telegram_id"])
    txt = profile_text(p)
    if p.get("_dist") is not None:
        txt += f"\n\n📍 ≈ {p['_dist']} км от тебя"
    kb = card_kb(p["telegram_id"], can_write=ok)
    try:
        if p.get("photo_file_id"):
            await cb.message.answer_photo(p["photo_file_id"], caption=txt, reply_markup=kb)
            try:
                await cb.message.delete()
            except Exception:
                pass
        else:
            await cb.message.edit_text(txt, reply_markup=kb)
    except Exception:
        try:
            if p.get("photo_file_id"):
                await cb.message.answer_photo(p["photo_file_id"], caption=txt, reply_markup=kb)
            else:
                await cb.message.answer(txt, reply_markup=kb)
        except Exception as e:
            await cb.message.answer(f"Не удалось показать фото: {esc(str(e))}. Попробуй позже.",
                                    reply_markup=back_menu())
    await cb.answer()


@router.callback_query(F.data == "menu:browse")
async def cb_browse(cb: CallbackQuery):
    await show_one(cb, 0)


@router.callback_query(F.data.startswith("skip:"))
async def cb_skip(cb: CallbackQuery):
    try:
        tid = int(cb.data.split(":")[1])
        d = db()
        await d.mark_viewed(cb.from_user.id, tid)
        await d.update_view_decision(cb.from_user.id, tid, "skip",
                                     _shown.pop((cb.from_user.id, tid), None))
    except Exception:
        pass
    await show_one(cb, 0)


@router.callback_query(F.data.startswith("like:"))
async def cb_like(cb: CallbackQuery):
    from services.matching import process_like
    d = db()
    try:
        tid = int(cb.data.split(":")[1])
    except ValueError:
        await cb.answer("Некорректная анкета.")
        return
    res = await process_like(d, cb.from_user.id, tid)
    if res.get("blocked"):
        await cb.answer("Недоступно (блокировка).", show_alert=True)
        return
    await d.log_funnel(cb.from_user.id, "like")
    if res.get("match"):
        await d.log_funnel(cb.from_user.id, "match")
        await d.log_funnel(tid, "match")
        # уведомляем обе стороны если включены уведомления
        other = await d.get_user(tid)
        me_u = await d.get_user(cb.from_user.id)
        try:
            if other and other.get("notify_matches", 1):
                await cb.bot.send_message(tid, "💞 У тебя новое совпадение! Открой «Мои совпадения».")
        except Exception:
            pass
        await cb.message.answer("💞 Взаимный лайк! Это совпадение! Смотри «Мои совпадения».")
    else:
        await cb.message.answer("❤️ Лайк отправлен.")
    try:
        await d.mark_viewed(cb.from_user.id, tid)
        await d.update_view_decision(cb.from_user.id, tid, "like",
                                     _shown.pop((cb.from_user.id, tid), None))
    except Exception:
        pass
    await cb.answer()
    await show_one(cb, 0)


@router.callback_query(F.data.startswith("block:"))
async def cb_block(cb: CallbackQuery):
    d = db()
    tid = int(cb.data.split(":")[1])
    await d.add_block(cb.from_user.id, tid, "user block")
    await d.mark_viewed(cb.from_user.id, tid)
    await cb.message.answer("🚫 Пользователь заблокирован.")
    await cb.answer()
    await show_one(cb, 0)


@router.callback_query(F.data.startswith("report:"))
async def cb_report(cb: CallbackQuery):
    tid = cb.data.split(":")[1]
    try:
        await cb.message.edit_text("Выбери причину жалобы:",
                                   reply_markup=report_reasons_kb(int(tid)))
    except Exception:
        await cb.message.answer("Выбери причину жалобы:", reply_markup=report_reasons_kb(int(tid)))
    await cb.answer()


@router.callback_query(F.data.startswith("report_go:"))
async def cb_report_go(cb: CallbackQuery):
    _, _, tid, reason = cb.data.split(":", 3)
    rid = await file_report(db(), cb.from_user.id, int(tid), reason)
    await cb.message.answer(f"⚠️ Жалоба #{rid} отправлена.", reply_markup=back_menu())
    await cb.answer()
