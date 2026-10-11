from __future__ import annotations
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from config import config
from database import Database
from keyboards.main import back_menu

router = Router()

@router.callback_query(F.data == "menu:likes")
async def cb_likes(cb: CallbackQuery):
    d = Database(config.DATABASE_PATH)
    me = await d.get_profile(cb.from_user.id)
    if not me or me.get("profile_status") != "active":
        await cb.message.answer("⚠️ Сначала создай анкету — нажми «📝 Создать анкету».", reply_markup=back_menu())
        await cb.answer()
        return
    rows = await d.get_likes_to(cb.from_user.id)
    if not rows:
        await cb.message.answer("Пока никто не поставил тебе лайк.", reply_markup=back_menu())
        await cb.answer()
        return
    b = InlineKeyboardBuilder()
    txt = ["❤️ <b>Твои лайки:</b>\n"]
    for r in rows[:20]:
        name = r.get("profile_name") or f"ID {r['from_id']}"
        txt.append(f"• {name}, {r.get('age') or '?'} ({r.get('city') or '?'})")
        b.add(InlineKeyboardButton(text=f"❤️ {name}", callback_data=f"like:{r['from_id']}"))
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    b.adjust(1)
    await cb.message.answer("\n".join(txt), reply_markup=b.as_markup())
    await cb.answer()
