from aiogram.fsm.state import State, StatesGroup


class AdminFSM(StatesGroup):
    password = State()
    search = State()
    edit_target = State()
    edit_name = State()
    broadcast_text = State()
    broadcast_audience = State()
    chat_with = State()
