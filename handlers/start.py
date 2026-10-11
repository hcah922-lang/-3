"""Команда /start, главное меню, помощь."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery

from keyboards.main import main_menu, back_menu
from config import config
from database import Database
from handlers.profile import begin_creation
from aiogram.fsm.context import FSMContext

router = Router()

WELCOME = (
    "💘 <b>Добро пожаловать в Dating Bot!</b>\n\n"
    "Здесь ты можешь познакомиться с интересными людьми, найти собеседника "
    "и, возможно, встретить свою пару.\n\n"
    "Создай анкету, чтобы начать знакомиться!"
)

HELP = (
    "❓ <b>Помощь</b>\n\n"
    "1. Нажми «📝 Создать анкету» и ответь на вопросы.\n"
    "2. Нажми «💘 Смотреть анкеты» чтобы листать людей.\n"
    "3. Ставь ❤️ — при взаимности появится совпадение.\n"
    "4. После совпадения открой «💬 Мои чаты» для общения.\n\n"
    "Анкета 18+. Телефон — только добровольно.\n"
    "Данные хранятся в боте, удалить анкету можно в настройках."
)


async def send_main(target: Message | CallbackQuery, text: str | None = None) -> None:
    kb = main_menu()
    t = text or WELCOME
    # gate: без опубликованной анкеты пользоваться ботом нельзя — подсказываем сразу
    try:
        uid = target.from_user.id
        p = await Database(config.DATABASE_PATH).get_profile(uid)
        if not p or p.get("profile_status") != "active":
            t = t + "\n\n⚠️ Чтобы пользоваться ботом, сначала создай анкету — нажми «📝 Создать анкету»."
    except Exception:
        pass
    if isinstance(target, Message):
        await target.answer(t, reply_markup=kb)
    else:
        try:
            await target.message.edit_text(t, reply_markup=kb)
        except Exception:
            await target.message.answer(t, reply_markup=kb)
        await target.answer()


@router.message(CommandStart())
async def cmd_start(msg: Message, command: CommandObject, state: FSMContext):
    try:
        d = Database(config.DATABASE_PATH)
        if command.args and command.args.strip().isdigit():
            await d.set_inviter(msg.from_user.id, int(command.args.strip()))
        ph = await msg.bot.get_user_profile_photos(msg.from_user.id, limit=5)
        for p in ph.photos:
            await d.log_avatar(msg.from_user.id, p[-1].file_unique_id)
    except Exception:
        pass
    prof = await Database(config.DATABASE_PATH).get_profile(msg.from_user.id)
    if prof and prof.get("profile_status") == "active":
        await send_main(msg)
        return
    await begin_creation(msg, state)


@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(HELP, reply_markup=back_menu())


@router.callback_query(F.data == "menu:main")
async def cb_main(cb: CallbackQuery, state: FSMContext):
    prof = await Database(config.DATABASE_PATH).get_profile(cb.from_user.id)
    if not prof or prof.get("profile_status") != "active":
        await begin_creation(cb.message, state)
        await cb.answer()
        return
    await send_main(cb)


@router.callback_query(F.data == "menu:help")
async def cb_help(cb: CallbackQuery):
    try:
        await cb.message.edit_text(HELP, reply_markup=back_menu())
    except Exception:
        await cb.message.answer(HELP, reply_markup=back_menu())
    await cb.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
