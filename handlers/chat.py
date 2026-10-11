"""Чаты между совпавшими пользователями."""
from __future__ import annotations
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from config import config
from database import Database
from keyboards.main import back_menu
from services.messaging import can_chat
from services.security import spam_guard, esc

router = Router()

class ChatFSM(StatesGroup):
    active = State()

def db() -> Database:
    return Database(config.DATABASE_PATH)

@router.callback_query(F.data == "menu:chats")
async def cb_chats(cb: CallbackQuery):
    d = db()
    me = await d.get_profile(cb.from_user.id)
    if not me or me.get("profile_status") != "active":
        await cb.message.answer("⚠️ Сначала создай анкету — нажми «📝 Создать анкету».", reply_markup=back_menu())
        await cb.answer()
        return
    rows = await d.get_matches(cb.from_user.id)
    if not rows:
        await cb.message.answer("Чатов пока нет.", reply_markup=back_menu())
        await cb.answer()
        return
    b = InlineKeyboardBuilder()
    for m in rows:
        other = m["user2_id"] if m["user1_id"] == cb.from_user.id else m["user1_id"]
        name = m.get("profile_name") or f"ID {other}"
        b.add(InlineKeyboardButton(text=f"💬 {name}", callback_data=f"chat:{other}"))
    b.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    b.adjust(1)
    await cb.message.answer("💬 <b>Твои чаты:</b> выбери собеседника.", reply_markup=b.as_markup())
    await cb.answer()

@router.callback_query(F.data.regexp(r"^chat:\d+$"))
async def cb_open_chat(cb: CallbackQuery, state: FSMContext):
    other = int(cb.data.split(":")[1])
    d = db()
    me = await d.get_profile(cb.from_user.id)
    if not me or me.get("profile_status") != "active":
        await cb.answer("Сначала создай анкету.", show_alert=True)
        return
    ok, why = await can_chat(d, cb.from_user.id, other)
    if not ok:
        await cb.answer(why, show_alert=True)
        return
    await state.set_state(ChatFSM.active)
    await state.update_data(peer=other)
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"block:{other}"))
    kb.add(InlineKeyboardButton(text="🔚 Закрыть чат", callback_data="chat:close"))
    kb.add(InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main"))
    kb.adjust(1)
    await cb.message.answer("✉️ Режим чата включён. Пиши сообщения — они уйдут собеседнику от имени бота.\n"
                            "/stop — выйти из чата.", reply_markup=kb.as_markup())
    await cb.answer()

@router.callback_query(F.data == "chat:close")
async def cb_close(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.answer("Чат закрыт.", reply_markup=back_menu())
    await cb.answer()

from aiogram.filters import Command


@router.message(Command("stop"))
async def cmd_stop(msg: Message, state: FSMContext):
    if await state.get_state() == ChatFSM.active:
        await state.clear()
        await msg.answer("Чат закрыт.", reply_markup=back_menu())

def _has_emoji(s: str) -> bool:
    return any(ord(c) > 0x2500 and (0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF
                                    or 0x2B00 <= ord(c) <= 0x2BFF or ord(c) == 0x2764) for c in s)


@router.message(ChatFSM.active)
async def chat_send(msg: Message, state: FSMContext):
    if (msg.text or "").startswith("/"):
        return  # команды не пересылаем
    if not spam_guard.allowed(msg.from_user.id):
        await msg.answer("⏳ Слишком быстро. Подожди секунду.")
        return
    data = await state.get_data()
    peer = data.get("peer")
    if not peer:
        await state.clear()
        return
    d = db()
    ok, why = await can_chat(d, msg.from_user.id, peer)
    if not ok:
        await msg.answer(why)
        await state.clear()
        return
    peer_u = await d.get_user(peer)
    fwd_src: str | None = None
    if msg.forward_origin:
        fo = msg.forward_origin
        ch = getattr(fo, "chat", None)
        if ch is not None:
            fwd_src = "fwd:@" + (ch.username or ch.title or "?")
        else:
            fwd_src = f"fwd:{fo.type}"
    fwd = fwd_src is not None
    try:
        if msg.text:
            await msg.bot.send_message(peer, f"💌 Новое сообщение:\n{esc(msg.text)}")
            await d.log_message(msg.from_user.id, peer, None, "sent", kind="text",
                                length=len(msg.text), is_forward=fwd, has_emoji=_has_emoji(msg.text),
                                extra=fwd_src)
        elif msg.photo:
            await msg.bot.send_photo(peer, msg.photo[-1].file_id, caption="💌 Фото от совпадения")
            await d.log_message(msg.from_user.id, peer, None, "sent", kind="photo",
                                length=len(msg.caption or ""), is_forward=fwd, extra=fwd_src)
        elif msg.video:
            await msg.bot.send_video(peer, msg.video.file_id, caption="💌 Видео от совпадения")
            await d.log_message(msg.from_user.id, peer, None, "sent", kind="video",
                                duration=msg.video.duration or 0, is_forward=fwd, extra=fwd_src)
        elif msg.video_note:
            await msg.bot.send_video_note(peer, msg.video_note.file_id)
            await d.log_message(msg.from_user.id, peer, None, "sent", kind="video_note",
                                duration=msg.video_note.duration or 0)
        elif msg.voice:
            await msg.bot.send_voice(peer, msg.voice.file_id)
            await d.log_message(msg.from_user.id, peer, None, "sent", kind="voice",
                                duration=msg.voice.duration or 0)
        elif msg.sticker:
            await msg.bot.send_sticker(peer, msg.sticker.file_id)
            await d.log_message(msg.from_user.id, peer, None, "sent", kind="sticker",
                                is_forward=fwd, extra=(msg.sticker.set_name or None))
        elif msg.document:
            await msg.bot.send_document(peer, msg.document.file_id,
                                        caption="💌 Файл от совпадения")
            await d.log_message(msg.from_user.id, peer, None, "sent", kind="document",
                                is_forward=fwd, extra=(msg.document.mime_type or None))
        else:
            await msg.answer("Этот тип сообщений не поддерживается.")
            return
        if peer_u and peer_u.get("notify_messages", 1):
            pass  # уведомление уже в самом сообщении
        await d.log_funnel(msg.from_user.id, "chat")
        await msg.answer("✅ Отправлено.")
    except Exception:
        await d.log_message(msg.from_user.id, peer, None, "failed")
        await msg.answer("⚠️ Не удалось доставить. Возможно, собеседник заблокировал бота.")


@router.edited_message(ChatFSM.active)
async def chat_edited(msg: Message, state: FSMContext):
    # тихо: фиксируем только факт правки, без чтения и уведомлений
    try:
        await db().bump_edits(msg.from_user.id)
    except Exception:
        pass
