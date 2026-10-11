from __future__ import annotations
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import config
from database import Database
from keyboards.main import back_menu

router = Router()

@router.callback_query(F.data == "menu:matches")
async def cb_matches(cb: CallbackQuery):
    d = Database(config.DATABASE_PATH)
    me = await d.get_profile(cb.from_user.id)
    if not me or me.get("profile_status") != "active":
        await cb.message.answer("⚠️ Сначала создай анкету — нажми «📝 Создать анкету».", reply_markup=back_menu())
        await cb.answer()
        return
    rows = await d.get_matches(cb.from_user.id)
    if not rows:
        await cb.message.answer("Совпадений пока нет. Ставь лайки!", reply_markup=back_menu())
        await cb.answer()
        return
    b = InlineKeyboardBuilder()
    txt = ["💞 <b>Твои совпадения:</b>\n"]
    for m in rows:
        other = m["user2_id"] if m["user1_id"] == cb.from_user.id else m["user1_id"]
        name = m.get("profile_name") or f"ID {other}"
        txt.append(f"• {name}, {m.get('age') or '?'}")
        b.add(InlineKeyboardButton(text=f"💬 {name}", callback_data=f"chat:{other}"))
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    b.adjust(1)
    await cb.message.answer("\n".join(txt), reply_markup=b.as_markup())
    await cb.answer()
